"""semantido semantic layer over Lenses/Kafka topics — v0.5.0 rebuild.

Topics are modelled as SQLAlchemy declarative classes purely as schema
descriptors — no engine, no DDL is ever emitted. ``__tablename__`` is the
Kafka topic name as seen by Lenses SQL (backtick it in queries because of
the dots).

The scenario is an ETD trade lifecycle (exchange executions -> clearing
events -> netted positions -> EMIR reports) engineered with four
streaming-specific semantic traps. NEW in the 0.5.0 rebuild: the traps
that are really *grain* statements are now declared as first-class
``grain=`` on their concepts, so ``semantido.lint`` (SL008) rejects
grain-mismatched joins statically — before any agent queries Kafka:

  T1  Compacted-topic trap: `etd.positions` rows are snapshots
      (grain "position_snapshot"), not events. Aggregating full history
      double-counts superseded snapshots.
  T2  Counterparty homonym: EMIR reporting counterparty (a legal
      entity, LEI) vs clearing member (a membership code) — declared
      DISTINCT_FROM with different grains ("legal_entity" vs
      "clearing_membership"), so the naive LEI=member_code join is an
      SL008 error, not just a prose warning.
  T3  Side vs direction: execution side (BUY/SELL, grain "execution")
      is not position direction (LONG/SHORT, grain "position_snapshot").
  T4  Event time vs Kafka ingestion time: business time axes declared
      per topic; `_meta.timestamp` is processing time.

Plus the classics, now also grain-typed: order (grain "order") ->
fills (grain "execution") fan-out, and EMIR dual-sided reporting
(grain "report": two reports per trade, so COUNT(reports) != trades).
"""

from sqlalchemy import BigInteger, Column, DateTime, Numeric, String
from sqlalchemy.orm import DeclarativeBase

from semantido import ConceptRegistry, OntologySource, SemanticBase, semantic_table
from semantido.generators.concept_registry import exact_match

# ------------------------------------------------------------------ #
# Concept registry: meaning only — this half travels                  #
# ------------------------------------------------------------------ #

registry = ConceptRegistry(namespace="etd_streaming")

registry.add_source(OntologySource(
    name="gleif", namespace="https://www.gleif.org/", version="2026",
    profile="Global LEI Foundation",
))
registry.add_source(OntologySource(
    name="emir", namespace="urn:eu:regulation:648-2012", version="refit-2024",
    profile="EMIR trade reporting",
))

order = registry.concept(
    "order",
    "A client order as submitted to the exchange. One order fills into "
    "one or more executions — counting executions counts fills, not "
    "orders.",
    grain="order",
)

execution = registry.concept(
    "execution",
    "An exchange fill event. Side is BUY/SELL from the aggressor's "
    "perspective and says nothing about the resulting net position "
    "direction.",
    grain="execution",
    synonyms=["fill", "trade"],
)

position_snapshot = registry.concept(
    "position_snapshot",
    "The netted position state for one (member, account, contract) key "
    "at a point in time, published to a COMPACTED topic. Each record "
    "supersedes the previous one for its key: only latest-per-key is a "
    "position; any aggregate over full history double-counts. "
    "net_quantity carries the direction sign (positive LONG, negative "
    "SHORT).",
    grain="position_snapshot",
    synonyms=["position", "net position"],
    distinct_from=execution,
)

reporting_counterparty = registry.concept(
    "reporting_counterparty",
    "The legal entity with the EMIR Art. 9 reporting obligation, "
    "identified by LEI. An entity-level identity that exists "
    "independently of any clearing arrangement.",
    grain="legal_entity",
    synonyms=["counterparty", "reporting party"],
    external=[exact_match("gleif", "gleif:lei")],
)

clearing_member = registry.concept(
    "clearing_member",
    "A CCP clearing membership, identified by member code. One legal "
    "entity can hold several memberships; a member code is not an LEI "
    "and must never be joined to one.",
    grain="clearing_membership",
    synonyms=["counterparty", "member"],
    distinct_from=reporting_counterparty,
)

trade_report = registry.concept(
    "emir_trade_report",
    "One side of an EMIR trade report. Dual-sided reporting means two "
    "reports per trade when both counterparties are in scope: "
    "COUNT(reports) is not COUNT(trades). Lifecycle action types "
    "(NEWT/MODI/EROR) mean the latest state per UTI is authoritative.",
    grain="report",
    external=[exact_match("emir", "emir:trade-report")],
)


# ------------------------------------------------------------------ #
# Topic descriptors: the groundings half — this stays with Kafka      #
# ------------------------------------------------------------------ #

class TopicBase(SemanticBase, DeclarativeBase):
    """Declarative base used only for semantic extraction (never bound)."""


