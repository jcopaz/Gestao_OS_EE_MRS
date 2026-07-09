# -*- coding: utf-8 -*-
# =============================================================================
# SGO Eletroeletrônica MRS — PITCH PREMIUM (palco fixo 1920x1080, escalado)
# Motor inspirado nos decks de referência (OAE-SIM / PMAV):
#   - Palco 16:9 fixo escalado para a tela (letterbox) -> layout pixel-perfect
#   - Tipografia Manrope + Space Mono
#   - Sistema de revelação (.reveal + --d) com stagger
#   - Chrome: barra de progresso, HUD, dots, controles, contador
#   - Contadores animados (data-count), parallax, print (1 slide/página)
# Gera um HTML único e autossuficiente e abre no navegador.
# =============================================================================
import os
import webbrowser

# ---------------------------------------------------------------------------
# Ícones (feather-style, traço) — visual premium, sem depender de emojis
# ---------------------------------------------------------------------------
_ICON = {
    'sap':      '<path d="M4 7h16v10H4z"/><path d="M8 11c-1 0-2 .4-2 1.4S8 14 8 15s-1 1-2 1M18 11h-3v5M15 13h2"/>',
    'gear':     '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 12H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 5.3l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 12 3V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.4 1z"/>',
    'phone':    '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
    'db':       '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    'brain':    '<path d="M9.5 3A2.5 2.5 0 0 1 12 5.5v13a2.5 2.5 0 0 1-4.9.7A2.5 2.5 0 0 1 4 16a2.5 2.5 0 0 1-.6-3.5A2.5 2.5 0 0 1 4 8a2.5 2.5 0 0 1 2-4 2.5 2.5 0 0 1 3.5-1zM14.5 3A2.5 2.5 0 0 0 12 5.5v13a2.5 2.5 0 0 0 4.9.7A2.5 2.5 0 0 0 20 16a2.5 2.5 0 0 0 .6-3.5A2.5 2.5 0 0 0 20 8a2.5 2.5 0 0 0-2-4 2.5 2.5 0 0 0-3.5-1z"/>',
    'map':      '<path d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3z"/><path d="M9 3v15M15 6v15"/>',
    'target':   '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    'clipboard':'<rect x="8" y="3" width="8" height="4" rx="1"/><path d="M8 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 12l2 2 4-4"/>',
    'camera':   '<path d="M4 7h3l2-2h6l2 2h3v12H4z"/><circle cx="12" cy="13" r="3.5"/>',
    'route':    '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5"/>',
    'shield':   '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    'satellite':'<path d="M5 13l-2 2 4 4 2-2M13 5l6 6M15 3l6 6M13 11l-2 2M9 15l-2-2"/><circle cx="17.5" cy="6.5" r="1"/>',
    'lock':     '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    'bolt':     '<path d="M13 2 4 14h6l-1 8 9-12h-6z"/>',
    'check':    '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    'layers':   '<path d="M12 3 3 8l9 5 9-5-9-5z"/><path d="M3 13l9 5 9-5M3 18l9 5 9-5"/>',
    'cloud':    '<path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.3A3.8 3.8 0 0 1 18 18z"/>',
    'cpu':      '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    'monitor':  '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    'python':   '<path d="M12 3c-3 0-4 1.5-4 3v2h5v1H6c-2 0-3 1.5-3 4s1 4 3 4h2v-3c0-2 1.5-3 3-3h4c2 0 3-1 3-3V6c0-2-1-3-4-3z"/><circle cx="9" cy="6" r="1"/>',
    'refresh':  '<path d="M21 12a9 9 0 1 1-3-6.7M21 3v5h-5"/>',
    'clock':    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'users':    '<circle cx="9" cy="8" r="3.5"/><path d="M3 20a6 6 0 0 1 12 0M16 5a3.5 3.5 0 0 1 0 7M15 20a6 6 0 0 1 6-3"/>',
    'file':     '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    'chart':    '<path d="M4 19V5M4 19h16M8 15l3-4 3 2 4-6"/>',
    'link':     '<path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
    'wifi-off': '<path d="M2 8.8A15 15 0 0 1 22 8.8M5 12.5a10 10 0 0 1 4-2.4M15 10.2a10 10 0 0 1 4 2.3M8.5 16a5 5 0 0 1 7 0M12 20h.01M2 2l20 20"/>',
    'diamond':  '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20M9 3l3 6 3-6M8 9l4 12 4-12"/>',
    'flag':     '<path d="M5 21V4M5 4c3-2 6 2 9 0s5-1 5-1v9s-2 1-5 0-6-2-9 0"/>',
    'compass':  '<circle cx="12" cy="12" r="9"/><path d="M16 8l-2.5 5.5L8 16l2.5-5.5z"/>',
}

def sv(name, cls=''):
    c = f' class="{cls}"' if cls else ''
    return f'<svg{c} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{_ICON[name]}</svg>'

