"""Claude API agent with tool use for NeuroDb queries."""
import json
import os
from collections.abc import Generator
from collections.abc import Iterable

from sqlalchemy import Engine, text

_DEFAULT_MODEL = "claude-opus-4-7"
_MODEL = os.environ.get("NEURODB_MODEL", _DEFAULT_MODEL)

from neurodb.db import get_session
from neurodb.study import list_tags, tag_dataset as _tag_dataset
from neurodb.vector_store import VectorStore

TOOLS = [
    {
        "name": "query_db",
        "description": (
            "Execute a read-only SQL SELECT query against the NeuroDb database "
            "and return results as JSON. Use this to count datasets, list sources, "
            "or retrieve any structured information from the database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SQL SELECT statement to execute.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "semantic_search",
        "description": (
            "Search datasets and study notes by semantic similarity using vector embeddings. "
            "Use this for natural language queries like 'find datasets related to spatial navigation'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_study_notes",
        "description": (
            "Retrieve study notes and concept tags from the database. "
            "Optionally filter by concept substring or data source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "Filter by concept tag substring (optional).",
                },
                "source": {
                    "type": "string",
                    "description": "Filter by data source — dandi, openneuro, etc. (optional).",
                },
            },
        },
    },
    {
        "name": "tag_dataset",
        "description": (
            "Tag a dataset with a study concept, creating a study note in the database. "
            "The dataset must already be ingested."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Data source name (dandi, openneuro, etc.).",
                },
                "source_id": {
                    "type": "string",
                    "description": "Dataset ID within the source (e.g. 000003).",
                },
                "concept_tag": {
                    "type": "string",
                    "description": "Concept tag to apply.",
                },
                "section_ref": {
                    "type": "string",
                    "description": "Optional section reference (e.g. 'Augustine Ch13 p.312').",
                },
                "note_text": {
                    "type": "string",
                    "description": "Optional free-form note text.",
                },
            },
            "required": ["source", "source_id", "concept_tag"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a helpful neuroscience research assistant with access to a local database "
    "of neuroscience datasets and study notes. "
    "Always ground your answers in real data retrieved via your tools. "
    "Never fabricate dataset IDs, counts, or details — if something is not found, say so clearly."
)

_MAX_TURNS = 10


def execute_tool(
    name: str,
    inputs: dict,
    engine: Engine,
    vector_store: VectorStore | None,
) -> str:
    """Dispatch a tool call and return the result as a JSON string."""
    if name == "query_db":
        return _run_query_db(inputs["sql"], engine)
    if name == "semantic_search":
        return _run_semantic_search(inputs["query"], inputs.get("n_results", 5), vector_store)
    if name == "get_study_notes":
        return _run_get_study_notes(inputs.get("concept"), inputs.get("source"), engine)
    if name == "tag_dataset":
        return _run_tag_dataset(
            inputs["source"],
            inputs["source_id"],
            inputs["concept_tag"],
            inputs.get("section_ref"),
            inputs.get("note_text"),
            engine,
            vector_store,
        )
    return json.dumps({"error": f"Unknown tool: {name}"})


def _execute_discovery_tool(name: str, inputs: dict, engine: Engine) -> str:
    from neurodb.discovery_tools import (
        run_search_external,
        run_suggest_import,
        run_suggest_learning_source,
        run_suggest_new_source,
    )

    if name == "search_external":
        return run_search_external(inputs["source"], inputs["query"], inputs.get("limit", 10))
    if name == "suggest_import":
        return run_suggest_import(
            inputs["source"],
            inputs["source_id"],
            inputs["title"],
            inputs["reason"],
            inputs.get("chapter_ref"),
            inputs.get("metadata", {}),
            engine,
        )
    if name == "suggest_learning_source":
        return run_suggest_learning_source(
            inputs["suggestion_type"],
            inputs["reference"],
            inputs["display_name"],
            inputs["reason"],
            engine,
        )
    if name == "suggest_new_source":
        return run_suggest_new_source(
            inputs["reference"],
            inputs["display_name"],
            inputs["reason"],
            engine,
        )
    return json.dumps({"error": f"Unknown discovery tool: {name}"})


def _run_query_db(sql: str, engine: Engine) -> str:
    if not sql.strip().lower().startswith("select"):
        return json.dumps({"error": "Only SELECT statements are allowed."})
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(zip(result.keys(), row)) for row in result]
        return json.dumps(rows)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _run_semantic_search(query: str, n_results: int, vector_store: VectorStore | None) -> str:
    if vector_store is None:
        return json.dumps({"error": "Vector store not available."})
    results = vector_store.search(query, n_results=n_results)
    return json.dumps(results)


