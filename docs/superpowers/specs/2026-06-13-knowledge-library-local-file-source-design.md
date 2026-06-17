# Knowledge Library — Local-File Source (design)

**Status:** Design approved 2026-06-13 · **Author:** Eric Herrmann
**Builds on:** `docs/superpowers/specs/2026-06-12-citation-grade-phase2b-pdf-html-design.md`

## 1. Goal

Let the user ingest a file they downloaded themselves — typically a paywalled / account-gated PDF
their institution grants them — into the Knowledge Library. The user drops the file into a project
**library directory**, picks it in the acquire UI, and the existing parse → quality-gate → chunk
pipeline ingests it. The file persists in the library dir so it remains the source of record.

### Context

Phase 2b added a "Supply link / upload PDF" control, but it is **URL-only**: it posts a
`source_url` the backend downloads via httpx (`_phase2b_parse`). There is no file upload and no
place that retains an original file. Paywalled PDFs cannot be fetched server-side, so the only way
in is a file the user already has. This feature adds a local-file source feeding the same pipeline.

## 2. Decisions (settled during design)

| Decision | Choice |
|---|---|
| Input mechanism | **Drop-folder + pick-from-library** (no browser multipart upload) |
| File types | `.pdf` (PyMuPDF), `.txt`/`.md` (user-supplied-text path), `.html`/`.htm` (trafilatura) |
| Integration | **Extend the existing acquire path** with a `source_path`; reuse all parsers + the gate |
| Retention | File **persists in the library dir** (the dir *is* the library); read in place |
| Re-acquire | Re-opens the picker (re-supply `source_path`); **no new DB migration** |

## 3. Scope / Non-goals

**In scope:** a project library directory; a list endpoint; a `source_path` acquire field with
extension-based routing into existing pipelines; path-traversal safety; a UI file picker; tests.

**Non-goals:** browser multipart upload (the drop-folder replaces it); office formats (`.docx`,
etc. — would need a new parser); recursive/subfolder scanning (top-level files only); a watch-folder
auto-ingest; persisting a re-acquire path on the paper row (deferred — re-acquire re-picks). The
Docling high-fidelity PDF adapter remains deferred per the 2b spec.

## 4. Library store & path-safety (`src/neurodb/library_store.py`)

A small, focused module — the only genuinely new security-sensitive unit.

- `library_root() -> Path` — `os.environ.get("NEURODB_LIBRARY_DIR")` else `knowledge_library_files/`
  at the project root. Created on demand (`mkdir(parents=True, exist_ok=True)`).
- `SUPPORTED_EXTS = {".pdf", ".txt", ".md", ".html", ".htm"}`.
- `list_library_files() -> list[dict]` — top-level regular files whose suffix is in
  `SUPPORTED_EXTS`; each `{"name", "size", "modified"}`. Missing dir → `[]`.
- `resolve_library_path(name: str) -> Path | None` — returns the resolved path **only if**:
  `(root / name).resolve()` is within `root.resolve()` (rejects `..`, absolute paths, and symlinks
  that escape), the target is an existing regular file, and its suffix is supported. Otherwise
  `None`. This is the path-traversal guard; it is unit-tested adversarially.

`.gitignore`: add `knowledge_library_files/`.

## 5. Request, routing, list endpoint (`src/neurodb/api/routes/knowledge_library.py`)

- `AcquireFullTextRequest` gains `source_path: str | None = None` (a library-relative filename).
- `SuppliedInput` (in `full_text_client.py`) gains `path: str | None = None` (a resolved local file
  path) so the 2b parser can read a file instead of downloading.
- `GET /api/knowledge-library/library-files` → `list_library_files()` (for the UI dropdown).
- In `acquire_full_text`, when `body.source_path` is set:
  - `resolved = resolve_library_path(body.source_path)`; if `None` → **400** (traversal / unsupported)
    or **404** (missing) — distinguish by re-checking existence for the message.
  - Route by extension:
    - `.txt` / `.md` → `SuppliedInput(text=resolved.read_text(), format="md"|"txt")` → existing
      **2a user-supplied-text** path (synchronous → `verified`).
    - `.pdf` / `.html` / `.htm` → `SuppliedInput(path=str(resolved))` → existing **2b async** path.
  - When `source_path` is absent, behavior is unchanged (`url`/`source_url`/`text`).
