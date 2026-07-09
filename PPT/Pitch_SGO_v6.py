# -*- coding: utf-8 -*-
"""
Pitch SGO Eletroeletrônica MRS — versão PREMIUM (v6)
Motor visual portado do deck ALIME (palco fixo 1920x1080 escalado, Manrope + Space Mono,
chrome completo, reveal por --d, contadores data-count). Conteúdo: SGO MRS.
Gera um HTML autocontido; a imagem do mapa é embutida 1x via var CSS --mapimg.
"""
import base64, os

BASE = os.path.dirname(os.path.abspath(__file__))

def load_map():
    for name in ('baixada_patios.png', 'baixada_dark2.png'):
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')
    return 'baixada_patios.png'

MAP_URI = load_map()

# ==========================================================================
# CSS — tokens + palco + chrome + reveal + componentes (portado do ALIME)
# ==========================================================================
CSS = r"""
:root{
  --navy-900:#03070f; --navy-850:#050c18; --navy-800:#071426; --navy-700:#0b1f38; --navy-650:#102844;
  --gold:#f3b13c; --gold-2:#ffd479; --cyan:#39d6e8; --teal:#1ea7b6; --blue:#3b82f6;
  --rail:#ff5a7e; --green:#37e07e; --red:#ff465e;
  --white:#eef4ff; --soft:#aebfda; --dim:#6f83a6; --line:rgba(120,160,220,.16);
  --stage-bg:#02050c; --slide-bg:#040a16;
  --card:linear-gradient(155deg, rgba(15,32,58,.72), rgba(6,15,30,.5));
  --card-soft:linear-gradient(155deg, rgba(13,28,52,.5), rgba(6,14,28,.32));
  --card-bd:rgba(120,160,220,.18); --shadow:0 24px 60px rgba(0,0,0,.5);
  --font:'Manrope', system-ui, sans-serif; --mono:'Space Mono', monospace;
  --t-h2:54px; --t-lead:26px; --t-body:21px; --t-small:16px;
  --ease:cubic-bezier(.16,1,.3,1); --pad-x:104px; --pad-y:80px;
  --mapimg:url(%MAP%);
}
*{ margin:0; padding:0; box-sizing:border-box; }
html,body{ width:100%; height:100%; overflow:hidden; background:var(--stage-bg);
  font-family:var(--font); color:var(--white); -webkit-font-smoothing:antialiased; }

/* ---- palco fixo 16:9 ---- */
.deck-viewport{ position:fixed; inset:0; overflow:hidden; background:var(--stage-bg); }
.deck-stage{ position:absolute; left:0; top:0; width:1920px; height:1080px; overflow:hidden;
  transform-origin:0 0; background:var(--slide-bg); }
.slide{ position:absolute; inset:0; width:1920px; height:1080px; overflow:hidden;
  visibility:hidden; opacity:0; pointer-events:none; background:
    radial-gradient(1100px 760px at 6% 0%, rgba(243,177,60,.10) 0%, transparent 56%),
    radial-gradient(1200px 820px at 100% 100%, rgba(57,214,232,.10) 0%, transparent 60%),
    linear-gradient(160deg, #061227 0%, var(--slide-bg) 55%, #03060f 100%); }
.slide.active,.slide.visible{ visibility:visible; opacity:1; pointer-events:auto; z-index:1; }
.slide::before{ content:""; position:absolute; inset:0; z-index:0; pointer-events:none;
  background-image:linear-gradient(rgba(120,160,220,.045) 1px,transparent 1px),
                   linear-gradient(90deg, rgba(120,160,220,.045) 1px,transparent 1px);
  background-size:66px 66px; mask-image:radial-gradient(130% 105% at 50% 30%, #000 26%, transparent 84%); }
.orb{ position:absolute; border-radius:50%; filter:blur(64px); opacity:.5; z-index:0; pointer-events:none;
  animation:orbFloat 11s ease-in-out infinite; }
.orb.b{ animation-duration:14s; animation-direction:reverse; }
@keyframes orbFloat{ 0%,100%{ transform:translate(0,0);} 50%{ transform:translate(30px,22px);} }
.slide-inner{ position:absolute; inset:0; z-index:2; padding:var(--pad-y) var(--pad-x);
  display:flex; flex-direction:column; }

/* ---- chrome: kicker, título, HUD, progresso, dots, controles ---- */
.kicker{ font-family:var(--mono); font-size:15px; letter-spacing:.26em; text-transform:uppercase;
  color:var(--gold); display:inline-flex; align-items:center; gap:14px; }
.kicker::before{ content:""; width:36px; height:2px;
  background:linear-gradient(90deg, var(--gold), transparent); box-shadow:0 0 12px var(--gold); }
.kicker.amber{ color:var(--gold-2);} .kicker.amber::before{ background:linear-gradient(90deg,var(--gold-2),transparent); box-shadow:0 0 12px var(--gold-2);}
.kicker.rail{ color:var(--rail);} .kicker.rail::before{ background:linear-gradient(90deg,var(--rail),transparent); box-shadow:0 0 12px var(--rail);}
.kicker.green{ color:var(--green);} .kicker.green::before{ background:linear-gradient(90deg,var(--green),transparent); box-shadow:0 0 12px var(--green);}
.kicker.cyan{ color:var(--cyan);} .kicker.cyan::before{ background:linear-gradient(90deg,var(--cyan),transparent); box-shadow:0 0 12px var(--cyan);}
.slide-title{ font-weight:800; font-size:var(--t-h2); line-height:1.05; letter-spacing:-.02em; margin-top:16px; }
.grad{ background:linear-gradient(100deg, var(--gold), var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-gold{ background:linear-gradient(100deg, var(--gold), var(--gold-2)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-rail{ background:linear-gradient(100deg, var(--rail), var(--gold)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-green{ background:linear-gradient(100deg, var(--green), var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.grad-cyan{ background:linear-gradient(100deg, var(--cyan), var(--blue)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.slide-lead,.lead{ font-size:var(--t-lead); color:var(--soft); line-height:1.42; margin-top:14px; max-width:1180px; }
.lead b, .slide-lead b{ color:var(--white); }
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
  box-shadow:var(--shadow); position:relative; overflow:hidden; }
.grid{ display:grid; gap:18px; }
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

/* ---- SLIDE 1: capa ---- */
.s1 .slide-inner{ justify-content:center; align-items:flex-start; }
.s1-photo{ position:absolute; inset:0; z-index:0; }
.s1-photo i{ position:absolute; right:-2%; top:0; width:64%; height:100%; background-image:var(--mapimg);
  background-size:cover; background-position:center; mix-blend-mode:screen; opacity:.5; }
.s1-photo::after{ content:""; position:absolute; inset:0; background:
  linear-gradient(90deg, var(--slide-bg) 26%, rgba(4,10,22,.35) 58%, transparent 100%),
  linear-gradient(0deg, var(--slide-bg), transparent 40%); }
.alime-badge{ display:inline-flex; align-items:center; gap:12px; margin-top:22px; padding:9px 16px;
  border-radius:999px; background:rgba(13,28,52,.6); border:1px solid var(--line); backdrop-filter:blur(6px); }
.alime-badge .ab-dot{ width:11px; height:11px; border-radius:50%; background:var(--gold); box-shadow:0 0 12px var(--gold); }
.alime-badge .ab-txt b{ font-size:15px; color:var(--white); } .alime-badge .ab-txt i{ display:block; font-style:normal; font-size:12px; color:var(--dim); font-family:var(--mono); letter-spacing:.04em; }
.title-main{ font-weight:800; font-size:118px; line-height:.98; letter-spacing:-.03em; margin-top:20px; }
.hl-gold{ background:linear-gradient(100deg, var(--gold), var(--gold-2)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.hl-cyan{ color:var(--cyan); } .hl-rail{ color:var(--rail); }
.title-sub{ font-size:34px; color:var(--soft); font-weight:500; margin-top:20px; line-height:1.24; }
.technical-card{ margin-top:34px; padding:20px 26px; border-radius:16px; max-width:760px;
  background:var(--card); border:1px solid var(--card-bd); border-left:3px solid var(--gold); box-shadow:var(--shadow); }
.technical-card .tc-eyebrow{ font-family:var(--mono); font-size:12px; letter-spacing:.2em; text-transform:uppercase; color:var(--gold); }
.technical-card .tc-txt{ display:block; margin-top:8px; font-size:21px; color:var(--soft); }
.technical-card .tc-txt b{ color:var(--white); } .technical-card .tc-txt em{ color:var(--gold-2); font-style:normal; }
.authors-block{ display:flex; gap:70px; margin-top:40px; }
.authors-block .lab{ font-family:var(--mono); font-size:12px; letter-spacing:.2em; text-transform:uppercase; color:var(--dim); }
.authors-block .val{ font-size:20px; color:var(--white); margin-top:6px; } .authors-block .val em{ font-style:normal; }

/* ---- equação (imp-calc) ---- */
.imp-calc{ display:flex; align-items:stretch; gap:9px; margin-top:26px; }
.imp-factor{ flex:1 1 0; min-width:0; display:flex; flex-direction:column; align-items:center; justify-content:center;
  text-align:center; padding:16px 12px; border-radius:14px; position:relative; overflow:hidden;
  background:linear-gradient(155deg, rgba(15,32,58,.5), rgba(6,14,28,.38)); border:1px solid rgba(120,160,220,.18);
  box-shadow:0 14px 34px rgba(0,0,0,.34); }
.imp-factor b{ font-family:var(--mono); font-weight:700; font-size:26px; color:var(--gold-2); line-height:1.05;
  text-shadow:0 0 18px rgba(243,177,60,.3); }
.imp-factor span{ font-size:13px; color:var(--soft); margin-top:9px; line-height:1.35; } .imp-factor span i{ color:var(--dim); font-style:normal; }
.imp-op{ flex:0 0 auto; align-self:center; font-family:var(--mono); font-size:22px; color:var(--dim); }
.imp-eq{ flex:0 0 auto; align-self:center; font-family:var(--mono); font-size:30px; font-weight:700; color:var(--gold);
  text-shadow:0 0 14px rgba(243,177,60,.5); padding:0 2px; }
.imp-result{ flex:0 0 430px; display:flex; align-items:center; gap:14px; padding:16px 22px; border-radius:15px; position:relative; overflow:hidden;
  background:linear-gradient(150deg, rgba(55,224,126,.2), rgba(6,15,30,.42)); border:1px solid rgba(55,224,126,.5);
  box-shadow:0 16px 40px rgba(0,0,0,.4), 0 0 30px rgba(55,224,126,.14); }
.ir-ico{ width:50px; height:50px; flex:0 0 auto; display:grid; place-items:center; border-radius:13px; color:var(--green);
  background:rgba(55,224,126,.14); border:1px solid rgba(55,224,126,.34); box-shadow:0 0 18px rgba(55,224,126,.2); font-size:24px; }
.ir-lab{ font-family:var(--mono); font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--green); }
.ir-tx b{ display:block; font-family:var(--mono); font-weight:700; font-size:30px; line-height:1.04; margin-top:3px; color:var(--green);
  white-space:nowrap; text-shadow:0 0 24px rgba(55,224,126,.4); }

/* ---- antes/depois (imp-maps) ---- */
.imp-maps{ display:grid; grid-template-columns:1fr auto 1fr; gap:16px; align-items:stretch; margin-top:26px; flex:1; min-height:0; }
.imp-map{ position:relative; border-radius:16px; overflow:hidden; min-height:0;
  border:1px solid rgba(120,160,220,.2); box-shadow:0 16px 40px rgba(0,0,0,.4); padding:26px; display:flex; flex-direction:column; }
.imp-map.atual{ border-color:rgba(255,90,126,.34); background:linear-gradient(160deg, rgba(60,12,26,.5), rgba(6,14,28,.5)); }
.imp-map.sol{ border-color:rgba(57,214,232,.36); background:linear-gradient(160deg, rgba(8,44,58,.5), rgba(6,14,28,.5)); }
.im-cap{ display:inline-flex; align-items:center; gap:8px; font-family:var(--mono); font-size:14px; color:var(--white); }
.im-list{ list-style:none; margin-top:20px; display:flex; flex-direction:column; gap:14px; }
.im-list li{ display:flex; align-items:center; gap:12px; font-size:19px; color:var(--soft); }
.im-list li .ic{ width:30px; height:30px; border-radius:8px; display:grid; place-items:center; flex:0 0 auto; font-size:15px; }
.imp-map.atual .ic{ color:var(--rail); background:rgba(255,90,126,.12); border:1px solid rgba(255,90,126,.3); }
.imp-map.sol .ic{ color:var(--cyan); background:rgba(57,214,232,.12); border:1px solid rgba(57,214,232,.3); }
.im-foot{ margin-top:auto; padding-top:18px; font-family:var(--mono); font-size:14px; }
.imp-map.atual .im-foot{ color:#ffd0d8; } .imp-map.sol .im-foot{ color:#dffaff; }
.imp-arrow{ align-self:center; color:var(--cyan); font-size:34px; animation:arrPulse 2.2s ease-in-out infinite; }
@keyframes arrPulse{ 0%,100%{ transform:translateX(0); opacity:.7;} 50%{ transform:translateX(6px); opacity:1;} }
.imp-insight{ display:flex; align-items:center; gap:14px; margin-top:22px; padding:14px 24px; font-size:18px; color:var(--soft);
  border-radius:14px; background:linear-gradient(155deg, rgba(57,214,232,.1), rgba(6,15,30,.34)); border:1px solid rgba(57,214,232,.3); }
.imp-insight b{ color:var(--gold-2); } .imp-insight b.cy{ color:var(--cyan); }

/* ---- matriz radial ---- */
.matrix{ position:relative; width:100%; flex:1; min-height:0; margin-top:18px; }
.matrix svg.mlinks{ position:absolute; inset:0; width:100%; height:100%; overflow:visible; z-index:1; }
.mlink{ stroke-width:1.5; fill:none; stroke-dasharray:var(--len,700); stroke-dashoffset:var(--len,700);
  transition:stroke-dashoffset 1.3s var(--ease); transition-delay:var(--md,.2s); }
.slide.visible .mlink{ stroke-dashoffset:0; }
.mnode{ position:absolute; transform:translate(-50%,-50%) scale(.6); opacity:0;
  transition:opacity .6s var(--ease), transform .6s var(--ease); transition-delay:var(--md,0s);
  display:flex; flex-direction:column; align-items:center; gap:9px; text-align:center; z-index:3; width:200px; }
.slide.visible .mnode{ opacity:1; transform:translate(-50%,-50%) scale(1); }
.morb{ width:var(--sz,104px); height:var(--sz,104px); border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:34px; color:var(--c,var(--cyan));
  background:radial-gradient(circle at 38% 32%, color-mix(in srgb, var(--c,var(--cyan)) 26%, rgba(8,18,34,.9)) 0%, rgba(6,14,28,.94) 70%);
  border:1.5px solid color-mix(in srgb, var(--c,var(--cyan)) 55%, transparent);
  box-shadow:0 0 34px -6px color-mix(in srgb, var(--c,var(--cyan)) 70%, transparent), inset 0 0 26px -10px color-mix(in srgb, var(--c,var(--cyan)) 80%, transparent); }
.mnode .mlabel{ font-family:var(--font); font-size:19px; font-weight:800; color:var(--white); line-height:1.15; }
.mnode .msub{ font-family:var(--mono); font-size:12px; letter-spacing:.14em; color:var(--dim); text-transform:uppercase; }
.mnode.center{ width:280px; }
.mnode.center .morb{ width:230px; height:230px; border-width:2px; flex-direction:column;
  box-shadow:0 0 70px -4px color-mix(in srgb, var(--c,var(--gold)) 60%, transparent), inset 0 0 50px -16px var(--c,var(--gold)); }
.mnode.center .mtitle{ font-family:var(--font); font-size:32px; font-weight:800; color:var(--white); line-height:1.05; padding:0 14px; }
.mnode.center .mtag{ font-family:var(--mono); font-size:13px; letter-spacing:.18em; color:var(--c,var(--gold)); margin-top:8px; text-transform:uppercase; }

/* ---- fluxo horizontal ---- */
.flow{ display:flex; align-items:stretch; gap:0; margin-top:auto; margin-bottom:auto; }
.fnode{ flex:1 1 0; display:flex; flex-direction:column; align-items:center; text-align:center; gap:12px; padding:0 8px; }
.fnode .fo{ width:96px; height:96px; border-radius:22px; display:grid; place-items:center; font-size:34px;
  background:var(--card); border:1px solid var(--c,var(--cyan)); box-shadow:0 0 26px -8px var(--c,var(--cyan)); color:var(--c,var(--cyan)); }
.fnode h4{ font-size:20px; color:var(--white); } .fnode p{ font-size:14px; color:var(--dim); font-family:var(--mono); line-height:1.4; }
.farr{ flex:0 0 60px; align-self:center; margin-top:-40px; color:var(--dim); font-size:26px; text-align:center; }

/* ---- pirâmide de priorização ---- */
.prio{ display:flex; flex-direction:column; gap:12px; margin-top:26px; max-width:1200px; }
.prow{ display:flex; align-items:center; gap:20px; padding:16px 24px; border-radius:14px;
  background:var(--card); border:1px solid var(--card-bd); border-left:5px solid var(--c,var(--cyan)); }
.prow .lvl{ font-family:var(--mono); font-size:13px; letter-spacing:.14em; color:var(--dim); width:70px; flex:0 0 auto; }
.prow .pio{ width:52px; height:52px; border-radius:13px; display:grid; place-items:center; font-size:24px; flex:0 0 auto;
  color:var(--c,var(--cyan)); background:color-mix(in srgb, var(--c,var(--cyan)) 12%, transparent); border:1px solid color-mix(in srgb, var(--c,var(--cyan)) 34%, transparent); }
.prow h4{ font-size:22px; color:var(--white); } .prow p{ font-size:15px; color:var(--soft); margin-top:2px; }
.prow .bignum{ margin-left:auto; font-family:var(--mono); font-size:40px; font-weight:700; color:color-mix(in srgb, var(--c,var(--cyan)) 80%, white); opacity:.5; }

/* ---- mapa (slide malha) ---- */
.mapwrap{ position:absolute; inset:0; z-index:0; overflow:hidden; }
.mapimg{ position:absolute; inset:0; background-image:var(--mapimg); background-size:cover; background-position:center; }
.mapwrap::after{ content:""; position:absolute; inset:0; z-index:1; pointer-events:none;
  background:linear-gradient(100deg, rgba(4,10,22,.96) 0%, rgba(4,10,22,.7) 30%, rgba(4,10,22,.18) 56%, rgba(4,10,22,.5) 100%),
             linear-gradient(0deg, rgba(4,10,22,.85), transparent 45%); }
.mappanel{ position:absolute; left:var(--pad-x); top:14%; z-index:6; max-width:640px; }
.gmark{ position:absolute; transform:translate(-50%,-50%); z-index:5; opacity:0; transition:opacity .7s ease; transition-delay:var(--gd,.3s); }
.slide.visible .gmark{ opacity:1; }
.gmark .disc{ width:14px; height:14px; border-radius:50%; background:radial-gradient(circle,#fff 0%,var(--c,var(--cyan)) 55%,transparent 78%);
  box-shadow:0 0 10px #fff,0 0 18px var(--c,var(--cyan)); position:relative; }
.gmark .disc::before{ content:""; position:absolute; inset:-6px; border-radius:50%; border:1px solid var(--c,var(--cyan)); opacity:.55; animation:gpulse 2.8s ease-out infinite; }
@keyframes gpulse{ 0%{ transform:scale(.6); opacity:.8;} 100%{ transform:scale(2.6); opacity:0;} }
.gmark .lab{ position:absolute; left:20px; top:50%; transform:translateY(-50%); white-space:nowrap; font-family:var(--font); }
.gmark.flip .lab{ left:auto; right:20px; text-align:right; }
.gmark .lab .t{ display:block; font-size:16px; font-weight:800; color:var(--white); text-shadow:0 2px 8px #000; line-height:1.1; }
.gmark .lab .s{ display:block; font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--c,var(--cyan)); margin-top:2px; font-family:var(--mono); }
.geofence{ position:absolute; transform:translate(-50%,-50%); z-index:4; width:230px; height:230px; border-radius:50%;
  border:1.5px dashed var(--rail); background:radial-gradient(circle, rgba(255,90,126,.12), transparent 70%);
  box-shadow:0 0 40px -6px var(--rail); opacity:0; transition:opacity .9s ease; transition-delay:.5s; }
.slide.visible .geofence{ opacity:1; }
.geofence .gf-tag{ position:absolute; bottom:10px; left:50%; transform:translateX(-50%); font-family:var(--mono);
  font-size:11px; letter-spacing:.1em; color:var(--rail); white-space:nowrap; }

/* ---- grade genérica de cards (features) ---- */
.feat{ display:grid; gap:16px; margin-top:26px; }
.feat .card{ padding:22px; }
.feat .fico{ font-size:30px; } .feat h4{ font-size:20px; color:var(--white); margin-top:12px; }
.feat p{ font-size:15px; color:var(--soft); margin-top:8px; line-height:1.45; }
.feat .card.gd{ border-left:4px solid var(--gold); } .feat .card.cy{ border-left:4px solid var(--cyan); }
.feat .card.gn{ border-left:4px solid var(--green); } .feat .card.rl{ border-left:4px solid var(--rail); }

/* ---- timeline (evolução) ---- */
.tl{ display:flex; gap:0; margin-top:34px; position:relative; }
.tl::before{ content:""; position:absolute; left:2%; right:2%; top:34px; height:2px; background:linear-gradient(90deg,var(--green),var(--gold),var(--cyan)); opacity:.4; }
.tstep{ flex:1 1 0; display:flex; flex-direction:column; align-items:center; text-align:center; gap:14px; position:relative; z-index:1; padding:0 6px; }
.tstep .tdot{ width:22px; height:22px; border-radius:50%; background:var(--c,var(--cyan)); box-shadow:0 0 16px var(--c,var(--cyan)); border:4px solid var(--slide-bg); }
.tstep h4{ font-size:17px; color:var(--white); } .tstep p{ font-size:13px; color:var(--dim); font-family:var(--mono); }
.tstep .tst{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase; }

/* ---- encerramento ---- */
.end .slide-inner{ justify-content:center; align-items:center; text-align:center; }
.end-photo{ position:absolute; inset:0; z-index:0; }
.end-photo i{ position:absolute; inset:0; background-image:var(--mapimg); background-size:cover; background-position:center; mix-blend-mode:screen; opacity:.32; }
.end-photo::after{ content:""; position:absolute; inset:0; background:radial-gradient(ellipse 72% 64% at 50% 48%, rgba(4,10,22,.55) 0%, rgba(4,10,22,.3) 48%, rgba(4,10,22,.72) 100%); }
"""

