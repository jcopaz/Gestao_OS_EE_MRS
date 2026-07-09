# README_AGENTE.md

> Atualizado em 03/Julho/2026 (2ª noite de deploy).

## Projeto
SGO MRS — sistema híbrido de gestão operacional, roteirização, geolocalização e apontamento de
Ordens de Serviço (OS) para operação ferroviária.

## Arquitetura resumida
- **Frontend / Painel:** Streamlit com HTML/CSS/JS, ECharts, Folium e componentes auxiliares.
- **Motor Antifraude / API:** FastAPI (Render). Endpoints: `/sincronizar_baixa_offline`,
  `/health`, `/publicar_pacote`, `/pacote/{id}`.
- **Banco de Dados:** PostgreSQL (Neon).
- **Storage de fotos:** Supabase.
- **Modo Offline (PWA):** HTML/JS gerado dinamicamente pelo Python, usando IndexedDB para fila
  local e sincronização via FormData. **Distribuído como PWA em HTTPS (nunca `file://`).**

## Regras inegociáveis
1. Estrutura por `#region` / `#endregion`; `#endregion` é a última linha do bloco.
2. Apenas um `with tab1:` e um `with tab2:` por caminho de execução (blocos 10.3.x usam guard
   `if tab2 is not None:`). **`tab1=None; tab2=None` inicializados ANTES do roteamento (10.1).**
3. Usar 4 espaços; nunca misturar TAB e espaços.
4. Remover HTML escapado (`&lt;`, `&gt;`, `&amp;`) do código final.
5. Tudo que precisa sobreviver a rerun vai para `st.session_state`.

## Roteirização
- **Raio inicial: 1 km.** Raio/ativo aplicados via botão **"Filtrar"**
  (`raio_aplicado`/`ativo_aplicado`), sem auto-refresh. `df_recomendado` inicia vazio → guardar
  `if df_recomendado.empty or "Ativo" not in df_recomendado.columns`.

## Priorização Muito Alta (VIGENTE)
- Qualquer OS Muito Alta (`Criticidade_rank==1`) trava as menores do MESMO grupo
  (Ativo × Tipo de Intervalo), **independente da data**. CI/SI filas independentes.
- OS bloqueadas ficam VISÍVEIS (sombreado + 🔒). Backlog priorizado só na ordenação.

## Baixa em massa
- **Horário único** (toggle default ligado): 1 Data/Hora Início/Fim replicado às OS selecionadas
  (online e offline). Modo individual mantido.

## Offline / PWA / GPS
- Sessões 3.9–3.13 geram HTML/JS em f-strings (chaves JS `{{`/`}}`).
- IndexedDB + `osGravadasSet` (boot/após gravar/após sync): OS some da lista.
- **GPS OBRIGATÓRIO (online e offline); EXIF REMOVIDO.** Sem GPS do navegador, não grava.
- `file://` bloqueia geolocation → distribuir via **PWA HTTPS**: "Publicar Rota PWA"
  → `POST /publicar_pacote` → abrir `GET /pacote/{id}` 1x online → usar offline.

## Autenticação
- Login em `st.session_state` + token HMAC na URL (`?sid=`, TTL 12h, `AUTH_TOKEN_SECRET`).
- Logout limpa o token (`st.query_params.clear()`).

## Antifraude
- Geofence 2,0 km (Haversine). Fonte de GPS: SOMENTE navegador (API rejeita 0,0 com HTTP 400).
- Bypass de teste: `debug_token = "mrs2026"`.

## Para agentes
- Corrigir por sessão; investigar estrutura antes da lógica.
- Validar: `py_compile` (app/api) + `node --check` na JS do pacote offline.