from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


class Store:
    """SQLite is authoritative; the vector index is a rebuildable projection."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT, root TEXT, sample INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY, project TEXT REFERENCES projects(id), type TEXT,
          label TEXT, kind TEXT, body TEXT, status TEXT, created TEXT, props TEXT);
        CREATE INDEX IF NOT EXISTS nodes_project ON nodes(project);
        CREATE TABLE IF NOT EXISTS edges(id TEXT PRIMARY KEY, project TEXT REFERENCES projects(id),
          source TEXT REFERENCES nodes(id), target TEXT REFERENCES nodes(id), kind TEXT, origin TEXT, created TEXT,
          UNIQUE(project,source,target,kind));
        CREATE TABLE IF NOT EXISTS layouts(node TEXT PRIMARY KEY REFERENCES nodes(id), position TEXT);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, project TEXT REFERENCES projects(id), session TEXT,
          role TEXT, text TEXT, created TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS cursors(path TEXT PRIMARY KEY, offset INTEGER);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, label TEXT, snapshot TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS outbox(node TEXT PRIMARY KEY, project TEXT);
        CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY, project TEXT, retrieval TEXT, memory TEXT,
          helpful INTEGER, evidence TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS retrievals(id TEXT PRIMARY KEY, project TEXT, query TEXT, memories TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project TEXT, status TEXT, detail TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS budget(id TEXT PRIMARY KEY, reserved REAL, actual REAL, status TEXT);
        CREATE TABLE IF NOT EXISTS processed_events(event TEXT PRIMARY KEY REFERENCES events(id), job TEXT);
        CREATE TABLE IF NOT EXISTS capture_tools(path TEXT, call_id TEXT, name TEXT, PRIMARY KEY(path,call_id));
        """)
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self.db
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def rows(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def project(self, project):
        rows = self.rows("SELECT * FROM projects WHERE id=?", (project,))
        if not rows:
            raise ValueError("Project not found")
        return rows[0]

    def node(self, node_id, project=None):
        rows = self.rows("SELECT * FROM nodes WHERE id=?", (node_id,))
        if not rows or (project and rows[0]["project"] != project):
            raise ValueError("Node not found in this project")
        node = rows[0]
        node["props"] = json.loads(node["props"])
        layout = self.rows("SELECT position FROM layouts WHERE node=?", (node_id,))
        if layout:
            node["position"] = json.loads(layout[0]["position"])
        return node

    def nodes(self, project, include_deleted=False):
        query = "SELECT id FROM nodes WHERE project=?"
        if not include_deleted:
            query += " AND status!='deleted'"
        return [self.node(r["id"]) for r in self.rows(query, (project,))]

    def snapshot(self, db, project, label):
        data = {
            "nodes": [dict(r) for r in db.execute("SELECT * FROM nodes WHERE project=?", (project,))],
            "edges": [dict(r) for r in db.execute("SELECT * FROM edges WHERE project=?", (project,))],
            "layouts": [dict(r) for r in db.execute(
                "SELECT * FROM layouts WHERE node IN (SELECT id FROM nodes WHERE project=?)", (project,))],
        }
        db.execute("INSERT INTO audit(project,label,snapshot,created) VALUES(?,?,?,?)",
                   (project, label, json.dumps(data), now()))
        db.execute("DELETE FROM audit WHERE project=? AND id NOT IN "
                   "(SELECT id FROM audit WHERE project=? ORDER BY id DESC LIMIT 20)", (project, project))

    def put_node(self, db, project, type, label, body="", kind="", props=None, node_id=None, status="active"):
        node_id = node_id or uid()
        db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?)",
                   (node_id, project, type, label, kind, body, status, now(), json.dumps(props or {})))
        if type == "memory":
            db.execute("INSERT OR REPLACE INTO outbox VALUES(?,?)", (node_id, project))
        return node_id

    def put_edge(self, db, project, source, target, kind, origin="system"):
        if source == target:
            raise ValueError("A node cannot connect to itself")
        for node in (source, target):
            r = db.execute("SELECT project,status FROM nodes WHERE id=?", (node,)).fetchone()
            if not r or r["project"] != project or r["status"] == "deleted":
                raise ValueError("Connections must stay within one project")
        edge_id = uid()
        db.execute("INSERT OR IGNORE INTO edges VALUES(?,?,?,?,?,?,?)",
                   (edge_id, project, source, target, kind, origin, now()))
        row = db.execute("SELECT id FROM edges WHERE project=? AND source=? AND target=? AND kind=?",
                         (project, source, target, kind)).fetchone()
        return row["id"]

    def undo(self, project):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM audit WHERE project=? ORDER BY id DESC LIMIT 1", (project,)).fetchone()
            if not row:
                raise ValueError("There are no edits to undo")
            snapshot = json.loads(row["snapshot"])
            old_ids = {r["id"] for r in snapshot["nodes"]}
            current = [dict(r) for r in db.execute("SELECT id,type FROM nodes WHERE project=?", (project,))]
            # Keep immutable source events. Hide nodes created by the reverted edit.
            for node in current:
                if node["id"] not in old_ids:
                    db.execute("UPDATE nodes SET status='deleted' WHERE id=?", (node["id"],))
                if node["type"] == "memory":
                    db.execute("INSERT OR REPLACE INTO outbox VALUES(?,?)", (node["id"], project))
            db.execute("DELETE FROM edges WHERE project=?", (project,))
            for node in snapshot["nodes"]:
                columns = list(node)
                db.execute("INSERT INTO nodes(" + ",".join(columns) + ") VALUES(" +
                           ",".join("?" for _ in columns) + ") ON CONFLICT(id) DO UPDATE SET " +
                           ",".join(c + "=excluded." + c for c in columns if c != "id"), tuple(node.values()))
            for edge in snapshot["edges"]:
                db.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", tuple(edge.values()))
            db.execute("DELETE FROM layouts WHERE node IN (SELECT id FROM nodes WHERE project=?)", (project,))
            for layout in snapshot["layouts"]:
                db.execute("INSERT INTO layouts VALUES(?,?)", (layout["node"], layout["position"]))
            db.execute("DELETE FROM audit WHERE id=?", (row["id"],))
            return row["label"]