# ==========================================================================
# JS — palco fixo, navegação, reveal, contadores (portado do ALIME)
# ==========================================================================
JS = r"""
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
    this.stage.style.transform=`translate(${x}px, ${y}px) scale(${s})`; }
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
  go(i,initial=false){ i=Math.max(0,Math.min(this.total-1,i)); if(i===this.current&&!initial) return;
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
  toggleFullscreen(){ if(!document.fullscreenElement) document.documentElement.requestFullscreen?.(); else document.exitFullscreen?.(); }
}
window.addEventListener('DOMContentLoaded',()=>{ new Deck(); });
"""


def head(kind, kicker_html, title_html, lead_html=''):
    """Cabeçalho comum: kicker + título + lead."""
    s = kicker_html + title_html
    if lead_html:
        s += lead_html
    return s


def build():
    S = []  # lista de slides (strings)

    # --- SLIDE 1: CAPA ---
    S.append('''
<section class="slide s1">
  <div class="s1-photo"><i></i></div>
  <div class="orb" style="width:520px;height:520px;background:rgba(243,177,60,.16);left:-140px;top:-110px;"></div>
  <div class="orb b" style="width:560px;height:560px;background:rgba(57,214,232,.14);left:120px;bottom:-200px;"></div>
  <div class="slide-inner">
    <p class="kicker reveal down" style="--d:.08s">Inteligência Operacional Aplicada à Malha · MRS</p>
    <div class="alime-badge reveal left" style="--d:.34s">
      <span class="ab-dot"></span>
      <span class="ab-txt"><b>Sistema SGO</b><i>Sistema de Gestão Operacional · Eletroeletrônica</i></span>
    </div>
    <h1 class="title-main reveal" style="--d:.56s">SGO <span class="hl-gold">Eletroeletrônica</span></h1>
    <p class="title-sub reveal up" style="--d:.98s">Conectando <span class="hl-cyan">SAP, ativos ferroviários, geolocalização</span><br>e execução em campo — em uma só camada digital.</p>
    <div class="technical-card reveal scale" style="--d:1.2s">
      <span class="tc-eyebrow">Arquitetura</span>
      <span class="tc-txt">Roteirização geográfica, priorização sistêmica e governança auditável aplicadas à <em>Baixada Santista</em></span>
    </div>
    <div class="authors-block reveal fade" style="--d:1.5s">
      <div class="ab-blk"><div class="lab">Stack</div><div class="val"><em>Streamlit · FastAPI · PostgreSQL · Supabase · PWA</em></div></div>
      <div class="ab-blk"><div class="lab">Malha</div><div class="val"><em>MRS Logística</em> — Corredor de Santos</div></div>
    </div>
  </div>
</section>''')

    # --- SLIDE 2: O PROBLEMA ---
    frentes = [
        ('🧠', 'Conhecimento dos Ativos', 'Saber o que é cada equipamento e o que ele exige.', 'gd'),
        ('🗺️', 'Conhecimento Geográfico', 'Onde estão os ativos e como se deslocar entre eles.', 'cy'),
        ('🎯', 'Priorização Correta', 'O que atacar primeiro diante de dezenas de OS.', 'gd'),
        ('📋', 'Aderência ao Plano', 'Executar conforme o que foi programado no SAP.', 'cy'),
        ('📸', 'Evidências da Execução', 'Comprovar o que foi feito, onde e quando.', 'gd'),
    ]
    cards = ''
    for i, (ic, t, d, cl) in enumerate(frentes):
        cards += f'<div class="card {cl} reveal up" style="--d:{.3+i*.09:.2f}s"><div class="fico">{ic}</div><h4>{t}</h4><p>{d}</p></div>'
    cards += ('<div class="card rl reveal up" style="--d:.75s;display:flex;align-items:center;">'
              '<p style="font-size:17px;color:var(--white);line-height:1.5;">Hoje, parte dessa inteligência está '
              '<b style="color:var(--rail)">concentrada na experiência individual</b> — um risco de continuidade para a malha.</p></div>')
    S.append(f'''
<section class="slide s2">
  <div class="orb" style="width:480px;height:480px;background:rgba(255,90,126,.12);right:-120px;top:-80px;"></div>
  <div class="slide-inner">
    <p class="kicker rail reveal left" style="--d:.05s">O Desafio · Manutenção em Malha</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Cinco frentes de decisão, <span class="grad-rail">ao mesmo tempo</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">A operação de campo depende, simultaneamente, de saber, localizar, priorizar, cumprir e comprovar.</p>
    <div class="feat" style="grid-template-columns:repeat(3,1fr);">{cards}</div>
  </div>
</section>''')

    # --- SLIDE 3: O QUE É O SGO (matriz radial) ---
    sat = [
        (50, 12, 500, 72, '🗂️', 'Organiza a execução', 'FLUXO', 'var(--cyan)', .25, .55),
        (78, 27, 780, 162, '🎯', 'Prioriza o crítico', 'SEGURANÇA', 'var(--rail)', .35, .65),
        (78, 73, 780, 438, '🔄', 'Integra ao SAP', 'IW47 · BAIXAS', 'var(--blue)', .45, .75),
        (50, 88, 500, 528, '📸', 'Registra evidências', 'GPS · FOTO', 'var(--green)', .55, .85),
        (22, 73, 220, 438, '💎', 'Padroniza a prática', 'CONHECIMENTO', 'var(--gold)', .65, .95),
        (22, 27, 220, 162, '🔒', 'Controla aderência', 'PLANEJAMENTO', 'var(--gold-2)', .75, 1.05),
    ]
    lines = ''.join(f'<line class="mlink" x1="500" y1="300" x2="{x}" y2="{y}" stroke="{c}" stroke-opacity="0.4" style="--len:340;--md:{dl}s"></line>'
                    for _, _, x, y, _, _, _, c, dl, _ in sat)
    nodes = ''.join(f'<div class="mnode" style="left:{lf}%;top:{tp}%;--c:{c};--md:{dn}s"><div class="morb">{ic}</div><div class="mlabel">{lb}</div><div class="msub">{sb}</div></div>'
                    for lf, tp, _, _, ic, lb, sb, c, _, dn in sat)
    S.append(f'''
<section class="slide s3">
  <div class="slide-inner">
    <p class="kicker reveal left" style="--d:.05s">O Conceito · O que é o SGO</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Um <span class="grad">mecanismo de decisão</span> operacional</h2>
    <p class="slide-lead reveal up" style="--d:.22s">Não é apenas um apontador de OS. É a inteligência da operação transformada em <b>regra sistêmica</b>.</p>
    <div class="matrix">
      <svg class="mlinks" viewBox="0 0 1000 600" preserveAspectRatio="none">{lines}</svg>
      <div class="mnode center" style="left:50%;top:50%;--c:var(--gold);--md:.35s"><div class="morb"><div class="mtitle">SGO</div><div class="mtag">a proposta</div></div></div>
      {nodes}
    </div>
  </div>
</section>''')

    # --- SLIDE 4: O CICLO (fluxo) ---
    steps = [
        ('📥', 'SAP', 'Planejamento<br>OS programadas', 'var(--blue)'),
        ('🧭', 'Motor SGO', 'Priorização · Regras<br>Geo · Governança', 'var(--gold)'),
        ('🛠️', 'Campo', 'GPS · Fotos<br>Offline · Evidências', 'var(--cyan)'),
        ('🗄️', 'Banco', 'Consolidação<br>Corporativa', 'var(--green)'),
        ('📤', 'Retorno SAP', 'IW47 · Baixas<br>em massa', 'var(--blue)'),
    ]
    flow = ''
    for i, (ic, t, p, c) in enumerate(steps):
        if i > 0:
            flow += '<div class="farr reveal fade" style="--d:%.2fs">▸▸</div>' % (.4 + i*.12)
        flow += f'<div class="fnode reveal up" style="--d:{.3+i*.12:.2f}s;--c:{c}"><div class="fo">{ic}</div><h4>{t}</h4><p>{p}</p></div>'
    S.append(f'''
<section class="slide s4">
  <div class="slide-inner">
    <p class="kicker cyan reveal left" style="--d:.05s">O Ciclo · Ponta a Ponta</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Do <span class="grad-cyan">planejamento</span> à baixa — sem retrabalho</h2>
    <p class="slide-lead reveal up" style="--d:.22s">O SGO fecha o ciclo: recebe o plano do SAP, organiza a execução em campo e devolve resultados estruturados.</p>
    <div class="flow">{flow}</div>
  </div>
</section>''')

    # --- SLIDE 5: INTELIGÊNCIA DA MALHA (mapa) ---
    pins = [
        (88.83, 9.51, 'var(--cyan)', True, 'Paranapiacaba', 'Serra · Km 0', .4),
        (67.03, 20.94, 'var(--cyan)', False, 'Serra do Mourão', 'Malha', .55),
        (55.99, 29.00, 'var(--gold)', False, 'Entroncamento', 'Bifurcação', .7),
        (66.83, 64.26, 'var(--cyan)', False, 'Pátio Guarapá', 'Malha', .85),
        (70.78, 81.11, 'var(--rail)', False, 'Ativo Crítico', 'Prioridade Muito Alta', 1.0),
    ]
    pinhtml = '<div class="geofence" style="left:70.78%;top:81.11%;"><span class="gf-tag">CERCA 2,0 KM</span></div>'
    for lf, tp, c, flip, t, sb, d in pins:
        fl = ' flip' if flip else ''
        pinhtml += (f'<div class="gmark{fl}" style="left:{lf}%;top:{tp}%;--c:{c};--gd:{d}s">'
                    f'<div class="disc"></div><div class="lab"><span class="t">{t}</span><span class="s">{sb}</span></div></div>')
    S.append(f'''
<section class="slide s5">
  <div class="mapwrap"><div class="mapimg"></div>{pinhtml}</div>
  <div class="mappanel">
    <p class="kicker reveal left" style="--d:.05s">A Malha Real · Baixada Santista</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da coordenada<br>ao <span class="grad">ativo</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s;max-width:560px;">Cada trilho, pátio e ativo eletroeletrônico georreferenciado. O <b>mesmo GPS</b> que roteiriza o técnico valida a baixa — dentro da <b>cerca de 2,0 km</b> do ativo.</p>
    <div class="reveal up" style="--d:.34s;margin-top:26px;display:flex;flex-direction:column;gap:12px;">
      <span class="pill"><span class="d cyan"></span><b>Trilha GPS</b> · malha ferroviária real</span>
      <span class="pill"><span class="d gold"></span><b>Pátios</b> · entroncamentos e bases</span>
      <span class="pill"><span class="d rail"></span><b>Ativo</b> · cerca de 2,0 km · geofencing</span>
    </div>
    <div class="reveal up" style="--d:.46s;margin-top:30px;display:flex;gap:44px;">
      <div class="stat"><b class="num" data-count="2.0" data-decimals="1" data-suffix=" km" data-delay="400">0</b><span>cerca por ativo</span></div>
      <div class="stat"><b class="num" data-count="1" data-suffix=" km" data-delay="600">0</b><span>raio inicial</span></div>
      <div class="stat"><b class="num" data-count="100" data-suffix="%" data-delay="800">0</b><span>GPS obrigatório</span></div>
    </div>
  </div>
</section>''')

    # --- SLIDE 6: ROTEIRIZAÇÃO (antes/depois) ---
    S.append('''
<section class="slide s6 imp">
  <div class="slide-inner">
    <p class="kicker amber reveal left" style="--d:.05s">Roteirização Inteligente</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da <span class="grad-rail">lista de OS</span> para a <span class="grad">geografia</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O técnico deixa de escolher no papel. O sistema posiciona, calcula e agrupa por proximidade.</p>
    <div class="imp-maps">
      <figure class="imp-map atual reveal left" style="--d:.5s">
        <span class="im-cap"><i class="d rail"></i>Antes · escolha manual</span>
        <ul class="im-list">
          <li><span class="ic">≣</span>Lista de OS sem ordem geográfica</li>
          <li><span class="ic">🤔</span>Escolha manual do próximo ativo</li>
          <li><span class="ic">↩︎</span>Deslocamentos improdutivos e cruzados</li>
          <li><span class="ic">👤</span>Dependente da experiência individual</li>
        </ul>
        <span class="im-foot">✕ percurso não otimizado</span>
      </figure>
      <span class="imp-arrow reveal fade" style="--d:.7s">▸▸▸</span>
      <figure class="imp-map sol reveal right" style="--d:.6s">
        <span class="im-cap"><i class="d cyan"></i>Depois · roteirização geográfica</span>
        <ul class="im-list">
          <li><span class="ic">📍</span>Posicionamento geográfico de cada ativo</li>
          <li><span class="ic">📐</span>Cálculo de distância real (Haversine)</li>
          <li><span class="ic">⬡</span>Agrupamento operacional por proximidade</li>
          <li><span class="ic">🧭</span>Execução na sequência mais eficiente</li>
        </ul>
        <span class="im-foot">✓ menos deslocamento · mais ativos/dia</span>
      </figure>
    </div>
    <div class="imp-insight reveal fade" style="--d:.9s">
      <span>A proximidade vira <b>critério sistêmico</b> — a decisão de rota sai da cabeça do técnico e passa a ser <b class="cy">reproduzível</b>.</span>
    </div>
  </div>
</section>''')

    # --- SLIDE 7: MOTOR DE PRIORIZAÇÃO (pirâmide) ---
    niveis = [
        ('1', '🛡️', 'Segurança', 'Risco a pessoas e à operação vem sempre primeiro.', 'var(--rail)'),
        ('2', '🔧', 'Confiabilidade', 'Ativos que sustentam a disponibilidade da malha.', 'var(--gold)'),
        ('3', '⚠️', 'Criticidade', 'Grau de impacto do ativo na operação.', 'var(--gold-2)'),
        ('4', '📍', 'Proximidade', 'Entre iguais, o mais próximo é priorizado.', 'var(--cyan)'),
        ('5', '⏱️', 'Atraso Operacional', 'O que está atrasado sobe na fila.', 'var(--blue)'),
    ]
    prio = ''
    for i, (lv, ic, t, d, c) in enumerate(niveis):
        prio += (f'<div class="prow reveal up" style="--d:{.3+i*.1:.2f}s;--c:{c}"><span class="lvl">NÍVEL {lv}</span>'
                 f'<span class="pio">{ic}</span><div><h4>{t}</h4><p>{d}</p></div><span class="bignum">{lv}</span></div>')
    S.append(f'''
<section class="slide s7">
  <div class="slide-inner">
    <p class="kicker rail reveal left" style="--d:.05s">Motor de Priorização · Decisão Sistêmica</p>
    <h2 class="slide-title reveal up" style="--d:.13s">O técnico não decide <span class="grad-rail">o que é mais importante</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O sistema aplica cinco níveis em cascata. Atividades críticas <b>bloqueiam</b> as inferiores do mesmo grupo operacional.</p>
    <div class="prio">{prio}</div>
  </div>
</section>''')

    # --- SLIDE 8: REGRA DE BAIXA (equação / cadeia de validação) ---
    S.append('''
<section class="slide s8 imp">
  <div class="slide-inner">
    <p class="kicker green reveal left" style="--d:.05s">Governança da Baixa · Regra Sistêmica</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Uma baixa só é aceita se <span class="grad-green">todas as portas</span> passarem</h2>
    <p class="slide-lead reveal up" style="--d:.22s">A validação não é opinião: é uma cadeia de condições verificadas pelo servidor antes de gravar.</p>
    <div class="imp-calc">
      <div class="imp-factor reveal up" style="--d:.34s"><b>GPS válido</b><span>coordenada do hardware<br><i>(0,0) → rejeitada (HTTP 400)</i></span></div>
      <span class="imp-op reveal fade" style="--d:.42s">×</span>
      <div class="imp-factor reveal up" style="--d:.46s"><b class="num" data-count="2.0" data-decimals="1" data-prefix="≤ " data-suffix=" km" data-delay="500">0</b><span>dentro da cerca<br><i>Haversine · geofencing</i></span></div>
      <span class="imp-op reveal fade" style="--d:.54s">×</span>
      <div class="imp-factor reveal up" style="--d:.58s"><b>Foto</b><span>evidência tratada<br><i>EXIF removido</i></span></div>
      <span class="imp-op reveal fade" style="--d:.66s">×</span>
      <div class="imp-factor reveal up" style="--d:.70s"><b class="num" data-count="12" data-suffix=" h" data-delay="700">0</b><span>token válido<br><i>sessão HMAC</i></span></div>
      <span class="imp-eq reveal fade" style="--d:.8s">=</span>
      <div class="imp-result reveal scale" style="--d:.86s">
        <span class="ir-ico">✓</span>
        <div class="ir-tx"><span class="ir-lab">Baixa auditável</span><b>Aceita &amp; rastreável</b></div>
      </div>
    </div>
    <div class="imp-insight reveal fade" style="--d:1.1s">
      <span>Cada baixa carrega <b>quem, onde, quando e a prova</b> — e volta ao SAP como informação estruturada, não como digitação manual.</span>
    </div>
    <div class="feat" style="grid-template-columns:repeat(3,1fr);margin-top:22px;">
      <div class="card gn reveal up" style="--d:1.2s"><div class="fico">🛰️</div><h4>GPS obrigatório</h4><p>Fonte única: o hardware. Coordenada (0,0) é rejeitada na origem.</p></div>
      <div class="card cy reveal up" style="--d:1.3s"><div class="fico">📍</div><h4>Geofencing 2,0 km</h4><p>Distância Haversine do ativo cadastrado valida a presença real.</p></div>
      <div class="card gd reveal up" style="--d:1.4s"><div class="fico">🗂️</div><h4>Histórico auditável</h4><p>Cada evento fica registrado, consultável e à prova de desvio.</p></div>
    </div>
  </div>
</section>''')

    # --- SLIDE 9: OPERAÇÃO OFFLINE ---
    S.append('''
<section class="slide s9">
  <div class="orb" style="width:500px;height:500px;background:rgba(57,214,232,.12);left:-120px;bottom:-160px;"></div>
  <div class="slide-inner">
    <p class="kicker cyan reveal left" style="--d:.05s">Continuidade Operacional</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Funciona onde <span class="grad-cyan">não há sinal</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">Na serra, no túnel, no pátio remoto — a operação não para. O que foi feito sincroniza depois, sem duplicar.</p>
    <div class="feat" style="grid-template-columns:repeat(4,1fr);">
      <div class="card cy reveal up" style="--d:.34s"><div class="fico">📶</div><h4>Sem rádio, Wi-Fi ou 4G</h4><p>A ausência de rede deixa de ser um bloqueio de campo.</p></div>
      <div class="card cy reveal up" style="--d:.44s"><div class="fico">📱</div><h4>PWA + IndexedDB</h4><p>App instalável que guarda os dados localmente no dispositivo.</p></div>
      <div class="card cy reveal up" style="--d:.54s"><div class="fico">🔁</div><h4>Sincronização posterior</h4><p>Ao recuperar o sinal, os pacotes sobem para o servidor.</p></div>
      <div class="card cy reveal up" style="--d:.64s"><div class="fico">🛡️</div><h4>Controle de duplicidade</h4><p>Idempotência garante que nada é gravado duas vezes.</p></div>
    </div>
    <div class="imp-insight reveal fade" style="--d:.8s">
      <span>O endpoint <b>/sincronizar_baixa_offline</b> reconcilia o campo com o corporativo — a rede volta e o trabalho já está lá.</span>
    </div>
  </div>
</section>''')

    # --- SLIDE 10: GOVERNANÇA (matriz radial) ---
    gsat = [
        (50, 12, 500, 72, '🔐', 'Login Controlado', 'TOKEN 12H', 'var(--cyan)', .25, .55),
        (77, 25, 770, 150, '👥', 'Perfis de Acesso', 'PAPÉIS', 'var(--gold)', .32, .62),
        (88, 50, 880, 300, '📝', 'Registro de Acessos', 'AUDITORIA', 'var(--cyan)', .39, .69),
        (77, 75, 770, 450, '🛰️', 'GPS Obrigatório', 'HARDWARE', 'var(--green)', .46, .76),
        (50, 88, 500, 528, '📸', 'Evidência Fotográfica', 'POR BAIXA', 'var(--green)', .53, .83),
        (23, 75, 230, 450, '📍', 'Geofencing', '2,0 KM', 'var(--gold-2)', .60, .90),
        (12, 50, 120, 300, '🗂️', 'Histórico Auditável', 'CONSULTÁVEL', 'var(--cyan)', .67, .97),
        (23, 25, 230, 150, '🚦', 'Controle de Execução', 'TRAVAS', 'var(--rail)', .74, 1.04),
    ]
    glines = ''.join(f'<line class="mlink" x1="500" y1="300" x2="{x}" y2="{y}" stroke="{c}" stroke-opacity="0.4" style="--len:340;--md:{dl}s"></line>'
                     for _, _, x, y, _, _, _, c, dl, _ in gsat)
    gnodes = ''.join(f'<div class="mnode" style="left:{lf}%;top:{tp}%;--c:{c};--md:{dn}s;--sz:88px"><div class="morb" style="font-size:28px">{ic}</div><div class="mlabel" style="font-size:17px">{lb}</div><div class="msub">{sb}</div></div>'
                     for lf, tp, _, _, ic, lb, sb, c, _, dn in gsat)
    S.append(f'''
<section class="slide s10">
  <div class="slide-inner">
    <p class="kicker green reveal left" style="--d:.05s">Governança Operacional</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Confiança é boa; <span class="grad-green">controle sistêmico</span> é à prova de falhas</h2>
    <div class="matrix">
      <svg class="mlinks" viewBox="0 0 1000 600" preserveAspectRatio="none">{glines}</svg>
      <div class="mnode center" style="left:50%;top:50%;--c:var(--green);--md:.35s"><div class="morb"><div class="mtitle">Governança</div><div class="mtag">à prova de falhas</div></div></div>
      {gnodes}
    </div>
  </div>
</section>''')

    # --- SLIDE 11: INTEGRAÇÃO SAP ---
    S.append('''
<section class="slide s11">
  <div class="slide-inner">
    <p class="kicker reveal left" style="--d:.05s">Integração de Ciclo Completo · SAP</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Entra plano, sai <span class="grad">baixa estruturada</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">Fim do retrabalho de digitação manual de relatórios no escritório.</p>
    <div class="feat" style="grid-template-columns:repeat(3,1fr);align-items:stretch;">
      <div class="card cy reveal up" style="--d:.34s"><span class="tag o-cyan">Entrada</span><h4 style="margin-top:14px">Planejamento</h4><p>OS programadas e plano de manutenção vindos do SAP.</p></div>
      <div class="card gd reveal up" style="--d:.46s"><span class="tag o-gold">Processamento</span><h4 style="margin-top:14px">Regras operacionais</h4><p>Priorização, roteirização e consolidação da execução de campo.</p></div>
      <div class="card gn reveal up" style="--d:.58s"><span class="tag" style="color:var(--green);border:1px solid rgba(55,224,126,.4)">Saída</span><h4 style="margin-top:14px">Arquivo SAP · IW47</h4><p>Baixas em massa e informações estruturadas de volta ao corporativo.</p></div>
    </div>
    <div class="reveal up" style="--d:.7s;margin-top:26px;display:flex;gap:14px;flex-wrap:wrap;">
      <span class="pill"><b>/publicar_pacote</b> · gera o pacote do dia</span>
      <span class="pill"><b>/pacote/{id}</b> · consulta e download</span>
      <span class="pill"><b>/health</b> · disponibilidade do serviço</span>
    </div>
  </div>
</section>''')

    # --- SLIDE 12: ARQUITETURA ---
    stack = [
        ('Front-end', 'Streamlit + PWA', '🖥️', 'var(--cyan)'),
        ('Back-end', 'Python · FastAPI', '⚙️', 'var(--gold)'),
        ('Hospedagem', 'Render', '☁️', 'var(--cyan)'),
        ('Banco', 'PostgreSQL · Neon', '🗄️', 'var(--green)'),
        ('Storage', 'Supabase (fotos)', '📦', 'var(--gold-2)'),
        ('Segurança', 'HTTPS + API Key', '🔒', 'var(--rail)'),
        ('Offline', 'IndexedDB', '📴', 'var(--cyan)'),
        ('Geo', 'GPS HTML5 · Haversine', '🛰️', 'var(--green)'),
    ]
    sk = ''
    for i, (t, d, ic, c) in enumerate(stack):
        sk += (f'<div class="card reveal up" style="--d:{.3+i*.07:.2f}s;border-left:4px solid {c}">'
               f'<div class="fico">{ic}</div><h4 style="margin-top:10px">{t}</h4>'
               f'<p style="font-family:var(--mono);color:{c};font-size:15px;margin-top:6px">{d}</p></div>')
    S.append(f'''
<section class="slide s12">
  <div class="slide-inner">
    <p class="kicker reveal left" style="--d:.05s">Arquitetura Tecnológica · Corporativa</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Stack <span class="grad">enxuta</span>, pronta para escalar</h2>
    <div class="feat" style="grid-template-columns:repeat(4,1fr);">{sk}</div>
  </div>
</section>''')

    # --- SLIDE 13: BENEFÍCIOS ---
    S.append('''
<section class="slide s13">
  <div class="slide-inner">
    <p class="kicker green reveal left" style="--d:.05s">Benefícios para a Malha</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Menos improviso, <span class="grad-green">mais aderência</span></h2>
    <div class="feat" style="grid-template-columns:repeat(3,1fr);">
      <div class="card gn reveal up" style="--d:.30s"><div class="fico">🧭</div><h4>Menos deslocamentos improdutivos</h4><p>Roteirização por proximidade encurta o trajeto do dia.</p></div>
      <div class="card gn reveal up" style="--d:.38s"><div class="fico">👷</div><h4>Melhor uso das equipes</h4><p>Mais ativos atendidos com o mesmo efetivo.</p></div>
      <div class="card cy reveal up" style="--d:.46s"><div class="fico">📋</div><h4>Maior aderência ao plano</h4><p>Execução alinhada ao que foi programado no SAP.</p></div>
      <div class="card cy reveal up" style="--d:.54s"><div class="fico">🎯</div><h4>Priorização automática</h4><p>O crítico sobe na fila sem depender de julgamento.</p></div>
      <div class="card gd reveal up" style="--d:.62s"><div class="fico">🔗</div><h4>Evidência rastreável</h4><p>Foto, GPS e horário atrelados a cada baixa.</p></div>
      <div class="card gd reveal up" style="--d:.70s"><div class="fico">📊</div><h4>Base para analytics</h4><p>Dados estruturados abrem caminho para inteligência preditiva.</p></div>
    </div>
  </div>
</section>''')

    # --- SLIDE 14: EVOLUÇÃO (timeline) ---
    tl = [
        ('Entregue', '🛡️', 'Governança operacional', 'HOJE', 'var(--green)'),
        ('Entregue', '🧭', 'Roteirização + GPS', 'HOJE', 'var(--green)'),
        ('Entregue', '📴', 'PWA Offline + SAP', 'HOJE', 'var(--green)'),
        ('Próximo', '🏢', 'Hospedagem corp. · SSO/AD', 'CURTO', 'var(--gold)'),
        ('Próximo', '📊', 'Dashboards executivos', 'MÉDIO', 'var(--gold-2)'),
        ('Visão', '🤖', 'Preditiva · recomendação de rotas', 'FUTURO', 'var(--cyan)'),
    ]
    tsteps = ''
    for i, (st, ic, t, tag, c) in enumerate(tl):
        tsteps += (f'<div class="tstep reveal up" style="--d:{.3+i*.1:.2f}s;--c:{c}"><div class="tdot"></div>'
                   f'<div style="font-size:26px">{ic}</div><h4>{t}</h4>'
                   f'<span class="tst" style="color:{c}">{tag}</span></div>')
    S.append(f'''
<section class="slide s14">
  <div class="slide-inner">
    <p class="kicker reveal left" style="--d:.05s">Evolução · Próximos Passos</p>
    <h2 class="slide-title reveal up" style="--d:.13s">Da base sólida à <span class="grad">inteligência preditiva</span></h2>
    <p class="slide-lead reveal up" style="--d:.22s">O que já está no ar sustenta a operação hoje; a evolução amplia governança, visão executiva e recomendação automática.</p>
    <div class="tl">{tsteps}</div>
  </div>
</section>''')

    # --- SLIDE 15: ENCERRAMENTO ---
    endflow = ''
    for i, (nm, c) in enumerate([('Planejamento', 'var(--cyan)'), ('Malha', 'var(--gold)'), ('Execução', 'var(--green)'), ('Governança', 'var(--gold-2)'), ('SAP', 'var(--blue)')]):
        if i > 0:
            endflow += '<span style="color:var(--dim);margin:0 6px;">→</span>'
        endflow += f'<span style="color:{c};font-weight:800;">{nm}</span>'
    S.append(f'''
<section class="slide end s15">
  <div class="end-photo"><i></i></div>
  <div class="slide-inner">
    <p class="kicker reveal down" style="--d:.05s">SGO Eletroeletrônica MRS</p>
    <h2 class="reveal up" style="--d:.2s;font-size:76px;font-weight:800;line-height:1.02;letter-spacing:-.02em;margin-top:18px;">Mais do que um <span class="grad">aplicativo</span></h2>
    <p class="reveal up" style="--d:.4s;font-size:26px;color:var(--soft);margin-top:20px;max-width:1000px;">Uma camada digital entre {endflow}.</p>
    <p class="reveal up" style="--d:.7s;font-size:23px;color:var(--white);margin-top:34px;">Transformando conhecimento operacional em <span class="grad">inteligência sistêmica</span>.</p>
    <p class="reveal fade" style="--d:1s;font-family:var(--mono);font-size:15px;letter-spacing:.14em;color:var(--dim);margin-top:44px;text-transform:uppercase;">Obrigado</p>
  </div>
</section>''')

    return '\n'.join(S)


