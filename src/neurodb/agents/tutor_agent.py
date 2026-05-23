"""NeuroTutorAgent for neuroscience learning with a curated knowledge library."""
import json
import os
import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import Engine

from neurodb.agents.base import BaseAgent
from neurodb.agents.db_agent import TOOLS as _DB_TOOLS
from neurodb.agents.db_agent import execute_tool
from neurodb.db import get_session
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Paper

_MODEL = os.environ.get("NEURODB_AGENT_MODEL", "claude-sonnet-4-6")

try:
    from neurodb.config.model_config import get_model_for_task as _get_task_config
    _DEFAULT_MAX_TOKENS = _get_task_config("agent.loop.neuro_tutor")[2]
except Exception:
    _DEFAULT_MAX_TOKENS = 2048

_TUTOR_SYSTEM_PROMPT = (
    "You are a neuroscience learning partner with access to a curated Knowledge Library, "
    "local study notes, local dataset tools, and your own training knowledge. "
    "For topic questions, call search_knowledge_library before relying on training "
    "knowledge alone. "
    "To retrieve local context for a topic, call search_topics to find the topic ID, "
    "then get_topic_bundle to retrieve related papers, concepts, notes, and datasets. "
    "Whenever you cite or recommend an external resource such as a paper, review, textbook, "
    "or website, call queue_source with the title, source type, and topic context so the user "
    "can review it later. To discover candidate learning resources, call search_literature. "
    "Never fabricate paper titles, DOIs, dataset IDs, counts, or source details. "
    "Never write that a source is queued, in the Knowledge Library, approved, local, "
    "or cited from NeuroDb unless that state came from a successful tool result in this "
    "turn or verified local context in the prompt. If you know a concept from training "
    "knowledge but cannot verify a specific source, label it as model knowledge or "
    "needs verification; do not attach a fake citation, DOI, queue status, or library "
    "status. Before finalizing an answer that mentions papers, DOIs, datasets, claims, "
    "or queued sources, audit those references against tool results and local context; "
    "if a reference cannot be verified, say that plainly. "
    "Format user-facing answers for the chat window with readable Markdown. Use short "
    "section headings, bold emphasis, bullet or numbered lists, Markdown links, inline "
    "code, fenced code blocks, and simple Markdown tables when they improve scanning "
    "or comparison. Keep formatting restrained and readable. Do not put raw tool JSON "
    "or debug traces in the final answer. "
    "When local context includes datasets, check each dataset's usefulness state. "
    "If a dataset is 'sparse', note the evidence gap rather than presenting the record "
    "as a learning resource; suggest the user request enrichment if the topic is relevant. "
    "Treat 'research_context_ready' and 'analysis_ready' datasets as suitable learning "
    "resources and cite them with appropriate confidence."
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
        "description": "Return candidate neuroscience papers and reviews for a topic.",
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
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topic names to link to this source.",
                },
            },
            "required": ["title", "source_type", "topic_context"],
        },
    },
    {
        "name": "search_topics",
        "description": (
            "Search for topics in the NeuroDb knowledge base by name or description keyword."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search for."},
                "limit": {"type": "integer", "description": "Maximum results to return."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_topic_bundle",
        "description": (
            "Retrieve all related papers, concepts, study notes, and dataset packets "
            "for a topic. Use search_topics first to find the topic_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "integer", "description": "Topic ID from search_topics."},
            },
            "required": ["topic_id"],
        },
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
        client=None,
        engine: Engine = None,
        vector_store=None,
        model: str = _MODEL,
        prior_context: str = "",
        knowledge_store: KnowledgeLibraryStore | None = None,
        literature_client=None,
        max_tool_iterations: int = 10,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model_client=None,
        model_provider: str = "anthropic",
        context_mode: str = "contextual",
        context_bundle: dict | None = None,
    ) -> None:
        super().__init__(
            client,
            engine,
            vector_store,
            model,
            prior_context,
            max_tool_iterations=max_tool_iterations,
            max_tokens=max_tokens,
            telemetry_mode="neuro_tutor",
            model_client=model_client,
            model_provider=model_provider,
            context_mode=context_mode,
            context_bundle=context_bundle,
        )
        self._knowledge_store = knowledge_store
        self._literature_client = literature_client

    def _get_active_tools(self) -> list[dict]:
        return list(_TUTOR_TOOLS) + list(_DB_TOOLS)

    def _build_system_prompt(self) -> str:
        system = f"{_TUTOR_SYSTEM_PROMPT}\n\n{_context_prompt_rules(self._context_mode)}"
        if self._context_bundle and self._context_bundle.get("prompt_block"):
            system = f"{system}\n\n{self._context_bundle['prompt_block']}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.tool_name == "queue_source":
            return self._execute_queue_source(block.tool_input)
        if block.tool_name == "search_knowledge_library":
            return self._execute_search_knowledge_library(block.tool_input)
        if block.tool_name == "search_literature":
            return self._execute_search_literature(block.tool_input)
        if block.tool_name == "search_topics":
            return self._execute_search_topics(block.tool_input)
        if block.tool_name == "get_topic_bundle":
            return self._execute_get_topic_bundle(block.tool_input)
        return execute_tool(block.tool_name, block.tool_input, self._engine, self._vector_store)

    def _execute_queue_source(self, inputs: dict) -> str:
        title = inputs["title"].strip()
        normalized = normalize_title(title)
        doi = (inputs.get("doi") or "").strip() or None

        with get_session(self._engine) as session:
            if doi:
                existing = session.query(Paper).filter_by(doi=doi).first()
            else:
                existing = session.query(Paper).filter_by(
                    normalized_title=normalized
                ).first()
            if existing is not None:
                return json.dumps({"status": "already_exists", "id": existing.id})

            row = Paper(
                title=title,
                normalized_title=normalized,
                doi=doi,
                url=(inputs.get("url") or None),
                source_type=inputs["source_type"],
                topic_context=inputs["topic_context"],
                status="pending",
                queued_at=datetime.now(UTC).isoformat(),
            )
            session.add(row)
            session.flush()
            paper_id = row.id
            topics = inputs.get("topics") or []
            if topics:
                from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
                for topic_name in topics:
                    topic = get_or_create_topic(session, topic_name)
                    link_paper_topic(session, paper_id, topic.id)
            return json.dumps({"status": "queued", "id": paper_id})

    def _execute_search_knowledge_library(self, inputs: dict) -> str:
        if self._knowledge_store is None:
            return json.dumps({"error": "Knowledge library not available."})
        results = self._knowledge_store.search(
            inputs["query"],
            n=inputs.get("n_results", 5),
        )
        return json.dumps(results)

    def _execute_search_literature(self, inputs: dict) -> str:
        if self._literature_client is None:
            from neurodb.literature_client import LiteratureSearchClient

            self._literature_client = LiteratureSearchClient(self._engine)
        return json.dumps(self._literature_client.search(inputs["query"]))

    def _execute_search_topics(self, inputs: dict) -> str:
        if self._context_bundle and self._context_bundle.get("topic_bundle"):
            topic = self._context_bundle["topic_bundle"].get("topic") or {}
            query = (inputs.get("query") or "").lower()
            if topic.get("name") and topic["name"].lower() in query:
                return json.dumps([topic])
        from neurodb.db.topic_store import search_topics
        with get_session(self._engine) as session:
            results = search_topics(session, inputs["query"], limit=inputs.get("limit", 10))
        return json.dumps(results)

    def _execute_get_topic_bundle(self, inputs: dict) -> str:
        if self._context_bundle and self._context_bundle.get("topic_bundle"):
            topic = self._context_bundle["topic_bundle"].get("topic") or {}
            if topic.get("id") == inputs["topic_id"]:
                return json.dumps(self._context_bundle["topic_bundle"])
        from neurodb.db.topic_store import get_topic_bundle
        with get_session(self._engine) as session:
            bundle = get_topic_bundle(session, inputs["topic_id"])
        return json.dumps(bundle)


def _context_prompt_rules(mode: str) -> str:
    if mode == "general":
        return (
            "Context mode: General. Teach from your neurology training first. "
            "Use NeuroDb context only when explicitly provided or clearly requested, "
            "and label it separately."
        )
    if mode == "grounded":
        return (
            "Context mode: Strictly grounded. Use approved/local NeuroDb sources "
            "for factual literature claims. You may explain terms with model knowledge, "
            "but do not present model-only knowledge as local evidence. Include local "
            "evidence and unsupported-or-missing boundaries when answering."
        )
    return (
        "Context mode: Use NeuroDb context. Teach from model neurology knowledge, "
        "then focus the answer using available NeuroDb topics, papers, notes, "
        "claims, and dataset packets. Separate general neurology from local context."
    )
