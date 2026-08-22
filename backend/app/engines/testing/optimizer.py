from app.engines.testing.models import PricingTestScenario
from app.engines.testing.scorer import score_scenario


def optimize_test_plan(
    candidates: list[PricingTestScenario], max_scenarios: int = 15
) -> list[PricingTestScenario]:
    """Applies a greedy risk-directed selection algorithm to pick a minimal scenario subset."""
    # 1. Score all candidates
    for cand in candidates:
        cand.score = score_scenario(cand)

    # Sort candidates by score descending, then by scenario ID ascending
    sorted_candidates = sorted(candidates, key=lambda c: (-c.score, c.id))

    selected: list[PricingTestScenario] = []
    covered_tags: set[str] = set()
    covered_nodes: set[str] = set()
    covered_risk_combos: set[tuple] = set()

    for cand in sorted_candidates:
        cand_tags = set(cand.tags)
        cand_nodes = set(cand.target_node_ids)
        combo_key = (
            cand.risk_values.get("roof_age"),
            cand.risk_values.get("territory"),
            cand.effective_date,
            cand.transaction_type,
        )

        if combo_key in covered_risk_combos:
            continue

        adds_new_node = not cand_nodes.issubset(covered_nodes) if cand_nodes else False
        adds_new_tag = not cand_tags.issubset(covered_tags)

        if adds_new_node or adds_new_tag or "BOUNDARY" in cand_tags or "CONTROL" in cand_tags:
            selected.append(cand)
            covered_tags.update(cand_tags)
            covered_nodes.update(cand_nodes)
            covered_risk_combos.add(combo_key)

        if len(selected) >= max_scenarios:
            break

    # Assign clean scenario IDs to selected plan (RG-001, RG-002, ...)
    for idx, sc in enumerate(selected, start=1):
        sc.id = f"RG-{idx:03d}"

    return selected

