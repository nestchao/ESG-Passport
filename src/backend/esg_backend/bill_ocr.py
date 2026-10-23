"""OCR candidates for the EXISTING record upload/edit flow.

The original file is always retained. OCR is untrusted: ambiguous amounts are
not inferred, and no extracted value is ever confirmed automatically.
"""
from calendar import monthrange
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
import re

from PIL import Image

UNITS = {
    'kwh': 'kWh', 'litres': 'L', 'liters': 'L', 'litre': 'L',
    'liter': 'L', 'l': 'L', 'm3': 'm3', 'm³': 'm3',
    'kg': 'kg', 'tonnes': 't', 'tonne': 't', 'tons': 't',
    'ton': 't', 't': 't',
}
UNIT_PATTERN = r'(?:kWh|m3|m³|litres?|liters?|kg|tonnes?|tons?|\bL\b|\bt\b)'
VALUE_UNIT = re.compile(r'(?<![\w./])([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(' + UNIT_PATTERN + r')(?![\w/])', re.I)
DATE_PATTERN = re.compile(r'(?<!\d)(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})(?!\d)')
LABELS = {'electricity': r'electricity|electric|usage|consum|penggunaan|kegunaan|tenaga|ringkasan|total|jumlah',
          'water': r'water|air|usage|consum|withdraw|volume|penggunaan|kegunaan|total|jumlah',
          'diesel': r'diesel|fuel|bahan api|litre|total|jumlah',
          'petrol': r'petrol|gasoline|fuel|bahan api|litre|total|jumlah',
          'waste_generated': r'generated|generation|dijana|total waste|jumlah sisa',
          'waste_diverted': r'diverted|diversion|recycl|dikitar|dialih',
          'waste_disposed': r'dispos|dilupus|landfill'}
EXPECTED = {'electricity': {'kWh'}, 'water': {'L', 'm3'},
            'diesel': {'L'}, 'petrol': {'L'},
            'waste_generated': {'kg', 't'}, 'waste_diverted': {'kg', 't'},
            'waste_disposed': {'kg', 't'}}


def _date(value):
    try:
        if re.match(r'^20\d{2}', value):
            return date.fromisoformat(value.replace('/', '-'))
        return datetime.strptime(value.replace('-', '/'), '%d/%m/%Y').date()
    except ValueError:
        return None


def _period(lines, month):
    year, number = map(int, month.split('-'))
    start, end = date(year, number, 1), date(year, number, monthrange(year, number)[1])
    for line in lines:
        if not re.search(r'\b(?:billing\s*period|bill\s*period|reading\s*period|usage\s*period|tempoh\s*bil|tempoh\s*penggunaan|period\s*of\s*supply)', line, re.I):
            continue
        found = [_date(value) for value in DATE_PATTERN.findall(line)]
        found = [d for d in found if d]
        if len(found) == 2 and found[0] <= found[1]:
            return found[0], found[1], True
    return start, end, False


