# Citation-Grade Data Access — Design Discussion (captured for follow-up)

**Captured:** 2026-06-07
**Purpose:** Verbatim capture of the conversation thread on whether the agents need access to actual paper data (full text / real content) to support citation-grade tutoring and research. Saved so the thread can be resumed after a system reboot.

**Thread:** (1) verification of what the Knowledge Library actually stores → (2) user's premise + pros/cons question → (3) the tiered-data answer ending in a Bottom line.

---

## 1. Claude — verification: does approving a paper make its contents available to the agents?

Verified end-to-end. Short answer: **no — approving a paper does not make its contents available to the agents.** What the agent retrieves is an LLM-written summary generated from the *title and metadata only*, not the paper's text. Here's the actual chain, with evidence:

| Step | What happens | Where |
|---|---|---|
| 1. Queue | The tutor's `queue_source` accepts only `title`, `source_type`, `topic_context`, `doi`, `url`, `topics`. **No abstract field, no full text.** Even though `search_literature` returns abstracts, there's nowhere to put them. | `tutor_agent.py` queue_source schema |
| 2. Store | The `Paper` row saves that metadata. The schema *has* `abstract`/`year`/`authors` columns, but the tutor's queue path leaves them **null**. | `tutor_agent.py:_execute_queue_source` |
| 3. Approve | `_generate_summary` asks the model to "create a concise summary" from **only** `title + source_type + DOI + URL + topic_context`. It never reads an abstract or any paper text. | `knowledge_library.py:472–505` |
| 4. Embed | That summary string is what gets embedded in ChromaDB. | `knowledge_store.add_summary` |
| 5. Retrieve | `search_knowledge_library` returns that summary as the document. | `knowledge_store.search` |

So the tutor's RAG is **retrieval over the model's own prior knowledge, keyed off the paper's title** — exactly the ungrounded situation the project was meant to avoid. The store's own docstring says it plainly: *"Semantic index of approved Neuro-Tutor source summaries."* Full text / PDF is never fetched, chunked, or embedded anywhere in the codebase.

**Two fairness caveats:**
- The **metadata** (title, DOI, URL, topic) is real and correct — that part is grounded.
- The **research agent** path is slightly better: it *can* store an abstract (`research_agent.py:728`) and surfaces it in context (`research_agent.py:610–611`) — but only if an abstract was supplied to it, and it's still the abstract, not full text. The tutor approve→RAG path doesn't use it.

**This is a real gap against your stated goal** ("RAG on actual data"). To close it, in increasing order of effort:

1. **Capture the abstract you already fetch.** Add an `abstract` field to `queue_source`, persist it on the `Paper` row, and feed `row.abstract` into `_generate_summary`. Low effort — the abstract is already in the `search_literature` envelope (currently discarded). Makes the summary grounded in real text instead of the title.
2. **Pull full abstracts, not the 300-char truncation.** `literature_client._truncate` caps abstracts at 300 chars; raise/remove that for stored text.
3. **True full-text RAG.** Fetch open-access full text (PubMed Central / arXiv / Unpaywall) at approval, chunk it, and embed the chunks — so retrieval is over the paper's actual content. Highest effort; this is what "RAG on real data" actually requires.

Want me to scope option 1 (the high-leverage, low-effort fix) as a TDD change, or go straight for option 3 / a phased plan toward full-text ingestion?

---

## 2. User — premise + pros/cons question

I don't think I have a good understanding yet, as example only, I'm currently exploring the arc of AI memory storage and retrieval and its relationship with biologic memory, I'm reading queued literature, with the goal of understanding both biologic memory and llm/ai memory/pattern matching alogrithms. As I read and identify papers that are specific to this research, and some that are old and some that are current, I want to reference them like an academic paper. If the agent assistinting me, both in tutoring and research, doesn't have access to the actual paper, they are limited in their precise understanding to their general training, possible hallucination, and do not have precise data on information generated after their training. I think that can be addressed by creating permanent store of the papers, or other data, that the agents have access to within the project. So with that preamble, my first question is my premis correct? Agents need the actual data, and can use it in their assigned roles or is it unnecessary extra weight. Please provide pros/cons

---

## 3. Claude — the tiered-data answer

Your premise is **mostly correct — for the work you're actually doing.** But it needs one refinement that changes the cost/benefit a lot: "the actual data" isn't one thing, and "the agent has access" isn't one mechanism. Get those two distinctions right and the answer stops being "yes/no" and becomes "yes, tiered."

### Is the premise correct?

For your stated goals — academic-grade citation, grounding claims in what a paper *actually* says, distinguishing a 1982 paper from a 2026 one, and using post-training-cutoff work — **yes, the agents need real text, not summaries-of-titles.** What you verified last turn is essentially the worst case for your goal: on the tutor path the agents have neither full text *nor* the abstract, only an LLM summary generated from the title. For "cite it like an academic paper," that is structurally incapable of the job — the agent is reconstructing the paper from its title and its training prior, which is exactly the hallucination surface you want to remove.

So the failure modes you named map directly:

