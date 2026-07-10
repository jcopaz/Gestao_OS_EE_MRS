# 📜 Histórico do Projeto

## 🗓️ Linha do tempo

| Fase | Período | Conquista |
|---|---|---|
| **MVP** | Jun 2026 | App Streamlit de baixa de OS com mapa e roteirização |
| **Motor Antifraude** | Jun–Jul 2026 | API FastAPI (Render) + geofence Haversine 2,0 km |
| **Offline / PWA** | Jul 2026 | HTML/JS gerado em Python + IndexedDB + sync via FormData |
| **Deploy 03/Jul** | 03/07/2026 | Raio inicial 1 km, botão "Filtrar", login persistente |
| **GPS obrigatório** | Jul 2026 | EXIF removido; GPS somente pelo navegador (online+offline) |
| **Apresentação v10** | 09/07/2026 | Deck executivo premium (9 slides, estilo v8/dourado) |

---

## ✅ Conquistas técnicas validadas

### Roteirização & Proximidade
- **Raio inicial 1 km** (era 10 km) — busca mais precisa.
- Raio/ativo aplicados via **botão "Filtrar"** (`raio_aplicado` / `ativo_aplicado`) — sem auto-refresh (app mais leve).
- `df_recomendado` inicia **vazio** → guarda obrigatória antes de acessar colunas.
- **Haversine** para distância técnico ↔ ativo; agrupamento por proximidade.

### Priorização Muito Alta (VIGENTE)
- Qualquer OS **Muito Alta** (`Criticidade_rank=1`) **trava as menores do mesmo grupo** (Ativo × Tipo de Intervalo), **independente da data**.
- Filas **CI/SI** (Com Intervalo / Sem Intervalo) são **independentes**.
- OS bloqueadas ficam **VISÍVEIS** (sombreado + 🔒) — nunca ocultas.

### Baixa em massa
- **Horário único** (toggle default ligado): 1 Data/Hora Início/Fim replicado às OS selecionadas (online e offline). Modo individual mantido.

### Offline / PWA / GPS
- Sessões **3.9–3.13** geram HTML/JS em f-strings (cuidado com chaves `{`/`}`).
- **IndexedDB** + `osGravadasSet` (boot / após gravar / após sync): OS some da lista ao gravar.
- **GPS OBRIGATÓRIO** (online e offline); **EXIF REMOVIDO** — sem GPS do navegador, não grava.
- `file://` bloqueia geolocation → distribuir via **PWA HTTPS**: "Publicar Rota PWA" → `POST /publicar_pacote` → abrir `GET /pacote/{id}` 1x online → usar offline.

### Autenticação
- Login em `st.session_state` + **token HMAC na URL** (`?sid=`, TTL 12 h, `AUTH_TOKEN_SECRET`).
- **Login persistente** mesmo ao abrir a câmera.
- Logout limpa o token (`st.query_params.clear()`).

### Antifraude
- **Geofence 2,0 km** (Haversine). GPS **somente do navegador** — API rejeita `0,0` com **HTTP 400**.
- Bypass de teste: `debug_token = "mrs2026"`.

---

## 🐛 Correções marcantes (pós 03/Jul)

| # | Sintoma | Correção |
|---|---|---|
| 10.3.3 | `KeyError "Ativo"` com raio 1 km e zero OS | Guarda `if df_recomendado.empty or "Ativo" not in df_recomendado.columns: return` |
| — | `NameError opcoes_ativos` | Linha reposta antes do `selectbox` |
| 8 | `404` em ação contra a API | Conferir rota em `api.py` + método liberado no CORS |
| 3.1.3 | Filtro de Programação/Execução não trazia OS com dia ≤12 | `parse_data_programada` invertia dia/mês (`dayfirst=True`) em datas já ISO; agora detecta ISO antes de decidir o parse |
| 10.3.3 | Baixa online concluía OS sem foto | Trava real (bloqueia `upsert_baixa`) além do aviso; servidor rejeita foto de 0 bytes em `/sincronizar_baixa_offline` |
| 10.3.3 | Geofence 2 km não valia no fluxo Online | Online grava direto no banco sem passar pela API (sem Haversine); replicada a mesma regra de 2,0 km no ponto de submissão online |
| 3.6 / overlay | Filtro de "Período de Execução" zerava o Backlog (Taxa 100%) | Duas causas: (1) máscara de execução sem `\| isna()` descartava pendentes; (2) **overlay de baixas contaminado entre ciclos** — SAP reaproveita número de OS ao reprogramar, e a baixa antiga (órfã) "grudava" na OS do novo ciclo via merge por `Ordem servico`. Corrigido validando `realizado_em >= Data inicial programada` do ciclo vigente antes de aplicar a baixa. Confirmado com 3736 OS afetadas via SQL no Neon (09/07/2026) |
| 10.3.3 | Geofence online ainda liberava baixa fora do raio (teste real: Guarulhos → concluiu OS em pátio IRA) | Causa raiz dupla: (1) lookup de coordenada usava `Ativo[:3]` em vez da coluna `Patio` já resolvida (mapeamento oficial); (2) design "fail-open" — se a OS ou o pátio não fossem resolvidos, o código pulava a validação (`continue`) e liberava a baixa. Corrigido para usar `Patio` resolvido e para **bloquear** (fail-closed) quando não for possível confirmar a localização (10/07/2026) |
| Deploy | App parou (`Segmentation fault`) após reboot manual no Streamlit Cloud | `requirements.txt` sem nenhum pin de versão — reboot puxou `numpy 2.x` (quebra binária com libs geoespaciais) e depois `geopandas<1.0` puxou `fiona`/GDAL nativo (indisponível no build). Corrigido travando versões + `geopandas>=1.0` (usa `pyogrio`) + Python do Streamlit Cloud fixado em **3.12** (estava em 3.14, sem wheels prontas). Ver [[Padrão de Dependências]] em `05_PADROES_TECNICOS.md` (10/07/2026) |

---

## 🎬 Apresentação executiva (v10)

- **Formato:** HTML5 standalone, imagens/logos embutidos em **base64**.
- **9 slides:** Capa → Problema → O que é (matrix) → Fluxo → Malha (antes/agora) → Priorização → Governança (matrix) → Arquitetura (malha pulsante) → Ponte para demo.
- **Estilo:** escuro/tech, **paleta dourada v8** (`#f3b13c` + cyan `#39d6e8`), FX (spots, sparks, geofencing pulsante).
- **Gerador:** `gerar_pitch_v10.py` (Pillow + numpy) → `SGO_Eletroeletronica_MRS_v10.html`.
- **Uso:** abertura antes da **demonstração ao vivo** da aplicação.

---

## 💡 Insights estratégicos

1. O valor do SGO é **transformar conhecimento tácito de campo em regra sistêmica** auditável.
2. A OS deixa de ser "linha em planilha" e vira **ponto operacional da malha**.
3. **GPS do navegador é a fonte de verdade** — remover EXIF simplificou e endureceu o antifraude.
4. **Baixa preferencial: ONLINE**; offline (PWA HTTPS) é **contingência**.
5. O deck deve **preparar** a audiência para a demo, não substituí-la.
