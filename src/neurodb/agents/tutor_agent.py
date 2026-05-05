"""NeuroTutorAgent for neuroscience learning with a curated knowledge library."""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import Engine

from neurodb.agents.base import BaseAgent, _DEFAULT_MODEL
from neurodb.agents.db_agent import TOOLS as _DB_TOOLS, execute_tool
from neurodb.db import get_session
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import KnowledgeSource

_MODEL = os.environ.get("NEURODB_MODEL", _DEFAULT_MODEL)

_TUTOR_SYSTEM_PROMPT = (
    "You are a neuroscience learning partner with access to a curated Knowledge Library, "
    "local study notes, local dataset tools, and your own training knowledge. "
    "For topic questions, call search_knowledge_library before relying on training knowledge alone. "
    "Whenever you cite or recommend an external resource such as a paper, review, textbook, "
    "or website, call queue_source with the title, source type, and topic context so the user "
    "can review it later. To discover candidate learning resources, call search_literature. "
    "Never fabricate paper titles, DOIs, dataset IDs, counts, or source details."
)

_TUTOR_TOOLS = [
    {
        "name": "search_knowledge_library",
        "description": "Search approved summaries in the curated Knowledge Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query."},
                "n_results": {"type": "integer", "description": "Maximum results to return."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_literature",
        "description": (
            "Return candidate neuroscience papers, reviews, textbooks, or websites for a topic. "
            "Phase LT-1 uses a built-in starter list; live PubMed/Semantic Scholar search is LT-2."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic to search for."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "queue_source",
        "description": "Queue a cited external resource for user review in the Knowledge Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Source title."},
                "source_type": {
                    "type": "string",
                    "description": "One of: paper, review, textbook, website.",
                },
                "topic_context": {
                    "type": "string",
                    "description": "Discussion context where the source was cited.",
                },
                "doi": {"type": "string", "description": "DOI if known."},
                "url": {"type": "string", "description": "URL if known."},
            },
            "required": ["title", "source_type", "topic_context"],
        },
    },
]

_STARTER_LITERATURE = [
    {
        "title": "A synaptic model of memory: long-term potentiation in the hippocampus",
        "source_type": "paper",
        "doi": "10.1038/361031a0",
        "description": "Classic review connecting hippocampal LTP to memory mechanisms.",
    },
    {
        "title": "Principles of Neural Science",
        "source_type": "textbook",
        "doi": None,
        "description": "Comprehensive textbook reference for synapses, plasticity, and systems neuroscience.",
    },
    {
        "title": "Synapses, Circuits, and the Beginnings of Memory",
        "source_type": "review",
        "doi": "10.1016/j.cell.2014.08.025",
        "description": "Review of synaptic and circuit mechanisms supporting memory.",
    },
]


def normalize_title(title: str) -> str:
    """Normalize titles for exact deduplication."""
    value = unicodedata.normalize("NFKD", title.strip().lower())
    value = re.sub(r"[^\w\s]", "", value)
    return re.sub(r"\s+", " ", value).strip()


class NeuroTutorAgent(BaseAgent):
    """Learning agent with Knowledge Library search and source queuing."""

    def __init__(
        self,
        client,
        engine: Engine,
        vector_store=None,
        model: str = _MODEL,
        prior_context: str = "",
        knowledge_store: KnowledgeLibraryStore | None = None,
    ) -> None:
        super().__init__(client, engine, vector_store, model, prior_context)
        self._knowledge_store = knowledge_store

    def _get_active_tools(self) -> list[dict]:
        return list(_TUTOR_TOOLS) + list(_DB_TOOLS)

    def _build_system_prompt(self) -> str:
        system = _TUTOR_SYSTEM_PROMPT
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.name == "queue_source":
            return self._execute_queue_source(block.input)
        if block.name == "search_knowledge_library":
            return self._execute_search_knowledge_library(block.input)
        if block.name == "search_literature":
            return self._execute_search_literature(block.input)
        return execute_tool(block.name, block.input, self._engine, self._vector_store)

    def _execute_queue_source(self, inputs: dict) -> str:
        title = inputs["title"].strip()
        normalized = normalize_title(title)
        doi = (inputs.get("doi") or "").strip() or None

        with get_session(self._engine) as session:
            if doi:
                existing = session.query(KnowledgeSource).filter_by(doi=doi).first()
            else:
                existing = session.query(KnowledgeSource).filter_by(
                    normalized_title=normalized
                ).first()
            if existing is not None:
                return json.dumps({"status": "already_exists", "id": existing.id})

            row = KnowledgeSource(
                title=title,
                normalized_title=normalized,
                doi=doi,
                url=(inputs.get("url") or None),
                source_type=inputs["source_type"],
                topic_context=inputs["topic_context"],
                status="pending",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            session.add(row)
            session.flush()
            return json.dumps({"status": "queued", "id": row.id})

    def _execute_search_knowledge_library(self, inputs: dict) -> str:
        if self._knowledge_store is None:
            return json.dumps({"error": "Knowledge library not available."})
        results = self._knowledge_store.search(
            inputs["query"],
            n=inputs.get("n_results", 5),
        )
        return json.dumps(results)

    def _execute_search_literature(self, inputs: dict) -> str:
        query = inputs["query"].lower()
        if any(term in query for term in ("ltp", "potentiation", "plasticity", "memory")):
            return json.dumps(_STARTER_LITERATURE)
        return json.dumps([])

