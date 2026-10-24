# Verification record

These are implementation checks, not a claim of winning or a general productivity improvement.

## Passed

- Production React/TypeScript/Vite build.
- Qdrant Edge 0.9.0 native Windows shard creation, indexing, querying, closing and reopening.
- Local FastEmbed model download and offline hybrid retrieval.
- Backend regression suite: 24 tests covering persistence, evidence, directed graph expansion and undo, project isolation, deletion/superseding, pinned layouts, capture checkpoints, privacy filtering, source validation, tentative assistant claims, budget guards, API failure handling, explicit public-origin support, and unrecognized-host rejection.
- Ten predefined synthetic retrieval cases: 10/10 expected lessons in the top five; median 13.02 ms, maximum 37.51 ms in this run.
- Live local hook-context and MCP transport check using a synthetic source event. All three tools were advertised; search and evidence inspection completed.
- Project-local setup in a disposable fixture: existing hooks preserved, backup created, launcher generated.
- Browser memory creation, quoted source inspection, prerequisite connection, recall path, and undo.
- Browser pin persistence across a full page reload.
- Foreground rendering sample: 58 Three.js renderer frames/s, 500 nodes, 1,195 connections, 5,018 ms, 1440×900 in the Windows in-app browser.
- Mobile breakpoint check: document content did not exceed the viewport width.

## Still requires the configured user environment

- Live paid extraction: no OpenAI API key was available.
- Actual fresh-Codex behavior with trusted project hooks and MCP enabled.
- A genuine Wispr microphone demonstration and the user's usage card.
- Five paired real coding trials. No time-saving or repeated-error percentage is claimed.
- Public Render deployment passed on 25 October 2026 IST: live hybrid search, 37-node graph, relationship creation and undo, visitor isolation, and disabled paid extraction. See evaluation/deployment.json.
- Linux Docker build passed on Render, including locked dependencies and bundled embeddings.

The deployment uses the exact RECALL_PUBLIC_ORIGIN or Render-provided RENDER_EXTERNAL_URL to validate the public origin. It does not globally trust arbitrary forwarded headers.

Reports: evaluation/retrieval.json, evaluation/rendering.json, and evaluation/integration.json.

