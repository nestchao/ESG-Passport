"""Deterministic document drawing and capture simulation."""
from pathlib import Path
from contextvars import ContextVar
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

S = 2
_context = ContextVar('document_context')
_font_dir = ContextVar('font_directory')

class Context:
    def __getitem__(self, key):
        return _context.get()[key]

CONTEXT = Context()

def configure(context, font_dir):
    """Set drawing state for the current execution context."""
    _context.set(context)
    _font_dir.set(Path(font_dir))

def font_path(mono=False, bold=False):
    return _font_dir.get() / (('cour' if mono else 'arial') + ('bd' if bold else '') + '.ttf')

def dm(value):
    return value.strftime('%d/%m/%Y')

def point(value):
    return {'start': value.isoformat(), 'end': value.isoformat()}

def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

class BasePage:
    def __init__(self, width, height, category, index):
        self.w, self.h = width, height
        self.category, self.index = category, index
        self.paper = Image.new('RGB', (width*S, height*S), '#fffefa')
        self.ink = Image.new('L', self.paper.size, 0)
        self.bg, self.pen = ImageDraw.Draw(self.paper), ImageDraw.Draw(self.ink)
        self.lines, self.fields, self.checks = [], [], []
        self.period = {'start': '2026-09-01', 'end': '2026-09-30'}

    def rect(self, box, fill=None, outline=None):
        self.bg.rectangle(tuple(int(v*S) for v in box), fill=fill, outline=outline, width=S)

    def rule(self, x1, y, x2):
        self.bg.line((x1*S, y*S, x2*S, y*S), fill='#adb5bd', width=S)

    def text(self, text, x, y, size=19, bold=False, right=False, key=None,
             value=None, unit=None, role='context', period=None, mono=False):
        font = ImageFont.truetype(str(font_path(mono, bold)), size*S)
        bbox0 = self.pen.textbbox((0, 0), text, font=font, anchor='lt')
        if right:
            x -= (bbox0[2]-bbox0[0])/S
        pos = (round(x*S), round(y*S))
        bbox = [v/S for v in self.pen.textbbox(pos, text, font=font, anchor='lt')]
        if not (0 <= bbox[0] <= bbox[2] < self.w and 0 <= bbox[1] <= bbox[3] < self.h):
            raise ValueError(f'Text out of bounds: {text}: {bbox}')
        self.pen.text(pos, text, font=font, fill=255, anchor='lt')
        line = {'line_id': f'l{len(self.lines)+1:03d}', 'text': text, 'bbox': bbox,
                'polygon': [[bbox[0],bbox[1]],[bbox[2],bbox[1]],[bbox[2],bbox[3]],[bbox[0],bbox[3]]]}
        self.lines.append(line)
        if key:
            self.fields.append({'field': key, 'value': value, 'unit': unit, 'role': role,
                                'period': period or self.period,
                                'evidence': [{'line_id': line['line_id'], 'text': text}]})
        return line

    def barcode(self, x, y, width, height):
        rng = np.random.default_rng(905+self.index)
        end = x+width
        while x < end-3:
            bw = int(rng.integers(1,4))
            self.rect([x,y,min(x+bw,end),y+height], fill='#444444')
            x += bw+int(rng.integers(2,5))

    def finish(self):
        return (self.paper.resize((self.w,self.h),Image.Resampling.LANCZOS),
                self.ink.resize((self.w,self.h),Image.Resampling.LANCZOS))

