"""NeuroTutorAgent for neuroscience learning with a curated knowledge library."""
import json
import os

from sqlalchemy import Engine

from neurodb.agents.base import BaseAgent
from neurodb.agents.behavior_instructions import load_agent_behavior_instructions
from neurodb.agents.db_agent import TOOLS as _DB_TOOLS
from neurodb.agents.db_agent import execute_tool
from neurodb.agents.full_text_tools import (
    FULL_TEXT_TOOLS,
    execute_search_full_text,
    execute_verify_quote,
)
from neurodb.agents.learning_plan_tools import (
    LEARNING_PLAN_TOOLS,
    build_learning_plan_terminal_response,
    execute_propose_learning_plan,
    execute_update_learning_plan,
)

# Re-exported for backward compatibility; the shared write path now lives in
# neurodb.agents.source_queue and is used by both the tutor and research agents.
from neurodb.agents.source_queue import (  # noqa: F401
    find_paper_metadata_conflicts,
    merge_existing_paper_metadata,
    normalize_title,
    queue_or_update_paper,
    replace_existing_paper_metadata,
)
from neurodb.db import get_session
from neurodb.discovery_tools import (
    READ_ONLY_DISCOVERY_TOOLS,
    run_inspect_external_dataset,
    run_search_external,
)
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Paper
from neurodb.temporal import TEMPORAL_DISCLOSURE_RULES, attach_temporal

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
    "To retrieve local context for a topic, call search_topics to find the topic grouping ID, "
    "then get_grouping_bundle to retrieve related papers, concepts, notes, and datasets. "
    "Whenever you cite or recommend an external resource such as a paper, review, preprint, "
    "textbook, or website outside a proposed learning plan, call queue_source with the title, "
    "source type, and topic context so the user can review it later. If the user explicitly "
    "asks you to correct metadata on an existing "
    "Knowledge Library source, call update_source_metadata with the source ID and corrected "
    "metadata instead of calling queue_source again. To discover candidate learning resources, "
    "call search_literature. When the user asks to search external sites for papers, "
    "reviews, or preprints, call search_literature before "
    "answering. When the user asks to find external datasets by topic, call "
    "search_external. When the user asks about an external dataset URL or source-native "
    "dataset ID, call inspect_external_dataset. Do not say you cannot search or browse "
    "external sites when one of these tools fits the request; if the tool returns no "
    "results or an error, report that result plainly. "
    "search_literature returns an envelope with result_count, a results list, and a "
    "providers map giving each source's status (ok or error). Treat only the items in "
    "results as found papers. If result_count is 0, state that the search returned no "
    "results and name any providers whose status is error (for example rate-limited or "
    "timed out); never invent papers, DOIs, or citation counts to fill an empty or "
    "failed search, and never say sources were found, queued, or saved when result_count "
    "is 0. "
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
    "resources and cite them with appropriate confidence. "
    "When the user asks for a study plan, learning plan, reading sequence, curriculum, "
    "or multi-step path, call propose_learning_plan with the full ordered read/action "
    "step list. Do not call queue_source separately for read-step sources that are only "
    "part of the proposed plan; plan read sources are queued only after the user approves "
    "the plan in Study Plan. When the user asks to modify an existing plan, call "
    "update_learning_plan. After a successful propose_learning_plan or update_learning_plan "
    "call, stop calling tools and summarize the saved plan or pending change. "
    "When the user wants a quotation, specific claim, figure, or method from a paper, "
    "call search_full_text and quote ONLY text it returns, rendering each quote with its "
    "source title and section. If search_full_text returns grounded=false, say you have no "
    "grounded full-text support rather than quoting from memory. Before presenting any "
    "verbatim quote, call verify_quote with the exact text and source_id; tag a quote "
    "[verified: Title section] ONLY after verify_quote returns matched=true. Any quoted "
    "text you did not or could not verify must be tagged [unverified - from memory]. "
    "Verified is earned from the tool result, never asserted on your own. "
    "When a quote's source was extracted from a PDF or web page (text_source pdf_* or "
    "html_extracted), note that and include the page number when present, so the reader "
    "knows it is not from a publisher-clean structured source."
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
                    "description": "One of: paper, review, preprint, textbook, website.",
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
                "abstract": {
                    "type": "string",
                    "description": "Abstract text from the search result, if available.",
                },
                "year": {"type": "integer", "description": "Publication year, if known."},
                "authors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Author names, if known.",
                },
            },
            "required": ["title", "source_type", "topic_context"],
        },
    },
    {
        "name": "update_source_metadata",
        "description": (
            "Correct DOI, URL, abstract, or year metadata for an existing Knowledge Library "
            "source. Use only when the user explicitly asks to correct a known source record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "integer",
                    "description": "Existing Knowledge Library source/paper ID to update.",
                },
                "doi": {"type": "string", "description": "Corrected DOI, if known."},
                "url": {"type": "string", "description": "Corrected URL, if known."},
                "abstract": {
                    "type": "string",
                    "description": "Corrected or fuller abstract, if known.",
                },
                "year": {"type": "integer", "description": "Corrected publication year, if known."},
                "update_reason": {
                    "type": "string",
                    "description": "Brief reason the existing metadata should be replaced.",
                },
            },
            "required": ["source_id", "update_reason"],
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
        "name": "get_grouping_bundle",
        "description": (
            "Retrieve all related papers, concepts, study notes, and dataset packets "
            "for a topic grouping. Use search_topics first to find the grouping_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "grouping_id": {"type": "integer", "description": "Topic grouping ID from search_topics."},
            },
            "required": ["grouping_id"],
        },
    },
]

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
        chunk_store=None,
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
        self._chunk_store = chunk_store

    def _get_active_tools(self) -> list[dict]:
        return (
            list(_TUTOR_TOOLS)
            + list(LEARNING_PLAN_TOOLS)
            + list(READ_ONLY_DISCOVERY_TOOLS)
            + list(_DB_TOOLS)
            + list(FULL_TEXT_TOOLS)
        )

    def _build_system_prompt(self) -> str:
        prompt_parts = [_TUTOR_SYSTEM_PROMPT]
        behavior_instructions = load_agent_behavior_instructions()
        if behavior_instructions:
            prompt_parts.append(behavior_instructions)
        prompt_parts.append(_context_prompt_rules(self._context_mode))
        prompt_parts.append(TEMPORAL_DISCLOSURE_RULES)
        system = "\n\n".join(prompt_parts)
        if self._context_bundle and self._context_bundle.get("prompt_block"):
            system = f"{system}\n\n{self._context_bundle['prompt_block']}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.tool_name == "queue_source":
            return self._execute_queue_source(block.tool_input)
        if block.tool_name == "update_source_metadata":
            return self._execute_update_source_metadata(block.tool_input)
        if block.tool_name == "search_knowledge_library":
            return self._execute_search_knowledge_library(block.tool_input)
        if block.tool_name == "search_literature":
            return self._execute_search_literature(block.tool_input)
        if block.tool_name == "search_external":
            return run_search_external(
                block.tool_input["source"],
                block.tool_input["query"],
                block.tool_input.get("limit", 10),
            )
        if block.tool_name == "inspect_external_dataset":
            return run_inspect_external_dataset(
                block.tool_input["source"],
                block.tool_input["reference"],
            )
        if block.tool_name == "search_topics":
            return self._execute_search_topics(block.tool_input)
        if block.tool_name == "get_grouping_bundle":
            return self._execute_get_grouping_bundle(block.tool_input)
        if block.tool_name == "propose_learning_plan":
            return execute_propose_learning_plan(
                self._engine, block.tool_input, origin_agent="tutor"
            )
        if block.tool_name == "update_learning_plan":
            return execute_update_learning_plan(self._engine, block.tool_input)
        if block.tool_name == "search_full_text":
            return execute_search_full_text(self._chunk_store, block.tool_input)
        if block.tool_name == "verify_quote":
            return execute_verify_quote(self._chunk_store, block.tool_input)
        return execute_tool(block.tool_name, block.tool_input, self._engine, self._vector_store)

    def _execute_queue_source(self, inputs: dict) -> str:
        self._backfill_source_metadata(inputs)
        with get_session(self._engine) as session:
            result = queue_or_update_paper(session, inputs, link_topics=True)
        if result.get("conflicts"):
            result["next_action"] = (
                "Call update_source_metadata if the user explicitly asked to "
                "correct this existing source."
            )
        return json.dumps(result)

    def _execute_update_source_metadata(self, inputs: dict) -> str:
        source_id = int(inputs["source_id"])
        with get_session(self._engine) as session:
            paper = session.get(Paper, source_id)
            if paper is None:
                return json.dumps({
                    "status": "not_found",
                    "id": source_id,
                    "message": f"No Knowledge Library source found for id {source_id}.",
                })
            updated_fields, previous_values, current_values = replace_existing_paper_metadata(
                paper, inputs
            )
            session.flush()
            return json.dumps({
                "status": "updated" if updated_fields else "unchanged",
                "id": source_id,
                "updated_fields": updated_fields,
                "previous_values": previous_values,
                "current_values": current_values or _paper_metadata_snapshot(paper),
                "update_reason": inputs["update_reason"],
            })

    def _execute_search_knowledge_library(self, inputs: dict) -> str:
        if self._knowledge_store is None:
            return json.dumps({"error": "Knowledge library not available."})
        results = self._knowledge_store.search(
            inputs["query"],
            n=inputs.get("n_results", 5),
        )
        return json.dumps(attach_temporal(results))

    def _execute_search_literature(self, inputs: dict) -> str:
        if self._literature_client is None:
            from neurodb.literature_client import LiteratureSearchClient

            self._literature_client = LiteratureSearchClient(self._engine)
        envelope = self._literature_client.search(inputs["query"])
        self._index_literature_results(envelope)
        return json.dumps(envelope)

    def _execute_search_topics(self, inputs: dict) -> str:
        if self._context_bundle and self._context_bundle.get("topic_bundle"):
            topic = (
                self._context_bundle["topic_bundle"].get("grouping")
                or self._context_bundle["topic_bundle"].get("topic")
                or {}
            )
            query = (inputs.get("query") or "").lower()
            if topic.get("name") and topic["name"].lower() in query:
                return json.dumps([topic])
        from neurodb.db.grouping_store import search_groupings

        with get_session(self._engine) as session:
            results = search_groupings(
                session, "topic", inputs["query"], limit=inputs.get("limit", 10)
            )
        return json.dumps(results)

    def _execute_get_grouping_bundle(self, inputs: dict) -> str:
        grouping_id = inputs["grouping_id"]
        if self._context_bundle and self._context_bundle.get("topic_bundle"):
            topic = (
                self._context_bundle["topic_bundle"].get("grouping")
                or self._context_bundle["topic_bundle"].get("topic")
                or {}
            )
            if topic.get("id") == grouping_id:
                return json.dumps(self._context_bundle["topic_bundle"])
        from neurodb.db.grouping_store import get_grouping_bundle

        with get_session(self._engine) as session:
            bundle = get_grouping_bundle(session, grouping_id)
        return json.dumps(bundle)

    def _build_terminal_tool_response(self, tool_trace: list[dict]) -> str | None:
        if not tool_trace:
            return None
        last = tool_trace[-1]
        if last.get("tool") in {"propose_learning_plan", "update_learning_plan"}:
            return build_learning_plan_terminal_response(last)
        if last.get("tool") != "update_source_metadata":
            return None
        try:
            result = json.loads(last["result"])
        except json.JSONDecodeError:
            return None
        status = result.get("status")
        source_id = result.get("id")
        if status == "updated":
            fields = ", ".join(result.get("updated_fields") or [])
            return f"Updated Knowledge Library source {source_id}: {fields}."
        if status == "unchanged":
            return f"Knowledge Library source {source_id} already has that metadata; no changes made."
        if status == "not_found":
            return result.get("message") or f"No Knowledge Library source found for id {source_id}."
        return None
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


def _paper_metadata_snapshot(paper: Paper) -> dict:
    return {
        "doi": paper.doi,
        "url": paper.url,
        "abstract": paper.abstract,
        "year": paper.year,
    }
