# OCR and structured extraction comparison

Review draft, 23 October 2026. This report documents one completed synthetic development screen and a proposed RapidOCR/Gemini ablation. The hybrid ablation has **not** been run on these eight pages. No result here establishes accuracy on real Malaysian records.

## Completed comparison

Gemini 3.5 Flash Lite and Grafilab Qwen3.5 397B A17B each received the same eight synthetic photo images: base document 002 in each of the eight electricity, water, fuel and waste layout families. There were eight fresh requests per model, one pass per image, no reused outputs, no retries and no model fallback. All samples are from the development split.

| Measure | Gemini 3.5 Flash Lite | Grafilab Qwen3.5 397B A17B |
|---|---:|---:|
| Completed images | 8/8 | 8/8 |
| Correct expected values | 43/43 | 43/43 |
| Exact field/value/unit records | 39/43 (90.70%) | 43/43 (100%) |
| Exact expected records including dates | 39/43 (90.70%) | 43/43 (100%) |
| Full-record precision, including extras | 39/44 (88.64%) | 43/44 (97.73%) |
| Full-record F1 | 89.66% | 98.85% |
| Expected activity records exact | 8/8 | 8/8 |
| Unsupported extra records | 1 | 1 |
| Custom mapping loss, lower is better | 6/43 = 0.1395 | 2/43 = 0.0465 |
| Mean per-image CER, lower is better | 11.34% | 8.63% |
| Mean per-image WER, lower is better | 10.91% | 9.01% |
| Mean per-image word-multiset F1 | 99.95% | 100% |
| Direct JSON objects | 8/8 | 0/8 |
| Valid schema after permitted fence removal | 8/8 | 8/8 |
| Median end-to-end request seconds | 3.66 | 50.56 |
| Cost for these requests | Project-declared free tier | API-reported MYR0.3721782 |

**Interpretation:** Gemini's four non-exact expected records contained correct electricity meter values with null units. The corresponding meter cells contain bare numbers, while the document provides electricity context; the frozen labels require kWh. This is a unit assignment/abstention difference, not four incorrectly read numbers. Qwen supplied the expected units. Neither model has perfect output precision: both incorrectly mapped `Amount paid RM 71.60` to `cash_paid` on a receipt with a noncash payment method. That extra record receives the predeclared extra-record penalty of 2.

The current integration preference remains Gemini because of the user's free-tier budget preference, direct JSON and the measured latency on this run. This is an operational choice, not a demonstrated real-world accuracy ranking. Missing units require contextual evidence or review, and a paid amount must not be classified as cash without payment-method evidence.

## Research supporting the design

The papers support the task decomposition and evaluation principles below. They do not validate these particular model versions, our synthetic realism, our eight-image sample size or our custom penalty weights. Sources were checked on 23 October 2026; no third-party dataset or paper assets are redistributed here.

