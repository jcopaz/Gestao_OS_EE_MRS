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
| `POST` | `/limpar_evidencias_expiradas` | Apaga do Storage as fotos além da retenção (`CICLO + 30 dias`). `dry_run=true` por padrão. Chamado pelo cron diário |
| `POST` | `/limpar_evidencias_orfas` | Apaga do Storage arquivos sem linha correspondente em `evidencias` (resíduo de upload duplicado). `dry_run=true` por padrão. Disparo manual |
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

## 🔑 Variáveis de ambiente / segredos

Não há `.env` no repositório. Cada host tem o seu conjunto:

| Nome | Lido em | Configurar em | Para quê |
|---|---|---|---|
| `NEON_POSTGRES_URL` | `api.py` (`os.environ`, ~32) · `app.py` (`st.secrets`, região 1.3) | Render (env) · Streamlit Cloud (Secrets) · `.streamlit/secrets.toml` local | DSN do Postgres/Neon — **todas** as tabelas |
| `SUPABASE_URL` | `api.py` · `app.py` região 3.3 | Render · Streamlit Cloud | Base REST do Storage (bucket `evidencias`) |
| `SUPABASE_KEY` | `api.py` · `app.py` região 3.3 | Render · Streamlit Cloud | `Authorization`/`apikey` do Storage (upload, list, delete) |
| `API_KEY_SECRET` | `api.py` (`validar_api_key`) | Render | Protege **todos** os endpoints do `api.py` (header `x-api-key`) |
| `OFFLINE_API_KEY` | `app.py` (`st.secrets` — embute no pacote PWA) · 3 workflows | Streamlit Cloud · **GitHub → Settings → Secrets → Actions** | Mesmo valor de `API_KEY_SECRET` |
| `AUTH_TOKEN_SECRET` | `app.py` | Streamlit Cloud | Segredo do token HMAC de login (`?sid=`, 12 h) |

> ⚠️ `API_KEY_SECRET` e `OFFLINE_API_KEY` são hoje **a mesma chave mestra**, embutida em texto no HTML do pacote PWA — dívida de segurança conhecida (ver `09_APRENDIZADOS_E_ERROS.md`, 21/08/2026). A URL da API (`https://gestao-os-ee-mrs-producao.onrender.com`) está **hardcoded** nos 3 workflows (`keep-alive-render`, `limpeza-evidencias-expiradas`, `limpeza-evidencias-orfas`) — se o serviço do Render mudar de nome, atualizar os 3 `.yml`.

---

## 📴 Modo Offline / PWA (fluxo)

1. No painel: **"Publicar Rota PWA"** → `POST /publicar_pacote`.
2. Abrir **`GET /pacote/{id}` 1x online** (contexto seguro HTTPS).
3. Usar **sem sinal** em campo → grava na fila **IndexedDB**.
4. Ao voltar a rede → **sincroniza** via `POST /sincronizar_baixa_offline`.
5. `osGravadasSet` evita duplicidade (OS some da lista após gravar/sync).

---

## 🗂️ Ciclo de vida da evidência fotográfica

A foto da baixa é **comprimida no servidor** (1280 px máx., JPEG q75 — `upload_foto_supabase`, duplicada em `app.py` e `api.py`) e enviada para o **bucket `evidencias` do Supabase Storage**. Só o arquivo mora lá; o vínculo (`os_referencia`, `ativo`, `atividade`, `concluido_por`, `geolocalizacao`) fica na tabela **`evidencias` do Neon**.

> ⚠️ **Banco e Storage são provedores diferentes.** Rodar SQL contra a tabela `evidencias` no **SQL Editor do Supabase** dá `relation "evidencias" does not exist` — ela está no **Neon**. O SQL Editor do Supabase só enxerga o schema `storage` (os arquivos em si, em `storage.objects`).

### Política de retenção

