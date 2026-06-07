# Study Plan — The AI ↔ Biological Memory Arc (1980s → 2026)

**Created:** 2026-06-06
**Owner:** Eric Herrmann
**Status:** Draft — Modules 3–4 well-evidenced from retrieved sources; Modules 1–2 need verification (see Limitations).

## Thesis under investigation

AI engineering's relationship to biological memory is a four-beat arc:

- **Phase I (~1982–1992) — Reproduce.** AI deliberately tried to reproduce biological memory store/retrieval (content-addressable/associative memory, distributed representations).
- **Phase II (~1993–2010) — Abandon.** The field turned to statistical/mathematical engineering (SVMs, kernels, graphical models) not motivated by biology.
- **Phase III (~2010–2017) — Converge (unintentionally).** Engineering did *not* target biology, but converged on analogous memory solutions (distributed semantic geometry in embeddings; attention as content-based routing).
- **Phase IV (~2016–2026) — Re-import (intentionally).** Neuroscience is deliberately re-imported — complementary learning systems, hippocampus-inspired LLM memory, sleep/consolidation against catastrophic forgetting.

The analogy is **functional, not precise**: similar computational solutions to shared information problems (compact storage, retrieval from partial cues, generalization, interference control, update without overwrite), not a claim that AI mechanisms equal neural ones.

## How to use this plan given current limitations

- The in-app `search_literature` tool is flaky/being fixed; do **not** depend on live search to execute this plan. Sources below marked **[✓ retrieved]** were actually returned by the app's search and are in `literature_searches` (DOIs on file). Sources marked **[⚠ verify]** are canonical primary works from model knowledge that the search did *not* return — confirm each before citing.
- Work modules in order. Each module lists: objective, the claim it tests, key readings, and the evidence that would confirm or disconfirm that beat of the arc.

---

## Module 0 — Frame and definitions

**Objective:** Make the thesis falsifiable before reading.

- Define "biological memory store/retrieve" operationally across the systems the arc touches: semantic (neocortical, distributed), episodic (hippocampal binding), working (PFC maintenance/gating), associative/pattern completion (CA3), consolidation (hippocampus→neocortex).
- For each later module, write the specific computational property at stake (e.g., "content-addressable recall from partial cue") so a paper either demonstrates it or doesn't.

**Output:** a one-page operational rubric you grade every later reading against.

---

## Module 1 — Phase I: Intentional biomimicry (~1982–1992)

**Claim tested:** Early AI explicitly aimed to reproduce biological memory.

**Key readings:**
- Hopfield (1982), associative/content-addressable attractor networks — **[⚠ verify]** (PNAS).
- Rumelhart & McClelland, *Parallel Distributed Processing* vols. (1986) — distributed representations, graceful degradation — **[⚠ verify]**.
- "Connectionism coming of age: legacy and future challenges" (2014) — **[✓ retrieved]** DOI 10.3389/fpsyg.2014.00187 — retrospective on the connectionist program; use as the bridge from the 1980s intent to later eras.

**Confirms the beat if:** primary sources state biological motivation and target associative/distributed memory. **Disconfirms if:** the biological framing is post-hoc or the math was the actual goal.

---

## Module 2 — Phase II: The turn away (~1993–2010)

**Claim tested:** The field abandoned biological-memory goals for non-biological statistical engineering.

**Key readings:**
- SVM/kernel-methods and probabilistic graphical-models literature (canonical texts) — **[⚠ verify]**.
- The backpropagation biological-plausibility debate (why backprop is biologically implausible; what the brain might do instead) — **[⚠ verify]**.
- "An anatomical substrate of credit assignment in reinforcement learning" (2025) — **[✓ retrieved]** PMID 41279705 — modern framing of the credit-assignment gap that motivated the turn.

**Confirms if:** dominant methods of the era are explicitly non-biological and the neuroscience↔AI dialogue thins. **Disconfirms if:** biological-memory work continued materially (e.g., sustained hippocampal-model AI line).

> This is the **weakest-evidenced module** — our retrieved corpus barely covers it. Treat conclusions as provisional pending the Module 1–2 verification searches (see companion query list).

---

## Module 3 — Phase III: Accidental convergence (~2010–2017)

**Claim tested:** Engineering converged on biological-memory-like solutions *without* intending to.

**Key readings:**
- Mikolov et al. (2013), word2vec — distributed semantic geometry ("king − man + woman ≈ queen") as an analog of neocortical semantic memory — **[⚠ verify]**.
- LSTM/seq2seq gating as a working-memory analog — **[⚠ verify]**.
- Vaswani et al. (2017), "Attention Is All You Need" — attention as content-based routing, compared (loosely) to hippocampal indexing / attentional gating — **[⚠ verify]**.

**Confirms if:** the design objective was prediction/optimization, yet the learned structure maps onto a defined biological-memory property (Module 0 rubric). **Disconfirms if:** the resemblance is superficial or the biological mapping requires heavy reinterpretation.

---

## Module 4 — Phase IV: Deliberate re-import (~2016–2026)

**Claim tested:** Neuroscience is now intentionally re-imported into AI memory design. **This module is strongly supported by retrieved sources.**

