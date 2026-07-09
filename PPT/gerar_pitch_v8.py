# -*- coding: utf-8 -*-
"""
GERADOR DO PITCH SGO ELETROELETRONICA - VERSAO 8
=================================================
Aplica, de forma cirurgica, os fundos animados + FX + correcao do Slide 5
sobre o arquivo-base da versao 6 (o conteudo do v6 e a fonte de verdade).

USO
    python3 gerar_pitch_v8.py [PASTA_ENTRADA] [ARQUIVO_SAIDA]

    PASTA_ENTRADA  (opcional) pasta com o v6.html + as 6 imagens.
                   Padrao: variavel de ambiente SGO_INPUT, senao a pasta do
                   proprio script, senao /app/uploads.
    ARQUIVO_SAIDA  (opcional) caminho do .html gerado.
                   Padrao: ./Pitch_Eletroeletronica_SGO_Premiumv8.html

ARQUIVOS DE ENTRADA ESPERADOS (na PASTA_ENTRADA)
    Pitch_Eletroeletronica_SGO_Premiumv6.html   <- base (conteudo ideal)
    bg_port.jpg  bg_yard.jpg  bg_prio.jpg  malha_map.png  fundo.png  baixada_patios.png

O gerado e um unico .html standalone (imagens embarcadas em base64).
Dependencia: Pillow (pre-instalado no ambiente).
"""
import base64, os, io, re, math, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("ERRO: Pillow ausente no ambiente Python.")

# ---- resolucao da pasta de entrada / saida --------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
def _pick_input():
    if len(sys.argv) > 1:
        return sys.argv[1]
    if os.environ.get('SGO_INPUT'):
        return os.environ['SGO_INPUT']
    if os.path.exists(os.path.join(_here, 'Pitch_Eletroeletronica_SGO_Premiumv6.html')):
        return _here
    return '/app/uploads'

UP  = _pick_input()
SRC = os.path.join(UP, 'Pitch_Eletroeletronica_SGO_Premiumv6.html')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(),
        'Pitch_Eletroeletronica_SGO_Premiumv8.html')

_need = ['Pitch_Eletroeletronica_SGO_Premiumv6.html', 'bg_port.jpg', 'bg_yard.jpg',
         'bg_prio.jpg', 'malha_map.png', 'fundo.png', 'baixada_patios.png']
_miss = [f for f in _need if not os.path.exists(os.path.join(UP, f))]
if _miss:
    sys.exit("ERRO: arquivos ausentes em '%s':\n  - %s" % (UP, "\n  - ".join(_miss)))
print("Entrada:", UP)

def b64(path, mime):
    with open(path, 'rb') as f:
        return 'data:%s;base64,%s' % (mime, base64.b64encode(f.read()).decode())

def map_jpg(path):
    im = Image.open(path).convert('RGB')
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=82, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()

A = {
    'bg_port': b64(os.path.join(UP, 'bg_port.jpg'), 'image/jpeg'),
    'bg_yard': b64(os.path.join(UP, 'bg_yard.jpg'), 'image/jpeg'),
    'bg_prio': b64(os.path.join(UP, 'bg_prio.jpg'), 'image/jpeg'),
    'malha':   b64(os.path.join(UP, 'malha_map.png'), 'image/png'),
    'fundo':   b64(os.path.join(UP, 'fundo.png'), 'image/png'),
    'baixada': map_jpg(os.path.join(UP, 'baixada_patios.png')),
}

html = open(SRC, encoding='utf-8').read()

