#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador da apresentacao SGO Eletroeletronica MRS (Pitch Premium v7).
Uso:  python3 gerar_pitch_v7.py [PASTA_DAS_IMAGENS] [SAIDA.html]
Requer: Pillow  (pip install pillow)
Imagens esperadas na pasta: bg_port.jpg, bg_yard.jpg, bg_prio.jpg,
                            malha_map.png, fundo.png, baixada_patios.png
Gera um HTML UNICO (imagens embutidas em base64), abre direto no navegador.
"""
import base64, os, sys, io
try:
    from PIL import Image
except ImportError:
    sys.exit("Instale a dependencia Pillow: pip install pillow")

IMG_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
OUT     = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(), "Pitch_Eletroeletronica_SGO_Premiumv7.html")

def _b64(path, mime):
    with open(path, "rb") as f:
        return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode())

def _map_jpg(path):
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

def _p(name): return os.path.join(IMG_DIR, name)

ASSETS = {
    "bg_port": _b64(_p("bg_port.jpg"), "image/jpeg"),
    "bg_yard": _b64(_p("bg_yard.jpg"), "image/jpeg"),
    "bg_prio": _b64(_p("bg_prio.jpg"), "image/jpeg"),
    "malha":   _b64(_p("malha_map.png"), "image/png"),
    "fundo":   _b64(_p("fundo.png"), "image/png"),
    "mapa":    _map_jpg(_p("baixada_patios.png")),
}

# Inline SVG brand marks (stylized renditions, brand-accurate colors)
LOGOS = {}

LOGOS['sap'] = '''<svg viewBox="0 0 128 60" class="lg"><defs><linearGradient id="gsap" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#00b8f1"/><stop offset="1" stop-color="#0057a8"/></linearGradient></defs><path d="M0 9 H128 L104 51 H0 Z" fill="url(#gsap)"/><text x="52" y="41" font-family="Arial,Helvetica,sans-serif" font-weight="800" font-size="30" letter-spacing="1" fill="#fff" text-anchor="middle">SAP</text></svg>'''

LOGOS['python'] = '''<svg viewBox="0 0 255 255" class="lg"><path fill="#3C78AA" d="M126.9 0C62 0 66 28 66 28l.1 29h62v9H41S0 61 0 127.5 36 191 36 191h22v-31s-1-36 35-36h62s34 .5 34-33V33S194 0 127 0zM92 19a11 11 0 1 1 0 22 11 11 0 0 1 0-22z"/><path fill="#FCD246" d="M128 255c65 0 61-28 61-28l-.1-29h-62v-9h87s41 5 41-61.5S218 64 218 64h-22v31s1 36-35 36H99s-34-.5-34 33v54s-5 37 63 37zm35-19a11 11 0 1 1 0-22 11 11 0 0 1 0 22z"/></svg>'''

LOGOS['fastapi'] = '''<svg viewBox="0 0 44 44" class="lg"><circle cx="22" cy="22" r="21" fill="#05998b"/><path d="M24 6 L11 25 H21 L20 38 L33 19 H23 Z" fill="#fff"/></svg>'''

LOGOS['render'] = '''<svg viewBox="0 0 44 44" class="lg"><rect x="1.5" y="1.5" width="41" height="41" rx="11" fill="#0b0b12" stroke="#4d55ff" stroke-width="2"/><path d="M16 32 V13 h9 a5.5 5.5 0 0 1 0 11 h-4 l7 8" fill="none" stroke="#7b83ff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'''

LOGOS['postgres'] = '''<svg viewBox="0 0 48 48" class="lg"><circle cx="24" cy="24" r="23" fill="#31648c"/><g fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M33 15c2 6 1.5 15-1 20-1.6 3-5 2-6-1"/><path d="M15 16c-2 5-2 14 .5 19 1.5 3 4.5 2.5 5.5 0"/><path d="M20 13c3-1.6 8-1.6 12 .5"/><path d="M20 34c0-4 .3-9 0-13"/><path d="M26 33c.4-4 .3-8 .2-12"/></g><circle cx="19.5" cy="19" r="1.7" fill="#fff"/></svg>'''

LOGOS['neon'] = '''<svg viewBox="0 0 44 44" class="lg"><rect x="2" y="2" width="40" height="40" rx="12" fill="#0a0f1c" stroke="#00e599" stroke-width="2"/><path d="M13 32 V13 l18 19 V13" fill="none" stroke="#00e599" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'''

LOGOS['supabase'] = '''<svg viewBox="0 0 44 44" class="lg"><defs><linearGradient id="gsb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3ecf8e"/><stop offset="1" stop-color="#1b8f5e"/></linearGradient></defs><path d="M25 3 L10 24 h11 l-2 17 L34 20 H23 Z" fill="url(#gsb)"/></svg>'''

LOGOS['streamlit'] = '''<svg viewBox="0 0 48 40" class="lg"><g fill="#ff4b4b"><path d="M4 15 L24 6 L44 15 L24 24 Z"/><path d="M4 21 L21 27 L21 35 Z" opacity=".82"/><path d="M44 21 L27 27 L27 35 Z" opacity=".9"/></g></svg>'''

LOGOS['pwa'] = '''<svg viewBox="0 0 60 44" class="lg"><rect x="1" y="8" width="58" height="28" rx="7" fill="#5a0fc8"/><text x="30" y="29" font-family="Arial,sans-serif" font-weight="800" font-size="16" fill="#fff" text-anchor="middle">PWA</text></svg>'''

LOGOS['html5'] = '''<svg viewBox="0 0 40 44" class="lg"><path d="M4 2 h32 l-3 34 -13 4 -13-4 Z" fill="#e44d26"/><path d="M20 5 v33 l10-3 2.4-30 Z" fill="#f16529"/><path d="M11 12 h18 l-.6 6 H15l.4 4h11l-.9 9-5.5 1.6-5.5-1.6-.4-4h3l.2 2 2.7.8 2.8-.8.3-3H11.5Z" fill="#fff"/></svg>'''

HEAD = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SGO Eletroeletronica MRS - Apresentacao</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap">
<style>
:root{
  --navy-900:#03070f; --navy-850:#050c18; --navy-800:#071426; --navy-700:#0b1f38; --navy-650:#102844;
  --gold:#f3b13c; --gold-2:#ffd479; --cyan:#39d6e8; --teal:#1ea7b6; --blue:#3b82f6;
  --rail:#ff5a7e; --green:#37e07e; --red:#ff465e; --violet:#9b7bff;
  --white:#eef4ff; --soft:#aebfda; --dim:#6f83a6; --line:rgba(120,160,220,.16);
  --stage-bg:#02050c; --slide-bg:#040a16;
  --card:linear-gradient(155deg, rgba(15,32,58,.72), rgba(6,15,30,.5));
  --card-soft:linear-gradient(155deg, rgba(13,28,52,.5), rgba(6,14,28,.32));
  --card-bd:rgba(120,160,220,.18); --shadow:0 24px 60px rgba(0,0,0,.5);
  --font:'Manrope', system-ui, sans-serif; --mono:'Space Mono', monospace;
  --t-h2:54px; --t-lead:26px; --t-body:21px; --t-small:16px;
  --ease:cubic-bezier(.16,1,.3,1); --pad-x:104px; --pad-y:80px;
}
*{ margin:0; padding:0; box-sizing:border-box; }
html,body{ width:100%; height:100%; overflow:hidden; background:var(--stage-bg);
  font-family:var(--font); color:var(--white); -webkit-font-smoothing:antialiased; }

/* ---- palco fixo 16:9 ---- */
.deck-viewport{ position:fixed; inset:0; overflow:hidden; background:var(--stage-bg); }
.deck-stage{ position:absolute; left:0; top:0; width:1920px; height:1080px; overflow:hidden;
  transform-origin:0 0; background:#03070f; }
.deck-stage::before{ content:""; position:absolute; inset:0; z-index:0; opacity:.5;
  background-image:var(--fundo); background-size:cover; background-position:center; }
/* particle network canvas (motion de pontos) */
.netbg{ position:absolute; inset:0; z-index:1; pointer-events:none; }

.slide{ position:absolute; inset:0; width:1920px; height:1080px; overflow:hidden;
  visibility:hidden; opacity:0; pointer-events:none; z-index:2; background:
    radial-gradient(1100px 760px at 6% 0%, rgba(243,177,60,.09) 0%, transparent 56%),
    radial-gradient(1200px 820px at 100% 100%, rgba(57,214,232,.09) 0%, transparent 60%),
    linear-gradient(160deg, rgba(6,18,39,.78) 0%, rgba(4,10,22,.86) 55%, rgba(3,6,15,.92) 100%); }
.slide.active,.slide.visible{ visibility:visible; opacity:1; pointer-events:auto; z-index:3; }
.slide::before{ content:""; position:absolute; inset:0; z-index:0; pointer-events:none;
  background-image:linear-gradient(rgba(120,160,220,.04) 1px,transparent 1px),
                   linear-gradient(90deg, rgba(120,160,220,.04) 1px,transparent 1px);
  background-size:66px 66px; mask-image:radial-gradient(130% 105% at 50% 30%, #000 26%, transparent 84%); }

/* ---- fundo de foto por slide ---- */
.sbg{ position:absolute; inset:0; z-index:0; overflow:hidden; }
.sbg i{ position:absolute; inset:-3%; background-image:var(--img); background-size:cover; background-position:center;
  animation:kb 26s ease-in-out infinite alternate; }
.slide.visible .sbg i{ animation-play-state:running; }
@keyframes kb{ 0%{ transform:scale(1.04) translate(0,0);} 100%{ transform:scale(1.12) translate(-1.4%,-1.2%);} }
.sbg::after{ content:""; position:absolute; inset:0; background:var(--veil,
  linear-gradient(100deg, rgba(3,8,18,.94) 0%, rgba(3,8,18,.74) 34%, rgba(3,8,18,.30) 60%, rgba(3,8,18,.66) 100%)); }
.slide.has-photo{ background:linear-gradient(160deg, rgba(4,9,18,.30), rgba(3,6,13,.42)); }
.slide.has-photo::before{ opacity:.5; }

.orb{ position:absolute; border-radius:50%; filter:blur(64px); opacity:.5; z-index:0; pointer-events:none;
  animation:orbFloat 11s ease-in-out infinite; }
.orb.b{ animation-duration:14s; animation-direction:reverse; }
@keyframes orbFloat{ 0%,100%{ transform:translate(0,0);} 50%{ transform:translate(30px,22px);} }
.slide-inner{ position:absolute; inset:0; z-index:2; padding:var(--pad-y) var(--pad-x);
  display:flex; flex-direction:column; }

/* ---- chrome ---- */
.kicker{ font-family:var(--mono); font-size:15px; letter-spacing:.26em; text-transform:uppercase;
  color:var(--gold); display:inline-flex; align-items:center; gap:14px; }
.kicker::before{ content:""; width:36px; height:2px;
  background:linear-gradient(90deg, var(--gold), transparent); box-shadow:0 0 12px var(--gold); }
.kicker.amber{ color:var(--gold-2);} .kicker.amber::before{ background:linear-gradient(90deg,var(--gold-2),transparent); box-shadow:0 0 12px var(--gold-2);}
.kicker.rail{ color:var(--rail);} .kicker.rail::before{ background:linear-gradient(90deg,var(--rail),transparent); box-shadow:0 0 12px var(--rail);}
.kicker.green{ color:var(--green);} .kicker.green::before{ background:linear-gradient(90deg,var(--green),transparent); box-shadow:0 0 12px var(--green);}
.kicker.cyan{ color:var(--cyan);} .kicker.cyan::before{ background:linear-gradient(90deg,var(--cyan),transparent); box-shadow:0 0 12px var(--cyan);}
.kicker.violet{ color:var(--violet);} .kicker.violet::before{ background:linear-gradient(90deg,var(--violet),transparent); box-shadow:0 0 12px var(--violet);}
.slide-title{ font-weight:800; font-size:var(--t-h2); line-height:1.05; letter-spacing:-.02em; margin-top:16px; }
.grad{ background:linear-gradient(100deg, var(--gold), var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-gold{ background:linear-gradient(100deg, var(--gold), var(--gold-2)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-rail{ background:linear-gradient(100deg, var(--rail), var(--gold)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-green{ background:linear-gradient(100deg, var(--green), var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-cyan{ background:linear-gradient(100deg, var(--cyan), var(--blue)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-violet{ background:linear-gradient(100deg, var(--violet), var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.slide-lead,.lead{ font-size:var(--t-lead); color:var(--soft); line-height:1.42; margin-top:14px; max-width:1180px; }
.lead b, .slide-lead b{ color:var(--white); }
.cy{ color:var(--cyan); } .gn{ color:var(--green); }
.num{ font-family:var(--mono); font-weight:700; font-variant-numeric:tabular-nums; }

.hud-corner{ position:fixed; top:24px; right:32px; z-index:1000; display:flex; align-items:center; gap:18px;
  font-family:var(--mono); font-size:12.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--dim); }
.hud-corner .brand{ color:var(--soft); } .hud-corner .brand b{ color:var(--gold); font-weight:700; }
.deck-progress{ position:fixed; top:0; left:0; right:0; height:4px; z-index:1001; background:rgba(120,160,220,.1); }
.deck-progress span{ display:block; height:100%; width:10%;
  background:linear-gradient(90deg, var(--gold), var(--cyan)); box-shadow:0 0 16px rgba(243,177,60,.55);
  transition:width .5s var(--ease); }
.deck-dots{ position:fixed; right:28px; top:50%; transform:translateY(-50%); z-index:1000;
  display:flex; flex-direction:column; gap:12px; }
.deck-dots button{ width:11px; height:11px; border-radius:50%; border:1px solid var(--line);
  background:rgba(120,160,220,.14); cursor:pointer; padding:0; transition:all .3s var(--ease); }
.deck-dots button:hover{ border-color:var(--gold); }
.deck-dots button.on{ background:var(--gold); border-color:var(--gold); box-shadow:0 0 12px var(--gold);
  height:26px; border-radius:6px; }
.deck-controls{ position:fixed; left:50%; bottom:20px; transform:translateX(-50%); z-index:1000;
  display:flex; align-items:center; gap:14px; padding:8px 14px; border-radius:999px;
  background:linear-gradient(155deg, rgba(13,28,52,.8), rgba(6,14,28,.62)); border:1px solid var(--line);
  backdrop-filter:blur(8px); }
.dc-btn{ width:38px; height:38px; border-radius:50%; border:1px solid var(--line); cursor:pointer;
  background:rgba(120,160,220,.08); color:var(--soft); font-size:16px; transition:all .25s var(--ease); }
.dc-btn:hover:not(:disabled){ border-color:var(--gold); color:var(--gold); }
.dc-btn:disabled{ opacity:.32; cursor:default; }
.dc-btn.fs{ font-size:14px; }
.page-counter{ position:fixed; right:34px; bottom:26px; z-index:1000; font-family:var(--mono); font-size:14px;
  letter-spacing:.1em; color:var(--dim); opacity:.7; user-select:none; }
.page-counter b{ color:var(--soft); } .page-counter i{ margin:0 5px; font-style:normal; opacity:.55; }
.kb-hint{ position:fixed; left:50%; bottom:68px; transform:translateX(-50%); z-index:1000;
  font-family:var(--mono); font-size:12px; letter-spacing:.1em; color:var(--dim); opacity:.8;
  transition:opacity .5s ease; } .kb-hint b{ color:var(--soft); } .kb-hint.hide{ opacity:0; }

/* ---- reveal ---- */
.reveal{ opacity:0; transform:translateY(18px);
  transition:opacity .7s var(--ease), transform .7s var(--ease); transition-delay:var(--d,0s); }
.reveal.left{ transform:translateX(-28px); } .reveal.right{ transform:translateX(28px); }
.reveal.up{ transform:translateY(26px); } .reveal.down{ transform:translateY(-20px); }
.reveal.scale{ transform:scale(.965); transform-origin:left center; } .reveal.fade{ transform:none; }
.slide.visible .reveal{ opacity:1; transform:none; }

/* ---- cards / pills / stats ---- */
.card{ background:var(--card); border:1px solid var(--card-bd); border-radius:18px; padding:24px;
  box-shadow:var(--shadow); position:relative; overflow:hidden; backdrop-filter:blur(4px); }
.card h4{ font-size:20px; } .card p{ font-size:16px; color:var(--soft); line-height:1.4; margin-top:7px; }
.card .fico{ font-size:32px; }
.card.cy{ border-color:rgba(57,214,232,.36); } .card.gn{ border-color:rgba(55,224,126,.36); }
.card.gd{ border-color:rgba(243,177,60,.36); } .card.rl{ border-color:rgba(255,90,126,.36); }
.feat{ display:grid; gap:18px; }
.pill{ display:inline-flex; align-items:center; gap:8px; font-family:var(--mono); font-size:13px;
  letter-spacing:.04em; padding:6px 13px; border-radius:9px; background:rgba(120,160,220,.08);
  border:1px solid var(--line); color:var(--soft); }
.pill b{ color:var(--white); font-weight:700; }
.tag{ display:inline-block; font-family:var(--mono); font-size:12px; letter-spacing:.06em; text-transform:uppercase;
  padding:4px 11px; border-radius:7px; }
.tag.gold{ color:#1a1205; background:linear-gradient(155deg,var(--gold),var(--gold-2)); font-weight:700; }
.tag.rail{ color:#1a0810; background:var(--rail); font-weight:700; }
.tag.cyan{ color:#04222a; background:var(--cyan); font-weight:700; }
.tag.o-gold{ color:var(--gold-2); border:1px solid rgba(243,177,60,.4); }
.tag.o-cyan{ color:var(--cyan); border:1px solid rgba(57,214,232,.4); }
.stat b{ font-family:var(--mono); font-size:46px; color:var(--gold); display:block; line-height:1; }
.stat span{ font-size:17px; color:var(--soft); display:block; margin-top:5px; }
.d{ width:11px; height:11px; border-radius:50%; display:inline-block; vertical-align:middle; margin-right:6px; }
.d.gold{ background:var(--gold); box-shadow:0 0 8px var(--gold); }
.d.cyan{ background:var(--cyan); box-shadow:0 0 8px var(--cyan); }
.d.rail{ background:var(--rail); box-shadow:0 0 8px var(--rail); }
.d.green{ background:var(--green); box-shadow:0 0 8px var(--green); }

/* ---- logos ---- */
.lg{ display:block; width:100%; height:100%; }
.logo-chip{ width:64px; height:64px; display:grid; place-items:center; border-radius:16px;
  background:rgba(255,255,255,.94); box-shadow:0 10px 26px rgba(0,0,0,.4); padding:11px; }
.logo-chip.dark{ background:linear-gradient(155deg,#12213c,#0a1526); border:1px solid var(--line); }
.logo-chip.plain{ background:transparent; box-shadow:none; }

/* ================= SLIDE 1 capa ================= */
.s1 .slide-inner{ justify-content:center; align-items:flex-start; }
.alime-badge{ display:inline-flex; align-items:center; gap:11px; padding:9px 17px; margin-bottom:22px;
  border-radius:999px; background:rgba(13,28,52,.6); border:1px solid var(--line); backdrop-filter:blur(6px); }
.alime-badge .ab-dot{ width:11px; height:11px; border-radius:50%; background:var(--gold); box-shadow:0 0 12px var(--gold); }
.alime-badge span{ font-family:var(--mono); font-size:14px; letter-spacing:.16em; text-transform:uppercase; color:var(--soft); }
.s1-title{ font-size:96px; font-weight:800; line-height:1.0; letter-spacing:-.03em; }
.hl-gold{ background:linear-gradient(100deg, var(--gold), var(--gold-2)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.s1-tags{ display:flex; gap:12px; margin-top:34px; flex-wrap:wrap; }

/* ================= flow S4 (logos) ================= */
.flow{ display:flex; align-items:stretch; justify-content:space-between; gap:8px; margin-top:52px; }
.fnode{ flex:1; display:flex; flex-direction:column; align-items:center; text-align:center; gap:14px;
  padding:26px 14px; border-radius:20px; background:var(--card); border:1px solid var(--card-bd);
  border-top:3px solid var(--c,var(--cyan)); box-shadow:var(--shadow); position:relative; }
.fnode .flogos{ display:flex; gap:9px; align-items:center; justify-content:center; min-height:66px; }
.fnode h4{ font-size:21px; } .fnode p{ font-size:14.5px; color:var(--soft); line-height:1.36; }
.fnode .fstep{ position:absolute; top:-15px; left:50%; transform:translateX(-50%); width:30px; height:30px;
  border-radius:50%; background:var(--c,var(--cyan)); color:#04141c; font-family:var(--mono); font-weight:700;
  font-size:15px; display:grid; place-items:center; box-shadow:0 0 16px var(--c,var(--cyan)); }
.farr{ align-self:center; color:var(--dim); font-size:26px; }

/* ================= S5 mapa ================= */
.mapwrap{ position:absolute; inset:0; z-index:0; }
.mapimg{ position:absolute; inset:0; background-image:var(--img); background-size:cover; background-position:center; }
.mapwrap::after{ content:""; position:absolute; inset:0;
  background:linear-gradient(100deg, rgba(4,10,22,.95) 0%, rgba(4,10,22,.7) 30%, rgba(4,10,22,.16) 56%, rgba(4,10,22,.5) 100%),
             radial-gradient(120% 90% at 78% 50%, transparent 40%, rgba(4,10,22,.55) 100%); }
.mappanel{ position:absolute; z-index:2; left:var(--pad-x); top:var(--pad-y); max-width:640px; }
.gmark{ position:absolute; z-index:2; transform:translate(-50%,-50%); opacity:0; animation:mk .5s var(--ease) forwards; animation-delay:var(--gd,.4s); }
.slide.visible .gmark{ }
.gmark .disc{ width:14px; height:14px; border-radius:50%; background:radial-gradient(circle,#fff 0%,var(--c,var(--cyan)) 55%,transparent 78%);
  box-shadow:0 0 0 6px color-mix(in srgb, var(--c,var(--cyan)) 22%, transparent), 0 0 20px var(--c,var(--cyan)); }
.gmark .lab{ position:absolute; left:20px; top:-8px; white-space:nowrap; }
.gmark .lab .t{ display:block; font-weight:700; font-size:16px; color:#fff; text-shadow:0 2px 8px #000; }
.gmark .lab .s{ display:block; font-family:var(--mono); font-size:11px; letter-spacing:.08em; color:var(--soft); text-shadow:0 2px 8px #000; }
@keyframes mk{ from{opacity:0; transform:translate(-50%,-40%) scale(.6);} to{opacity:1; transform:translate(-50%,-50%) scale(1);} }
.geofence{ position:absolute; z-index:1; width:150px; height:150px; transform:translate(-50%,-50%);
  border-radius:50%; border:1.5px dashed var(--rail); background:radial-gradient(circle, rgba(255,90,126,.12), transparent 70%); }
.geofence .gf-tag{ position:absolute; left:50%; bottom:-14px; transform:translateX(-50%); font-family:var(--mono);
  font-size:11px; letter-spacing:.08em; color:var(--rail); white-space:nowrap; }

/* ================= infografico generico ================= */
.info-badge{ display:inline-flex; align-items:center; gap:9px; font-family:var(--mono); font-size:12px;
  letter-spacing:.14em; text-transform:uppercase; color:var(--dim); padding:5px 12px; border-radius:8px;
  border:1px solid var(--line); background:rgba(120,160,220,.05); }

/* S6 antes/depois */
.imp-maps{ display:flex; align-items:stretch; gap:24px; margin-top:34px; }
.imp-map{ flex:1; border-radius:20px; padding:26px 28px; position:relative; }
.imp-map.atual{ border:1px solid rgba(255,90,126,.34); background:linear-gradient(160deg, rgba(60,12,26,.5), rgba(6,14,28,.5)); }
.imp-map.sol{ border:1px solid rgba(57,214,232,.36); background:linear-gradient(160deg, rgba(8,44,58,.5), rgba(6,14,28,.5)); }
.im-cap{ display:flex; align-items:center; gap:10px; font-family:var(--mono); font-size:14px; letter-spacing:.06em;
  text-transform:uppercase; color:var(--soft); margin-bottom:18px; }
.im-list{ list-style:none; display:flex; flex-direction:column; gap:14px; }
.im-list li{ display:flex; align-items:center; gap:14px; font-size:18px; color:var(--white); }
.im-list .ic{ width:38px; height:38px; flex:none; border-radius:11px; display:grid; place-items:center; font-size:18px; }
.imp-map.atual .ic{ color:var(--rail); background:rgba(255,90,126,.12); border:1px solid rgba(255,90,126,.3); }
.imp-map.sol .ic{ color:var(--cyan); background:rgba(57,214,232,.12); border:1px solid rgba(57,214,232,.3); }
.im-foot{ display:block; margin-top:20px; font-family:var(--mono); font-size:14px; }
.imp-map.atual .im-foot{ color:var(--rail); } .imp-map.sol .im-foot{ color:var(--cyan); }
.imp-arrow{ align-self:center; color:var(--cyan); font-size:34px; }
.imp-insight{ margin-top:26px; padding:18px 24px; border-radius:14px;
  background:linear-gradient(155deg, rgba(57,214,232,.1), rgba(6,15,30,.34)); border:1px solid rgba(57,214,232,.3);
  font-size:19px; color:var(--white); }

/* S7 cascata priorizacao */
.cascade{ margin-top:38px; display:flex; flex-direction:column; gap:14px; position:relative; }
.crow{ display:grid; grid-template-columns:118px 66px 1fr auto; align-items:center; gap:22px;
  padding:18px 26px; border-radius:16px; background:var(--card); border:1px solid var(--card-bd);
  border-left:5px solid var(--c,var(--cyan)); box-shadow:var(--shadow); position:relative; }
.crow .lvl{ font-family:var(--mono); font-size:13px; letter-spacing:.08em; color:var(--c,var(--cyan)); text-transform:uppercase; }
.crow .pio{ width:52px; height:52px; border-radius:14px; display:grid; place-items:center; font-size:26px;
  background:color-mix(in srgb, var(--c,var(--cyan)) 14%, transparent); border:1px solid color-mix(in srgb, var(--c,var(--cyan)) 40%, transparent); }
.crow h4{ font-size:22px; } .crow p{ font-size:15.5px; color:var(--soft); margin-top:3px; }
.crow .bignum{ font-family:var(--mono); font-weight:700; font-size:60px; line-height:1; color:color-mix(in srgb, var(--c,var(--cyan)) 40%, transparent); }
.crow .cbar{ position:absolute; left:0; top:0; bottom:0; width:var(--w,100%); border-radius:16px;
  background:linear-gradient(90deg, color-mix(in srgb, var(--c,var(--cyan)) 12%, transparent), transparent); pointer-events:none; }
.crow.lock::after{ content:"bloqueia inferiores"; position:absolute; right:130px; top:50%; transform:translateY(-50%);
  font-family:var(--mono); font-size:11px; color:var(--dim); letter-spacing:.06em; }

/* S8 equacao de portas */
.imp-calc{ display:flex; align-items:stretch; justify-content:center; gap:12px; margin-top:40px; flex-wrap:nowrap; }
.imp-factor{ flex:1; max-width:220px; text-align:center; padding:24px 16px; border-radius:16px;
  background:var(--card); border:1px solid rgba(55,224,126,.28); box-shadow:var(--shadow);
  display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; }
.imp-factor .fmk{ font-size:32px; } .imp-factor b{ font-size:22px; color:#fff; }
.imp-factor .fnum{ font-family:var(--mono); font-weight:700; font-size:30px; color:var(--green); }
.imp-factor span{ font-size:13.5px; color:var(--soft); line-height:1.35; } .imp-factor i{ color:var(--dim); font-style:italic; }
.imp-op,.imp-eq{ align-self:center; font-family:var(--mono); font-size:30px; color:var(--dim); }
.imp-result{ display:flex; align-items:center; gap:16px; padding:24px 30px; border-radius:16px;
  background:linear-gradient(150deg, rgba(55,224,126,.2), rgba(6,15,30,.42)); border:1px solid rgba(55,224,126,.55); }
.imp-result .ir-ico{ width:50px; height:50px; border-radius:50%; display:grid; place-items:center; font-size:24px;
  background:rgba(55,224,126,.14); border:1px solid rgba(55,224,126,.34); box-shadow:0 0 18px rgba(55,224,126,.2); }
.ir-lab{ font-family:var(--mono); font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--soft); display:block; }
.imp-result .ir-tx b{ font-size:22px; color:var(--green); }

/* S9 offline journey */
.ojourney{ display:flex; align-items:stretch; gap:14px; margin-top:44px; }
.ostep{ flex:1; position:relative; border-radius:20px; padding:26px 22px 24px; background:var(--card);
  border:1px solid var(--card-bd); border-top:3px solid var(--c,var(--cyan)); box-shadow:var(--shadow); }
.ostep .oi{ width:60px; height:60px; border-radius:16px; display:grid; place-items:center; font-size:30px;
  background:color-mix(in srgb, var(--c,var(--cyan)) 14%, transparent); border:1px solid color-mix(in srgb, var(--c,var(--cyan)) 40%, transparent); }
.ostep h4{ font-size:20px; margin-top:16px; } .ostep p{ font-size:15px; color:var(--soft); margin-top:8px; line-height:1.4; }
.ostep .ost{ position:absolute; top:20px; right:22px; font-family:var(--mono); font-size:12px; color:var(--c,var(--cyan)); letter-spacing:.08em; }
.oconn{ align-self:center; color:var(--cyan); font-size:24px; }
.osignal{ position:absolute; top:20px; right:22px; }

/* S10 honeycomb */
.honey{ margin-top:30px; position:relative; height:640px; }
.hex{ position:absolute; width:224px; height:250px; transform:translate(-50%,-50%);
  clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);
  background:linear-gradient(155deg, color-mix(in srgb,var(--c,var(--cyan)) 20%, rgba(9,20,38,.9)), rgba(6,14,28,.94));
  display:flex; flex-direction:column; align-items:center; justify-content:center; gap:9px; text-align:center;
  padding:0 26px; box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c,var(--cyan)) 45%, transparent), 0 18px 44px rgba(0,0,0,.5);
  opacity:0; transition:opacity .6s var(--ease), transform .6s var(--ease); transition-delay:var(--hd,0s); }
.slide.visible .hex{ opacity:1; }
.hex.core{ background:linear-gradient(155deg, rgba(55,224,126,.32), rgba(6,20,16,.92));
  box-shadow:inset 0 0 0 2px rgba(55,224,126,.7), 0 0 60px rgba(55,224,126,.28); }
.hex .hi{ font-size:32px; } .hex h4{ font-size:18px; line-height:1.12; }
.hex .hs{ font-family:var(--mono); font-size:11px; letter-spacing:.1em; color:var(--soft); text-transform:uppercase; }
.hex.core h4{ font-size:24px; } .hex.core .hs{ color:var(--green); }

/* S11 pipeline */
.pipe{ display:flex; align-items:stretch; gap:0; margin-top:40px; }
.pcol{ flex:1; padding:30px 26px; position:relative; }
.pcol .ptag{ display:inline-block; font-family:var(--mono); font-size:12px; letter-spacing:.08em; text-transform:uppercase;
  padding:5px 12px; border-radius:8px; margin-bottom:16px; }
.pcol h4{ font-size:24px; } .pcol p{ font-size:16.5px; color:var(--soft); margin-top:8px; line-height:1.42; }
.pcol .plogos{ display:flex; gap:10px; margin-top:18px; }
.pchev{ align-self:center; color:var(--dim); font-size:40px; padding:0 6px; }
.pcol.in{ border-radius:20px 0 0 20px; background:linear-gradient(155deg, rgba(57,214,232,.12), rgba(6,15,30,.4)); border:1px solid rgba(57,214,232,.3); }
.pcol.pr{ background:linear-gradient(155deg, rgba(243,177,60,.12), rgba(6,15,30,.4)); border:1px solid rgba(243,177,60,.3); border-left:none; border-right:none; }
.pcol.out{ border-radius:0 20px 20px 0; background:linear-gradient(155deg, rgba(55,224,126,.12), rgba(6,15,30,.4)); border:1px solid rgba(55,224,126,.3); }

/* S12 stack grid */
.stackgrid{ display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin-top:36px; }
.scard{ border-radius:18px; padding:24px 22px; background:var(--card); border:1px solid var(--card-bd);
  border-left:4px solid var(--c,var(--cyan)); box-shadow:var(--shadow); display:flex; align-items:center; gap:16px; }
.scard .sc-tx h4{ font-size:14px; font-family:var(--mono); letter-spacing:.06em; text-transform:uppercase; color:var(--dim); }
.scard .sc-tx b{ font-size:19px; color:#fff; display:block; margin-top:3px; }

/* S13 benefit tiles */
.btiles{ display:grid; grid-template-columns:repeat(3,1fr); gap:18px; margin-top:34px; }
.btile{ border-radius:18px; padding:26px 24px; background:var(--card); border:1px solid var(--card-bd);
  box-shadow:var(--shadow); position:relative; overflow:hidden; }
.btile::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--c,var(--cyan)); }
.btile .bt-ic{ width:52px; height:52px; border-radius:14px; display:grid; place-items:center; font-size:26px;
  background:color-mix(in srgb,var(--c,var(--cyan)) 14%, transparent); border:1px solid color-mix(in srgb,var(--c,var(--cyan)) 38%, transparent); }
.btile h4{ font-size:19px; margin-top:16px; } .btile p{ font-size:15px; color:var(--soft); margin-top:7px; line-height:1.4; }

/* S14 roadmap */
.tl{ display:flex; justify-content:space-between; gap:8px; margin-top:60px; position:relative; }
.tl::before{ content:""; position:absolute; left:2%; right:2%; top:34px; height:2px; background:linear-gradient(90deg,var(--green),var(--gold),var(--cyan)); opacity:.45; }
.tstep{ flex:1; text-align:center; display:flex; flex-direction:column; align-items:center; gap:10px; }
.tstep .tdot{ width:22px; height:22px; border-radius:50%; background:var(--c,var(--cyan)); box-shadow:0 0 16px var(--c,var(--cyan)); border:4px solid #050c18; }
.tstep h4{ font-size:17px; margin-top:6px; max-width:200px; } .tstep .tst{ font-family:var(--mono); font-size:12px; letter-spacing:.1em; }

/* end */
.end-photo{ position:absolute; inset:0; z-index:0; }
.end-photo i{ position:absolute; inset:0; background-image:var(--img); background-size:cover; background-position:center; opacity:.5; }
.end-photo::after{ content:""; position:absolute; inset:0; background:radial-gradient(ellipse 82% 74% at 50% 48%, rgba(4,10,22,.5) 0%, rgba(4,10,22,.32) 42%, rgba(4,10,22,.82) 100%); }

@media print{ .deck-progress,.deck-dots,.deck-controls,.page-counter,.kb-hint,.hud-corner{ display:none !important; } }
</style>
</head>
<body>
<div class="deck-viewport">
  <div class="deck-stage" id="deckStage">
    <canvas class="netbg" id="netbg"></canvas>
'''

# inject fundo asset into stage bg via style
HEAD = HEAD.replace('.deck-stage::before{ content:""; position:absolute; inset:0; z-index:0; opacity:.5;\n  background-image:var(--fundo);',
                    '.deck-stage::before{ content:""; position:absolute; inset:0; z-index:0; opacity:.5;\n  background-image:url(%s);' % ASSETS['fundo'])


def chip(name, cls='logo-chip'):
    return '<span class="%s">%s</span>' % (cls, LOGOS[name])

S = []

# ===== S1 capa (bg_port) =====
S.append('''
<section class="slide s1 has-photo">
  <div class="sbg" style="--img:url(%(bg_port)s); --veil:linear-gradient(100deg, rgba(3,8,18,.92) 0%%, rgba(3,8,18,.62) 40%%, rgba(3,8,18,.28) 70%%, rgba(3,8,18,.6) 100%%);"><i></i></div>
  <div class="orb" style="width:520px;height:520px;background:rgba(243,177,60,.16);left:-140px;top:-110px;"></div>
  <div class="slide-inner">
    <div class="alime-badge reveal down" style="--d:.05s"><span class="ab-dot"></span><span>SGO &middot; Malha Ferroviaria MRS</span></div>
    <h1 class="s1-title reveal up" style="--d:.16s">Gestao Operacional<br><span class="hl-gold">Eletroeletronica</span></h1>
    <p class="slide-lead reveal up" style="--d:.3s;max-width:900px;">Roteirizacao inteligente, apontamento de campo com GPS e governanca da baixa &mdash; do planejamento SAP ate a evidencia auditavel, online e offline.</p>
    <div class="s1-tags reveal up" style="--d:.44s">
      <span class="pill"><span class="d gold"></span><b>Roteirizacao geografica</b></span>
      <span class="pill"><span class="d cyan"></span><b>GPS obrigatorio &middot; cerca 2,0 km</b></span>
      <span class="pill"><span class="d green"></span><b>PWA offline</b></span>
    </div>
  </div>
</section>''' % ASSETS)

# ===== S2 problema =====
S.append('''
<section class="slide s2">
  <div class="orb" style="width:480px;height:480px;background:rgba(255,90,126,.12);right:-120px;top:-80px;"></div>
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker rail reveal left" style="--d:.05s">O Problema &middot; Antes do SGO</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Execucao de campo <span class="grad-rail">sem trilha digital</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O plano existia no SAP, mas a execucao acontecia no improviso &mdash; e voltava como digitacao manual, sem prova.</p>
    <div class="feat" style="grid-template-columns:repeat(4,1fr);margin-top:38px;">
      <div class="card rl reveal up" style="--d:.32s"><div class="fico">&#128506;</div><h4>Rota no papel</h4><p>Sequencia decidida na hora, dependente da experiencia de cada tecnico.</p></div>
      <div class="card rl reveal up" style="--d:.42s"><div class="fico">&#10067;</div><h4>Baixa sem prova</h4><p>Sem GPS, sem foto, sem horario &mdash; dificil auditar o que foi feito.</p></div>
      <div class="card rl reveal up" style="--d:.52s"><div class="fico">&#128245;</div><h4>Zona sem sinal</h4><p>Serra, tunel e patio remoto travavam qualquer registro em tempo real.</p></div>
      <div class="card rl reveal up" style="--d:.62s"><div class="fico">&#9000;</div><h4>Retrabalho no escritorio</h4><p>Relatorios redigitados manualmente de volta ao corporativo.</p></div>
    </div>
  </div>
</section>''')

# ===== S3 solucao =====
S.append('''
<section class="slide s3">
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker cyan reveal left" style="--d:.05s">A Solucao &middot; Camada Digital</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Uma camada entre <span class="grad">plano e malha</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O SGO recebe o plano, organiza a execucao com regras e geografia, e devolve resultado estruturado e auditavel.</p>
    <div class="feat" style="grid-template-columns:repeat(3,1fr);margin-top:38px;">
      <div class="card cy reveal up" style="--d:.34s"><div class="fico">&#129517;</div><h4>Roteiriza</h4><p>Ordena as OS por proximidade real (Haversine) em vez de escolha manual.</p></div>
      <div class="card gd reveal up" style="--d:.46s"><div class="fico">&#128737;</div><h4>Governa</h4><p>Priorizacao em cascata e validacao da baixa no servidor, sem excecao.</p></div>
      <div class="card gn reveal up" style="--d:.58s"><div class="fico">&#128279;</div><h4>Rastreia</h4><p>GPS, foto e horario atrelados a cada baixa &mdash; e de volta ao SAP.</p></div>
    </div>
  </div>
</section>''')

# ===== S4 ciclo com LOGOS =====
_s4 = {
    'sap': chip('sap'), 'py': chip('python'), 'fast': chip('fastapi'),
    'stream': chip('streamlit'), 'pwa': chip('pwa'), 'pg': chip('postgres'), 'neon': chip('neon'),
}
S.append('''
<section class="slide s4">
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker cyan reveal left" style="--d:.05s">O Ciclo &middot; Ponta a Ponta</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Do <span class="grad-cyan">planejamento</span> a baixa &mdash; sobre a stack real</h2>
    <p class="slide-lead reveal up" style="--d:.22s">Cada etapa roda sobre uma tecnologia dedicada. O ciclo fecha sem retrabalho.</p>
    <div class="flow">
      <div class="fnode reveal up" style="--d:.30s;--c:var(--blue)"><span class="fstep">1</span><div class="flogos">{sap}</div><h4>SAP</h4><p>Planejamento<br>OS programadas</p></div>
      <span class="farr reveal fade" style="--d:.5s">&#9656;</span>
      <div class="fnode reveal up" style="--d:.40s;--c:var(--gold)"><span class="fstep">2</span><div class="flogos">{py}{fast}</div><h4>Motor SGO</h4><p>Python &middot; FastAPI<br>Priorizacao &middot; Regras</p></div>
      <span class="farr reveal fade" style="--d:.6s">&#9656;</span>
      <div class="fnode reveal up" style="--d:.50s;--c:var(--cyan)"><span class="fstep">3</span><div class="flogos">{stream}{pwa}</div><h4>Campo</h4><p>Streamlit &middot; PWA<br>GPS &middot; Fotos &middot; Offline</p></div>
      <span class="farr reveal fade" style="--d:.7s">&#9656;</span>
      <div class="fnode reveal up" style="--d:.60s;--c:var(--green)"><span class="fstep">4</span><div class="flogos">{pg}{neon}</div><h4>Banco</h4><p>PostgreSQL &middot; Neon<br>Consolidacao</p></div>
      <span class="farr reveal fade" style="--d:.8s">&#9656;</span>
      <div class="fnode reveal up" style="--d:.70s;--c:var(--blue)"><span class="fstep">5</span><div class="flogos">{sap}</div><h4>Retorno SAP</h4><p>IW47 &middot; Baixas<br>em massa</p></div>
    </div>
  </div>
</section>'''.format(**_s4))

# ===== S5 mapa real (baixada_patios) =====
S.append('''
<section class="slide s5 has-photo">
  <div class="mapwrap"><div class="mapimg" style="--img:url(%(mapa)s);"></div>
    <div class="geofence" style="left:70.78%%;top:81.11%%;"><span class="gf-tag">CERCA 2,0 KM</span></div>
    <div class="gmark" style="left:88.83%%;top:9.51%%;--c:var(--cyan);--gd:.45s"><div class="disc"></div><div class="lab"><span class="t">Paranapiacaba</span><span class="s">Serra &middot; Km 0</span></div></div>
    <div class="gmark" style="left:67.03%%;top:20.94%%;--c:var(--gold);--gd:.6s"><div class="disc"></div><div class="lab"><span class="t">Serra do Mourao</span><span class="s">Patio</span></div></div>
    <div class="gmark" style="left:55.99%%;top:29.0%%;--c:var(--cyan);--gd:.75s"><div class="disc"></div><div class="lab"><span class="t">Cubatao</span><span class="s">Entroncamento</span></div></div>
    <div class="gmark" style="left:66.83%%;top:64.26%%;--c:var(--gold);--gd:.9s"><div class="disc"></div><div class="lab"><span class="t">Guarapa</span><span class="s">Patio</span></div></div>
    <div class="gmark" style="left:70.78%%;top:81.11%%;--c:var(--rail);--gd:1.05s"><div class="disc"></div><div class="lab"><span class="t">Ilha Barnabe</span><span class="s">Ativo &middot; Prioridade Muito Alta</span></div></div>
  </div>
  <div class="mappanel">
    <p class="kicker reveal left" style="--d:.05s">A Malha Real &middot; Baixada Santista</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da coordenada<br>ao <span class="grad">ativo</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s;max-width:560px;">Cada trilho, patio e ativo eletroeletronico georreferenciado a partir das <b>coordenadas fixas</b> da malha. O <b>mesmo GPS</b> que roteiriza o tecnico valida a baixa &mdash; dentro da <b>cerca de 2,0 km</b> do ativo.</p>
    <div class="reveal up" style="--d:.34s;margin-top:24px;display:flex;flex-direction:column;gap:11px;">
      <span class="pill"><span class="d cyan"></span><b>Trilha GPS</b> &middot; malha ferroviaria real</span>
      <span class="pill"><span class="d gold"></span><b>Patios</b> &middot; entroncamentos e bases</span>
      <span class="pill"><span class="d rail"></span><b>Ativo</b> &middot; cerca de 2,0 km &middot; geofencing</span>
    </div>
    <div class="reveal up" style="--d:.46s;margin-top:26px;display:flex;gap:40px;">
      <div class="stat"><b class="num" data-count="54" data-delay="300">0</b><span>ativos georreferenciados</span></div>
      <div class="stat"><b class="num" data-count="2.0" data-decimals="1" data-suffix=" km" data-delay="500">0</b><span>cerca por ativo</span></div>
      <div class="stat"><b class="num" data-count="100" data-suffix="%%" data-delay="700">0</b><span>GPS obrigatorio</span></div>
    </div>
  </div>
</section>''' % ASSETS)

# ===== S6 antes/depois (infografico) =====
S.append('''
<section class="slide s6">
  <div class="slide-inner">
    <p class="kicker amber reveal left" style="--d:.05s">Roteirizacao Inteligente</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da <span class="grad-rail">lista de OS</span> para a <span class="grad">geografia</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O tecnico deixa de escolher no papel. O sistema posiciona, calcula e agrupa por proximidade.</p>
    <div class="imp-maps">
      <div class="imp-map atual reveal left" style="--d:.5s">
        <span class="im-cap"><i class="d rail"></i>Antes &middot; escolha manual</span>
        <ul class="im-list">
          <li><span class="ic">&#8801;</span>Lista de OS sem ordem geografica</li>
          <li><span class="ic">&#129300;</span>Escolha manual do proximo ativo</li>
          <li><span class="ic">&#8617;</span>Deslocamentos improdutivos e cruzados</li>
          <li><span class="ic">&#128100;</span>Dependente da experiencia individual</li>
        </ul>
        <span class="im-foot">&#10007; percurso nao otimizado</span>
      </div>
      <span class="imp-arrow reveal fade" style="--d:.7s">&#9656;&#9656;&#9656;</span>
      <div class="imp-map sol reveal right" style="--d:.6s">
        <span class="im-cap"><i class="d cyan"></i>Depois &middot; roteirizacao geografica</span>
        <ul class="im-list">
          <li><span class="ic">&#128205;</span>Posicionamento geografico de cada ativo</li>
          <li><span class="ic">&#128208;</span>Calculo de distancia real (Haversine)</li>
          <li><span class="ic">&#11041;</span>Agrupamento operacional por proximidade</li>
          <li><span class="ic">&#129517;</span>Execucao na sequencia mais eficiente</li>
        </ul>
        <span class="im-foot">&#10003; menos deslocamento &middot; mais ativos/dia</span>
      </div>
    </div>
    <div class="imp-insight reveal fade" style="--d:.9s"><span>A proximidade vira <b>criterio sistemico</b> &mdash; a decisao de rota sai da cabeca do tecnico e passa a ser <b class="cy">reproduzivel</b>.</span></div>
  </div>
</section>''')

# ===== S7 cascade priorizacao (infografico) =====
S.append('''
<section class="slide s7">
  <div class="slide-inner">
    <p class="kicker rail reveal left" style="--d:.05s">Motor de Priorizacao &middot; Decisao Sistemica</p>
    <h2 class="slide-title reveal up" style="--d:.13s">O tecnico nao decide <span class="grad-rail">o que e mais importante</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">Cinco niveis em cascata. Atividades criticas <b>bloqueiam</b> as inferiores do mesmo grupo operacional.</p>
    <div class="cascade">
      <div class="crow lock reveal up" style="--d:.30s;--c:var(--rail);--w:100%%"><div class="cbar"></div><span class="lvl">Nivel 1</span><span class="pio">&#128737;</span><div><h4>Seguranca</h4><p>Risco a pessoas e a operacao vem sempre primeiro.</p></div><span class="bignum">1</span></div>
      <div class="crow reveal up" style="--d:.40s;--c:var(--gold);--w:84%%"><div class="cbar"></div><span class="lvl">Nivel 2</span><span class="pio">&#128295;</span><div><h4>Confiabilidade</h4><p>Ativos que sustentam a disponibilidade da malha.</p></div><span class="bignum">2</span></div>
      <div class="crow reveal up" style="--d:.50s;--c:var(--gold-2);--w:68%%"><div class="cbar"></div><span class="lvl">Nivel 3</span><span class="pio">&#9888;</span><div><h4>Criticidade</h4><p>Grau de impacto do ativo na operacao.</p></div><span class="bignum">3</span></div>
      <div class="crow reveal up" style="--d:.60s;--c:var(--cyan);--w:52%%"><div class="cbar"></div><span class="lvl">Nivel 4</span><span class="pio">&#128205;</span><div><h4>Proximidade</h4><p>Entre iguais, o mais proximo e priorizado.</p></div><span class="bignum">4</span></div>
      <div class="crow reveal up" style="--d:.70s;--c:var(--blue);--w:36%%"><div class="cbar"></div><span class="lvl">Nivel 5</span><span class="pio">&#9201;</span><div><h4>Atraso Operacional</h4><p>O que esta atrasado sobe na fila.</p></div><span class="bignum">5</span></div>
    </div>
  </div>
</section>'''.replace('%%','%'))

# ===== S8 equacao de portas (infografico, enxuto) =====
S.append('''
<section class="slide s8">
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker green reveal left" style="--d:.05s">Governanca da Baixa &middot; Regra Sistemica</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Uma baixa so e aceita se <span class="grad-green">todas as portas</span> passarem</h2>
    <p class="slide-lead reveal up" style="--d:.22s">A validacao nao e opiniao: e uma cadeia de condicoes verificadas pelo servidor antes de gravar.</p>
    <div class="imp-calc">
      <div class="imp-factor reveal up" style="--d:.34s"><div class="fmk">&#128752;</div><b>GPS valido</b><span>coordenada do hardware<br><i>(0,0) rejeitada &middot; HTTP 400</i></span></div>
      <span class="imp-op reveal fade" style="--d:.42s">&times;</span>
      <div class="imp-factor reveal up" style="--d:.46s"><div class="fmk">&#128205;</div><b class="fnum num" data-count="2.0" data-decimals="1" data-prefix="&le; " data-suffix=" km" data-delay="500">0</b><span>dentro da cerca<br><i>Haversine &middot; geofencing</i></span></div>
      <span class="imp-op reveal fade" style="--d:.54s">&times;</span>
      <div class="imp-factor reveal up" style="--d:.58s"><div class="fmk">&#128247;</div><b>Foto</b><span>evidencia tratada<br><i>Pillow &middot; RGB &middot; q75</i></span></div>
      <span class="imp-op reveal fade" style="--d:.66s">&times;</span>
      <div class="imp-factor reveal up" style="--d:.70s"><div class="fmk">&#128273;</div><b class="fnum num" data-count="12" data-suffix=" h" data-delay="700">0</b><span>token valido<br><i>sessao HMAC</i></span></div>
      <span class="imp-eq reveal fade" style="--d:.8s">=</span>
      <div class="imp-result reveal scale" style="--d:.86s"><span class="ir-ico">&#10003;</span><div class="ir-tx"><span class="ir-lab">Baixa auditavel</span><b>Aceita &amp; rastreavel</b></div></div>
    </div>
    <div class="imp-insight reveal fade" style="--d:1.05s;max-width:1180px;"><span>Cada baixa carrega <b>quem, onde, quando e a prova</b> &mdash; e volta ao SAP como informacao estruturada, nao como digitacao manual.</span></div>
  </div>
</section>''')

# ===== S9 offline journey (novo estilo, bg_yard) =====
S.append('''
<section class="slide s9 has-photo">
  <div class="sbg" style="--img:url(%(bg_yard)s); --veil:linear-gradient(180deg, rgba(3,8,18,.86) 0%%, rgba(3,8,18,.6) 40%%, rgba(3,8,18,.82) 100%%);"><i></i></div>
  <div class="slide-inner">
    <p class="kicker cyan reveal left" style="--d:.05s">Continuidade Operacional</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Funciona onde <span class="grad-cyan">nao ha sinal</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">Na serra, no tunel, no patio remoto &mdash; a operacao nao para. O que foi feito sincroniza depois, sem duplicar.</p>
    <div class="ojourney">
      <div class="ostep reveal up" style="--d:.34s;--c:var(--rail)"><span class="ost">SEM REDE</span><div class="oi">&#128245;</div><h4>Campo sem sinal</h4><p>Serra, tunel ou patio remoto. Rede ausente deixa de ser bloqueio.</p></div>
      <span class="oconn reveal fade" style="--d:.5s">&#9656;</span>
      <div class="ostep reveal up" style="--d:.44s;--c:var(--cyan)"><span class="ost">LOCAL</span><div class="oi">&#128241;</div><h4>PWA + IndexedDB</h4><p>App instalavel grava GPS, foto e baixa em fila local no dispositivo.</p></div>
      <span class="oconn reveal fade" style="--d:.6s">&#9656;</span>
      <div class="ostep reveal up" style="--d:.54s;--c:var(--gold)"><span class="ost">SINAL VOLTA</span><div class="oi">&#128246;</div><h4>Sincroniza</h4><p>Ao recuperar rede, os pacotes sobem para o servidor automaticamente.</p></div>
      <span class="oconn reveal fade" style="--d:.7s">&#9656;</span>
      <div class="ostep reveal up" style="--d:.64s;--c:var(--green)"><span class="ost">SEGURO</span><div class="oi">&#128737;</div><h4>Sem duplicar</h4><p>Idempotencia (ON CONFLICT) garante que nada e gravado duas vezes.</p></div>
    </div>
    <div class="imp-insight reveal fade" style="--d:.85s"><span>O endpoint <b>/sincronizar_baixa_offline</b> reconcilia o campo com o corporativo &mdash; a rede volta e o trabalho ja esta la.</span></div>
  </div>
</section>''' % ASSETS)

# ===== S10 honeycomb (conexao disruptiva) =====
S.append('''
<section class="slide s10">
  <div class="slide-inner">
    <p class="kicker green reveal left" style="--d:.05s">Governanca Operacional</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Confianca e boa; <span class="grad-green">controle sistemico</span> e a prova de falhas</h2>
    <div class="honey">
      <div class="hex core" style="left:50%%;top:50%%;--c:var(--green);--hd:.3s"><div class="hi">&#128737;</div><h4>Governanca</h4><span class="hs">a prova de falhas</span></div>
      <div class="hex reveal" style="left:29.5%%;top:23%%;--c:var(--cyan);--hd:.42s"><div class="hi">&#128272;</div><h4>Login Controlado</h4><span class="hs">Token 12h</span></div>
      <div class="hex" style="left:50%%;top:14%%;--c:var(--gold);--hd:.5s"><div class="hi">&#128101;</div><h4>Perfis de Acesso</h4><span class="hs">Papeis</span></div>
      <div class="hex" style="left:70.5%%;top:23%%;--c:var(--cyan);--hd:.58s"><div class="hi">&#128221;</div><h4>Registro de Acessos</h4><span class="hs">Auditoria</span></div>
      <div class="hex" style="left:70.5%%;top:77%%;--c:var(--gold-2);--hd:.66s"><div class="hi">&#128205;</div><h4>Geofencing</h4><span class="hs">2,0 km</span></div>
      <div class="hex" style="left:50%%;top:86%%;--c:var(--green);--hd:.74s"><div class="hi">&#128248;</div><h4>Evidencia Fotografica</h4><span class="hs">por baixa</span></div>
      <div class="hex" style="left:29.5%%;top:77%%;--c:var(--rail);--hd:.82s"><div class="hi">&#128680;</div><h4>Controle de Execucao</h4><span class="hs">Travas</span></div>
      <div class="hex" style="left:19%%;top:50%%;--c:var(--cyan);--hd:.9s"><div class="hi">&#128449;</div><h4>Historico Auditavel</h4><span class="hs">Consultavel</span></div>
      <div class="hex" style="left:81%%;top:50%%;--c:var(--green);--hd:.98s"><div class="hi">&#128752;</div><h4>GPS Obrigatorio</h4><span class="hs">Hardware</span></div>
    </div>
  </div>
</section>'''.replace('%%','%'))

# ===== S11 pipeline SAP (infografico) =====
_s11 = {'sap': chip('sap'), 'py': chip('python'), 'fast': chip('fastapi'), 'stream': chip('streamlit')}
S.append('''
<section class="slide s11">
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker reveal left" style="--d:.05s">Integracao de Ciclo Completo &middot; SAP</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Entra plano, sai <span class="grad">baixa estruturada</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">Fim do retrabalho de digitacao manual de relatorios no escritorio.</p>
    <div class="pipe">
      <div class="pcol in reveal left" style="--d:.34s"><span class="ptag tag o-cyan">Entrada</span><h4>Planejamento</h4><p>OS programadas e plano de manutencao vindos do SAP.</p><div class="plogos">{sap}</div></div>
      <span class="pchev reveal fade" style="--d:.5s">&#9656;</span>
      <div class="pcol pr reveal up" style="--d:.44s"><span class="ptag tag o-gold">Processamento</span><h4>Regras operacionais</h4><p>Priorizacao, roteirizacao e consolidacao da execucao de campo.</p><div class="plogos">{py}{fast}{stream}</div></div>
      <span class="pchev reveal fade" style="--d:.6s">&#9656;</span>
      <div class="pcol out reveal right" style="--d:.54s"><span class="ptag tag" style="color:var(--green);border:1px solid rgba(55,224,126,.4)">Saida</span><h4>Arquivo SAP &middot; IW47</h4><p>Baixas em massa e informacoes estruturadas de volta ao corporativo.</p><div class="plogos">{sap}</div></div>
    </div>
    <div class="reveal up" style="--d:.72s;margin-top:26px;display:flex;gap:14px;flex-wrap:wrap;justify-content:center;">
      <span class="pill"><b>/publicar_pacote</b> &middot; gera o pacote do dia</span>
      <span class="pill"><b>/pacote/&#123;id&#125;</b> &middot; consulta e download</span>
      <span class="pill"><b>/health</b> &middot; disponibilidade do servico</span>
    </div>
  </div>
</section>'''.format(**_s11))

# ===== S12 stack com LOGOS (infografico) =====
_s12 = {
    'stream': chip('streamlit'), 'pwa': chip('pwa'), 'py': chip('python'), 'fast': chip('fastapi'),
    'render': chip('render','logo-chip dark'), 'pg': chip('postgres'), 'neon': chip('neon'), 'sup': chip('supabase'), 'html': chip('html5'),
}
S.append('''
<section class="slide s12">
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker reveal left" style="--d:.05s">Arquitetura Tecnologica &middot; Corporativa</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Stack <span class="grad">enxuta</span>, pronta para escalar</h2>
    <div class="stackgrid">
      <div class="scard reveal up" style="--d:.30s;--c:var(--cyan)">{stream}<div class="sc-tx"><h4>Front-end</h4><b>Streamlit + PWA</b></div></div>
      <div class="scard reveal up" style="--d:.36s;--c:var(--gold)">{fast}<div class="sc-tx"><h4>Back-end</h4><b>Python &middot; FastAPI</b></div></div>
      <div class="scard reveal up" style="--d:.42s;--c:var(--violet)">{render}<div class="sc-tx"><h4>Hospedagem</h4><b>Render</b></div></div>
      <div class="scard reveal up" style="--d:.48s;--c:var(--green)">{pg}<div class="sc-tx"><h4>Banco</h4><b>PostgreSQL &middot; Neon</b></div></div>
      <div class="scard reveal up" style="--d:.54s;--c:var(--green)">{neon}<div class="sc-tx"><h4>Serverless</h4><b>Neon</b></div></div>
      <div class="scard reveal up" style="--d:.60s;--c:var(--green)">{sup}<div class="sc-tx"><h4>Storage fotos</h4><b>Supabase</b></div></div>
      <div class="scard reveal up" style="--d:.66s;--c:var(--gold-2)">{html}<div class="sc-tx"><h4>Offline</h4><b>HTML5 &middot; IndexedDB</b></div></div>
      <div class="scard reveal up" style="--d:.72s;--c:var(--cyan)">{pwa}<div class="sc-tx"><h4>Distribuicao</h4><b>PWA HTTPS</b></div></div>
    </div>
    <div class="reveal fade" style="--d:.86s;margin-top:24px;display:flex;gap:14px;flex-wrap:wrap;">
      <span class="pill"><span class="d green"></span><b>Seguranca</b> &middot; HTTPS + API Key</span>
      <span class="pill"><span class="d cyan"></span><b>Geo</b> &middot; GPS HTML5 &middot; Haversine</span>
    </div>
  </div>
</section>'''.format(**_s12))

# ===== S13 beneficios (tiles infografico) =====
S.append('''
<section class="slide s13">
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker green reveal left" style="--d:.05s">Beneficios para a Malha</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Menos improviso, <span class="grad-green">mais aderencia</span></h2>
    <div class="btiles">
      <div class="btile reveal up" style="--d:.30s;--c:var(--green)"><div class="bt-ic">&#129517;</div><h4>Menos deslocamentos improdutivos</h4><p>Roteirizacao por proximidade encurta o trajeto do dia.</p></div>
      <div class="btile reveal up" style="--d:.38s;--c:var(--green)"><div class="bt-ic">&#128119;</div><h4>Melhor uso das equipes</h4><p>Mais ativos atendidos com o mesmo efetivo.</p></div>
      <div class="btile reveal up" style="--d:.46s;--c:var(--cyan)"><div class="bt-ic">&#128203;</div><h4>Maior aderencia ao plano</h4><p>Execucao alinhada ao que foi programado no SAP.</p></div>
      <div class="btile reveal up" style="--d:.54s;--c:var(--cyan)"><div class="bt-ic">&#127919;</div><h4>Priorizacao automatica</h4><p>O critico sobe na fila sem depender de julgamento.</p></div>
      <div class="btile reveal up" style="--d:.62s;--c:var(--gold)"><div class="bt-ic">&#128279;</div><h4>Evidencia rastreavel</h4><p>Foto, GPS e horario atrelados a cada baixa.</p></div>
      <div class="btile reveal up" style="--d:.70s;--c:var(--gold)"><div class="bt-ic">&#128202;</div><h4>Base para analytics</h4><p>Dados estruturados abrem caminho para inteligencia preditiva.</p></div>
    </div>
  </div>
</section>''')

# ===== S14 roadmap (infografico, malha bg leve) =====
S.append('''
<section class="slide s14 has-photo">
  <div class="sbg" style="--img:url(%(malha)s); --veil:linear-gradient(160deg, rgba(3,8,18,.9) 0%%, rgba(3,8,18,.82) 55%%, rgba(3,8,18,.92) 100%%);"><i></i></div>
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker reveal left" style="--d:.05s">Evolucao &middot; Proximos Passos</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da base solida a <span class="grad">inteligencia preditiva</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O que ja esta no ar sustenta a operacao hoje; a evolucao amplia governanca, visao executiva e recomendacao automatica.</p>
    <div class="tl">
      <div class="tstep reveal up" style="--d:.30s;--c:var(--green)"><div class="tdot"></div><div style="font-size:26px">&#128737;</div><h4>Governanca operacional</h4><span class="tst" style="color:var(--green)">HOJE</span></div>
      <div class="tstep reveal up" style="--d:.40s;--c:var(--green)"><div class="tdot"></div><div style="font-size:26px">&#129517;</div><h4>Roteirizacao + GPS</h4><span class="tst" style="color:var(--green)">HOJE</span></div>
      <div class="tstep reveal up" style="--d:.50s;--c:var(--green)"><div class="tdot"></div><div style="font-size:26px">&#128245;</div><h4>PWA Offline + SAP</h4><span class="tst" style="color:var(--green)">HOJE</span></div>
      <div class="tstep reveal up" style="--d:.60s;--c:var(--gold)"><div class="tdot"></div><div style="font-size:26px">&#127970;</div><h4>Hospedagem corp. &middot; SSO/AD</h4><span class="tst" style="color:var(--gold)">CURTO</span></div>
      <div class="tstep reveal up" style="--d:.70s;--c:var(--gold-2)"><div class="tdot"></div><div style="font-size:26px">&#128202;</div><h4>Dashboards executivos</h4><span class="tst" style="color:var(--gold-2)">MEDIO</span></div>
      <div class="tstep reveal up" style="--d:.80s;--c:var(--cyan)"><div class="tdot"></div><div style="font-size:26px">&#129302;</div><h4>Preditiva &middot; recomendacao de rotas</h4><span class="tst" style="color:var(--cyan)">FUTURO</span></div>
    </div>
  </div>
</section>''' % ASSETS)

# ===== S15 encerramento (bg_port) =====
S.append('''
<section class="slide end s15 has-photo">
  <div class="end-photo"><i style="--img:url(%(bg_port)s);background-image:url(%(bg_port)s);"></i></div>
  <div class="slide-inner" style="justify-content:center;">
    <p class="kicker reveal down" style="--d:.05s">SGO Eletroeletronica MRS</p>
    <h2 class="reveal up" style="--d:.2s;font-size:76px;font-weight:800;line-height:1.02;letter-spacing:-.02em;margin-top:18px;">Mais do que um <span class="grad">aplicativo</span></h2>
    <p class="reveal up" style="--d:.4s;font-size:26px;color:var(--soft);margin-top:20px;max-width:1000px;">Uma camada digital entre <span style="color:var(--cyan);font-weight:800;">Planejamento</span><span style="color:var(--dim);margin:0 6px;">&rarr;</span><span style="color:var(--gold);font-weight:800;">Malha</span><span style="color:var(--dim);margin:0 6px;">&rarr;</span><span style="color:var(--green);font-weight:800;">Execucao</span><span style="color:var(--dim);margin:0 6px;">&rarr;</span><span style="color:var(--gold-2);font-weight:800;">Governanca</span><span style="color:var(--dim);margin:0 6px;">&rarr;</span><span style="color:var(--blue);font-weight:800;">SAP</span>.</p>
    <p class="reveal up" style="--d:.7s;font-size:23px;color:var(--white);margin-top:34px;">Transformando conhecimento operacional em <span class="grad">inteligencia sistemica</span>.</p>
    <p class="reveal fade" style="--d:1s;font-family:var(--mono);font-size:15px;letter-spacing:.14em;color:var(--dim);margin-top:44px;text-transform:uppercase;">Obrigado</p>
  </div>
</section>''' % ASSETS)

# ---------------------------------------------------------------- CHROME + JS
CHROME = '''
  </div>
</div>
<div class="hud-corner"><span class="brand"><b>SGO</b> Eletroeletronica MRS</span></div>
<div class="deck-progress"><span id="progressBar"></span></div>
<div class="deck-dots" id="deckDots"></div>
<div class="deck-controls">
  <button id="btnPrev" class="dc-btn" aria-label="Anterior">&#9666;</button>
  <button id="btnNext" class="dc-btn" aria-label="Proximo">&#9656;</button>
  <button id="btnFs" class="dc-btn fs" aria-label="Tela cheia">&#9974;</button>
</div>
<div class="page-counter"><b id="curNum">01</b><i>/</i><span id="totNum">15</span></div>
<div class="kb-hint" id="kbHint">use <b>&larr; &rarr;</b> para navegar &middot; <b>F</b> tela cheia</div>
'''

JS = r'''<script>
'use strict';
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const fmtInt = v => Math.round(v).toLocaleString('pt-BR');
const fmtDec = (v,d) => v.toFixed(d).replace('.', ',');
function formatCounter(el,v){ const d=el.dataset; let s;
  if(d.money==='1') s=fmtInt(v); else if(+(d.decimals||0)>0) s=fmtDec(v,+d.decimals); else s=fmtInt(v);
  return (d.prefix||'')+s+(d.suffix||''); }
function animateCounter(el){ const d=el.dataset; const to=parseFloat(d.count);
  const from=d.from!==undefined?parseFloat(d.from):0; const dur=+(d.dur||1400); const t0=performance.now();
  function frame(now){ const t=Math.min(1,(now-t0)/dur); const e=1-Math.pow(1-t,3);
    el.textContent=formatCounter(el,from+(to-from)*e); if(t<1) requestAnimationFrame(frame); else el.textContent=formatCounter(el,to); }
  requestAnimationFrame(frame); }
function runCounters(slide){ slide.querySelectorAll('[data-count]').forEach(el=>{
  const start=el.dataset.from!==undefined?parseFloat(el.dataset.from):0; el.textContent=formatCounter(el,start);
  if(REDUCED){ el.textContent=formatCounter(el,parseFloat(el.dataset.count)); return; }
  setTimeout(()=>animateCounter(el), +(el.dataset.delay||0)); }); }

/* ---- fundo de particulas (pontos se conectando) ---- */
function initNet(){
  const cv=document.getElementById('netbg'); if(!cv) return; const ctx=cv.getContext('2d');
  const W=1920,H=1080; cv.width=W; cv.height=H;
  const N=REDUCED?0:70, MAX=170;
  const cols=['57,214,232','243,177,60','155,123,255'];
  const pts=[]; for(let i=0;i<N;i++){ pts.push({x:Math.random()*W,y:Math.random()*H,
    vx:(Math.random()-.5)*.35, vy:(Math.random()-.5)*.35, r:Math.random()*1.8+1.1,
    c:cols[Math.floor(Math.random()*cols.length)]}); }
  function step(){
    ctx.clearRect(0,0,W,H);
    for(let i=0;i<N;i++){ const p=pts[i]; p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>W) p.vx*=-1; if(p.y<0||p.y>H) p.vy*=-1; }
    for(let i=0;i<N;i++){ for(let j=i+1;j<N;j++){ const a=pts[i],b=pts[j];
      const dx=a.x-b.x, dy=a.y-b.y, d=Math.hypot(dx,dy);
      if(d<MAX){ const o=(1-d/MAX)*.32; ctx.strokeStyle='rgba('+a.c+','+o.toFixed(3)+')';
        ctx.lineWidth=.7; ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); } } }
    for(let i=0;i<N;i++){ const p=pts[i]; ctx.fillStyle='rgba('+p.c+',.72)';
      ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,6.2832); ctx.fill(); }
    requestAnimationFrame(step);
  }
  if(N>0) step();
}

class Deck{
  constructor(){
    this.stage=document.getElementById('deckStage');
    this.slides=Array.from(document.querySelectorAll('.slide'));
    this.total=this.slides.length; this.current=0; this.wheelLock=false;
    this.btnPrev=document.getElementById('btnPrev'); this.btnNext=document.getElementById('btnNext'); this.btnFs=document.getElementById('btnFs');
    this.curNum=document.getElementById('curNum'); this.totNum=document.getElementById('totNum');
    this.bar=document.getElementById('progressBar'); this.dotsWrap=document.getElementById('deckDots'); this.kbHint=document.getElementById('kbHint');
    this.totNum.textContent=String(this.total).padStart(2,'0');
    this.buildDots(); this.bindEvents(); this.scaleStage(); this.go(0,true);
  }
  scaleStage(){ const s=Math.min(window.innerWidth/1920, window.innerHeight/1080);
    const x=(window.innerWidth-1920*s)/2, y=(window.innerHeight-1080*s)/2;
    this.stage.style.transform='translate('+x+'px, '+y+'px) scale('+s+')'; }
  buildDots(){ this.dots=this.slides.map((_,i)=>{ const b=document.createElement('button');
    b.setAttribute('aria-label','Slide '+(i+1)); b.addEventListener('click',()=>this.go(i)); this.dotsWrap.appendChild(b); return b; }); }
  bindEvents(){
    window.addEventListener('resize',()=>this.scaleStage());
    this.btnPrev.addEventListener('click',()=>this.prev()); this.btnNext.addEventListener('click',()=>this.next());
    if(this.btnFs) this.btnFs.addEventListener('click',()=>this.toggleFullscreen());
    document.addEventListener('keydown',e=>{ switch(e.key){
      case 'ArrowRight': case ' ': case 'PageDown': case 'ArrowDown': e.preventDefault(); this.next(); break;
      case 'ArrowLeft': case 'PageUp': case 'ArrowUp': e.preventDefault(); this.prev(); break;
      case 'Home': e.preventDefault(); this.go(0); break; case 'End': e.preventDefault(); this.go(this.total-1); break;
      case 'f': case 'F': this.toggleFullscreen(); break; } });
    window.addEventListener('wheel',e=>{ e.preventDefault(); if(this.wheelLock||Math.abs(e.deltaY)<14) return;
      this.wheelLock=true; (e.deltaY>0)?this.next():this.prev(); setTimeout(()=>(this.wheelLock=false),820); },{passive:false});
    let tx=0,ty=0; window.addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY;},{passive:true});
    window.addEventListener('touchend',e=>{ const dx=e.changedTouches[0].clientX-tx, dy=e.changedTouches[0].clientY-ty;
      if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)) (dx<0?this.next():this.prev()); },{passive:true});
  }
  go(i,initial){ i=Math.max(0,Math.min(this.total-1,i)); if(i===this.current&&!initial) return;
    this.slides.forEach((s,idx)=>{ if(idx!==i) s.classList.remove('active','visible'); });
    const cur=this.slides[i]; cur.classList.add('active');
    requestAnimationFrame(()=>requestAnimationFrame(()=>cur.classList.add('visible')));
    this.current=i; this.updateChrome(); runCounters(cur);
    if(!initial&&this.kbHint) this.kbHint.classList.add('hide'); }
  next(){ this.go(this.current+1); } prev(){ this.go(this.current-1); }
  updateChrome(){ this.curNum.textContent=String(this.current+1).padStart(2,'0');
    this.bar.style.width=((this.current+1)/this.total*100)+'%';
    this.btnPrev.disabled=this.current===0; this.btnNext.disabled=this.current===this.total-1;
    this.dots.forEach((d,i)=>d.classList.toggle('on',i===this.current)); }
  toggleFullscreen(){ if(!document.fullscreenElement) document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen(); else document.exitFullscreen&&document.exitFullscreen(); }
}
window.addEventListener('DOMContentLoaded',()=>{ initNet(); new Deck(); });
</script>
</body></html>'''


html = HEAD + "".join(S) + CHROME + JS
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT, "(%.2f MB)" % (len(html) / 1024 / 1024))
