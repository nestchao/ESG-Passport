"""Optional procedural print wear, not calibrated to real aging or OCR difficulty."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def smooth_noise(rng,w,h,cell):
    # Coarse randomness becomes smoothly varying exposure over the page.
    small=rng.random((max(3,h//cell),max(3,w//cell)))
    im=Image.fromarray(np.uint8(small*255)).resize((w,h),Image.Resampling.BICUBIC)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(max(1,cell/9))),dtype=float)/255

def natural_wear(paper,mask,seed,profile,severity):
    if not 0 <= severity <= 1:
        raise ValueError('severity must be between zero and one')
    if profile not in ('thermal', 'printed'):
        raise ValueError('unknown print profile')
    rng=np.random.default_rng(seed)
    original=np.asarray(mask,dtype=float)/255
    h,w=original.shape
    fade=smooth_noise(rng,w,h,45)
    edge_variation=smooth_noise(rng,w,h,8)
    eroded=np.asarray(mask.filter(ImageFilter.MinFilter(3)),dtype=float)/255
    boundary=np.maximum(original-eroded,0)
    # Sparse clusters centre on actual ink, rather than independent pixel dropout.
    holes=Image.new('L',(w,h),0);draw=ImageDraw.Draw(holes)
    positions=np.argwhere(original>.15)
    centres=positions[rng.choice(len(positions),min(160,len(positions)),replace=False)]
    for y,x in centres:
        for _ in range(3):
            cx=x+rng.normal(0,1.4);cy=y+rng.normal(0,1.4)
            rx=rng.uniform(.4,1.5);ry=rng.uniform(.4,1.1)
            draw.ellipse((cx-rx,cy-ry,cx+rx,cy+ry),fill=int(rng.uniform(155,255)))
    holes=np.asarray(holes.filter(ImageFilter.GaussianBlur(.3)),float)/255
    yy,xx=np.mgrid[:h,:w]
    intercept=rng.uniform(.20,.80)*w;slope=rng.uniform(-.10,.10)
    fold=np.exp(-.5*((xx-intercept-slope*(yy-h/2))/rng.uniform(1.3,3.0))**2)
    thermal=profile=='thermal'
    # All severity levels share the exact same fields, so stronger wear only
    # removes more ink. Neither character shapes nor field values are invented.
    fade_loss=(.14+.92*fade) if thermal else (.06+.55*fade)
    worn=np.maximum(original-boundary*severity*(.15+.45*edge_variation),0)
    worn*=np.clip(1-severity*fade_loss,.08,1)
    worn*=1-severity*.88*holes
    worn*=1-severity*.55*fold
    assert np.all(worn<=original+1e-12)
    assert not np.any(worn[original==0])
    background=np.asarray(paper,dtype=float).copy()
    # Paper and print aging are distinct: warmth, fibres, crease shade and
    # broad thermal darkening belong to paper, not to removed glyph pixels.
    fibres=smooth_noise(rng,w,h,4)-.5
    heat=np.exp(-.5*(((xx-rng.uniform(.2,.8)*w)/(.22*w))**2+
                     ((yy-rng.uniform(.2,.8)*h)/(.18*h))**2))
    gain=np.stack([np.ones((h,w)),np.full((h,w),1-.012*severity),
                   np.full((h,w),1-.035*severity)],axis=2)
    if thermal:gain*=1-severity*heat[:,:,None]*np.array([.07,.09,.15])
    background*=gain*(1-.05*severity*fold[:,:,None])
    background+=fibres[:,:,None]*severity*2.4
    adjusted_paper=Image.fromarray(np.uint8(np.clip(background,0,255)))
    adjusted_ink=Image.fromarray(np.uint8(np.clip(worn*255,0,255)))
    active=original>.15
    neighbours=np.corrcoef(fade[:,:-1].ravel(),fade[:,1:].ravel())[0,1]
    params={'seed':seed,'print_profile':profile,'severity':severity,
      'fading':'smooth exposure field, nominal45px spatial scale',
      'stroke_damage':'edge-dependent wear plus160 small clusters of three ink-loss patches',
      'paper':'warmth, subtle fibres and crease shading; broad heat-like patch for thermal profile',
      'mean_ink_retention':float(worn[active].sum()/original[active].sum()),
      'fading_neighbour_correlation':float(neighbours),
      'not_calibrated':'Procedural visual approximation; no age-in-months or real-data distribution claim.',
      'limitations':'Text-mask wear only; printed barcodes/rules are not yet included in the ink-loss layer.'}
    return adjusted_paper,adjusted_ink,params,worn

class CapturePage:
    def __init__(self,page,paper,ink):self.page,self.paper,self.ink=page,paper,ink
    def __getattr__(self,name):return getattr(self.page,name)
    def finish(self):return self.paper.copy(),self.ink.copy()