# arrow icon (fluxo)
ARROW = '<span class="flow-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>'

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = r"""
:root{
  --navy-900:#03070f; --navy-850:#050c18; --navy-800:#071426; --navy-700:#0b1f38; --navy-650:#102844;
  --cyan:#00E5FF; --teal:#19b6c4; --blue:#3b82f6;
  --amber:#F59E0B; --green:#10B981; --red:#EF4444; --violet:#A78BFA; --yellow:#ffcf4d;
  --white:#F1F6FF; --soft:#aebfda; --dim:#6f83a6; --line:rgba(120,160,220,.16);
  --stage-bg:#02050c; --slide-bg:#040a16;
  --card:linear-gradient(155deg, rgba(15,32,58,.72), rgba(6,15,30,.5));
  --card-soft:linear-gradient(155deg, rgba(13,28,52,.5), rgba(6,14,28,.32));
  --card-bd:rgba(120,160,220,.18); --shadow:0 24px 60px rgba(0,0,0,.5);
  --font:'Manrope', system-ui, sans-serif; --mono:'Space Mono', monospace;
  --t-hero:100px; --t-h2:58px; --t-lead:29px; --t-body:22px; --t-small:16px; --t-kpi:64px;
  --ease:cubic-bezier(.16,1,.3,1); --slow:cubic-bezier(.22,.61,.36,1);
  --pad-x:112px; --pad-y:86px;
}
*{ margin:0; padding:0; box-sizing:border-box; }
html,body{ width:100%; height:100%; overflow:hidden; background:var(--stage-bg);
  font-family:var(--font); color:var(--white); -webkit-font-smoothing:antialiased; }

/* ---- Palco fixo 1920x1080 escalado ---- */
.deck-viewport{ position:fixed; inset:0; overflow:hidden; background:var(--stage-bg); }
.deck-stage{ position:absolute; left:0; top:0; width:1920px; height:1080px; overflow:hidden;
  transform-origin:0 0; background:var(--slide-bg); }
.slide{ position:absolute; inset:0; width:1920px; height:1080px; overflow:hidden;
  visibility:hidden; opacity:0; pointer-events:none; background:var(--slide-bg); }
.slide.active,.slide.visible{ visibility:visible; opacity:1; pointer-events:auto; z-index:1; }

/* ---- Fundo comum: gradientes + grade técnica + orbes ---- */
.slide{ background:
  radial-gradient(1100px 760px at 8% 0%, rgba(0,229,255,.10) 0%, transparent 56%),
  radial-gradient(1200px 820px at 100% 100%, rgba(59,130,246,.12) 0%, transparent 60%),
  linear-gradient(160deg,#061226 0%, var(--slide-bg) 55%, #03060f 100%); }
.slide::before{ content:""; position:absolute; inset:0; z-index:0; pointer-events:none;
  background-image:linear-gradient(rgba(59,130,246,.05) 1px,transparent 1px),
                   linear-gradient(90deg, rgba(59,130,246,.05) 1px,transparent 1px);
  background-size:66px 66px;
  mask-image:radial-gradient(130% 105% at 50% 30%, #000 26%, transparent 84%); }
.orb{ position:absolute; border-radius:50%; filter:blur(64px); opacity:.5; z-index:0; pointer-events:none; }
.slide-inner{ position:absolute; inset:0; z-index:2; padding:var(--pad-y) var(--pad-x); display:flex; flex-direction:column; }

/* ---- Chrome ---- */
.progress{ position:fixed; top:0; left:0; right:0; height:4px; background:rgba(255,255,255,.06); z-index:1200; }
.progress .bar{ height:100%; width:0; background:linear-gradient(90deg,var(--cyan),var(--blue),var(--green));
  box-shadow:0 0 16px rgba(0,229,255,.7); transition:width .55s var(--ease); }
.hud{ position:fixed; top:22px; right:150px; z-index:1200; font-family:var(--mono); font-size:13px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--dim); }
.hud b{ color:var(--cyan); font-weight:700; }
.counter{ position:fixed; right:30px; bottom:26px; z-index:1200; font-family:var(--mono); font-size:16px; color:var(--soft); letter-spacing:.12em; }
.counter b{ color:var(--cyan); font-weight:700; }
.brandtag{ position:fixed; left:30px; bottom:26px; z-index:1200; font-family:var(--mono); font-size:14px; color:var(--dim); letter-spacing:.18em; text-transform:uppercase; }
.navbtn{ position:fixed; top:50%; transform:translateY(-50%); z-index:1200; width:54px; height:54px; border-radius:50%;
  background:rgba(8,18,34,.55); border:1px solid rgba(0,229,255,.28); color:var(--soft); cursor:pointer;
  display:flex; align-items:center; justify-content:center; backdrop-filter:blur(8px); transition:all .3s var(--ease); opacity:.4; }
.navbtn:hover{ opacity:1; border-color:var(--cyan); color:var(--cyan); box-shadow:0 0 28px -6px var(--cyan); }
.navbtn.prev{ left:26px } .navbtn.next{ right:26px } .navbtn svg{ width:22px; height:22px; }
.dots{ position:fixed; left:50%; bottom:26px; transform:translateX(-50%); z-index:1200; display:flex; gap:10px; }
.dots b{ width:9px; height:9px; border-radius:50%; background:rgba(255,255,255,.22); cursor:pointer; transition:all .3s var(--ease); }
.dots b.on{ background:var(--cyan); box-shadow:0 0 12px var(--cyan); width:26px; border-radius:6px; }
.fsbtn{ position:fixed; right:30px; top:16px; z-index:1200; width:40px; height:40px; border-radius:10px; cursor:pointer;
  background:rgba(8,18,34,.6); border:1px solid rgba(0,229,255,.3); color:var(--soft); display:flex; align-items:center; justify-content:center; transition:all .3s var(--ease); opacity:.5; }
.fsbtn:hover{ opacity:1; color:var(--cyan); border-color:var(--cyan); }
.fsbtn svg{ width:20px; height:20px; }
.kb-hint{ position:fixed; left:34px; top:20px; z-index:1200; font-family:var(--mono); font-size:12px; letter-spacing:.1em; color:var(--dim); transition:opacity .6s; }
.kb-hint kbd{ font-size:11px; padding:3px 7px; border-radius:6px; border:1px solid var(--line); background:rgba(120,160,220,.08); color:var(--soft); }
.kb-hint.hide{ opacity:0; }

/* ---- Reveal ---- */
.reveal{ opacity:0; transform:translateY(28px); transition:opacity .7s var(--ease), transform .7s var(--ease); transition-delay:var(--d,0s); }
.slide.visible .reveal{ opacity:1; transform:none; }
.reveal.fade{ transform:none; } .reveal.left{ transform:translateX(-34px); }
.reveal.right{ transform:translateX(40px); } .reveal.scale{ transform:scale(.92); }

/* ---- Tipografia base ---- */
.kicker{ font-family:var(--mono); font-size:16px; letter-spacing:.26em; text-transform:uppercase; color:var(--cyan); display:inline-flex; align-items:center; gap:14px; }
.kicker::before{ content:""; width:38px; height:2px; background:linear-gradient(90deg,var(--cyan),transparent); box-shadow:0 0 12px var(--cyan); }
.kicker.amber{ color:var(--amber);} .kicker.amber::before{ background:linear-gradient(90deg,var(--amber),transparent); box-shadow:0 0 12px var(--amber);}
.kicker.red{ color:var(--red);} .kicker.red::before{ background:linear-gradient(90deg,var(--red),transparent); box-shadow:0 0 12px var(--red);}
.kicker.green{ color:var(--green);} .kicker.green::before{ background:linear-gradient(90deg,var(--green),transparent); box-shadow:0 0 12px var(--green);}
.s-title{ font-weight:800; font-size:var(--t-h2); line-height:1.05; letter-spacing:-.02em; margin-top:16px; }
.s-title .grad{ background:linear-gradient(100deg,var(--cyan),var(--blue)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.s-title .amber{ color:var(--amber);} .s-title .red{ color:var(--red);} .s-title .violet{ color:var(--violet);} .s-title .green{ color:var(--green);}
.s-lead{ font-size:var(--t-lead); color:var(--soft); line-height:1.4; margin-top:18px; max-width:1320px; }
.s-lead b{ color:var(--white); font-weight:700; }

/* ---- Componentes ---- */
.card{ background:var(--card); border:1px solid var(--card-bd); border-radius:20px; padding:30px 32px;
  backdrop-filter:blur(12px); box-shadow:var(--shadow); position:relative; overflow:hidden;
  transition:transform .35s var(--ease), border-color .35s var(--ease), box-shadow .35s var(--ease); }
.card:hover{ transform:translateY(-6px); border-color:color-mix(in srgb,var(--c,var(--cyan)) 46%,transparent);
  box-shadow:0 26px 60px -18px color-mix(in srgb,var(--c,var(--cyan)) 55%,transparent); }
.card.edge{ border-left:4px solid var(--c,var(--cyan)); }
.card.top{ border-top:4px solid var(--c,var(--cyan)); }
.ico{ width:60px; height:60px; border-radius:15px; display:flex; align-items:center; justify-content:center;
  background:color-mix(in srgb,var(--c,var(--cyan)) 15%,transparent); color:var(--c,var(--cyan));
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c,var(--cyan)) 30%,transparent); }
.ico svg{ width:32px; height:32px; }
.ico.sm{ width:48px; height:48px; border-radius:12px; } .ico.sm svg{ width:26px; height:26px; }
.card h3{ font-size:24px; font-weight:800; color:var(--white); line-height:1.15; }
.card p{ font-size:17px; color:var(--soft); line-height:1.46; }
.eyebrow-c{ font-family:var(--mono); font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--c,var(--cyan)); }

.chip{ display:inline-flex; align-items:center; gap:11px; font-size:20px; color:var(--white);
  padding:14px 22px; border-radius:999px; border:1px solid color-mix(in srgb,var(--cyan) 34%,transparent);
  background:color-mix(in srgb,var(--cyan) 8%,transparent); }
.chip svg{ width:20px; height:20px; color:var(--green); }

.kpi{ background:var(--card); border:1px solid var(--card-bd); border-radius:18px; padding:24px 28px; position:relative; overflow:hidden; }
.kpi::after{ content:""; position:absolute; left:0; top:20px; bottom:20px; width:3px; border-radius:3px; background:var(--c,var(--cyan)); box-shadow:0 0 14px var(--c,var(--cyan)); }
.kpi .kv{ font-weight:800; font-size:var(--t-kpi); line-height:1; letter-spacing:-.02em; color:var(--white); }
.kpi .kl{ font-family:var(--mono); font-size:13px; letter-spacing:.12em; text-transform:uppercase; color:var(--dim); margin-top:10px; }

/* Fluxo horizontal */
.flow{ display:flex; align-items:stretch; gap:14px; width:100%; }
.flow-arrow{ flex:0 0 auto; display:flex; align-items:center; color:var(--cyan); filter:drop-shadow(0 0 7px var(--cyan)); }
.flow-arrow svg{ width:34px; height:34px; }
.node{ flex:1; border-radius:18px; padding:26px 22px; background:var(--card); border:1px solid var(--card-bd);
  display:flex; flex-direction:column; align-items:center; text-align:center; gap:12px; justify-content:center; }
.node.on{ border-color:color-mix(in srgb,var(--c,var(--cyan)) 50%,transparent); box-shadow:0 0 40px -14px var(--c,var(--cyan)); }
.node .n-ico{ width:66px; height:66px; border-radius:16px; display:flex; align-items:center; justify-content:center;
  background:color-mix(in srgb,var(--c,var(--cyan)) 16%,transparent); color:var(--c,var(--cyan)); }
.node .n-ico svg{ width:34px; height:34px; }
.node h4{ font-size:21px; font-weight:800; color:var(--white); }
.node .n-sub{ font-family:var(--mono); font-size:12.5px; letter-spacing:.06em; color:var(--soft); line-height:1.5; }

/* ladder de prioridade */
.prio{ display:flex; flex-direction:column; gap:14px; }
.prio-row{ display:flex; align-items:center; gap:20px; background:var(--card-soft); border:1px solid var(--line);
  border-left:4px solid var(--c,var(--cyan)); border-radius:14px; padding:20px 26px; }
.prio-row .lv{ font-family:var(--mono); font-weight:700; font-size:14px; letter-spacing:.14em; color:var(--c,var(--cyan)); width:88px; }
.prio-row .nm{ font-size:26px; font-weight:700; color:var(--white); }
.prio-row .bd{ margin-left:auto; color:var(--c,var(--cyan)); display:flex; }
.prio-row .bd svg{ width:24px; height:24px; }

/* radar */
.radar{ width:230px; height:230px; border-radius:50%; border:1px solid rgba(0,229,255,.3); position:relative; display:flex; align-items:center; justify-content:center; margin:0 auto; }
.radar::before{ content:""; position:absolute; inset:0; border-radius:50%; border:1px solid var(--cyan); animation:rpulse 2.4s infinite; }
.radar .rc{ width:16px; height:16px; background:var(--cyan); border-radius:50%; box-shadow:0 0 22px var(--cyan); }
.radar .tg{ width:12px; height:12px; background:var(--red); border-radius:50%; position:absolute; top:28%; right:22%; box-shadow:0 0 12px var(--red); }
@keyframes rpulse{ 0%{ transform:scale(.5); opacity:1; } 100%{ transform:scale(1.55); opacity:0; } }

/* pills capa */
.pill{ display:inline-flex; flex-direction:column; gap:4px; padding:18px 30px; border-radius:16px;
  background:var(--card-soft); border:1px solid var(--card-bd); text-align:center; }
.pill .pv{ font-weight:800; font-size:30px; color:var(--c,var(--cyan)); letter-spacing:-.01em; }
.pill .pl{ font-family:var(--mono); font-size:13px; letter-spacing:.1em; text-transform:uppercase; color:var(--soft); }

.foot-line{ margin-top:auto; padding-top:24px; border-top:1px solid var(--line); display:flex; gap:60px; align-items:flex-end; }
.foot-line .lab{ font-family:var(--mono); font-size:12.5px; letter-spacing:.2em; text-transform:uppercase; color:var(--dim); }
.foot-line .val{ font-size:21px; font-weight:600; color:var(--soft); margin-top:8px; }
.foot-line .val em{ font-style:normal; color:var(--white); }

.mono-strip{ font-family:var(--mono); font-size:16px; letter-spacing:.05em; color:var(--soft); }
.mono-strip b{ color:var(--cyan); }

ul.ck{ list-style:none; display:flex; flex-direction:column; gap:14px; }
ul.ck li{ display:flex; gap:14px; align-items:flex-start; font-size:21px; color:var(--white); line-height:1.4; }
ul.ck li svg{ width:24px; height:24px; flex:0 0 auto; margin-top:3px; color:var(--c,var(--cyan)); }
ul.ck.dim li{ color:var(--soft); }

/* grids helpers */
.g{ display:grid; gap:22px; } .g2{ grid-template-columns:1fr 1fr; } .g3{ grid-template-columns:repeat(3,1fr); } .g4{ grid-template-columns:repeat(4,1fr); }

/* print */
@media print{
  html,body{ width:1920px; height:auto; overflow:visible; background:#fff; }
  .deck-viewport{ position:static; overflow:visible; }
  .deck-stage{ position:static; width:auto; height:auto; transform:none!important; }
  .slide{ position:relative; visibility:visible!important; opacity:1!important; width:1920px; height:1080px; break-after:page; }
  .progress,.hud,.counter,.brandtag,.navbtn,.dots,.fsbtn,.kb-hint{ display:none!important; }
}
@media (prefers-reduced-motion: reduce){ *,*::before,*::after{ animation-duration:.01ms!important; transition-duration:.2s!important; } }
"""

