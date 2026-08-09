"""Reflect Kafka topic schemas from a (Confluent-compatible) Schema
Registry into semantido declarative models.

Direction of authority
----------------------
  PHYSICAL layer  <- Schema Registry (authoritative, versioned).
                     Regenerated; never hand-edited.
  SEMANTIC layer  <- overlays/*.yaml (human-authored sidecar).
                     Merged into the generated models at codegen time,
                     so registry evolution never clobbers semantics.

Avro `doc` strings (the one semantic field the registry carries) seed
default descriptions; enum symbols seed sample_values.

Subject naming: TopicNameStrategy (`<topic>-value`, optional
`<topic>-key`). A record-typed key schema contributes the primary key;
otherwise the overlay's `primary_key` is used; otherwise the first field
(flagged with a TODO comment).

Nested records are flattened: attribute `settlement_ccy` for Lenses path
`settlement.ccy` (the real access path is recorded in the description,
since Lenses SQL addresses nested fields with dots).

Usage:
  python semantic/reflect.py --registry http://localhost:8081 \
      --overlay semantic/overlays/etd.yaml \
      --out semantic/topics_generated.py
  python semantic/reflect.py ... --check   # drift detection (CI): exit 1
                                           # if regeneration differs
"""

import argparse
import json
import keyword
import re
import sys
import urllib.request
from pathlib import Path

import yaml

# --------------------------------------------------------------------------
# Registry client (stdlib only)
# --------------------------------------------------------------------------


def _get(url: str):
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        return json.loads(resp.read())


def fetch_topic_schemas(registry: str, topic_filter=None):
    """Returns {topic: {"value": avro_dict, "key": avro_dict | None}}."""
    subjects = _get(f"{registry}/subjects")
    out = {}
    for subj in subjects:
        if not subj.endswith("-value"):
            continue
        topic = subj[: -len("-value")]
        if topic_filter and not re.match(topic_filter, topic):
            continue
        value = json.loads(
            _get(f"{registry}/subjects/{subj}/versions/latest")["schema"]
        )
        key = None
        key_subj = f"{topic}-key"
        if key_subj in subjects:
            key = json.loads(
                _get(f"{registry}/subjects/{key_subj}/versions/latest")["schema"]
            )
        out[topic] = {"value": value, "key": key}
    return out


# --------------------------------------------------------------------------
# Avro -> flat field list
# --------------------------------------------------------------------------

_LOGICAL = {
    "timestamp-millis": "DateTime",
    "timestamp-micros": "DateTime",
    "local-timestamp-millis": "DateTime",
    "date": "Date",
    "time-millis": "Time",
    "decimal": "Numeric",
    "uuid": "String",
}
_PRIMITIVE = {
    "string": "String",
    "int": "Integer",
    "long": "BigInteger",
    "float": "Float",
    "double": "Float",
    "boolean": "Boolean",
    "bytes": "LargeBinary",
}


def _resolve_type(avro_type):
    """Returns (sa_type, nullable, note, enum_symbols)."""
    if isinstance(avro_type, list):  # union
        non_null = [t for t in avro_type if t != "null"]
        nullable = "null" in avro_type
        sa, _, note, syms = _resolve_type(
            non_null[0] if len(non_null) == 1 else "string"
        )
        if len(non_null) > 1:
            note = f"Avro union of {non_null}; treated as string"
            sa = "String"
        return sa, nullable, note, syms
    if isinstance(avro_type, dict):
        logical = avro_type.get("logicalType")
        if logical in _LOGICAL:
            return _LOGICAL[logical], False, None, None
        t = avro_type.get("type")
        if t == "enum":
            return "String", False, None, avro_type.get("symbols")
        if t in ("array", "map"):
            return "String", False, f"Avro {t}; JSON-encoded in Lenses SQL", None
        if t == "record":
            return "RECORD", False, None, None
        if t == "fixed":
            return "LargeBinary", False, None, None
        return _resolve_type(t)
    if avro_type in _PRIMITIVE:
        return _PRIMITIVE[avro_type], False, None, None
    return "String", False, f"Unrecognized Avro type {avro_type!r}", None


def flatten_fields(record: dict, prefix=()):
    """Yields (path_tuple, field_dict, resolved) for leaf fields."""
    for field in record.get("fields", []):
        path = prefix + (field["name"],)
        sa, nullable, note, syms = _resolve_type(field["type"])
        if sa == "RECORD":
            sub = field["type"] if isinstance(field["type"], dict) else {}
            yield from flatten_fields(sub, path)
        else:
            yield path, field, (sa, nullable, note, syms)


# --------------------------------------------------------------------------
# Codegen
# --------------------------------------------------------------------------


def _class_name(topic: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^0-9a-zA-Z]+", topic) if p)


def _attr(path) -> str:
    a = "_".join(path)
    a = re.sub(r"\W", "_", a)
    if keyword.iskeyword(a) or a.startswith("_"):
        a = f"f_{a}"
    return a


def _pyrepr(v) -> str:
    return repr(v)


