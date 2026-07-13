# 🏛️ Arquitetura do SGO Eletroeletrônica

## 🎯 Visão de produto

> **Plataforma de inteligência operacional aplicada à malha ferroviária MRS**, que conecta SAP, ativos, geolocalização, execução em campo, evidências e governança em uma única camada digital.

---

## 🔄 Fluxo ponta a ponta

```
SAP  →  Motor SGO  →  Campo  →  Banco / Evidências  →  Retorno SAP
```

| Etapa | O que faz |
|---|---|
| **SAP** | OS programadas + plano de manutenção (origem) |
| **Motor SGO** | Priorização, regras, geografia, governança |
| **Campo** | GPS, foto, modo offline, baixa da OS |
| **Banco / Evidências** | Histórico auditável + storage de fotos |
| **Retorno SAP** | IW47, baixas em massa, dados estruturados |

---

## 💻 Stack tecnológica

| Camada | Tecnologia | Observação |
|---|---|---|
| Frontend / Painel | **Streamlit** (+ HTML/CSS/JS, ECharts, Folium) | Domínio do Julio |
| Motor Antifraude / API | **FastAPI** (Render) | Endpoints de sync/publicação |
| Banco de dados | **PostgreSQL (Neon)** | Serverless |
| Storage de fotos | **Supabase Storage** | Evidência fotográfica |
| Modo Offline | **PWA** (HTML/JS gerado por Python) + **IndexedDB** | Sync via FormData |
| Segurança | **HTTPS + API Key** · token HMAC na URL | GPS somente navegador |
| Geolocalização | **GPS HTML5 + Haversine** | Geofence 2,0 km |
| ERP | **SAP / IW47** | Retorno estruturado |
| Hospedagem — Painel (`app.py`) | **Streamlit Community Cloud** (`sgomrs.streamlit.app`) | ⚠️ Plataforma DIFERENTE do Render — Python fixado em **3.12** nas Settings do app (3.14 quebra build de pandas/geopandas) |
| Hospedagem — API (`api.py`) | **Render** (`gestao-os-ee-mrs-producao.onrender.com`, free tier) | Free tier "dorme" por inatividade; keep-alive duplo: cron-job.org + GitHub Actions (`.github/workflows/keep-alive-render.yml`, a cada 10min) |

> ⚠️ **`app.py` e `api.py` NÃO ficam no mesmo host.** Um push no `main` dispara redeploy nos dois lugares (Render + Streamlit Cloud) de forma independente — sempre confirmar os DOIS quando uma correção envolver o painel.

> ⚠️ **Distribuído como PWA em HTTPS — nunca `file://`** (senão o navegador bloqueia geolocation).

---

## 🔌 Contrato da API (Motor Antifraude)

### Endpoints
| Método | Rota | Função |
|---|---|---|
| `POST` | `/sincronizar_baixa_offline` | Sincroniza baixa feita offline |
| `GET` | `/health` | Healthcheck |
| `POST` | `/publicar_pacote` | Publica pacote da Rota PWA |
| `GET` | `/pacote/{id}` | Abre o pacote 1x online (antes de usar offline) |

### `POST /sincronizar_baixa_offline`

**Campos obrigatórios (Form):**
`os_id`, `ativo_id`, `usuario`, `lat_browser`, `lon_browser`, `data_hora_local`, `horario_inicio`, `horario_fim` · **`foto`** (File/UploadFile)

**Campos opcionais:** `acompanhante` (default vazio), `debug_token` (default `None`)

**Regras de negócio:**
1. GPS **somente do navegador**. Se `lat_browser = 0.0` e `lon_browser = 0.0` → **HTTP 400** (não há mais fallback EXIF).
2. Distância validada por **Haversine**.
3. **Limite geográfico: 2,0 km por padrão** — configurável por coordenação via tabela `configuracoes_operacionais` (`carregar_config_operacional`, resolvida pela coordenação da OS em `os_programadas`). Fora da janela de vigência, volta ao padrão de 2,0 km sozinho.
4. `debug_token = "mrs2026"` → ignora o bloqueio geográfico (teste).

---

## 🔐 Autenticação & Governança

- Login em `st.session_state` + **token HMAC na URL** (`?sid=`, TTL **12 h**, segredo `AUTH_TOKEN_SECRET`).
- **Login persistente** ao abrir a câmera; logout limpa o token (`st.query_params.clear()`).
- Governança registrada: usuário · data · hora · localização · foto de evidência.
- Rejeição de coordenada inválida (`0,0`); geofencing 2,0 km; perfis de acesso.

---

## 📴 Modo Offline / PWA (fluxo)

1. No painel: **"Publicar Rota PWA"** → `POST /publicar_pacote`.
2. Abrir **`GET /pacote/{id}` 1x online** (contexto seguro HTTPS).
3. Usar **sem sinal** em campo → grava na fila **IndexedDB**.
4. Ao voltar a rede → **sincroniza** via `POST /sincronizar_baixa_offline`.
5. `osGravadasSet` evita duplicidade (OS some da lista após gravar/sync).

---

## 🗺️ Domínio operacional

| Termo | Significado |
|---|---|
| **OS** | Ordem de Serviço (origem SAP) |
| **Ativo** | Equipamento eletroeletrônico na malha (com coordenadas) |
| **Pátio** | Ponto operacional com coordenadas |
| **Tipo de Intervalo** | CI (Com Intervalo) / SI (Sem Intervalo) — filas independentes; é um **filtro prévio**, não entra no cascateamento de prioridade |
| **Criticidade_rank** | 1 = Muito Alta (trava as menores do mesmo grupo) |
| **Geofence** | Cerca operacional — padrão 2,0 km do ativo, configurável por coordenação |
| **Segurança da Operação** | Camada composta de priorização (classificação × criticidade) — ver `configuracoes_operacionais` |
| **Configurações Operacionais** | Tela admin (perfil "Administrador") para ajustar geofence/trava/escopo/ordem por coordenação, com vigência automática |

---

## 🔑 Decisões arquiteturais cristalizadas

| Decisão | Por quê |
|---|---|
| **GPS somente do navegador (EXIF removido)** | Antifraude mais simples e confiável |
| **Baixa preferencial ONLINE; offline = contingência** | Consistência dos dados |
| **PWA HTTPS, nunca `file://`** | Geolocation exige contexto seguro |
| **Raio inicial 1 km + botão "Filtrar"** | Precisão e performance (sem auto-refresh) |
| **OS Muito Alta trava as menores do grupo** | Governança de priorização |
| **OS bloqueadas visíveis (🔒)** | Transparência para o técnico |
| **Horário único na baixa em massa** | Agilidade sem perder rastreabilidade |
| **Deck HTML standalone (base64)** | Portabilidade total, F11 fullscreen, sem dependências |
| **Geofence/trava/ordem configuráveis por coordenação, com vigência** | Cenários operacionais especiais (plano de guerra) sem mexer em código — e sem risco de esquecer uma trava de segurança desligada (expira sozinha) |
| **Config expira "na leitura", sem cron** | `vigente_desde`/`vigente_ate` comparados a `datetime.now()` a cada leitura — simples, sem infraestrutura de job agendado |