# ---------------------------------------------------------------- COORDENADAS FIXAS
COORDS = {
 "FPI":[-23.444413,-46.309269],"IAA":[-23.862936,-46.398189],"IAB":[-23.521338,-46.688570],
 "IBA":[-23.907681,-46.325638],"ICB":[-23.886147,-46.416167],"ICG":[-23.767863,-46.343114],
 "ICP":[-23.658495,-46.490753],"ICQ":[-23.926493,-46.402720],"ICR":[-23.640310,-46.323992],
 "ICZ":[-23.954824,-46.293306],"IEF":[-23.477809,-46.360984],"IES":[-23.545441,-46.603648],
 "IIP":[-23.564977,-46.604896],"IJN":[-23.195297,-46.870829],"IJU":[-23.889626,-46.338534],
 "ILA":[-23.520217,-46.698082],"IMO":[-23.557803,-46.608382],"IOF":[-23.658579,-46.338538],
 "IPA":[-23.774399,-46.306769],"IPG":[-23.847950,-46.370812],"IPR":[-23.537749,-46.625522],
 "IQA":[-23.925948,-46.380123],"IQB":[-23.875674,-46.348587],"IRA":[-23.500572,-46.339448],
 "IRG":[-23.736705,-46.382241],"IRP":[-23.713578,-46.414862],"IRS":[-23.828162,-46.363101],
 "ISA":[-23.647553,-46.531007],"ISC":[-23.613874,-46.558834],"ISL":[-23.752383,-46.389262],
 "ISN":[-23.928399,-46.363015],"ISU":[-23.551210,-46.288671],"IUF":[-23.860615,-46.359726],
 "IUT":[-23.624864,-46.544716],"IVP":[-23.848139,-46.390430],"OAR":[-23.500419,-46.339111],
 "OBF":[-23.525591,-46.666726],"OBR":[-23.545397,-46.616293],"OCE":[-23.484980,-46.481471],
 "OCV":[-23.525061,-46.333701],"OEG":[-23.498082,-46.519759],"OET":[-23.510887,-46.552273],
 "OGP":[-23.691962,-46.448784],"OIC":[-23.479040,-46.367395],"OIT":[-23.493970,-46.401392],
 "OLU":[-23.535423,-46.634503],"OMA":[-23.667910,-46.462083],"OMP":[-23.490530,-46.443668],
 "OPS":[-23.637494,-46.537198],"OSU":[-23.534010,-46.308025],"OTA":[-23.591863,-46.590075],
 "OTT":[-23.539844,-46.575501],"ZPD":[-22.363436,-48.711002],"ZPG":[-23.874149,-46.411283],
}
CRIT = "IPA"          # ativo destacado (geofence / prioridade)
OFFMAP = ["ZPD"]      # fora do enquadramento da Baixada

frame = {c: v for c, v in COORDS.items() if c not in OFFMAP}
lats = [v[0] for v in frame.values()]; lons = [v[1] for v in frame.values()]
la0, la1 = min(lats), max(lats); lo0, lo1 = min(lons), max(lons)
xL, xR, yT, yB = 40.5, 95.0, 15.0, 90.0

def proj(lat, lon):
    nx = (lon - lo0) / (lo1 - lo0)
    ny = (la1 - lat) / (la1 - la0)   # norte para cima
    return xL + nx * (xR - xL), yT + ny * (yB - yT)

P = {c: proj(*v) for c, v in frame.items()}

# rotulos: critico + extremos geograficos + alguns espalhados
ext = {
    max(frame, key=lambda c: frame[c][0]): "N",   # mais ao norte
    min(frame, key=lambda c: frame[c][0]): "S",
    min(frame, key=lambda c: frame[c][1]): "O",    # oeste (lon menor)
    max(frame, key=lambda c: frame[c][1]): "L",
}
labelset = set(list(ext.keys()) + [CRIT, "OGP", "IES", "ICB"])

# linhas de rede: cada ponto liga ao vizinho mais proximo (projetado)
def px(c):
    x, y = P[c]; return x/100*1920, y/100*1080
edges = set()
codes = list(P.keys())
for a in codes:
    ax, ay = px(a); best = None; bd = 1e9
    for b in codes:
        if b == a: continue
        bx, by = px(b); d = math.hypot(ax-bx, ay-by)
        if d < bd: bd = d; best = b
    edges.add(tuple(sorted((a, best))))

svg_lines = []
for a, b in sorted(edges):
    ax, ay = px(a); bx, by = px(b)
    svg_lines.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f"/>' % (ax, ay, bx, by))
SVG_NET = '<svg class="cnet" viewBox="0 0 1920 1080" preserveAspectRatio="none">%s</svg>' % ''.join(svg_lines)

dots = []
for i, c in enumerate(codes):
    x, y = P[c]
    crit = (c == CRIT)
    color = 'var(--rail)' if crit else ('var(--gold)' if c in ext else 'var(--cyan)')
    cls = 'cpt' + ('' if (c in labelset) else ' sm')
    lab = ''
    if crit:
        lab = '<span class="clab"><b>%s</b><i>Ativo &middot; Muito Alta</i></span>' % c
    elif c in labelset:
        lab = '<span class="clab">%s</span>' % c
    dots.append('<div class="%s" style="left:%.2f%%;top:%.2f%%;--c:%s;--gd:%.2fs">%s</div>'
                % (cls, x, y, color, .35 + i*0.012, lab))

gfx, gfy = P[CRIT]
GEOFENCE = '<div class="geofence" style="left:%.2f%%;top:%.2f%%;"><span class="gf-tag">CERCA 2,0 KM</span></div>' % (gfx, gfy)

