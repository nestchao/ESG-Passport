# Synthetic Malaysian document dataset

360 PNG images with 360 JSON annotations, generated from 120 fictional base records. Each of the four category folders contains 90 images and 90 paired labels. The JSON `intended_lines` also provides the transcript, so separate transcript files are unnecessary.

| Category | Layouts | Base records | Images |
|---|---|---:|---:|
| Electricity | Itemised statement, payment stub | 30 | 90 |
| Water | Sidebar bill, payment stub | 30 | 90 |
| Fuel | Pump receipt, illustrative subsidy receipt | 30 | 90 |
| Waste | Thermal slip, landscape weighbridge | 30 | 90 |

Each base has clean, scan and photo variants. Scan/photo images have seeded per-line ink erosion, mean blur, brightness variation and fixed sharpness. The optional natural-wear experiment is available in the generator, but is not applied to this published set.

Annotations include intended text, polygons, field/value/unit associations, periods and evidence line IDs. Meter readings use their printed point dates; reading-type context is unscoped; amount due uses the issue date. Fuel gross amount is separate from the net rounded payable amount. Waste weight describes a transfer, and the declared destination does not prove completed disposal or recovery. No emissions are calculated and no SEDG mapping is asserted.

Splits group all variants of each base together: 80 development bases (240 images), 24 validation candidates (72 images), and 16 test candidates (48 images). Layout families are shared across splits. Human visibility review is pending; labels describe intended content, and heavily degraded text may need review. These are development fixtures and candidate evaluation data, not an independently validated benchmark or evidence of real-world OCR performance. Never split image variants randomly between training and testing.

`manifest.json` lists every image/annotation hash, configuration, generator hashes and font hashes. `validation.json` records offline integrity checks. `provenance.json` explains structural references and their limitations. The original generator and synthetic contributions use the repository's Apache-2.0 license. Third-party reference images and font binaries are not distributed. Prices, names, identifiers and quantities are fictional; these are not official bills, tariff/subsidy guidance or regulated waste forms.

Run the sibling generator package to validate or create a separate dataset. Generation is fully offline and refuses an existing output directory. Keep generated experiments outside this versioned dataset until reviewed.
