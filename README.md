# semantido × Lenses CE sandbox

Tests whether a semantido semantic layer improves an agent's Lenses SQL
generation against Kafka streams — the text-to-SQL content-effect
benchmark, transposed to streaming. The scenario is an ETD trade
lifecycle (executions → clearing events → netted positions → EMIR
reports) engineered with four streaming-specific semantic traps:

| Trap                       | Where                                                 | Failure mode                                                                                                                                        |
|----------------------------|-------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| T1 Compacted state topic   | `etd.positions`                                       | aggregating over full history double-counts superseded snapshots                                                                                    |
| T2 Counterparty homonym    | `emir.trade-reports` vs `etd.clearing-events`         | conflating EMIR reporting counterparty (LEI) with clearing member (member code) — modelled as `DISTINCT_FROM` concept edges (v0.4 concept registry) |
| T3 Side vs direction       | `etd.executions.side` vs `etd.positions.net_quantity` | inferring LONG/SHORT from BUY/SELL                                                                                                                  |
| T4 Event vs ingestion time | `exec_time` vs `_meta.timestamp`                      | trade-date logic on Kafka timestamps                                                                                                                |

Plus the classics: order→fill fan-out, EMIR dual-sided report counting,
action-type lifecycle (NEWT/MODI/EROR).

## Layout

```
semantic/topics.py    topics modelled as semantido SQLAlchemy descriptors
                      (never bound to an engine) + ConceptRegistry
semantic/export.py    → exports/context_baseline.md (schemas only)
                        exports/context_semantic.md (full bundle)
seed/producer.py      deterministic lifecycle data + ground_truth.json
questions/questions.yaml   8 questions mapped to traps
agent/run_benchmark.py     two-condition harness (manual or MCP execution)
```

## Run

1. **Lenses CE** (needs Docker, ≥5 GB for Docker):
   ```bash
   curl -L https://lenses.io/community-edition/download -o docker-compose.yml
   ACCEPT_EULA=true docker compose up -d --wait
   # UI on http://localhost:9991
   ```

2. **Python deps**:
   add semantido kafka-python pyyaml anthropic mcp to pyproject deps

3. **uv sync**:
   ```bash
    uv sync
   ```

4. **Seed data** — check the broker's advertised host port first
   (`docker compose ps`, look for the Kafka listener; adjust
   `KAFKA_BOOTSTRAP` accordingly):
   ```bash
   KAFKA_BOOTSTRAP=localhost:9092 uv run python seed/producer.py
   ```
   Verify in the Lenses UI that the five topics exist and browse
   `etd.positions` — you should see multiple records per key.

5. **Export agent contexts**:
   ```bash
   python semantic/export.py
   ```

6. **Benchmark**, either:
   - **Interactive (recommended first):** add the Lenses MCP to Claude
     Code (`claude mcp add --transport http Lenses
     http://localhost:8000/mcp`), then in a session paste
     `exports/context_semantic.md` (or the baseline) and ask the
     questions from `questions/questions.yaml`. Watch what q5 and q6 do.
   - **Scripted:**
     ```bash
     export ANTHROPIC_API_KEY=...
     python agent/run_benchmark.py --mode manual   # SQL to exports/generated_sql/
     python agent/run_benchmark.py --mode mcp      # execute via Lenses MCP
     ```
     MCP mode needs `LENSES_MCP_TOKEN` (OAuth 2.1 bearer); tool name
     auto-detected or set with `--sql-tool`.

7. **Score** automatically:
   ```bash
   python agent/score.py            # scores exports/benchmark_results.json
   python agent/score.py --judge    # LLM-grades inconclusive (REVIEW) cells
   ```
   Two evidence sources per (question, condition): static SQL analysis
   (regex detection of the correct pattern *and* each trap's failure
   pattern – works even without execution) and, when results are
   present (from `--mode mcp`), value comparison against
   `ground_truth.json` including the exact **distractor values** each
   trap produces (`seed/lifecycle.py` computes e.g., the naive
   history-sum over the compacted topic), so failures are diagnosed as
   the specific trap rather than just "wrong". Output: PASS/FAIL/REVIEW
   scorecard, per-condition pass rates, and the content-effect delta
   (semantic - baseline). `exports/benchmark_results.example.json` is a
   synthetic run demonstrating the format; a validated example
   scorecard shows baseline tripping all seven traps.

   q6 (the counterparty homonym) is interpretation-graded: static
   classification of which sense the SQL resolved to, with `--judge`
   for the ambiguous cells -- a mechanical value check can't grade
   disambiguation behavior.

   Note: `ground_truth.json` is (re)written by `seed/producer.py` or
   standalone via `python seed/lifecycle.py`; event generation is pure
   and deterministic, so truth always matches what was seeded.


## Notes / warnings

- The Lenses SQL syntax note appended to both contexts is minimal and
  identical across conditions (so only semantic content varies). Verify
  `_meta` accessor spelling and snapshot-engine specifics against the
  SQL Reference in docs.lenses.io for your Lenses version, and adjust
  `LENSES_SQL_NOTE` in `semantic/export.py` if needed.
- The MCP execution path discovers tools dynamically because Lenses MCP
  tool names/schemas may differ by version; `--sql-tool` overrides.
- Broker port `19092` is a guess-with-override; CE compose files have
  changed listener layouts between releases.
- A natural v2: interpret `sql_filters` / application rules as SQL
  **Processor** definitions and have the agent deploy continuous queries
  (Lenses gates processor start behind UI confirmation — agents compose,
  humans commit).