S5 = '''<section class="slide s5 has-photo">
  <div class="mapwrap"><div class="mapimg" style="background-image:url(%(malha)s)"></div>
    %(net)s
    %(geo)s
    %(dots)s
  </div>
  <div class="mappanel">
    <p class="kicker reveal left" style="--d:.05s">A Malha Real &middot; Baixada Santista</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da coordenada<br>ao <span class="grad">ativo</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s;max-width:560px;">Cada ativo eletroeletr&ocirc;nico &eacute; posicionado a partir das <b>coordenadas fixas</b> cadastradas (lat/lon reais). O <b>mesmo GPS</b> que roteiriza o t&eacute;cnico valida a baixa &mdash; dentro da <b>cerca de 2,0&nbsp;km</b> do ativo.</p>
    <div class="reveal up" style="--d:.34s;margin-top:22px;display:flex;flex-direction:column;gap:10px;">
      <span class="pill"><span class="d cyan"></span><b>Ativos</b> &middot; c&oacute;digo de 3 letras (FPI, IPA, OGP&hellip;)</span>
      <span class="pill"><span class="d gold"></span><b>Extremos da malha</b> &middot; N / S / L / O</span>
      <span class="pill"><span class="d rail"></span><b>%(crit)s</b> &middot; cerca de 2,0&nbsp;km &middot; geofencing</span>
    </div>
    <div class="reveal up" style="--d:.46s;margin-top:24px;display:flex;gap:38px;">
      <div class="stat"><b class="num" data-count="%(n)d" data-delay="300">0</b><span>ativos georreferenciados</span></div>
      <div class="stat"><b class="num" data-count="2.0" data-decimals="1" data-suffix=" km" data-delay="500">0</b><span>cerca por ativo</span></div>
      <div class="stat"><b class="num" data-count="100" data-suffix="%%" data-delay="700">0</b><span>GPS obrigat&oacute;rio</span></div>
    </div>
    <p class="reveal fade" style="--d:.6s;margin-top:16px;font-family:var(--mono);font-size:12px;color:var(--dim);">* ZPD (-22,36 / -48,71) fica fora do enquadramento da Baixada.</p>
  </div>
</section>''' % {
    'malha': A['malha'], 'net': SVG_NET, 'geo': GEOFENCE, 'dots': ''.join(dots),
    'crit': CRIT, 'n': len(COORDS),
}

# substitui a secao s5 inteira
html = re.sub(r'<section class="slide s5">.*?</section>', lambda m: S5, html, count=1, flags=re.S)

# ---------------------------------------------------------------- FX (linhas glow + faiscas)
_fxc = [0]
def fx(swap=False):
    _fxc[0] += 1; u = 'fx%d' % _fxc[0]
    a, b = ('gold', '') if not swap else ('', 'gold')
    return ('<div class="slide-fx" aria-hidden="true"><svg viewBox="0 0 1920 1080" preserveAspectRatio="none">'
      '<defs>'
      '<path id="%sA" d="M 1150 190 C 1300 360 1372 520 1452 662 C 1520 782 1576 868 1660 948"/>'
      '<path id="%sB" d="M 1020 560 C 1230 520 1392 566 1556 520 C 1716 476 1820 452 1900 420"/>'
      '<path id="%sC" d="M 1250 792 C 1356 826 1490 862 1650 892"/>'
      '<radialGradient id="%sg" cx="50%%" cy="50%%" r="50%%"><stop offset="0%%" stop-color="#fff"/><stop offset="38%%" stop-color="#ffd479"/><stop offset="100%%" stop-color="#ffd479" stop-opacity="0"/></radialGradient>'
      '<radialGradient id="%sc" cx="50%%" cy="50%%" r="50%%"><stop offset="0%%" stop-color="#fff"/><stop offset="38%%" stop-color="#39d6e8"/><stop offset="100%%" stop-color="#39d6e8" stop-opacity="0"/></radialGradient>'
      '</defs>'
      '<use href="#%sA" class="fxline %s"/>'
      '<use href="#%sB" class="fxline %s"/>'
      '<use href="#%sC" class="fxline dim"/>'
      '<circle r="5.5" fill="url(#%sg)" class="fxspark"><animateMotion dur="8.5s" repeatCount="indefinite" rotate="auto"><mpath href="#%sA"/></animateMotion></circle>'
      '<circle r="5" fill="url(#%sc)" class="fxspark"><animateMotion dur="11s" begin="-3s" repeatCount="indefinite"><mpath href="#%sB"/></animateMotion></circle>'
      '<circle r="4.5" fill="url(#%sg)" class="fxspark"><animateMotion dur="7s" begin="-1.6s" repeatCount="indefinite"><mpath href="#%sC"/></animateMotion></circle>'
      '</svg></div>') % (u,u,u,u,u, u,a, u,b, u, u,u, u,u, u,u)