class Page(BasePage):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.period=CONTEXT['period']
    def text(self,text,x,y,size=19,bold=False,right=False,key=None,value=None,unit=None,
             role='context',period=None,mono=False):
        c=CONTEXT
        text=text.replace('(30 hari)',f'({(c["end"]-c["start"]).days+1} hari)')
        if self.category=='waste' and text in [': CARDBOARD',': GENERAL WASTE']:
            text=': '+c['material']
        for old,new in [('01/09/2026',dm(c['start'])),('30/09/2026',dm(c['end'])),
                        ('22/09/2026',dm(c['transaction'])),('02/10/2026',dm(c['issue'])),
                        ('01/11/2026',dm(c['due']))]:text=text.replace(old,new)
        text=text.replace('JUL 2026',c['history_months'][0]).replace('OGO 2026',c['history_months'][1])
        for old in ['KILANG REKAAN ANGSANA','KEDAI REKAAN ANGSANA','KEDAI REKAAN MERANTI']:
            text=text.replace(old,c['business'])
        if key=='reading_type':
            period={'start':None,'end':None}
        elif key=='amount_due':period=point(c['issue'])
        elif self.category=='water' and key in ['water_previous_reading','water_current_reading']:
            period=point(c['start'] if 'previous' in key else c['end'])
        else:period=c['period']
        if key=='treatment_route':
            route=c['route'];text=text.replace('RECYCLING',route.upper()).replace('LANDFILL',route.upper())
            value=route
        # The original API uses None as a no-field signal. Explicit temporal labels
        # are provided for every actual field, including contextual null periods.
        return super().text(text,x,y,size,bold,right,key,value,unit,role,period,mono)

def homography(source,destination):
    rows=[];values=[]
    for (x,y),(u,v) in zip(source,destination):
        rows.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]])
        values.extend([u,v])
    return np.append(np.linalg.solve(np.array(rows,float),np.array(values,float)),1).reshape(3,3)

