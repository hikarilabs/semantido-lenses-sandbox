"""Two-condition text-to-Lenses-SQL benchmark harness.

Conditions:
  baseline  -> exports/context_baseline.md  (schemas only)
  semantic  -> exports/context_semantic.md  (full semantido bundle)

For each question x condition, an LLM generates a Lenses SQL Snapshot
query. Execution modes:

  --mode manual   (default) write generated SQL to exports/generated_sql/
                  for you to run via the Lenses UI or Claude Code + Lenses
                  MCP, and eyeball against questions/questions.yaml +
                  exports/ground_truth.json.

  --mode mcp      execute each query through the Lenses MCP server
                  (http://localhost:8000/mcp). The Lenses MCP uses OAuth
                  2.1; obtain a token via your MCP client's auth flow and
                  pass it as LENSES_MCP_TOKEN. Tool discovery is dynamic:
                  the harness lists tools and picks the one whose name
                  matches --sql-tool (default: first tool containing
                  'sql' and 'quer').

Requires: pip install anthropic pyyaml mcp
Env: ANTHROPIC_API_KEY, optionally LENSES_MCP_URL, LENSES_MCP_TOKEN
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

import yaml
from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"

SYSTEM = """You are a data agent querying Apache Kafka through Lenses SQL
(Snapshot engine). You will be given context about the available topics,
then a question. Respond with ONLY the Lenses SQL query (no markdown
fences, no commentary). If the question is ambiguous in a way the context
flags as a known ambiguity, resolve it explicitly with a SQL comment on
the first line explaining the interpretation chosen."""


def generate_sql(client, model, context: str, question: str) -> str:
    msg = client.messages.create(
        model=model,
        max_tokens=1000,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"<context>\n{context}\n</context>\n\n"
                f"Question: {question}",
            }
        ],
    )
    return msg.content[0].text.strip()


async def execute_via_mcp(sql: str, url: str, token: str, sql_tool: str | None):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with streamablehttp_client(url, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            if sql_tool:
                tool = next(t for t in tools if t.name == sql_tool)
            else:
                tool = next(
                    (
                        t
                        for t in tools
                        if "sql" in t.name.lower() and "quer" in t.name.lower()
                    ),
                    None,
                )
                if tool is None:
                    names = [t.name for t in tools]
                    raise SystemExit(
                        f"No SQL query tool auto-detected. Available: {names}\n"
                        "Re-run with --sql-tool <name>."
                    )
            # Inspect tool.inputSchema for the exact argument name if this
            # guess fails on your Lenses version.
            arg_name = next(iter(tool.inputSchema.get("properties", {"sql": {}})))
            result = await session.call_tool(tool.name, {arg_name: sql})
            return [c.text for c in result.content if hasattr(c, "text")]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["manual", "mcp"], default="manual")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--sql-tool", default=None)
    ap.add_argument("--questions", default=str(ROOT / "questions/questions.yaml"))
    args = ap.parse_args()

    questions = yaml.safe_load(Path(args.questions).read_text())
    contexts = {
        "baseline": (EXPORTS / "context_baseline.md").read_text(),
        "semantic": (EXPORTS / "context_semantic.md").read_text(),
    }
    client = Anthropic()
    out_dir = EXPORTS / args.mode / "generated_sql"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for q in questions:
        for cond, ctx in contexts.items():
            sql = generate_sql(client, args.model, ctx, q["question"])
            (out_dir / f"{q['id']}__{cond}.sql").write_text(sql + "\n")
            row = {"id": q["id"], "condition": cond, "sql": sql}
            if args.mode == "mcp":
                url = os.environ.get("LENSES_MCP_URL", "http://localhost:8000/mcp")
                token = os.environ.get("LENSES_MCP_TOKEN", "")
                try:
                    row["result"] = asyncio.run(
                        execute_via_mcp(sql, url, token, args.sql_tool)
                    )
                except Exception as exc:  # noqa: BLE001
                    row["error"] = str(exc)
            results.append(row)
            print(f"[{q['id']} / {cond}] done")

    (EXPORTS / args.mode / "benchmark_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nwrote {EXPORTS / args.mode / 'benchmark_results.json'}")
    print(f"generated SQL in {out_dir}")


if __name__ == "__main__":
    main()
