"""Pure synthetic ETD lifecycle generator (no Kafka dependency).

Single source of truth for both:
  seed/producer.py   -- sends the events to Kafka
  agent/score.py     -- scores results against ground truth

Deterministic (fixed seed). Besides correct answers, ground truth also
includes the exact DISTRACTOR values each trap produces (e.g. the naive
SUM over the compacted topic's history), so the scorer can diagnose
*which* failure mode a wrong answer fell into.
"""

import random
from datetime import datetime, timedelta

MEMBERS = ["GCMABC", "GCMXYZ", "DCMFOO", "GCMBAR", "DCMQUX"]
LEIS = {m: f"{m}LEI000000000000{i}" for i, m in enumerate(MEMBERS)}
CLIENT_LEIS = [f"CLIENTLEI0000000000{i}" for i in range(8)]
SERIES = {
    "FDAX-2026-09": ("FUTURE", "DAX", 25),
    "FESX-2026-09": ("FUTURE", "EURO STOXX 50", 10),
    "FGBL-2026-09": ("FUTURE", "Bund", 1000),
    "OESX-2026-09-C-5400": ("OPTION", "EURO STOXX 50", 10),
    "OESX-2026-09-P-5000": ("OPTION", "EURO STOXX 50", 10),
}
T0 = datetime(2026, 7, 20, 8, 0, 0)
N_FILLS = 600

TOPIC_CONFIGS = {
    "etd.executions": {},
    "etd.clearing-events": {},
    "etd.positions": {"cleanup.policy": "compact"},
    "emir.trade-reports": {},
    "refdata.contracts": {"cleanup.policy": "compact"},
}


