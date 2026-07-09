# -*- coding: utf-8 -*-
"""
Gerador do Pitch SGO Eletroeletronica MRS - 9 slides (arquivo unico standalone).
Fundos ANIMADOS + logo MRS (capa/canto) + LOGOS OFICIAIS da stack em plaquinhas brancas.
Uso:  python3 gerar_pitch_v10.py
Requisitos: Pillow + numpy  e as imagens na MESMA pasta do script:
  Fotos: fundo.png bg_yard.jpg bg_port.jpg malha_map.png baixada_dark2.png bg_prio.jpg
  Logos: logo_mrs.png  sap.png python.png fastapi.png streamlit.png postgre.png neon.png supabase.png render.png
Saida: SGO_Eletroeletronica_MRS_v10.html
"""
import base64, io, os
import numpy as np
from PIL import Image

IMG_DIR = os.environ.get("IMG_DIR", ".")
OUT     = "SGO_Eletroeletronica_MRS_v10.html"

def enc(fname, w, q):
    im = Image.open(os.path.join(IMG_DIR, fname)).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height*w/im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

def enc_png(fname, w):
    im = Image.open(os.path.join(IMG_DIR, fname)).convert("RGBA")
    bb = im.getbbox()
    if bb: im = im.crop(bb)
    if im.width > w:
        im = im.resize((w, round(im.height*w/im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

def enc_logo(fname, w=520):
    """Logo da stack -> fundo branco limpo (remove checker/transparencia) + trim."""
    im = Image.open(os.path.join(IMG_DIR, fname)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255,255,255,255))
    im = Image.alpha_composite(bg, im).convert("RGB")
    a = np.array(im)
    nw = (a[:,:,0]>=234)&(a[:,:,1]>=234)&(a[:,:,2]>=234)
    a[nw] = [255,255,255]
    im = Image.fromarray(a)
    arr = np.array(im)
    mask = ~((arr[:,:,0]==255)&(arr[:,:,1]==255)&(arr[:,:,2]==255))
    ys, xs = np.where(mask)
    if len(xs):
        p = 14
        im = im.crop((max(xs.min()-p,0), max(ys.min()-p,0),
                      min(xs.max()+p,im.width), min(ys.max()+p,im.height)))
    if im.width > w:
        im = im.resize((w, round(im.height*w/im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

imgs = {
    "fundo":   enc("fundo.png",         1920, 82),
    "yard":    enc("bg_yard.jpg",       1920, 80),
    "port":    enc("bg_port.jpg",       1920, 80),
    "const":   enc("malha_map.png",     1920, 80),
    "baixada": enc("baixada_dark2.png", 1468, 86),
    "prio":    enc("bg_prio.jpg",       1920, 80),
    "mrs":     enc_png("logo_mrs.png",  520),
}
for _n in ["sap","python","fastapi","streamlit","postgre","neon","supabase","render"]:
    imgs["l_"+_n] = enc_logo(_n+".png")

# ---------- icones genericos (nao-marca) recoloridos p/ plaquinha branca ----------
GLYPH = {
"https":'<svg viewBox="0 0 48 48"><rect x="11" y="21" width="26" height="19" rx="4" fill="none" stroke="#0A2540" stroke-width="3"/><path d="M16 21 V15 a8 8 0 0116 0 V21" fill="none" stroke="#0A2540" stroke-width="3"/><circle cx="24" cy="29" r="2.6" fill="#00A3C4"/><rect x="22.6" y="30" width="2.8" height="6" rx="1.4" fill="#00A3C4"/></svg>',
"gps":'<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="14" fill="none" stroke="#5B4BD6" stroke-width="3"/><circle cx="24" cy="24" r="4" fill="#5B4BD6"/><line x1="24" y1="4" x2="24" y2="12" stroke="#5B4BD6" stroke-width="3"/><line x1="24" y1="36" x2="24" y2="44" stroke="#5B4BD6" stroke-width="3"/><line x1="4" y1="24" x2="12" y2="24" stroke="#5B4BD6" stroke-width="3"/><line x1="36" y1="24" x2="44" y2="24" stroke="#5B4BD6" stroke-width="3"/></svg>',
"idb":'<svg viewBox="0 0 48 48"><g fill="none" stroke="#0E9F6E" stroke-width="3"><ellipse cx="24" cy="12" rx="14" ry="5"/><path d="M10 12 V36 a14 5 0 0028 0 V12"/><path d="M10 24 a14 5 0 0028 0"/></g></svg>',
}
def tile_img(key, rl):
    return f'<div class="tile"><div class="plate"><img src="{imgs[key]}" alt=""/></div><div class="rl">{rl}</div></div>'
def tile_glyph(name, rl):
    return f'<div class="tile"><div class="plate">{GLYPH[name]}</div><div class="rl">{rl}</div></div>'
def sap_inline():
    return f'<span class="saplg"><img src="{imgs["l_sap"]}" alt="SAP"/></span>'

HEAD = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>SGO Eletroeletrônica MRS — Inteligência Operacional Aplicada à Malha</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#040a16; --stage-bg:#02050c;
  --ink:#eef4ff; --mut:#aebfda; --dim:#6f83a6;
  --white:#eef4ff; --soft:#aebfda;
  --cyan:#39d6e8; --amber:#f3b13c; --green:#37e07e; --red:#ff465e; --violet:#9b7bff;
  --gold:#f3b13c; --gold-2:#ffd479; --teal:#1ea7b6; --blue:#3b82f6; --rail:#ff5a7e;
  --mrs:#E4002B; --line:rgba(120,160,220,.16); --panel:rgba(15,32,58,.42);
  --card:linear-gradient(155deg, rgba(15,32,58,.72), rgba(6,15,30,.5));
  --card-bd:rgba(120,160,220,.18); --shadow:0 24px 60px rgba(0,0,0,.5);
  --font:'Manrope',system-ui,sans-serif; --mono:'Space Mono',monospace;
  --ease:cubic-bezier(.16,1,.3,1);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:#000;color:#EAF2FF;color:var(--ink);font-family:'Manrope',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  overflow:hidden;-webkit-font-smoothing:antialiased}
.mono{font-family:'Space Mono','SF Mono',ui-monospace,monospace}

#viewport{position:fixed;inset:0;display:grid;place-items:center;background:#000;overflow:hidden}
#stage{position:relative;width:1920px;height:1080px;transform-origin:center center;
  background:#060a12;background:var(--bg);overflow:hidden;box-shadow:0 40px 160px rgba(0,0,0,.7)}

.slide{position:absolute;inset:0;opacity:0;visibility:hidden;transition:opacity .6s ease, visibility .6s;
  padding:96px 120px;display:flex;flex-direction:column;justify-content:center}
.slide.active{opacity:1;visibility:visible;z-index:2}

/* ---------- backgrounds + FX ---------- */
.bg{position:absolute;inset:0;z-index:0;overflow:hidden}
.bg img{position:absolute;inset:-4%;width:108%;height:108%;object-fit:cover;
  transform:scale(1.05);animation:kb 26s ease-in-out infinite alternate;will-change:transform}
@keyframes kb{0%{transform:scale(1.05) translate(0,0)}100%{transform:scale(1.16) translate(-18px,-14px)}}
.veil{position:absolute;inset:0;z-index:1}
.veil.left{background:linear-gradient(90deg,rgba(6,10,18,.96) 0%,rgba(6,10,18,.8) 32%,rgba(6,10,18,.32) 66%,rgba(6,10,18,.12) 100%)}
.veil.bottom{background:linear-gradient(180deg,rgba(6,10,18,.5) 0%,rgba(6,10,18,.14) 38%,rgba(6,10,18,.92) 100%)}
.veil.full{background:radial-gradient(120% 90% at 30% 24%,rgba(6,10,18,.5),rgba(6,10,18,.92))}
.vign{position:absolute;inset:0;z-index:1;pointer-events:none;
  box-shadow:inset 0 0 240px 40px rgba(0,0,0,.55);animation:breathe 9s ease-in-out infinite}
@keyframes breathe{0%,100%{opacity:.85}50%{opacity:1}}

.fx{position:absolute;inset:0;z-index:1;pointer-events:none;overflow:hidden}
.orb{position:absolute;border-radius:50%;filter:blur(72px);opacity:.55;mix-blend-mode:screen;
  animation:orbFloat 15s ease-in-out infinite;will-change:transform}
.orb.b{animation-duration:19s;animation-direction:reverse}
.orb.c{animation-duration:23s}
@keyframes orbFloat{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(38px,28px) scale(1.09)}}
.spot{position:absolute;border-radius:50%;transform:translate(-50%,-50%);mix-blend-mode:screen;
  background:radial-gradient(circle,#fff 0%,var(--sc,#00E5FF) 42%,transparent 72%);
  box-shadow:0 0 20px 5px var(--sc,#00E5FF);animation:spotPulse var(--sd,3.4s) ease-in-out infinite}
@keyframes spotPulse{0%,100%{opacity:.2;transform:translate(-50%,-50%) scale(.65)}
  50%{opacity:1;transform:translate(-50%,-50%) scale(1.3)}}
.sflow{position:absolute;inset:0;width:100%;height:100%}
.sflow .ln{fill:none;stroke:var(--fc,#00E5FF);stroke-width:2.4;opacity:.22;
  stroke-dasharray:2 12;stroke-linecap:round;filter:drop-shadow(0 0 6px var(--fc,#00E5FF));
  animation:dash 3.2s linear infinite}
@keyframes dash{to{stroke-dashoffset:-140}}
.sflow .sp{filter:drop-shadow(0 0 9px #fff)}
canvas.net{position:absolute;inset:0;z-index:0}
.slide>.wrap{position:relative;z-index:4;width:100%}

/* type */
.eyebrow{font-family:'Space Mono',monospace;letter-spacing:.42em;text-transform:uppercase;font-size:15px;
  color:var(--gold);display:flex;align-items:center;gap:14px;margin-bottom:22px}
.eyebrow::before{content:"";width:44px;height:2px;background:linear-gradient(90deg,var(--gold),transparent);
  box-shadow:0 0 12px var(--gold)}
h1{font-size:104px;line-height:.98;font-weight:800;letter-spacing:-.02em}
h2{font-size:60px;line-height:1.02;font-weight:800;letter-spacing:-.015em}
.grad{background:linear-gradient(100deg,var(--gold) 0%,var(--gold-2) 45%,var(--cyan) 100%);-webkit-background-clip:text;
  background-clip:text;color:transparent}
.lead{font-size:26px;line-height:1.5;color:var(--mut);font-weight:400;max-width:1180px}
.big{font-size:40px;line-height:1.3;font-weight:700;letter-spacing:-.01em}
.accent{color:var(--cyan)}.amber{color:var(--amber)}.green{color:var(--green)}.red{color:var(--red)}.violet{color:var(--violet)}

.badges{display:flex;flex-wrap:wrap;gap:14px;margin-top:40px}
.badge{display:inline-flex;align-items:center;gap:10px;padding:12px 20px;border-radius:999px;border:1px solid var(--line);
  background:var(--panel);font-size:16px;font-weight:600;backdrop-filter:blur(8px)}
.badge .dot{width:8px;height:8px;border-radius:50%;background:var(--cyan);box-shadow:0 0 12px var(--cyan);
  animation:spotPulse 2.6s ease-in-out infinite}

.cards{display:grid;gap:20px;margin-top:14px}
.card{border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:26px 28px;backdrop-filter:blur(10px);
  position:relative;overflow:hidden}
.card h3{font-size:23px;font-weight:700;margin:8px 0 8px}
.card p{font-size:16.5px;color:var(--mut);line-height:1.45}
.card .num{position:absolute;right:18px;top:6px;font-size:64px;font-weight:800;color:rgba(255,255,255,.06);font-family:'Space Mono',monospace}
.card .ico{font-size:30px;margin-bottom:10px;display:block}

.flow{display:flex;align-items:stretch;gap:0;margin-top:26px}
.node{flex:1;border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:24px 22px;position:relative;backdrop-filter:blur(8px)}
.node .t{font-family:'Space Mono',monospace;font-size:13px;letter-spacing:.14em;color:var(--cyan);text-transform:uppercase}
.node h4{font-size:22px;font-weight:800;margin:10px 0 12px}
.node ul{list-style:none}
.node li{font-size:15px;color:var(--mut);line-height:1.7;padding-left:16px;position:relative}
.node li::before{content:"";position:absolute;left:0;top:11px;width:6px;height:6px;border-radius:50%;background:var(--cyan);opacity:.8}
.arrow{display:flex;align-items:center;justify-content:center;width:56px;flex:0 0 56px;font-size:30px;color:var(--cyan);
  opacity:.85;animation:arr 1.8s ease-in-out infinite}
@keyframes arr{0%,100%{transform:translateX(0);opacity:.6}50%{transform:translateX(6px);opacity:1}}
.node.hl{border-color:rgba(0,229,255,.45);background:linear-gradient(180deg,rgba(0,229,255,.10),rgba(255,255,255,.03))}
.node.mrs{border-color:rgba(228,0,43,.5)}
.node.mrs .t{color:var(--mrs)}.node.mrs li::before{background:var(--mrs)}

.two{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:22px}
.panel{border:1px solid var(--line);background:var(--panel);border-radius:20px;padding:32px 34px;backdrop-filter:blur(10px)}
.panel .head{display:flex;align-items:center;gap:14px;margin-bottom:20px}
.panel .head .tag{font-family:'Space Mono',monospace;font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.panel .head .ico{font-size:32px}
.panel h3{font-size:28px;font-weight:800}
.list{list-style:none;display:grid;gap:12px}
.list li{font-size:17.5px;color:#d7e4f5;line-height:1.35;padding-left:30px;position:relative}
.list li::before{content:"\2713";position:absolute;left:0;top:1px;color:var(--green);font-weight:800}
.list.steps li::before{content:"\2192";color:var(--cyan)}

.casc{display:grid;gap:12px;margin-top:20px;max-width:1180px}
.prow{display:flex;align-items:center;gap:20px}
.prow .rk{width:44px;height:44px;flex:0 0 44px;border-radius:12px;display:grid;place-items:center;font-weight:800;font-size:20px;font-family:'Space Mono',monospace}
.prow .bar{height:44px;border-radius:12px;display:flex;align-items:center;padding:0 22px;font-size:20px;font-weight:700;color:#04121a;white-space:nowrap;
  box-shadow:0 6px 26px rgba(0,0,0,.35)}
.prow .meta{font-size:15px;color:var(--mut)}

.road{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:22px}
.rcol{border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:22px 22px;backdrop-filter:blur(8px)}
.rcol .ph{font-family:'Space Mono',monospace;font-size:13px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px}
.rcol .yr{font-size:20px;font-weight:800;margin-bottom:14px}
.rcol ul{list-style:none;display:grid;gap:9px}
.rcol li{font-size:15px;color:var(--mut);line-height:1.3;padding-left:16px;position:relative}
.rcol li::before{content:"";position:absolute;left:0;top:9px;width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.7}

.chips{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;max-width:1180px}
.chip{display:inline-flex;align-items:center;gap:9px;padding:12px 18px;border-radius:12px;border:1px solid var(--line);background:var(--panel);font-size:16px;font-weight:600}
.chip b{color:var(--cyan);font-family:'Space Mono',monospace;font-weight:700;font-size:14px}

.mcards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:24px}
.mcard{border:1px solid var(--line);background:rgba(6,10,18,.62);border-radius:16px;padding:20px 22px;backdrop-filter:blur(6px)}
.mcard .ic{font-size:26px}
.mcard h4{font-size:19px;font-weight:700;margin:8px 0 5px}
.mcard p{font-size:14.5px;color:var(--mut);line-height:1.4}

.demo{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:22px}
.dstep{border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:22px;backdrop-filter:blur(8px);position:relative}
.dstep .n{font-family:'Space Mono',monospace;font-size:15px;color:var(--cyan);font-weight:700}
.dstep h4{font-size:19px;font-weight:700;margin-top:10px}
.dstep p{font-size:14px;color:var(--mut);margin-top:6px;line-height:1.4}

.footline{margin-top:30px;font-size:22px;font-weight:600;color:#cfe0f5;border-left:3px solid var(--cyan);padding-left:22px;line-height:1.4;max-width:1200px}

/* logos */
#brand .blogo{height:26px;width:auto;filter:drop-shadow(0 0 7px rgba(120,180,255,.55))}
.herologo{margin-bottom:24px;display:inline-flex;align-items:center;gap:20px}
.herologo img{height:104px;width:auto;filter:drop-shadow(0 0 26px rgba(120,180,255,.35))}
.herologo .hl-txt{font-family:'Space Mono',monospace;font-size:13px;letter-spacing:.24em;text-transform:uppercase;
  color:var(--mut);border-left:1px solid var(--line);padding-left:20px;line-height:1.5}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:18px;margin-top:16px}
.tile{border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:16px 14px;backdrop-filter:blur(10px);
  display:flex;flex-direction:column;align-items:center;text-align:center;gap:12px;position:relative;overflow:hidden}
.tile::after{content:"";position:absolute;left:0;right:0;top:0;height:2px;background:linear-gradient(90deg,transparent,var(--cyan),transparent);opacity:.45}
.tile .plate{width:100%;height:78px;background:#fff;border-radius:12px;display:flex;align-items:center;justify-content:center;
  padding:14px 16px;box-shadow:0 6px 22px rgba(0,0,0,.28)}
.tile .plate img{max-height:100%;max-width:100%;width:auto;object-fit:contain;display:block}
.tile .plate svg{height:46px;width:auto;display:block}
.tile .rl{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.node .saplg{display:inline-flex;background:#fff;border-radius:6px;padding:5px 9px;margin-top:8px;box-shadow:0 4px 14px rgba(0,0,0,.3)}
.node .saplg img{height:20px;width:auto;display:block}
.hostnote{margin-top:16px;font-family:'Space Mono',monospace;font-size:14px;letter-spacing:.06em;color:var(--mut)}
.hostnote b{color:var(--mrs)}
#progress{position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--cyan),var(--violet));z-index:60;transition:width .5s ease}
#dots{position:fixed;bottom:26px;left:50%;transform:translateX(-50%);display:flex;gap:12px;z-index:60}
#dots .d{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.22);cursor:pointer;transition:.3s}
#dots .d.on{background:var(--cyan);width:26px;border-radius:6px;box-shadow:0 0 12px var(--cyan)}
#counter{position:fixed;bottom:26px;right:34px;z-index:60;font-family:'Space Mono',monospace;font-size:14px;color:var(--mut)}
#counter b{color:var(--ink)}
.nav{position:fixed;top:50%;transform:translateY(-50%);z-index:60;width:52px;height:52px;border-radius:50%;border:1px solid var(--line);
  background:rgba(10,16,26,.6);color:var(--ink);font-size:22px;cursor:pointer;display:grid;place-items:center;backdrop-filter:blur(8px);transition:.25s}
.nav:hover{background:rgba(0,229,255,.16);border-color:var(--cyan)}
#prev{left:26px}#next{right:26px}
#brand{position:fixed;top:26px;left:34px;z-index:60;display:flex;align-items:center;gap:12px;font-weight:800;font-size:16px;letter-spacing:.02em}
#brand .b{width:26px;height:26px;border-radius:7px;background:linear-gradient(135deg,var(--mrs),#ff5a76);display:grid;place-items:center;font-size:14px;color:#fff}
#hint{position:fixed;top:30px;right:34px;z-index:60;font-family:'Space Mono',monospace;font-size:12px;color:var(--dim);opacity:.7}
@media print{#dots,#counter,.nav,#progress,#hint{display:none!important}
  #viewport{position:static;display:block}#stage{transform:none!important}
  .slide{opacity:1!important;visibility:visible!important;position:relative;page-break-after:always;height:1080px}}

/* ==================== v9.5 ported components (v8 style) ==================== */
.kicker{font-family:var(--mono);font-size:15px;letter-spacing:.26em;text-transform:uppercase;color:var(--gold);display:inline-flex;align-items:center;gap:14px;margin-bottom:14px}
.kicker::before{content:"";width:36px;height:2px;background:linear-gradient(90deg,var(--gold),transparent);box-shadow:0 0 12px var(--gold)}
.kicker.rail{color:var(--rail)}.kicker.rail::before{background:linear-gradient(90deg,var(--rail),transparent);box-shadow:0 0 12px var(--rail)}
.kicker.green{color:var(--green)}.kicker.green::before{background:linear-gradient(90deg,var(--green),transparent);box-shadow:0 0 12px var(--green)}
.kicker.cyan{color:var(--cyan)}.kicker.cyan::before{background:linear-gradient(90deg,var(--cyan),transparent);box-shadow:0 0 12px var(--cyan)}
.grad-gold{background:linear-gradient(100deg,var(--gold),var(--gold-2));-webkit-background-clip:text;background-clip:text;color:transparent}
.grad-cyan{background:linear-gradient(100deg,var(--cyan),var(--blue));-webkit-background-clip:text;background-clip:text;color:transparent}
.grad-green{background:linear-gradient(100deg,var(--green),var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
/* reveal */
.reveal{opacity:0;transform:translateY(18px);transition:opacity .7s var(--ease),transform .7s var(--ease);transition-delay:var(--d,0s)}
.reveal.left{transform:translateX(-28px)}.reveal.right{transform:translateX(28px)}.reveal.fade{transform:none}
.slide.active .reveal{opacity:1;transform:none}
/* radial matrix (slides 3 e 7) */
.matrix{position:relative;width:100%;height:560px;margin-top:10px}
.matrix svg.mlinks{position:absolute;inset:0;width:100%;height:100%;overflow:visible;z-index:1}
.mlink{stroke-width:1.5;fill:none;stroke-dasharray:var(--len,760);stroke-dashoffset:var(--len,760);transition:stroke-dashoffset 1.3s var(--ease);transition-delay:var(--md,.2s)}
.slide.active .mlink{stroke-dashoffset:0}
.mnode{position:absolute;transform:translate(-50%,-50%) scale(.6);opacity:0;transition:opacity .6s var(--ease),transform .6s var(--ease);transition-delay:var(--md,0s);display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center;z-index:3;width:210px}
.slide.active .mnode{opacity:1;transform:translate(-50%,-50%) scale(1)}
.morb{width:var(--sz,104px);height:var(--sz,104px);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:34px;color:var(--c,var(--cyan));
  background:radial-gradient(circle at 38% 32%,color-mix(in srgb,var(--c,var(--cyan)) 26%,rgba(8,18,34,.9)) 0%,rgba(6,14,28,.94) 70%);
  border:1.5px solid color-mix(in srgb,var(--c,var(--cyan)) 55%,transparent);
  box-shadow:0 0 34px -6px color-mix(in srgb,var(--c,var(--cyan)) 70%,transparent),inset 0 0 26px -10px color-mix(in srgb,var(--c,var(--cyan)) 80%,transparent);
  animation:orbFloat 6s ease-in-out infinite}
.mnode .mlabel{font-size:19px;font-weight:800;color:var(--white);line-height:1.15}
.mnode .msub{font-family:var(--mono);font-size:11.5px;letter-spacing:.12em;color:var(--dim);text-transform:uppercase}
.mnode.center{width:300px}
.mnode.center .morb{width:236px;height:236px;border-width:2px;flex-direction:column;
  box-shadow:0 0 70px -4px color-mix(in srgb,var(--c,var(--gold)) 60%,transparent),inset 0 0 50px -16px var(--c,var(--gold))}
.mnode.center .mtitle{font-size:34px;font-weight:800;color:var(--white);line-height:1.03;padding:0 14px}
.mnode.center .mtag{font-family:var(--mono);font-size:12.5px;letter-spacing:.18em;color:var(--c,var(--gold));margin-top:9px;text-transform:uppercase}
@keyframes orbFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
/* flow v7 (slide 4) */
.flow4{display:flex;align-items:stretch;justify-content:space-between;gap:6px;margin-top:52px}
.fnode{flex:1;display:flex;flex-direction:column;align-items:center;text-align:center;gap:14px;padding:28px 14px;border-radius:20px;background:var(--card);border:1px solid var(--card-bd);border-top:3px solid var(--c,var(--cyan));box-shadow:var(--shadow);position:relative}
.fnode .flogos{display:flex;gap:9px;align-items:center;justify-content:center;min-height:66px}
.fnode h4{font-size:21px;font-weight:800}
.fnode p{font-size:14.5px;color:var(--soft);line-height:1.36}
.fnode .fstep{position:absolute;top:-15px;left:50%;transform:translateX(-50%);width:30px;height:30px;border-radius:50%;background:var(--c,var(--cyan));color:#04141c;font-family:var(--mono);font-weight:700;font-size:15px;display:grid;place-items:center;box-shadow:0 0 16px var(--c,var(--cyan))}
.farr{align-self:center;color:var(--dim);font-size:30px;flex:none}
.logo-chip{width:62px;height:62px;display:grid;place-items:center;border-radius:15px;background:rgba(255,255,255,.95);box-shadow:0 10px 26px rgba(0,0,0,.4);padding:10px}
.logo-chip img{max-width:100%;max-height:100%;object-fit:contain;display:block}
/* imp-maps antes/agora v7 (slide 5) */
.imp-maps{display:flex;align-items:stretch;gap:22px;margin-top:26px}
.imp-map{flex:1;border-radius:20px;padding:22px 26px;position:relative}
.imp-map.atual{border:1px solid rgba(255,90,126,.34);background:linear-gradient(160deg,rgba(60,12,26,.5),rgba(6,14,28,.5))}
.imp-map.sol{border:1px solid rgba(57,214,232,.36);background:linear-gradient(160deg,rgba(8,44,58,.5),rgba(6,14,28,.5))}
.im-cap{display:flex;align-items:center;gap:10px;font-family:var(--mono);font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--soft);margin-bottom:14px}
.im-cap .d{width:9px;height:9px;border-radius:50%}
.im-cap .d.rail{background:var(--rail);box-shadow:0 0 8px var(--rail)}
.im-cap .d.cyan{background:var(--cyan);box-shadow:0 0 8px var(--cyan)}
.im-list{list-style:none;display:flex;flex-direction:column;gap:11px}
.im-list li{display:flex;align-items:center;gap:14px;font-size:16.5px;color:var(--white)}
.im-list .ic{width:34px;height:34px;flex:none;border-radius:10px;display:grid;place-items:center;font-size:16px}
.imp-map.atual .ic{color:var(--rail);background:rgba(255,90,126,.12);border:1px solid rgba(255,90,126,.3)}
.imp-map.sol .ic{color:var(--cyan);background:rgba(57,214,232,.12);border:1px solid rgba(57,214,232,.3)}
.im-foot{display:block;margin-top:16px;font-family:var(--mono);font-size:13px}
.imp-map.atual .im-foot{color:var(--rail)}.imp-map.sol .im-foot{color:var(--cyan)}
.imp-arrow{align-self:center;color:var(--cyan);font-size:30px;flex:none}
.imp-insight{margin-top:20px;font-size:19px;font-weight:600;color:#cfe0f5;border-left:3px solid var(--gold);padding-left:20px;line-height:1.4}
/* pulsing malha bg v6 (slide 8) */
.mapwrap{position:absolute;inset:0;z-index:0;overflow:hidden}
.mapimg{position:absolute;inset:0;background-size:cover;background-position:center;opacity:.42}
.mapwrap::after{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;
  background:linear-gradient(100deg,rgba(4,10,22,.94) 0%,rgba(4,10,22,.66) 34%,rgba(4,10,22,.4) 64%,rgba(4,10,22,.8) 100%),linear-gradient(0deg,rgba(4,10,22,.92),transparent 46%)}
.gmark{position:absolute;transform:translate(-50%,-50%);z-index:2}
.gmark .disc{width:13px;height:13px;border-radius:50%;background:radial-gradient(circle,#fff 0%,var(--c,var(--cyan)) 55%,transparent 78%);box-shadow:0 0 10px #fff,0 0 18px var(--c,var(--cyan));position:relative}
.gmark .disc::before{content:"";position:absolute;inset:-6px;border-radius:50%;border:1px solid var(--c,var(--cyan));opacity:.55;animation:gpulse 2.8s ease-out infinite;animation-delay:var(--gd,0s)}
@keyframes gpulse{0%{transform:scale(.6);opacity:.8}100%{transform:scale(2.8);opacity:0}}
/* end slide v8 (slide 9) */
.end-photo{position:absolute;inset:0;z-index:0}
.end-photo i{position:absolute;inset:0;background-size:cover;background-position:center;mix-blend-mode:screen;opacity:.30}
.end-photo::after{content:"";position:absolute;inset:0;background:radial-gradient(ellipse 72% 64% at 50% 48%,rgba(4,10,22,.5) 0%,rgba(4,10,22,.3) 48%,rgba(4,10,22,.74) 100%)}
.slide-fx{position:absolute;inset:0;z-index:1;pointer-events:none}
.slide-fx svg{width:100%;height:100%;overflow:visible}
.fxline{fill:none;stroke:var(--cyan);stroke-width:2;opacity:.4;filter:drop-shadow(0 0 6px var(--cyan));stroke-dasharray:5 12;animation:fxdash 6s linear infinite}
.fxline.gold{stroke:var(--gold);filter:drop-shadow(0 0 6px var(--gold))}
.fxspark{filter:drop-shadow(0 0 6px #fff)}
@keyframes fxdash{to{stroke-dashoffset:-170}}
.endchain{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-top:26px;font-size:26px;font-weight:800}
.endchain .sep{color:var(--dim);font-weight:400}
.thanks{margin-top:40px;font-family:var(--mono);font-size:40px;font-weight:700;letter-spacing:.04em;color:var(--white)}
</style>
</head>
<body>
<div id="progress" style="width:11%"></div>
<div id="brand"><img class="blogo" src="__MRS__" alt="MRS"/> <span>SGO · Eletroeletrônica</span></div>
<div id="hint">← → navegar · F fullscreen</div>
<div id="viewport"><div id="stage">
"""

def fx(spots=None, sparks=None, orbA="rgba(0,229,255,.16)", orbB="rgba(155,140,255,.14)", orbC=None):
    h = '<div class="fx">'
    h += f'<div class="orb" style="width:560px;height:560px;background:{orbA};left:-120px;top:-150px"></div>'
    h += f'<div class="orb b" style="width:620px;height:620px;background:{orbB};right:-170px;bottom:-210px"></div>'
    if orbC:
        h += f'<div class="orb c" style="width:440px;height:440px;background:{orbC};right:22%;top:-160px"></div>'
    if sparks:
        h += '<svg class="sflow" viewBox="0 0 1920 1080" preserveAspectRatio="none">'
        for path, c, dur in sparks:
            h += f'<path class="ln" d="{path}" style="--fc:{c}"/>'
        for path, c, dur in sparks:
            h += f'<circle class="sp" r="5.5" fill="#fff"><animateMotion dur="{dur}s" repeatCount="indefinite" path="{path}"/></circle>'
            h += f'<circle class="sp" r="4" fill="{c}"><animateMotion dur="{dur}s" begin="-{dur/2:.2f}s" repeatCount="indefinite" path="{path}"/></circle>'
        h += '</svg>'
    if spots:
        for x, y, c, d, s in spots:
            h += f'<span class="spot" style="left:{x}%;top:{y}%;--sc:{c};--sd:{d}s;width:{s}px;height:{s}px"></span>'
    h += '</div>'
    return h

def photo(src, veil, fxhtml, net=False):
    n = '<canvas class="net"></canvas>' if net else ''
    return f'<div class="bg"><img src="{src}" alt=""/></div><div class="veil {veil}"></div><div class="vign"></div>{fxhtml}{n}'

def netbg(fxhtml):
    return f'<canvas class="net"></canvas><div class="veil full"></div><div class="vign"></div>{fxhtml}'

CY="#00E5FF"; AM="#FFB020"; VI="#9B8CFF"; GR="#37E39A"; WH="#dbeeff"

# ---- v9.5 componentes portados ----
import math
GOLD="#f3b13c"; CYAN="#39d6e8"; GREEN="#37e07e"; RAIL="#ff5a7e"; BLUE="#3b82f6"; VIO="#9b7bff"; REDX="#ff465e"; TEAL="#1ea7b6"

def matrix(center, nodes, rx=0.315, ry=0.345):
    W, H = 1680.0, 560.0
    cx, cy = W*0.5, H*0.5
    n = len(nodes)
    pts = []
    for k in range(n):
        ang = math.radians(-90 + k*(360.0/n))
        px = cx + rx*W*math.cos(ang)
        py = cy + ry*H*math.sin(ang)
        pts.append((px, py, nodes[k]))
    links = ""
    for k, (px, py, nd) in enumerate(pts):
        links += (f'<line class="mlink" x1="{cx:.0f}" y1="{cy:.0f}" x2="{px:.0f}" y2="{py:.0f}" '
                  f'stroke="{nd[2]}" style="--len:1200;--md:{0.3+k*0.07:.2f}s"/>')
    svg = f'<svg class="mlinks" viewBox="0 0 1680 560" preserveAspectRatio="none">{links}</svg>'
    ctitle, ctag, ccol = center
    h = (f'<div class="mnode center" style="left:50%;top:50%;--c:{ccol};--md:.1s">'
         f'<div class="morb"><div class="mtitle">{ctitle}</div><div class="mtag">{ctag}</div></div></div>')
    for k, (px, py, nd) in enumerate(pts):
        label, sub, col, icon = nd
        h += (f'<div class="mnode" style="left:{px/W*100:.2f}%;top:{py/H*100:.2f}%;--c:{col};--md:{0.55+k*0.08:.2f}s">'
              f'<div class="morb">{icon}</div><div class="mlabel">{label}</div><div class="msub">{sub}</div></div>')
    return f'<div class="matrix">{svg}{h}</div>'

def fnode(step, title, sub, color, logokeys, delay):
    logos = "".join(f'<div class="logo-chip"><img src="{imgs[k]}" alt=""/></div>' for k in logokeys)
    return (f'<div class="fnode reveal" style="--c:{color};--d:{delay:.2f}s">'
            f'<div class="fstep">{step}</div><div class="flogos">{logos}</div>'
            f'<h4>{title}</h4><p>{sub}</p></div>')

slides = []

# S1 — CAPA (fundo: trem wireframe centro)
s1_spots=[(52,30,CY,3.2,14),(58,44,WH,3.8,11),(46,54,CY,4.2,10),(64,49,VI,3.6,9),(41,26,AM,4.6,8),(70,58,CY,4.0,8)]
s1_sparks=[("M 300 780 Q 660 560 1050 470 Q 1380 396 1740 300",CY,6.5),
           ("M 560 250 Q 720 356 900 470",AM,5.2)]
slides.append(f"""
<section class="slide active" data-t="Abertura">
  {photo(imgs['fundo'],'left',fx(s1_spots,s1_sparks,"rgba(0,229,255,.18)","rgba(155,140,255,.14)"))}
  <div class="wrap">
    <div class="herologo"><img src="__MRS__" alt="MRS"/><span class="hl-txt">Malha<br/>Regional<br/>Sudeste</span></div>
    <div class="eyebrow">SGO · Sistema de Gestão Operacional</div>
    <h1><span class="grad">SGO Eletroeletrônica<br/>MRS</span></h1>
    <p class="big" style="margin-top:26px">Inteligência Operacional Aplicada à Malha</p>
    <p class="lead" style="margin-top:18px">Conecta <b class="accent">SAP</b>, ativos ferroviários, geolocalização,
      execução em campo, evidências e governança em uma <b>única camada digital</b>.</p>
    <div class="badges">
      <span class="badge"><span class="dot"></span>Roteirização</span>
      <span class="badge"><span class="dot"></span>GPS obrigatório</span>
      <span class="badge"><span class="dot"></span>PWA offline</span>
      <span class="badge"><span class="dot"></span>Evidência fotográfica</span>
      <span class="badge"><span class="dot"></span>Governança</span>
    </div>
  </div>
</section>""")

# S2 — PROBLEMA (yard: fileira de luzes no topo)
s2_spots=[(10,20,WH,3.0,12),(19,19,CY,3.6,10),(28,21,VI,3.2,11),(37,19,WH,3.8,12),(47,20,AM,3.0,10),
          (57,19,CY,3.4,11),(67,21,VI,3.6,10),(77,19,WH,3.0,12),(87,20,CY,3.8,10),(93,22,AM,3.2,9),
          (14,40,AM,4.2,8),(34,41,AM,3.6,7),(53,40,AM,4.0,8),(72,41,AM,3.4,7),(88,40,AM,4.4,8)]
slides.append(f"""
<section class="slide" data-t="O Problema">
  {photo(imgs['yard'],'left',fx(s2_spots,None,"rgba(0,229,255,.14)","rgba(255,176,32,.14)"))}
  <div class="wrap">
    <div class="eyebrow">O Problema da Operação em Malha</div>
    <h2>Cada manutenção exige <span class="accent">cinco decisões<br/>simultâneas</span></h2>
    <div class="cards" style="grid-template-columns:repeat(5,1fr);margin-top:34px">
      <div class="card"><span class="num">01</span><span class="ico">🧩</span><h3>Ativos</h3><p>Conhecer o equipamento e sua função na malha.</p></div>
      <div class="card"><span class="num">02</span><span class="ico">🗺️</span><h3>Geografia</h3><p>Saber onde está e como chegar ao ponto.</p></div>
      <div class="card"><span class="num">03</span><span class="ico">⚡</span><h3>Prioridade</h3><p>O que atacar primeiro sem improviso.</p></div>
      <div class="card"><span class="num">04</span><span class="ico">📋</span><h3>Aderência</h3><p>Executar conforme o planejamento.</p></div>
      <div class="card"><span class="num">05</span><span class="ico">📸</span><h3>Comprovação</h3><p>Provar o que foi efetivamente feito.</p></div>
    </div>
    <p class="footline" style="margin-top:34px">Hoje, parte dessa inteligência ainda depende da <b class="amber">experiência individual</b>.
      O SGO transforma essa experiência em <b class="accent">regra sistêmica</b>.</p>
  </div>
</section>""")

# S3 — O QUE E (port: telas holograficas esq + neon trem centro + lua)
s3_spots=[(15,50,CY,3.0,12),(21,58,CY,3.6,10),(11,46,CY,3.2,9),(28,52,CY,3.8,9),
          (54,44,VI,3.2,11),(60,50,CY,3.6,10),(50,52,CY,3.0,9),(66,54,VI,4.0,8),
          (92,12,WH,4.4,7),(84,66,AM,3.4,8)]
s3_sparks=[("M 300 980 Q 800 830 1200 700 Q 1470 612 1740 540",CY,6.6),
           ("M 720 430 Q 900 470 1080 520",VI,5.4)]
slides.append(f"""
<section class="slide" data-t="O Que é o SGO">
  {photo(imgs['port'],'left',fx(s3_spots,s3_sparks,"rgba(0,229,255,.16)","rgba(155,140,255,.16)"))}
  <div class="wrap" style="text-align:center">
    <div class="kicker" style="margin-left:auto;margin-right:auto">O Que é o SGO</div>
    <h2 style="font-size:52px">Não é um apontador de OS. <span class="grad">É um mecanismo de decisão.</span></h2>
    {matrix(
      ("SGO", "Núcleo de decisão", GOLD),
      [
        ("Organiza execução", "Sequência ótima", CYAN, "🎯"),
        ("Prioriza crítico", "Sem improviso", RAIL, "⚡"),
        ("Roteiriza", "Por proximidade", TEAL, "🧭"),
        ("Integra ao SAP", "Retorno estruturado", BLUE, "🔁"),
        ("Registra evidências", "Foto · GPS · hora", GREEN, "📷"),
        ("Padroniza a prática", "Auditável", VIO, "🛡️"),
      ])}
    <p class="footline" style="max-width:1240px;margin:8px auto 0;text-align:left">O SGO transforma
      <b class="amber">conhecimento tácito de campo</b> em regra operacional
      <b class="accent">padronizada, auditável e reproduzível</b>.</p>
  </div>
</section>""")

# S4 — FLUXO (const: constelacao) sparks diagonais + net
s4_spots=[(20,20,CY,3.4,9),(44,24,WH,3.8,8),(63,16,CY,3.2,9),(74,12,AM,4.0,8),
          (58,45,CY,3.6,9),(80,40,VI,3.4,8),(70,72,CY,3.8,8),(88,82,AM,4.2,7)]
s4_sparks=[("M 200 210 Q 720 400 1200 350 Q 1600 320 1860 500",CY,8.0),
           ("M 1860 900 Q 1300 760 800 820 Q 400 860 120 720",VI,9.0)]
slides.append(f"""
<section class="slide" data-t="Fluxo Ponta a Ponta">
  {photo(imgs['const'],'full',fx(s4_spots,s4_sparks,"rgba(0,229,255,.16)","rgba(155,140,255,.14)"),net=True)}
  <div class="wrap">
    <div class="eyebrow">Fluxo Ponta a Ponta</div>
    <h2>Do <span class="grad">planejamento</span> ao <span class="grad">retorno ao SAP</span></h2>
    <div class="flow4">
      {fnode('1','SAP','OS programadas e plano de manutenção.',GOLD,['l_sap'],0.15)}
      <div class="farr reveal" style="--d:.25s">➜</div>
      {fnode('2','Motor SGO','Priorização, regras, geografia e governança.',CYAN,['l_python','l_fastapi'],0.30)}
      <div class="farr reveal" style="--d:.40s">➜</div>
      {fnode('3','Campo','GPS, foto, modo offline e baixa da OS.',GREEN,['l_streamlit'],0.45)}
      <div class="farr reveal" style="--d:.55s">➜</div>
      {fnode('4','Banco / Evidências','Histórico auditável e storage de fotos.',VIO,['l_postgre','l_neon'],0.60)}
      <div class="farr reveal" style="--d:.70s">➜</div>
      {fnode('5','Retorno SAP','IW47, baixas em massa e dados estruturados.',RAIL,['l_sap'],0.75)}
    </div>
    <p class="footline reveal" style="--d:.9s;margin-top:44px">Uma linha contínua: <b class="accent">SAP → Motor SGO → Campo → Evidências → SAP</b>.</p>
  </div>
</section>""")

# S5 — MALHA (baixada: rota real) faisca viaja a rota + pátios pulsando
s5_spots=[(90,11,CY,3.0,13),(66,22,CY,3.4,11),(26,39,CY,3.2,11),(70,84,CY,3.6,12),(55,63,AM,3.4,10),(14,38,CY,4.0,9)]
s5_sparks=[("M 1674 128 Q 1360 231 1180 300 Q 1000 380 900 470 Q 760 610 700 940",CY,7.2),
           ("M 900 470 Q 620 430 523 420 Q 380 434 300 470",CY,6.0)]
slides.append(f"""
<section class="slide" data-t="Inteligência Aplicada à Malha">
  {photo(imgs['baixada'],'bottom',fx(s5_spots,s5_sparks,"rgba(0,229,255,.14)","rgba(0,229,255,.10)"))}
  <div class="wrap">
    <div class="eyebrow">Inteligência Aplicada à Malha</div>
    <h2>A OS deixa de ser uma linha em planilha e vira um <span class="accent">ponto operacional da malha</span></h2>
    <div class="mcards" style="margin-top:18px">
      <div class="mcard"><span class="ic">📍</span><h4>Base geográfica</h4><p>Coordenadas por pátio / ativo em toda a malha.</p></div>
      <div class="mcard"><span class="ic">🎯</span><h4>Geofencing</h4><p>Cerca operacional de <b class="accent">2,0 km</b> do ativo.</p></div>
      <div class="mcard"><span class="ic">🛰️</span><h4>GPS obrigatório</h4><p>Validação pelo hardware do aparelho.</p></div>
    </div>
    <div class="imp-maps">
      <div class="imp-map atual reveal" style="--d:.15s">
        <div class="im-cap"><span class="d rail"></span>Antes · escolha manual</div>
        <ul class="im-list">
          <li><span class="ic">🧠</span>Decisão dependente da experiência individual</li>
          <li><span class="ic">📄</span>OS como linha solta em planilha</li>
          <li><span class="ic">🔀</span>Deslocamento sem sequência ótima</li>
        </ul>
        <span class="im-foot">Conhecimento tácito, não reproduzível</span>
      </div>
      <div class="imp-arrow reveal" style="--d:.3s">➜</div>
      <div class="imp-map sol reveal" style="--d:.45s">
        <div class="im-cap"><span class="d cyan"></span>Depois · roteirização geográfica</div>
        <ul class="im-list">
          <li><span class="ic">📐</span>Haversine: distância real técnico ↔ ativo</li>
          <li><span class="ic">🧲</span>Agrupamento por raio de atuação</li>
          <li><span class="ic">🛰️</span>GPS + geofencing validando a execução</li>
        </ul>
        <span class="im-foot">Regra sistêmica, padronizada e auditável</span>
      </div>
    </div>
    <p class="imp-insight reveal" style="--d:.6s">A mesma malha — agora lida como <b>geografia operacional</b>, não como lista.</p>
  </div>
</section>""")

# S6 — PRIORIZACAO (prio: nebulosa) twinkles nos bokeh
s6_spots=[(58,26,CY,3.0,13),(73,9,AM,3.6,11),(55,36,AM,3.2,10),(88,62,CY,3.8,12),(41,83,CY,3.4,11),(74,89,AM,3.0,10),(80,20,CY,4.0,9)]
slides.append(f"""
<section class="slide" data-t="Motor de Priorização">
  {photo(imgs['prio'],'left',fx(s6_spots,None,"rgba(155,140,255,.16)","rgba(255,176,32,.14)"))}
  <div class="wrap">
    <div class="eyebrow">Motor de Priorização Operacional</div>
    <h2>Decisão <span class="accent">sistêmica</span>, não improviso</h2>
    <div class="casc">
      <div class="prow"><div class="rk" style="background:rgba(255,59,78,.16);color:var(--red)">1</div>
        <div class="bar" style="width:100%;background:linear-gradient(90deg,#FF3B4E,#ff7a86)">Segurança / Confiabilidade</div>
        <div class="meta">nível máximo</div></div>
      <div class="prow"><div class="rk" style="background:rgba(255,176,32,.16);color:var(--amber)">2</div>
        <div class="bar" style="width:84%;background:linear-gradient(90deg,#FFB020,#ffd07a)">Criticidade</div></div>
      <div class="prow"><div class="rk" style="background:rgba(155,140,255,.16);color:var(--violet)">3</div>
        <div class="bar" style="width:68%;background:linear-gradient(90deg,#9B8CFF,#c3b9ff)">Atraso ou vencimento</div></div>
      <div class="prow"><div class="rk" style="background:rgba(0,229,255,.16);color:var(--cyan)">4</div>
        <div class="bar" style="width:52%;background:linear-gradient(90deg,#00E5FF,#7ef0ff)">Tipo de intervalo</div></div>
      <div class="prow"><div class="rk" style="background:rgba(55,227,154,.16);color:var(--green)">5</div>
        <div class="bar" style="width:38%;background:linear-gradient(90deg,#37E39A,#9af0c7)">Proximidade geográfica</div></div>
    </div>
    <p class="footline">OS <b class="red">críticas</b> bloqueiam as inferiores do mesmo grupo —
      que permanecem <b class="accent">visíveis</b> (sombreadas + 🔒), nunca ocultas.</p>
  </div>
</section>""")

# S7 — GOVERNANCA + OFFLINE (net) orbs + spots + sparks
s7_spots=[(24,22,GR,3.2,9),(78,18,CY,3.6,9),(66,68,CY,3.4,8),(30,74,GR,3.8,8),(88,52,VI,3.4,8)]
s7_sparks=[("M 120 240 Q 620 180 960 300 Q 1300 420 1820 320",CY,8.5)]
slides.append(f"""
<section class="slide" data-t="Governança &amp; Continuidade">
  {netbg(fx(s7_spots,s7_sparks,"rgba(55,227,154,.14)","rgba(0,229,255,.14)"))}
  <div class="wrap" style="text-align:center">
    <div class="kicker green" style="margin-left:auto;margin-right:auto">Governança &amp; Continuidade Operacional</div>
    <h2 style="font-size:50px">Cada baixa nasce <span class="grad-green">rastreável</span> — com sinal e sem ele</h2>
    {matrix(
      ("Governança", "Trilha auditável", GREEN),
      [
        ("Login controlado", "Acesso seguro", CYAN, "🔐"),
        ("Perfis de acesso", "Papel definido", BLUE, "👤"),
        ("Registro de acessos", "Quem · quando", VIO, "🗒️"),
        ("GPS obrigatório", "Hardware valida", GOLD, "🛰️"),
        ("Evidência fotográfica", "Prova do serviço", RAIL, "📷"),
        ("Geofencing 2,0 km", "Cerca do ativo", TEAL, "🎯"),
        ("Histórico auditável", "Reproduzível", GREEN, "📚"),
        ("PWA offline", "Sync sem duplicar", CYAN, "📶"),
      ])}
    <p class="footline" style="max-width:1240px;margin:8px auto 0;text-align:left">Sem rádio, Wi-Fi ou 4G a operação continua —
      e volta <b class="accent">sincronizada, rastreável e sem duplicidade</b>.</p>
  </div>
</section>""")

# S8 — ARQUITETURA (net)
s8_spots=[(22,20,CY,3.2,9),(80,16,VI,3.6,9),(60,66,GR,3.4,8),(34,76,AM,3.8,8),(86,50,CY,3.4,8)]
s8_sparks=[("M 1820 260 Q 1300 200 960 320 Q 620 440 120 340",VI,8.5)]
slides.append(f"""
<section class="slide" data-t="Arquitetura &amp; Evolução">
  <div class="mapwrap"><div class="mapimg" style="background-image:url({imgs['baixada']})"></div>{"".join(f'<div class="gmark" style="left:{x}%;top:{y}%;--c:{c};--gd:{d}s"><div class="disc"></div></div>' for x,y,c,d in [(17,28,CYAN,0),(33,58,GOLD,.6),(49,34,CYAN,1.1),(62,68,GREEN,.3),(74,44,CYAN,.9),(85,60,GOLD,1.4),(27,76,CYAN,.5),(57,20,RAIL,1.2),(90,30,CYAN,.2),(44,82,CYAN,1.6)])}</div>
  {fx(s8_spots,None,"rgba(243,177,60,.12)","rgba(57,214,232,.12)")}
  <div class="wrap">
    <div class="eyebrow">Arquitetura Tecnológica &amp; Evolução</div>
    <h2>Base <span class="accent">sólida</span> hoje, caminho <span class="accent">corporativo</span> a frente</h2>
    <div class="tiles">
      {tile_img('l_streamlit','UI + PWA')}
      {tile_img('l_python','Linguagem')}
      {tile_img('l_fastapi','API')}
      {tile_img('l_postgre','Banco')}
      {tile_img('l_neon','DB serverless')}
      {tile_img('l_supabase','Storage fotos')}
      {tile_img('l_sap','ERP · IW47')}
      {tile_img('l_render','Hospedagem')}
      {tile_glyph('https','HTTPS · API Key')}
      {tile_glyph('gps','GPS · Haversine')}
    </div>
    <div class="hostnote">Hospedagem atual: <b>Render</b> &nbsp;·&nbsp; Evolução prevista: ambiente corporativo MRS</div>
    <div class="road" style="grid-template-columns:repeat(3,1fr)">
      <div class="rcol" style="color:var(--cyan)"><div class="ph">Hoje</div><div class="yr" style="color:var(--ink)">Em produção</div>
        <ul><li>Roteirização</li><li>GPS &amp; evidência</li><li>PWA Offline</li><li>Integração SAP</li><li>Governança</li></ul></div>
      <div class="rcol" style="color:var(--green)"><div class="ph">Curto prazo</div><div class="yr" style="color:var(--ink)">Corporativo</div>
        <ul><li>Hospedagem MRS</li><li>SSO / AD</li><li>API corporativa</li></ul></div>
      <div class="rcol" style="color:var(--violet)"><div class="ph">Futuro</div><div class="yr" style="color:var(--ink)">Inteligência</div>
        <ul><li>Manutenção preditiva</li><li>Recomendação automática de rotas</li></ul></div>
    </div>
  </div>
</section>""")

# S9 — PONTE DEMO (fundo bookend) verde/cyan
s9_spots=[(52,30,GR,3.2,14),(58,44,WH,3.8,11),(46,54,CY,4.2,10),(64,49,GR,3.6,9),(41,26,CY,4.6,8)]
s9_sparks=[("M 300 780 Q 660 560 1050 470 Q 1380 396 1740 300",GR,6.5),
           ("M 560 250 Q 720 356 900 470",CY,5.2)]
slides.append(f"""
<section class="slide" data-t="Agora vamos ver funcionando">
  <div class="end-photo"><i style="background-image:url({imgs['baixada']})"></i></div>
  <div class="slide-fx">
    <svg viewBox="0 0 1920 1080" preserveAspectRatio="none">
      <path class="fxline gold" d="M -40 300 Q 520 180 980 360 Q 1440 540 1960 340"/>
      <path class="fxline" d="M -40 780 Q 560 640 1020 800 Q 1460 950 1960 720"/>
      <path class="fxline gold dim" d="M -40 540 Q 620 460 980 560 Q 1420 680 1960 520"/>
      <circle class="fxspark" r="6" fill="#fff"><animateMotion dur="7s" repeatCount="indefinite" path="M -40 300 Q 520 180 980 360 Q 1440 540 1960 340"/></circle>
      <circle class="fxspark" r="5" fill="{GOLD}"><animateMotion dur="7s" begin="-3.5s" repeatCount="indefinite" path="M -40 300 Q 520 180 980 360 Q 1440 540 1960 340"/></circle>
      <circle class="fxspark" r="6" fill="#fff"><animateMotion dur="8s" repeatCount="indefinite" path="M -40 780 Q 560 640 1020 800 Q 1460 950 1960 720"/></circle>
      <circle class="fxspark" r="5" fill="{CYAN}"><animateMotion dur="8s" begin="-4s" repeatCount="indefinite" path="M -40 780 Q 560 640 1020 800 Q 1460 950 1960 720"/></circle>
    </svg>
  </div>
  {fx(s9_spots,None,"rgba(243,177,60,.14)","rgba(57,214,232,.14)")}
  <div class="wrap" style="text-align:center">
    <div class="kicker" style="margin-left:auto;margin-right:auto">Agora vamos ver funcionando</div>
    <h2 style="font-size:74px">Mais do que um <span class="grad">aplicativo</span></h2>
    <p class="lead" style="margin:18px auto 0;max-width:1080px">A apresentação mostrou o conceito.
      A demonstração ao vivo mostra a <b>execução real</b> — do planejamento ao retorno ao SAP.</p>
    <div class="endchain" style="justify-content:center">
      <span class="amber">Planejamento</span><span class="sep">·</span>
      <span class="accent">Malha</span><span class="sep">·</span>
      <span class="green">Execução</span><span class="sep">·</span>
      <span class="violet">Governança</span><span class="sep">·</span>
      <span style="color:var(--rail)">SAP</span>
    </div>
    <p class="lead" style="margin:22px auto 0;max-width:1040px">Transformando <b>conhecimento operacional</b> em
      <span class="grad">inteligência sistêmica</span>.</p>
    <div class="thanks">Obrigado.</div>
  </div>
</section>""")

JS = r"""
</div></div>
<button class="nav" id="prev">‹</button>
<button class="nav" id="next">›</button>
<div id="dots"></div>
<div id="counter"><b>01</b> / 09</div>
<script>
(function(){
  var slides=[].slice.call(document.querySelectorAll('.slide'));
  var N=slides.length, i=0;
  var stage=document.getElementById('stage'), vp=document.getElementById('viewport');
  var dots=document.getElementById('dots'), prog=document.getElementById('progress'), ctr=document.getElementById('counter');
  slides.forEach(function(s,k){var d=document.createElement('div');d.className='d';d.onclick=function(){go(k)};dots.appendChild(d);});
  var dd=[].slice.call(dots.children);
  function fit(){var s=Math.min(vp.clientWidth/1920, vp.clientHeight/1080);stage.style.transform='scale('+s+')';}
  function pad(n){return (n<10?'0':'')+n;}
  function go(n){
    i=Math.max(0,Math.min(N-1,n));
    slides.forEach(function(s,k){s.classList.toggle('active',k===i);});
    dd.forEach(function(d,k){d.classList.toggle('on',k===i);});
    prog.style.width=((i+1)/N*100)+'%';
    ctr.innerHTML='<b>'+pad(i+1)+'</b> / '+pad(N);
    slides[i].querySelectorAll('canvas.net').forEach(startNet);
  }
  document.getElementById('next').onclick=function(){go(i+1)};
  document.getElementById('prev').onclick=function(){go(i-1)};
  window.addEventListener('keydown',function(e){
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){go(i+1);e.preventDefault();}
    else if(e.key==='ArrowLeft'||e.key==='PageUp'){go(i-1);}
    else if(e.key==='Home'){go(0);}
    else if(e.key==='End'){go(N-1);}
    else if(e.key==='f'||e.key==='F'){if(!document.fullscreenElement)document.documentElement.requestFullscreen();else document.exitFullscreen();}
  });
  var sx=0;
  window.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;},{passive:true});
  window.addEventListener('touchend',function(e){var dx=e.changedTouches[0].clientX-sx;if(Math.abs(dx)>60)go(dx<0?i+1:i-1);},{passive:true});
  window.addEventListener('resize',fit);
  function startNet(cv){
    if(cv._on)return; cv._on=true;
    var ctx=cv.getContext('2d'), W,H,pts;
    W=cv.width=1920;H=cv.height=1080;
    pts=[];for(var k=0;k<74;k++){pts.push({x:Math.random()*W,y:Math.random()*H,vx:(Math.random()-.5)*.35,vy:(Math.random()-.5)*.35});}
    (function loop(){
      ctx.clearRect(0,0,W,H);
      for(var a=0;a<pts.length;a++){var p=pts[a];p.x+=p.vx;p.y+=p.vy;
        if(p.x<0||p.x>W)p.vx*=-1; if(p.y<0||p.y>H)p.vy*=-1;
        for(var b=a+1;b<pts.length;b++){var q=pts[b],dx=p.x-q.x,dy=p.y-q.y,ds=dx*dx+dy*dy;
          if(ds<26000){var o=1-ds/26000;ctx.strokeStyle='rgba(0,229,255,'+(o*.28)+')';ctx.lineWidth=1;
            ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();}}
        ctx.fillStyle='rgba(120,230,255,.75)';ctx.beginPath();ctx.arc(p.x,p.y,1.7,0,6.283);ctx.fill();
      }
      requestAnimationFrame(loop);
    })();
  }
  fit();go(0);
})();
</script>
</body>
</html>
"""

html = HEAD + "\n".join(slides) + JS
html = html.replace("__MRS__", imgs["mrs"])
open(OUT,"w",encoding="utf-8").write(html)
print("WROTE", len(html), "bytes")
