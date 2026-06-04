
## 2. The Research Question Lifecycle

A research question is not a hypothesis. It starts as a hunch, an analogy, a provocation. It needs to be:

1. **Captured** — recorded before it evaporates, attached to a date and a context
2. **Categorized** — tagged to one or more topics, domains, or conceptual clusters
3. **Connected** — linked to papers, datasets, prior notes, or other questions that bear on it
4. **Explored** — discussed with an agent that can surface relevant evidence, propose framings, push back with counterexamples
5. **Matured** — either promoted to a testable hypothesis, archived as answered, or flagged as out-of-scope for the current evidence base
6. **Remembered** — retrievable across sessions so it can be revisited as new evidence accumulates

NeuroDb supports steps 3–6 well. It has significant gaps at steps 1–2.

## user Goal.  Focus effort on achieving this goal
I want to be able to consider a question, ask for existing research that are adjacent or similar to the topic, find papers, review them, then load them into the db and associate them with the appropriate topics, when pulling papers, that are related to the question they need to conditionally associated with topics, as the questions should be broken into logical topics.  This also goes for finding related research studies that have data associated with the research, so as the question matures, the data can be used to strengthen or conversly contradict the thesis of the question.  So this is basically 1-3. 

I need to be able to come into neurodb and ask the agent to then find questions, associated with a topic.  That should then allow me to find the links associated with that topic or question to go through steps 4-6.

I think this naturally fits with the Socratic Agent Mode, my style of exploring questions.  When the agent is exploring the question with the user, it should be in a find relevant/related information (3), explore the pros/cons of the question (4), etc.

Both existing agents (Tutor and Research) are task-oriented. Neither is designed to:
- hold a speculative question open deliberately
- probe it from multiple angles (analogy, counterexample, constraint)
- surface related questions rather than pushing toward a hypothesis

## I agree with this summary of what is needed:
### What it cannot do yet

- Store the original question with a timestamp and "this is where it started" provenance
- Tag it to topics without going through a hypothesis
- Explore it in a mode designed for open-ended Socratic dialogue rather than hypothesis formulation
- Surface it automatically in a future unrelated session on, say, "hippocampal indexing" because they share conceptual territory

## This is good and relevant framing
Question: In what ways are cue-driven retrieval, semantic stores, and pattern-matching behavior in frontier LLM systems useful or misleading analogies for human memory and learning?

Topic candidates:
- memory and retrieval
- semantic representations
- learning systems
- computational neuroscience analogies
- LLM architecture analogies

Concept candidates:
- cue-dependent retrieval
- semantic memory
- associative memory
- vector embeddings
- pattern completion
- working memory
- consolidation
- analogy limits
```

The important thing is to capture the question, the vocabulary around it, and the uncertainty boundaries. The system should not need to decide whether the analogy is correct on day one.

### I'm not sure I understand this, it needs to be explored

The four-axis categorization taxonomy (type, maturity, evidence posture, learning state) is more expressive than Claude's single status field and would make routing decisions between Tutor and Research agents automatable. It is, however, a larger schema change — it belongs in a second phase after the basic question workspace is functional.

This framing is correct for me;
The research question lifecycle (capture → categorize → connect → explore → mature → remember) is a cleaner mental model for evaluating completeness than Codex's feature list. It makes it easy to identify which lifecycle stages are served and which are not. The proposed inquiry agent mode is the right long-term destination even if it should wait until the UI is wired.