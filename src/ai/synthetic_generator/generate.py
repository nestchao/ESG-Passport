"""Generate paired images and intended labels without API calls."""
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
import calendar
import hashlib
import json
import random
from . import layouts
from .render import configure, render_capture as _capture
from .wear import CapturePage, natural_wear

CATEGORIES = ['electricity', 'water', 'fuel', 'waste']

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def point(value):
    return {'start': value.isoformat(), 'end': value.isoformat()}

def context(category,n,family):
    rng=random.Random(load_config()['context_seed']+CATEGORIES.index(category)*1000+n*19)
    month=rng.randrange(1,10);year=2026
    start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
    trans=date(year,month,rng.randrange(1,calendar.monthrange(year,month)[1]+1))
    issue=end+timedelta(days=2);due=issue+timedelta(days=30)
    route=rng.choice(['landfill','recycling'])
    material='GENERAL WASTE' if route=='landfill' else rng.choice(['CARDBOARD','PAPER','PLASTIC','SCRAP METAL'])
    return {'rng':rng,'start':start,'end':end,'transaction':trans,'issue':issue,'due':due,
      'period':{'start':start.isoformat(),'end':end.isoformat()} if category in ['electricity','water'] else point(trans),
      'history_months':[(start-timedelta(days=60)).strftime('%b %Y').upper(),(start-timedelta(days=30)).strftime('%b %Y').upper()],
      'business':rng.choice(['KEDAI DEMO MERANTI','KILANG DEMO ANGSANA','BENGKEL DEMO CERIA','KAFE DEMO KENCANA']),
      'route':route,'material':material}

FAMILIES = [
    ('electricity', 'itemised', layouts.electricity_itemised),
    ('electricity', 'payment-stub', layouts.electricity_stub),
    ('water', 'sidebar', layouts.sidebar_water),
    ('water', 'payment-stub', layouts.water_stub),
    ('fuel', 'pump', lambda index: layouts.fuel_receipt(index, False)),
    ('fuel', 'subsidy', lambda index: layouts.fuel_receipt(index, True)),
    ('waste', 'thermal', layouts.thermal_waste),
    ('waste', 'landscape', layouts.landscape_waste),
]

def load_config():
    return json.loads(Path(__file__).with_name('config.json').read_text(encoding='utf-8'))

def resolve_fonts(font_dir):
    directory = Path(font_dir).expanduser().resolve()
    for name in ('arial.ttf', 'arialbd.ttf', 'cour.ttf', 'courbd.ttf'):
        if not (directory / name).is_file():
            raise FileNotFoundError(f'Required font missing: {directory / name}')
    return directory

def render_capture(page, profile, seed, wear='none'):
    effects = load_config()['text_effects']
    if wear == 'none' or profile == 'clean':
        return _capture(page, profile, seed, text_effects=effects)
    severity = {'light': .32, 'moderate': .70}[wear]
    paper, ink = page.finish()
    printing = 'thermal' if page.category == 'fuel' or (page.category == 'waste' and page.w < 600) else 'printed'
    paper, ink, wear_params, _ = natural_wear(paper, ink, seed+190007, printing, severity)
    effects = dict(effects, erosion_blend=0, erosion_range=[0, 0])
    image, params, lines = _capture(CapturePage(page, paper, ink), profile, seed, text_effects=effects)
    params['natural_wear'] = wear_params
    params['order'] = ['natural_material_wear'] + params['order']
    return image, params, lines

