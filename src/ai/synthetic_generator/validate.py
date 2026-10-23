"""Validate hashes, evidence, geometry, dates, arithmetic and split isolation offline."""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from PIL import Image


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(root, relative):
    candidate = (root / relative).resolve()
    require(candidate.is_relative_to(root), f'Path outside dataset: {relative}')
    return candidate


def validate(root):
    """Raise ValueError on invalid data; return machine-readable checks otherwise.

    Validation verifies intended labels and packaging, not human legibility,
    OCR accuracy or representativeness of real Malaysian documents.
    """
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    items = manifest['items']
    require(len(items) == manifest['image_count'] and len(items) > 0, 'Image count mismatch')
    seen_ids, seen_hashes, files = set(), set(), set()
    groups = defaultdict(list)
    schema = json.loads(Path(__file__).with_name('label_schema.json').read_text(encoding='utf-8'))
    allowed_fields = schema['$defs']['field']['properties']['field']['enum']
    allowed_units = schema['$defs']['field']['properties']['unit']['enum']
    for item in items:
        identity = item['item_id']
        require(identity not in seen_ids, f'Duplicate item: {identity}')
        seen_ids.add(identity)
        paths = {}
        for key, digest in [('image', 'sha256'), ('annotation', 'annotation_sha256')]:
            path = safe_path(root, item[key])
            require(path not in files, f'Duplicate file: {item[key]}')
            files.add(path)
            require(hashlib.sha256(path.read_bytes()).hexdigest() == item[digest], f'Hash mismatch: {item[key]}')
            paths[key] = path
        require(item['sha256'] not in seen_hashes, f'Duplicate image: {identity}')
        seen_hashes.add(item['sha256'])
        ann = json.loads(paths['annotation'].read_text(encoding='utf-8'))
        require(all(key in ann for key in schema['required']), f'Missing label keys: {identity}')
        for key in ['item_id', 'base_document_id', 'category', 'layout_family', 'split']:
            require(ann[key] == item[key], f'Metadata mismatch: {identity}/{key}')
        require(ann['category'] in ('electricity', 'water', 'fuel', 'waste'), 'Unknown category')
        with Image.open(paths['image']) as image:
            image.load()
            require(image.format == 'PNG' and image.size == (ann['width'], ann['height']), f'Image dimensions: {identity}')
        require(ann['source_real_pixels_used'] is False, f'Source pixel declaration: {identity}')
        lines = {line['line_id']: line for line in ann['intended_lines']}
        require(len(lines) == len(ann['intended_lines']) and len(lines) > 0, f'Line IDs: {identity}')
        for line in lines.values():
            require(len(line['polygon']) == 4, f'Polygon corners: {identity}')
            require(all(0 <= x < ann['width'] and 0 <= y < ann['height'] for x, y in line['polygon']), f'Polygon bounds: {identity}')
            xs, ys = zip(*line['polygon'])
            require(line['bbox'] == [min(xs), min(ys), max(xs), max(ys)], f'Polygon/bbox mismatch: {identity}')
        for field in ann['expected_fields']:
            require(field['field'] in allowed_fields and field['unit'] in allowed_units, f'Unknown field/unit: {identity}')
            require(field['evidence'], f'Missing evidence: {identity}')
            for evidence in field['evidence']:
                require(evidence['line_id'] in lines and lines[evidence['line_id']]['text'] == evidence['text'], f'Evidence mismatch: {identity}')
            start, end = field['period']['start'], field['period']['end']
            if start is None or end is None:
                require(start is None and end is None and field['temporal_semantics'] == 'unscoped_context', f'Unscoped period: {identity}')
            else:
                require(date.fromisoformat(start) <= date.fromisoformat(end), f'Period order: {identity}')
                require(field['temporal_semantics'] == ('point_date' if start == end else 'service_period_context'), f'Period semantics: {identity}')
            if field['field'] == 'reading_type':
                require(start is None and end is None, f'Reading type must be unscoped: {identity}')
            if field['field'] in ('water_previous_reading', 'water_current_reading', 'amount_due'):
                require(start is not None and start == end, f'Expected point date: {identity}')
        for equation in ann['arithmetic_checks']:
            require(Decimal(str(equation['lhs'])) == Decimal(str(equation['rhs'])), f'Arithmetic: {identity}')
        transforms = ann['transforms']
        require(transforms['profile'] == item['profile'], f'Capture profile: {identity}')
        require(transforms['sharpness_factor'] == 1.0, f'Sharpness: {identity}')
        require(1 <= transforms['brightness_factor'] <= 1.085, f'Brightness: {identity}')
        if item['profile'] != 'clean':
            require(transforms['blur_kernel'] == [3, 3] and transforms['mean_blur_blend'] == .45, f'Mean blur: {identity}')
            strengths = transforms['line_erosion']
            require(set(strengths) == set(lines), f'Erosion line coverage: {identity}')
            lo, hi = transforms['erosion_range']
            require(all(lo <= value <= hi for value in strengths.values()), f'Erosion range: {identity}')
            require(abs(sum(strengths.values()) / len(strengths) - (lo+hi)/2) < 1e-10, f'Erosion mean: {identity}')
        groups[item['base_document_id']].append(item)
    for base, variants in groups.items():
        require(len(variants) == 3 and {i['profile'] for i in variants} == {'clean', 'scan', 'photo'}, f'Capture variants: {base}')
        require(len({i['split'] for i in variants}) == 1, f'Split leakage: {base}')
    require(len(groups) == manifest['base_documents'], 'Base count mismatch')
    require(dict(Counter(i['category'] for i in items)) == manifest['category_counts'], 'Category count mismatch')
    actual = {p.resolve() for p in root.glob('*/*') if p.suffix in ('.png', '.json')}
    require(actual == files, 'Unlisted image or annotation files')
    return {'status': 'pass', 'images': len(items), 'base_documents': len(groups),
            'category_counts': manifest['category_counts'], 'model_calls': 0,
            'checks': ['SHA-256', 'unique images', 'PNG decoding', 'field vocabulary', 'evidence links',
                       'polygon bounds', 'temporal semantics', 'arithmetic', 'capture parameters', 'base-grouped splits', 'file completeness'],
            'human_visibility_review': 'pending',
            'limitations': 'Intended-label checks only; no OCR accuracy or real-world validity claim.'}
