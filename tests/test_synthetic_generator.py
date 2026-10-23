"""Offline integrity and regression tests for the public synthetic package."""
from pathlib import Path
import copy
import hashlib
import json
import os
import random
import tempfile
import unittest
import numpy as np
from PIL import Image, ImageDraw
from ai.synthetic_generator.generate import FAMILIES, configure, context, generate, render_capture
from ai.synthetic_generator.validate import safe_path, validate
from ai.synthetic_generator.wear import natural_wear

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'src/ai/synthetic_dataset'


class DatasetTests(unittest.TestCase):
    def test_all_published_pairs_have_valid_evidence_geometry_and_splits(self):
        result = validate(DATASET)
        self.assertEqual(result['images'], 360)
        self.assertEqual(result['base_documents'], 120)
        self.assertEqual(set(result['category_counts'].values()), {90})

    def test_rejects_parent_path_escape(self):
        with self.assertRaisesRegex(ValueError, 'outside dataset'):
            safe_path(DATASET.resolve(), '../outside.png')

    def test_corrupt_field_evidence_is_rejected_even_with_updated_file_hash(self):
        # A broken evidence link must fail semantic checks even after rehashing.
        manifest = json.loads((DATASET/'manifest.json').read_text())
        first_base = manifest['items'][0]['base_document_id']
        manifest['items'] = [copy.deepcopy(i) for i in manifest['items'] if i['base_document_id'] == first_base]
        manifest.update(image_count=3, base_documents=1, category_counts={'electricity': 3})
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as directory:
            folder = Path(directory)
            for item in manifest['items']:
                for key in ['image', 'annotation']:
                    target = folder/item[key]
                    target.parent.mkdir(exist_ok=True)
                    target.write_bytes((DATASET/item[key]).read_bytes())
            item = manifest['items'][0]
            annotation = folder/item['annotation']
            value = json.loads(annotation.read_text())
            value['expected_fields'][0]['evidence'][0]['text'] = 'INVALID EVIDENCE'
            annotation.write_text(json.dumps(value))
            item['annotation_sha256'] = hashlib.sha256(annotation.read_bytes()).hexdigest()
            (folder/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Evidence mismatch'):
                validate(folder)


class WearTests(unittest.TestCase):
    def test_seeded_wear_removes_ink_monotonically_and_preserves_background_mask(self):
        paper = Image.new('RGB', (180, 120), '#fffefa')
        mask = Image.new('L', paper.size)
        draw = ImageDraw.Draw(mask)
        draw.rectangle((20, 35, 140, 55), fill=230)
        draw.rectangle((40, 75, 155, 90), fill=255)
        for printing in ('thermal', 'printed'):
            low = natural_wear(paper, mask, 219, printing, .32)
            high = natural_wear(paper, mask, 219, printing, .70)
            repeat = natural_wear(paper, mask, 219, printing, .32)
            np.testing.assert_array_equal(low[3], repeat[3])
            self.assertEqual(low[0].tobytes(), repeat[0].tobytes())
            self.assertTrue(np.all(high[3] <= low[3] + 1e-12))
            self.assertTrue(np.all(low[3][np.asarray(mask) == 0] == 0))
            self.assertLess(high[2]['mean_ink_retention'], low[2]['mean_ink_retention'])

    def test_invalid_wear_strength_is_rejected(self):
        with self.assertRaises(ValueError):
            natural_wear(Image.new('RGB', (20, 20)), Image.new('L', (20, 20)), 1, 'printed', -1)


class ReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        supplied = os.environ.get('SYNTHETIC_FONT_DIR')
        candidates = [Path(supplied)] if supplied else [Path('C:/Windows/Fonts'), Path('/mnt/c/Windows/Fonts')]
        cls.font_dir = next((p for p in candidates if all((p/name).is_file() for name in ['arial.ttf','arialbd.ttf','cour.ttf','courbd.ttf'])), None)
        if cls.font_dir is None:
            raise unittest.SkipTest('Provide SYNTHETIC_FONT_DIR with locally licensed Arial/Courier fonts')
        manifest = json.loads((DATASET/'manifest.json').read_text())
        expected = manifest['font_sha256']
        if any(hashlib.sha256((cls.font_dir/name).read_bytes()).hexdigest() != digest for name,digest in expected.items()):
            raise unittest.SkipTest('Font hashes differ from published reproduction baseline')
        cls.items = {item['item_id']: item for item in manifest['items']}

    def test_all_layouts_reproduce_published_clean_scan_photo_pixels_and_coordinates(self):
        for k, (category, family, renderer) in enumerate(FAMILIES):
            order = list(range(30))
            random.Random(73000+k*45).shuffle(order)
            configure(context(category, 0 if k % 2 == 0 else 15, family), self.font_dir)
            page = renderer(order[0])
            for profile in ('clean', 'scan', 'photo'):
                identity = f'{category}-{family}-001-{profile}'
                with self.subTest(identity=identity):
                    item = self.items[identity]
                    ann = json.loads((DATASET/item['annotation']).read_text())
                    image, params, lines = render_capture(page, profile, ann['transforms']['seed'])
                    with Image.open(DATASET/item['image']) as expected:
                        self.assertEqual(image.tobytes(), expected.tobytes())
                    self.assertEqual(json.loads(json.dumps(params)), ann['transforms'])
                    self.assertEqual(lines, ann['intended_lines'])

    def test_generation_refuses_existing_output_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as directory:
            marker = Path(directory)/'keep.txt'
            marker.write_text('preserve')
            with self.assertRaises(FileExistsError):
                generate(directory, self.font_dir, bases_per_family=1)
            self.assertEqual(marker.read_text(), 'preserve')

    def test_small_generation_writes_valid_pairs_and_revision_metadata(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as directory:
            output = Path(directory)/'generated'
            manifest = generate(output, self.font_dir, bases_per_family=1)
            self.assertEqual(manifest['image_count'], 24)
            self.assertEqual(validate(output)['base_documents'], 8)
            for item in manifest['items']:
                label = json.loads((output/item['annotation']).read_text())
                if item['profile'] == 'clean':
                    self.assertNotIn('augmentation_revision', label)
                else:
                    self.assertEqual(label['augmentation_revision'], 'random-per-line-text-erosion-v1')

    def test_optional_wear_preserves_field_values_and_label_geometry(self):
        configure(context('fuel', 0, 'pump'), self.font_dir)
        page = FAMILIES[4][2](1)
        before = copy.deepcopy(page.fields)
        baseline, _, lines = render_capture(page, 'photo', 811)
        aged, params, aged_lines = render_capture(page, 'photo', 811, wear='moderate')
        self.assertEqual(lines, aged_lines)
        self.assertEqual(before, page.fields)
        self.assertNotEqual(baseline.tobytes(), aged.tobytes())
        self.assertIn('natural_wear', params)


if __name__ == '__main__':
    unittest.main()
