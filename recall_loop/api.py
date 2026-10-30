import asyncio
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .sample import seed
from .service import MemoryService
from .store import uid


def create_app(directory=None, embeddings=True, demo=None):
    data = Path(directory or os.getenv("RECALL_DATA_DIR", "data")).resolve()
    is_demo = demo if demo is not None else os.getenv("RECALL_DEMO", "0") == "1"
    public_origin = (os.getenv("RECALL_PUBLIC_ORIGIN") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    public_url = urlsplit(public_origin)
    if public_origin and (public_url.scheme not in {"https", "http"} or not public_url.hostname or
                          public_url.path or public_url.query or public_url.fragment or public_url.username):
        raise ValueError("RECALL_PUBLIC_ORIGIN must be one exact HTTP(S) origin without a path or credentials")
    allowed_hosts = {"127.0.0.1", "localhost", "::1", "testserver"}
    if public_url.hostname:
        allowed_hosts.add(public_url.hostname)
    service = MemoryService(data, embeddings)
    token_path = data / "hook-token"
    if not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(32))
    hook_token = token_path.read_text().strip()
    if not is_demo:
        project = service.create_project("Atlas storefront", project="sample-atlas", sample=True)
        seed(service, project)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title="bunch", version="0.1.0", lifespan=lifespan)
    app.state.service = service

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({"detail": "That connection or record already exists."}, status_code=409)

    @app.middleware("http")
    async def isolation(request: Request, call_next):
        if request.url.hostname not in allowed_hosts and request.url.path != "/health":
            return JSONResponse({"detail": "Unrecognized host. Configure the exact public origin for deployment."}, status_code=400)
        origin = request.headers.get("origin")
        allowed_origins = {str(request.base_url).rstrip("/")}
        if public_origin:
            allowed_origins.add(public_origin)
        if origin and origin.rstrip("/") not in allowed_origins:
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
        visitor = request.cookies.get("recall_visitor")
        import re
        if not visitor or not re.fullmatch(r"[a-f0-9]{32}", visitor):
            visitor = secrets.token_hex(16)
        request.state.visitor = visitor
        response = await call_next(request)
        if request.cookies.get("recall_visitor") != visitor:
            response.set_cookie("recall_visitor", visitor, httponly=True, samesite="strict",
                                secure=request.url.scheme == "https", max_age=86400)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    def allow(request, project):
        service.store.project(project)
        if is_demo and not project.startswith(request.state.visitor + ":"):
            raise HTTPException(404, "Project not found")

    def hook_auth(request):
        if is_demo or not secrets.compare_digest(request.headers.get("x-recall-token", ""), hook_token):
            raise HTTPException(403, "Local integration token required")

    @app.get("/health")
    def health():
        return {"status": "ok", "index": "qdrant-edge", "embeddings": service.index.embedding_state,
                "embedding_error": service.index.embedding_error, "demo": is_demo,
                "extraction_enabled": bool(os.getenv("OPENAI_API_KEY")) and not is_demo}

    @app.get("/api/projects")
    def projects(request: Request):
        if is_demo:
            project = request.state.visitor + ":atlas"
            service.create_project("Atlas storefront", project=project, sample=True)
            seed(service, project)
            return service.store.rows("SELECT * FROM projects WHERE id=?", (project,))
        return service.store.rows("SELECT * FROM projects ORDER BY sample DESC,name")

    class ProjectIn(BaseModel):
        name: str = Field(min_length=1, max_length=100)
        root: str = Field(default="", max_length=1000)

    @app.post("/api/projects")
    def add_project(body: ProjectIn):
        if is_demo:
            raise HTTPException(403, "Hosted demo uses isolated sample projects")
        return {"id": service.create_project(body.name, body.root)}

    @app.get("/api/graph")
    def graph(request: Request, project: str, limit: int = Query(200, ge=1, le=500),
              kind: str | None = None, status: str | None = None, session: str | None = None,
              since: str | None = None, focus: str | None = None):
        allow(request, project)
        return service.graph(project, limit, kind, status, session, since, focus)

    @app.get("/api/graph/events")
    async def stream(request: Request, project: str):
        allow(request, project)
        async def updates():
            last = -1
            while not await request.is_disconnected():
                if service.version != last:
                    last = service.version
                    yield f"id: {last}\ndata: {json.dumps({'version': last})}\n\n"
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(updates(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    class SearchIn(BaseModel):
        project: str
        query: str = Field(min_length=1, max_length=1000)
        limit: int = Field(default=5, ge=1, le=5)

    @app.post("/api/memories/search")
    def search(request: Request, body: SearchIn):
        allow(request, body.project)
        return service.search(body.project, body.query, body.limit)

    @app.get("/api/nodes/{node}")
    def node_detail(request: Request, node: str, project: str):
        allow(request, project)
        return service.detail(node, project)

    class EvidenceIn(BaseModel):
        event_id: str = Field(min_length=1, max_length=200)
        quote: str = Field(min_length=1, max_length=5000)

    class MemoryIn(BaseModel):
        project: str
        label: str = Field(min_length=1, max_length=160)
        body: str = Field(min_length=1, max_length=5000)
        kind: str = "decision"
        evidence: list[EvidenceIn] = Field(default_factory=list, max_length=10)
        session: str | None = None

    @app.post("/api/memories")
    def memory(request: Request, body: MemoryIn):
        allow(request, body.project)
        return service.create_memory(body.project, body.label, body.body, body.kind,
                                     [e.model_dump() for e in body.evidence], body.session)

    @app.patch("/api/memories/{memory}")
    def edit_memory(request: Request, memory: str, body: dict):
        project = body.get("project", "")
        allow(request, project)
        allowed = {"project", "label", "body", "status", "kind"}
        if set(body) - allowed or any(not isinstance(v, str) for v in body.values()):
            raise HTTPException(422, "Invalid memory fields")
        if len(body.get("body", "")) > 5000 or len(body.get("label", "")) > 160:
            raise HTTPException(422, "Memory is too long")
        return service.edit_memory(project, memory, body)

    @app.delete("/api/memories/{memory}")
    def delete_memory(request: Request, memory: str, project: str):
        allow(request, project)
        service.edit_memory(project, memory, {"status": "deleted"})
        return {"ok": True}

    @app.post("/api/memories/{memory}/supersede")
    def supersede(request: Request, memory: str, body: MemoryIn):
        allow(request, body.project)
        return service.supersede(body.project, memory, body.label, body.body)

    class RelationshipIn(BaseModel):
        project: str
        source: str
        target: str
        kind: str

    @app.post("/api/relationships")
    def relationship(request: Request, body: RelationshipIn):
        allow(request, body.project)
        return {"id": service.relationship(body.project, body.source, body.target, body.kind)}

    @app.patch("/api/relationships/{edge}")
    def edit_relationship(request: Request, edge: str, body: dict):
        project = body.get("project", "")
        allow(request, project)
        if body.get("kind") not in {"related_to", "prerequisite_for", "contradicts"}:
            raise HTTPException(422, "Unsupported relationship")
        service.change_relationship(project, edge, body["kind"])
        return {"ok": True}

    @app.delete("/api/relationships/{edge}")
    def delete_relationship(request: Request, edge: str, project: str):
        allow(request, project)
        service.change_relationship(project, edge)
        return {"ok": True}

    @app.post("/api/undo")
    def undo(request: Request, body: dict):
        project = body.get("project", "")
        allow(request, project)
        return {"label": service.undo(project)}

    @app.put("/api/layout")
    def layout(request: Request, body: dict):
        project = body.get("project", "")
        allow(request, project)
        positions = body.get("positions", [])
        if not isinstance(positions, list) or len(positions) > 500:
            raise HTTPException(422, "Layout limit exceeded")
        import math
        with service.store.transaction() as db:
            for position in positions:
                service.store.node(position["id"], project)
                values = [position.get(k, 0) for k in ("x", "y", "z")]
                if any(not isinstance(v, (float, int)) or not math.isfinite(v) or abs(v) > 1e6 for v in values):
                    raise HTTPException(422, "Invalid coordinates")
                db.execute("INSERT OR REPLACE INTO layouts VALUES(?,?)",
                           (position["id"], json.dumps({**dict(zip(("x", "y", "z"), values)),
                                                        "pinned": bool(position.get("pinned"))})))
        return {"ok": True}

    @app.delete("/api/layout")
    def reset_layout(request: Request, project: str):
        allow(request, project)
        with service.store.transaction() as db:
            db.execute("DELETE FROM layouts WHERE node IN (SELECT id FROM nodes WHERE project=?)", (project,))
        service.changed()
        return {"ok": True}

    class FeedbackIn(BaseModel):
        project: str
        retrieval_id: str
        memory_id: str
        helpful: bool
        evidence: str = Field(default="", max_length=2000)

    @app.post("/api/feedback")
    def feedback(request: Request, body: FeedbackIn):
        allow(request, body.project)
        service.feedback(body.project, body.retrieval_id, body.memory_id, body.helpful, body.evidence)
        return {"ok": True}

    @app.get("/api/status")
    def status(request: Request, project: str):
        allow(request, project)
        return {"jobs": service.store.rows("SELECT * FROM jobs WHERE project=? ORDER BY created DESC LIMIT 10", (project,)),
                "budget": {"limit": service.cap, "committed": service.store.rows(
                    "SELECT COALESCE(SUM(CASE WHEN status='done' THEN actual ELSE reserved END),0) amount FROM budget")[0]["amount"]},
                "pending_index": service.store.rows("SELECT COUNT(*) n FROM outbox WHERE project=?", (project,))[0]["n"]}

    @app.post("/api/capture")
    def capture(request: Request, body: dict):
        hook_auth(request)
        required = {"project", "session", "role", "text"}
        if not required <= set(body) or any(not isinstance(body[k], str) for k in required):
            raise HTTPException(422, "Invalid capture event")
        return {"id": service.capture(body["project"], body["session"], body["role"], body["text"],
                                       body.get("source", "Codex hook"), body.get("event_id"))}

    @app.post("/api/import")
    def import_trace(request: Request, body: dict):
        hook_auth(request)
        count = service.import_transcript(body["project"], body["session"], body["path"])
        return {"events": count}

    @app.post("/api/extract")
    def extract(request: Request, body: dict):
        hook_auth(request)
        return {"job": service.enqueue_extract(body["project"], body["session"])}

    @app.post("/api/sample/replay")
    def replay(request: Request, body: dict):
        project = body.get("project", "")
        allow(request, project)
        if not service.store.project(project)["sample"]:
            raise HTTPException(400, "Replay is available only in sample projects")
        sid = uid()
        quote = ("We fixed the race by awaiting session persistence before navigation. "
                 "The timeout workaround was unreliable; use an explicit ordering guarantee.")
        eid = service.capture(project, sid, "user", quote, "Synthetic extraction replay")
        return service.create_memory(project, "Await persistence, then navigate", quote, "correction",
                                     [{"event_id": eid, "quote": quote}], sid)

    static = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if static.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")
        @app.get("/")
        def homepage():
            return FileResponse(static / "index.html")
    else:
        @app.get("/")
        def homepage():
            return {"message": "Build the frontend with npm run build, or run its Vite dev server."}
    return app


def app_factory():
    return create_app()