def parse_bill_text(lines, category, month):
    """Require unit + relevant label; never guess based on price or arbitrary numbers."""
    notes = ['OCR candidates are unverified. Check the original document before confirming.']
    clean_lines = [re.sub(r'\s+', ' ', line).strip() for line in lines if line and line.strip()]
    first, last, period_found = _period(clean_lines, month)
    if not period_found:
        notes.append('Billing-period dates were not reliably identified; the selected reporting month is a placeholder.')
    elif first.strftime('%Y-%m') != month or last.strftime('%Y-%m') != month:
        notes.append('Extracted billing dates differ from the selected reporting month; resolve before confirming.')
    categories = ('waste_generated', 'waste_diverted', 'waste_disposed') if category == 'waste' else (category,)
    activities = []
    for kind in categories:
        candidates = []
        for index, line in enumerate(clean_lines):
            # OCR often separates a usage heading from the following number.
            # Match the immediately preceding label; do not borrow headings
            # from arbitrary lines farther away (e.g. previous months).
            labelled = bool(re.search(LABELS[kind], line, re.I))
            if not labelled and index:
                labelled = bool(re.search(LABELS[kind], clean_lines[index - 1], re.I))
            if not labelled:
                continue
            for match in VALUE_UNIT.finditer(line):
                unit = UNITS.get(match.group(2).lower())
                if unit not in EXPECTED[kind]:
                    continue
                # Amounts are accepted only alongside an explicit relevant label;
                # avoid interpreting other waste streams as the requested type.
                if category == 'waste':
                    others = [k for k in categories if k != kind and re.search(LABELS[k], line, re.I)]
                    if others:
                        continue
                value = match.group(1).replace(',', '')
                candidates.append((value, unit, line))
        unique = {(value, unit) for value, unit, _ in candidates}
        if len(unique) == 1:
            value, unit, line = candidates[0]
            activities.append({'category': kind, 'quantity': value, 'unit': unit,
                               'period_start': first.isoformat(), 'period_end': last.isoformat(),
                               'estimated': False, 'assumptions': '', 'allocated_period': None,
                               'source_reference': ('OCR page 1: ' + line[:170])})
        elif len(unique) > 1:
            notes.append(f'{kind}: multiple different quantities found; left blank for manual entry.')
        else:
            notes.append(f'{kind}: no clearly labelled quantity and unit found; enter manually.')
    document_date = None
    for line in clean_lines:
        if re.search(r'\b(?:invoice date|bill date|issued on|tarikh bil)\b', line, re.I):
            dates = [_date(text) for text in DATE_PATTERN.findall(line)]
            document_date = next((d.isoformat() for d in dates if d), None)
            if document_date:
                break
    supplier = None
    for line in clean_lines[:4]:
        if re.search(r'\b(?:invoice|billing period|bill date|account no|tax invoice|receipt|statement)\b', line, re.I):
            continue
        if re.search('[A-Za-z]', line) and not re.search(r'\b(?:kwh|kg|m3|litres?)\b', line, re.I):
            supplier = line[:150]
            break
    return {'supplier_name': supplier, 'document_date': document_date,
            'period_start': first.isoformat(), 'period_end': last.isoformat(),
            'activities': activities, 'uncertainty_notes': notes,
            'ocr_status': 'candidate_found' if activities else 'manual_entry_required',
            'ocr_engine': 'RapidOCR (offline)'}


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def _image_lines(image):
    import numpy as np
    # Re-check after decoding; uploads are separately limited by validate_file.
    if image.width * image.height > 40_000_000:
        raise ValueError('OCR image too large')
    rows, _ = _engine()(np.asarray(image.convert('RGB')))
    if not rows:
        return []
    # Preserve reading order; using OCR's native detection order.
    return [row[1] for row in rows if len(row) >= 3 and row[2] >= 0.50]


def extract_upload(content, mime, category, reporting_month):
    """OCR image / one-page PDF; errors return editable manual fallback metadata."""
    try:
        used_pdf_text = False
        if mime == 'application/pdf':
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            embedded = reader.pages[0].extract_text() or ''
            if len(embedded.strip()) >= 30:
                lines = embedded.splitlines()
                used_pdf_text = True
            else:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(content)
                page = pdf[0]
                width, height = page.get_size()
                if width * height * 4 > 40_000_000:
                    raise ValueError('PDF page exceeds OCR pixel limit')
                image = page.render(scale=2).to_pil()
                lines = _image_lines(image)
                image.close()
                page.close()
                pdf.close()
        else:
            with Image.open(BytesIO(content)) as im:
                lines = _image_lines(im)
        result = parse_bill_text(lines, category, reporting_month)
        if used_pdf_text:
            result['ocr_engine'] = 'PDF text extraction (offline)'
        if not lines:
            result['uncertainty_notes'].append('OCR found no readable text; enter values manually.')
        return result
    except Exception:
        # Do not lose the uploaded original if OCR or the local runtime fails.
        result = parse_bill_text([], category, reporting_month)
        result['ocr_status'] = 'unavailable'
        result['uncertainty_notes'].append('OCR could not process this file; the original is stored, and manual entry is required.')
        return result
