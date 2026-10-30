# Verification record

These are implementation checks, not a claim of winning or a general productivity improvement.

## Passed

- Production React/TypeScript/Vite build.
- Qdrant Edge 0.9.0 native Windows shard creation, indexing, querying, closing and reopening.
- Local FastEmbed model download and offline hybrid retrieval.
- Backend regression suite: 26 tests covering persistence, evidence, directed graph expansion and undo, project isolation, deletion/superseding, pinned layouts, capture checkpoints, privacy filtering, source validation, tentative assistant claims, budget guards, API failure handling, explicit public-origin support, and unrecognized-host rejection.
- Ten predefined synthetic retrieval cases: 10/10 expected lessons in the top five; median 13.02 ms, maximum 37.51 ms in this run.
- Live local hook-context and MCP transport check using a synthetic source event. All three tools were advertised; search and evidence inspection completed.
- Project-local setup in a disposable fixture: existing hooks preserved, backup created, launcher generated.
- Browser memory creation, quoted source inspection, prerequisite connection, recall path, and undo.
- Browser pin persistence across a full page reload.
- Foreground rendering sample: 53 Three.js renderer frames/s, 500 nodes, 1,195 connections, 5,009 ms, 1280×720 in the Windows in-app browser.
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


## Observatory redesign — 30 October 2026 IST

- Three frontend regressions pass. The original merge logic failed two of these checks; explicit canonical pin reconciliation fixes both.
- The actual engineering workspace stores the user design request and real before/after terminal evidence. A fresh MCP process retrieves the lesson and inspects its evidence; a fresh hook process supplies it as context.
- Memory selection clears stale evidence while loading another node. Connections name records outside the bounded snapshot and can navigate to their neighborhood.
- Searchable keyboard-accessible node directory, 2D/3D view, labels, evidence/suggestion layers, freeze, zoom and focus controls. Project selection remains available on narrow screens and persists across reloads.
- No paid automatic extraction, fresh native Codex run, Wispr recording, or paired productivity result is claimed. See evaluation/real-coding.json.

The original frontend failure/pass terminal reports are included in evaluation/graph-regression-before.txt and evaluation/graph-regression-after.txt, with local paths redacted.

Public Observatory deployment verified live at source commit 14d0056c8e0872b9238e2630881d6a28d1a7709c (deploy dep-dbibhcajnfac73dbnt3g). Public search, connection creation/undo, visitor isolation, and disabled paid extraction passed.

Final readable-label release verified live: ec255ea3389b19ba329823b69c3239161e9d068e, deploy dep-dbibl08n74is73avp54g. Foreground renderer check: 53 FPS at 500 nodes / 1,195 links, 1280×720, 5,009 ms.

## bunch · immersive canvas and transparent panels

The product is branded bunch. The graph fills the viewport behind transparent, collapsible workspace and memory panels. Search, filters, node directory, session/recall views, and dialogs use the shared galactic backdrop. Desktop (1440×900) and mobile (390×844) layouts, panel toggles, session navigation, and memory dialogs were checked. Labels keep a consistent screen size and avoid rendering through panel text. Existing memory and MCP retrieval were preserved. See evaluation/bunch-interface.json.