def generate():
    """Returns (events, ground_truth).

    events: list of (topic, key, value_dict) in send order.
    ground_truth: dict of correct answers and named distractors.
    """
    rng = random.Random(42)
    events = []

    def send(topic, key, value):
        events.append((topic, key, value))

    # --- refdata (two versions for FDAX: latest-per-key on refdata too) --
    for series, (ptype, under, mult) in SERIES.items():
        send("refdata.contracts", series, {
            "contract_series": series, "product_type": ptype,
            "underlying": under, "contract_multiplier": mult,
            "expiry_date": "2026-09-18",
        })
    send("refdata.contracts", "FDAX-2026-09", {
        "contract_series": "FDAX-2026-09", "product_type": "FUTURE",
        "underlying": "DAX", "contract_multiplier": 25,
        "expiry_date": "2026-09-18", "version": 2,
    })

    positions = {}          # (member, account, series) -> signed net qty
    naive_sum = {}          # series -> sum over ALL snapshots (distractor)
    fills_by_date = {}
    order_pool = []
    n_orders = 0
    emir_utis, errored_utis = set(), set()
    lei_utis = {}           # LEI -> set of UTIs (activity per counterparty)
    n_report_records = 0

    for i in range(N_FILLS):
        if not order_pool or rng.random() < 0.4:
            n_orders += 1
            order_pool.append(f"ORD{n_orders:05d}")
        order_id = rng.choice(order_pool[-3:])

        exec_id = f"EXE{i:05d}"
        series = rng.choice(list(SERIES))
        member = rng.choice(MEMBERS)
        # Directional bias per member so long/short members separate
        # cleanly (needed for q7 to be scorable from results).
        buy_prob = {"GCMABC": 0.80, "GCMXYZ": 0.72, "DCMFOO": 0.25,
                    "GCMBAR": 0.50, "DCMQUX": 0.22}[member]
        side = "BUY" if rng.random() < buy_prob else "SELL"
        qty = rng.randint(1, 50)
        account = rng.choice(["A1", "P1"])
        exec_time = T0 + timedelta(minutes=rng.randint(0, 1700))  # asymmetric across the two trade dates
        price = round(rng.uniform(50, 24000), 2)
        fills_by_date[exec_time.date().isoformat()] = (
            fills_by_date.get(exec_time.date().isoformat(), 0) + 1
        )

        send("etd.executions", exec_id, {
            "exec_id": exec_id, "order_id": order_id,
            "contract_series": series, "side": side, "quantity": qty,
            "price": price, "executing_member": member,
            "exec_time": exec_time.isoformat(),
        })
        send("etd.clearing-events", f"CLR{i:05d}", {
            "event_id": f"CLR{i:05d}", "event_type": "NOVATION",
            "exec_id": exec_id, "clearing_member_id": member,
            "account": account,
            "event_time": (exec_time + timedelta(seconds=30)).isoformat(),
        })

        pkey = (member, account, series)
        positions[pkey] = positions.get(pkey, 0) + (qty if side == "BUY" else -qty)
        naive_sum[series] = naive_sum.get(series, 0) + positions[pkey]
        send("etd.positions", "|".join(pkey), {
            "position_key": "|".join(pkey),
            "clearing_member_id": member, "account": account,
            "contract_series": series, "net_quantity": positions[pkey],
            "as_of_time": (exec_time + timedelta(seconds=60)).isoformat(),
        })

        uti = f"UTI2026{i:07d}"
        emir_utis.add(uti)
        cp_client = rng.choice(CLIENT_LEIS)
        lei_utis.setdefault(LEIS[member], set()).add(uti)
        lei_utis.setdefault(cp_client, set()).add(uti)
        rt = exec_time + timedelta(minutes=5)
        for j, (cp1, cp2) in enumerate(
            [(LEIS[member], cp_client), (cp_client, LEIS[member])]
        ):
            n_report_records += 1
            send("emir.trade-reports", f"RPT{i:05d}{j}", {
                "report_id": f"RPT{i:05d}{j}", "uti": uti,
                "counterparty_1": cp1, "counterparty_2": cp2,
                "exec_id": exec_id, "action_type": "NEWT",
                "notional": round(price * SERIES[series][2] * qty, 2),
                "notional_currency": "EUR",
                "reporting_timestamp": rt.isoformat(),
            })
        if rng.random() < 0.05:
            errored_utis.add(uti)
            for j in range(2):
                n_report_records += 1
                send("emir.trade-reports", f"RPT{i:05d}{j}E", {
                    "report_id": f"RPT{i:05d}{j}E", "uti": uti,
                    "counterparty_1": LEIS[member] if j == 0 else cp_client,
                    "counterparty_2": cp_client if j == 0 else LEIS[member],
                    "exec_id": exec_id, "action_type": "EROR",
                    "notional": None, "notional_currency": "EUR",
                    "reporting_timestamp": (rt + timedelta(hours=1)).isoformat(),
                })

    for g in range(15):
        src, dst = rng.sample(MEMBERS, 2)
        et = T0 + timedelta(hours=rng.randint(1, 30))
        for etype, mem in (("GIVE_UP", src), ("TAKE_UP", dst)):
            send("etd.clearing-events", f"GUP{g:03d}{etype[0]}", {
                "event_id": f"GUP{g:03d}{etype[0]}", "event_type": etype,
                "exec_id": f"EXE{rng.randint(0, N_FILLS - 1):05d}",
                "clearing_member_id": mem, "account": "A1",
                "event_time": et.isoformat(),
            })

    open_interest = {}
    for (member, account, series), q in positions.items():
        open_interest[series] = open_interest.get(series, 0) + abs(q)

    short_members_fdax = sorted(
        {m for (m, a, s), q in positions.items()
         if s == "FDAX-2026-09" and q < 0}
    )
    # per-member aggregate FDAX net (all accounts) — the stricter reading
    fdax_by_member = {}
    for (m, a, s), q in positions.items():
        if s == "FDAX-2026-09":
            fdax_by_member[m] = fdax_by_member.get(m, 0) + q
    short_members_fdax_net = sorted(
        m for m, q in fdax_by_member.items() if q < 0
    )

    truth = {
        "n_fills": N_FILLS,
        "n_orders": n_orders,
        "n_economic_trades": len(emir_utis),
        "n_live_utis": len(emir_utis - errored_utis),
        "n_fills_by_date": fills_by_date,
        "sum_abs_net_qty_by_series": open_interest,
        "current_net_positions": {"|".join(k): v
                                  for k, v in sorted(positions.items())},
        "short_members_fdax_any_account": short_members_fdax,
        "short_members_fdax_net": short_members_fdax_net,
        "trades_per_lei": {lei: len(u)
                           for lei, u in sorted(lei_utis.items())},
        "distractors": {
            "q2_count_star_fills": N_FILLS,
            "q3_report_record_count": n_report_records,
            "q4_all_utis": len(emir_utis),
            "q5_naive_history_sum_by_series": naive_sum,
        },
    }
    return events, truth


if __name__ == "__main__":
    import json
    from pathlib import Path

    events, truth = generate()
    out = Path(__file__).resolve().parent.parent / "exports" / "ground_truth.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(truth, indent=2, default=str))
    print(f"{len(events)} events; ground truth -> {out}")
    print(json.dumps({k: v for k, v in truth.items()
                      if not isinstance(v, dict)}, indent=2))
