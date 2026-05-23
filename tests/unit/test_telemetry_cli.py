from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.cli.telemetry import render_telemetry
from neurodb.schema import Base, ModelCallLog, SystemWarning


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_render_telemetry_prints_model_calls_and_warnings():
    engine = _engine()
    with Session(engine) as session:
        session.add(ModelCallLog(
            recorded_at="2026-05-23T13:45:22+00:00",
            task_type="agent.loop.neuro_tutor",
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=1234,
            output_tokens=456,
            estimated_cost_usd=0.0023,
        ))
        session.add(SystemWarning(
            recorded_at="2026-05-23T13:45:21+00:00",
            warning_type="routing_fallback",
            severity="info",
            task_type="agent.loop.neuro_tutor",
            requested_provider="anthropic",
            selected_provider="openai",
            message="selected fallback: openai",
        ))
        session.commit()

    output = render_telemetry(engine, tail=20)

    assert "Model Call Log" in output
    assert "System Warnings" in output
    assert "13:45:22 23/05/26" in output
    assert "agent.loop.neuro_tutor" in output
    assert "anthropic / claude-sonnet-4-6" in output
    assert "routing_fallback" in output
    assert "anthropic -> openai" in output


def test_render_telemetry_warnings_only_filters_sections():
    engine = _engine()

    output = render_telemetry(engine, tail=5, warnings_only=True)

    assert "Model Call Log" not in output
    assert "System Warnings" in output
    assert "No system warnings found." in output


def test_render_telemetry_filters_by_provider_and_task_type():
    engine = _engine()
    with Session(engine) as session:
        session.add(ModelCallLog(
            recorded_at="2026-05-23T13:45:22+00:00",
            task_type="summary.session",
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
        ))
        session.add(ModelCallLog(
            recorded_at="2026-05-23T13:45:23+00:00",
            task_type="agent.loop.neuro_tutor",
            provider="openai",
            model="gpt-5.4",
        ))
        session.commit()

    output = render_telemetry(engine, tail=20, provider="openai", task_type="agent.loop")

    assert "gpt-5.4" in output
    assert "claude-haiku" not in output