# ---------------------------------------------------------------------------
# JS (engine)
# ---------------------------------------------------------------------------
JS = r"""
class Deck{
  constructor(){
    this.slides=Array.from(document.querySelectorAll('.slide'));
    this.i=0; this.stage=document.getElementById('deckStage'); this.bar=document.getElementById('progressBar');
    this.curEl=document.getElementById('cur');
    document.getElementById('total').textContent=String(this.slides.length).padStart(2,'0');
    this.buildDots(); this.scaleStage(); this.keys(); this.buttons(); this.touch(); this.wheel(); this.parallax();
    this.show(0); window.addEventListener('resize',()=>this.scaleStage());
    setTimeout(()=>document.getElementById('kbHint')?.classList.add('hide'),5200);
  }
  scaleStage(){ const f=Math.min(innerWidth/1920,innerHeight/1080);
    const x=(innerWidth-1920*f)/2, y=(innerHeight-1080*f)/2;
    this.stage.style.transform=`translate(${x}px,${y}px) scale(${f})`; }
  buildDots(){ const w=document.getElementById('dots');
    this.slides.forEach((_,k)=>{ const b=document.createElement('b'); b.onclick=()=>this.show(k); w.appendChild(b); });
    this.dots=Array.from(w.children); }
  keys(){ document.addEventListener('keydown',e=>{ switch(e.key){
    case 'ArrowRight': case ' ': case 'PageDown': e.preventDefault(); this.next(); break;
    case 'ArrowLeft': case 'PageUp': e.preventDefault(); this.prev(); break;
    case 'Home': e.preventDefault(); this.show(0); break;
    case 'End': e.preventDefault(); this.show(this.slides.length-1); break;
    case 'f': case 'F': this.fs(); break; } }); }
  buttons(){ document.getElementById('nextBtn').onclick=()=>this.next();
    document.getElementById('prevBtn').onclick=()=>this.prev();
    document.getElementById('fsBtn').onclick=()=>this.fs(); }
  touch(){ let x0=null; this.stage.addEventListener('touchstart',e=>x0=e.touches[0].clientX,{passive:true});
    this.stage.addEventListener('touchend',e=>{ if(x0===null)return; const dx=e.changedTouches[0].clientX-x0;
      if(Math.abs(dx)>60){ dx<0?this.next():this.prev(); } x0=null; },{passive:true}); }
  wheel(){ let lock=false; window.addEventListener('wheel',e=>{ if(lock||Math.abs(e.deltaY)<24)return;
    lock=true; e.deltaY>0?this.next():this.prev(); setTimeout(()=>lock=false,750); },{passive:true}); }
  parallax(){ window.addEventListener('mousemove',e=>{ const nx=(e.clientX/innerWidth-.5), ny=(e.clientY/innerHeight-.5);
    const a=this.slides[this.i]; if(!a)return; a.querySelectorAll('.orb').forEach((p,k)=>{ const d=(k+1)*8;
      p.style.transform=`translate(${(-nx*d).toFixed(1)}px,${(-ny*d).toFixed(1)}px)`; }); }); }
  fs(){ if(!document.fullscreenElement) document.documentElement.requestFullscreen?.(); else document.exitFullscreen?.(); }
  next(){ this.show(this.i+1); } prev(){ this.show(this.i-1); }
  show(k){ this.i=Math.max(0,Math.min(k,this.slides.length-1));
    this.slides.forEach((s,idx)=>{ const on=idx===this.i; s.classList.toggle('active',on); s.classList.toggle('visible',on); });
    this.curEl.textContent=String(this.i+1).padStart(2,'0');
    this.bar.style.width=((this.i+1)/this.slides.length*100)+'%';
    this.dots.forEach((d,idx)=>d.classList.toggle('on',idx===this.i));
    this.counters(this.slides[this.i]); }
  counters(slide){ slide.querySelectorAll('[data-count]').forEach(el=>{
    const to=parseFloat(el.dataset.count), dec=parseInt(el.dataset.dec||'0',10);
    const pre=el.dataset.prefix||'', suf=el.dataset.suffix||'', dur=parseInt(el.dataset.dur||'1400',10), delay=parseInt(el.dataset.delay||'0',10);
    const fmt=v=>pre+v.toLocaleString('pt-BR',{minimumFractionDigits:dec,maximumFractionDigits:dec})+suf;
    el.textContent=fmt(0);
    const run=()=>{ let t0=null; const tick=ts=>{ if(!t0)t0=ts; const p=Math.min((ts-t0)/dur,1), e=1-Math.pow(1-p,3);
      el.textContent=fmt(to*e); if(p<1)requestAnimationFrame(tick); else el.textContent=fmt(to); }; requestAnimationFrame(tick); };
    delay>0?setTimeout(run,delay):run(); }); }
  const_(){} }
new Deck();
"""

