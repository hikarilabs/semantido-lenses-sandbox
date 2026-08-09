"""Exports agent contexts, the groundings file, and runs the lint gate.

v0.5.0 rebuild. Produces:

  exports/context_baseline.md    schema tier only (the DDL-equivalent)
  exports/context_semantic.md    full bundle: schema + enriched + concepts
  exports/groundings.yaml        concept -> topic/field anchors + checksums
  exports/concepts.yaml          meaning only — the half that travels

Then runs ``semantido.lint`` twice:

  1. Gate: the model as authored must lint clean (errors fail the run).
  2. Demo: the T2 naive join (LEI = member_code) is added and shown to
     be rejected statically as SL008 — the homonym trap caught before
     any agent queries Kafka.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from topics import build_layer, registry  # noqa: E402

from semantido.exporters import (  # noqa: E402
    to_groundings_file,
    to_markdown_file,
)
from semantido.generators.semantic_layer import (  # noqa: E402
    Relationship,
    RelationshipType,
)
from semantido.lint import Severity, lint_layer  # noqa: E402

EXPORTS = Path(__file__).parent.parent / "exports"
EXPORTS.mkdir(exist_ok=True)


def main() -> int:
    layer = build_layer()

    # sanctioned joins (same-grain: order->execution via order concept id)
    layer.add_relationship(Relationship(
        from_table="etd.executions",
        to_table="etd.orders",
        join_condition='"etd.executions".order_id = "etd.orders".order_id',
        relationship_type=RelationshipType.MANY_TO_ONE,
        description="Fill fan-out: many executions per order.",
    ))

    # --- exports ------------------------------------------------------
    to_markdown_file(layer, str(EXPORTS / "context_baseline.md"),
                     include=("schema",))
    to_markdown_file(layer, str(EXPORTS / "context_semantic.md"))
    to_groundings_file(layer, str(EXPORTS / "groundings.yaml"))
    registry.to_yaml(str(EXPORTS / "concepts.yaml"))

    # --- 1. lint gate on the authored model ---------------------------
    findings = lint_layer(layer, groundings=str(EXPORTS / "groundings.yaml"))
    errors = [f for f in findings if f.severity is Severity.ERROR]
    for finding in findings:
        print(finding)
    if errors:
        print(f"\nLINT GATE FAILED: {len(errors)} error(s)")
        return 1
    print("lint gate: clean "
          f"({len(findings)} warning(s))" if findings else
          "lint gate: clean (0 findings)")

    # --- 2. demo: T2 homonym join rejected statically ------------------
    print("\n--- SL008 demo: the naive T2 join an agent might write ---")
    layer.add_relationship(Relationship(
        from_table="emir.trade-reports",
        to_table="etd.clearing-events",
        join_condition=(
            '"emir.trade-reports".counterparty_lei = '
            '"etd.clearing-events".member_code'
        ),
        relationship_type=RelationshipType.MANY_TO_ONE,
        description="NAIVE: conflates the two senses of 'counterparty'.",
    ))
    for finding in lint_layer(layer):
        if finding.code == "SL008":
            print(finding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
