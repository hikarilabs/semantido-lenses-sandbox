"""Score benchmark runs against ground truth.

Two evidence sources per (question, condition):

  1. STATIC SQL ANALYSIS -- always available. Regex-level detection of
     the correct pattern and of each question's known failure mode
     ("bad" patterns). Catches the trap even before execution.

  2. RESULT CHECK -- when exports/benchmark_results.json rows contain a
     "result" (from --mode mcp), extracted numbers are compared against
     ground truth AND against the exact distractor values computed by
     seed/lifecycle.py, so a failure is diagnosed as the specific trap
     (e.g. "matched q5 naive-history-sum distractor").

Verdict per cell: PASS / FAIL(reason) / REVIEW (inconclusive -- look at
the SQL yourself; --judge grades REVIEW cells with an LLM against the
rubric in questions/questions.yaml).

Output: scorecard table + per-condition pass rates + the content-effect
delta (semantic - baseline), and exports/scorecard.json.

Usage:
  python agent/score.py                 # scores exports/benchmark_results.json
  python agent/score.py --judge         # LLM-grade the REVIEW cells
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def norm(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)  # strip comments for pattern checks
    return re.sub(r"\s+", " ", sql).lower()


def has_comment(sql: str) -> bool:
    return bool(re.search(r"^\s*--", sql, re.M))


def numbers_in(result) -> set:
    """All numeric values appearing anywhere in the result payload."""
    text = json.dumps(result)
    return {float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text)}


def result_rows(result):
    """Best-effort: parse JSON rows out of MCP text blocks."""
    rows = []
    for block in result if isinstance(result, list) else [result]:
        try:
            data = json.loads(block) if isinstance(block, str) else block
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            rows.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            rows.append(data)
    return rows


def scalar_check(result, truth_val, distractors):
    """distractors: {label: value}. Returns (verdict, detail)."""
    nums = numbers_in(result)
    hit = float(truth_val) in nums
    tripped = [label for label, v in distractors.items()
               if float(v) in nums and float(v) != float(truth_val)]
    if hit and not tripped:
        return "PASS", f"found {truth_val}"
    if tripped and not hit:
        return "FAIL", f"matched distractor {tripped[0]} instead of {truth_val}"
    if hit and tripped:
        return "REVIEW", f"both truth and distractor present: {tripped}"
    return "REVIEW", f"expected {truth_val}; numbers seen: {sorted(nums)[:8]}"


# --------------------------------------------------------------------------
# Per-question specs
# --------------------------------------------------------------------------

def build_specs(gt):
    d = gt["distractors"]

    def q5_result(result):
        rows = result_rows(result)
        truth = gt["sum_abs_net_qty_by_series"]
        naive = d["q5_naive_history_sum_by_series"]
        if not rows:
            return scalar_check(
                result, sum(truth.values()),
                {"naive_history_sum_total": sum(naive.values())},
            )
        ok = wrong = 0
        for series, val in truth.items():
            for row in rows:
                if series in json.dumps(row):
                    nums = numbers_in(row)
                    if float(val) in nums or float(abs(val)) in nums:
                        ok += 1
                    elif float(naive[series]) in nums:
                        wrong += 1
                    break
        if ok == len(truth):
            return "PASS", "all series match latest-per-key totals"
        if wrong:
            return "FAIL", f"{wrong} series match the naive history-sum distractor"
        return "REVIEW", f"{ok}/{len(truth)} series matched"

    def q6_static(sql_raw, s):
        uses_emir = "emir.trade-reports" in s and "counterpart" in s
        uses_clearing = ("member_code" in s or "clearing_member_id" in s
                         or "etd.clearing-events" in s)
        stated = bool(re.search(
            r"^\s*--.*(counterpart|clearing|member|emir|lei|interpret)",
            sql_raw, re.I | re.M))
        if uses_emir and not uses_clearing:
            return "PASS", "resolved to EMIR legal counterparties (LEIs)"
        if uses_clearing and not uses_emir:
            if stated:
                return ("REVIEW",
                        "resolved to clearing-member sense WITH a stated "
                        "interpretation -- rubric allows noting the "
                        "distinction; judge reasonableness")
            return "FAIL", "silently used clearing members as 'counterparties'"
        if uses_emir and uses_clearing:
            return "REVIEW", "references both senses -- check for a join of LEIs to member codes (auto-fail if joined)"
        return "REVIEW", "could not classify interpretation"

    def q7_result(result):
        text = json.dumps(result)
        expected = set(gt["short_members_fdax_net"]) | set(
            gt["short_members_fdax_any_account"]
        )
        found = {m for m in expected if m in text}
        # side='SELL' inference tends to include *every* member; detect by
        # members present that are not short under either reading
        extra = {m for m in ["GCMABC", "GCMXYZ", "DCMFOO", "GCMBAR", "DCMQUX"]
                 if m in text} - expected
        if found and not extra:
            return "PASS", f"short members: {sorted(found)}"
        if extra:
            return "FAIL", f"non-short members included: {sorted(extra)} (side-vs-direction trap?)"
        return "REVIEW", "no member codes recognized in result"

    def date_truth():
        return gt["n_fills_by_date"].get("2026-07-21", 0)

    return {
        "q1_control_count": {
            "good": [r"count\s*\("], "bad": [],
            "result": lambda r: scalar_check(r, gt["n_fills"], {}),
        },
        "q2_fanout_orders": {
            # Two correct routes since v0.5 added the etd.orders topic:
            # distinct order_id over executions, or counting order records.
            "good": [r"distinct\s+(\w+\.)?order_id",
                     r"etd\.orders"],
            "bad_fn": lambda s: (
                ("FAIL", "counted fills, not orders (fan-out trap)")
                if re.search(r"count\s*\(\s*(\*|\w*\.?order_id)\s*\)", s)
                and "etd.executions" in s and "etd.orders" not in s
                and not re.search(r"distinct\s+(\w+\.)?order_id", s)
                else None
            ),
            "bad": [],
            "result": lambda r: scalar_check(
                r, gt["n_orders"],
                {"count_star_fills": d["q2_count_star_fills"]},
            ),
        },
        "q3_emir_trade_count": {
            "good": [r"count\s*\(\s*distinct\s+(\w+\.)?uti"],
            "bad": [r"count\s*\(\s*\*\s*\)", r"count\s*\(\s*report_id"],
            "result": lambda r: scalar_check(
                r, gt["n_economic_trades"],
                {"report_record_count": d["q3_report_record_count"]},
            ),
        },
        "q4_live_trades": {
            "good": [r"eror", r"not\s+in\s*\("],
            "bad": [],
# Row-level EROR filtering is wrong for lifecycle state: it
            # applies before "latest action per UTI" is resolved, so a
            # cancelled trade survives as its NEWT. Textual signature: an
            # EROR filter attached to the emir.trade-reports scan itself.
            # Exemption: an anti-join excluding whole UTIs is correct.
            "bad_fn": lambda s: (
                None
                if re.search(r"uti\s+not\s+in\s*\(\s*select", s)
                else ("FAIL", "row-level EROR filter applied before "
                              "latest-action-per-UTI resolution "
                              "(cancelled trades survive as their NEWT)")
                if re.search(
                    r"from\s+`emir\.trade-reports`[^)]{0,160}?"
                    r"((<>|!=)\s*'eror'|not\s+in\s*\('eror')", s)
                else None
            ),
            "result": lambda r: scalar_check(
                r, gt["n_live_utis"], {"all_utis": d["q4_all_utis"]},
            ),
        },
        "q5_open_interest": {
            "good": [r"_meta\.offset", r"max\s*\(\s*_meta",
                     r"latest", r"row_number"],
            "bad": [],
            "bad_fn": lambda s: (
                ("FAIL", "plain SUM over full topic history (compaction trap)")
                if re.search(r"sum\s*\(\s*(abs\s*\(\s*)?net_quantity", s)
                and not re.search(r"_meta\.offset|latest|row_number|max\s*\(", s)
                else None
            ),
            "result": q5_result,
        },
        "q6_counterparty_homonym": {
            "static_fn": q6_static,
            "result": None,  # interpretation question; static + judge only
        },
        "q7_side_vs_direction": {
            "good": [r"net_quantity\s*<\s*0"],
            "bad": [r"side\s*=\s*'sell'", r'side\s*=\s*"sell"'],
            "result": q7_result,
        },
        "q8_event_time": {
            "good": [r"exec_time"],
            "bad": [r"_meta\.timestamp"],
            "result": lambda r: scalar_check(r, date_truth(), {}),
        },
    }


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def score_cell(spec, sql, result):
    s = norm(sql)

    # static
    if "static_fn" in spec:
        static = spec["static_fn"](sql, s)
    else:
        bad_hit = next((p for p in spec.get("bad", []) if re.search(p, s)), None)
        custom = spec.get("bad_fn", lambda _: None)(s)
        good_hit = any(re.search(p, s) for p in spec.get("good", []))
        if custom:
            static = custom
        elif bad_hit and not good_hit:
            static = ("FAIL", f"failure pattern: /{bad_hit}/")
        elif good_hit:
            static = ("PASS", "correct SQL pattern present")
        else:
            static = ("REVIEW", "no known pattern matched")

    # result (authoritative when present)
    if result is not None and spec.get("result"):
        res = spec["result"](result)
        # a distractor-matching result overrides an optimistic static pass
        verdict, detail = res
        if verdict == "REVIEW" and static[0] != "REVIEW":
            verdict, detail = static[0], f"{static[1]} (result inconclusive: {detail})"
        return verdict, detail, {"static": static, "result": res}
    return static[0], static[1], {"static": static, "result": None}


def llm_judge(client, model, question, expected, sql, result):
    prompt = (
        "Grade this generated Lenses SQL against the rubric. Reply with "
        "exactly one line: PASS: <reason> or FAIL: <reason>.\n\n"
        f"Question: {question}\nRubric: {expected}\nSQL:\n{sql}\n"
        f"Result (may be empty): {json.dumps(result)[:2000]}"
    )
    msg = client.messages.create(
        model=model, max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    line = msg.content[0].text.strip().splitlines()[0]
    verdict = "PASS" if line.upper().startswith("PASS") else "FAIL"
    return verdict, f"judge: {line}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["manual", "mcp"], default="manual",
                    help="Which benchmark run folder to score (exports/<mode>/)")
    ap.add_argument("--results", default=None)
    ap.add_argument("--judge", action="store_true",
                    help="LLM-grade REVIEW cells (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args()

    results_path = Path(args.results) if args.results else EXPORTS / args.mode / "benchmark_results.json"

    gt = json.loads((EXPORTS / "ground_truth.json").read_text())
    if "distractors" not in gt:
        raise SystemExit(
            "ground_truth.json predates the scorer -- regenerate with "
            "`python seed/lifecycle.py` (or re-run seed/producer.py)"
        )
    specs = build_specs(gt)

    import yaml
    rubrics = {q["id"]: q for q in yaml.safe_load(
        (ROOT / "questions/questions.yaml").read_text())}

    rows = json.loads(results_path.read_text())
    judge_client = None
    if args.judge:
        from anthropic import Anthropic
        judge_client = Anthropic()

    scorecard = []
    for row in rows:
        qid, cond = row["id"], row["condition"]
        spec = specs.get(qid)
        if spec is None:
            continue
        verdict, detail, evidence = score_cell(
            spec, row["sql"], row.get("result"))
        if verdict == "REVIEW" and judge_client:
            verdict, detail = llm_judge(
                judge_client, args.model, rubrics[qid]["question"],
                rubrics[qid]["expected"], row["sql"], row.get("result"))
        scorecard.append({
            "id": qid, "condition": cond, "verdict": verdict,
            "detail": detail, "evidence": evidence,
        })

    # ---- report -----------------------------------------------------------
    conds = sorted({c["condition"] for c in scorecard})
    qids = sorted({c["id"] for c in scorecard})
    cell = {(c["id"], c["condition"]): c for c in scorecard}

    width = max(len(q) for q in qids) + 2
    print(f"\n{'question'.ljust(width)}" + "".join(c.ljust(10) for c in conds))
    for qid in qids:
        line = qid.ljust(width)
        for c in conds:
            v = cell.get((qid, c), {}).get("verdict", "-")
            line += v.ljust(10)
        print(line)
        for c in conds:
            e = cell.get((qid, c))
            if e and e["verdict"] != "PASS":
                print(f"  [{c}] {e['detail']}")

    print()
    rates = {}
    for c in conds:
        cells = [x for x in scorecard if x["condition"] == c]
        rates[c] = sum(x["verdict"] == "PASS" for x in cells) / len(cells)
        n_review = sum(x["verdict"] == "REVIEW" for x in cells)
        print(f"{c}: {rates[c]:.0%} pass"
              + (f" ({n_review} REVIEW -- rerun with --judge)" if n_review else ""))
    if {"baseline", "semantic"} <= set(rates):
        delta = rates["semantic"] - rates["baseline"]
        print(f"content effect (semantic - baseline): {delta:+.0%}")

    out = (results_path.parent / "scorecard.json")
    out.write_text(json.dumps(scorecard, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
