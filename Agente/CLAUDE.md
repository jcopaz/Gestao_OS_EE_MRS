# 🚂 SGO Eletroeletrônica MRS — Guia do Agente (Claude / Copilot)

> Este arquivo é o **ponto de entrada** do agente. Ele orienta o Claude Code
> (e o GitHub Copilot) a trabalhar no projeto **SGO Eletroeletrônica MRS**.

---

## 📖 Como usar este pacote

Ao iniciar, **leia os arquivos de contexto na pasta `docs/agente/`** (ou onde
este pacote estiver), nesta ordem:

1. `00_INDICE.md` — índice mestre
2. `01_IDENTIDADE.md` — quem é o agente, missão e tom
3. `02_CONTEXTO_USUARIO.md` — perfil do Julio
4. `03_HISTORICO_PROJETO.md` — linha do tempo + conquistas
5. `04_ARQUITETURA.md` — stack, fluxo, contrato da API
6. `05_PADROES_TECNICOS.md` — regras inegociáveis
7. `06_PREFERENCIAS_JULIO.md` — estilo de trabalho
8. `07_ROADMAP.md` — em produção / curto prazo / futuro
9. `08_GLOSSARIO_SGO.md` — termos, endpoints, campos

---

## 🎯 Missão

O SGO **não é um apontador de OS** — é um **mecanismo de decisão operacional**
aplicado à malha ferroviária MRS, conectando SAP, ativos, geolocalização,
execução em campo, evidências e governança.

O agente atua em **duas frentes**:

| Frente | Arquivos | Subagente |
|---|---|---|
| **App SGO** (execução em campo) | `app.py`, `api.py`, PWA offline | `.claude/agents/sgo-dev.md` |
| **Apresentação executiva** (deck v11) | `gerar_pitch_v11.py` | `.claude/agents/pitch-builder.md` |

---

## 🧭 Fluxo de trabalho padrão

1. **Confirme o alvo:** App SGO ou Apresentação v11?
2. **Investigue a estrutura** (o bloco/`#region` atual) antes de propor lógica.
3. **Patch cirúrgico** — corrija **por sessão**, nunca reescreva o arquivo inteiro.
4. **Valide:** `python -m py_compile app.py api.py` + `node --check` na JS do PWA.
5. **Antes de promover `dev` → `main`**, se a mudança mexeu em lógica de negócio, priorização, segurança/GPS ou dado sensível: rodar uma revisão de qualidade (skill `security-guidance` e/ou `receiving-code-review`) além do `py_compile`. Objetivo: pegar o bug **antes** do deploy — um ciclo de "usuário reporta bug em produção → investigar → corrigir → redeployar" custa muito mais (tempo e tokens) do que uma revisão rápida antes de subir.
6. **Tarefa grande ou requisito ambíguo** (ex.: mudança de regra de negócio, feature com vários passos): usar a skill `writing-plans` e/ou `brainstorming` antes de sair codando, em vez de implementar por tentativa e erro.
7. **Entregue** o bloco completo da sessão alterada, dizendo **onde colar**.

---

## 🚫 Regras de ouro

- ❌ **Não** reescrever `app.py` inteiro.
- ❌ **Não** reintroduzir leitura de **EXIF** / fallback de GPS pela foto.
- ❌ **Não** distribuir via `file://` (quebra geolocation) — sempre **PWA HTTPS**.
- ✅ **GPS obrigatório** pelo navegador (online e offline); coordenada `0,0` → HTTP 400.
- ✅ **Geofence 2,0 km** (Haversine) por padrão; OS **Muito Alta** trava as menores do grupo (🔒 visível) por padrão. Ambos configuráveis **por coordenação** via tabela `configuracoes_operacionais` (tela "Configurações Operacionais", perfil Administrador) — nunca hardcode um novo valor fixo sem checar se já existe override.
- ✅ Tudo que sobrevive a rerun → `st.session_state`.
- ✅ Responder em **PT-BR**, tom didático, com **onde colar** e **tabela antes/depois** quando ajudar.

---

## 🎨 Apresentação (resumo)

- Editar o **gerador Python** (`gerar_pitch_v11.py`), não o HTML final.
- Paleta **v8/dourado**: `#f3b13c` + cyan `#39d6e8` sobre fundo escuro.
- **9 slides**, sem imagem estática sem FX; **acentuação PT-BR** correta.
- Saída: `SGO_Eletroeletronica_MRS_v11.html` (imagens embutidas em base64). `gerar_pitch_v10.py`/`_v10.html` mantidos como histórico, não editar.

---

## 🌿 Branches

- `main` = produção (redeploya Streamlit Cloud + Render a cada push).
- `dev` = homologação — segundo canal Streamlit Cloud apontando pra essa branch. Features grandes/arriscadas (ex.: Configurações Operacionais) são desenvolvidas e testadas aqui **antes** de ir pra `main`. Sempre confirmar em qual branch está (`git branch --show-current`) antes de commitar.

---

## 📌 Estado atual

- **App:** em produção — painel Streamlit em **Streamlit Community Cloud** (`sgomrs.streamlit.app`, Python 3.12) + API FastAPI em **Render** (`gestao-os-ee-mrs-producao.onrender.com`) · Banco Neon · Storage Supabase. São **duas hospedagens diferentes**, cada push no `main` redeploya as duas.
- **Deck:** v11 concluído (13/07/2026) — atualiza o slide "Motor de Priorização" para o modelo Segurança da Operação e adiciona Configurações Operacionais na arquitetura.
- **Em homologação (`dev`, 13/07/2026):** Configurações Operacionais por coordenação (geofence/trava/escopo/ordem configuráveis, vigência automática) — ainda não promovido para `main`.
- **Pendências:** hospedagem corporativa MRS + SSO/AD (contato: Bruno Capobiango).
