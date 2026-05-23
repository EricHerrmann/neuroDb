"""NeuroResearchAgent for structured, evidence-grounded research scaffolding."""
import json
import os
from datetime import date

from sqlalchemy import Engine

from neurodb.agents.base import BaseAgent
from neurodb.agents.db_agent import TOOLS as _DB_TOOLS
from neurodb.agents.db_agent import execute_tool
from neurodb.discovery_tools import (
    READ_ONLY_DISCOVERY_TOOLS,
    run_inspect_external_dataset,
    run_search_external,
)
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
try:
    from neurodb.config.model_config import get_model_for_task as _get_task_config
    _RESEARCH_MAX_TOKENS = _get_task_config("agent.loop.neuro_research")[2]
except Exception:
    _RESEARCH_MAX_TOKENS = int(os.environ.get("NEURODB_RESEARCH_MAX_TOKENS", "4096"))

_RESEARCH_SYSTEM_PROMPT = (
    "You are a neuroscience research partner for NeuroDb. Your job is to turn "
    "curated learning context, local dataset metadata, study notes, and live literature "
    "search into structured research questions and draft hypotheses. Distinguish "
    "evidence, inference, speculation, and missing data. Use tools before making claims "
    "about local datasets, curated sources, prior project knowledge, or literature-search "
    "history. Hypotheses are drafts until explicitly tested. Every draft hypothesis must "
    "include confounds and limitations. Never claim a hypothesis is tested unless local "
    "DB evidence and a testing plan support that claim. "
    "Never write that a source is queued, in the Knowledge Library, approved, local, "
    "or cited from NeuroDb unless that state came from a successful tool result in this "
    "turn or verified local context in the prompt. If you know a concept from training "
    "knowledge but cannot verify a specific source, label it as model knowledge or "
    "needs verification; do not attach a fake citation, DOI, queue status, or library "
    "status. Before finalizing an answer that mentions papers, DOIs, datasets, claims, "
    "evidence links, or queued sources, audit those references against tool results "
    "and local context; if a reference cannot be verified, say that plainly. "
    "When the user asks you to check "
    "an external dataset URL or source-native id, call inspect_external_dataset instead "
    "of saying you cannot browse. When the user asks to find external datasets by topic, "
    "call search_external. Format user-facing answers for the chat window with readable "
    "Markdown. Use short section headings, bold emphasis, bullet or numbered lists, "
    "Markdown links, inline code, fenced code blocks, and simple Markdown tables when "
    "they improve scanning or comparison. Keep formatting restrained and readable. Do "
    "not put raw tool JSON or debug traces in the final answer. "
    "Before answering a research question, call get_question_bundle to retrieve the active "
    "topic, hypotheses, approved claims, and open gaps; use add_evidence_link to ground "
    "hypothesis drafts in local sources rather than free-text evidence; use add_gap when "
    "local evidence is insufficient to support a claim. "
    "When you find a relevant paper or review during research, call nominate_paper to queue "
    "it for Knowledge Library approval — do not just mention it in the answer. "
    "When the user asks for dataset suggestions or you identify a relevant external dataset "
    "via search_external or inspect_external_dataset, call suggest_dataset_import to add it "
    "to the import queue. "
    "When local context includes datasets, treat only 'research_context_ready' or "
    "'analysis_ready' datasets as supporting evidence for claims. Label 'sparse' and "
    "'partial' datasets as insufficient for claims and record them as evidence gaps "
    "using add_gap rather than citing them as support."
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
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["source", "summary"],
                    },
                },
                "predictions": {"type": "array", "items": {"type": "string"}},
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dataset_id": {"type": "string"},
                            "relevance": {"type": "string"},
                        },
                        "required": ["dataset_id", "relevance"],
                    },
                },
                "confounds": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "string"},
                "question_id": {"type": "integer"},
                "status": {"type": "string"},
            },
            "required": [
                "title",
                "mechanism",
                "predictions",
                "confounds",
                "limitations",
            ],
        },
    },
    {
        "name": "extract_claims",
        "description": (
            "Extract candidate claims from an approved paper using the paper's "
            "title, abstract, and summary. Stores each as a candidate claim for review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "integer",
                    "description": "ID of the approved paper to extract claims from.",
                },
            },
            "required": ["paper_id"],
        },
    },
    {
        "name": "update_claim_status",
        "description": "Approve or reject a candidate claim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "description": "approved or rejected",
                },
            },
            "required": ["claim_id", "status"],
        },
    },
    {
        "name": "add_evidence_link",
        "description": (
            "Attach a structured evidence link to a hypothesis from a claim, paper, "
            "dataset packet, or study note."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hypothesis_id": {"type": "integer"},
                "link_type": {
                    "type": "string",
                    "description": "supports, contradicts, or contextualizes",
                },
                "source_type": {
                    "type": "string",
                    "description": "claim, paper, dataset, or note",
                },
                "source_id": {
                    "type": "integer",
                    "description": "ID of the source object",
                },
            },
            "required": ["hypothesis_id", "link_type", "source_type", "source_id"],
        },
    },
    {
        "name": "add_gap",
        "description": (
            "Record a named evidence gap for a research question or hypothesis. "
            "You MUST supply at least one of question_id or hypothesis_id — "
            "the call will fail if both are omitted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "gap_type": {
                    "type": "string",
                    "description": (
                        "missing_dataset, missing_paper, missing_evidence, "
                        "unsupported_claim, or other"
                    ),
                },
                "question_id": {"type": "integer"},
                "hypothesis_id": {"type": "integer"},
            },
            "required": ["description", "gap_type"],
        },
    },
    {
        "name": "resolve_gap",
        "description": "Mark an evidence gap as resolved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gap_id": {"type": "integer"},
            },
            "required": ["gap_id"],
        },
    },
    {
        "name": "get_question_bundle",
        "description": (
            "Retrieve the full workspace context for a research question: "
            "topic, hypotheses, approved claims, and open gaps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "integer"},
            },
            "required": ["question_id"],
        },
    },
    {
        "name": "nominate_paper",
        "description": (
            "Nominate a paper or review for the Knowledge Library. Creates a pending entry "
            "that requires human approval before it is searchable. Use when you discover a "
            "relevant paper during research and want to flag it for the knowledge library."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "source_type": {
                    "type": "string",
                    "description": "paper, review, textbook, or website",
                },
                "topic_context": {
                    "type": "string",
                    "description": "Why this source is relevant to current research",
                },
                "url": {"type": "string"},
                "doi": {"type": "string"},
                "abstract": {"type": "string"},
            },
            "required": ["title", "source_type", "topic_context"],
        },
    },
    {
        "name": "suggest_dataset_import",
        "description": (
            "Add an external dataset to the import queue for later ingestion. Use when the "
            "user asks for dataset suggestions or when search_external or "
            "inspect_external_dataset surfaces a dataset relevant to the current research."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "openneuro, neurovault, dandi, or allen_brain",
                },
                "source_id": {"type": "string"},
                "title": {"type": "string"},
                "reason": {
                    "type": "string",
                    "description": "Why this dataset is relevant to current research",
                },
            },
            "required": ["source", "source_id", "title", "reason"],
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
        client=None,
        engine: Engine = None,
        vector_store=None,
        model: str = _MODEL,
        prior_context: str = "",
        knowledge_store: KnowledgeLibraryStore | None = None,
        literature_client=None,
        context_store=None,
        current_date: str | None = None,
        max_tool_iterations: int = _RESEARCH_MAX_TOOL_ITERATIONS,
        max_tokens: int = _RESEARCH_MAX_TOKENS,
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
            save_partial_progress_on_budget=True,
            max_tokens=max_tokens,
            telemetry_mode="neuro_research",
            model_client=model_client,
            model_provider=model_provider,
            context_mode=context_mode,
            context_bundle=context_bundle,
        )
        self._knowledge_store = knowledge_store
        self._literature_client = literature_client
        self._context_store = context_store
        self._current_date = current_date

    def _get_active_tools(self) -> list[dict]:
        return list(_RESEARCH_TOOLS) + list(READ_ONLY_DISCOVERY_TOOLS) + list(_READ_ONLY_DB_TOOLS)

    def _build_system_prompt(self) -> str:
        current_date = self._current_date or date.today().isoformat()
        system = (
            f"{_RESEARCH_SYSTEM_PROMPT}\n\n"
            f"{_context_prompt_rules(self._context_mode)}\n\n"
            f"Current date: {current_date}"
        )
        if self._context_bundle and self._context_bundle.get("prompt_block"):
            system = f"{system}\n\n{self._context_bundle['prompt_block']}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
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
        if block.tool_name == "cross_reference_datasets":
            return json.dumps(cross_reference_datasets(
                self._engine,
                block.tool_input["query"],
                vector_store=self._vector_store,
                concept_tags=block.tool_input.get("concept_tags"),
                sources=block.tool_input.get("sources"),
                n_results=block.tool_input.get("n_results", 5),
            ))
        if block.tool_name == "get_knowledge_growth_metrics":
            return json.dumps(get_knowledge_growth_metrics(
                self._engine,
                vector_store=self._vector_store,
                knowledge_store=self._knowledge_store,
                context_store=self._context_store,
                persist=block.tool_input.get("persist", False),
            ))
        if block.tool_name == "record_research_question":
            return json.dumps(record_research_question(
                self._engine,
                block.tool_input["question"],
                block.tool_input["topic_context"],
                status=block.tool_input.get("status", "open"),
            ))
        if block.tool_name == "draft_hypothesis":
            return json.dumps(draft_hypothesis(
                self._engine,
                title=block.tool_input["title"],
                mechanism=block.tool_input["mechanism"],
                evidence=block.tool_input.get("evidence", []),
                predictions=block.tool_input.get("predictions", []),
                datasets=block.tool_input.get("datasets", []),
                confounds=block.tool_input.get("confounds", []),
                limitations=block.tool_input["limitations"],
                question_id=block.tool_input.get("question_id"),
                status=block.tool_input.get("status", "draft"),
            ))
        if block.tool_name == "extract_claims":
            return json.dumps(self._execute_extract_claims(block.tool_input))
        if block.tool_name == "update_claim_status":
            from neurodb.db import get_session
            from neurodb.db.claim_store import update_claim_status as _update_claim_status
            with get_session(self._engine) as session:
                return json.dumps(_update_claim_status(
                    session,
                    block.tool_input["claim_id"],
                    block.tool_input["status"],
                ))
        if block.tool_name == "add_evidence_link":
            return json.dumps(self._execute_add_evidence_link(block.tool_input))
        if block.tool_name == "add_gap":
            from neurodb.db import get_session
            from neurodb.db.claim_store import add_gap as _add_gap
            try:
                with get_session(self._engine) as session:
                    gap = _add_gap(
                        session,
                        block.tool_input["description"],
                        block.tool_input["gap_type"],
                        question_id=block.tool_input.get("question_id"),
                        hypothesis_id=block.tool_input.get("hypothesis_id"),
                    )
                    return json.dumps({"id": gap.id, "status": gap.status, "gap_type": gap.gap_type})
            except ValueError as exc:
                return json.dumps({"error": str(exc)})
        if block.tool_name == "resolve_gap":
            from neurodb.db import get_session
            from neurodb.db.claim_store import resolve_gap as _resolve_gap
            with get_session(self._engine) as session:
                return json.dumps(_resolve_gap(session, block.tool_input["gap_id"]))
        if block.tool_name == "get_question_bundle":
            if self._context_bundle and self._context_bundle.get("question_bundle"):
                question = self._context_bundle["question_bundle"].get("question") or {}
                if question.get("id") == block.tool_input["question_id"]:
                    return json.dumps(self._context_bundle["question_bundle"])
            from neurodb.db import get_session
            from neurodb.db.claim_store import get_question_bundle as _get_question_bundle
            with get_session(self._engine) as session:
                return json.dumps(_get_question_bundle(session, block.tool_input["question_id"]))
        if block.tool_name == "nominate_paper":
            return self._execute_nominate_paper(block.tool_input)
        if block.tool_name == "suggest_dataset_import":
            return self._execute_suggest_dataset_import(block.tool_input)
        return execute_tool(block.tool_name, block.tool_input, self._engine, self._vector_store)

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

    def _execute_extract_claims(self, inputs: dict) -> dict:
        from neurodb.db import get_session
        from neurodb.db.claim_store import create_claim
        from neurodb.schema import Paper

        paper_id = inputs["paper_id"]
        with get_session(self._engine) as session:
            paper = session.get(Paper, paper_id)
            if paper is None:
                return {"error": f"Paper {paper_id} not found"}
            if paper.status != "approved":
                return {"error": f"Paper {paper_id} is not approved (status={paper.status!r})"}

            parts = [f"Title: {paper.title}"]
            if paper.abstract:
                parts.append(f"Abstract: {paper.abstract}")
            if paper.summary:
                parts.append(f"Summary: {paper.summary}")
            context = "\n\n".join(parts)

            prompt = (
                "Extract distinct claims from this neuroscience paper. "
                "Return a JSON array of objects, each with 'text' (string) and "
                "'claim_type' (one of: finding, limitation, method, question).\n\n"
                f"{context}\n\nReturn only the JSON array."
            )
            response = self._model_client.create_message(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                system="",
                tools=[],
                max_tokens=1024,
            )
            text_blocks = [b for b in response.content if b.type == "text" and b.text]
            if not text_blocks:
                return {"error": "Claim extraction returned no text content"}
            raw = text_blocks[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0].strip()
            try:
                candidate_claims = json.loads(raw)
            except (json.JSONDecodeError, IndexError):
                return {"error": "Failed to parse claim extraction response", "raw": raw}
            if not isinstance(candidate_claims, list):
                return {"error": "Claim extraction returned non-array JSON", "raw": raw}

            created = []
            for item in candidate_claims:
                if not isinstance(item, dict) or "text" not in item or "claim_type" not in item:
                    continue
                try:
                    claim = create_claim(session, paper_id, item["text"], item["claim_type"])
                    created.append({
                        "id": claim.id,
                        "text": claim.text,
                        "claim_type": claim.claim_type,
                    })
                except ValueError:
                    continue
            return {
                "paper_id": paper_id,
                "claims_created": len(created),
                "claims": created,
            }

    def _execute_add_evidence_link(self, inputs: dict) -> dict:
        from neurodb.db import get_session
        from neurodb.db.claim_store import add_evidence_link as _add_evidence_link

        source_type = inputs["source_type"]
        source_id = inputs["source_id"]
        source_kwargs = {
            "claim": {"claim_id": source_id},
            "paper": {"paper_id": source_id},
            "dataset": {"packet_id": source_id},
            "note": {"note_id": source_id},
        }
        if source_type not in source_kwargs:
            return {
                "error": (
                    f"Unknown source_type: {source_type!r}. "
                    "Valid: claim, paper, dataset, note"
                )
            }

        with get_session(self._engine) as session:
            link = _add_evidence_link(
                session,
                inputs["hypothesis_id"],
                inputs["link_type"],
                **source_kwargs[source_type],
            )
            return {
                "id": link.id,
                "hypothesis_id": link.hypothesis_id,
                "link_type": link.link_type,
                "source_type": source_type,
                "source_id": source_id,
            }

    def _execute_nominate_paper(self, inputs: dict) -> str:
        from datetime import UTC, datetime
        from neurodb.agents.tutor_agent import normalize_title
        from neurodb.db import get_session
        from neurodb.schema import Paper as PaperModel

        title = inputs["title"].strip()
        normalized = normalize_title(title)
        doi = (inputs.get("doi") or "").strip() or None

        with get_session(self._engine) as session:
            existing = (
                session.query(PaperModel).filter_by(doi=doi).first()
                if doi
                else session.query(PaperModel).filter_by(normalized_title=normalized).first()
            )
            if existing is not None:
                return json.dumps({"status": "already_exists", "id": existing.id})
            row = PaperModel(
                title=title,
                normalized_title=normalized,
                doi=doi,
                url=(inputs.get("url") or None),
                source_type=inputs["source_type"],
                topic_context=inputs["topic_context"],
                abstract=(inputs.get("abstract") or None),
                status="pending",
                queued_at=datetime.now(UTC).isoformat(),
            )
            session.add(row)
            session.flush()
            return json.dumps({"status": "queued", "id": row.id})

    def _execute_suggest_dataset_import(self, inputs: dict) -> str:
        from neurodb.discovery_tools import run_suggest_import
        return run_suggest_import(
            source=inputs["source"],
            source_id=inputs["source_id"],
            title=inputs["title"],
            reason=inputs["reason"],
            chapter_ref=None,
            metadata={},
            engine=self._engine,
        )

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


def _context_prompt_rules(mode: str) -> str:
    if mode == "general":
        return (
            "Context mode: General. You may brainstorm and explain mechanisms from "
            "model neurology knowledge, but label ungrounded research ideas as model "
            "reasoning rather than local evidence."
        )
    if mode == "grounded":
        return (
            "Context mode: Strictly grounded. Start from approved/local evidence, "
            "claims, notes, and question bundles. Do not present a research conclusion "
            "without local support. If support is missing, identify or record an "
            "evidence gap instead."
        )
    return (
        "Context mode: Use NeuroDb context. Use model neurology knowledge for "
        "reasoning, but organize the answer around available question bundles, "
        "topic context, approved claims, evidence links, and gaps."
    )
