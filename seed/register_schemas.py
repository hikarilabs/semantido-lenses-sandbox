"""Register Avro schemas for the sandbox topics into a Confluent-
compatible Schema Registry (Lenses CE ships one).

This closes the loop for the reflection path: after registering, run
    python semantic/reflect.py --registry http://localhost:8081 \
        --overlay semantic/overlays/etd.yaml
and the physical layer is pulled from the registry instead of being
hand-authored.

Env: SCHEMA_REGISTRY (default http://localhost:8081 -- check
`docker compose ps` for the mapped port on your CE stack).

Note: seed/producer.py writes plain JSON payloads; registering these
schemas documents the contract in the registry (subject per topic) so
reflection works. If you want end-to-end Avro serialization too, switch
the producer to confluent-kafka's AvroSerializer.
"""

import json
import os
import urllib.request

REGISTRY = os.environ.get("SCHEMA_REGISTRY", "http://localhost:8081")

TS = {"type": "long", "logicalType": "timestamp-millis"}
DEC = {"type": "bytes", "logicalType": "decimal", "precision": 18, "scale": 2}

SCHEMAS = {
    "etd.executions-value": {
        "type": "record", "name": "Execution",
        "doc": "Exchange execution (fill) events, append-only",
        "fields": [
            {"name": "exec_id", "type": "string"},
            {"name": "order_id", "type": "string",
             "doc": "Parent order; many fills per order"},
            {"name": "contract_series", "type": "string"},
            {"name": "side", "type": {"type": "enum", "name": "Side",
                                       "symbols": ["BUY", "SELL"]}},
            {"name": "quantity", "type": DEC},
            {"name": "price", "type": DEC},
            {"name": "executing_member", "type": "string"},
            {"name": "exec_time", "type": TS},
        ],
    },
    "etd.executions-key": {
        "type": "record", "name": "ExecKey",
        "fields": [{"name": "exec_id", "type": "string"}],
    },
    "etd.clearing-events-value": {
        "type": "record", "name": "ClearingEvent",
        "doc": "Clearing lifecycle events (C7-style)",
        "fields": [
            {"name": "event_id", "type": "string"},
            {"name": "event_type", "type": {"type": "enum", "name": "EvType",
             "symbols": ["NOVATION", "GIVE_UP", "TAKE_UP",
                          "POSITION_NETTING", "TRADE_CORRECTION"]}},
            {"name": "exec_id", "type": "string"},
            {"name": "clearing_member_id", "type": "string"},
            {"name": "account", "type": "string"},
            {"name": "event_time", "type": TS},
        ],
    },
    "etd.clearing-events-key": {
        "type": "record", "name": "ClrKey",
        "fields": [{"name": "event_id", "type": "string"}],
    },
    "etd.positions-value": {
        "type": "record", "name": "Position",
        "doc": "CCP net position snapshot (compacted topic)",
        "fields": [
            {"name": "position_key", "type": "string"},
            {"name": "clearing_member_id", "type": "string"},
            {"name": "account", "type": "string"},
            {"name": "contract_series", "type": "string"},
            {"name": "net_quantity", "type": DEC},
            {"name": "as_of_time", "type": TS},
        ],
    },
    "etd.positions-key": {
        "type": "record", "name": "PosKey",
        "fields": [{"name": "position_key", "type": "string"}],
    },
    "emir.trade-reports-value": {
        "type": "record", "name": "EmirReport",
        "doc": "EMIR trade report submissions, dual-sided",
        "fields": [
            {"name": "report_id", "type": "string"},
            {"name": "uti", "type": "string",
             "doc": "Unique Transaction Identifier"},
            {"name": "counterparty_1", "type": "string"},
            {"name": "counterparty_2", "type": "string"},
            {"name": "exec_id", "type": "string"},
            {"name": "action_type", "type": {"type": "enum", "name": "Action",
             "symbols": ["NEWT", "MODI", "EROR", "TERM"]}},
            {"name": "notional", "type": ["null", DEC], "default": None},
            {"name": "notional_currency", "type": "string"},
            {"name": "reporting_timestamp", "type": TS},
        ],
    },
    "emir.trade-reports-key": {
        "type": "record", "name": "RptKey",
        "fields": [{"name": "report_id", "type": "string"}],
    },
    "refdata.contracts-value": {
        "type": "record", "name": "ContractRef",
        "doc": "Contract series reference data (compacted)",
        "fields": [
            {"name": "contract_series", "type": "string"},
            {"name": "product_type", "type": {"type": "enum", "name": "PType",
                                               "symbols": ["FUTURE", "OPTION"]}},
            {"name": "underlying", "type": "string"},
            {"name": "contract_multiplier", "type": DEC},
            {"name": "expiry_date", "type": {"type": "int",
                                              "logicalType": "date"}},
        ],
    },
    "refdata.contracts-key": {
        "type": "record", "name": "RefKey",
        "fields": [{"name": "contract_series", "type": "string"}],
    },
}


def register(subject: str, schema: dict):
    body = json.dumps(
        {"schema": json.dumps(schema), "schemaType": "AVRO"}
    ).encode()
    req = urllib.request.Request(
        f"{REGISTRY}/subjects/{subject}/versions",
        data=body,
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read())


if __name__ == "__main__":
    for subject, schema in SCHEMAS.items():
        result = register(subject, schema)
        print(f"{subject}: id={result.get('id')}")
