"""Cross-session memory via a ChromaDB agent_context collection."""
import uuid

_COLLECTION_NAME = "agent_context"
_RELEVANCE_THRESHOLD = 0.7  # cosine distance; summaries above this are not injected

_SUMMARY_PROMPT = """You are summarizing a neuroscience research session for future reference.
Given the conversation below, produce a concise structured summary.

Format exactly:
Topic: <main topic>
Date: <today's date>
Concepts covered: <comma-separated list>
Datasets explored: <dataset IDs if any, else "none">
Knowledge state: <one sentence on what the user understands>
Open questions: <if any, else "none">

Conversation:
{conversation}"""


class AgentContextStore:
    """Append-only ChromaDB collection storing session summaries for cross-session memory."""

    def __init__(
        self,
        path: str | None = None,
        client=None,
        collection_name: str | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            import chromadb
            self._client = chromadb.PersistentClient(path=path)
        self._col = self._client.get_or_create_collection(
            name=collection_name or _COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_summary(self, session_id: str, text: str, metadata: dict) -> None:
        """Store a session summary. Append-only — always uses a unique doc ID."""
        doc_id = f"session:{session_id}:{uuid.uuid4().hex[:8]}"
        self._col.add(documents=[text], ids=[doc_id], metadatas=[metadata or None])

    def get_relevant(
        self,
        query: str,
        n: int = 3,
        threshold: float = _RELEVANCE_THRESHOLD,
    ) -> list[str]:
        """Return the n most semantically relevant session summaries for query."""
        if not query:
            return []
        count = self._col.count()
        if count == 0:
            return []
        results = self._col.query(query_texts=[query], n_results=min(n, count))
        if not results["documents"]:
            return []
        docs = results["documents"][0]
        distances = results["distances"][0]
        return [doc for doc, dist in zip(docs, distances) if dist <= threshold]


def format_context(summaries: list[str]) -> str:
    """Format a list of session summaries as a system prompt context block."""
    if not summaries:
        return ""
    lines = ["Prior sessions relevant to this topic:"]
    for summary in summaries:
        # indent each line of the summary for readability
        indented = "\n".join(f"  {line}" for line in summary.strip().splitlines())
        lines.append(f"---\n{indented}")
    return "\n".join(lines)


class SessionManager:
    """Manages session lifecycle: prior context retrieval and summary generation."""

    def __init__(self, context_store: AgentContextStore, client=None) -> None:
        self._store = context_store
        self._client = client  # Anthropic client

    def start_session(
        self,
        topic: str,
        threshold: float = _RELEVANCE_THRESHOLD,
    ) -> tuple[str, str]:
        """Return (session_id, prior_context_str). Context is empty on cold start."""
        session_id = str(uuid.uuid4())
        if not topic:
            return session_id, ""
        summaries = self._store.get_relevant(topic, n=3, threshold=threshold)
        return session_id, format_context(summaries)

    def end_session(self, session_id: str, conversation: list[dict]) -> None:
        """Generate a session summary via Claude and store it. Failures are swallowed."""
        if not conversation or self._client is None:
            return
        try:
            summary = self._generate_summary(conversation)
            self._store.add_summary(session_id, summary, {"session_id": session_id})
        except Exception:
            pass  # losing one summary is acceptable per spec

    def _generate_summary(self, conversation: list[dict]) -> str:
        from datetime import date
        convo_text = "\n".join(
            f"{m['role'].upper()}: {m['content'] if isinstance(m['content'], str) else '[tool content]'}"
            for m in conversation
        )
        prompt = _SUMMARY_PROMPT.format(conversation=convo_text)
        response = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
        return f"Topic: unknown\nDate: {date.today()}"