def generate(schemas: dict, overlay: dict) -> str:
    lines = [
        '"""GENERATED by semantic/reflect.py -- DO NOT EDIT.',
        "",
        "Physical layer reflected from the Schema Registry; semantics merged",
        "from overlay YAML. Edit the overlay, then regenerate.",
        '"""',
        "",
        "from sqlalchemy import (",
        "    BigInteger, Boolean, Column, Date, DateTime, Float, Integer,",
        "    LargeBinary, Numeric, String, Time,",
        ")",
        "from sqlalchemy.orm import DeclarativeBase",
        "",
        "from semantido import SemanticBase, semantic_table",
        "",
        "",
        "class TopicBase(SemanticBase, DeclarativeBase):",
        '    """Declarative base used only for semantic extraction."""',
        "",
        "",
    ]
    topics_overlay = overlay.get("topics", {})

    for topic, schema in sorted(schemas.items()):
        t_ov = topics_overlay.get(topic, {})
        value, key_schema = schema["value"], schema["key"]

        pk_fields = set()
        if key_schema and isinstance(key_schema, dict) and key_schema.get("type") == "record":
            pk_fields = {f["name"] for f in key_schema.get("fields", [])}
        elif t_ov.get("primary_key"):
            pk_fields = set(t_ov["primary_key"])

        fields = list(flatten_fields(value))
        if not pk_fields:
            pk_fields = {"_".join(fields[0][0])}
            pk_todo = True
        else:
            pk_todo = False

        # --- decorator ---
        dec = ["@semantic_table("]
        desc = t_ov.get("description") or value.get("doc") or f"Kafka topic {topic}"
        dec.append(f"    description={_pyrepr(desc)},")
        for slot in (
            "synonyms",
            "sql_filters",
            "application_context",
            "business_context",
            "time_dimension",
            "concept",
        ):
            if t_ov.get(slot) is not None:
                dec.append(f"    {slot}={_pyrepr(t_ov[slot])},")
        dec.append(")")
        lines.extend(dec)
        lines.append(f"class {_class_name(topic)}(TopicBase):")
        lines.append(f"    __tablename__ = {_pyrepr(topic)}")
        if pk_todo:
            lines.append(
                "    # TODO: no key schema and no overlay primary_key; "
                "defaulted to first field"
            )
        lines.append("")

        col_overlay = t_ov.get("columns", {})
        for path, field, (sa, nullable, note, syms) in fields:
            attr = _attr(path)
            lenses_path = ".".join(path)
            c_ov = col_overlay.get(lenses_path, col_overlay.get(attr, {}))
            is_pk = attr in pk_fields or lenses_path in pk_fields
            args = [_pyrepr(lenses_path)] if attr != lenses_path else []
            args.append(sa + "()" if sa == "Numeric" else sa)
            if is_pk:
                args.append("primary_key=True")
            if nullable and not is_pk:
                args.append("nullable=True")
            lines.append(f"    {attr} = Column({', '.join(args)})")

            desc_parts = []
            if c_ov.get("description"):
                desc_parts.append(c_ov["description"])
            elif field.get("doc"):
                desc_parts.append(field["doc"])
            if len(path) > 1:
                desc_parts.append(f"Lenses SQL path: {lenses_path}")
            if note:
                desc_parts.append(note)
            if desc_parts:
                lines.append(
                    f"    {attr}_description = {_pyrepr('. '.join(desc_parts))}"
                )
            samples = c_ov.get("sample_values") or syms
            if samples:
                lines.append(f"    {attr}_sample_values = {_pyrepr(list(samples))}")
            for slot in (
                "synonyms",
                "application_rules",
                "concept",
                "privacy_level",
                "is_time_dimension",
                "time_grain",
            ):
                if c_ov.get(slot) is not None:
                    lines.append(f"    {attr}_{slot} = {_pyrepr(c_ov[slot])}")
        lines.append("")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="http://localhost:8081")
    ap.add_argument("--overlay", action="append", default=[])
    ap.add_argument("--topic-filter", default=None, help="regex on topic names")
    ap.add_argument(
        "--out", default=str(Path(__file__).parent / "topics_generated.py")
    )
    ap.add_argument("--check", action="store_true", help="drift check, no write")
    args = ap.parse_args()

    overlay = {"topics": {}}
    for path in args.overlay:
        loaded = yaml.safe_load(Path(path).read_text()) or {}
        overlay["topics"].update(loaded.get("topics", {}))

    schemas = fetch_topic_schemas(args.registry, args.topic_filter)
    if not schemas:
        sys.exit("No -value subjects found (check --registry / --topic-filter)")
    code = generate(schemas, overlay)

    out = Path(args.out)
    if args.check:
        current = out.read_text() if out.exists() else ""
        if current != code:
            print("DRIFT: registry schemas differ from generated models")
            sys.exit(1)
        print("no drift")
        return
    out.write_text(code)
    print(f"generated {out} from {len(schemas)} topics")


if __name__ == "__main__":
    main()