# s1: FX sobre a foto
html = html.replace('<section class="slide s1">\n  <div class="s1-photo"><i></i></div>',
                    '<section class="slide s1 has-photo">\n  <div class="s1-photo"><i></i></div>\n  ' + fx())

# s9 (offline): foto bg_yard + FX
html = html.replace('<section class="slide s9">',
                    '<section class="slide s9 has-photo">\n  <div class="ambient strong" style="--img:url(%s)"></div>\n  %s' % (A['bg_yard'], fx(swap=True)))

# s15 (end): FX sobre a foto
html = html.replace('<div class="end-photo"><i></i></div>',
                    '<div class="end-photo"><i></i></div>\n  ' + fx())

# s6: baixada (rota real) como ambiente sutil E DESFOCADO (nomes queimados na imagem ficam ilegiveis)
html = html.replace('<section class="slide s6 imp">',
                    '<section class="slide s6 imp has-amb">\n  <div class="ambient blur" style="--img:url(%s)"></div>' % A['baixada'])

# s10: bg_prio (pontos conectando) como ambiente sutil
html = html.replace('<section class="slide s10">',
                    '<section class="slide s10 has-amb">\n  <div class="ambient" style="--img:url(%s)"></div>' % A['bg_prio'])

# s14: malha_map como ambiente sutil
html = html.replace('<section class="slide s14">',
                    '<section class="slide s14 has-amb">\n  <div class="ambient" style="--img:url(%s)"></div>' % A['malha'])

# ---------------------------------------------------------------- CSS EXTRA
EXTRA = '''
/* ====== v8: fundos animados + FX ====== */
.deck-stage::before{ content:""; position:absolute; inset:0; z-index:0; opacity:.42;
  background-image:url(%(fundo)s); background-size:cover; background-position:center; }
.netbg{ position:absolute; inset:0; z-index:1; pointer-events:none; }
.slide{ background:
  radial-gradient(1100px 760px at 6%% 0%%, rgba(243,177,60,.09) 0%%, transparent 56%%),
  radial-gradient(1200px 820px at 100%% 100%%, rgba(57,214,232,.09) 0%%, transparent 60%%),
  linear-gradient(160deg, rgba(6,18,39,.80) 0%%, rgba(4,10,22,.86) 55%%, rgba(3,6,15,.92) 100%%) !important; }
@keyframes kb{ 0%%{ transform:scale(1.05); } 100%%{ transform:scale(1.14) translate(-1.4%%,-1.2%%); } }
/* capa e encerramento passam a usar a foto do porto ferroviario */
.s1-photo i{ left:0 !important; right:0 !important; top:0 !important; width:100%% !important; height:100%% !important;
  background-image:url(%(bg_port)s) !important; mix-blend-mode:normal !important; opacity:.62 !important;
  animation:kb 32s ease-in-out infinite alternate; }
.s1-photo::after{ background:linear-gradient(90deg, var(--slide-bg) 20%%, rgba(4,10,22,.42) 54%%, transparent 100%%),
  linear-gradient(0deg, var(--slide-bg), transparent 42%%) !important; }
.end-photo i{ background-image:url(%(bg_port)s) !important; mix-blend-mode:normal !important; opacity:.5 !important;
  animation:kb 32s ease-in-out infinite alternate; }
/* ambiente sutil (fotos de apoio) */
.ambient{ position:absolute; inset:0; z-index:0; overflow:hidden; }
.ambient::before{ content:""; position:absolute; inset:-3%%; background-image:var(--img); background-size:cover;
  background-position:center; opacity:.16; animation:kb 34s ease-in-out infinite alternate; }
.ambient.strong::before{ opacity:.30; }
.ambient.blur::before{ filter:blur(5px) saturate(1.1); opacity:.22; }
.ambient::after{ content:""; position:absolute; inset:0;
  background:linear-gradient(160deg, rgba(4,10,22,.6), rgba(3,6,15,.72)); }
.ambient.strong::after{ background:linear-gradient(180deg, rgba(4,10,22,.62), rgba(3,6,15,.5) 40%%, rgba(3,6,15,.8)); }
/* camada FX: linhas com glow + faiscas viajando */
.slide-fx{ position:absolute; inset:0; z-index:1; pointer-events:none; }
.slide-fx svg{ width:100%%; height:100%%; overflow:visible; }
.fxline{ fill:none; stroke:var(--cyan); stroke-width:2; opacity:.42;
  filter:drop-shadow(0 0 6px var(--cyan)); stroke-dasharray:5 12; animation:fxdash 6s linear infinite; }
.fxline.gold{ stroke:var(--gold); filter:drop-shadow(0 0 6px var(--gold)); }
.fxline.dim{ opacity:.22; }
@keyframes fxdash{ to{ stroke-dashoffset:-170; } }
.fxspark{ filter:drop-shadow(0 0 6px #fff); }
/* dispersao de coordenadas (S5) */
.cnet{ position:absolute; inset:0; z-index:2; overflow:visible; }
.cnet line{ stroke:rgba(57,214,232,.28); stroke-width:1; }
.cpt{ position:absolute; width:13px; height:13px; border-radius:50%%; transform:translate(-50%%,-50%%); z-index:3;
  background:radial-gradient(circle,#fff 0%%,var(--c,var(--cyan)) 58%%,transparent 80%%);
  box-shadow:0 0 0 4px color-mix(in srgb, var(--c,var(--cyan)) 20%%, transparent), 0 0 12px var(--c,var(--cyan));
  opacity:0; transition:opacity .5s var(--ease); transition-delay:var(--gd,.3s); }
.slide.visible .cpt{ opacity:1; }
.cpt.sm{ width:8px; height:8px; box-shadow:0 0 0 3px color-mix(in srgb, var(--c,var(--cyan)) 16%%, transparent), 0 0 8px var(--c,var(--cyan)); }
.cpt .clab{ position:absolute; left:15px; top:50%%; transform:translateY(-50%%); white-space:nowrap;
  font-family:var(--mono); font-size:13px; letter-spacing:.06em; color:#fff; text-shadow:0 2px 8px #000; }
.cpt .clab b{ font-size:15px; } .cpt .clab i{ display:block; font-style:normal; font-size:10.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--rail); }
</style>'''
EXTRA = EXTRA % {'fundo': A['fundo'], 'bg_port': A['bg_port']}
html = html.replace('</style>', EXTRA, 1)

