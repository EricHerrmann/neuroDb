# Phase 3 Field Coverage Review
Date: 2026-04-12
DB: neurodb.db
Sources ingested: openneuro (50 datasets), allen_brain (39 datasets)

Note: Allen Brain ingest yielded 39 rows (not 50) because the connector filters
out `failed=True` records before persisting. 11 of the 50 fetched records were
marked failed by the API and skipped.

Also note: a bug was found and fixed during this audit run — `AllenBrainConnector.normalize_dataset`
used `raw.get("name", "")` which passes `None` through when the key exists but has a null value.
Fix applied: changed to `raw.get("name") or ""`.

## Field Coverage Table

```
source      total  has_doi  has_modality  has_n_subjects  has_description
allen_brain    39        0            39               0                0
openneuro      50       36            44              36               44
```

## Dataset Summary

```
source       modality  n_datasets  total_subjects
allen_brain  ISH               39               0
openneuro    None               6             168
openneuro    eeg               16             748
openneuro    meg                3             131
openneuro    mri               22             537
openneuro    nirs               3              30
```

## Semantic Gaps Identified

- **n_subjects**: Allen Brain shows 0 as expected — the source uses mouse brain specimens, not
  human subjects. `n_subjects` is intentionally NULL for allen_brain records; the `v_all_datasets`
  view correctly emits NULL for this column on the Allen side.
- **modality**: Allen Brain stores "ISH" (in situ hybridization) for all SectionDataSet records,
  which is accurate and normalized. OpenNeuro modalities span eeg, meg, mri, nirs, and None
  (6 datasets with undetectable modality from BIDS metadata).
- **doi**: OpenNeuro has 36/50 records with DOI (72% coverage). Allen Brain has 0 DOIs — the
  Allen Brain Atlas API does not expose DOI fields at the SectionDataSet level.
- **description**: OpenNeuro has 44/50 records with non-empty description (88% coverage).
  Allen Brain has 0 descriptions — the `name` field is frequently null in the API response,
  and the `description` field is not populated for SectionDataSet records.

## DOI Overlap

```
(no DOI overlap found between sources)
```

## Approach B Decision

- **DOI exact-match populating cross_refs**: NO
  Reason: Allen Brain Atlas SectionDataSet records carry no DOI field. With zero DOI coverage
  on the Allen side, no deterministic DOI-based cross-source join is possible at this time.
  The `cross_refs` table remains empty and Approach B is deferred.

- **Fuzzy subject matching**: DEFERRED
  Reason: Semantic gap — Allen Brain uses mouse brain specimens (no human subject metadata),
  OpenNeuro uses human subjects. Subject-level entity resolution across these two sources is
  not meaningful and should not be attempted.

- **Next review trigger**: When DANDI or NeuroVault is added as a 3rd source. Both sources
  expose DOIs for datasets, which could create a viable DOI overlap with OpenNeuro and
  re-open Approach B for that source pair.
