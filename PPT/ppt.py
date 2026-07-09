# -*- coding: utf-8 -*-
import os
import webbrowser

def main():
    #region Sessão 0 — Configuração
    h = ''
    #endregion

    #region Sessão 1 — Head e CSS Base
    h += '<!DOCTYPE html><html lang=pt-BR><head><meta charset=UTF-8>'
    h += '<meta name=viewport content=\'width=device-width,initial-scale=1\'>'
    h += '<title>SGO Eletroeletrônica MRS | Premium Pitch</title>'
    h += '<link href=\'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600;700&family=Inter:wght@300;400;700;900&display=swap\' rel=stylesheet>'
    h += '<style>'
    
    h += ':root{--bg:#0B1120;--txt:#F8FAFC;--mu:#94A3B8;--ac:#00E5FF;--yl:#F59E0B;--gn:#10B981;--rd:#EF4444;--glass:rgba(15,23,42,0.65);--border:rgba(0,229,255,0.25);}'
    h += '*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden;background:var(--bg);color:var(--txt);font-family:\'Inter\',sans-serif;}'
    
    # Efeitos de Fundo
    h += '.bg-main{position:fixed;inset:0;z-index:0;background:linear-gradient(rgba(11, 17, 32, 0.85), rgba(11, 17, 32, 0.90)), url("fundo.png");background-size:cover;background-position:center;}'
    h += '.bg-glow{position:fixed;width:60vw;height:60vw;background:radial-gradient(circle,rgba(0,229,255,0.08),transparent 60%);top:-20%;left:-10%;z-index:1;border-radius:50%;filter:blur(80px);}'
    h += '.bg-glow2{position:fixed;width:50vw;height:50vw;background:radial-gradient(circle,rgba(245,158,11,0.05),transparent 60%);bottom:-20%;right:-10%;z-index:1;border-radius:50%;filter:blur(80px);}'
    h += '#cvN{position:fixed;inset:0;z-index:2;pointer-events:none;}'
    #endregion

    #region Sessão 2 — CSS: Componentes e Layouts
    h += 'h1,h2,h3{font-family:\'Space Grotesk\',sans-serif;font-weight:700;line-height:1.2;}'
    h += '.hl{color:var(--ac)}.hl-y{color:var(--yl)}.hl-g{color:var(--gn)}.hl-r{color:var(--rd)}'
    
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
    
    # Ticker Tape (Painel Rolando)
    h += '.tkb{position:fixed;top:0;left:0;right:0;height:35px;background:rgba(11,17,32,0.9);border-bottom:1px solid rgba(0,229,255,0.2);z-index:9999;display:flex;align-items:center;backdrop-filter:blur(10px);overflow:hidden;}'
    h += '.tkt{display:flex;width:max-content;animation:tks 40s linear infinite;}'
    h += '.tkc{display:flex;white-space:nowrap;}'
    h += '.tki{font-family:\'Space Grotesk\',sans-serif;font-size:11px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:var(--ac);padding:0 2em;}'
    h += '@keyframes tks{to{transform:translateX(-50%);}}'

    # Fluxograma e Animações
    h += '.flow{display:flex;align-items:center;justify-content:space-between;width:100%;background:rgba(0,0,0,0.4);padding:2rem;border-radius:100px;border:1px solid rgba(255,255,255,0.05);}'
    h += '.node{display:flex;flex-direction:column;align-items:center;text-align:center;gap:0.5rem;z-index:2;}'
    h += '.node-circle{width:80px;height:80px;border-radius:50%;background:var(--glass);border:2px solid var(--mu);display:flex;align-items:center;justify-content:center;font-size:2rem;box-shadow:0 0 20px rgba(0,0,0,0.5);transition:all 0.3s;}'
    h += '.node.active .node-circle{border-color:var(--ac);box-shadow:0 0 30px rgba(0,229,255,0.4);background:rgba(0,229,255,0.1);}'
    h += '.arrow{flex:1;height:2px;background:linear-gradient(90deg,transparent,var(--ac),transparent);margin:0 1rem;position:relative;opacity:0.5;}'
    h += '.arrow::after{content:"▶";position:absolute;right:10%;top:-10px;color:var(--ac);}'
    
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
    h += '</style></head>'
    #endregion

    #region Sessão 3 — HTML: Body e Layout
    h += '<body><div class="bg-main"></div><div class="bg-glow"></div><div class="bg-glow2"></div><canvas id="cvN"></canvas>'
    
    # Ticker / Painel Rolando
    h += '<div class="tkb"><div class="tkt">'
    h += '<div class="tkc"><span class="tki">⚡ SGO ELETROELETRÔNICA MRS ⚡ GESTÃO OPERACIONAL ⚡ ROTEIRIZAÇÃO INTELIGENTE ⚡ GEOFENCING ⚡ OPERAÇÃO OFFLINE ⚡ AUTOMAÇÃO DE DADOS ⚡ AUDITORIA TME</span></div>'
    h += '<div class="tkc"><span class="tki">⚡ SGO ELETROELETRÔNICA MRS ⚡ GESTÃO OPERACIONAL ⚡ ROTEIRIZAÇÃO INTELIGENTE ⚡ GEOFENCING ⚡ OPERAÇÃO OFFLINE ⚡ AUTOMAÇÃO DE DADOS ⚡ AUDITORIA TME</span></div>'
    h += '</div></div>'

    # Dica de Tela Cheia
    h += '<div style="position:fixed;top:45px;right:20px;color:rgba(255,255,255,0.3);font-size:0.8rem;z-index:9999;font-family:\'Space Grotesk\', sans-serif;">Pressione [F] para Tela Cheia</div>'

    h += '<div class="nav-prev nav-btn" onclick="prevSlide()">❮</div><div class="nav-next nav-btn" onclick="nextSlide()">❯</div>'
    h += '<div class="nav-dots" id="dots">'
    for i in range(11): h += f'<div class="dot {"active" if i==0 else ""}"></div>'
    h += '</div><div class="sw">'
    #endregion

    #region SLIDE 1: Capa (Impacto)
    h += '<div class="sd ac"><div class="si" style="text-align:center;">'
    h += '<h3 class="an" style="color:var(--mu);letter-spacing:0.3em;text-transform:uppercase;">Inteligência de Malha Integrada</h3>'
    h += '<h1 class="an" style="font-size:var(--f1);font-weight:900;margin:1rem 0;font-size:4.5rem;">SGO <span class="hl">Eletroeletrônica</span> MRS</h1>'
    h += '<p class="an" style="font-size:1.5rem;color:var(--mu);max-width:800px;margin:0 auto;">A tecnologia operacional aplicada à ponta da linha de ferro.</p>'
    h += '<div class="an" style="margin-top:3rem;display:flex;gap:2rem;justify-content:center;">'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl" style="font-size:1.5rem;font-weight:700;">Zero</span><br><span style="font-size:0.8rem">Papel</span></div>'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl-y" style="font-size:1.5rem;font-weight:700;">100%</span><br><span style="font-size:0.8rem">Rastreabilidade</span></div>'
    h += '<div class="glass" style="padding:1rem 2rem;"><span class="hl-g" style="font-size:1.5rem;font-weight:700;">Operação</span><br><span style="font-size:0.8rem">Offline</span></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 2: As Dores do Processo
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">A Desconexão <span class="hl-r">Operacional</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:3rem;font-size:1.2rem;">Onde a operação perde eficiência entre o escritório e os trilhos.</p>'
    h += '<div class="an grid-2" style="gap:2rem;">'
    
    h += '<div class="glass" style="border-left:4px solid var(--rd);padding:1.5rem;">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">🧠</div><h3 style="margin-bottom:0.5rem;color:var(--txt);">1. O Risco da Decisão Humana</h3>'
    h += '<p style="color:var(--mu);font-size:1rem;line-height:1.6;">O técnico analisa uma lista de dezenas de OSs e escolhe a atividade pelo "feeling". Sem visão sistêmica ou geográfica, geramos viagens perdidas e baixa produtividade.</p></div>'
    
    h += '<div class="glass" style="border-left:4px solid var(--yl);padding:1.5rem;">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">📉</div><h3 style="margin-bottom:0.5rem;color:var(--txt);">2. Desvio da Programação</h3>'
    h += '<p style="color:var(--mu);font-size:1rem;line-height:1.6;">A ausência de travas sistêmicas em campo permite que a execução real se distancie do que foi planejado, comprometendo os indicadores da manutenção.</p></div>'
    
    h += '<div class="glass" style="border-left:4px solid var(--rd);padding:1.5rem;">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">🚨</div><h3 style="margin-bottom:0.5rem;color:var(--txt);">3. Falta de Priorização</h3>'
    h += '<p style="color:var(--mu);font-size:1rem;line-height:1.6;">Para o papel, todas as OSs têm o mesmo peso. Frequentemente, uma preventiva de baixo impacto concorre por atenção com uma falha de confiabilidade crítica.</p></div>'
    
    h += '<div class="glass" style="border-left:4px solid var(--yl);padding:1.5rem;">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">🌫️</div><h3 style="margin-bottom:0.5rem;color:var(--txt);">4. Visão Cega Pós-Emergência</h3>'
    h += '<p style="color:var(--mu);font-size:1rem;line-height:1.6;">O técnico é acionado para um chamado urgente. Após resolver, o que fazer? Sem visão espacial do trecho, a equipe retorna à base deixando manutenções vizinhas para trás.</p></div>'
    
    h += '</div></div></div>'
    #endregion

    #region SLIDE 3: O Fluxo de Dados (Linguagem Executiva + Logos)
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">O <span class="hl">Fluxo de Dados</span> Operacional</h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:4rem;font-size:1.2rem;">Como transformamos informações brutas em inteligência para tomada de decisão.</p>'
    h += '<div class="an flow">'
    
    h += '<div class="node"><div class="node-circle" style="background:#fff;"><img src="https://upload.wikimedia.org/wikipedia/commons/5/59/SAP_2011_logo.svg" style="width:40px;"></div><h3 style="margin-top:0.5rem">SAP ERP</h3><p style="font-size:0.8rem;color:var(--mu)">Exportação do SAP<br>Dados Brutos Operacionais</p></div>'
    h += '<div class="arrow"></div>'
    
    h += '<div class="node active"><div class="node-circle" style="background:var(--glass);border-color:var(--yl);box-shadow:0 0 20px var(--yl);"><img src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg" style="width:40px;"></div><h3 class="hl-y" style="margin-top:0.5rem">Motor Python</h3><p style="font-size:0.8rem;color:var(--mu)">Limpeza Automática<br>Cruzamento de Informações<br>Tradução para Inteligência</p></div>'
    h += '<div class="arrow"></div>'
    
    h += '<div class="node active"><div class="node-circle" style="background:var(--glass)">⚙️</div><h3 class="hl" style="margin-top:0.5rem">Core SGO</h3><p style="font-size:0.8rem;color:var(--mu)">Geolocalização Topológica<br>Regras de Negócio e Travas</p></div>'
    h += '<div class="arrow"></div>'
    
    h += '<div class="node"><div class="node-circle">☁️</div><h3 style="margin-top:0.5rem">Nuvem SGO</h3><p style="font-size:0.8rem;color:var(--mu)">Banco de Dados Seguro<br>Informação Pronta para Uso</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 4: Roteirização Topológica
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="margin-bottom:3rem;">Roteirização <span class="hl">Geográfica</span></h1>'
    h += '<div class="an grid-2">'
    h += '<div>'
    h += '<p style="font-size:1.2rem;margin-bottom:2rem;">O aplicativo abandona o conceito de lista e adota a <strong>geolocalização inteligente</strong>.</p>'
    h += '<div class="glass" style="border-left:4px solid var(--ac);padding:1.5rem;"><h3 class="hl">Inteligência Geográfica (Cálculo de Distância Real)</h3><p style="margin-top:0.5rem;color:var(--txt);">O motor cruza as coordenadas de GPS em tempo real do técnico com o nosso dicionário espacial da ferrovia. Ele entrega visualmente apenas as OSs que estão no raio de atuação escolhido pela equipe (ex: 5km, 10km).</p></div>'
    h += '</div>'
    h += '<div class="glass" style="padding:1rem;"><img src="roteirizaçao_OS.png" alt="Roteirização SGO" class="img-glow" onerror="this.src=\'https://images.unsplash.com/photo-1524661135-423995f22d0b?q=80&w=800&auto=format&fit=crop\'; this.style.filter=\'hue-rotate(180deg) brightness(0.8)\';"></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 5: A Trava Lógica de Priorização
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="margin-bottom:3rem;text-align:center;">Decisão Sistêmica, <span class="hl-r">Não Humana</span></h1>'
    h += '<div class="an grid-2">'
    h += '<div class="glass" style="display:flex;flex-direction:column;align-items:center;border-color:var(--rd);">'
    h += '<div class="radar"><div class="radar-dot"></div><div class="target-dot"></div><div style="position:absolute;bottom:20%;left:20%;width:8px;height:8px;background:var(--mu);border-radius:50%;"></div></div>'
    h += '<div style="margin-top:2rem;width:100%;"><div style="display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:10px;"><span style="color:var(--rd);font-weight:700">OS 23089846 (MUITO ALTA)</span><span>0.8 km</span></div><div style="display:flex;justify-content:space-between;padding-top:10px;color:var(--mu);"><span>OS 23460803 (Confiabilidade Normal)</span><span>Bloqueada Sistemicamente</span></div></div>'
    h += '</div>'
    h += '<div>'
    h += '<h2 style="margin-bottom:1rem;">A Trava de Prioridade</h2>'
    h += '<p style="font-size:1.1rem;color:var(--mu);">Tiramos o peso da decisão das costas do técnico. O sistema dita a regra operacional.</p><br>'
    h += '<ul style="margin-left:1.5rem;color:var(--txt);line-height:2;font-size:1.1rem;">'
    h += '<li>Identifica OS de Segurança ou Confiabilidade Crítica.</li>'
    h += '<li><strong>Bloqueia a interface</strong> (acinzenta) as OSs de menor prioridade no mesmo raio.</li>'
    h += '<li>Força a equipe a atacar e resolver a emergência antes de prosseguir com manutenções preventivas normais.</li></ul>'
    h += '</div></div></div></div>'
    #endregion

    #region SLIDE 6: Resiliência Extrema: Operação Offline
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:1rem;">Resiliência Extrema: <span class="hl-y">Operação Offline</span></h1>'
    h += '<p class="an" style="text-align:center;color:var(--mu);margin-bottom:3rem;font-size:1.2rem;">A operação continua fluída mesmo sem sinal de rádio ou 4G no trecho.</p>'
    h += '<div class="an grid-3">'
    h += '<div class="glass" style="text-align:center;"><div style="font-size:3rem;margin-bottom:1rem;">📡</div><h3>1. Carga Pré-Viagem</h3><p style="margin-top:1rem;color:var(--mu);">Ainda na base, com internet, o técnico carrega no celular todas as rotas, mapas e dados da sua jornada do dia.</p></div>'
    h += '<div class="glass" style="text-align:center;border-color:var(--yl);box-shadow:0 0 30px rgba(245,158,11,0.2);"><div style="font-size:3rem;margin-bottom:1rem;">📴</div><h3 class="hl-y">2. Modo Local</h3><p style="margin-top:1rem;color:var(--mu);">No trecho sem sinal, o aplicativo roda em modo local offline diretamente do navegador. Captura horas e armazena fotos no próprio aparelho.</p></div>'
    h += '<div class="glass" style="text-align:center;"><div style="font-size:3rem;margin-bottom:1rem;">🔄</div><h3>3. Sincronização</h3><p style="margin-top:1rem;color:var(--mu);">Ao reconectar na rede, o aplicativo envia todos os apontamentos e fotos para o servidor de uma só vez, garantindo zero perda de dados.</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 7: Governança e Antifraude
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="margin-bottom:3rem;text-align:center;">Governança e <span class="hl-g">Auditoria</span></h1>'
    h += '<div class="an grid-2">'
    h += '<div>'
    h += '<p style="font-size:1.2rem;margin-bottom:2rem;">A confiança é boa, mas o <strong>controle sistêmico</strong> é à prova de falhas.</p>'
    h += '<div style="margin-bottom:2rem;display:flex;gap:1.5rem;align-items:flex-start;"><div style="font-size:2.5rem;">📍</div><div><h3 class="hl-g">Geofencing Estrito</h3><p style="color:var(--mu);margin-top:0.5rem;">O botão de Baixa Eletrônica só é ativado se o GPS atestar que o tablet está num raio máximo de <strong>2.0 km</strong> da coordenada oficial do ativo na linha.</p></div></div>'
    h += '<div style="display:flex;gap:1.5rem;align-items:flex-start;"><div style="font-size:2.5rem;">📸</div><div><h3 class="hl">Rastreabilidade de Evidências</h3><p style="color:var(--mu);margin-top:0.5rem;">O técnico tentou falsificar o GPS por outro aplicativo? O sistema extrai os dados de localização gravados "dentro" do arquivo da foto (metadados), impedindo falsificações de local e garantindo a auditoria.</p></div></div>'
    h += '</div>'
    h += '<div class="glass" style="padding:1rem;border-color:var(--gn);">'
    h += '<img src="map.png" alt="Técnico com Tablet" class="img-glow" style="filter: brightness(0.7) contrast(1.2);" onerror="this.src=\'https://images.unsplash.com/photo-1581092162384-8987c1d64718?q=80&w=800&auto=format&fit=crop\';">'
    h += '</div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 8: Auditoria de Mobilização (TME)
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="text-align:center;margin-bottom:3rem;">Gestão de <span class="hl-y">Tempos e Movimentos</span></h1>'
    h += '<div class="an glass" style="padding:3rem; border-top: 4px solid var(--yl)">'
    h += '<div class="grid-2" style="margin-top:0; gap:2rem;">'
    h += '<div><h3 style="font-size:1.5rem;margin-bottom:1rem;">Tempo Médio de Execução Real</h3><p style="color:var(--txt);font-size:1.1rem;line-height:1.6;">Acabou a dependência da memória do técnico para registrar horários.<br><br>O painel captura exatamente a hora de acesso ao sistema e subtrai da hora de conclusão da 1ª atividade, revelando o nosso verdadeiro <strong>Tempo de Mobilização</strong> da equipe.</p></div>'
    h += '<div><h3 style="font-size:1.5rem;margin-bottom:1rem;color:var(--rd);">Controle Inteligente de Jornada</h3><p style="color:var(--mu);font-size:1.1rem;line-height:1.6;">Se um turno noturno inicia às 22h e a OS é encerrada à 01h da manhã, o sistema compreende a travessia de dias. Ele calcula a data correta automaticamente e alerta os gestores para inconsistências de jornada, protegendo a empresa.</p></div>'
    h += '</div></div></div></div>'
    #endregion

    #region SLIDE 9: Arquitetura e Nuvem
    h += '<div class="sd"><div class="si">'
    h += '<h1 class="an" style="margin-bottom:3rem;text-align:center;">A Máquina <span class="hl">Tecnológica</span></h1>'
    h += '<div class="an grid-4">'
    h += '<div class="glass" style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;margin-bottom:1rem;">🖥️</div><h3 class="hl">Portal Web</h3><p style="font-size:0.85rem;color:var(--mu);margin-top:1rem;">Telas interativas, mapas instantâneos e gráficos gerenciais focados na facilidade de uso do técnico e do gestor.</p></div>'
    h += '<div class="glass" style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;margin-bottom:1rem;">⚡</div><h3 class="hl-y">Processador Central</h3><p style="font-size:0.85rem;color:var(--mu);margin-top:1rem;">Recebe as fotos de campo, comprime o tamanho dos arquivos e cruza as informações de forma 100% automática e segura.</p></div>'
    h += '<div class="glass" style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;margin-bottom:1rem;">🐘</div><h3 class="hl-g">Banco de Dados</h3><p style="font-size:0.85rem;color:var(--mu);margin-top:1rem;">Armazenamento de alta segurança na nuvem. Separação rigorosa: senhas e acessos totalmente isolados dos dados operacionais da ferrovia.</p></div>'
    h += '<div class="glass" style="text-align:center;padding:1.5rem;"><div style="font-size:2.5rem;margin-bottom:1rem;">☁️</div><h3 style="color:#A78BFA">Nuvem de Arquivos</h3><p style="font-size:0.85rem;color:var(--mu);margin-top:1rem;">Repositório infinito e seguro para guardar todas as fotos e evidências da operação, garantindo o histórico fotográfico da malha.</p></div>'
    h += '</div></div></div>'
    #endregion

    #region SLIDE 10: Impacto (Big Numbers)
    h += '<div class="sd"><div class="si" style="text-align:center;">'
    h += '<h1 class="an" style="font-size:3.5rem;margin-bottom:1rem;">O Novo Padrão da <span class="hl">Eletroeletrônica de SP</span></h1>'
    h += '<p class="an" style="font-size:1.5rem;color:var(--mu);margin-bottom:4rem;">A transformação digital real, gerando eficiência e governança na ponta da linha.</p>'
    h += '<div class="an grid-3" style="margin-bottom:2rem;">'
    h += '<div class="glass"><h2 class="big-num ac">100%</h2><h3 style="margin-top:1rem;">Auditoria Integrada</h3><p style="font-size:0.9rem;color:var(--mu);">Governança garantida pelo sistema via GPS e validação fotográfica.</p></div>'
    h += '<div class="glass"><h2 class="big-num yl">Zero</h2><h3 style="margin-top:1rem;">Decisão às Cegas</h3><p style="font-size:0.9rem;color:var(--mu);">Fim das viagens perdidas com a roteirização automática de tarefas.</p></div>'
    h += '<div class="glass"><h2 class="big-num" style="background:linear-gradient(135deg,#10B981,#047857);-webkit-background-clip:text;">Real</h2><h3 style="margin-top:1rem;">Automação no SAP</h3><p style="font-size:0.9rem;color:var(--mu);">Integração que erradica o retrabalho de digitação manual de relatórios no escritório.</p></div>'
    h += '</div>'
    h += '</div></div>'
    #endregion

    #region SLIDE 11: A Síntese (O Que, Como, Por Que)
    h += '<div class="sd"><div class="si" style="text-align:center;">'
    h += '<h1 class="an" style="font-size:3.5rem;margin-bottom:1rem;">A Síntese da <span class="hl">Transformação</span></h1>'
    h += '<p class="an" style="font-size:1.5rem;color:var(--mu);margin-bottom:3rem;">O que entregamos hoje para a MRS.</p>'
    
    h += '<div class="an grid-3" style="margin-bottom:4rem; text-align: left;">'
    h += '<div class="glass" style="border-top: 4px solid var(--rd);">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">🎯</div>'
    h += '<h3 class="hl-r" style="margin-bottom:1rem;">O que Resolvemos</h3>'
    h += '<p style="color:var(--txt);line-height:1.6;font-size:1rem;">Acabamos com o <strong>"voo às cegas"</strong> operacional. Eliminamos o uso de papel, as viagens perdidas, a falta de priorização de emergências e o enorme retrabalho de digitação no escritório.</p>'
    h += '</div>'
    
    h += '<div class="glass" style="border-top: 4px solid var(--ac);">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">⚙️</div>'
    h += '<h3 class="hl" style="margin-bottom:1rem;">Como Resolvemos</h3>'
    h += '<p style="color:var(--txt);line-height:1.6;font-size:1rem;">Levando tecnologia ao campo com: <strong>Roteirização por GPS</strong>, travas sistêmicas contra decisões erradas e modo de <strong>Operação Offline</strong> para garantir fluidez no trecho.</p>'
    h += '</div>'
    
    h += '<div class="glass" style="border-top: 4px solid var(--yl);">'
    h += '<div style="font-size:2.5rem;margin-bottom:1rem;">💎</div>'
    h += '<h3 class="hl-y" style="margin-bottom:1rem;">Padrão Ouro</h3>'
    h += '<p style="color:var(--txt);line-height:1.6;font-size:1rem;">Entregamos uma <strong>Governança Intocável</strong>.A possibilidade de integração limpa com o SAP, auditoria fotográfica antifraude (EXIF) e medição gerencial do real Tempo de Execução (TME).</p>'
    h += '</div>'
    h += '</div>'

    h += '<h3 class="an" style="color:var(--txt);font-weight:400;font-size:1.5rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 2rem;">Muito Obrigado.</h3>'
    h += '</div></div>'
    #endregion

    #region Sessão Final — JS Logic
    h += '</div>' # Fecha .sw
    h += '<script>'
    h += 'const TS=11; let cur=0; const sls=document.querySelectorAll(".sd"); const dts=document.querySelectorAll(".dot");'
    h += 'function show(x){ if(x<0||x>=TS)return; cur=x; sls.forEach((s,i)=>{s.classList.toggle("ac",i===x);}); dts.forEach((d,i)=>{d.classList.toggle("active",i===x);}); }'
    h += 'function nextSlide(){show(cur+1);} function prevSlide(){show(cur-1);}'
    h += 'function tFS(){ if(!document.fullscreenElement) document.documentElement.requestFullscreen().catch(()=>{}); else document.exitFullscreen(); }'
    h += 'document.addEventListener("keydown",e=>{ if(e.key==="ArrowRight"||e.key===" ")nextSlide(); if(e.key==="ArrowLeft")prevSlide(); if(e.key==="f"||e.key==="F")tFS(); });'
    h += 'dts.forEach((d,i)=>{ d.addEventListener("click",function(){ show(i); }); });'
    h += 'const cn=document.getElementById("cvN"), xn=cn.getContext("2d"); let w,h_c, nodes=[], edges=[];'
    h += 'function rz(){ w=cn.width=innerWidth; h_c=cn.height=innerHeight; nodes=[]; edges=[]; for(let i=0;i<45;i++)nodes.push({x:Math.random()*w,y:Math.random()*h_c,vx:(Math.random()-0.5)*0.3,vy:(Math.random()-0.5)*0.3}); }'
    h += 'function dr(){ xn.clearRect(0,0,w,h_c); xn.strokeStyle="rgba(0, 242, 255, 0.2)"; xn.lineWidth=1.5; nodes.forEach((n,i)=>{ n.x+=n.vx; n.y+=n.vy; if(n.x<0||n.x>w)n.vx*=-1; if(n.y<0||n.y>h_c)n.vy*=-1; xn.beginPath(); xn.arc(n.x,n.y,2,0,Math.PI*2); xn.fillStyle="#00F2FF"; xn.fill(); for(let j=i+1;j<nodes.length;j++){ let d=Math.hypot(n.x-nodes[j].x, n.y-nodes[j].y); if(d<120){ xn.beginPath(); xn.moveTo(n.x,n.y); xn.lineTo(nodes[j].x,nodes[j].y); xn.stroke(); } } }); requestAnimationFrame(dr); }'
    h += 'window.addEventListener("resize",rz); rz(); dr(); show(0);'
    h += '</script></body></html>'
    #endregion

    #region Output File Generation
    fn = 'Pitch_Eletroeletronica_SGO.html'
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(h)
    print('Premium Pitch Gerado:', os.path.abspath(fn))
    webbrowser.open('file://' + os.path.abspath(fn))
    #endregion

if __name__ == '__main__':
    main()