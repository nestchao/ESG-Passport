# AI module

Application code for document extraction and SEDG question mapping belongs here.
The offline workflow core is available; live OCR adapters, authenticated storage
and the review UI still require application integration.

- [synthetic_generator](synthetic_generator/README.md): offline four-category document generator, capture effects, optional natural print wear and validation.
- [synthetic_dataset](synthetic_dataset/README.md): 360 fictional images with JSON field/evidence labels, split metadata and provenance.
- [staff records](workflow/fixtures/staff_records/README.md): supplemental fictional manual register; low-strength self-declared evidence, separate from OCR benchmark images.
- [workflow](workflow/README.md): four-stage ingestion, reviewed SEDG forms, matching, controlled preparation and approval/export core.

Automated generator checks are in `tests/test_synthetic_generator.py`. The generator has its own minimal dependency files and makes no API calls.

Private datasets, research, evaluation tooling and personal development records
are stored in .local/ and excluded from version control. Real source records and
credentials must not be included in application code or competition fixtures.
