"""Compatibility facade for the explainable domain decision policy."""

from unified_intelligence.domain.decisions import UnifiedDecisionPolicy


def create_unified_recommendation(inventory: dict, delivery: dict | None = None) -> dict:
    return UnifiedDecisionPolicy().evaluate(inventory, delivery).to_dict()
