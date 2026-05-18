from unittest.mock import MagicMock

from sqlalchemy import create_engine

from neurodb.agents.db_agent import NeuroDbAgent
from neurodb.db import init_db, seed_learning_sources
from neurodb.discovery_tools import DISCOVERY_TOOLS


def _make_agent(mode="local_db"):
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    client = MagicMock()
    agent = NeuroDbAgent(client, engine, mode=mode)
    return agent, client


def test_local_db_mode_passes_only_local_tools():
    agent, client = _make_agent(mode="local_db")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("what datasets do you have?", []))

    call_kwargs = client.messages.create.call_args[1]
    tool_names = {tool["name"] for tool in call_kwargs["tools"]}
    discovery_names = {tool["name"] for tool in DISCOVERY_TOOLS}
    assert tool_names.isdisjoint(discovery_names), "Discovery tools leaked into local_db mode"
    assert "query_db" in tool_names


def test_external_db_mode_includes_discovery_tools():
    agent, client = _make_agent(mode="external_db")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("search for retinotopy datasets", []))

    call_kwargs = client.messages.create.call_args[1]
    tool_names = {tool["name"] for tool in call_kwargs["tools"]}
    assert "search_external" in tool_names
    assert "inspect_external_dataset" in tool_names
    assert "suggest_import" in tool_names
    assert "query_db" in tool_names


def test_chapter_context_injected_into_system_prompt():
    agent, client = _make_agent()
    agent.chapter_context = "Ch12 — Central Visual Pathways\nTopics: retinotopy, LGN"
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("tell me about V1", []))

    call_kwargs = client.messages.create.call_args[1]
    assert "Central Visual Pathways" in call_kwargs["system"]


def test_mode_can_be_changed_between_calls():
    agent, client = _make_agent(mode="local_db")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("first message", []))
    call1 = client.messages.create.call_args[1]
    assert "search_external" not in {tool["name"] for tool in call1["tools"]}

    agent.mode = "external_db"
    list(agent.chat("second message", []))
    call2 = client.messages.create.call_args[1]
    assert "search_external" in {tool["name"] for tool in call2["tools"]}