- `classify_for_phase2b` extended: `supplied.path` → `"phase2b"` (alongside `supplied.url`);
  `supplied.text` still → `"structured"`.

## 6. Local-file parse, provenance, persistence

- `_phase2b_parse(paper, supplied)` extended: if `supplied.path` is set, read the local file
  (bytes → `parse_pdf`; text → `extract_html`, chosen by suffix) instead of the httpx download;
  set `artifact.fetched_url` to the library-relative filename for provenance. URL flow unchanged.
- **Persistence:** the file stays in the library dir (the user manages it); later quoting works via
  the already-persisted Chroma chunks. The library dir is the source of record / audit artifact.
- **Provenance:** parser `text_source` (`pdf_pymupdf` / `html_extracted` / `user_supplied`) + page
  anchor, same as 2b; the needs-review staging preview shows the library filename (`fetched_url`).
- **Re-acquire:** a local-file paper is re-acquired by re-picking the file in the UI (no persisted
  re-acquire path; deliberately no migration).

## 7. UI (`frontend/src/pages/KnowledgeLibraryPanel.tsx` + `frontend/src/api/`)

- `SupplyLinkInput` gains a **library-file picker**: on open it calls `listLibraryFiles()` and shows
  a dropdown of filenames (with size) plus a **refresh** control (so a just-dropped file appears
  without a full reload). The user supplies a source two ways: paste a URL, or pick a downloaded
  file. A selected file posts `{source_path}`; otherwise a URL posts `{source_url}` (existing).
- Shown in the same status states as today (`metadata`/`abstract` → acquire; `unavailable`/`failed`
  → recovery; `verified` → Re-acquire).
- Empty dir → hint: "No files in library — drop a file in `knowledge_library_files/`."
- API client: add `listLibraryFiles()`; extend the acquire call to accept `source_path`.

## 8. Error handling

- Path escape / traversal / absolute path → **400**.
- Unsupported extension → **400**.
- Missing / unreadable file → **404**.
- Garbled / scanned PDF → the existing confidence gate (low → `unavailable`), same as 2b.
- Absent library dir → list returns `[]` (no crash); acquire of a missing file → 404.

## 9. Testing

- **Backend unit (`library_store`)**: valid resolve; traversal (`../…`) and absolute path rejected;
  missing → `None`; unsupported ext rejected; `list_library_files` filters by extension and ignores
  subdirectories; absent dir → `[]`.
- **API**: `GET /library-files` lists dropped files; acquire with a `.txt` `source_path` → `verified`
  (synchronous); acquire with the `sample.pdf` fixture copied into a temp library dir (point
  `NEURODB_LIBRARY_DIR` at it) → background job runs real `parse_pdf` → `verified`; traversal
  `source_path` → 400; missing → 404.
- **`_phase2b_parse` local-file branch**: reads fixture PDF bytes → `ParsedArtifact(pdf_pymupdf)`;
  reads an `.html` fixture → `html_extracted`.
- **Frontend (Vitest)**: picker lists files from a mocked `listLibraryFiles`; selecting + acquire
  posts `{source_path}`; empty-list hint renders.
- **Manual** (addendum to the 2b plan or a short new section): drop a real paywalled PDF into
  `knowledge_library_files/`, pick it, confirm `pending → verified` and a grounded quote; confirm a
  traversal filename is refused. Prerequisites run `uv run pytest tests/ -q` first per repo policy.

## 10. Risks & mitigations

- **Path traversal / arbitrary file read** → `resolve_library_path` constrains every read to the
  library root, suffix-allowlisted; adversarial unit tests.
- **Stale references** (user deletes a file after ingest) → quoting still works (chunks persisted);
  re-acquire simply re-lists current files.
- **Large library dir** → top-level only, suffix-filtered listing; fine for a single-user tool.

## 11. Open decisions deferred to implementation

- Whether the file picker is a `<select>` vs a small searchable list (UI detail).
- Whether to also surface the library filename on the verified paper row in the UI (cosmetic).
- One-click re-acquire (would need a persisted `source_path` column → a future migration).