# ---------------------------------------------------------------- canvas + JS
html = html.replace('<div class="deck-viewport"><main class="deck-stage" id="deckStage">',
                    '<div class="deck-viewport"><main class="deck-stage" id="deckStage">\n<canvas class="netbg" id="netbg"></canvas>')

NET_JS = '''
const REDUCED_V8 = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function initNet(){
  const cv=document.getElementById('netbg'); if(!cv) return; const ctx=cv.getContext('2d');
  const W=1920,H=1080; cv.width=W; cv.height=H;
  const N=REDUCED_V8?0:66, MAX=175, cols=['57,214,232','243,177,60','155,123,255'];
  const pts=[]; for(let i=0;i<N;i++){ pts.push({x:Math.random()*W,y:Math.random()*H,
    vx:(Math.random()-.5)*.33,vy:(Math.random()-.5)*.33,r:Math.random()*1.7+1.1,
    c:cols[Math.floor(Math.random()*cols.length)]}); }
  function step(){ ctx.clearRect(0,0,W,H);
    for(let i=0;i<N;i++){ const p=pts[i]; p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>W)p.vx*=-1; if(p.y<0||p.y>H)p.vy*=-1; }
    for(let i=0;i<N;i++)for(let j=i+1;j<N;j++){ const a=pts[i],b=pts[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.hypot(dx,dy);
      if(d<MAX){ const o=(1-d/MAX)*.3; ctx.strokeStyle='rgba('+a.c+','+o.toFixed(3)+')'; ctx.lineWidth=.7;
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); } }
    for(let i=0;i<N;i++){ const p=pts[i]; ctx.fillStyle='rgba('+p.c+',.72)';
      ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,6.2832); ctx.fill(); }
    requestAnimationFrame(step); }
  if(N>0) step();
}
window.addEventListener('DOMContentLoaded',()=>{ initNet(); new Deck(); });'''
html = html.replace("window.addEventListener('DOMContentLoaded',()=>{ new Deck(); });", NET_JS, 1)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print('WROTE', OUT, '%.2f MB' % (len(html)/1024/1024))
print('S5 substituida:', '<section class="slide s5 has-photo">' in html)
print('sections:', html.count('<section'), '/', html.count('</section>'))
print('coord dots:', html.count('class="cpt'), 'labels:', len(labelset))
print('fx blocks:', html.count('slide-fx'))