| Source and inspected section | Evidence relevant to this comparison | Application and boundary |
|---|---|---|
| [SROIE, Huang et al., ICDAR 2019](https://arxiv.org/html/2103.10213), §§III-B–III-C; [publisher DOI](https://doi.org/10.1109/ICDAR.2019.00244) | Separates receipt transcription from key-information extraction. Recognition matches repeated word occurrences and reports precision/recall/F1; extraction requires both content and category to match. | Supports separate text and field scores. Our unit/date equivalence rules extend its task; our numbers are not SROIE benchmark results. |
| [FUNSD, Jaume, Ekenel and Thiran, 2019](https://arxiv.org/html/1905.13538), §III-C | Distinguishes word grouping, semantic labeling and relations between entities; linking is evaluated separately using precision/recall/F1. | Supports checking which value belongs to which field rather than scoring text alone. We do not implement the FUNSD graph-linking benchmark. |
| [Donut: OCR-free Document Understanding Transformer, Kim et al., ECCV 2022](https://arxiv.org/html/2111.15664), introduction and §§3.2–3.4 | Discusses downstream propagation of OCR errors and compares OCR-based/OCR-free document systems using field-level F1, structural accuracy and runtime. | Supports testing OCR assistance as an ablation and counting the whole pipeline's cost. It does not prove RapidOCR plus Gemini improves extraction. |
| [HELM, Liang et al., 2022/2023](https://arxiv.org/html/2211.09110), §1.1 and evaluation methodology | Uses common evaluation scenarios with multiple metrics to expose capability and efficiency trade-offs. | Supports paired inputs, recorded settings and reporting quality alongside latency/cost. Our provider transports still differ. |
| [OCRBench, Liu et al., 2023/2024](https://arxiv.org/abs/2305.07895v7), abstract and task scope | Evaluates multimodal models across text recognition and key-information extraction, among other tasks. | Supports assessing more than transcription alone; we do not reproduce OCRBench or inherit its scores. |
| [OCR-D: Quality Assurance](https://ocr-d.de/en/spec/ocrd_eval.html), text-evaluation and resource-utilization sections; **technical specification, not a research paper** | Defines edit-distance measures, order-independent word counts and processing-resource measures. | Supports explicit metric definitions. Our codepoint/whitespace implementation differs from its grapheme-based and normalized variants. |

## Frozen comparison protocol

1. Select the same development images for both models before seeing predictions. Preserve image and annotation SHA-256 hashes. Keep all capture variants of a base document in one split; shared layout families mean these splits are not unseen-layout tests.
2. Freeze the prompt, supported fields, label dates, parser and scoring policy before requests. Labels are intended generator content; human visibility review remains pending. Do not send answer labels to either provider.
3. Use temperature 0 and an 8192-token output limit. These settings do not make stochastic services deterministic or their tokenizers equivalent.
4. Gemini receives the image through native JSON mode; Qwen receives the same image/prompt through its chat-completion interface. Record this format-adaptation difference. Permit only removal of one complete surrounding Markdown JSON fence, apply the same parser policy to either model and record direct-JSON success separately.
5. Preserve returned fields and uncertainties. Do not repair their values, units or dates during parsing. Score each expected field once; duplicate or unsupported predictions count as extras.
6. Report completed-pair quality separately from service coverage. A failed request must not disappear from the accounting; do not infer a quality ranking from unequal successful subsets. Retain an all-scheduled diagnostic counting absent outputs as empty.
7. Record token usage, returned model identifier, request latency and per-request charge source. No automatic retries. Validate and seal outputs before interpreting results. The current record is a descriptive screen without significance tests or a validated confidence interval.

The date rules are application definitions: water previous/current readings use their printed individual dates; utility `amount_due` uses the issue date; consumption and electricity meter readings use the service period; `reading_type` has null dates; fuel/waste fields use the transaction date. These rules are not prescribed by the papers or asserted as SEDG requirements.

## Metric definitions and implementation choices

### Transcription

Let `R` be the reference and `H` the prediction, `d` Levenshtein distance, and `N` the reference length:

```text
CER = d(character_sequence(R), character_sequence(H)) / reference_characters
WER = d(word_sequence(R), word_sequence(H)) / reference_words
```

The implementation applies Unicode NFC, collapses whitespace, retains case/punctuation, uses Unicode codepoints for characters and whitespace splitting for words. Neither rate is clipped; insertion-heavy output can exceed 100%. Reported CER/WER are unweighted means of the eight page-level rates, not pooled character/word rates.

These are reference-length edit-error variants. OCR-D also documents different normalized denominators, grapheme units and tokenization; we do not claim exact compliance with its implementation. Table reading order can change CER/WER despite correct words, so use field scores and an order-independent diagnostic alongside them. [OCR-D definitions](https://ocr-d.de/en/spec/ocrd_eval.html)

For word counts `r(w)` and `h(w)`, define `M = sum_w min(r(w), h(w))`:

```text
word_precision = M / sum_w h(w)
word_recall    = M / sum_w r(w)
word_multiset_F1 = 2M / (sum_w r(w) + sum_w h(w))
```

Repeated words count repeatedly. With identical tokenization this also equals `1 - sum_w |r(w)-h(w)| / (|R_words|+|H_words|)`. SROIE's word-matching evaluation provides the direct F1 precedent; OCR-D describes the complementary bag-of-words error. Order-independent scores cannot detect a swapped label/value relationship. [SROIE §III-B](https://arxiv.org/html/2103.10213); [OCR-D bag of words](https://ocr-d.de/en/spec/ocrd_eval.html)

### Structured fields

The strict comparison record is `(field, normalized value, equivalent unit, period_start, period_end)`. Exact deterministic conversions include m3↔L, kg↔t and MWh↔kWh; kW is not interchangeable with kWh. Defined aliases normalize `RM` to `MYR` and `Sebenar` to `actual`. No estimated emissions, unknown factors or guessed dates are accepted. These are project-specific normalization rules.

Let `G` be expected records, `P` all returned records including duplicates/extras, and `T` strict exact matches:

```text
expected_record_exactness = T / G
precision = T / P
recall = T / G
F1 = 2 * precision * recall / (precision + recall)
```

`expected_record_exactness` is recall-like, not whole-output accuracy. It must appear with precision, F1 and extra counts: matching every expected record does not make a response perfect. `activity_record_exactness` restricts this calculation to expected fields marked as activity quantities. Content/category matching and field-level F1 have precedents in [SROIE](https://arxiv.org/html/2103.10213) and [Donut](https://arxiv.org/html/2111.15664); the additional unit/date tuple is our application extension.

### Custom mapping loss

This measure encodes the user's preference that incorrect associations incur more cost than omissions. **The numeric costs are project-defined and unvalidated; no cited paper establishes them as a standard.**

| Outcome | Cost |
|---|---:|
| Correct strict expected record | 0 |
| Missing, abstained or incomplete | 1 |
| Wrong value/unit/date, including an invented date for unscoped context | 2 |
| Evidence-supported wrong association with a unique other expected field | 3 |
| Each unsupported or duplicate extra prediction | 2 |

```text
mapping_loss = (sum of expected-record costs + 2 * number_of_extras) / G
```

Apply conditions in the frozen scorer's precedence: correct; null-value abstention; uniquely evidenced association error; missing required unit/date; otherwise wrong value/unit/date. Before the cost-3 association test, the prediction must match the other field's normalized value/unit and its evidence must overlap that field's evidence. Equal numbers alone are insufficient. A wrong association that does not meet this evidence rule can instead receive cost 2; extras always receive their separate cost 2. This conservative detector is not an exhaustive relationship audit. The loss can exceed 1 and is not a probability.

The primary costs were frozen before this run. A future sensitivity analysis should vary the cost-3 and extra penalties and retain unweighted precision/recall/F1, so a chosen cost matrix cannot conceal errors. [FUNSD](https://arxiv.org/html/1905.13538) supports evaluating relations separately; it does not validate this loss function or its exact evidence-matching heuristic.

### Operational measures

Direct-JSON rate, schema validity, failures and review flags are separate from semantic correctness. A valid schema cannot certify a correct payment type. Median request time includes image reading/encoding, transport, generation and parsing; it is not isolated model compute. The eight-observation nearest-rank p95 is simply the slowest call and should not be treated as a production tail-latency estimate.

API-reported MYR charges are recorded where returned; otherwise estimates use the user's console prices, MYR1.60/M input and MYR11.00/M output. Google's zero-charge description relies on the project free-tier declaration, not an account-level billing audit. Failed attempts may be chargeable. Different tokenizers and provider defaults prevent a controlled compute comparison. These operational details implement the multi-metric trade-off principle, not a published benchmark recipe. [HELM](https://arxiv.org/html/2211.09110)

## Proposed RapidOCR/Gemini comparison — not yet run

The next study should preserve a Gemini-only baseline and change one pipeline component at a time:

| Arm | Inputs and role | What it isolates |
|---|---|---|
| A: Gemini image-only | Original image; frozen field schema and prompt | Existing baseline |
| B: RapidOCR text recognition | Original image; retain text, boxes and engine scores | Local OCR transcription quality; no direct field-score comparison unless a field extractor is explicitly defined |
| C: RapidOCR-assisted Gemini | Same image plus RapidOCR text/boxes explicitly marked as fallible evidence; same semantic extraction instructions | Whether OCR assistance improves extraction or propagates OCR errors |
| D: Optional image preprocessing | Deterministic mild deskew/contrast variant with original retained; compare against the equivalent unprocessed arm | Effect of preprocessing, separately from OCR assistance |

An independently extracted Gemini pass plus local OCR disagreement checks is a separate fusion design from arm C. If tested, report it as another arm rather than silently combining its results. Freeze alignment, selection and disagreement rules; agreement is not proof of correctness. Engine confidence is not a calibrated correctness probability. Any second Gemini crop/reconciliation request counts in that arm's cost, latency and request budget. A budget-matched one-call C arm and a multi-call fusion arm answer different questions.

Use the same sample IDs and references for paired pipeline comparisons. For the first ablation, retain all eight current pages but call it development reuse, not a new held-out test; repeated exposure can guide tuning. A stronger follow-up requires independently reviewed labels, fresh bases/layouts and grouped splits. Record per-page changes and error categories, particularly omitted units, net/gross/tare confusion and noncash-to-cash associations. Later statistical uncertainty should resample independent base documents, not correlated capture variants; eight bases are too small for strong generalization claims.

The reason for this ablation is to measure possible gains **and** error propagation, as discussed by [Donut](https://arxiv.org/html/2111.15664). No improvement is assumed, no confidence threshold is justified yet and no new API run is authorized by this document.

## Evidence package and review status

[results.json](results.json) contains the eight synthetic input hashes, frozen prompt/schema, recorded run configuration, model predictions, references, metric summaries and error review. Image/annotation paths resolve from `src/ai/synthetic_dataset/`. It omits credentials, authorization headers, request IDs, raw provider envelopes, local absolute paths, real records and private development notes. The original provider envelopes remain in the ignored local audit record; summary export does not independently verify provider billing or response authenticity.

The public predictions allow inspection of reported transcription and field errors. This review package does not yet include a standalone public scoring CLI, so it is not presented as a turnkey benchmark. The completed experiment and the research justification were written at different times: this literature review is retrospective and is not a claim of preregistration against these papers. Hybrid arms are proposed only.

Proposed Git additions: this README and `results.json` only. Status: awaiting user review before staging, commit or push. The previously staged generator/dataset files are outside this review change.
