# -*- coding: utf-8 -*-
# Pitch_SGO_TI_Malha.py
# Gera apresentação HTML executiva do SGO, alinhada ao código real: Streamlit, FastAPI, PWA offline, GPS, SAP, banco e governança.

import os
import html
import webbrowser
from datetime import datetime

OUTPUT_FILE = 'Pitch_SGO_TI_Malha.html'

SLIDES = [
    {
        'kicker': 'Inteligência de Malha Integrada',
        'title': 'SGO Eletroeletrônica MRS',
        'lead': 'Uma plataforma de inteligência operacional que conecta SAP, ativos ferroviários, geolocalização, evidências e execução em campo.',
        'kind': 'metrics',
        'items': [('Zero', 'Papel', 'operação digital'), ('100%', 'Rastreável', 'GPS + foto + usuário'), ('PWA', 'Offline', 'campo sem sinal'), ('SAP', 'Ciclo Completo', 'entrada e retorno')]
    },
    {
        'kicker': 'O desafio',
        'title': 'A manutenção em malha não falha por falta de esforço. Falha por desconexão.',
        'lead': 'A decisão de campo exige combinar planejamento, criticidade, localização, intervalo, disponibilidade e conhecimento dos ativos — muitas vezes em ambiente sem sinal.',
        'kind': 'cards',
        'items': [('🧠', 'Conhecimento tácito', 'A experiência do técnico é valiosa, mas fica concentrada em pessoas e turnos.'), ('🗺️', 'Geografia operacional', 'A lista de OS não mostra proximidade real entre equipe, pátio e ativo.'), ('🚨', 'Priorização crítica', 'OS de segurança e confiabilidade competem com atividades normais sem regra sistêmica.'), ('🌫️', 'Pós-emergência cego', 'Após atender uma falha, a equipe pode retornar deixando OS vizinhas pendentes.')]
    },
    {
        'kicker': 'Reposicionamento',
        'title': 'O SGO não é um apontador de OS.',
        'lead': 'Ele é uma camada digital entre o planejamento e a malha, transformando conhecimento operacional em regra, execução e governança.',
        'kind': 'pills',
        'items': ['Motor de regras', 'Roteirização', 'GPS obrigatório', 'PWA offline', 'Evidência fotográfica', 'Integração SAP', 'Auditoria', 'Gestão de usuários', 'Dashboards']
    },
    {
        'kicker': 'Fluxo digital completo',
        'title': 'SAP → SGO → Campo → Governança → SAP',
        'lead': 'O sistema fecha o ciclo operacional: recebe planejamento, aplica inteligência de malha, orienta execução, captura evidência e prepara retorno estruturado.',
        'kind': 'flow',
        'items': [('SAP', 'OS programadas, criticidade, datas e informações operacionais'), ('ETL Python', 'Normalização, classificação e enriquecimento dos dados'), ('Core SGO', 'Regras, priorização, pátios, distância e governança'), ('Campo', 'GPS, PWA offline, foto, baixa e sincronização'), ('Retorno SAP', 'Arquivo SAP, IW47 e consolidação de execução')]
    },
    {
        'kicker': 'Inteligência ferroviária',
        'title': 'O sistema passa a conhecer a malha.',
        'lead': 'A camada geográfica do SGO carrega coordenadas de pátios, bases e ativos, permitindo que a execução deixe de ser apenas uma lista e passe a ser uma visão de território.',
        'kind': 'cards',
        'items': [('📍', 'Pátios e bases', 'Banco fixo de coordenadas com pátios e sedes operacionais.'), ('🚆', 'Ativos da malha', 'Mapeamento de ativo para pátio e resolução por prefixo ou planilha.'), ('📐', 'Distância real', 'Cálculo Haversine entre equipe, pátio e ativo para recomendação de rota.')]
    },
    {
        'kicker': 'Para Matheus Gravel e Eduardo Kamel',
        'title': 'O valor está na solução para a malha, não só na tecnologia.',
        'lead': 'A solução transforma experiência de campo em padrão operacional auditável e reproduzível.',
        'kind': 'compare',
        'items': [('Antes', ['Equipe enxerga lista de OS.', 'Priorização depende de interpretação individual.', 'Conhecimento de ativo e proximidade fica no técnico experiente.', 'Emergência interrompe a programação e dificulta retomada eficiente.']), ('Depois', ['Equipe enxerga OS por território, raio e pátio.', 'Criticidade e segurança viram regra sistêmica.', 'Conhecimento operacional fica padronizado no sistema.', 'Após emergência, o SGO mostra o que está próximo e pendente.'])]
    },
    {
        'kicker': 'Motor de priorização',
        'title': 'Decisão sistêmica, não decisão no improviso.',
        'lead': 'O SGO combina classificação, criticidade, prazo, tipo de intervalo e distância. OS Muito Alta bloqueia atividades inferiores do mesmo grupo operacional, mantendo-as visíveis e explicáveis.',
        'kind': 'timeline',
        'items': [('01', 'Classificação', 'Segurança, Confiabilidade ou ambas.'), ('02', 'Criticidade', 'Muito Alta, Alta, Média ou Baixa.'), ('03', 'Prazo', 'Atrasada, do dia ou futura.'), ('04', 'Intervalo', 'Com Intervalo e Sem Intervalo tratados como filas independentes.'), ('05', 'Distância', 'Ordenação por proximidade operacional.')]
    },
    {
        'kicker': 'Roteirização',
        'title': 'Da lista de tarefas para a navegação operacional.',
        'lead': 'O técnico seleciona base ou GPS, define raio, filtra e recebe OS próximas, ordenadas por prioridade e prontas para cronograma de campo.',
        'kind': 'code',
        'items': ['Origem GPS/Base', 'Cálculo Haversine', 'Filtro por raio', 'Backlog + Criticidade', 'Cronograma de Campo']
    },
    {
        'kicker': 'Offline real',
        'title': 'Operar sem sinal deixa de ser exceção técnica.',
        'lead': 'A rota é publicada como PWA em HTTPS. O técnico abre uma vez online, usa em campo sem sinal, registra GPS, horários, equipe e foto, e sincroniza ao reconectar.',
        'kind': 'cards',
        'items': [('🌐', 'Publicar Rota PWA', 'Gera pacote HTML seguro para abrir uma vez no celular.'), ('📴', 'Fila Local', 'OS, horários, foto e GPS ficam guardados no aparelho.'), ('🔄', 'Sync Idempotente', 'Envio posterior sem duplicidade e com preservação da evidência.')]
    },
    {
        'kicker': 'Governança operacional',
        'title': 'A baixa passa a ser uma evidência auditável.',
        'lead': 'Login, perfil, GPS, foto, horário, equipe e trilha de execução ficam amarrados à OS.',
        'kind': 'cards',
        'items': [('🔐', 'Acesso por perfil', 'Técnico, Assistente, Coordenador e Gerência com permissões distintas.'), ('📍', 'GPS obrigatório', 'Técnico acessa e baixa com geolocalização do navegador.'), ('📸', 'Foto obrigatória', 'Evidência comprimida, orientada e armazenada na nuvem.'), ('🛡️', 'Trava de preservação', 'Importações IW47 não sobrescrevem evidência operacional validada.')]
    },
    {
        'kicker': 'Integração SAP',
        'title': 'Não é apenas exportar planilha. É fechar o ciclo.',
        'lead': 'O SGO recebe OS programadas, processa execução e retorna dados estruturados para SAP/IW47, reduzindo retrabalho e protegendo evidência de campo.',
        'kind': 'cards',
        'items': [('📥', 'Entrada', 'Upload de OS programadas com normalização de colunas e escopo.'), ('⚙️', 'Processamento', 'Status, datas, equipes, turnos, criticidade e prazos consolidados.'), ('📤', 'Saída', 'Arquivo de baixa em massa SAP + importação IW47 com validações.')]
    },
    {
        'kicker': 'Arquitetura corporativa',
        'title': 'A solução já nasce com separação de camadas.',
        'lead': 'Streamlit no portal, Python no motor de negócio, FastAPI para sincronização offline, PostgreSQL/Neon como persistência e Supabase Storage para evidências.',
        'kind': 'architecture',
        'items': [('Portal Web', 'Streamlit, dashboards, mapa e administração'), ('Campo PWA', 'HTML/JS offline, GPS, fila local e sincronização'), ('Core SGO', 'Python, ETL, regras, Haversine e governança'), ('API', 'FastAPI, API Key, healthcheck e endpoints offline'), ('Banco', 'PostgreSQL/Neon com pool e upserts'), ('Storage', 'Supabase Storage para evidências fotográficas')]
    },
    {
        'kicker': 'Segurança e sustentação',
        'title': 'O que a TI costuma perguntar — e o SGO já responde.',
        'lead': 'A aplicação já contempla autenticação, escopo, trilha de auditoria, conexão controlada, API key, evidência fotográfica e preservação de dados operacionais.',
        'kind': 'cards',
        'items': [('🔑', 'Autenticação', 'Senha com hash, reset obrigatório e token HMAC de sessão.'), ('🧭', 'Escopo', 'Restrição por coordenação, governança e perfil de uso.'), ('🧾', 'Auditoria', 'Logs de acesso, geolocalização de login e execução.'), ('🧱', 'Persistência', 'Tabelas normalizadas, upsert e pool de conexões.'), ('🚦', 'API controlada', 'API Key no header e endpoints dedicados ao offline.'), ('📦', 'Evidências', 'Fotos compactadas, armazenadas e vinculadas à OS/ativo.')]
    },
    {
        'kicker': 'Gestão e indicadores',
        'title': 'A operação vira dado gerencial.',
        'lead': 'O SGO entrega planejado x realizado, backlog, execução por turno, matriz de criticidade, calendário de demanda, mapa operacional e lista auditável de OS.',
        'kind': 'metrics',
        'items': [('KPI', 'Planejado x Realizado', 'visão acumulada'), ('Turno', 'Execução real', 'dia / administrativo / noite'), ('Mapa', 'Demanda por pátio', 'raio e prioridade'), ('PDF', 'Fim de turno', 'cronograma e concluídas')]
    },
    {
        'kicker': 'Conhecimento operacional',
        'title': 'O principal ganho: experiência transformada em sistema.',
        'lead': 'O conhecimento da malha deixa de depender apenas de quem está no turno e passa a ser padronizado, rastreável e reproduzível.',
        'kind': 'pills',
        'items': ['Ativo → Pátio', 'Prioridade → Bloqueio', 'GPS → Evidência', 'SAP → Campo', 'Turno → Produtividade', 'Backlog → Ação']
    },
    {
        'kicker': 'Benefícios para a malha',
        'title': 'Impacto esperado na operação.',
        'lead': 'Menos deslocamento improdutivo, maior foco nas críticas, maior aderência ao planejamento e base estruturada para analytics e IA.',
        'kind': 'cards',
        'items': [('🚗', 'Menos deslocamento improdutivo', 'Equipe atua por proximidade e prioridade.'), ('🎯', 'Mais foco nas críticas', 'Muito Alta passa na frente por regra sistêmica.'), ('🧑‍🔧', 'Menor dependência individual', 'Boas práticas viram padrão operacional.'), ('📅', 'Mais aderência ao planejamento', 'Calendário, status e backlog claros.'), ('📚', 'Histórico da malha', 'Foto, GPS, usuário, horário e OS em base única.'), ('🤖', 'Base para analytics/IA', 'Dados estruturados para predição e recomendação futura.')]
    },
    {
        'kicker': 'Roadmap',
        'title': 'Da solução local à plataforma corporativa.',
        'lead': 'A solução já entrega rota, offline, SAP, evidência e governança. Como evolução, recomenda-se institucionalizar hospedagem, SSO/AD, APIs e observabilidade.',
        'kind': 'compare',
        'items': [('Já implementado', ['Roteirização por GPS e pátios.', 'PWA offline HTTPS.', 'GPS obrigatório e evidência fotográfica.', 'Importação/exportação SAP e IW47.', 'Gestão de usuários e permissões.', 'Dashboards, mapas e relatórios PDF.']), ('Próximas evoluções', ['Hospedagem corporativa MRS.', 'SSO/AD e política oficial de acesso.', 'API corporativa e observabilidade.', 'Dashboards executivos por gerência.', 'Motor preditivo de demanda e falha.', 'Recomendação automática de roteiro.'])]
    },
    {
        'kicker': 'Síntese executiva',
        'title': 'O SGO cria uma nova camada digital para a manutenção.',
        'lead': 'Mais do que digitalizar baixa: o SGO transforma planejamento, malha, execução, governança e SAP em inteligência sistêmica.',
        'kind': 'flow',
        'items': [('Planejamento', 'SAP e programação'), ('Malha', 'Ativos, pátios, distância'), ('Execução', 'Campo, offline, evidência'), ('Governança', 'GPS, logs, auditoria'), ('SAP', 'Retorno estruturado')]
    },
]


