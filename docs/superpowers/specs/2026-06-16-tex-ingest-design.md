# TeX Ingest & Parsing — Design

- **Date:** 2026-06-16
- **Status:** Approved for planning
- **Phase context:** Extends Citation-Grade Phase 2b (full-text acquisition) and the Knowledge Library local-file source.
- **Related specs:** `2026-06-12-citation-grade-phase2b-pdf-html-design.md`, `2026-06-13-knowledge-library-local-file-source-design.md`

## 1. Problem & Motivation

Phase 2b acquires full text from PDF and HTML. PDF is a presentation format: reading
order, sections, math, tables, and references must be reverse-engineered from glyph
positions, which is inherently lossy. When a paper's TeX source is available (e.g., an
arXiv `e-print` tarball), it carries explicit structure — `\section`, `\cite`, math markup,
and a bibliography — that yields higher-fidelity full text than parsing the rendered PDF.

Today the project has **no TeX handling at any layer**: `.tex`/`.tar.gz` are not in
`SUPPORTED_EXTS`, the library picker is flat and file-only, parse routing forks only on
`.pdf` vs HTML, and no TeX parser exists. This work adds a TeX ingest path that mirrors the
existing PDF path.

## 2. Scope

### In scope
- Ingest a **user-extracted TeX project folder** dropped into `knowledge_library_files/`
  (the configured `NEURODB_LIBRARY_DIR`). The unit of ingest is a folder containing a
  main `.tex`.
- A new `tex_parser.py` producing a `ParsedArtifact`, consumed by the existing Phase 2b
  background job → chunks → DuckDB `PaperChunk` rows + ChromaDB, so TeX-sourced papers
  become searchable full text alongside PDF/HTML.
- Picker and routing changes so a TeX project folder is selectable and routes to the
  Phase 2b job.

### Non-goals
- **No tarball extraction in code.** The operator extracts the `.tar.gz` into the library
  folder. Rationale: keeps the connector aligned with the existing local-file source, which
  reads user-supplied files in place.
- **No fetching arXiv source by ID.** Local-folder only.
- **No new UI** beyond surfacing project folders in the existing picker.
- **No LaTeXML implementation.** The high-fidelity seam is defined but ships unimplemented
  (default `None`), identical to how `docling_convert` shipped in Phase 2b.

## 3. Approach Decision

LaTeX is Turing-complete (custom macros, package-specific syntax), so a regex parser is not
"robust." Robust extraction means either a pure-Python LaTeX walker or an external compiler.
The chosen design is a **hybrid**, mirroring the established `docling_convert` seam pattern:

- **Default path — `pylatexenc` (pure-Python):** pinned in `uv`, works on a fresh clone and
  in CI with no system binaries. Produces clean body text, section structure, and inline
  math preserved as raw LaTeX. This is the reproducible floor.
- **High-fidelity path — `latexml_convert` seam (deferred):** an injectable converter
  (default `None`) that, when LaTeXML is installed, yields structured math (MathML), tables,
  and resolved references. Optional and async-friendly; its absence degrades gracefully to
  the pylatexenc floor.

Rationale for not making LaTeXML a hard dependency: LaTeXML is a Perl application, not
pip-installable, cannot be pinned by `uv`, its XML output drifts across versions, and it
would require a system install in CI to test. The seam isolates that cost without making the
whole pipeline depend on an unpinnable binary. This is the same tradeoff the project already
resolved for Docling.

### Fidelity expectations

| Capability        | `tex_pylatexenc` (default, always on) | `tex_latexml` (seam, when installed) |
|-------------------|----------------------------------------|--------------------------------------|
| Body text + sections | Good                                 | Good                                 |
| Math              | raw LaTeX inline                       | MathML + LaTeX                       |
| Tables            | flattened to text (lossy)              | structured                           |
| References        | `.bbl` text + inline `\cite` keys      | resolved/structured                  |

## 4. Components

### 4.1 New module: `src/neurodb/tex_parser.py`

Mirrors `pdf_parser.py`, including the deferred seam.

```python
def parse_tex(
    project_dir: Path,
    *,
    latexml_convert: Callable[[Path], list[Section]] | None = None,
    text_source: str = "tex_latexml",
) -> ParsedArtifact:
    """Parse a TeX project folder into a ParsedArtifact.

    Uses latexml_convert if provided and it yields sections; otherwise (the default today)
    uses the pylatexenc path. Raises ValueError if no text is extractable.
    """
```

Default (pylatexenc) path internals, in order:

1. **Main-file detection.** Scan `*.tex` in `project_dir` (recursively) for a file containing
   both `\documentclass` and `\begin{document}`. If exactly one, use it. If several, use the
   first by sorted path and log the ambiguity. If none, raise `ValueError`.
2. **Include expansion.** Recursively inline `\input{…}` / `\include{…}` relative to
   `project_dir` (pylatexenc does not resolve includes). Missing include → skip + log; guard
   against cycles with a visited-set; cap recursion depth.
3. **Walk + sectionize.** Use `pylatexenc.latexwalker.LatexWalker` +
   `pylatexenc.latex2text.LatexNodes2Text` to strip markup and split on
   `\section`/`\subsection`/`\subsubsection` into `Section`s. Inline math (`$…$`, `\[…\]`) is
   **preserved as raw LaTeX** in the text stream rather than dropped.
4. **References.** If a `.bbl` exists in `project_dir`, append its rendered text as a
   `References` section. `\cite` keys remain inline as text. Structured/resolved references
   are a seam-only upgrade.

Returns a `ParsedArtifact(sections, parse_confidence, text_source)` with `text_source`
`"tex_pylatexenc"` (default) or `"tex_latexml"` (seam). `parse_confidence` is set via the
existing `parse_quality.score`.

