# RecallLoop

**Coding-agent memory you can inspect, connect, and carry into your next session.**

An independent local-first application: Python/FastAPI, SQLite, Qdrant Edge, local FastEmbed embeddings, Codex hooks/MCP, and an editable Three.js knowledge graph.

Public demo: https://recall-loop-demo.onrender.com · Source: https://github.com/OptimistOtaku/recall-loop

The hosted demo uses synthetic, visitor-isolated data. Free hosting can sleep and resets temporary edits after restarts.

## Implemented

- Create, inspect, correct, supersede, delete, and undo evidence-backed memories.
- Explore session, memory, file, and outcome nodes in 3D; orbit, zoom, focus, drag, pin, filter, and expand neighborhoods.
- Connect memories with related-to, prerequisite-for, or contradiction relationships. Typed connections influence recall; dragging changes layout.
- Hybrid dense/BM25 retrieval, bounded graph expansion, usefulness feedback, and source references.
- Durable SQLite records and rebuildable embedded Qdrant indexes; no database server required locally.
- Codex lifecycle capture, automatic asynchronous extraction, and an MCP server with search, inspection, and feedback tools.
- Model-cost reservations, credential-pattern redaction, source-quote validation, and failure-safe capture.
- Cookie-isolated hosted samples, explicitly labeled sample replays, and a no-WebGL list fallback.

This is an MVP, not a claim of a competition win or a proven general productivity improvement.

## Celestial Observatory

The 3D workspace uses a dark celestial palette, luminous typed nodes, session constellations, and a decorative galaxy backdrop. Background stars are visual context, not memories. Positions do not imply semantic similarity.

Use **Browse nodes** to search by title, filename, or content, then select a result to inspect and fly to it. Use **2D map** for planar navigation, **Smart labels** to reduce clutter, **Freeze layout** to stop physics, and the evidence/suggestion toggles to control detail. Typed user connections affect recall; dragging only pins layout. The inspector explains prerequisite direction.

Actual repository testing reproduced and fixed a pin synchronization bug: two frontend assertions failed before the fix, and all three pass afterward. The lesson and terminal evidence are stored in the local **RecallLoop · real engineering** workspace. Fresh MCP and hook processes retrieve it. This is explicitly curated evidence, not a claim that paid extraction or a fresh native Codex session was verified.

Run the frontend regression checks with Node.js 22.14+: `node --experimental-strip-types --test frontend/test/graph-model.test.mjs`.

## Run on Windows

Prerequisites: Python 3.11 and Node.js 22+, or uv for Python management.

```powershell
uv sync --python 3.11 --frozen --extra test
Set-Location frontend
npm ci
npm run build
Set-Location ..
uv run --frozen recall-loop serve
```

Open **http://127.0.0.1:7331**. First startup downloads the local embedding model; cached retrieval can subsequently work offline.

The supplied `Start-RecallLoop.ps1` also starts an existing environment. It accepts `-NoEmbeddings` for explicit keyword-only operation and `-AskForApiKey` for masked API-key entry. The key stays in the launcher process.

In this delivered workspace, `.venv311` is the tested Python environment. The original `.venv` points at a Windows Store alias and is not the tested launcher.

### Live extraction

Provide `OPENAI_API_KEY` in the server process, or run:

```powershell
.\Start-RecallLoop.ps1 -AskForApiKey
```

No API key was available during implementation. Live paid extraction has **not** been verified. Quote validation, allowance enforcement, failure behavior, and checkpoints are tested with mocked responses.

Sample memories and the replay action require no API key and are explicitly labeled. Use Wispr Flow for dictation into ordinary fields or Codex; this app does not include a separate speech recognizer.

### Configuration

| Variable | Default / behavior |
|---|---|
| RECALL_DATA_DIR | data under the launch directory |
| RECALL_MODEL_CACHE | models inside the data directory |
| RECALL_BUDGET_USD | 10; application maximum is US$10 |
| OPENAI_API_KEY | Required only for automatic extraction |
| RECALL_URL | http://127.0.0.1:7331 for hooks/MCP |
| RECALL_PROJECT | Project ID for hooks/MCP |
| RECALL_DEMO | 1 isolates sample visitors and disables capture/import/extraction |
| RECALL_PUBLIC_ORIGIN | One exact public origin; defaults to Render's RENDER_EXTERNAL_URL when available |
| HF_HUB_OFFLINE | 1 uses the already cached embedding model |

