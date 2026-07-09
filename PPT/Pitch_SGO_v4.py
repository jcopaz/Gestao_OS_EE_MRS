# -*- coding: utf-8 -*-
import os
import webbrowser

def main():
    #region Sessão 0 — Configuração
    h = ''
    TS = 15  # total de slides
    #endregion

    #region Sessão 1 — Head e CSS Base
    h += '<!DOCTYPE html><html lang=pt-BR><head><meta charset=UTF-8>'
    h += '<meta name=viewport content=\'width=device-width,initial-scale=1\'>'
    h += '<title>SGO Eletroeletrônica MRS | Pitch</title>'
    h += '<link href=\'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600;700&family=Inter:wght@300;400;700;900&display=swap\' rel=stylesheet>'
    h += '<style>'

    h += ':root{--bg:#0B1120;--txt:#F8FAFC;--mu:#94A3B8;--ac:#00E5FF;--yl:#F59E0B;--gn:#10B981;--rd:#EF4444;--vl:#A78BFA;--glass:rgba(15,23,42,0.65);--border:rgba(0,229,255,0.25);}'
    h += '*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden;background:var(--bg);color:var(--txt);font-family:\'Inter\',sans-serif;}'

    # Efeitos de Fundo
    h += '.bg-main{position:fixed;inset:0;z-index:0;background:linear-gradient(rgba(11, 17, 32, 0.85), rgba(11, 17, 32, 0.90)), url("fundo.png");background-size:cover;background-position:center;}'
    h += '.bg-glow{position:fixed;width:60vw;height:60vw;background:radial-gradient(circle,rgba(0,229,255,0.08),transparent 60%);top:-20%;left:-10%;z-index:1;border-radius:50%;filter:blur(80px);}'
    h += '.bg-glow2{position:fixed;width:50vw;height:50vw;background:radial-gradient(circle,rgba(245,158,11,0.05),transparent 60%);bottom:-20%;right:-10%;z-index:1;border-radius:50%;filter:blur(80px);}'
    h += '#cvN{position:fixed;inset:0;z-index:2;pointer-events:none;}'
    #endregion

    #region Sessão 2 — CSS: Componentes e Layouts
    h += 'h1,h2,h3{font-family:\'Space Grotesk\',sans-serif;font-weight:700;line-height:1.2;}'
    h += '.hl{color:var(--ac)}.hl-y{color:var(--yl)}.hl-g{color:var(--gn)}.hl-r{color:var(--rd)}.hl-v{color:var(--vl)}'

    h += '.sw{position:fixed;inset:0;z-index:5;padding-top:30px;}.sd{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem 6vw;opacity:0;transform:scale(0.95);transition:all 0.6s cubic-bezier(0.16,1,0.3,1);pointer-events:none}.sd.ac{opacity:1;transform:scale(1);pointer-events:auto}.si{max-width:1400px;width:100%}'
    h += '.an{opacity:0;transform:translateY(20px);transition:all 0.6s ease}.sd.ac .an{opacity:1;transform:translateY(0)}'
    h += '.sd.ac .an:nth-child(1){transition-delay:0.1s}.sd.ac .an:nth-child(2){transition-delay:0.2s}.sd.ac .an:nth-child(3){transition-delay:0.3s}.sd.ac .an:nth-child(4){transition-delay:0.4s}.sd.ac .an:nth-child(5){transition-delay:0.5s}.sd.ac .an:nth-child(6){transition-delay:0.6s}'

    h += '.glass{background:var(--glass);backdrop-filter:blur(20px);border:1px solid var(--border);border-radius:20px;padding:2rem;box-shadow:0 10px 40px rgba(0,0,0,0.5);}'
    h += '.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:1.5rem;width:100%;margin-top:2rem;}'
    h += '.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:2rem;width:100%;margin-top:2rem;}'
    h += '.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:2rem;width:100%;margin-top:2rem;align-items:center;}'

    h += '.big-num{font-size:4rem;font-weight:900;background:linear-gradient(135deg,#fff,var(--mu));-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1;}'
    h += '.big-num.ac{background:linear-gradient(135deg,var(--ac),#0077ff);-webkit-background-clip:text;}'
    h += '.big-num.yl{background:linear-gradient(135deg,var(--yl),#ff5500);-webkit-background-clip:text;}'

    # Chips / listas de verificação
    h += '.chips{display:flex;flex-wrap:wrap;gap:0.8rem;margin-top:1.5rem;}'
    h += '.chip{background:rgba(0,229,255,0.06);border:1px solid var(--border);border-radius:100px;padding:0.6rem 1.2rem;font-size:0.95rem;display:flex;align-items:center;gap:0.5rem;}'

    # Ticker Tape (Painel Rolando)
    h += '.tkb{position:fixed;top:0;left:0;right:0;height:35px;background:rgba(11,17,32,0.9);border-bottom:1px solid rgba(0,229,255,0.2);z-index:9999;display:flex;align-items:center;backdrop-filter:blur(10px);overflow:hidden;}'
    h += '.tkt{display:flex;width:max-content;animation:tks 40s linear infinite;}'
    h += '.tkc{display:flex;white-space:nowrap;}'
    h += '.tki{font-family:\'Space Grotesk\',sans-serif;font-size:11px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:var(--ac);padding:0 2em;}'
    h += '@keyframes tks{to{transform:translateX(-50%);}}'

    # Fluxograma / Nós / Setas
    h += '.flow{display:flex;align-items:center;justify-content:space-between;width:100%;background:rgba(0,0,0,0.4);padding:2rem;border-radius:100px;border:1px solid rgba(255,255,255,0.05);}'
    h += '.node{display:flex;flex-direction:column;align-items:center;text-align:center;gap:0.5rem;z-index:2;}'
    h += '.node-circle{width:80px;height:80px;border-radius:50%;background:var(--glass);border:2px solid var(--mu);display:flex;align-items:center;justify-content:center;font-size:2rem;box-shadow:0 0 20px rgba(0,0,0,0.5);transition:all 0.3s;}'
    h += '.node.active .node-circle{border-color:var(--ac);box-shadow:0 0 30px rgba(0,229,255,0.4);background:rgba(0,229,255,0.1);}'
    h += '.arrow{flex:1;height:2px;background:linear-gradient(90deg,transparent,var(--ac),transparent);margin:0 1rem;position:relative;opacity:0.5;}'
    h += '.arrow::after{content:"▶";position:absolute;right:10%;top:-10px;color:var(--ac);}'

    # Pilha de prioridade
    h += '.prio{display:flex;flex-direction:column;gap:0.6rem;width:100%;}'
    h += '.prio-row{display:flex;align-items:center;gap:1rem;background:var(--glass);border-left:4px solid var(--mu);border-radius:10px;padding:0.9rem 1.2rem;}'
    h += '.prio-row .lv{font-family:\'Space Grotesk\';font-weight:700;font-size:0.8rem;color:var(--mu);width:70px;}'

    h += '.radar{width:200px;height:200px;border-radius:50%;border:1px solid rgba(0,229,255,0.3);position:relative;display:flex;align-items:center;justify-content:center;margin:0 auto;}'
    h += '.radar::before{content:"";position:absolute;inset:0;border-radius:50%;border:1px solid var(--ac);animation:pulse 2s infinite;}'
    h += '.radar-dot{width:15px;height:15px;background:var(--ac);border-radius:50%;box-shadow:0 0 20px var(--ac);}'
    h += '.target-dot{width:10px;height:10px;background:var(--rd);border-radius:50%;position:absolute;top:30%;right:20%;box-shadow:0 0 10px var(--rd);}'
    h += '@keyframes pulse{0%{transform:scale(0.5);opacity:1;}100%{transform:scale(1.5);opacity:0;}}'
    h += '.img-glow{width:100%;max-height:45vh;object-fit:cover;border-radius:12px;border:1px solid var(--ac);box-shadow:0 0 30px rgba(0,229,255,0.2);}'

    h += '.nav-dots{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);display:flex;gap:12px;z-index:10;}'
    h += '.dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.2);cursor:pointer;transition:all 0.3s;}'
    h += '.dot.active{background:var(--ac);transform:scale(1.5);box-shadow:0 0 10px var(--ac);}'
    h += '.nav-btn{position:fixed;top:50%;transform:translateY(-50%);font-size:2rem;color:rgba(255,255,255,0.2);cursor:pointer;transition:all 0.3s;z-index:10;}.nav-btn:hover{color:var(--ac);}.nav-prev{left:2rem;}.nav-next{right:2rem;}'
    # Matriz radial (constelação: nó central + satélites) — infográfico
    h += '.matrix{position:relative;width:100%;max-width:1150px;height:60vh;min-height:460px;margin:1rem auto 0;}'
    h += '.matrix svg.mlinks{position:absolute;inset:0;width:100%;height:100%;overflow:visible;z-index:1;}'
    h += '.mlink{stroke-width:1.5;fill:none;stroke-dasharray:var(--len,700);stroke-dashoffset:var(--len,700);transition:stroke-dashoffset 1.3s cubic-bezier(0.16,1,0.3,1);transition-delay:var(--d,0.2s);}'
    h += '.sd.ac .mlink{stroke-dashoffset:0;}'
    h += '.mnode{position:absolute;transform:translate(-50%,-50%) scale(0.6);opacity:0;transition:opacity 0.6s cubic-bezier(0.16,1,0.3,1),transform 0.6s cubic-bezier(0.16,1,0.3,1);transition-delay:var(--d,0s);display:flex;flex-direction:column;align-items:center;gap:0.55rem;text-align:center;z-index:3;width:180px;}'
    h += '.sd.ac .mnode{opacity:1;transform:translate(-50%,-50%) scale(1);}'
    h += '.morb{width:var(--sz,104px);height:var(--sz,104px);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:2rem;color:var(--c,var(--ac));background:radial-gradient(circle at 38% 32%,color-mix(in srgb,var(--c,var(--ac)) 26%,rgba(8,18,34,0.9)) 0%,rgba(6,14,28,0.94) 70%);border:1.5px solid color-mix(in srgb,var(--c,var(--ac)) 55%,transparent);box-shadow:0 0 34px -6px color-mix(in srgb,var(--c,var(--ac)) 70%,transparent),inset 0 0 26px -10px color-mix(in srgb,var(--c,var(--ac)) 80%,transparent);}'
    h += '.mnode .mlabel{font-family:\'Space Grotesk\',sans-serif;font-size:1rem;font-weight:700;color:var(--txt);text-shadow:0 2px 10px #000;line-height:1.2;}'
    h += '.mnode .msub{font-family:\'Space Grotesk\',sans-serif;font-size:0.7rem;letter-spacing:0.14em;color:var(--mu);text-transform:uppercase;}'
    h += '.mnode.center{width:230px;}'
    h += '.mnode.center .morb{width:210px;height:210px;border-width:2px;flex-direction:column;box-shadow:0 0 70px -4px color-mix(in srgb,var(--ac) 65%,transparent),inset 0 0 50px -16px var(--ac);}'
    h += '.mnode.center .mtitle{font-family:\'Space Grotesk\',sans-serif;font-size:1.6rem;font-weight:800;color:var(--txt);line-height:1.1;padding:0 1rem;}'
    h += '.mnode.center .mtag{font-family:\'Space Grotesk\',sans-serif;font-size:0.72rem;letter-spacing:0.18em;color:var(--ac);margin-top:0.4rem;text-transform:uppercase;}'
    h += '</style></head>'
    #endregion

    #region Sessão 3 — HTML: Body e Layout
    h += '<body><div class="bg-main"></div><div class="bg-glow"></div><div class="bg-glow2"></div><canvas id="cvN"></canvas>'

    # Ticker / Painel Rolando
    ticker = '⚡ SGO ELETROELETRÔNICA MRS ⚡ INTELIGÊNCIA OPERACIONAL ⚡ ROTEIRIZAÇÃO GEOGRÁFICA ⚡ PRIORIZAÇÃO SISTÊMICA ⚡ GEOFENCING 2,0 KM ⚡ GPS OBRIGATÓRIO ⚡ PWA OFFLINE HTTPS ⚡ INTEGRAÇÃO SAP / IW47 ⚡ GOVERNANÇA AUDITÁVEL'
    h += '<div class="tkb"><div class="tkt">'
    h += f'<div class="tkc"><span class="tki">{ticker}</span></div>'
    h += f'<div class="tkc"><span class="tki">{ticker}</span></div>'
    h += '</div></div>'

    # Dica de Tela Cheia
    h += '<div style="position:fixed;top:45px;right:20px;color:rgba(255,255,255,0.3);font-size:0.8rem;z-index:9999;font-family:\'Space Grotesk\', sans-serif;">Pressione [F] para Tela Cheia</div>'

    h += '<div class="nav-prev nav-btn" onclick="prevSlide()">❮</div><div class="nav-next nav-btn" onclick="nextSlide()">❯</div>'
    h += '<div class="nav-dots" id="dots">'
    for i in range(TS): h += f'<div class="dot {"active" if i==0 else ""}"></div>'
    h += '</div><div class="sw">'
    #endregion

    #region SLIDE 1: Capa
    h += '<div class="sd ac"><div class="si" style="text-align:center;">'
    h += '<h3 class="an" style="color:var(--mu);letter-spacing:0.3em;text-transform:uppercase;">Inteligência Operacional Aplicada à Malha</h3>'
    h += '<h1 class="an" style="font-weight:900;margin:1rem 0;font-size:4.5rem;">SGO <span class="hl">Eletroeletrônica</span> MRS</h1>'
    h += '<p class="an" style="font-size:1.5rem;color:var(--mu);max-width:900px;margin:0 auto;">Conectando SAP, ativos ferroviários, geolocalização e execução em campo.</p>'
    h += '<div class="an" style="margin-top:3rem;display:flex;gap:2rem;justify-content:center;flex-wrap:wrap;">'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl" style="font-size:1.5rem;font-weight:700;">SAP</span><br><span style="font-size:0.8rem">Planejamento</span></div>'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl-y" style="font-size:1.5rem;font-weight:700;">GPS</span><br><span style="font-size:0.8rem">Execução em Campo</span></div>'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl-g" style="font-size:1.5rem;font-weight:700;">PWA</span><br><span style="font-size:0.8rem">Operação Offline</span></div>'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl-v" style="font-size:1.5rem;font-weight:700;">100%</span><br><span style="font-size:0.8rem">Governança</span></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 2: O Problema
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">O Desafio da Manutenção em <span class="hl-r">Malha</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:2.5rem;font-size:1.2rem;">A operação depende, simultaneamente, de cinco frentes de decisão.</p>'
    h += '<div class="an grid-3" style="gap:1.5rem;">'
    itens = [
        ('🧠','Conhecimento dos Ativos','Saber o que é cada equipamento e o que ele exige.'),
        ('🗺️','Conhecimento Geográfico','Onde estão os ativos e como se deslocar entre eles.'),
        ('🎯','Priorização Correta','O que atacar primeiro diante de dezenas de OS.'),
        ('📋','Cumprimento do Planejamento','Executar aderente ao que foi programado.'),
        ('📸','Evidências da Execução','Comprovar o que foi feito, onde e quando.'),
    ]
    for ic,t,d in itens:
        h += f'<div class="glass" style="border-left:4px solid var(--yl);padding:1.5rem;"><div style="font-size:2.2rem;margin-bottom:0.8rem;">{ic}</div><h3 style="margin-bottom:0.5rem;color:var(--txt);">{t}</h3><p style="color:var(--mu);font-size:0.95rem;line-height:1.5;">{d}</p></div>'
    h += '<div class="glass" style="padding:1.5rem;display:flex;align-items:center;border-left:4px solid var(--rd);"><p style="color:var(--txt);font-size:1.05rem;line-height:1.5;">Hoje, parte dessa inteligência está <strong>concentrada na experiência individual</strong> — um risco de continuidade para a malha.</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 3: O Conceito (Matriz Radial — infográfico)
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:0.6rem;">O que é o <span class="hl">SGO</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:0.5rem;font-size:1.2rem;">Um <strong>mecanismo de decisão operacional</strong> — não apenas um apontador de OS.</p>'

    # Nós satélites: (left%, top%, viewBox x, viewBox y, ícone, rótulo, sublabel, cor, delay-linha, delay-nó)
    sat = [
        (28, 21.7, 280, 130, '🗂️', 'Organiza a execução',       'FLUXO',          'var(--ac)', 0.25, 0.55),
        (50, 15.8, 500,  95, '🎯', 'Prioriza o que é crítico',   'SEGURANÇA',      'var(--rd)', 0.35, 0.65),
        (72, 21.7, 720, 130, '🔒', 'Controla a aderência',       'PLANEJAMENTO',   'var(--yl)', 0.45, 0.75),
        (72, 78.3, 720, 470, '🔄', 'Integra ao SAP',             'IW47 · BAIXAS',  '#3b82f6',   0.55, 0.85),
        (50, 84.2, 500, 505, '📸', 'Registra evidências',        'GPS · FOTO',     'var(--gn)', 0.65, 0.95),
        (28, 78.3, 280, 470, '💎', 'Padroniza a boa prática',    'CONHECIMENTO',   '#A78BFA',   0.75, 1.05),
    ]
    h += '<div class="matrix an" style="transition-delay:0.2s;">'
    # Camada de linhas (SVG) — nó central (500,300) até cada satélite
    h += '<svg class="mlinks" viewBox="0 0 1000 600" preserveAspectRatio="none">'
    for _,_,x,y,_,_,_,cor,dl,_ in sat:
        h += f'<line class="mlink" x1="500" y1="300" x2="{x}" y2="{y}" stroke="{cor}" stroke-opacity="0.4" style="--len:320;--d:{dl}s"></line>'
    h += '</svg>'
    # Nó central
    h += ('<div class="mnode center" style="left:50%;top:50%;--c:var(--ac);--d:0.35s">'
          '<div class="morb"><div class="mtitle">SGO</div><div class="mtag">a proposta</div></div></div>')
    # Satélites
    for lft,top,_,_,ic,lbl,sub,cor,_,dn in sat:
        h += (f'<div class="mnode" style="left:{lft}%;top:{top}%;--c:{cor};--d:{dn}s">'
              f'<div class="morb">{ic}</div><div class="mlabel">{lbl}</div><div class="msub">{sub}</div></div>')
    h += '</div>'
    h += '</div></div>'
    #endregion

    #region SLIDE 4: O Ciclo (Fluxo Ponta a Ponta)
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">O <span class="hl">Ciclo</span> Operacional Completo</h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:3rem;font-size:1.15rem;">Do planejamento no SAP ao retorno estruturado — com o motor do SGO no centro.</p>'
    h += '<div class="an flow">'
    h += '<div class="node"><div class="node-circle" style="background:#fff;"><img src="https://upload.wikimedia.org/wikipedia/commons/5/59/SAP_2011_logo.svg" style="width:40px;"></div><h3 style="margin-top:0.5rem">SAP</h3><p style="font-size:0.75rem;color:var(--mu)">Planejamento<br>OS Programadas</p></div>'
    h += '<div class="arrow"></div>'
    h += '<div class="node active"><div class="node-circle" style="border-color:var(--yl);box-shadow:0 0 20px var(--yl);">⚙️</div><h3 class="hl-y" style="margin-top:0.5rem">Motor SGO</h3><p style="font-size:0.75rem;color:var(--mu)">Priorização · Regras<br>Geo · Governança</p></div>'
    h += '<div class="arrow"></div>'
    h += '<div class="node active"><div class="node-circle">📱</div><h3 class="hl" style="margin-top:0.5rem">Campo</h3><p style="font-size:0.75rem;color:var(--mu)">GPS · Fotos<br>Evidências · Offline</p></div>'
    h += '<div class="arrow"></div>'
    h += '<div class="node"><div class="node-circle">🗄️</div><h3 style="margin-top:0.5rem">Banco Corporativo</h3><p style="font-size:0.75rem;color:var(--mu)">PostgreSQL<br>Histórico Auditável</p></div>'
    h += '<div class="arrow"></div>'
    h += '<div class="node"><div class="node-circle" style="background:#fff;"><img src="https://upload.wikimedia.org/wikipedia/commons/5/59/SAP_2011_logo.svg" style="width:40px;"></div><h3 style="margin-top:0.5rem">Retorno SAP</h3><p style="font-size:0.75rem;color:var(--mu)">IW47 · Baixas<br>em Massa</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 5: Inteligência da Malha
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">Inteligência Ferroviária <span class="hl">Incorporada</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:1rem;font-size:1.2rem;">O sistema conhece a malha — não depende da memória de quem está no campo.</p>'
    h += '<div class="an chips" style="justify-content:center;">'
    saberes = ['Pátios','Bases operacionais','Coordenadas dos ativos','Distâncias reais','Tipo de intervalo (CI/SI)','Criticidade','Regras de confiabilidade','Regras de segurança','Histórico operacional']
    for s in saberes:
        h += f'<div class="chip"><span class="hl-g">✅</span>{s}</div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 6: Roteirização Inteligente
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:3rem;">Da <span class="hl-r">Lista</span> para a <span class="hl">Geografia</span></h1>'
    h += '<div class="an grid-2">'
    h += '<div class="glass" style="border-left:4px solid var(--rd);">'
    h += '<h3 class="hl-r" style="margin-bottom:1rem;">Antes</h3>'
    h += '<ul style="margin-left:1.2rem;color:var(--mu);line-height:2.2;font-size:1.1rem;"><li>Lista de OS</li><li>Escolha manual pelo "feeling"</li><li>Viagens perdidas</li></ul></div>'
    h += '<div class="glass" style="border-left:4px solid var(--ac);">'
    h += '<h3 class="hl" style="margin-bottom:1rem;">Depois</h3>'
    h += '<ul style="margin-left:1.2rem;color:var(--txt);line-height:2.2;font-size:1.1rem;"><li>Posicionamento geográfico (GPS)</li><li>Cálculo de distância real (Haversine)</li><li>Agrupamento operacional por proximidade</li><li>Execução por raio ajustável (início 1 km)</li></ul></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 7: Motor de Priorização
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="margin-bottom:1rem;text-align:center;">Decisão <span class="hl">Sistêmica</span>, Não Humana</h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:2rem;font-size:1.15rem;">O técnico não precisa decidir o que é mais importante. O sistema aplica a hierarquia.</p>'
    h += '<div class="an grid-2" style="align-items:stretch;">'
    h += '<div class="prio">'
    niveis = [
        ('Nível 1','Segurança','var(--rd)'),
        ('Nível 2','Confiabilidade','var(--yl)'),
        ('Nível 3','Criticidade','var(--ac)'),
        ('Nível 4','Proximidade','var(--gn)'),
        ('Nível 5','Atraso operacional','var(--vl)'),
    ]
    for lv,nm,cor in niveis:
        h += f'<div class="prio-row" style="border-left-color:{cor};"><span class="lv">{lv}</span><span style="font-size:1.1rem;font-weight:600;">{nm}</span></div>'
    h += '</div>'
    h += '<div class="glass" style="display:flex;flex-direction:column;justify-content:center;border-color:var(--rd);">'
    h += '<div class="radar" style="margin-bottom:2rem;"><div class="radar-dot"></div><div class="target-dot"></div></div>'
    h += '<p style="color:var(--txt);font-size:1.1rem;line-height:1.6;text-align:center;">Atividades críticas <strong>bloqueiam</strong> atividades inferiores do mesmo grupo operacional.<br><br>As bloqueadas permanecem <strong>visíveis</strong> (sombreadas + 🔒), forçando a resolução da emergência antes das preventivas.</p>'
    h += '</div></div></div></div>'
    #endregion

    #region SLIDE 8: Operação Offline
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">Continuidade <span class="hl-y">Operacional</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:2rem;font-size:1.2rem;">O sistema funciona sem rádio, sem Wi-Fi e sem 4G — via PWA instalado em contexto seguro (HTTPS), nunca por arquivo solto.</p>'
    h += '<div class="an grid-3">'
    h += '<div class="glass" style="text-align:center;"><div style="font-size:3rem;margin-bottom:1rem;">📡</div><h3>1. Publicar a Rota</h3><p style="margin-top:1rem;color:var(--mu);">Com sinal, o gestor publica o pacote. O técnico abre o link seguro (HTTPS) uma vez e o app fica instalado.</p></div>'
    h += '<div class="glass" style="text-align:center;border-color:var(--yl);box-shadow:0 0 30px rgba(245,158,11,0.2);"><div style="font-size:3rem;margin-bottom:1rem;">📴</div><h3 class="hl-y">2. Modo Local Seguro</h3><p style="margin-top:1rem;color:var(--mu);">No trecho sem sinal, o PWA roda no aparelho. O <strong>GPS permanece ativo</strong> e apontamentos/fotos ficam em fila local (IndexedDB).</p></div>'
    h += '<div class="glass" style="text-align:center;"><div style="font-size:3rem;margin-bottom:1rem;">🔄</div><h3>3. Sincronização</h3><p style="margin-top:1rem;color:var(--mu);">Ao reconectar, envia tudo de uma vez. Gravação idempotente: <strong>zero perda e zero duplicidade</strong>.</p></div>'
    h += '</div>'
    h += '<div class="an chips" style="justify-content:center;margin-top:1.5rem;">'
    for t in ['PWA (Service Worker + manifest)','IndexedDB','Sincronização posterior','Controle de duplicidade']:
        h += f'<div class="chip"><span class="hl">▹</span>{t}</div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 9: Governança
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">Governança <span class="hl-g">Operacional</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:1rem;font-size:1.2rem;">Confiança é boa; controle sistêmico é à prova de falhas.</p>'
    h += '<div class="an grid-4">'
    govs = [
        ('🔐','Login Controlado','Token persistente (12h) que sobrevive à câmera.'),
        ('👥','Perfis de Acesso','Separação de responsabilidades por papel.'),
        ('📝','Registro de Acessos','Rastro de quem entrou e quando.'),
        ('🛰️','GPS Obrigatório','Fonte única: o hardware. Coordenada (0,0) rejeitada.'),
        ('📸','Evidência Fotográfica','Foto tratada e arquivada por baixa.'),
        ('📍','Geofencing','Baixa só dentro de 2,0 km do ativo (Haversine).'),
        ('🗂️','Histórico Auditável','Cada evento fica registrado e consultável.'),
        ('🚦','Controle de Execução','Travas sistêmicas contra desvio do plano.'),
    ]
    for ic,t,d in govs:
        h += f'<div class="glass" style="padding:1.4rem;"><div style="font-size:2rem;margin-bottom:0.6rem;">{ic}</div><h3 class="hl-g" style="font-size:1rem;">{t}</h3><p style="font-size:0.82rem;color:var(--mu);margin-top:0.5rem;">{d}</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 10: Integração SAP
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:3rem;">Integração de <span class="hl">Ciclo Completo</span></h1>'
    h += '<div class="an grid-3">'
    h += '<div class="glass" style="border-top:4px solid var(--ac);"><h3 class="hl" style="margin-bottom:1rem;">Entrada</h3><ul style="margin-left:1.2rem;color:var(--mu);line-height:2;font-size:1.05rem;"><li>Planejamento</li><li>OS programadas</li></ul></div>'
    h += '<div class="glass" style="border-top:4px solid var(--yl);"><h3 class="hl-y" style="margin-bottom:1rem;">Processamento</h3><ul style="margin-left:1.2rem;color:var(--mu);line-height:2;font-size:1.05rem;"><li>Regras operacionais</li><li>Consolidação de execução</li></ul></div>'
    h += '<div class="glass" style="border-top:4px solid var(--gn);"><h3 class="hl-g" style="margin-bottom:1rem;">Saída</h3><ul style="margin-left:1.2rem;color:var(--mu);line-height:2;font-size:1.05rem;"><li>Arquivo SAP</li><li>IW47</li><li>Baixas em massa</li><li>Informações estruturadas</li></ul></div>'
    h += '</div>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-top:2rem;font-size:1.1rem;">Fim do retrabalho de digitação manual de relatórios no escritório.</p>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 11: Arquitetura Corporativa
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">Arquitetura <span class="hl">Tecnológica</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:1rem;font-size:1.15rem;">A stack real, em nomes — para quem constrói sistemas.</p>'
    h += '<div class="an grid-4">'
    arq = [
        ('🖥️','Front-end','Streamlit + PWA','var(--ac)'),
        ('🐍','Back-end','Python','var(--yl)'),
        ('⚡','API','FastAPI','var(--gn)'),
        ('🐘','Banco','PostgreSQL','var(--vl)'),
        ('☁️','Storage','Supabase','var(--ac)'),
        ('🔒','Segurança','HTTPS + API Key','var(--rd)'),
        ('🛰️','Geolocalização','GPS HTML5 + Haversine','var(--gn)'),
        ('🔄','Idempotência','Upsert ON CONFLICT','var(--yl)'),
    ]
    for ic,t,d,cor in arq:
        h += f'<div class="glass" style="padding:1.5rem;text-align:center;border-bottom:3px solid {cor};"><div style="font-size:2.2rem;margin-bottom:0.8rem;">{ic}</div><h3 style="font-size:1rem;color:{cor}">{t}</h3><p style="font-size:0.9rem;color:var(--txt);margin-top:0.6rem;">{d}</p></div>'
    h += '</div>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-top:1.8rem;font-size:0.95rem;font-family:\'Space Grotesk\';letter-spacing:0.05em;">Endpoints: /sincronizar_baixa_offline · /health · /publicar_pacote · /pacote/{id}</p>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 12: Proteção do Conhecimento Operacional
    h += '<div class="sd"><div class="si" style="text-align:center;">'
    h += '<h1 class="an" style="margin-bottom:1.5rem;">Transformando <span class="hl-v">Experiência</span> em Sistema</h1>'
    h += '<p class="an" style="font-size:1.35rem;color:var(--mu);max-width:900px;margin:0 auto 2.5rem;">A experiência dos técnicos deixa de estar apenas nas pessoas. O conhecimento passa a estar no sistema — e a boa prática é reproduzida de forma padronizada.</p>'
    h += '<div class="an grid-4" style="margin-top:0;">'
    for ic,t in [('📐','nas regras'),('🧮','nos algoritmos'),('🗃️','nos cadastros'),('🗺️','na inteligência geográfica')]:
        h += f'<div class="glass" style="padding:2rem 1.5rem;"><div style="font-size:2.5rem;margin-bottom:1rem;">{ic}</div><h3 class="hl-v" style="font-size:1.1rem;">{t}</h3></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 13: Benefícios para a Malha
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:2.5rem;">Benefícios para a <span class="hl-g">Malha</span></h1>'
    h += '<div class="an grid-3">'
    bens = [
        ('🚗','Menos deslocamentos improdutivos'),
        ('👷','Melhor utilização das equipes'),
        ('📋','Maior aderência ao planejamento'),
        ('🚦','Priorização automática'),
        ('📸','Evidência rastreável'),
        ('🧠','Menor dependência de conhecimento tácito'),
    ]
    for ic,t in bens:
        h += f'<div class="glass" style="padding:1.6rem;display:flex;align-items:center;gap:1rem;"><div style="font-size:2rem;">{ic}</div><h3 style="font-size:1.05rem;">{t}</h3></div>'
    h += '</div>'
    h += '<div class="an glass" style="margin-top:1.5rem;text-align:center;border-color:var(--ac);padding:1.5rem;"><h3 class="hl">Base estruturada para analytics</h3><p style="color:var(--mu);margin-top:0.5rem;">Dados limpos e consolidados abrem caminho para indicadores e inteligência preditiva.</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 14: Evolução
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:3rem;">Próximos <span class="hl">Passos</span></h1>'
    h += '<div class="an grid-2" style="align-items:stretch;">'
    h += '<div class="glass" style="border-left:4px solid var(--gn);"><h3 class="hl-g" style="margin-bottom:1rem;">Entregue</h3><ul style="list-style:none;line-height:2.4;font-size:1.1rem;"><li>✅ Governança operacional</li><li>✅ Roteirização</li><li>✅ GPS obrigatório</li><li>✅ PWA Offline</li><li>✅ Integração SAP</li></ul></div>'
    h += '<div class="glass" style="border-left:4px solid var(--yl);"><h3 class="hl-y" style="margin-bottom:1rem;">Próximas Evoluções</h3><ul style="list-style:none;line-height:2.4;font-size:1.1rem;color:var(--txt);"><li>🔄 Hospedagem corporativa</li><li>🔄 SSO / AD</li><li>🔄 APIs corporativas</li><li>🔄 Dashboards executivos</li><li>🔄 Inteligência preditiva</li><li>🔄 Recomendação automática de roteiros</li></ul></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 15: Encerramento
    h += '<div class="sd"><div class="si" style="text-align:center;">'
    h += '<h1 class="an" style="font-size:3.5rem;margin-bottom:1.5rem;">Mais do que um <span class="hl">aplicativo</span></h1>'
    h += '<p class="an" style="font-size:1.4rem;color:var(--mu);max-width:900px;margin:0 auto 3rem;">O SGO se torna uma camada digital entre planejamento e execução.</p>'
    h += '<div class="an flow" style="border-radius:16px;max-width:1000px;margin:0 auto;">'
    for i,(nm,cor) in enumerate([('Planejamento','var(--ac)'),('Malha','var(--yl)'),('Execução','var(--gn)'),('Governança','var(--vl)'),('SAP','var(--ac)')]):
        if i>0: h += '<div class="arrow"></div>'
        h += f'<div class="node"><div class="node-circle" style="border-color:{cor};box-shadow:0 0 20px {cor};font-size:1.2rem;">{"◆"}</div><h3 style="margin-top:0.5rem;font-size:1rem;color:{cor}">{nm}</h3></div>'
    h += '</div>'
    h += '<h3 class="an" style="color:var(--txt);font-weight:400;font-size:1.4rem;margin-top:3rem;">Transformando conhecimento operacional em <span class="hl">inteligência sistêmica</span>.</h3>'
    h += '<h3 class="an" style="color:var(--mu);font-weight:400;font-size:1.2rem;margin-top:1.5rem;border-top:1px solid rgba(255,255,255,0.1);padding-top:1.5rem;display:inline-block;">Muito Obrigado.</h3>'
    h += '</div></div>'
    #endregion

    #region Sessão Final — JS Logic
    h += '</div>'  # Fecha .sw
    h += '<script>'
    h += f'const TS={TS}; let cur=0; const sls=document.querySelectorAll(".sd"); const dts=document.querySelectorAll(".dot");'
    h += 'function show(x){ if(x<0||x>=TS)return; cur=x; sls.forEach((s,i)=>{s.classList.toggle("ac",i===x);}); dts.forEach((d,i)=>{d.classList.toggle("active",i===x);}); }'
    h += 'function nextSlide(){show(cur+1);} function prevSlide(){show(cur-1);}'
    h += 'function tFS(){ if(!document.fullscreenElement) document.documentElement.requestFullscreen().catch(()=>{}); else document.exitFullscreen(); }'
    h += 'document.addEventListener("keydown",e=>{ if(e.key==="ArrowRight"||e.key===" ")nextSlide(); if(e.key==="ArrowLeft")prevSlide(); if(e.key==="f"||e.key==="F")tFS(); });'
    h += 'dts.forEach((d,i)=>{ d.addEventListener("click",function(){ show(i); }); });'
    h += 'const cn=document.getElementById("cvN"), xn=cn.getContext("2d"); let w,h_c, nodes=[];'
    h += 'function rz(){ w=cn.width=innerWidth; h_c=cn.height=innerHeight; nodes=[]; for(let i=0;i<45;i++)nodes.push({x:Math.random()*w,y:Math.random()*h_c,vx:(Math.random()-0.5)*0.3,vy:(Math.random()-0.5)*0.3}); }'
    h += 'function dr(){ xn.clearRect(0,0,w,h_c); xn.strokeStyle="rgba(0, 242, 255, 0.2)"; xn.lineWidth=1.5; nodes.forEach((n,i)=>{ n.x+=n.vx; n.y+=n.vy; if(n.x<0||n.x>w)n.vx*=-1; if(n.y<0||n.y>h_c)n.vy*=-1; xn.beginPath(); xn.arc(n.x,n.y,2,0,Math.PI*2); xn.fillStyle="#00F2FF"; xn.fill(); for(let j=i+1;j<nodes.length;j++){ let d=Math.hypot(n.x-nodes[j].x, n.y-nodes[j].y); if(d<120){ xn.beginPath(); xn.moveTo(n.x,n.y); xn.lineTo(nodes[j].x,nodes[j].y); xn.stroke(); } } }); requestAnimationFrame(dr); }'
    h += 'window.addEventListener("resize",rz); rz(); dr(); show(0);'
    h += '</script></body></html>'
    #endregion

    #region Output File Generation
    fn = 'Pitch_Eletroeletronica_SGO_v4.html'
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(h)
    print('Pitch v2 Gerado:', os.path.abspath(fn))
    webbrowser.open('file://' + os.path.abspath(fn))
    #endregion

if __name__ == '__main__':
    main()
