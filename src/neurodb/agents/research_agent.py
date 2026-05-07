"""NeuroResearchAgent for structured, evidence-grounded research scaffolding."""
import json
import os
from datetime import date

from sqlalchemy import Engine

from neurodb.agents.base import BaseAgent
from neurodb.agents.db_agent import TOOLS as _DB_TOOLS, execute_tool
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.research_tools import (
    cross_reference_datasets,
    draft_hypothesis,
    get_knowledge_growth_metrics,
    record_research_question,
)

_MODEL = os.environ.get("NEURODB_RESEARCH_MODEL", "claude-sonnet-4-6")
_RESEARCH_MAX_TOOL_ITERATIONS = int(
    os.environ.get("NEURODB_RESEARCH_MAX_TOOL_ITERATIONS", "25")
)
_RESEARCH_MAX_TOKENS = int(os.environ.get("NEURODB_RESEARCH_MAX_TOKENS", "4096"))

_RESEARCH_SYSTEM_PROMPT = (
    "You are a neuroscience research partner for NeuroDb. Your job is to turn "
    "curated learning context, local dataset metadata, study notes, and live literature "
    "search into structured research questions and draft hypotheses. Distinguish "
    "evidence, inference, speculation, and missing data. Use tools before making claims "
    "about local datasets, curated sources, prior project knowledge, or literature-search "
    "history. Hypotheses are drafts until explicitly tested. Every draft hypothesis must "
    "include confounds and limitations. Never claim a hypothesis is tested unless local "
    "DB evidence and a testing plan support that claim."
)

_RESEARCH_TOOLS = [
    {
        "name": "search_knowledge_library",
        "description": "Search approved summaries in the curated Knowledge Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_literature",
        "description": "Return candidate neuroscience papers and reviews for a topic.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "cross_reference_datasets",
        "description": "Find local datasets related to a research topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "concept_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "n_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_knowledge_growth_metrics",
        "description": "Compute current learning and research growth metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "persist": {
                    "type": "boolean",
                    "description": "When true, persist an append-only metrics snapshot.",
                },
            },
        },
    },
    {
        "name": "record_research_question",
        "description": "Persist a candidate research question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "topic_context": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["question", "topic_context"],
        },
    },
    {
        "name": "draft_hypothesis",
        "description": "Persist a structured draft hypothesis with safeguards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "mechanism": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "predictions": {"type": "array"},
                "datasets": {"type": "array", "items": {"type": "object"}},
                "confounds": {"type": "array"},
                "limitations": {"type": "string"},
                "question_id": {"type": "integer"},
                "status": {"type": "string"},
            },
            "required": [
                "title",
                "mechanism",
                "evidence",
                "predictions",
                "datasets",
                "confounds",
                "limitations",
            ],
        },
    },
]

_READ_ONLY_DB_TOOLS = [
    tool
    for tool in _DB_TOOLS
    if tool["name"] in {"query_db", "semantic_search", "get_study_notes"}
]