### 4.2 `src/neurodb/library_store.py`

- Add `SUPPORTED_EXTS` awareness of TeX projects. Add:
  - `list_library_projects() -> list[dict]` — surface **subdirectories that contain at least
    one `.tex`** as selectable items (`{"name", "size"?, "modified"}`), with the same
    path-traversal guard used for files. Combined into the picker listing alongside files.
  - `resolve_library_project(name: str) -> Path | None` — return the resolved folder path iff
    `name` is a directory inside the library root containing a `.tex` (path-traversal guard).
- Existing file functions (`list_library_files`, `resolve_library_path`) are unchanged;
  PDF/HTML/txt/md continue to work exactly as today.

### 4.3 `src/neurodb/api/routes/knowledge_library.py`

- **`/library-files` listing** (~L99): include TeX project folders so the picker shows them.
- **Acquire routing** (~L252): new branch — if `source_path` resolves to a TeX project folder
  via `resolve_library_project`, build `SuppliedInput(path=<folder>)`. Reuses the existing
  `SuppliedInput.path` field (no new field).
- **`_phase2b_parse`** (~L382): new branch — if `supplied.path` is a directory, call
  `parse_tex(Path(supplied.path))`; else the existing `.pdf` / `.html` logic. Set
  `artifact.fetched_url = <folder name>` (mirrors the PDF path storing `p.name`).
- **Routing to the job:** `classify_for_phase2b` already returns `"phase2b"` whenever
  `supplied.path` is set (full_text_client.py:236), so a TeX folder routes to
  `_run_phase2b_job` with no change. Covered by a test.

### 4.4 Dependency

Add `pylatexenc` to `[project.dependencies]` in `pyproject.toml` and update `uv.lock`.

## 5. Data Flow

```
operator extracts arXiv .tar.gz into knowledge_library_files/<project>/
  → GET /library-files lists <project> as a TeX project
  → POST acquire {source_path: "<project>"}
  → resolve_library_project -> SuppliedInput(path=<abs folder>)
  → classify_for_phase2b -> "phase2b"
  → background _run_phase2b_job
  → _phase2b_parse: dir -> parse_tex(folder) -> ParsedArtifact
  → _commit_chunks: chunk_sections -> PaperChunk rows + ChromaDB (delete-then-insert)
  → paper full_text searchable, anchored by section label
```

## 6. Anchor Model

`Section`/`Chunk` carry `page: int | None`. TeX has no pages, so for TeX **`page=None` and
`label` carries section identity** (e.g., `"2 Methods"`). `chunk_sections` passes `label` and
`page` through untouched and `PaperChunk.page` is nullable, so **no schema migration is
required**. Citations from TeX-sourced chunks anchor by section label instead of page number.

## 7. Error Handling & Provenance

- Parse failure (no main file, no extractable text, unrecoverable includes) → `parse_tex`
  raises `ValueError`; `_phase2b_parse` logs via `logger.exception` and returns `None`, the
  same contract as the PDF/HTML path. The job records a failure rather than crashing.
- Provenance: `text_source` = `"tex_pylatexenc"` (or `"tex_latexml"` for the seam);
  `fetched_url` = the project folder name.

## 8. Testing

Per project rules, the manual test plan and its automated-test prerequisite are written
**before** implementation.

### Unit (`tests/unit/`)
- Main-file detection: single match, multiple matches (first + log), no match (raises).
- Include expansion: nested `\input`, missing include (skip + log), cycle guard.
- Sectionization: `\section`/`\subsection` boundaries, offset-correct `char_start`/`char_end`.
- Math preservation: inline and display math retained as raw LaTeX.
- References: `.bbl` appended as a `References` section; `\cite` keys remain inline.
- Failure: empty/no-text project raises `ValueError`.
- Seam: injected fake `latexml_convert` yields sections → `text_source="tex_latexml"`;
  exception in the seam falls back to pylatexenc.

### Integration (`tests/integration/`)
- Fixture TeX project: main `.tex` + one `\input` child + `.bbl`, run through `parse_tex` →
  `chunk_sections` → assert sections present, `page=None`, label anchors populated.
- **Idempotency:** re-acquiring the same project does not duplicate chunks (the existing
  delete-then-insert in `_commit_chunks` enforces this; the test asserts stable chunk counts
  and `chroma_id`s across two runs).
- Routing: `classify_for_phase2b` returns `"phase2b"` for `SuppliedInput(path=<folder>)`.

### CI
- Default pylatexenc path only; no LaTeXML installed. The seam is exercised via an injected
  fake converter, never a real binary.

### Manual test plan
- New `docs/testsPlans/manualTestPlan_tex_ingest.md`: extract a real arXiv tarball into the
  library folder, select the project in the Knowledge Library, acquire, and verify the paper
  becomes searchable with section-anchored citations.
- Prerequisites section leads with the mandated `uv run pytest tests/ -q` step (pass
  criteria: no new failures beyond those tracked in `docs/testLog.md`).
- Long verification commands live in a helper under `tests/manual/`.

## 9. Project-State Sync

In the implementing commit(s):
- Add `docs/testsPlans/manualTestPlan_tex_ingest.md` to the `docs/projectStatus.md` reference
  table and active test-plan list when the plan is first created.
- Update the active-focus line and phase row/test count per the normal sync rules.
- Add this spec to the reference table.

## 10. Follow-ups (tracked, out of scope here)

- Implement the `latexml_convert` seam against an installed LaTeXML for structured
  math/tables/references.
- Optional: in-code tarball extraction if manual extraction proves friction-heavy.
