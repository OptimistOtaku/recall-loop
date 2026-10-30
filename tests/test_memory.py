import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from recall_loop.api import create_app
from recall_loop.service import MemoryService
from recall_loop.privacy import redact, visible_messages


@pytest.fixture
def service(tmp_path):
    s = MemoryService(tmp_path, embeddings=False)
    s.create_project("Real project", project="p")
    yield s
    s.close()


def lesson(s, title, text):
    return s.create_memory("p", title, text, "decision")


def test_evidence_and_restart(service, tmp_path):
    memory = lesson(service, "Await persistence", "Await session persistence before navigation.")
    assert service.detail(memory["id"], "p")["evidence"][0]["quote"] == memory["body"]
    service.close()
    reopened = MemoryService(tmp_path, embeddings=False)
    assert reopened.search("p", "session persistence")["results"][0]["id"] == memory["id"]
    reopened.close()


def test_graph_prerequisite_changes_recall_and_undo(service):
    seed = lesson(service, "Callback race", "The callback race requires awaiting persistence.")
    prerequisite = lesson(service, "Special prerequisite", "Prepare the configuration using the documented setup.")
    for i in range(7):
        lesson(service, f"Callback race reference {i}", "Another callback race observation.")
    before = service.search("p", "callback race")
    assert prerequisite["id"] not in [n["id"] for n in before["results"]]
    service.relationship("p", prerequisite["id"], seed["id"], "prerequisite_for")
    after = service.search("p", "callback race")
    found = next(n for n in after["results"] if n["id"] == prerequisite["id"])
    assert found["path"]["relationship"] == "prerequisite_for"
    service.undo("p")
    assert prerequisite["id"] not in [n["id"] for n in service.search("p", "callback race")["results"]]


def test_same_project_and_non_memory_connections(service):
    a = lesson(service, "First", "First lesson.")
    service.create_project("Other", project="other")
    b = service.create_memory("other", "Other", "Other project lesson.")
    with pytest.raises(ValueError):
        service.relationship("p", a["id"], b["id"], "related_to")
    with pytest.raises(ValueError):
        service.relationship("p", a["id"], a["id"], "related_to")
    assert not service.search("p", "Other project")["results"]


def test_supersede_delete_undo_and_evidence(service):
    a = lesson(service, "Timeout workaround", "Timeout workaround to avoid racing.")
    b = service.supersede("p", a["id"], "Await the operation", "Await persistence explicitly instead of racing.")
    assert service.store.node(a["id"])["status"] == "superseded"
    assert a["id"] not in [n["id"] for n in service.search("p", "racing")["results"]]
    assert service.detail(b["id"], "p")["evidence"][0]["source"] == "explicit superseding correction"
    service.edit_memory("p", b["id"], {"status": "deleted"})
    assert b["id"] not in [n["id"] for n in service.search("p", "persistence")["results"]]
    service.undo("p")
    assert service.store.node(b["id"])["status"] == "active"


def test_claim_edits_have_new_source_and_revision(service):
    a = lesson(service, "Initial", "First assertion.")
    result = service.edit_memory("p", a["id"], {"body": "Corrected assertion."})
    assert result["props"]["revision"] == 2
    assert result["evidence"][0]["quote"] == "Corrected assertion."
    assert result["props"]["history"][0]["body"] == "First assertion."


def test_tentative_not_recalled(service):
    m = service.create_memory("p", "Unknown", "An unverified interpretation.", tentative=True)
    assert m["id"] not in [n["id"] for n in service.search("p", "interpretation")["results"]]