| Your concern | Does real data fix it? |
|---|---|
| Hallucinated claims/quotes | Yes — agent can quote verbatim with a source anchor instead of paraphrasing memory |
| No data on post-cutoff papers (2024–2026) | **Only** real data fixes this — training can't |
| Precise citation (specific claim, figure, method) | Yes — needs the actual passage, ideally page/section-anchored |
| Old vs. current papers blurring together | Yes — agent compares actual texts, not averaged priors |

### The refinement: "actual data" is a spectrum, not a switch

This is where "unnecessary extra weight" becomes a real risk if you over-build. There are tiers, and the right one depends on the task:

| Tier | Cost to capture | What it unlocks | When it's enough |
|---|---|---|---|
| **Metadata** (title, authors, year, venue, DOI) | Trivial (you already fetch it) | Correct *references* — the bibliography half of "cite like an academic" | Listing/organizing papers; building a reference list |
| **Abstract** | Cheap (in your `search_literature` envelope today, then discarded) | Grounded orientation, accurate "what is this paper about," basic claims | Surveying the field; deciding what to read |
| **Full text** (OA: PMC/arXiv/Unpaywall) | Real engineering (fetch, parse, chunk, embed, provenance) | Verbatim quotes, specific methods/figures, page-anchored citations | The papers *central to your thesis* |
| **Extracted claims/evidence with locations** | Highest (curation on top of full text) | The research epoch's claim→evidence model becomes real | When you're writing/defending arguments |

The expensive tier (full text) has the **highest marginal value exactly where training fails you**: recent papers and precise quotation. It has the **lowest marginal value** for canonical pre-cutoff papers (the model's prior on Hopfield 1982 is genuinely decent). So "full text for everything, always" is the over-engineering trap; "full text for the ~20 papers your arc actually rests on, metadata+abstract for the rest" is the sweet spot.

### The other distinction: *access* ≠ *stuffing it in context*

"Agents have access to the data within the project" can mean two very different things, with different economics:

- **Retrieval (RAG):** store papers, embed chunks, the agent searches and pulls only relevant passages on demand. Scales to a whole library; only the relevant paragraphs enter the prompt. This is what your project was set up for and what's missing.
- **Whole-document in context:** put a full paper in the prompt. Precise but token-expensive, context-window-limited, and doesn't scale past a handful — and you already hit `max_tokens`/truncation friction.

For your use case the answer is RAG with provenance: real text stored, retrieval returns verbatim passages *with stable source IDs*, agent cites with that provenance.

### Pros / cons of a permanent real-data store the agents can use

**Pros**
- **Grounding & verifiability** — claims trace to a stored passage, not model memory; you can check the citation.
- **Post-cutoff coverage** — the only way to use 2024–2026 papers at all.
- **Precision for citation** — exact claims/quotes/figures, ideally anchored to section/page.
- **Old-vs-current discrimination** — the thing your whole arc depends on.
- **Reproducibility/lineage** — matches the project's stated audit/provenance goals; makes the research epoch's claim/evidence model meaningful instead of decorative.
- **Cross-session consistency** — grounded memory persists on stable artifacts, not regenerated summaries.

**Cons / real costs**
- **Acquisition is uneven** — abstracts are broadly available; full text is often paywalled. Only open-access (PMC, arXiv, Unpaywall) is freely/legally storable. Expect a mixed library, not 100% full text.
- **Ingestion engineering** — fetch, parse (PDF/JATS XML is messy), clean, chunk, embed, dedup, provenance. This is the bulk of the work.
- **Compute/storage** — embedding full papers is non-trivial in your environment (your prior SPECTER2/CPU-only hang is exactly this friction). Storage itself is cheap.
- **Retrieval-quality risk** — bad chunking/embedding makes the agent retrieve the *wrong* passage and cite it confidently. Garbage retrieval can be worse than an honest "I don't have that paper."
- **Maintenance** — versions, retractions, updates, keeping provenance honest.
- **Diminishing returns** — for famous pre-cutoff papers, you spent real effort to slightly beat a prior that was already good.

**When it genuinely is "extra weight":** organizing/listing papers, building a reference list, or orienting on well-known foundational work — metadata (and sometimes abstract) is sufficient, and full text adds cost without changing the answer.

### Bottom line

Your instinct is right: for citation-grade tutoring and research on a fast-moving topic that crosses the training cutoff, the agents need real paper data, and both roles can use it (tutor → accurate teaching with verifiable citations; research → grounded claims/evidence/hypotheses). The correction to your premise is *not* "agents need all the data" but **"agents need the right tier of data per task, retrieved with provenance — metadata for all, abstracts cheaply for all, full text for the papers your argument depends on."** That captures ~90% of the value while sidestepping the over-engineering and the paywall wall.

If that framing lands, the natural next step is to design it properly — brainstorm the tiered ingestion + retrieval + citation-provenance model before any code, since there are real choices (OA-only vs. user-supplied PDFs, chunking strategy, how citations surface in the UI).

---

## Suggested resume point (after reboot)

Next step on the table: decide whether to (a) brainstorm the full tiered ingestion + retrieval + citation-provenance design, or (b) start with the low-effort win — capture the abstract already fetched by `search_literature` (add `abstract` to `queue_source`, persist on `Paper`, feed into `_generate_summary`) as a TDD change.
