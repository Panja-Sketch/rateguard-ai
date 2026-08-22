from app.engines.diff.enums import DifferenceSeverity, DifferenceType
from app.engines.diff.models import SemanticDiffResult
from app.engines.impact.graph import PricingDependencyGraph
from app.engines.reconciliation.models import RootCauseFinding, TraceDifference
from app.ipir.package import IPIRPackage


def perform_root_cause_analysis(
    trace_diffs: list[TraceDifference],
    diff_result: SemanticDiffResult,
    package: IPIRPackage,
) -> tuple[str | None, RootCauseFinding | None]:
    """Identifies the first divergent upstream node and constructs a RootCauseFinding."""
    if not trace_diffs:
        return None, None

    graph = PricingDependencyGraph(package)
    divergent_node_ids = {td.node_id for td in trace_diffs}

    first_divergent_id: str | None = None
    first_diff: TraceDifference | None = None

    # Filter divergent nodes by checking which ones have no upstream ancestors in divergent set
    root_candidates: list[TraceDifference] = []
    for td in trace_diffs:
        ancestors = set(graph.get_ancestors(td.node_id))
        if not (ancestors & divergent_node_ids):
            root_candidates.append(td)

    if root_candidates:
        first_diff = root_candidates[0]
        first_divergent_id = first_diff.node_id
    else:
        first_diff = trace_diffs[0]
        first_divergent_id = first_diff.node_id

    # Find matching SemanticDifference evidence from diff_result
    matching_semantic_diff = next(
        (d for d in diff_result.differences if d.node_id == first_divergent_id), None
    )

    if matching_semantic_diff:
        diff_type = matching_semantic_diff.difference_type
        severity = matching_semantic_diff.severity
        sem_path = matching_semantic_diff.semantic_path
        explanation = (
            f"Pricing mismatch originating at '{first_divergent_id}'. "
            f"{matching_semantic_diff.description}."
        )
    else:
        diff_type = DifferenceType.VALUE_CHANGE
        severity = DifferenceSeverity.HIGH
        sem_path = f"nodes.{first_divergent_id}"
        explanation = (
            f"Calculation divergence detected at node '{first_divergent_id}'. "
            f"Expected: {first_diff.expected_value}, Actual: {first_diff.actual_value}."
        )

    downstream = graph.get_descendants(first_divergent_id)
    abs_diff_str = (
        str(first_diff.absolute_difference) if first_diff.absolute_difference else None
    )
    sem_diff_id = matching_semantic_diff.id if matching_semantic_diff else None

    root_cause = RootCauseFinding(
        node_id=first_divergent_id,
        category=diff_type.value,
        title=f"Root Cause: {diff_type.value} at {first_divergent_id}",
        explanation=explanation,
        expected_value=first_diff.expected_value,
        actual_value=first_diff.actual_value,
        semantic_path=sem_path,
        difference_type=diff_type,
        severity=severity,
        evidence={
            "expected_value": str(first_diff.expected_value),
            "actual_value": str(first_diff.actual_value),
            "absolute_difference": abs_diff_str,
            "semantic_difference_id": sem_diff_id,
        },
        downstream_effects=downstream,
    )

    return first_divergent_id, root_cause