def render_capture(page,profile,seed,text_effects=None):
    rng=np.random.default_rng(seed)
    paper,mask=page.finish();w,h=paper.size
    original=np.asarray(mask,float)
    region=np.zeros((h,w),bool);blend=np.zeros((h,w),float)
    for line in page.lines:
        x0,y0,x1,y1=[int(v) for v in line['bbox']]
        region[y0:y1+1,x0:x1+1]=True
        if profile=='clean' or rng.random()<.40:continue
        for _ in range(int(rng.integers(1,3))):
            length=min(x1-x0,int(rng.integers(12,55)))
            left=int(rng.integers(x0,max(x0+1,x1-length+1)))
            blend[y0:y1+1,left:left+length]=rng.uniform(.16,.42 if page.category=='waste' else .30)
    eroded=np.asarray(mask.filter(ImageFilter.MinFilter(3)),float)
    ink=original*(1-blend)+eroded*blend
    line_erosion={}
    random_lines=bool(text_effects and text_effects.get('erosion_mode')=='random_per_line_uniform')
    if profile!='clean' and text_effects:
        # White foreground ink: MinFilter erodes glyphs. A uniform blend gives
        # moderate thinning across the text instead of random strong patches.
        if random_lines:
            # Separate seeded stream preserves existing brightness and geometry.
            # Balanced strata give an exact unweighted mean strength of 0.30.
            lo,hi=text_effects['erosion_range']
            strengths=np.linspace(lo,hi,len(page.lines)) if len(page.lines)>1 else np.array([(lo+hi)/2])
            np.random.default_rng(seed+730019).shuffle(strengths)
            fractions=np.zeros_like(original)
            for line,strength in zip(page.lines,strengths):
                x0,y0,x1,y1=[int(v) for v in line['bbox']]
                fractions[y0:y1+1,x0:x1+1]=strength
                line_erosion[line['line_id']]=float(strength)
            ink=original*(1-fractions)+eroded*fractions
        else:
            fraction=text_effects['erosion_blend']
            ink=original*(1-fraction)+eroded*fraction
    drop_p=0 if profile=='clean' else (.009 if page.category=='waste' else .003)
    if random_lines:drop_p=0  # No random holes within a line: strength stays even.
    ink[(rng.random((h,w))<drop_p)&region]*=.30
    assert np.all(ink<=original+1e-5)
    if profile!='clean' and text_effects:
        # BoxBlur radius 1 is a 3x3 arithmetic-mean filter, applied to ink only.
        # Blending retains legibility. Rules, barcodes and paper are unaffected.
        blurred=np.asarray(Image.fromarray(np.uint8(ink)).filter(ImageFilter.BoxBlur(1)),float)
        fraction=text_effects['mean_blur_blend']
        ink=ink*(1-fraction)+blurred*fraction
    paperarray=np.asarray(paper,float)
    if profile!='clean':paperarray+=rng.normal(0,.7,(h,w,1))
    alpha=(ink/255)[:,:,None]
    image=Image.fromarray(np.uint8(np.clip(paperarray*(1-alpha)+35*alpha,0,255)))
    brightness=1 if profile=='clean' else float(rng.uniform(1.025,1.085))
    image=ImageEnhance.Brightness(image).enhance(brightness)
    image=ImageEnhance.Sharpness(image).enhance(1.0)
    H=np.eye(3)
    params={'seed':seed,'profile':profile,'erosion_kernel':3,'dropout_probability':drop_p,
            'brightness_factor':brightness,'sharpness_factor':1.0,'blur_sigma':0,
            'order':['localized_text_erosion','brightness_increase','fixed_sharpness','capture']}
    if profile!='clean' and text_effects:
        params.update({'text_erosion':'uniform moderate thinning','erosion_blend':text_effects['erosion_blend'],
            'blur_type':'arithmetic_mean_box','blur_kernel':[3,3],
            'mean_blur_blend':text_effects['mean_blur_blend'],'blur_sigma':None,
            'effects_scope':'text ink only; intended glyph boxes retained, filter footprint may extend 1px',
            'order':['uniform_text_erosion','ink_dropout','text_mean_blur','brightness_increase','fixed_sharpness','capture']})
        if random_lines:
            params.update({'text_erosion':'random strength per text line, uniform across each line',
                'erosion_mode':'random_per_line_uniform','erosion_range':text_effects['erosion_range'],
                'line_erosion':line_erosion,'mean_line_erosion':float(np.mean(list(line_erosion.values()))),
                'erosion_seed':seed+730019,
                'order':['random_per_line_uniform_erosion','text_mean_blur','brightness_increase','fixed_sharpness','capture']})
    if profile=='photo':
        # Perspective is modeled explicitly so evidence coordinates follow the page.
        margin=round(min(w,h)*.035)
        canvasw,canvash=w+2*margin,h+2*margin
        src=[(0,0),(w,0),(w,h),(0,h)]
        jitter=lambda:float(rng.uniform(-margin*.3,margin*.3))
        dst=[(margin+jitter(),margin+jitter()),(margin+w+jitter(),margin+jitter()),
             (margin+w+jitter(),margin+h+jitter()),(margin+jitter(),margin+h+jitter())]
        H=homography(src,dst)
        inverse=np.linalg.inv(H);inverse/=inverse[2,2]
        image=image.transform((canvasw,canvash),Image.Transform.PERSPECTIVE,tuple(inverse.flatten()[:8]),
                              resample=Image.Resampling.BICUBIC,fillcolor=(211,207,199))
        y,x=np.mgrid[:canvash,:canvasw]
        shadow=1-.075*(x/canvasw)-.025*np.exp(-((y-canvash*.48)/(canvash*.20))**2)
        tint=np.array([1.0,.985,.965]) if seed%2 else np.array([.96,.98,1.0])
        rgb=np.asarray(image,float)*shadow[:,:,None]*tint
        image=Image.fromarray(np.uint8(np.clip(rgb,0,255)))
        params.update({'page_corners':dst,'rgb_gain':tint.tolist(),'capture':'mild perspective, warm/cool light and gradient shadow'})
    elif profile=='scan':
        rgb=np.asarray(image,float)
        x=np.arange(w)[None,:,None]
        rgb*=1-.015*x/w
        image=Image.fromarray(np.uint8(np.clip(rgb,0,255)))
        params['capture']='neutral scan with subtle uneven exposure'
    params['forward_homography']=H.tolist()
    lines=[]
    for line in page.lines:
        pts=[]
        for x,y in line['polygon']:
            v=H@np.array([x,y,1]);pts.append([round(float(v[0]/v[2]),3),round(float(v[1]/v[2]),3)])
        assert all(0<=x<image.width and 0<=y<image.height for x,y in pts)
        lines.append({**line,'source_bbox':line['bbox'],'polygon':pts,
                      'bbox':[min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]})
    return image,params,lines