| Item | Regra |
|---|---|
| Quando expira | `baixas.realizado_em` + `CICLO` (dias, de `os_programadas.dados_completos`) + **30 dias de folga** |
| Chave `CICLO` | Lida com `COALESCE('CICLO','Ciclo','ciclo')` — busca em JSON é sensível a caixa (bug real de 26/07/2026, ver `09_APRENDIZADOS_E_ERROS.md`) |
| Sem `CICLO` ou `realizado_em` ilegível | **Nunca expira** (fail-safe — não arrisca apagar evidência sem saber a janela) |
| Ao expirar | Apaga o **arquivo** no Storage; a **linha** em `evidencias` fica, com `foto_url = ''` (mantém histórico/auditoria da baixa) |

### Automação (GitHub Actions)

| Workflow | Endpoint | Quando |
|---|---|---|
| `limpeza-evidencias-expiradas.yml` | `POST /limpar_evidencias_expiradas` | **Cron diário 06:00 UTC (03:00 BRT)** — força `dry_run=false`. Disparo manual assume `dry_run=true` |
| `limpeza-evidencias-orfas.yml` | `POST /limpar_evidencias_orfas` | **Manual apenas** — faxina de arquivos no bucket sem linha em `evidencias` (upload duplicado). O grupo `seguro_apagar` só inclui órfã cuja OS já tem evidência atual |

Ambos exigem `x-api-key` (`OFFLINE_API_KEY`) e respondem com JSON de auditoria (`total_candidatas` / `total_no_bucket` / `apagadas` / `erros`). `curl -s` sem `-f` no workflow → o job fica verde mesmo se a API responder erro; conferir o corpo JSON no log da execução, não só a cor.

### Dimensionamento (verificado em 06/09/2026)

~3.000–3.600 fotos/mês (~550 MB/mês), média ~158 KB. Com a retenção de ~2 meses vivos ao mesmo tempo, o regime permanente do bucket fica **acima de 1 GB** — teto do plano free do Supabase. O ciclo funciona (junho/2026 tinha só 15 arquivos); o gargalo é o plano, não o job. Alavancas em `09_APRENDIZADOS_E_ERROS.md` (06/09/2026): comprimir mais, reduzir a folga de 30 dias (decisão de negócio) ou Supabase Pro.

### Onde está no código

| Peça | Arquivo / região |
|---|---|
| Compressão + envio (1280 px / JPEG q75) | `app.py` região **3.3** (`upload_foto_supabase`, `_sanear_nome_arquivo`, `upsert_evidencia`, `carregar_evidencias_df`) · `api.py` **~165–225** — mesmas funções, **duplicadas** (editar as duas) |
| Upload no fluxo **online** | `app.py` chamadas em **~7720** (Conclusão) e **~8034** (NRAV). A versão de `app.py` do `upload_foto_supabase` **levanta exceção** se o Supabase recusar → a baixa **não grava**, técnico vê erro |
| Upload no fluxo **offline** | `api.py` `POST /sincronizar_baixa_offline` (**~401**), upload em **~481**. A versão de `api.py` **retorna `""`** se o Supabase recusar → cai no **fallback base64** (**~486**): grava `foto_url = "data:image/jpeg;base64,..."` **no Neon**. A baixa grava, mas a foto passa a pesar no **banco** (não no bucket) e **nunca é ciclada** — o filtro de expiração só casa `foto_url LIKE '%/object/public/evidencias/%'` |
| Expiração (`CICLO + 30`) | `api.py` `POST /limpar_evidencias_expiradas` (**~541–610**); o `+ 30` literal está em **~575** (`timedelta(days=float(ciclo) + 30)`) |
| Órfãs | `api.py` `POST /limpar_evidencias_orfas` (**~636–762**) |
| Agendamento | `.github/workflows/limpeza-evidencias-expiradas.yml` · `limpeza-evidencias-orfas.yml` |
| Formato de `realizado_em` | texto `DD/MM/AAAA HH:MM` (`formatar_dt_br`, `api.py` ~114) — `baixas.realizado_em` é `VARCHAR`, não timestamp; por isso o SQL de diagnóstico usa `to_timestamp(..., 'DD/MM/YYYY HH24:MI')` |

