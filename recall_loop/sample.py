"""Explicitly synthetic fixtures. They are never reported as measured real-world results."""
from .store import now, uid

LESSONS = [
    ("Persist the session before redirecting", "The sign-in callback must await session persistence before redirecting to /workspace. Otherwise the first page load appears signed out.", "correction", "src/auth/session.ts"),
    ("Invalidate refresh tokens on logout", "Logout must revoke the server refresh token and clear the local session. Clearing local state alone leaves the refresh path active.", "decision", "src/auth/logout.ts"),
    ("The timeout fix did not solve the race", "Adding a 500 ms timeout hid the sign-in race on one machine. It did not establish an ordering guarantee. Await persistence instead.", "failed_approach", "src/auth/session.ts"),
    ("Run the callback regression test", "After changing authentication, run the callback regression that checks session persistence happens before navigation.", "procedure", "tests/auth-callback.test.ts"),
    ("Keep migrations in timestamp order", "Create a new migration for schema changes. Editing an already applied migration made the local database disagree with deployed instances.", "correction", "db/migrations/"),
    ("Use idempotency keys for checkout", "A retry of POST /checkout must reuse its idempotency key. The payment operation must not be repeated after a network timeout.", "decision", "src/api/checkout.ts"),
    ("Replay the double-click checkout case", "The checkout regression should submit twice with the same idempotency key and assert that exactly one order is created.", "procedure", "tests/checkout.test.ts"),
    ("A passing build is not a passing checkout", "The TypeScript build passed while the checkout request still returned a 409. Verify the user workflow as well as the build command.", "failed_approach", "src/api/checkout.ts"),
    ("Keep customer records out of logs", "Log the request ID and error category. Do not log customer emails, tokens, or the full checkout payload.", "decision", "src/lib/logger.ts"),
    ("Cache keys must include the workspace", "Prefix customer-cache keys with workspace_id. Otherwise switching workspaces can display stale data from another workspace.", "correction", "src/cache/customers.ts"),
    ("Validate environment variables on startup", "Fail startup with the missing variable name if required configuration is absent. Never include the variable value in the error.", "procedure", "src/config.ts"),
    ("Use optimistic updates with rollback", "The task board can move a card immediately, but it must restore the previous column if persistence fails.", "decision", "src/board/move.ts"),
    ("Check keyboard navigation in dialogs", "Test the connection dialog using only Tab, Enter, and Escape. Restore focus to the opening button when it closes.", "procedure", "src/components/Dialog.tsx"),
    ("Open question: refresh in another tab", "We have not verified whether signing out in one browser tab invalidates the displayed session in a second tab.", "question", "src/auth/broadcast.ts"),
    ("Do not mutate stored graph snapshots", "The force graph mutates node coordinates. Give it stable render objects instead of canonical API records.", "correction", "src/graph/Graph.tsx"),
    ("Profile labels before changing the engine", "Too many visible text labels can dominate the graph frame time. Label the selected neighborhood before replacing the renderer.", "procedure", "src/graph/labels.ts"),
]


def seed(service, project, name="Atlas storefront"):
    if service.store.rows("SELECT id FROM nodes WHERE project=? LIMIT 1", (project,)):
        return
    sessions, files, memories = [], {}, []
    with service.store.transaction() as db:
        for i, title in enumerate(["Authentication race", "Checkout reliability", "Workspace isolation", "Graph interactions"]):
            sessions.append(service.store.put_node(db, project, "session", title,
                "Synthetic sample session. Use Replay to inspect how its lessons connect.",
                props={"sample": True, "harness": "Codex", "duration": f"{12+i*7} min"}))
        for i, (title, body, kind, file) in enumerate(LESSONS):
            sid = sessions[(i // 4) % len(sessions)]
            eid = uid()
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                       (eid, project, sid, "user", body, now(), "Synthetic sample fixture"))
            mid = service.store.put_node(db, project, "memory", title, body, kind,
                {"evidence": [{"event_id": eid, "quote": body}], "classification": "sample_user_stated",
                 "revision": 1, "sample": True, "applicability": file})
            memories.append(mid)
            service.store.put_edge(db, project, mid, sid, "derived_from")
            if file not in files:
                files[file] = service.store.put_node(db, project, "artifact", file.split("/")[-1] or file,
                                                      file, props={"path": file, "sample": True})
            service.store.put_edge(db, project, mid, files[file], "references")
        for i, text in enumerate(["Callback ordering asserted", "One order created", "Workspace switch checked", "Keyboard path reviewed"]):
            outcome = service.store.put_node(db, project, "outcome", text,
                "Illustrative sample outcome. This is not a measured RecallLoop evaluation.",
                props={"sample": True, "classification": "sample_outcome"})
            service.store.put_edge(db, project, memories[i * 4], outcome, "observed_outcome")
        service.store.put_edge(db, project, memories[3], memories[0], "prerequisite_for", "user")
        service.store.put_edge(db, project, memories[6], memories[5], "prerequisite_for", "user")
        service.store.put_edge(db, project, memories[0], memories[2], "supersedes")
        db.execute("UPDATE nodes SET status='superseded' WHERE id=?", (memories[2],))
        service.store.put_edge(db, project, memories[8], memories[10], "related_to", "user")
    service.sync()
    service.changed()
