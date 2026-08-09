"""Shared business-concept registry (schema-independent tier).

Imported by both the hand-authored models (topics.py) and the
registry-reflected models (topics_generated.py) -- one vocabulary,
many physical realizations.
"""

from semantido.concepts import (
    ConceptRegistry,
    OntologySource,
    close_match,
    exact_match,
)

registry = ConceptRegistry()
registry.add_source(
    OntologySource(
        name="fibo",
        namespace="https://spec.edmcouncil.org/fibo/ontology/",
        version="2025Q3",
    )
)

emir_counterparty = registry.concept(
    "counterparty.emir_reporting",
    definition=(
        "The entity on whose behalf an EMIR trade report is submitted "
        "(EMIR RTS field 1.4). Identified by LEI. One of the two legal "
        "parties to the derivative contract."
    ),
    label="counterparty",
    synonyms=["reporting counterparty", "CP1"],
    external=close_match(
        "fibo",
        "https://spec.edmcouncil.org/fibo/ontology/"
        "DER/DerivativesContracts/DerivativesBasics/Counterparty",
        because="EMIR reporting counterparty is a role-restricted subset "
        "of the FIBO derivatives counterparty",
    ),
)

clearing_member = registry.concept(
    "counterparty.clearing_member",
    definition=(
        "A member of the CCP that clears trades (GCM/DCM). NOT a legal "
        "counterparty to the economic trade for EMIR reporting purposes; "
        "faces the CCP post-novation. The word 'counterparty' in clearing "
        "system docs (e.g. Eurex C7) usually means this entity."
    ),
    label="counterparty",
    synonyms=["clearing member", "clearer", "GCM", "DCM"],
    distinct_from=emir_counterparty,
    external=exact_match(
        "fibo",
        "https://spec.edmcouncil.org/fibo/ontology/"
        "FBC/FunctionalEntities/MarketsIndividuals/ClearingMember",
    ),
)

net_position = registry.concept(
    "position.net",
    definition=(
        "Post-netting exposure per (clearing member, account, contract "
        "series). Signed: positive = long, negative = short. Current "
        "state, not a flow."
    ),
    related=clearing_member,
)