**Key readings — all [✓ retrieved], DOIs on file:**
- Kumaran, Hassabis & McClelland (2016), "What Learning Systems Do Intelligent Agents Need? Complementary Learning Systems Theory Updated," *TiCS* — DOI 10.1016/j.tics.2016.05.004 (735 citations). The anchor for the re-import thesis.
- Hassabis et al. (2017), "Neuroscience-Inspired Artificial Intelligence," *Neuron* — DOI 10.1016/j.neuron.2017.06.011. Landmark manifesto for the deliberate-convergence program.
- HiMeS (2026), "Hippocampus-inspired Memory System for Personalized AI Assistants" — DOI 10.48550/arXiv.2601.06152.
- SynapNet (2024), "A Complementary Learning System Inspired Algorithm…" — DOI 10.1109/TNNLS.2024.3446171.
- "Sleep prevents catastrophic forgetting in spiking neural networks…" (2022) — DOI 10.1371/journal.pcbi.1010628.
- "Bayesian continual learning and forgetting in neural networks" (2025) — DOI 10.1038/s41467-025-64601-w.
- "Neuroplasticity Meets AI: A Hippocampus-Inspired Approach to the Stability-Plasticity Dilemma" (2024) — DOI 10.3390/brainsci14111111.

**Confirms if:** these works cite neuroscience as explicit design source (CLS, hippocampal indexing, sleep consolidation). **Disconfirms if:** the biological language is decorative and the mechanisms are conventional ML.

---

## Module 5 — The gap and the publishable review

**Claim tested:** No single paper traces the *longitudinal* 1980s→2026 arc; the field publishes point-in-time comparisons, not the intellectual history.

**Steps:**
1. Run the Module 1–2 + gap-verification searches (companion list) once the server is restarted on the fixed `search_literature`.
2. For every candidate "review/history" hit, classify scope: does it cover all four phases longitudinally, or a single snapshot (e.g., "LLMs vs human memory")?
3. If the longitudinal gap holds, outline the review: the four-beat structure above, the functional-vs-precise analogy framing, and the convergent-evolution argument (independent systems converging under shared information constraints).

**Confirms the gap if:** existing reviews are snapshot comparisons; **disconfirms if:** a comprehensive longitudinal review already exists (then pivot to a narrower contribution).

---

## Limitations (state these in any writeup)

- **Evidence asymmetry:** retrieved sources are dense for Phases III–IV (2014–2026) and thin for Phases I–II. The historical "reproduce → abandon" claim is currently under-supported and is the riskiest part of the thesis.
- **Gap claim unverified:** the "no single longitudinal review" premise has not been confirmed against real search results; it must be tested in Module 5 before grounding a publication.
- **Analogy discipline:** keep claims functional ("solves an analogous problem"), not mechanistic ("is the same mechanism"). Note where the analogy breaks (e.g., transformer attention is symmetric, fixed-window, time-agnostic vs. hippocampal indexing).

## Retrieved-source appendix (selection, [✓] = in `literature_searches`)

| Year | Title | DOI / ID |
|---|---|---|
| 2016 | What Learning Systems Do Intelligent Agents Need? (CLS updated) | 10.1016/j.tics.2016.05.004 |
| 2017 | Neuroscience-Inspired Artificial Intelligence | 10.1016/j.neuron.2017.06.011 |
| 2014 | Connectionism coming of age: legacy and future challenges | 10.3389/fpsyg.2014.00187 |
| 2024 | SynapNet: Complementary Learning System Inspired Algorithm | 10.1109/TNNLS.2024.3446171 |
| 2024 | Neuroplasticity Meets AI: Hippocampus-Inspired Stability-Plasticity | 10.3390/brainsci14111111 |
| 2026 | HiMeS: Hippocampus-inspired Memory System for AI Assistants | 10.48550/arXiv.2601.06152 |
| 2022 | Sleep prevents catastrophic forgetting in spiking neural networks | 10.1371/journal.pcbi.1010628 |
| 2025 | Bayesian continual learning and forgetting in neural networks | 10.1038/s41467-025-64601-w |
| 2025 | An anatomical substrate of credit assignment in RL | PMID 41279705 |

---

## Companion: Module 1–2 + gap-verification search queries

Run these through `search_literature` **after** the server is restarted on the fixed tool
(arXiv https + envelope + NCBI key). They target the under-evidenced historical modules and
test the longitudinal-gap premise. For each, record `result_count` and per-provider status; a
zero with `providers.*.status == "error"` means retry, not absence.

**Module 1 — intentional biomimicry (1980s):**
1. `Hopfield 1982 associative memory neural network content addressable`
2. `Rumelhart McClelland 1986 parallel distributed processing connectionism`
3. `content addressable memory neural network biological associative recall history`
4. `distributed representations neocortex semantic memory connectionism 1980s`

**Module 2 — the turn away (1990s–2000s):**
5. `backpropagation biological plausibility criticism brain credit assignment`
6. `support vector machines kernel methods rise statistical machine learning history`
7. `decline of neural networks AI winter 1990s symbolic statistical methods`
8. `graphical models probabilistic machine learning non-biological 2000s`

**Module 5 — gap test (does a longitudinal review already exist?):**
9. `history of artificial intelligence and biological memory review 1980s to present`
10. `connectionism to large language models intellectual history memory analogy review`
11. `longitudinal review neuroscience inspired AI convergence connectionism transformers LLM`
12. `survey biological memory analogies deep learning embeddings attention hippocampus history`

**Interpretation rule:** if queries 9–12 return only point-in-time comparisons (e.g., "LLMs vs
human memory") and no four-phase longitudinal history, the publication gap stands; if a
comprehensive longitudinal review surfaces, pivot to a narrower contribution.