def test_import_idempotent_partial_line_and_redaction(service, tmp_path):
    path = tmp_path / "trace.jsonl"
    messages = [
        {"type": "response_item", "payload": {"type": "message", "role": "system", "content": [{"type": "input_text", "text": "DO NOT CAPTURE"}]}},
        {"type": "response_item", "payload": {"type": "reasoning", "summary": "DO NOT CAPTURE"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Use token=abcdef0123456789 carefully."}]}},
    ]
    path.write_bytes(("\n".join(json.dumps(m) for m in messages) + "\n" + '{"type":').encode())
    assert service.import_transcript("p", "s", path) == 1
    assert service.import_transcript("p", "s", path) == 0
    events = service.store.rows("SELECT * FROM events")
    assert len(events) == 1
    assert "abcdef0123456789" not in events[0]["text"]
    assert "DO NOT CAPTURE" not in events[0]["text"]


def test_evidence_quotes_cannot_be_invented(service):
    with pytest.raises(ValueError):
        service.create_memory("p", "Invalid", "Claim", evidence=[{"event_id": "missing", "quote": "invented"}])


def test_no_api_key_preserves_capture(service, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service.capture("p", "s", "user", "Remember the actual correction.")
    job = service.enqueue_extract("p", "s")
    service.executor.submit(lambda: None).result()
    assert service.store.rows("SELECT * FROM jobs WHERE id=?", (job,))[0]["status"] == "paused"
    assert len(service.store.rows("SELECT * FROM events")) == 1


def test_feedback_requires_actual_retrieval(service):
    a = lesson(service, "Useful", "Useful configuration lesson.")
    with pytest.raises(ValueError):
        service.feedback("p", "fake", a["id"], True)
    result = service.search("p", "configuration")
    service.feedback("p", result["retrieval_id"], a["id"], True, "User confirmed it helped.")
    assert len(service.store.rows("SELECT * FROM feedback")) == 1


def test_demo_isolation_and_integration_boundary(tmp_path):
    app = create_app(tmp_path, embeddings=False, demo=True)
    with TestClient(app) as one, TestClient(app) as two:
        p1 = one.get("/api/projects").json()[0]["id"]
        p2 = two.get("/api/projects").json()[0]["id"]
        assert p1 != p2
        assert one.get("/api/graph", params={"project": p2}).status_code == 404
        assert one.post("/api/import", json={"path": "private.jsonl"}).status_code == 403
        assert one.post("/api/capture", json={}).status_code == 403
        assert one.post("/api/memories", json={"project": p1, "label": "Own", "body": "Isolated visitor correction."}).status_code == 200
        assert not any(n["label"] == "Own" for n in two.get("/api/graph", params={"project": p2}).json()["nodes"])


def test_layout_reset_preserves_knowledge(tmp_path):
    app = create_app(tmp_path, embeddings=False, demo=False)
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Actual project"}).json()["id"]
        m = client.post("/api/memories", json={"project": project, "label": "Pinned", "body": "A pinned lesson."}).json()
        assert client.put("/api/layout", json={"project": project, "positions": [{"id": m["id"], "x": 1, "y": 2, "z": 3, "pinned": True}]}).status_code == 200
        assert client.get("/api/nodes/"+m["id"], params={"project": project}).json()["position"]["pinned"]
        client.delete("/api/layout", params={"project": project})
        assert client.get("/api/nodes/"+m["id"], params={"project": project}).json()["body"] == "A pinned lesson."


def test_cross_origin_mutation_is_rejected(tmp_path):
    app = create_app(tmp_path, embeddings=False)
    with TestClient(app) as client:
        assert client.post("/api/projects", json={"name": "Evil"}, headers={"origin": "https://untrusted.test"}).status_code == 403


def mock_extractor(monkeypatch, build):
    from types import SimpleNamespace
    import openai
    import tiktoken
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-credential")
    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: SimpleNamespace(encode=lambda s: list(s.encode())))
    class FakeClient:
        calls = 0
        def __init__(self, **kwargs):
            self.responses = self
        def create(self, **kwargs):
            FakeClient.calls += 1
            return build(kwargs)
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    return FakeClient


def test_extraction_quote_validation_and_processed_checkpoint(service, monkeypatch):
    from types import SimpleNamespace
    event = service.capture("p", "session", "user", "Await persistence before redirecting.")
    def response(kwargs):
        payload = {"lessons": [
            {"title":"Await persistence","body":"Await persistence before redirecting.","kind":"correction",
             "tentative":False,"event_id":event,"quote":"Await persistence before redirecting."},
            {"title":"Invented","body":"An unsupported interpretation.","kind":"decision",
             "tentative":False,"event_id":event,"quote":"This quote was never said."},
        ]}
        return SimpleNamespace(output_text=json.dumps(payload),
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50))
    client = mock_extractor(monkeypatch, response)
    service.enqueue_extract("p", "session")
    service.executor.submit(lambda: None).result()
    assert [n["label"] for n in service.store.nodes("p") if n["type"]=="memory"] == ["Await persistence"]
    assert service.search("p","persistence")["results"][0]["props"]["classification"] == "source_supported"
    service.enqueue_extract("p", "session")
    service.executor.submit(lambda: None).result()
    assert client.calls == 1


def test_budget_blocks_before_api_call(service, monkeypatch):
    service.capture("p", "session", "user", "A useful decision to preserve.")
    client = mock_extractor(monkeypatch, lambda kwargs: pytest.fail("Budget must block this call"))
    service.cap = 0.000001
    job = service.enqueue_extract("p", "session")
    service.executor.submit(lambda: None).result()
    assert client.calls == 0
    assert "budget" in service.store.rows("SELECT * FROM jobs WHERE id=?", (job,))[0]["detail"]


def test_failed_call_keeps_reservation_and_source(service, monkeypatch):
    service.capture("p", "session", "user", "A useful decision to preserve.")
    def fail(kwargs):
        raise RuntimeError("Simulated connection loss after dispatch")
    mock_extractor(monkeypatch, fail)
    job = service.enqueue_extract("p", "session")
    service.executor.submit(lambda: None).result()
    assert service.store.rows("SELECT * FROM budget")[0]["reserved"] > 0
    assert service.store.rows("SELECT * FROM jobs WHERE id=?", (job,))[0]["status"] == "paused"
    assert len(service.store.rows("SELECT * FROM events")) == 1


def test_undo_with_pinned_layout_preserves_foreign_keys(service):
    a = lesson(service, "Pinned", "A pinned source lesson.")
    with service.store.transaction() as db:
        db.execute("INSERT INTO layouts VALUES(?,?)", (a["id"], json.dumps({"x":1,"y":2,"z":3,"pinned":True})))
    service.edit_memory("p", a["id"], {"body":"Updated pinned source lesson."})
    service.undo("p")
    assert service.store.node(a["id"])["body"] == "A pinned source lesson."
    assert service.store.node(a["id"])["position"]["pinned"]


def test_deleted_vectors_do_not_starve_active_search(service):
    for i in range(35):
        a = lesson(service, f"Deleted {i}", "Shared search identifier.")
        service.edit_memory("p", a["id"], {"status":"deleted"})
    active = lesson(service, "Still active", "Shared search identifier.")
    assert service.search("p", "shared search identifier")["results"][0]["id"] == active["id"]


def test_contradictions_are_warnings(service):
    a = lesson(service, "Token policy", "Token policy for authentication.")
    b = lesson(service, "Alternate token policy", "An alternate token policy is under discussion.")
    service.relationship("p", a["id"], b["id"], "contradicts")
    assert service.search("p", "token policy")["warnings"]


def test_unsupported_transcript_message_format_is_visible(service, tmp_path):
    path = tmp_path / "trace.jsonl"
    path.write_text(json.dumps({"type":"response_item","payload":{"type":"message","role":"user","content":"changed format"}})+"\n")
    with pytest.raises(ValueError, match="Unsupported Codex"):
        service.import_transcript("p", "s", path)
    assert not service.store.rows("SELECT * FROM cursors")


def test_tool_capture_excludes_memory_retrieval_feedback_loops(service, tmp_path):
    records = [
        {"type":"response_item","payload":{"type":"function_call","name":"exec_command","call_id":"shell","arguments":"test"}},
        {"type":"response_item","payload":{"type":"function_call_output","call_id":"shell","output":"Regression test: exit code 0"}},
        {"type":"response_item","payload":{"type":"function_call","name":"mcp__recall__search_memory","call_id":"memory","arguments":"{}"}},
        {"type":"response_item","payload":{"type":"function_call_output","call_id":"memory","output":'{"retrieval_id":"old","guidance":"Historical evidence"}'}},
    ]
    path=tmp_path/"trace.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records)+"\n")
    assert service.import_transcript("p","s",path)==1
    assert service.store.rows("SELECT * FROM events")[0]["text"] == "Regression test: exit code 0"


def test_assistant_only_claims_stay_tentative(service, monkeypatch):
    from types import SimpleNamespace
    event = service.capture("p","s","assistant","I think a timeout might fix the issue.")
    def response(kwargs):
        return SimpleNamespace(output_text=json.dumps({"lessons":[{"title":"Timeout hypothesis","body":"A timeout might fix the issue.",
            "kind":"decision","tentative":False,"event_id":event,"quote":"I think a timeout might fix the issue."}]}),
            usage=SimpleNamespace(input_tokens=100,output_tokens=50))
    mock_extractor(monkeypatch,response)
    service.enqueue_extract("p","s")
    service.executor.submit(lambda:None).result()
    assert service.store.nodes("p")[-1]["status"] == "tentative"
    assert not service.search("p","timeout")["results"]


def test_exact_public_origin_works_behind_proxy_without_trusting_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("RECALL_PUBLIC_ORIGIN", "https://recall.example.test")
    app = create_app(tmp_path, embeddings=False, demo=True)
    with TestClient(app, base_url="http://recall.example.test") as client:
        p = client.get("/api/projects").json()[0]["id"]
        body = {"project":p,"label":"Public demo","body":"A sample assertion."}
        assert client.post("/api/memories", json=body, headers={"origin":"https://recall.example.test"}).status_code == 200
        assert client.post("/api/memories", json=body, headers={"origin":"https://evil.test","x-forwarded-host":"evil.test","x-forwarded-proto":"https"}).status_code == 403


def test_unknown_host_cannot_read_local_memory(tmp_path):
    app = create_app(tmp_path, embeddings=False)
    with TestClient(app, base_url="http://untrusted.test") as client:
        assert client.get("/api/projects").status_code == 400

def test_explicit_source_roles_are_not_mislabeled_as_user_assertions(service):
    tool = service.capture('p', 'real-outcome', 'tool', '3 passed, 0 failed', source='Actual terminal outcome')
    memory = service.create_memory('p', 'Observed regression result', 'The regression command reported three passing checks.', 'procedure',
                                   [{'event_id':tool,'quote':'3 passed, 0 failed'}], 'real-outcome')
    assert memory['props']['classification'] == 'source_supported'
    assistant = service.capture('p', 'uncertain-claim', 'assistant', 'I think the issue is fixed.')
    guess = service.create_memory('p', 'Unverified assistant claim', 'The issue might be fixed.', 'question',
                                  [{'event_id':assistant,'quote':'I think the issue is fixed.'}], 'uncertain-claim')
    assert guess['status'] == 'tentative'
    assert guess['props']['classification'] == 'inferred'

def test_detail_names_connections_outside_the_visible_snapshot(service):
    a=service.create_memory('p','Graph reconciliation','Keep live node identity during refresh.')
    b=service.create_memory('p','Canonical pin constraints','Apply saved pins explicitly.')
    service.relationship('p',a['id'],b['id'],'prerequisite_for')
    edge=service.detail(a['id'],'p')['relationships'][0]
    assert edge['source_label']=='Graph reconciliation'
    assert edge['target_label']=='Canonical pin constraints'