> O bucket `evidencias` é **público** (`/storage/v1/object/public/evidencias/...`). O painel exibe a foto pela URL direta gravada em `evidencias.foto_url`, **sem URL assinada** e sem endpoint intermediário (`/fotos/url` é do outro app, o SGO Workforce). `upsert_evidencia` faz `ON CONFLICT (os_referencia)` — **1 evidência por OS**, a nova sobrescreve a anterior.

### Manutenção / diagnóstico

**Rodar manual:** GitHub → aba **Actions** → o workflow → **Run workflow**. Input `dry_run`: `true` só simula (devolve `total_candidatas` / `seguro_apagar` no log do passo `curl`), `false` apaga. Cron diário = `dry_run=false`; disparo manual = `true`.

**Não há teste local** — os endpoints batem em Supabase + Neon de produção. Ao mudar a lógica: validar com `dry_run=true` (idempotente) antes de liberar `false`. `py_compile api.py` continua obrigatório.

**"Está ciclando?" — SQL no Neon** (a tabela `evidencias` está no **Neon**, não no SQL Editor do Supabase):

```sql
WITH base AS (
  SELECT ev.id, b.realizado_em, (op.os IS NOT NULL) AS tem_op,
         COALESCE(op.dados_completos->>'CICLO', op.dados_completos->>'Ciclo',
                  op.dados_completos->>'ciclo') AS ciclo_txt
  FROM evidencias ev
  JOIN baixas b               ON TRIM(b.os)  = TRIM(ev.os_referencia)
  LEFT JOIN os_programadas op ON TRIM(op.os) = TRIM(ev.os_referencia)
  WHERE ev.foto_url LIKE '%/storage/v1/object/public/evidencias/%'
), calc AS (
  SELECT *,
    CASE WHEN btrim(ciclo_txt) ~ '^[0-9]+(\.[0-9]+)?$' THEN btrim(ciclo_txt)::numeric END AS ciclo_dias,
    CASE WHEN realizado_em ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}$'
         THEN to_timestamp(realizado_em,'DD/MM/YYYY HH24:MI')::timestamp END AS realizado_ts
  FROM base
)
SELECT count(*) FILTER (WHERE tem_op AND ciclo_dias IS NULL)                          AS imune_sem_chave_ciclo,
       count(*) FILTER (WHERE ciclo_dias IS NOT NULL AND realizado_ts IS NOT NULL
             AND realizado_ts + (ciclo_dias+30)*interval '1 day'
                 <= now() AT TIME ZONE 'America/Sao_Paulo')                           AS ja_venceu_e_ainda_no_storage
FROM calc;
```

`imune_sem_chave_ciclo > 0` → regressão da chave `CICLO` (ver `09_`, 26/07). `ja_venceu_e_ainda_no_storage` em dezenas+ enquanto os runs do workflow mostram `apagadas: []` → o job não está apagando de verdade (Render dormindo às 06:00 UTC, secret errado, ou exceção no endpoint). Poucas unidades = lag normal do cron das 03:00 BRT.

```sql
-- Tamanho do bucket e crescimento por mês (SQL no Supabase)
SELECT date_trunc('month', created_at) AS mes, count(*) AS arquivos,
       pg_size_pretty(sum((metadata->>'size')::bigint)) AS tamanho
FROM storage.objects WHERE bucket_id = 'evidencias' GROUP BY 1 ORDER BY 1;
```

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
| **Segurança da Operação** | Camada composta de priorização (classificação × criticidade) — ver `configuracoes_operacionais`. Atualizado 21/07/2026: só existe classificação Segurança **ou** Confiabilidade (não existe "Confiabilidade e Segurança") — ver `05_PADROES_TECNICOS.md` |
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
| **Evidência expira por `CICLO + 30 dias`, apagando só o arquivo** | Storage do plano free é escasso; a linha em `evidencias` fica (com `foto_url=''`) para não perder o histórico de auditoria da baixa. Sem `CICLO`/data → nunca expira (fail-safe) |