# ---------------------------------------------------------------------------
# Helpers de layout
# ---------------------------------------------------------------------------
def rv(d, cls=''):
    """style/class de revelação"""
    c = f' {cls}' if cls else ''
    return f'class="reveal{c}" style="--d:{d}s"'

def orbs():
    return ('<div class="orb" style="width:520px;height:520px;background:rgba(0,229,255,.16);left:-120px;top:-90px;"></div>'
            '<div class="orb" style="width:600px;height:600px;background:rgba(59,130,246,.14);right:-160px;bottom:-180px;"></div>')

SLIDES = []
def slide(html, active=False):
    SLIDES.append(f'<section class="slide{" active" if active else ""}">{orbs()}<div class="slide-inner">{html}</div></section>')

# ===========================================================================
# SLIDE 1 — Capa
# ===========================================================================
s = ''
s += f'<div style="margin:auto 0;">'
s += f'<p class="kicker" {rv(.05)}>Inteligência Operacional Aplicada à Malha</p>'
s += f'<h1 class="s-title" style="font-size:var(--t-hero);max-width:1400px;margin-top:24px;" {rv(.18)}>SGO <span class="grad">Eletroeletrônica</span> MRS</h1>'
s += f'<p class="s-lead" style="font-size:34px;margin-top:26px;" {rv(.4)}>Conectando SAP, ativos ferroviários, geolocalização e execução em campo.</p>'
s += f'<div style="display:flex;gap:20px;margin-top:44px;flex-wrap:wrap;" {rv(.6,"fade")}>'
for pv,pl,c in [('SAP','Planejamento','var(--cyan)'),('GPS','Execução em Campo','var(--amber)'),('PWA','Operação Offline','var(--green)'),('100%','Governança','var(--violet)')]:
    s += f'<div class="pill" style="--c:{c}"><span class="pv">{pv}</span><span class="pl">{pl}</span></div>'
