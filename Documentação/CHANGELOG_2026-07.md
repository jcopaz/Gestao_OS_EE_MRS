# CHANGELOG — SGO MRS (Deploy Julho/2026)

> Base de conhecimento consolidada das correções e melhorias aplicadas durante o deploy.
> Para uso como Knowledge no Copilot Studio.

## Contexto do Deploy
Deploy em produção do SGO Eletroeletrônica MRS com acompanhamento do time em campo.
Baixas online realizadas com sucesso (10 OS na 1ª noite). Correções aplicadas por sessão,
sem reescrita do `app.py`.

---

## ✅ Bugs Corrigidos

### 1. Offline: bloqueio geográfico falso ("5655 km do local") — CRÍTICO
- **Sintoma:** no pacote offline, o app não capturava GPS e a API rejeitava a baixa
  alegando ~5655 km de distância (limite antifraude = 2,0 km).
- **Causa raiz (encadeada):**
  1. Pacote aberto como `file://` (contexto inseguro) → o navegador bloqueia
     `navigator.geolocation` → payload segue com `lat_browser=0.0 / lon_browser=0.0`
     (comportamento esperado, aciona o fallback EXIF na API).
  2. A função `comprimirImagemArquivo` (canvas `toBlob`) **removia o EXIF/GPS** da foto.
     Sem EXIF, a API calculava Haversine de (0,0) até o ativo (~5655 km) e estourava a cerca.
- **Correção (sessão 3.12, `montarPayload`):** quando `gpsAtual == null`, enviar a
  **foto ORIGINAL** (EXIF preservado) em vez da comprimida. Com GPS de navegador presente,
  a compressão normal é mantida (payload leve).
- **Validação:** a API (`/sincronizar_baixa_offline`) lê o GPS EXIF a partir dos **bytes
  originais** da foto, ANTES de qualquer `exif_transpose`/resize — fallback funcional ponta a ponta.

### 2. Câmera derrubava o login (online e offline) — CRÍTICO
- **Sintoma:** ao abrir a câmera do celular, o técnico era deslogado e perdia o apontamento.
- **Causa raiz:** autenticação vivia apenas em `st.session_state`. No mobile, abrir a câmera
  manda o navegador para segundo plano → WebSocket do Streamlit cai → sessão recriada →
  `logged_in` volta a `False`.
- **Correção:** persistência de sessão via **token HMAC assinado** na URL (`?sid=`), com TTL de 12h.
  - Nova subsessão **1.6**: helpers `gerar_token_sessao` / `validar_token_sessao`.
  - Restauração da sessão no boot (antes da barreira de login 2.1).
  - Emissão do token no início do 10.1 (após login).
  - `st.query_params.clear()` no logout (botões "🚪 Sair" e "🔑 Trocar", sessão 9.2).
  - Requer segredo `AUTH_TOKEN_SECRET` no secrets do app.

### 3. Cronograma não filtrava por ativo + app pesado (auto-refresh)
- **Sintoma:** selecionar ativo não filtrava o cronograma; alterar o raio recalculava tudo
  automaticamente (app lento).
- **Causa raiz:** o `selectbox` de ativo estava dentro de `@st.fragment` (10.3.3), enquanto o
  cronograma (10.3.5) está fora — a troca só rerodava o fragment. O slider do raio disparava
  rerun completo a cada ajuste.
- **Correção:** botão **"🔎 Filtrar"** aplica raio + ativo via `st.session_state`
  (`raio_aplicado` / `ativo_aplicado`); nada é recalculado automaticamente.
  Cronograma passou a ler `ativo_aplicado`.

### 4. KeyError "Ativo" com raio de 1 km
- **Causa raiz:** `df_recomendado` é inicializado como `pd.DataFrame()` (sem colunas) e só ganha
  a coluna `Ativo` quando há OS no raio. Com raio de 1 km surgiu o cenário "zero OS", expondo o
  acesso `df_recomendado["Ativo"]` sem coluna.
- **Correção (10.3.3):** guarda no início do fragment —
  `if df_recomendado.empty or "Ativo" not in df_recomendado.columns: return` com aviso amigável.

### 5. NameError `opcoes_ativos`
- **Causa raiz:** a linha `opcoes_ativos = ["Todos os Ativos na Rota"] + ativos_disp` foi removida
  acidentalmente ao inserir a guarda do item 4.
- **Correção:** linha reposta antes do `selectbox`.

---

## 🚀 Melhorias Aplicadas
- **Botão "Filtrar"** — fim da atualização automática; app mais leve e rápido.
- **Raio inicial de 1 km** (era 10 km) — busca mais precisa por proximidade.
- **Login persistente** — sessão mantida mesmo ao usar a câmera.
- **Preservação do GPS da foto** — localização mais confiável no apontamento offline.
- **Filtro CI / SI (Com Intervalo / Sem Intervalo) no modo offline** — organização das OS por tipo de intervalo.

---

## 📌 Regras Operacionais Atuais
- **Baixa preferencial: ONLINE.** Offline é contingência para área de sombra.
- **Limite antifraude:** 2,0 km do ativo (Haversine). Bypass de teste: `debug_token = "mrs2026"`.
- **GPS obrigatório** para conclusão da baixa.
- **Fonte de localização (ordem):** 1º GPS do navegador; 2º GPS EXIF da foto (só quando o navegador manda 0,0).

## ✅ 2ª rodada (03/Jul)
4. Baixa DUPLICADA → dedup evidências antes do merge 1:N.
5. OS "fantasma" online → hash com MAX(realizado_em).
6. OS não some offline → osGravadasSet.
7. NameError tab2 → tab1/tab2=None antes do roteamento.
8. Bloqueio Muito Alta furado → mask_critica = rank==1 (sem data).
9. OS bloqueadas invisíveis → sombreado + cadeado 🔒 (online expander / offline card).
10. 404 Publicar PWA → endpoints /health, /publicar_pacote, /pacote/{id}, CORS GET, pwa_pacotes.

## 🔁 Mudança de estratégia GPS/EXIF (03/Jul)
GPS OBRIGATÓRIO (online e offline); EXIF REMOVIDO. Foto offline sempre comprimida.
API rejeita 0,0 (HTTP 400). Offline agora via PWA HTTPS (publicar → abrir /pacote/{id} 1x online).

## 🚀 Melhorias
Botão Filtrar; raio 1 km; login persistente; filtro CI/SI offline; horário único na baixa em massa;
OS bloqueadas visíveis; publicação PWA HTTPS.
