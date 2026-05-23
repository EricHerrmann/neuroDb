from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from neurodb.model_telemetry import build_system_warning, record_system_warning
from neurodb.schema import Base, SystemWarning


def test_build_system_warning_sets_fields():
    row = build_system_warning(
        warning_type="provider_missing",
        severity="warning",
        task_type="agent.loop.neuro_tutor",
        requested_provider="anthropic",
        selected_provider=None,
        message="anthropic not registered",
    )

    assert row.warning_type == "provider_missing"
    assert row.severity == "warning"
    assert row.task_type == "agent.loop.neuro_tutor"
    assert row.requested_provider == "anthropic"
    assert row.selected_provider is None
    assert row.message == "anthropic not registered"
    assert "T" in row.recorded_at


def test_record_system_warning_writes_row():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    record_system_warning(
        engine,
        warning_type="routing_fallback",
        severity="info",
        task_type="agent.loop.neuro_tutor",
        requested_provider="anthropic",
        selected_provider="openai",
        message="selected fallback: openai",
    )

    with Session(engine) as session:
        rows = session.execute(select(SystemWarning)).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.warning_type == "routing_fallback"
    assert row.selected_provider == "openai"


def test_record_system_warning_swallows_write_failures():
    # No exception should escape even when the target is unusable.
    record_system_warning(
        None,
        warning_type="routing_failed",
        severity="error",
        task_type="agent.loop.neuro_tutor",
        message="no viable provider",
    )