s += '</div></div>'
s += (f'<div class="foot-line" {rv(.9,"fade")}>'
      '<div><div class="lab">Sistema</div><div class="val"><em>SGO</em> · Gestão Operacional</div></div>'
      '<div><div class="lab">Operação</div><div class="val">Eletroeletrônica <em>MRS</em></div></div>'
      '<div><div class="lab">Deploy</div><div class="val"><em>Produção</em> · 03/Jul</div></div></div>')
slide(s, active=True)

# ===========================================================================
# SLIDE 2 — O Problema
# ===========================================================================
s = ''
s += f'<p class="kicker red" {rv(.05)}>O Problema</p>'
s += f'<h2 class="s-title" {rv(.12)}>O Desafio da Manutenção em <span class="red">Malha</span></h2>'
s += f'<p class="s-lead" {rv(.2)}>A operação depende, simultaneamente, de cinco frentes de decisão.</p>'
probs = [
    ('brain','Conhecimento dos Ativos','Saber o que é cada equipamento e o que ele exige.','var(--amber)'),
    ('map','Conhecimento Geográfico','Onde estão os ativos e como se deslocar entre eles.','var(--cyan)'),
    ('target','Priorização Correta','O que atacar primeiro diante de dezenas de OS.','var(--yellow)'),
    ('clipboard','Cumprimento do Planejamento','Executar aderente ao que foi programado.','var(--blue)'),
    ('camera','Evidências da Execução','Comprovar o que foi feito, onde e quando.','var(--green)'),
]
s += '<div class="g g3" style="margin-top:46px;">'
for i,(ic,t,d,c) in enumerate(probs):
    s += (f'<div class="card edge" style="--c:{c}" {rv(round(.3+i*.09,2),"up")}>'
          f'<div class="ico sm" style="margin-bottom:16px;">{sv(ic)}</div>'
          f'<h3>{t}</h3><p style="margin-top:10px;">{d}</p></div>')
