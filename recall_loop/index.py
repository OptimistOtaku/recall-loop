from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from qdrant_edge import (
    Bm25, Bm25Config, Distance, EdgeConfig, EdgeShard, EdgeSparseVectorParams,
    EdgeVectorParams, Modifier, Point, Query, QueryRequest, UpdateOperation, Filter, FieldCondition, MatchValue,
)

log = logging.getLogger(__name__)


class MemoryIndex:
    def __init__(self, directory: Path, embeddings=True):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.shards = {}
        self.bm25 = Bm25(Bm25Config(language="english"))
        self.model = None
        self.embedding_state = "loading" if embeddings else "disabled"
        self.embedding_error = None
        self.embedding_enabled = embeddings

    def load_embeddings(self):
        if not self.embedding_enabled:
            return
        try:
            from fastembed import TextEmbedding
            self.model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5",
                                       cache_dir=os.getenv("RECALL_MODEL_CACHE", str(self.directory.parent / "models")), threads=2)
            self.embedding_state = "ready"
        except Exception as exc:
            log.warning("Local embeddings unavailable: %s", type(exc).__name__)
            self.embedding_state = "unavailable"
            self.embedding_error = "Embedding model could not be loaded. Keyword retrieval remains available."

    def shard(self, project):
        with self.lock:
            if project not in self.shards:
                import hashlib
                path = self.directory / hashlib.sha256(project.encode()).hexdigest()[:24]
                if path.exists() and any(path.iterdir()):
                    self.shards[project] = EdgeShard.load(str(path))
                else:
                    self.shards[project] = EdgeShard.create(str(path), EdgeConfig(
                        vectors={"dense": EdgeVectorParams(size=384, distance=Distance.Cosine)},
                        sparse_vectors={"text": EdgeSparseVectorParams(modifier=Modifier.Idf)},
                        max_search_threads=2,
                    ))
            return self.shards[project]

    def upsert(self, node):
        text = f"{node['label']}\n{node['body']}\n{node['props'].get('applicability', '')}"
        vectors = {"text": self.bm25.embed_document(text)}
        if self.model is not None:
            vectors["dense"] = list(self.model.embed([text]))[0].tolist()
        with self.lock:
            self.shard(node["project"]).update(UpdateOperation.upsert_points([
                Point(id=node["id"], vector=vectors,
                      payload={"status": node["status"], "kind": node["kind"]})
            ]))

    def rank(self, project, query, limit=30):
        with self.lock:
            shard = self.shard(project)
            active_filter = Filter(must=[FieldCondition(key="status", match=MatchValue(value="active"))])
            sparse = shard.query(QueryRequest(query=Query.Nearest(self.bm25.embed_query(query), using="text"),
                                               limit=limit, with_payload=True, filter=active_filter))
            lists = [[str(p.id) for p in sparse]]
            if self.model is not None:
                vector = list(self.model.query_embed([query]))[0].tolist()
                dense = shard.query(QueryRequest(query=Query.Nearest(vector, using="dense"),
                                                  limit=limit, with_payload=True, filter=active_filter))
                lists.append([str(p.id) for p in dense])
            scores = {}
            for result in lists:
                for rank, memory_id in enumerate(result):
                    scores[memory_id] = scores.get(memory_id, 0) + 1 / (60 + rank + 1)
            return scores

    def close(self):
        with self.lock:
            for shard in self.shards.values():
                shard.close()
            self.shards.clear()