def _run_get_study_notes(concept: str | None, source: str | None, engine: Engine) -> str:
    with get_session(engine) as session:
        rows = list_tags(session, concept=concept, source=source)
    return json.dumps(rows)


def _run_tag_dataset(
    source: str,
    source_id: str,
    concept_tag: str,
    section_ref: str | None,
    note_text: str | None,
    engine: Engine,
    vector_store: VectorStore | None,
) -> str:
    with get_session(engine) as session:
        note = _tag_dataset(session, source, source_id, concept_tag, section_ref, note_text)
    if note is None:
        return json.dumps({"error": f"Dataset not found: {source}:{source_id}"})
    if vector_store is not None:
        from neurodb.embed_hooks import embed_note
        embed_note(vector_store, note.id, source, source_id, concept_tag, section_ref, note_text)
    return json.dumps({"success": True, "tag_id": note.id, "concept_tag": concept_tag})


class NeuroAgent:
    """Claude API agent that answers questions about NeuroDb using tool use."""

    def __init__(
        self,
        client,
        engine: Engine,
        vector_store: VectorStore | None = None,
        model: str = _MODEL,
        prior_context: str = "",
        mode: str = "learning",
        chapter_context: str = "",
    ) -> None:
        self._client = client
        self._engine = engine
        self._vector_store = vector_store
        self._model = model
        self.prior_context = prior_context
        self.mode = mode
        self.chapter_context = chapter_context

    def _get_active_tools(self) -> list[dict]:
        from neurodb.discovery_tools import DISCOVERY_TOOLS

        active_tools = list(TOOLS)
        if self.mode == "discovery":
            active_tools.extend(DISCOVERY_TOOLS)
        return active_tools

    def _build_system_prompt(self) -> str:
        system = _SYSTEM_PROMPT
        if self.chapter_context:
            system = f"{system}\n\nCurrent reading context:\n{self.chapter_context}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.name in {
            "search_external",
            "suggest_import",
            "suggest_learning_source",
            "suggest_new_source",
        }:
            return _execute_discovery_tool(block.name, block.input, self._engine)
        return execute_tool(
            block.name, block.input, self._engine, self._vector_store
        )

    def chat(self, user_message: str, messages: list[dict]) -> Generator[str, None, None]:
        """Run one user turn, executing tools as needed, and yield response text.

        messages is mutated in place: all turns (user, tool_use, tool_result, assistant)
        are appended so the caller retains the full conversation for subsequent calls.
        """
        active_tools = self._get_active_tools()
        system = self._build_system_prompt()

        messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TURNS):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system,
                tools=active_tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_text = self._execute_tool_block(block)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [{"type": "text", "text": result_text}],
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            break

        yield "[Agent reached maximum tool iterations without a final answer]"

    def chat_stream(self, user_message: str, messages: list[dict]) -> Iterable[dict]:
        """Run one user turn with streaming output and visible tool activity."""
        active_tools = self._get_active_tools()
        system = self._build_system_prompt()

        messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TURNS):
            with self._client.messages.stream(
                model=self._model,
                max_tokens=2048,
                system=system,
                tools=active_tools,
                messages=messages,
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        yield {"type": "text_delta", "text": event.delta.text}

                final_message = stream.get_final_message()

            messages.append({"role": "assistant", "content": final_message.content})

            if final_message.stop_reason == "end_turn":
                text_blocks = [
                    block.text
                    for block in final_message.content
                    if block.type == "text"
                ]
                yield {
                    "type": "done",
                    "text": "".join(text_blocks),
                    "stop_reason": final_message.stop_reason,
                }
                return

            if final_message.stop_reason == "tool_use":
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    yield {
                        "type": "tool_start",
                        "tool_name": block.name,
                        "tool_input": block.input,
                    }
                    result_text = self._execute_tool_block(block)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": [{"type": "text", "text": result_text}],
                    })
                    yield {
                        "type": "tool_result",
                        "tool_name": block.name,
                        "result": result_text,
                    }
                messages.append({"role": "user", "content": tool_results})
                continue

            break

        yield {
            "type": "error",
            "text": "[Agent reached maximum tool iterations without a final answer]",
        }