s += (f'<div class="card edge" style="--c:var(--red);display:flex;align-items:center;" {rv(.75,"up")}>'
      '<p style="font-size:21px;color:var(--white);line-height:1.45;">Hoje, parte dessa inteligência está '
      '<b style="color:var(--red)">concentrada na experiência individual</b> — um risco de continuidade para a malha.</p></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 3 — O Conceito
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>O Conceito</p>'
s += f'<h2 class="s-title" {rv(.12)}>O que é o <span class="grad">SGO</span></h2>'
s += (f'<p class="s-lead" {rv(.2)}>O SGO transforma conhecimento operacional em <b>regras sistêmicas</b>. '
      'Não é apenas um apontador de OS — é um <b>mecanismo de decisão operacional</b>.</p>')
conc = [
    ('layers','Organiza a execução','var(--cyan)'),
    ('target','Prioriza atividades críticas','var(--red)'),
    ('lock','Controla a aderência ao planejamento','var(--amber)'),
    ('camera','Registra evidências','var(--green)'),
    ('refresh','Integra os resultados ao SAP','var(--blue)'),
    ('diamond','Padroniza a boa prática','var(--violet)'),
]
s += '<div class="g g3" style="margin-top:46px;">'
for i,(ic,t,c) in enumerate(conc):
    s += (f'<div class="card" style="--c:{c};display:flex;align-items:center;gap:20px;" {rv(round(.3+i*.08,2),"up")}>'
          f'<div class="ico sm">{sv(ic)}</div><h3 style="font-size:23px;">{t}</h3></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 4 — O Ciclo
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>O Ciclo</p>'
s += f'<h2 class="s-title" {rv(.12)}>O <span class="grad">Ciclo</span> Operacional Completo</h2>'
s += f'<p class="s-lead" {rv(.2)}>Do planejamento no SAP ao retorno estruturado — com o motor do SGO no centro.</p>'
nodes = [
    ('sap','SAP','Planejamento · OS Programadas','var(--cyan)',False),
    ('gear','Motor SGO','Priorização · Regras · Geo · Governança','var(--amber)',True),
    ('phone','Campo','GPS · Fotos · Evidências · Offline','var(--green)',True),
    ('db','Banco Corporativo','PostgreSQL · Histórico Auditável','var(--violet)',False),
    ('sap','Retorno SAP','IW47 · Baixas em Massa','var(--cyan)',False),
]
s += f'<div class="flow" style="margin:auto 0;" {rv(.34)}>'
for i,(ic,t,sub,c,on) in enumerate(nodes):
    if i>0: s += ARROW
    s += (f'<div class="node{" on" if on else ""}" style="--c:{c}">'
          f'<div class="n-ico">{sv(ic)}</div><h4>{t}</h4><div class="n-sub">{sub}</div></div>')
s += '</div>'
s += f'<p class="mono-strip" style="text-align:center;margin-top:8px;" {rv(.7)}>Fluxo idempotente ponta a ponta — <b>zero perda</b>, <b>zero duplicidade</b>.</p>'
slide(s)

# ===========================================================================
# SLIDE 5 — Inteligência da Malha
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>Inteligência da Malha</p>'
s += f'<h2 class="s-title" {rv(.12)}>Inteligência Ferroviária <span class="grad">Incorporada</span></h2>'
s += f'<p class="s-lead" {rv(.2)}>O sistema conhece a malha — não depende da memória de quem está no campo.</p>'
saberes = ['Pátios','Bases operacionais','Coordenadas dos ativos','Distâncias reais','Tipo de intervalo (CI/SI)','Criticidade','Regras de confiabilidade','Regras de segurança','Histórico operacional']
s += '<div style="display:flex;flex-wrap:wrap;gap:18px;margin:auto 0;max-width:1500px;">'
for i,t in enumerate(saberes):
    s += f'<div class="chip" {rv(round(.28+i*.06,2),"scale")}>{sv("check")}{t}</div>'
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 6 — Roteirização
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>Roteirização Inteligente</p>'
s += f'<h2 class="s-title" {rv(.12)}>Da <span class="red">Lista</span> para a <span class="grad">Geografia</span></h2>'
s += '<div class="g g2" style="margin:52px 0 auto;align-items:stretch;gap:40px;">'
s += (f'<div class="card edge" style="--c:var(--red)" {rv(.28,"left")}>'
      f'<div class="eyebrow-c" style="--c:var(--red)">ANTES</div>'
      '<ul class="ck dim" style="--c:var(--red);margin-top:22px;font-size:23px;gap:20px;">'
      f'<li>{sv("target","")}Lista de OS</li>'
      f'<li>{sv("brain","")}Escolha manual pelo "feeling"</li>'
      f'<li>{sv("route","")}Viagens perdidas</li></ul></div>')
s += (f'<div class="card edge" style="--c:var(--cyan)" {rv(.42,"right")}>'
      f'<div class="eyebrow-c">DEPOIS</div>'
      '<ul class="ck" style="margin-top:22px;font-size:22px;gap:18px;">'
      f'<li>{sv("satellite")}Posicionamento geográfico (GPS)</li>'
      f'<li>{sv("compass")}Cálculo de distância real (Haversine)</li>'
      f'<li>{sv("layers")}Agrupamento operacional por proximidade</li>'
      f'<li>{sv("target")}Execução por raio ajustável (início 1 km)</li></ul></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 7 — Motor de Priorização
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>Motor de Priorização</p>'
s += f'<h2 class="s-title" {rv(.12)}>Decisão <span class="grad">Sistêmica</span>, Não Humana</h2>'
s += f'<p class="s-lead" {rv(.2)}>O técnico não precisa decidir o que é mais importante. O sistema aplica a hierarquia.</p>'
s += '<div class="g g2" style="margin:44px 0 auto;align-items:stretch;gap:44px;">'
niveis = [('Nível 1','Segurança','var(--red)'),('Nível 2','Confiabilidade','var(--amber)'),
          ('Nível 3','Criticidade','var(--cyan)'),('Nível 4','Proximidade','var(--green)'),
          ('Nível 5','Atraso operacional','var(--violet)')]
s += f'<div class="prio" {rv(.28,"left")}>'
for lv,nm,c in niveis:
    s += f'<div class="prio-row" style="--c:{c}"><span class="lv">{lv}</span><span class="nm">{nm}</span><span class="bd">{sv("bolt")}</span></div>'
s += '</div>'
s += (f'<div class="card" style="--c:var(--red);display:flex;flex-direction:column;justify-content:center;" {rv(.42,"right")}>'
      '<div class="radar" style="margin-bottom:28px;"><div class="rc"></div><div class="tg"></div></div>'
      '<p style="font-size:21px;color:var(--white);line-height:1.5;text-align:center;">'
      'Atividades críticas <b style="color:var(--red)">bloqueiam</b> atividades inferiores do mesmo grupo.<br><br>'
      'As bloqueadas permanecem <b style="color:var(--cyan)">visíveis</b> (sombreadas + 🔒), forçando a resolução '
      'da emergência antes das preventivas.</p></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 8 — Operação Offline
# ===========================================================================
s = ''
s += f'<p class="kicker amber" {rv(.05)}>Operação Offline</p>'
s += f'<h2 class="s-title" {rv(.12)}>Continuidade <span class="amber">Operacional</span></h2>'
s += (f'<p class="s-lead" {rv(.2)}>Funciona sem rádio, Wi-Fi ou 4G — via PWA instalado em contexto seguro (HTTPS), '
      'nunca por arquivo solto.</p>')
steps = [
    ('satellite','1. Publicar a Rota','Com sinal, o gestor publica o pacote. O técnico abre o link seguro (HTTPS) uma vez e o app fica instalado.','var(--cyan)',False),
    ('wifi-off','2. Modo Local Seguro','No trecho sem sinal, o PWA roda no aparelho. O GPS permanece ativo e apontamentos/fotos ficam em fila local (IndexedDB).','var(--amber)',True),
    ('refresh','3. Sincronização','Ao reconectar, envia tudo de uma vez. Gravação idempotente: zero perda e zero duplicidade.','var(--green)',False),
]
s += '<div class="g g3" style="margin-top:46px;">'
for i,(ic,t,d,c,hi) in enumerate(steps):
    extra = 'box-shadow:0 0 40px -12px var(--c);' if hi else ''
    s += (f'<div class="card top" style="--c:{c};text-align:center;{extra}" {rv(round(.3+i*.12,2),"up")}>'
          f'<div class="ico" style="margin:0 auto 18px;">{sv(ic)}</div><h3>{t}</h3>'
          f'<p style="margin-top:12px;">{d}</p></div>')
s += '</div>'
s += f'<div style="display:flex;gap:16px;margin-top:36px;flex-wrap:wrap;" {rv(.72)}>'
for t in ['PWA (Service Worker + manifest)','IndexedDB','Sincronização posterior','Controle de duplicidade']:
    s += f'<div class="chip" style="font-size:17px;padding:11px 18px;">{sv("check")}{t}</div>'
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 9 — Governança
# ===========================================================================
s = ''
s += f'<p class="kicker green" {rv(.05)}>Governança</p>'
s += f'<h2 class="s-title" {rv(.12)}>Governança <span class="green">Operacional</span></h2>'
s += f'<p class="s-lead" {rv(.2)}>Confiança é boa; controle sistêmico é à prova de falhas.</p>'
govs = [
    ('lock','Login Controlado','Token persistente (12h) que sobrevive à câmera.','var(--cyan)'),
    ('users','Perfis de Acesso','Separação de responsabilidades por papel.','var(--blue)'),
    ('file','Registro de Acessos','Rastro de quem entrou e quando.','var(--violet)'),
    ('satellite','GPS Obrigatório','Fonte única: o hardware. Coordenada (0,0) rejeitada.','var(--amber)'),
    ('camera','Evidência Fotográfica','Foto tratada e arquivada por baixa.','var(--green)'),
    ('target','Geofencing','Baixa só dentro de 2,0 km do ativo (Haversine).','var(--cyan)'),
    ('db','Histórico Auditável','Cada evento fica registrado e consultável.','var(--violet)'),
    ('shield','Controle de Execução','Travas sistêmicas contra desvio do plano.','var(--red)'),
]
s += '<div class="g g4" style="margin:44px 0 auto;">'
for i,(ic,t,d,c) in enumerate(govs):
    s += (f'<div class="card" style="--c:{c};padding:24px;" {rv(round(.28+i*.06,2),"up")}>'
          f'<div class="ico sm" style="margin-bottom:14px;">{sv(ic)}</div>'
          f'<h3 style="font-size:20px;color:{c}">{t}</h3><p style="margin-top:8px;font-size:15px;">{d}</p></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 10 — Integração SAP
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>Integração SAP</p>'
s += f'<h2 class="s-title" {rv(.12)}>Integração de <span class="grad">Ciclo Completo</span></h2>'
cols = [
    ('Entrada','var(--cyan)',['Planejamento','OS programadas']),
    ('Processamento','var(--amber)',['Regras operacionais','Consolidação de execução']),
    ('Saída','var(--green)',['Arquivo SAP','IW47','Baixas em massa','Informações estruturadas']),
]
s += '<div class="flow" style="margin:56px 0 auto;align-items:stretch;">'
for i,(t,c,items) in enumerate(cols):
    if i>0: s += ARROW
    li = ''.join(f'<li>{sv("check")}{x}</li>' for x in items)
    s += (f'<div class="card top" style="--c:{c};flex:1;" {rv(round(.3+i*.14,2),"up")}>'
          f'<h3 style="color:{c};font-size:28px;margin-bottom:20px;">{t}</h3>'
          f'<ul class="ck" style="--c:{c};font-size:20px;">{li}</ul></div>')
s += '</div>'
s += f'<p class="s-lead" style="text-align:center;margin-top:34px;" {rv(.8)}>Fim do retrabalho de digitação manual de relatórios no escritório.</p>'
slide(s)

# ===========================================================================
# SLIDE 11 — Arquitetura Corporativa
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>Arquitetura Corporativa</p>'
s += f'<h2 class="s-title" {rv(.12)}>Arquitetura <span class="grad">Tecnológica</span></h2>'
s += f'<p class="s-lead" {rv(.2)}>A stack real, em nomes — para quem constrói sistemas.</p>'
arq = [
    ('monitor','Front-end','Streamlit + PWA','var(--cyan)'),
    ('python','Back-end','Python','var(--amber)'),
    ('bolt','API','FastAPI','var(--green)'),
    ('db','Banco','PostgreSQL','var(--violet)'),
    ('cloud','Storage','Supabase','var(--cyan)'),
    ('shield','Segurança','HTTPS + API Key','var(--red)'),
    ('satellite','Geolocalização','GPS HTML5 + Haversine','var(--green)'),
    ('refresh','Idempotência','Upsert ON CONFLICT','var(--amber)'),
]
s += '<div class="g g4" style="margin-top:42px;">'
for i,(ic,t,d,c) in enumerate(arq):
    s += (f'<div class="card top" style="--c:{c};text-align:center;padding:26px;" {rv(round(.28+i*.06,2),"up")}>'
          f'<div class="ico sm" style="margin:0 auto 14px;">{sv(ic)}</div>'
          f'<h3 style="font-size:20px;color:{c}">{t}</h3><p style="margin-top:8px;font-size:16px;color:var(--white)">{d}</p></div>')
s += '</div>'
s += (f'<p class="mono-strip" style="text-align:center;margin-top:auto;padding-top:26px;" {rv(.86)}>'
      'Endpoints &nbsp;<b>/sincronizar_baixa_offline</b> · <b>/health</b> · <b>/publicar_pacote</b> · <b>/pacote/{id}</b></p>')
slide(s)

# ===========================================================================
# SLIDE 12 — Proteção do Conhecimento
# ===========================================================================
s = ''
s += '<div style="margin:auto 0;text-align:center;">'
s += f'<p class="kicker" style="justify-content:center;" {rv(.05)}>Proteção do Conhecimento Operacional</p>'
s += f'<h2 class="s-title" style="margin-top:20px;" {rv(.12)}>Transformando <span class="violet">Experiência</span> em Sistema</h2>'
s += (f'<p class="s-lead" style="max-width:1200px;margin:22px auto 0;" {rv(.2)}>A experiência dos técnicos deixa de estar '
      'apenas nas pessoas. O conhecimento passa a estar no sistema — e a boa prática é reproduzida de forma padronizada.</p>')
s += '<div class="g g4" style="margin-top:52px;">'
for i,(ic,t) in enumerate([('clipboard','nas regras'),('cpu','nos algoritmos'),('db','nos cadastros'),('map','na inteligência geográfica')]):
    s += (f'<div class="card" style="--c:var(--violet);text-align:center;padding:36px 26px;" {rv(round(.32+i*.1,2),"up")}>'
          f'<div class="ico" style="margin:0 auto 18px;">{sv(ic)}</div><h3 style="color:var(--violet);font-size:22px;">{t}</h3></div>')
s += '</div></div>'
slide(s)

# ===========================================================================
# SLIDE 13 — Benefícios (com KPIs animados)
# ===========================================================================
s = ''
s += f'<p class="kicker green" {rv(.05)}>Benefícios</p>'
s += f'<h2 class="s-title" {rv(.12)}>Benefícios para a <span class="green">Malha</span></h2>'
bens = [
    ('route','Menos deslocamentos improdutivos','var(--cyan)'),
    ('users','Melhor utilização das equipes','var(--blue)'),
    ('clipboard','Maior aderência ao planejamento','var(--amber)'),
    ('target','Priorização automática','var(--red)'),
    ('camera','Evidência rastreável','var(--green)'),
    ('brain','Menor dependência de conhecimento tácito','var(--violet)'),
]
s += '<div class="g g3" style="margin-top:42px;">'
for i,(ic,t,c) in enumerate(bens):
    s += (f'<div class="card" style="--c:{c};display:flex;align-items:center;gap:18px;padding:24px 26px;" {rv(round(.28+i*.07,2),"up")}>'
          f'<div class="ico sm">{sv(ic)}</div><h3 style="font-size:21px;">{t}</h3></div>')
s += '</div>'
# faixa KPI animada
kpis = [('1','km','raio inicial de busca','var(--cyan)'),('2,0','km','geofencing por ativo','var(--green)'),
        ('12','h','sessão persistente','var(--amber)'),('100','%','execução auditável','var(--violet)')]
s += f'<div class="g g4" style="margin-top:34px;" {rv(.72)}>'
for v,u,l,c in kpis:
    dc = v.replace(',','.')
    dec = '1' if ',' in v else '0'
    s += (f'<div class="kpi" style="--c:{c}"><div class="kv"><span data-count="{dc}" data-dec="{dec}" data-delay="200">0</span>'
          f'<span style="font-size:32px;color:var(--soft)"> {u}</span></div><div class="kl">{l}</div></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 14 — Evolução
# ===========================================================================
s = ''
s += f'<p class="kicker" {rv(.05)}>Evolução</p>'
s += f'<h2 class="s-title" {rv(.12)}>Próximos <span class="grad">Passos</span></h2>'
s += '<div class="g g2" style="margin:52px 0 auto;align-items:stretch;gap:44px;">'
entregue = ['Governança operacional','Roteirização','GPS obrigatório','PWA Offline','Integração SAP']
prox = ['Hospedagem corporativa','SSO / AD','APIs corporativas','Dashboards executivos','Inteligência preditiva','Recomendação automática de roteiros']
li1 = ''.join(f'<li>{sv("check")}{x}</li>' for x in entregue)
li2 = ''.join(f'<li>{sv("refresh")}{x}</li>' for x in prox)
s += (f'<div class="card edge" style="--c:var(--green)" {rv(.28,"left")}>'
      f'<div class="eyebrow-c" style="--c:var(--green)">ENTREGUE</div>'
      f'<ul class="ck" style="--c:var(--green);margin-top:22px;font-size:23px;gap:18px;">{li1}</ul></div>')
s += (f'<div class="card edge" style="--c:var(--amber)" {rv(.42,"right")}>'
      f'<div class="eyebrow-c" style="--c:var(--amber)">PRÓXIMAS EVOLUÇÕES</div>'
      f'<ul class="ck" style="--c:var(--amber);margin-top:22px;font-size:22px;gap:16px;">{li2}</ul></div>')
s += '</div>'
slide(s)

# ===========================================================================
# SLIDE 15 — Encerramento
# ===========================================================================
s = ''
s += '<div style="margin:auto 0;text-align:center;">'
s += f'<p class="kicker" style="justify-content:center;" {rv(.05)}>Encerramento</p>'
s += f'<h2 class="s-title" style="font-size:72px;margin-top:18px;" {rv(.12)}>Mais do que um <span class="grad">aplicativo</span></h2>'
s += f'<p class="s-lead" style="max-width:1100px;margin:22px auto 46px;" {rv(.2)}>O SGO se torna uma camada digital entre planejamento e execução.</p>'
chain = [('Planejamento','var(--cyan)'),('Malha','var(--amber)'),('Execução','var(--green)'),('Governança','var(--violet)'),('SAP','var(--cyan)')]
s += f'<div class="flow" style="max-width:1300px;margin:0 auto;align-items:center;" {rv(.36)}>'
for i,(nm,c) in enumerate(chain):
    if i>0: s += ARROW
    s += (f'<div class="node" style="--c:{c};padding:22px 14px;">'
          f'<div class="n-ico" style="width:56px;height:56px;">{sv("diamond")}</div><h4 style="font-size:20px;color:{c}">{nm}</h4></div>')
s += '</div>'
s += (f'<h3 style="font-weight:600;font-size:30px;color:var(--white);margin-top:46px;" {rv(.6)}>'
      'Transformando conhecimento operacional em <span class="grad" style="font-weight:800">inteligência sistêmica</span>.</h3>')
s += (f'<p class="mono-strip" style="margin-top:26px;letter-spacing:.16em;text-transform:uppercase;" {rv(.74)}>'
      'Muito Obrigado</p>')
s += '</div>'
slide(s)

# ===========================================================================
# Montagem final
# ===========================================================================
TICKER = ''  # (mantido só como referência; chrome usa HUD/dots)
html = '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
html += '<title>SGO Eletroeletrônica MRS | Pitch Premium</title>'
html += '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
html += '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap">'
html += f'<style>{CSS}</style></head><body>'
html += '<div class="progress"><div class="bar" id="progressBar"></div></div>'
html += '<div class="deck-viewport"><main class="deck-stage" id="deckStage">'
html += ''.join(SLIDES)
html += '</main></div>'
# chrome
html += '<div class="hud"><b>SGO</b> · Eletroeletrônica MRS</div>'
html += '<div class="brandtag">SGO · MRS</div>'
html += '<div class="counter"><b id="cur">01</b> / <span id="total">15</span></div>'
html += '<div class="kb-hint" id="kbHint"><kbd>←</kbd> <kbd>→</kbd> navegar · <kbd>F</kbd> tela cheia</div>'
html += '<button class="fsbtn" id="fsBtn" title="Tela cheia (F)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button>'
html += '<button class="navbtn prev" id="prevBtn" aria-label="Anterior"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button>'
html += '<button class="navbtn next" id="nextBtn" aria-label="Próximo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg></button>'
html += '<div class="dots" id="dots"></div>'
html += f'<script>{JS}</script></body></html>'

fn = 'Pitch_Eletroeletronica_SGO_Premium.html'
with open(fn, 'w', encoding='utf-8') as f:
    f.write(html)
print('Pitch Premium gerado:', os.path.abspath(fn), '| slides:', len(SLIDES))
try:
    webbrowser.open('file://' + os.path.abspath(fn))
except Exception:
    pass
