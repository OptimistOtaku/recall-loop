"""Exercise hook context and MCP transport using an explicitly synthetic source event."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(project, env, memory, evidence):
    params = StdioServerParameters(command=sys.executable, args=["-m", "recall_loop.cli", "mcp"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog = await session.list_tools()
            names = {t.name for t in catalog.tools}
            assert names == {"search_memory", "get_memory", "record_feedback"}
            result = await session.call_tool("search_memory", {"query": "Python runtime for RecallLoop"})
            assert not result.isError
            content = json.loads(result.content[0].text)
            assert memory in [m["id"] for m in content["results"]]
            detail = await session.call_tool("get_memory", {"memory_id": memory})
            assert not detail.isError
            assert json.loads(detail.content[0].text)["evidence"][0]["event_id"] == evidence
    return sorted(names)


def main():
    data = Path(os.environ["RECALL_DATA_DIR"]).resolve()
    url = os.getenv("RECALL_URL", "http://127.0.0.1:7331")
    token = (data / "hook-token").read_text().strip()
    with httpx.Client(base_url=url, headers={"X-Recall-Token": token}) as client:
        p = client.post("/api/projects", json={"name":"Integration verification · synthetic"})
        p.raise_for_status()
        project = p.json()["id"]
        sid = str(uuid4())
        text = "Synthetic integration assertion: RecallLoop runs on Python 3.11 and serves the local app on port 7331."
        e = client.post("/api/capture", json={"project":project,"session":sid,"role":"user","text":text,"source":"Integration verification fixture"})
        e.raise_for_status()
        m = client.post("/api/memories", json={"project":project,"label":"RecallLoop Python runtime","body":text,
            "kind":"procedure","session":sid,"evidence":[{"event_id":e.json()["id"],"quote":text}]})
        m.raise_for_status()
        memory = m.json()["id"]
    env = dict(os.environ, RECALL_PROJECT=project, RECALL_DATA_DIR=str(data), RECALL_URL=url)
    payload = {"session_id":str(uuid4()),"hook_event_name":"UserPromptSubmit","turn_id":"integration-check",
               "prompt":"Which Python runtime should I use for RecallLoop?"}
    hook = subprocess.run([sys.executable,"-m","recall_loop.cli","hook"], input=json.dumps(payload),
                          text=True,capture_output=True,env=env,timeout=20,check=True)
    hook_result = json.loads(hook.stdout)
    assert memory in hook_result["hookSpecificOutput"]["additionalContext"]
    tools = asyncio.run(verify(project, env, memory, e.json()["id"]))
    report = {"hook_context":"passed","mcp_transport":"passed","tools":tools,
              "project":project,"dataset":"Synthetic integration fixture",
              "live_codex_agent_behavior":"not tested","paid_extraction":"not tested"}
    output = Path(__file__).resolve().parent.parent / "evaluation" / "integration.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