def e(value):
    return html.escape(str(value), quote=True)


def render_metrics(items):
    return '<div class="metric-row">' + ''.join(f'<div class="metric"><div class="metric-value">{e(v)}</div><div class="metric-label">{e(l)}</div><div class="metric-detail">{e(d)}</div></div>' for v, l, d in items) + '</div>'


def render_cards(items):
    n = len(items)
    cls = 'grid-4' if n == 4 else 'grid-3'
    return f'<div class="grid {cls}">' + ''.join(f'<div class="card"><div class="card-icon">{icon}</div><h4>{e(t)}</h4><p>{e(txt)}</p></div>' for icon, t, txt in items) + '</div>'


def render_pills(items):
    return '<div class="pills">' + ''.join(f'<span class="pill">{e(x)}</span>' for x in items) + '</div>'


def render_flow(items):
    return '<div class="flow">' + ''.join(f'<div class="flow-box"><div class="flow-title">{e(t)}</div><div class="flow-sub">{e(s)}</div></div>' for t, s in items) + '</div>'


def render_compare(items):
    left_title, left_list = items[0]
    right_title, right_list = items[1]
    def lis(values): return ''.join(f'<li>{e(x)}</li>' for x in values)
    return f'<div class="compare"><div class="before"><h3>{e(left_title)}</h3><ul class="clean">{lis(left_list)}</ul></div><div class="after"><h3>{e(right_title)}</h3><ul class="clean">{lis(right_list)}</ul></div></div>'


