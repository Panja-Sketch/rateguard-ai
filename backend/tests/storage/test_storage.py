from app.storage import (
    AssuranceRunRecord,
    EvidenceRecord,
    EvidenceType,
    FirestoreRunStore,
    InMemoryRunStore,
    RunEvent,
)


def test_01_in_memory_run_store_lifecycle() -> None:
    store = InMemoryRunStore()

    run = AssuranceRunRecord(
        run_id="RUN-TEST-001",
        left_package_id="AZ_HO3_2026_09",
        right_package_id="AZ_HO3_2026_09_DEFECTIVE",
    )
    store.create_run(run)

    fetched = store.get_run("RUN-TEST-001")
    assert fetched is not None
    assert fetched.left_package_id == "AZ_HO3_2026_09"

    event = RunEvent(
        event_id="EVT-01",
        run_id="RUN-TEST-001",
        stage="TESTING",
        agent_name="TestAgent",
        action="TEST_ACTION",
    )
    store.add_event("RUN-TEST-001", event)

    events = store.get_events("RUN-TEST-001")
    assert len(events) == 1
    assert events[0].action == "TEST_ACTION"

    evidence = EvidenceRecord(
        evidence_id="EV-01",
        run_id="RUN-TEST-001",
        evidence_type=EvidenceType.SEMANTIC_DIFF,
        title="Test Evidence",
        description="Test description",
    )
    store.add_evidence("RUN-TEST-001", evidence)

    ev_list = store.get_evidence("RUN-TEST-001")
    assert len(ev_list) == 1
    assert ev_list[0].title == "Test Evidence"


def test_02_firestore_run_store_fallback_in_unit_test() -> None:
    # FirestoreRunStore falls back cleanly to InMemoryRunStore when offline / unauthenticated
    store = FirestoreRunStore(project_id="rateguard-ai", fallback_on_error=True)

    run = AssuranceRunRecord(
        run_id="RUN-FS-001",
        left_package_id="AZ_HO3_2026_09",
        right_package_id="AZ_HO3_2026_09_DEFECTIVE",
    )
    store.create_run(run)

    fetched = store.get_run("RUN-FS-001")
    assert fetched is not None
    assert fetched.run_id == "RUN-FS-001"
