from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Infrastructure


def test_infra_job_rolls_back_and_records_failure(monkeypatch):
    # Setup an in-memory SQLite DB and SessionLocal replacement
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    # Insert a test infrastructure row
    db = TestSession()
    infra = Infrastructure(owner_id=1, name="test-cluster", cloud_provider="aws", config={}, status="queued")
    db.add(infra)
    db.commit()
    infra_id = infra.id
    db.close()

    # Call the internal runner with an action that raises to force the exception path
    import services.infra_jobs as infra_jobs

    monkeypatch.setattr(infra_jobs, "SessionLocal", TestSession)

    def failing_action(name, provider, cfg):
        raise RuntimeError("simulated failure")

    # Run job - should not raise, and should record failure state in DB
    infra_jobs._run_infrastructure_job(
        infra_id,
        failing_action,
        in_progress_status="provisioning",
        success_status="ready",
        failure_status="failed",
    )

    # Verify the infrastructure row was updated to failure
    db2 = TestSession()
    refreshed = db2.get(Infrastructure, infra_id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.last_error is not None and "simulated failure" in refreshed.last_error
    db2.close()
