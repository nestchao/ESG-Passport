# Synthetic document generator

Offline code renders fictional Malaysian-style electricity bills, water bills, fuel receipts and waste weighbridge slips. Eight layout families produce clean, scan and photo variants, with JSON field values, units, dates, evidence lines and transformed coordinates. No credentials, external images, API calls or private development modules are required.

Use Python 3.12 and the pinned Pillow/NumPy dependencies in `requirements.txt`; `requirements.in` records the direct dependencies. Install with `uv pip install --python <your-venv-interpreter> -r src/ai/synthetic_generator/requirements.txt`. Create or select a project virtual environment first. Substitute its explicit interpreter path in the commands below.

From the repository root, set `PYTHONPATH` to `src`. For PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
& <your-venv-interpreter> -m ai.synthetic_generator validate src/ai/synthetic_dataset
& <your-venv-interpreter> -m ai.synthetic_generator generate --output src/ai/.local/generated-example --font-dir C:/Windows/Fonts
& <your-venv-interpreter> -m unittest discover -s tests -p test_synthetic_generator.py
```

For a POSIX shell, prefix the interpreter command with `PYTHONPATH=src`. Supply the local font directory, such as `/mnt/c/Windows/Fonts` when using WSL on Windows. The four required files are `arial.ttf`, `arialbd.ttf`, `cour.ttf` and `courbd.ttf`. They are not bundled or downloaded; use locally licensed fonts. Exact reproduction requires the font hashes in the dataset manifest, the pinned dependencies and the recorded configuration. Renaming substitute fonts can change geometry and will not reproduce the published images.

The output directory must not already exist. Default generation creates 120 base documents and 360 images. `--bases-per-family 1` creates a 24-image smoke sample; values 1–15 are supported. Smaller samples are separately seeded datasets rather than a guaranteed subset of the full set. `config.json` records the default configuration and controls random seeds and text effects; the CLI controls count and optional wear. Changing settings produces a different dataset.

The published JSON and source hashes use LF line endings. Preserve those bytes when checking out or editing the dataset; on Windows, clone with `git -c core.autocrlf=false clone <repository-url>` to avoid automatic JSON line-ending conversion. The published reproduction check used Python 3.12 under WSL with the recorded fonts and pinned dependencies.

Default scan/photo degradation applies a shuffled 0.12–0.48 erosion strength, uniform within each text line, with mean strength 0.30. It then blends a 3×3 arithmetic mean blur at 0.45, raises brightness by a seeded factor of 1.025–1.085, and holds sharpness at 1.0. Photo capture adds perspective, tint and mild shadow; label polygons follow the homography. Clean images retain the original print. Lines and barcodes are separate from the text ink mask.

`--wear light` or `--wear moderate` optionally replaces the default erosion with correlated fading, stroke-edge loss, clustered gaps, crease wear and paper aging. Clean variants stay unchanged. This is an experimental visual approximation, not a calibrated aging model; barcode/rule ink-loss is not simulated. The published dataset uses `--wear none`.

`validate` checks file hashes, decoding, geometry, evidence, arithmetic, temporal semantics, capture settings and split isolation. `label_schema.json` is also available for consumers using JSON Schema; the CLI performs its own dependency-light semantic checks. Validation does not establish OCR accuracy, human visibility or similarity to real records. See the dataset README and provenance for licensing and evaluation limits.