@semantic_table(
    description="Client orders as submitted. One row per order event.",
    concept="order",
    time_dimension="submitted_at",
)
class Orders(TopicBase):
    __tablename__ = "etd.orders"
    order_id = Column(String(20), primary_key=True)
    order_id_concept = "order"
    account = Column(String(12))
    contract = Column(String(20))
    quantity = Column(BigInteger)
    quantity_description = "Ordered quantity; fills may sum to less (partials)."
    submitted_at = Column(DateTime)
    submitted_at_description = "Business event time, NOT the Kafka timestamp."
    submitted_at_is_time_dimension = True
    submitted_at_time_grain = "second"


@semantic_table(
    description="Exchange executions (fills). One order fans out to one "
                "or more rows here — counting rows counts fills, not "
                "orders.",
    concept="execution",
    time_dimension="exec_time",
    application_context="side is BUY/SELL aggressor convention; never "
                        "infer LONG/SHORT from it (see position_snapshot).",
)
class Executions(TopicBase):
    __tablename__ = "etd.executions"
    exec_id = Column(String(20), primary_key=True)
    exec_id_concept = "execution"
    order_id = Column(String(20))
    order_id_description = "Parent order (fan-out join key)."
    order_id_concept = "order"
    member_code = Column(String(10))
    member_code_description = "Executing clearing membership code."
    member_code_concept = "clearing_member"
    side = Column(String(4))
    side_sample_values = ["BUY", "SELL"]
    exec_qty = Column(BigInteger)
    exec_price = Column(Numeric(18, 6))
    exec_time = Column(DateTime)
    exec_time_description = "Business event time; `_meta.timestamp` is "\
                            "Kafka ingestion time and must not be used "\
                            "for trade-date logic."
    exec_time_is_time_dimension = True
    exec_time_time_grain = "second"


@semantic_table(
    description="Clearing lifecycle events (novation, give-up, netting "
                "runs) keyed by clearing membership.",
    concept="clearing_member",
    time_dimension="event_time",
)
class ClearingEvents(TopicBase):
    __tablename__ = "etd.clearing-events"
    event_id = Column(String(20), primary_key=True)
    member_code = Column(String(10))
    member_code_description = "CCP membership code — NOT an LEI."
    member_code_concept = "clearing_member"
    event_type = Column(String(12))
    event_type_sample_values = ["NOVATION", "GIVE_UP", "NETTING"]
    event_time = Column(DateTime)
    event_time_is_time_dimension = True
    event_time_time_grain = "second"


@semantic_table(
    description="COMPACTED state topic: netted positions per (member, "
                "account, contract). Records supersede by key; browsing "
                "shows multiple records per key until compaction.",
    concept="position_snapshot",
    application_context="COMPACTED topic: the only valid aggregate is "
                        "over latest-per-key state — a Lenses-dialect "
                        "concern (_meta.offset), deliberately NOT a "
                        "sql_filter because it is not SQL over this "
                        "schema. "
                        "state. In Lenses SQL, group by key and take the "
                        "max-offset record, or query the table projection.",
    time_dimension="as_of",
)
class Positions(TopicBase):
    __tablename__ = "etd.positions"
    position_key = Column(String(40), primary_key=True)
    position_key_concept = "position_snapshot"
    member_code = Column(String(10))
    member_code_concept = "clearing_member"
    account = Column(String(12))
    contract = Column(String(20))
    net_quantity = Column(BigInteger)
    net_quantity_description = "Signed: positive LONG, negative SHORT. "\
                               "This — not execution side — is direction."
    as_of = Column(DateTime)
    as_of_is_time_dimension = True
    as_of_time_grain = "second"


@semantic_table(
    description="EMIR trade reports, one row per report side per "
                "lifecycle action. Dual-sided: in-scope trades appear "
                "twice (one per reporting counterparty).",
    concept="emir_trade_report",
    sql_filters=["action_type <> 'EROR'"],
    application_context="Latest action per UTI is the trade state; "
                        "count distinct UTIs for trade counts, never "
                        "report rows.",
    time_dimension="reporting_timestamp",
)
class TradeReports(TopicBase):
    __tablename__ = "emir.trade-reports"
    report_id = Column(String(24), primary_key=True)
    report_id_concept = "emir_trade_report"
    uti = Column(String(52))
    uti_description = "Unique Trade Identifier — the trade-level key."
    counterparty_lei = Column(String(20))
    counterparty_lei_description = "Reporting counterparty LEI (entity), "\
                                   "NOT a clearing member code."
    counterparty_lei_concept = "reporting_counterparty"
    action_type = Column(String(4))
    action_type_sample_values = ["NEWT", "MODI", "EROR"]
    reporting_timestamp = Column(DateTime)
    reporting_timestamp_is_time_dimension = True
    reporting_timestamp_time_grain = "second"


def build_layer():
    """Extracts the layer with the registry attached (meaning + grounding)."""
    registry.validate()
    return TopicBase.get_semantic_bridge().sync_from_models(
        concept_registry=registry
    )
