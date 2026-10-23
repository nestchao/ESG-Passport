# Reviewed SEDG preparation workflow

Offline application core for four stages. No API calls, automatic provider fallback,
or CMM website submission. A frontend/backend must connect real upload/OCR adapters
and enforce authentication, roles, storage/privacy and authenticated audit events.
The supplied walkthrough uses fictional documents and **simulated** human actions.

## Layout and stage boundaries

| Stage | Modules | Checked behaviour |
|---|---|---|
| 1. Ingest/review | `evidence.py` | Normalised OCR/manual observations, file hashes, source location, separate evidence strength and review priority; accepted manual records remain self-declared. |
| 2. Requirement form | `mapping.py`, `forms.py`, `catalogue/` | Conservative EN/BM rules, editable requirements, exact-offset keyword cues, code/unit validation and review snapshot. |
| 3. Match/review | `coverage.py`, `matching.py` | Metric/boundary/period match, unit checks, duplicate/overlap handling, water applicability, evidence display and accepted decision snapshot. |
| 4. Prepare/approve/export | `outcome.py` | Quantity conversions, guarded location-based Scope 2 calculation, preserved gaps, explicit final acknowledgement and JSON preparation export. |

Core mapping supports five Basic codes: E1.1, E1.2, E2.1, E3.1 and E4.1. It does
not cover all 38 disclosures. Social/Governance or unsupported Environmental
requirements must go to manual handling, not a guessed code. The supplemental
staff register contains such examples to expose this limitation.

Evidence weakness and review urgency are different: self-declared entries have
low strength, ordinarily P2 review urgency; contradictions and missing coverage
may be P1. A logo does not authenticate a source. Unknown quantities remain null,
not zero. A staff-reported zero is an explicit, uncorroborated assertion.

Call `question_form`, allow edits, then `review_form`. Matching requires its accepted
snapshot and individually reviewed observations. `review_matches` records a match
decision. `prepare_outcome` preserves partial/missing states; `approve_outcome`
requires explicit acknowledgement of every unresolved requirement. `export_preparation`
rejects stale approval or changed audit entries. Changed fields must be re-reviewed.
These checks are application logic, not cryptographic proof of a human identity.

## Calculation limits

Scope 2: only purchased grid electricity under an explicitly reviewed location-based
factor policy. Require a single inventory year, full activity-period coverage,
reviewed boundary, evidence grid region, explicit factor-site scope, factor value/unit,
year/source and selection reason. Different or unknown evidence grids block calculation.
No default factor. Formula: `kWh * kgCO2e_per_kWh / 1000 = tCO2e`.
Uncorroborated activity still produces an unverified candidate, never assurance.
Scope 1 and litres-to-energy calculations currently remain `calculation_required`;
the app must supply a separately validated fuel/refrigerant method. Do not present
this module as a complete GHG inventory or an official CMM calculator integration.

## Run offline checks/demo

Python 3.12+, dependency pin in `requirements.txt`; install with uv targeting an
explicit project venv. The repository's private environment is not distributed.
From repository root, set PYTHONPATH to src (as for the synthetic generator), then use your approved venv interpreter:

```
<venv-python> -m unittest discover -s tests -v
<venv-python> -m ai.workflow.demo
```

The demo reads `fixtures/staff_records/`, uses no external data and
prints five preparation exports plus three manual-only assertions. All approvals
are explicitly simulated. It deliberately leaves partial-year and source gaps.
It is an integration fixture, not an OCR accuracy result or independent benchmark.

The saved-OCR ingestion contract accepts adapter-supplied quantities, metric IDs,
units, period, organisation/site, and page/source text. Live Gemini/RapidOCR adapters,
PDF parsing and a review UI are not included in this offline core. Keyword cues
are simple inspectable matches, not a full clause parser or causal explanation.

## Security and audit boundary

Only trusted server code may set source corroboration and reviewer/declaration
metadata. Hashes detect stale snapshots and accidental changes; an attacker with
write access can recompute them. Persist events in access-controlled, append-only
storage in production. Do not accept public client review booleans or permit a
reviewer to silently overwrite evidence provenance. Preserve original uploads and
changes according to the approved retention/privacy policy. Public fixtures only
contain invented team-created data.

## Sources

Catalogue labels are project paraphrases, not a redistributed official publication:
[CMM SEDG V2, July 2025](https://sedg.capitalmarketsmalaysia.com/wp-content/uploads/2025/07/SEDG-v2.pdf),
printed pp7–8 and 11–13. Factor and boundary design references:
[CMM calculator methodology](https://www.capitalmarketsmalaysia.com/sedg-ghg-calculator/methodology.html),
[ST 2022–2024 provisional GEF](https://myenergystats.st.gov.my/documents/d/guest/grid-emission-factor-gef-in-malaysia-2022-2024-provisional-).
An older-vintage factor in a fictional test is an explicit test input, not an
endorsement of that factor for a later reporting year.