def main():
    slides = build()
    css = CSS.replace('%MAP%', MAP_URI)
    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SGO Eletroeletrônica MRS — Apresentação</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap">
<style>{css}</style>
</head>
<body>
<div class="deck-progress"><span id="progressBar"></span></div>
<div class="hud-corner"><span class="brand"><b>SGO</b> · Eletroeletrônica MRS</span></div>
<nav class="deck-dots" id="deckDots" aria-label="Ir para slide"></nav>
<div class="deck-viewport"><main class="deck-stage" id="deckStage">
{slides}
</main></div>
<div class="deck-controls">
  <button id="btnPrev" class="dc-btn" aria-label="Anterior">◂</button>
  <button id="btnNext" class="dc-btn" aria-label="Próximo">▸</button>
  <button id="btnFs" class="dc-btn fs" aria-label="Tela cheia">⛶</button>
</div>
<div class="page-counter"><b id="curNum">01</b><i>/</i><span id="totNum">15</span></div>
<div class="kb-hint" id="kbHint">use <b>← →</b> para navegar · <b>F</b> tela cheia</div>
<script>{JS}</script>
</body>
</html>'''
    out = os.path.join(BASE, 'Pitch_Eletroeletronica_SGO_Premiumv6.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    n = slides.count('<section class="slide')
    print('Premium gerado:', out)
    print('Slides:', n, '| Tamanho MB:', round(len(html) / 1048576, 2))


if __name__ == '__main__':
    main()