def render_timeline(items):
    return '<div class="timeline">' + ''.join(f'<div class="step"><div class="step-num">{e(n)}</div><h4>{e(t)}</h4><p>{e(txt)}</p></div>' for n, t, txt in items) + '</div>'


def render_code(items):
    chain = chr(10).join([e(items[0])] + ['  ↓' + chr(10) + e(x) for x in items[1:]])
    return f'<div class="grid grid-2"><div><h3>Como funciona</h3><ul class="clean"><li>Seleciona Minha Base ou Minha Localização.</li><li>Define raio de atuação visual.</li><li>Clica em Filtrar.</li><li>Recebe OS próximas, ordenadas e priorizadas.</li></ul></div><div class="codebox">{chain}</div></div>'


def render_architecture(items):
    left = items[:2]
    core = items[2]
    right = items[3:]
    def stack(values):
        return '<div class="stack-col">' + ''.join(f'<div class="stack-item"><strong>{e(t)}</strong><span>{e(s)}</span></div>' for t, s in values) + '</div>'
    return f'<div class="arch">{stack(left)}<div class="core"><div class="core-title">{e(core[0])}</div><div class="core-sub">{e(core[1])}</div></div>{stack(right)}</div>'


def render_body(slide):
    kind = slide['kind']
    items = slide['items']
    if kind == 'metrics': return render_metrics(items)
    if kind == 'cards': return render_cards(items)
    if kind == 'pills': return render_pills(items)
    if kind == 'flow': return render_flow(items)
    if kind == 'compare': return render_compare(items)
    if kind == 'timeline': return render_timeline(items)
    if kind == 'code': return render_code(items)
    if kind == 'architecture': return render_architecture(items)
    return ''