class NeuroResearchAgent(BaseAgent):
    """Research-layer agent for questions, evidence review, and hypothesis drafts."""

    def __init__(
        self,
        client,
        engine: Engine,
        vector_store=None,
        model: str = _MODEL,
        prior_context: str = "",
        knowledge_store: KnowledgeLibraryStore | None = None,
        literature_client=None,
        context_store=None,
        current_date: str | None = None,
        max_tool_iterations: int = _RESEARCH_MAX_TOOL_ITERATIONS,
        max_tokens: int = _RESEARCH_MAX_TOKENS,
    ) -> None:
        super().__init__(
            client,
            engine,
            vector_store,
            model,
            prior_context,
            max_tool_iterations=max_tool_iterations,
            save_partial_progress_on_budget=True,
            max_tokens=max_tokens,
        )
        self._knowledge_store = knowledge_store
        self._literature_client = literature_client
        self._context_store = context_store
        self._current_date = current_date

    def _get_active_tools(self) -> list[dict]:
        return list(_RESEARCH_TOOLS) + list(_READ_ONLY_DB_TOOLS)

    def _build_system_prompt(self) -> str:
        current_date = self._current_date or date.today().isoformat()
        system = f"{_RESEARCH_SYSTEM_PROMPT}\n\nCurrent date: {current_date}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.name == "search_knowledge_library":
            return self._execute_search_knowledge_library(block.input)
        if block.name == "search_literature":
            return self._execute_search_literature(block.input)
        if block.name == "cross_reference_datasets":
            return json.dumps(cross_reference_datasets(
                self._engine,
                block.input["query"],
                vector_store=self._vector_store,
                concept_tags=block.input.get("concept_tags"),
                sources=block.input.get("sources"),
                n_results=block.input.get("n_results", 5),
            ))
        if block.name == "get_knowledge_growth_metrics":
            return json.dumps(get_knowledge_growth_metrics(
                self._engine,
                vector_store=self._vector_store,
                knowledge_store=self._knowledge_store,
                context_store=self._context_store,
                persist=block.input.get("persist", False),
            ))
        if block.name == "record_research_question":
            return json.dumps(record_research_question(
                self._engine,
                block.input["question"],
                block.input["topic_context"],
                status=block.input.get("status", "open"),
            ))
        if block.name == "draft_hypothesis":
            return json.dumps(draft_hypothesis(
                self._engine,
                title=block.input["title"],
                mechanism=block.input["mechanism"],
                evidence=block.input.get("evidence", []),
                predictions=block.input.get("predictions", []),
                datasets=block.input.get("datasets", []),
                confounds=block.input.get("confounds", []),
                limitations=block.input["limitations"],
                question_id=block.input.get("question_id"),
                status=block.input.get("status", "draft"),
            ))
        return execute_tool(block.name, block.input, self._engine, self._vector_store)

    def _execute_search_knowledge_library(self, inputs: dict) -> str:
        if self._knowledge_store is None:
            return json.dumps({"error": "Knowledge library not available."})
        return json.dumps(self._knowledge_store.search(
            inputs["query"],
            n=inputs.get("n_results", 5),
        ))

    def _execute_search_literature(self, inputs: dict) -> str:
        if self._literature_client is None:
            from neurodb.literature_client import LiteratureSearchClient

            self._literature_client = LiteratureSearchClient(self._engine)
        return json.dumps(self._literature_client.search(inputs["query"]))

    def _build_terminal_tool_response(self, tool_trace: list[dict]) -> str | None:
        if not tool_trace:
            return None
        last_tool = next(
            (tool for tool in reversed(tool_trace) if tool["tool"] == "draft_hypothesis"),
            None,
        )
        if last_tool is None:
            return None

        try:
            result = json.loads(last_tool["result"])
        except json.JSONDecodeError:
            return None
        if result.get("status") != "drafted":
            return None

        inputs = last_tool["input"]
        lines = [
            f"Draft hypothesis saved: {result.get('title', inputs.get('title', 'Untitled'))}",
            "",
            f"Mechanism: {inputs['mechanism']}",
        ]
        lines.extend(_section_lines("Evidence", inputs.get("evidence", [])))
        lines.extend(_section_lines("Predictions", inputs.get("predictions", [])))
        lines.extend(_section_lines("Candidate datasets", inputs.get("datasets", [])))
        lines.extend(_section_lines("Confounds", inputs.get("confounds", [])))
        lines.append(f"Limitations: {inputs['limitations']}")
        lines.append("")
        lines.append(
            "Status: draft only. It is not tested or proven until a separate analysis plan "
            "is run against local evidence."
        )
        return "\n".join(lines)


def _section_lines(title: str, values: list | None) -> list[str]:
    lines = [f"{title}:"]
    if not values:
        return lines + ["- None recorded."]
    return lines + [f"- {_format_section_value(value)}" for value in values]


def _format_section_value(value) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}: {val}" for key, val in value.items())
    return str(value)