The implementation preview uses the workspace's work/recall-data directory, outside this source deliverable.

To continue that same preview dataset after stopping the current service, use
`.\Start-RecallLoop.ps1 -DataDirectory ..\..\work\recall-data` from this directory.

Reservations use US$2/M input and US$12/M output tokens for gpt-5.6-terra, verified during planning. Recheck provider pricing before future use. Failed dispatched calls retain their worst-case reservation. The allowance covers this application's calls, not other API-account activity.

## Connect Codex

Keep the service running. In another shell, set the same data directory and URL, then preview:

```powershell
uv run --frozen recall-loop setup C:\path\to\your-project
```

Add `--write` to install project-local hooks. Setup preserves existing hooks, writes a backup when needed, and prints the MCP configuration. It does not change global Codex settings. Preview registers an empty project but installs no hooks.

**Review and trust the generated hooks in Codex, then restart that project session.** Add the printed MCP command, arguments, and environment through Codex's MCP settings.

No hooks were automatically installed into your existing projects. A live fresh-session Codex demonstration is still pending your configured integration.

- SessionStart retrieves project knowledge.
- UserPromptSubmit captures the prompt and supplies historical context.
- PostToolUse imports new visible transcript items.
- Stop imports remaining items and queues extraction.

Hook failures are fail-open. MCP tools: `search_memory`, `get_memory`, and `record_feedback`. Current instructions take precedence over historical records.

## Graph controls

Select a node or recent lesson to inspect its sources. Choose Connect, then source and target memories. A prerequisite points source → target; retrieving the target can recall its prerequisite.

Dashed proposals are category-based suggestions and require acceptance before affecting recall. Pin/Unpin and Reset saved layout affect layout only. Edit, Supersede, and Delete change knowledge; Undo restores the last 20 knowledge edits.

## Verification

```powershell
uv run --frozen --extra test pytest -q
uv run --frozen python scripts/evaluate.py --model-cache .\data\models --output evaluation\retrieval.json
```

Restricted Windows environments may need an explicit workspace pytest basetemp and permission for the asynchronous test client's local sockets.

The delivered retrieval report uses ten **synthetic** Atlas cases. It is not a real productivity study. Five paired real coding tasks remain to be run with fresh sessions, identical model/settings, and the integration enabled versus disabled.

To create the 500-node rendering workspace, stop the service, run `python scripts/graph_fixture.py --data .\data` in the project environment, then restart. Select Performance lab, expand to 500 nodes, and use Integration help → Measure five seconds of rendering. This counts Three.js renderer frames; record the actual result instead of assuming the target was met.

## Deploy the sample demo

Included: multi-stage Dockerfile, hashed requirements.lock, uv.lock, package-lock.json, and Render Free blueprint.

1. Publish this source without credentials, private data, environments, or model caches.
2. Connect the repository to Render and create a Blueprint from render.yaml.
3. Deploy. The build bundles the embedding model and compiled frontend.
4. Leave OPENAI_API_KEY unset for the hosted sample.
5. Verify health, replay, live search, graph editing, and isolation in two clean browser sessions.

The demo has ephemeral storage and reconstructs samples after restarts. Render Free can sleep and cold-start; visitor changes are temporary. This is demonstration hosting, not durable multi-user production hosting.

Render was not connected during implementation, so no public deployment is claimed. The local Docker engine was not running; the container build is not yet verified.

## Boundaries

- Transcript formats can change. The adapter excludes instruction/hidden-reasoning records and stops on unsupported visible-message shapes.
- Redaction detects common patterns, not every possible secret. Review project sensitivity before enabling model processing.
- Qdrant Edge is beta; retain SQLite records for index rebuilding.
- Native Codex memory exists. Keep its settings constant in comparisons.
- Automatic capture requires the local installation. Do not expose your real local data directory publicly; keep the local service on loopback.

See docs/DEMO_SCRIPT.md, docs/CONTEST_CHECKLIST.md, and evaluation/retrieval.json.