def build_html():
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M')
    css = r'''
:root{--bg:#050B18;--panel:#0B1224;--panel2:#111A30;--blue:#3B82F6;--cyan:#22D3EE;--green:#10B981;--amber:#F59E0B;--red:#EF4444;--text:#F8FAFC;--muted:#94A3B8;--line:rgba(148,163,184,.25);--white:#FFFFFF}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 10%,rgba(59,130,246,.25),transparent 35%),radial-gradient(circle at 80% 70%,rgba(34,211,238,.14),transparent 38%),linear-gradient(135deg,#030712 0%,#07111F 45%,#071827 100%);color:var(--text);font-family:'Segoe UI',Arial,sans-serif;overflow:hidden}.ticker{position:fixed;top:0;left:0;right:0;height:34px;background:rgba(5,11,24,.88);border-bottom:1px solid var(--line);overflow:hidden;z-index:50;backdrop-filter:blur(12px)}.ticker-content{white-space:nowrap;display:inline-block;padding-left:100%;animation:ticker 34s linear infinite;color:#BAE6FD;font-weight:700;letter-spacing:.08em;line-height:34px;font-size:13px}@keyframes ticker{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}.deck{height:100vh;width:100vw;position:relative;padding-top:34px}.slide{position:absolute;inset:34px 0 0 0;padding:54px 72px 56px;display:none;opacity:0;transform:translateX(24px) scale(.985);transition:.35s ease}.slide.active{display:block;opacity:1;transform:translateX(0) scale(1)}.kicker{color:var(--cyan);text-transform:uppercase;font-weight:800;letter-spacing:.18em;font-size:14px;margin-bottom:12px}h1{font-size:62px;line-height:1.02;margin:0 0 16px;letter-spacing:-.04em}h2{font-size:45px;line-height:1.06;margin:0 0 18px;letter-spacing:-.035em}h3{font-size:26px;margin:0 0 14px;color:#E2E8F0}h4{font-size:20px;margin:0 0 8px;color:#F8FAFC}p,li{font-size:19px;line-height:1.45;color:#CBD5E1}.lead{font-size:24px;max-width:1060px;color:#DCEBFF;line-height:1.38}.grid{display:grid;gap:18px;margin-top:28px}.grid-2{grid-template-columns:repeat(2,1fr)}.grid-3{grid-template-columns:repeat(3,1fr)}.grid-4{grid-template-columns:repeat(4,1fr)}.card{background:linear-gradient(180deg,rgba(17,26,48,.86),rgba(10,18,36,.72));border:1px solid var(--line);border-radius:22px;padding:22px;box-shadow:0 18px 45px rgba(0,0,0,.22);min-height:156px}.card-icon{font-size:33px;margin-bottom:10px}.card p{font-size:17px;margin:0;color:#B9C6DA}.metric-row{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:34px}.metric{background:rgba(59,130,246,.09);border:1px solid rgba(59,130,246,.26);border-radius:24px;padding:24px;text-align:center}.metric-value{font-size:48px;font-weight:900;color:#FFFFFF;letter-spacing:-.04em}.metric-label{font-size:16px;color:#BAE6FD;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.metric-detail{margin-top:6px;font-size:14px;color:#94A3B8}.pills{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}.pill{display:inline-flex;border:1px solid rgba(34,211,238,.35);background:rgba(34,211,238,.08);color:#CFFAFE;border-radius:999px;padding:9px 14px;font-weight:700;font-size:15px}.flow{display:flex;align-items:stretch;gap:16px;margin-top:30px}.flow-box{flex:1;border-radius:20px;border:1px solid var(--line);background:rgba(15,23,42,.7);padding:20px;text-align:center;position:relative}.flow-box:after{content:'→';position:absolute;right:-18px;top:42%;color:var(--cyan);font-size:25px;font-weight:900}.flow-box:last-child:after{display:none}.flow-title{font-size:19px;font-weight:900;color:white;margin-bottom:8px}.flow-sub{font-size:15px;color:#A7B5CC;line-height:1.35}.arch{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:24px;align-items:center;margin-top:28px}.stack-col{display:grid;gap:14px}.stack-item{border:1px solid var(--line);background:rgba(15,23,42,.72);padding:16px 18px;border-radius:16px}.stack-item strong{display:block;color:#F8FAFC;font-size:18px;margin-bottom:4px}.stack-item span{color:#A9B8CE;font-size:15px}.core{border:2px solid rgba(34,211,238,.5);background:radial-gradient(circle at center,rgba(34,211,238,.16),rgba(59,130,246,.08));border-radius:28px;padding:34px 24px;text-align:center;box-shadow:0 0 60px rgba(34,211,238,.09)}.core-title{font-size:31px;font-weight:900;letter-spacing:-.03em}.core-sub{font-size:17px;color:#CDE8FF;margin-top:10px}.compare{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:28px}.before,.after{border-radius:24px;padding:26px;border:1px solid var(--line)}.before{background:rgba(239,68,68,.08);border-color:rgba(239,68,68,.25)}.after{background:rgba(16,185,129,.09);border-color:rgba(16,185,129,.28)}.before h3{color:#FCA5A5}.after h3{color:#A7F3D0}ul.clean{list-style:none;padding:0;margin:0}ul.clean li{margin:12px 0;padding-left:30px;position:relative}ul.clean li:before{content:'•';position:absolute;left:8px;color:var(--cyan);font-weight:900}.timeline{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:32px}.step{background:rgba(15,23,42,.72);border:1px solid var(--line);border-radius:20px;padding:18px;min-height:190px}.step-num{color:#67E8F9;font-size:15px;font-weight:900;letter-spacing:.12em}.step h4{margin-top:10px}.nav{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);display:flex;gap:12px;align-items:center;z-index:60;background:rgba(5,11,24,.75);border:1px solid var(--line);padding:10px 14px;border-radius:999px;backdrop-filter:blur(12px)}button{color:white;background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);border-radius:999px;padding:9px 14px;cursor:pointer;font-size:16px;font-weight:800}.counter{font-size:14px;color:#CBD5E1;min-width:78px;text-align:center}.footer-note{position:absolute;right:72px;bottom:58px;color:#64748B;font-size:13px}.codebox{background:#020617;border:1px solid rgba(148,163,184,.25);border-radius:20px;padding:22px;font-family:Consolas,Monaco,monospace;color:#BAE6FD;font-size:20px;line-height:1.6;white-space:pre;text-align:center}.fullscreen-tip{position:fixed;top:44px;right:18px;z-index:65;font-size:12px;color:#8FB3D9;opacity:.7}@media(max-width:900px){body{overflow:auto}.slide{padding:42px 24px 72px;overflow:auto}.slide{position:relative;min-height:100vh}h1{font-size:42px}h2{font-size:34px}.lead{font-size:20px}.grid-2,.grid-3,.grid-4,.compare,.arch,.timeline,.metric-row,.flow{grid-template-columns:1fr;display:grid}.flow-box:after{display:none}}
'''
    slides_html = []
    for i, slide in enumerate(SLIDES):
        cls = 'slide active' if i == 0 else 'slide'
        footer = f'<div class="footer-note">Versão TI + Malha • Gerado em {e(generated_at)}</div>' if i == 0 else ''
        slides_html.append(f'<section class="{cls}"><div class="kicker">{e(slide["kicker"])}</div><h1>{e(slide["title"])}</h1><p class="lead">{e(slide["lead"])}</p>{render_body(slide)}{footer}</section>')
    js = r'''
const slides=Array.from(document.querySelectorAll('.slide'));let current=0;document.getElementById('total').innerText=slides.length;function showSlide(i){slides[current].classList.remove('active');current=(i+slides.length)%slides.length;slides[current].classList.add('active');document.getElementById('idx').innerText=current+1}function nextSlide(){showSlide(current+1)}function prevSlide(){showSlide(current-1)}document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' ')nextSlide();if(e.key==='ArrowLeft'||e.key==='PageUp')prevSlide();if(e.key.toLowerCase()==='f'){if(!document.fullscreenElement){document.documentElement.requestFullscreen()}else{document.exitFullscreen()}}});
'''
    return f'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>SGO Eletroeletrônica MRS | Pitch TI + Malha</title><style>{css}</style></head><body><div class="ticker"><div class="ticker-content">⚡ SGO ELETROELETRÔNICA MRS ⚡ INTELIGÊNCIA OPERACIONAL ⚡ MALHA FERROVIÁRIA ⚡ GPS OBRIGATÓRIO ⚡ PWA OFFLINE HTTPS ⚡ SAP ↔ CAMPO ⚡ GOVERNANÇA ⚡ EVIDÊNCIA FOTOGRÁFICA ⚡ PRIORIZAÇÃO SISTÊMICA ⚡</div></div><div class="fullscreen-tip">Pressione F para tela cheia</div><div class="deck">{''.join(slides_html)}</div><div class="nav"><button onclick="prevSlide()">❮</button><div class="counter"><span id="idx">1</span> / <span id="total">1</span></div><button onclick="nextSlide()">❯</button></div><script>{js}</script></body></html>'''


def main():
    html_out = build_html()
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_out)
    abs_path = os.path.abspath(OUTPUT_FILE)
    print('Apresentação gerada:', abs_path)
    try:
        webbrowser.open('file://' + abs_path)
    except Exception:
        pass


if __name__ == '__main__':
    main()