def generate(output, font_dir, *, bases_per_family=15, wear='none'):
    if not isinstance(bases_per_family, int) or not 1 <= bases_per_family <= 15:
        raise ValueError('bases_per_family must be an integer from 1 to 15')
    if wear not in ('none', 'light', 'moderate'):
        raise ValueError('wear must be none, light or moderate')
    font_dir = resolve_fonts(font_dir)
    OUT = Path(output).resolve()
    # An exclusive new directory prevents overwriting datasets or unrelated files.
    OUT.mkdir(parents=True, exist_ok=False)
    families = FAMILIES
    config = load_config()
    items=[];base_ids=set();checks=[]
    for category,family,renderer in families:
        folder=OUT/category;folder.mkdir(exist_ok=True)
        order=list(range(30));random.Random(config['layout_seed']+len(items)).shuffle(order)
        for local in range(bases_per_family):
            n=(0 if family==next(f for c,f,_ in families if c==category) else 15)+local
            current_context=context(category,n,family)
            configure(current_context,font_dir)
            p=renderer(order[local]);p.period=current_context['period']
            # Capture reading type when it was printed as context by the old layout.
            if category=='electricity' and not any(f['field']=='reading_type' for f in p.fields):
                l=next(l for l in p.lines if 'Jenis bacaan' in l['text'])
                p.fields.append({'field':'reading_type','value':'actual','unit':None,'role':'context',
                    'period':{'start':None,'end':None},'evidence':[{'line_id':l['line_id'],'text':l['text']}]})
            for f in p.fields:
                if f['field']=='treatment_route':f['field']='declared_destination'
                f['temporal_semantics']='unscoped_context' if f['period']['start'] is None else (
                    'point_date' if f['period']['start']==f['period']['end'] else 'service_period_context')
            for eq in p.checks:assert Decimal(str(eq['lhs']))==Decimal(str(eq['rhs'])),eq
            for f in p.fields:
                for e in f['evidence']:assert any(l['line_id']==e['line_id'] and l['text']==e['text'] for l in p.lines)
            base=f'{category}-{family}-{local+1:03}';base_ids.add(base)
            split='development' if local<10 else ('validation_candidate' if local<13 else 'test_candidate')
            checks.append({'base_document_id':base,'equations':p.checks,'evidence_links_valid':True})
            for v,profile in enumerate(['clean','scan','photo']):
                seed=config['capture_seed']+len(base_ids)*10+v
                im,params,lines=render_capture(p,profile,seed,wear)
                stem=base+'-'+profile;imagepath=folder/(stem+'.png');im.save(imagepath)
                ann={'version':'malaysia-four-categories-v2','item_id':stem,'base_document_id':base,
                    'category':category,'layout_family':family,'split':split,'width':im.width,'height':im.height,
                    'language':'mixed-ms-en','period':p.period,'intended_lines':lines,'expected_fields':p.fields,
                    'transforms':params,'source_real_pixels_used':False,'human_visibility_review':'pending',
                    'label_status':'intended text; provisional visibility and temporal labels',
                    'supporting_fields':getattr(p,'supporting_fields',{}),'arithmetic_checks':p.checks,
                    'not_official':'Fictional identities, prices and quantities. Not official tariff or subsidy guidance.'}
                if profile != 'clean':
                    ann['augmentation_revision'] = 'random-per-line-text-erosion-v1' if wear == 'none' else 'natural-material-wear-v1'
                annotationpath=folder/(stem+'.json');write(annotationpath,ann)
                items.append({'item_id':stem,'base_document_id':base,'category':category,'layout_family':family,
                    'split':split,'profile':profile,'image':imagepath.relative_to(OUT).as_posix(),
                    'annotation':annotationpath.relative_to(OUT).as_posix(),'sha256':sha(imagepath),'annotation_sha256':sha(annotationpath)})
            if (local+1)%5==0:print(json.dumps({'category':category,'family':family,'base_documents':len(base_ids),'images':len(items)}),flush=True)
    manifest = {
        'version': 'malaysia-four-categories-v2', 'image_count': len(items),
        'base_documents': len(base_ids), 'layout_families': len(families),
        'category_counts': {c: sum(i['category'] == c for i in items) for c in CATEGORIES},
        'items': items, 'model_calls': 0, 'wear': wear,
        'config': dict(load_config(), bases_per_family=bases_per_family),
        'font_sha256': {p.name: sha(p) for p in sorted(font_dir.glob('*.ttf')) if p.name in ('arial.ttf','arialbd.ttf','cour.ttf','courbd.ttf')},
        'generator_files': {p.name: sha(p) for p in sorted(Path(__file__).parent.iterdir()) if p.suffix in ('.py', '.json')},
        'split_warning': 'Base-grouped candidate splits share layout families and need independent visibility review; no real-world accuracy claim.'
    }
    write(OUT/'manifest.json', manifest)
    from .validate import validate
    report = validate(OUT)
    write(OUT/'validation.json', report)
    return manifest
