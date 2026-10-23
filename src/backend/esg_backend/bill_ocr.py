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
UNIT_PATTERN = r'(?:kWh|m3|m³|litres?|liters?|kg|tonnes?|tons?|L\b|t\b)'
VALUE_UNIT = re.compile(r'(?<![\w./])([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(' + UNIT_PATTERN + r')(?![\w/])', re.I)
DATE_PATTERN = re.compile(r'(?<!\d)(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})(?!\d)')
LABELS = {'electricity': r'electricity|electric|usage|consum|penggunaan|kegunaan|tenaga|ringkasan|total|jumlah',
          'water': r'water|air|usage|consum|withdraw|volume|penggunaan|kegunaan|total|jumlah',
          'diesel': r'diesel|fuel|bahan api|litre|volume|isipadu|total|jumlah',
          'petrol': r'petrol|gasoline|fuel|bahan api|litre|volume|isipadu|total|jumlah',
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
        if not re.search(r'\b(?:billing\s*period|bill\s*period|reading\s*period|usage\s*period|tempoh\s*bil|tempoh\s*penggunaan|tempoh\s*:|period\s*of\s*supply)', line, re.I):
            continue
        found = [_date(value) for value in DATE_PATTERN.findall(line)]
        found = [d for d in found if d]
        if len(found) == 2 and found[0] <= found[1]:
            return found[0], found[1], True
    return start, end, False


def _labelled_mass(lines, labels):
    """Read exactly one weight next to an unambiguous weighbridge label."""
    results = []
    for index, line in enumerate(lines):
        if not re.search(labels, line, re.I):
            continue
        # Gross and tare labels must never become the accepted net weight.
        if re.search(r'\b(?:gross|tare|berat\s*kasar|berat\s*kenderaan)\b', line, re.I) and labels == NET_WEIGHT_LABEL:
            continue
        own = [(m.group(1).replace(',', ''), UNITS.get(m.group(2).lower()), line)
               for m in VALUE_UNIT.finditer(line)]
        if not own and index + 1 < len(lines):
            next_line = lines[index + 1]
            # Only a *directly adjacent* numeric line, not another heading.
            if not re.search(r'[a-z]', next_line, re.I) or re.match(r'^\s*[:\-]?\s*[0-9]', next_line):
                own = [(m.group(1).replace(',', ''), UNITS.get(m.group(2).lower()), next_line)
                       for m in VALUE_UNIT.finditer(next_line)]
        results.extend((quantity, unit, source) for quantity, unit, source in own if unit in ('kg', 't'))
    return results


NET_WEIGHT_LABEL = r'\bnet\b|berat\s*bersih'
GROSS_WEIGHT_LABEL = r'\bgross\b|berat\s*kasar'
TARE_WEIGHT_LABEL = r'\btare\b|berat\s*kenderaan'


def _waste_transfer_weight(lines, first, last):
    """Net transfer weight only; never claim disposal, generation or diversion."""
    from decimal import Decimal
    net = _labelled_mass(lines, NET_WEIGHT_LABEL)
    unique = {(quantity, unit) for quantity, unit, _ in net}
    if len(unique) != 1:
        return None, ('Multiple different net weights appear on the ticket; enter the verified transfer weight manually.'
                      if unique else 'No clearly labelled net transfer weight was found.')
    quantity, unit, source = net[0]
    gross = _labelled_mass(lines, GROSS_WEIGHT_LABEL)
    tare = _labelled_mass(lines, TARE_WEIGHT_LABEL)
    if len({(q, u) for q, u, _ in gross}) == 1 and len({(q, u) for q, u, _ in tare}) == 1:
        gross_value, gross_unit, _ = gross[0]
        tare_value, tare_unit, _ = tare[0]
        if gross_unit == tare_unit == unit and Decimal(gross_value) - Decimal(tare_value) != Decimal(quantity):
            return None, 'Printed net weight conflicts with gross minus tare; verify the ticket manually.'
    return {'quantity': quantity, 'unit': unit,
            'period_start': first.isoformat(), 'period_end': last.isoformat(),
            'source_reference': 'OCR page 1, NET / BERAT BERSIH: ' + source[:145]}, None


# A declared route is only a clue about a possible ESG outcome. Never
# interpret notes/disclaimers (e.g. "not proof of completed disposal") or a
# bare word elsewhere in the ticket as classification evidence.
WASTE_ROUTE_LABEL = re.compile(
    r'^\s*(?:tujuan|destination|destinasi|route|disposal\s*route|treatment\s*route|laluan)\s*[:\-]?\s*(.*)$', re.I)
WASTE_ROUTE_RECYCLING = re.compile(r'\b(?:recycl(?:ing|e[ds]?)|recovery|kitar\s*semula|dikitar\s*semula)\b', re.I)
WASTE_ROUTE_DISPOSAL = re.compile(r'\b(?:landfill|dispos(?:al|ed)|pelupusan|tapak\s*pelupusan)\b', re.I)


def _waste_route_suggestion(lines):
    """Suggest from an explicit declared destination, never verified outcome.

    Keep a blank category on contradictory/negated/unsupported route text.
    """
    suggestions = []
    route_values = 0
    for index, text in enumerate(lines):
        match = WASTE_ROUTE_LABEL.fullmatch(text)
        if not match:
            continue
        route = match.group(1).strip()
        source = text
        if not route and index + 1 < len(lines):
            # Structured two-line route values occur in weighbridge slips.
            next_value = lines[index + 1].strip()
            if next_value.startswith(':'):
                route = next_value.lstrip(':').strip()
                source = text + ' ' + next_value
        if not route:
            continue
        route_values += 1
        if len(route) > 90:
            continue
        recycling = bool(WASTE_ROUTE_RECYCLING.search(route))
        disposal = bool(WASTE_ROUTE_DISPOSAL.search(route))
        if recycling == disposal:
            continue
        # Ambiguous / negated route wording is not safe to suggest.
        if re.search(r'\b(?:not|no|without|bukan|tidak|unknown|pending|planned|proposed)\b', route, re.I):
            continue
        category = 'waste_diverted' if recycling else 'waste_disposed'
        suggestions.append((category, source))
    if not suggestions or len(suggestions) != route_values or len(set(category for category, _ in suggestions)) != 1:
        return None
    category, source = suggestions[0]
    return {'category': category, 'confidence': 'low', 'status': 'unverified_suggestion',
            'basis': 'declared_destination_only', 'source_text': source[:150],
            'reason': 'The ticket declares a recycling/recovery destination, but does not prove completed diversion.'
                      if category == 'waste_diverted' else
                      'The ticket declares a landfill/disposal destination, but does not prove completed disposal.'}


def parse_bill_text(lines, category, month):
    """Require unit + relevant label; never guess based on price or arbitrary numbers."""
    notes = ['OCR candidates are unverified. Check the original document before confirming.']
    clean_lines = [re.sub(r'\s+', ' ', line).strip() for line in lines if line and line.strip()]
    first, last, period_found = _period(clean_lines, month)
    # Fuel pump slips and waste tickets typically specify a point date, not a
    # multi-day billing period. Use the explicitly printed receipt date only.
    if not period_found and category in ('petrol', 'diesel', 'waste'):
        for index, line in enumerate(clean_lines):
            if re.search(r'^\s*(?:date|tarikh)\s*:', line, re.I):
                dates = [_date(value) for value in DATE_PATTERN.findall(line)]
                if dates and dates[0]:
                    first = last = dates[0]
                    period_found = True
                    break
            # Thermal weighbridge slips sometimes print their sole date on
            # the line immediately after the ticket identifier. Do not scan
            # unrelated free-standing dates throughout the document.
            if (category == 'waste' and re.search(r'^\s*ticket\s*:', line, re.I)
                    and index + 1 < len(clean_lines)
                    and DATE_PATTERN.fullmatch(clean_lines[index + 1])):
                parsed = _date(clean_lines[index + 1])
                if parsed:
                    first = last = parsed
                    period_found = True
                    break
    if not period_found:
        notes.append('Billing-period dates were not reliably identified; the selected reporting month is a placeholder.')
    elif first.strftime('%Y-%m') != month or last.strftime('%Y-%m') != month:
        notes.append('Transfer ticket date differs from the selected reporting month; change the record reporting month before confirming.'
                     if category == 'waste' else
                     'Extracted billing dates differ from the selected reporting month; resolve before confirming.')
    categories = ('waste_generated', 'waste_diverted', 'waste_disposed') if category == 'waste' else (category,)
    # Weighbridge/transfer documentation describes movement, not verified
    # treatment or generation. Even a destination and mass on the SAME LINE
    # ("RECYCLING 4,850 kg") must not automatically become waste_diverted.
    is_transfer_ticket = category == 'waste' and any(re.search(
        r'weighbridge|timbang|\bgross\b|\btare\b|\bnet\b|berat\s*bersih',
        line, re.I) for line in clean_lines)
    activities = []
    for kind in categories:
        if is_transfer_ticket:
            continue
        candidates = []
        for index, line in enumerate(clean_lines):
            # OCR often separates a usage heading from the following number.
            # Match the immediately preceding label; do not borrow headings
            # from arbitrary lines farther away (e.g. previous months).
            labelled = bool(re.search(LABELS[kind], line, re.I))
            if not labelled and index:
                labelled = bool(re.search(LABELS[kind], clean_lines[index - 1], re.I))
            # Some synthetic statements put the consumption label immediately
            # AFTER its numeric value. Only accept specific usage headings;
            # generic "total" on the following line is not strong evidence.
            if not labelled and kind in ('electricity', 'water') and index + 1 < len(clean_lines):
                labelled = bool(re.search(
                    r'energy|usage|consum|penggunaan|tenaga|kegunaan',
                    clean_lines[index + 1], re.I))
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
        # A water bill may contain a reading table whose consumption heading
        # is several lines above the sole printed m3 total. Never guess when
        # there is more than one volume anywhere in the source.
        if kind == 'water' and not candidates:
            printed = [(m.group(1).replace(',', ''), UNITS.get(m.group(2).lower()), i, line)
                       for i, line in enumerate(clean_lines) for m in VALUE_UNIT.finditer(line)]
            printed = [(v, u, i, line) for v, u, i, line in printed if u in EXPECTED[kind]]
            if len(printed) == 1:
                value, unit, index, line = printed[0]
                context = ' '.join(clean_lines[max(0, index - 8):index])
                if re.search(r'penggunaan|consum|water\s+usage', context, re.I):
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
    transfer_candidate = None
    waste_category_suggestion = None
    if category == 'waste' and not activities:
        transfer_candidate, transfer_warning = _waste_transfer_weight(clean_lines, first, last)
        if transfer_warning:
            notes.append(transfer_warning)
        if transfer_candidate:
            waste_category_suggestion = _waste_route_suggestion(clean_lines)
            # The exact mass was found; category is deliberately unresolved.
            # Three redundant per-category "no quantity" messages otherwise
            # make this look like OCR failed completely.
            notes = [note for note in notes if not re.match(r'^waste_(?:generated|diverted|disposed): no clearly labelled', note)]
            notes.append('Detected net transfer weight ' + transfer_candidate['quantity'] + ' ' + transfer_candidate['unit'] + '. You must choose a supported ESG waste category after checking additional evidence.')
        if waste_category_suggestion:
            notes.append('Suggested category is based only on the declared route and is NOT verified. Review supporting evidence before applying or confirming it.')
        notes.append('Transfer weights and declared destinations do not prove waste generated, diverted, or disposed; select a category only with supporting evidence.')
    document_date = None
    for line in clean_lines:
        if re.search(r'\b(?:invoice date|bill date|issued on|tarikh\s*bil|tarikh\s*:|date\s*:)\b', line, re.I) or re.match(r'^\s*(?:date|tarikh)\s*:', line, re.I):
            dates = [_date(text) for text in DATE_PATTERN.findall(line)]
            document_date = next((d.isoformat() for d in dates if d), None)
            if document_date:
                break
    if document_date is None and category in ('waste', 'petrol', 'diesel') and period_found and first == last:
        document_date = first.isoformat()
    supplier = None
    for line in clean_lines[:4]:
        if re.search(r'\b(?:invoice|billing period|bill date|account no|tax invoice|receipt|statement)\b', line, re.I):
            continue
        if re.search('[A-Za-z]', line) and not re.search(r'\b(?:kwh|kg|m3|litres?)\b', line, re.I):
            supplier = line[:150]
            break
    return {'supplier_name': supplier, 'document_date': document_date,
            'period_start': first.isoformat(), 'period_end': last.isoformat(),
            'activities': activities, 'waste_transfer_candidate': transfer_candidate,
            'waste_category_suggestion': waste_category_suggestion,
            'uncertainty_notes': notes,
            'ocr_status': 'candidate_found' if activities or transfer_candidate else 'manual_entry_required',
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
