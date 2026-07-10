# 🚂 SGO Eletroeletrônica MRS — Guia do Agente (Claude Code / Copilot)

> Ponto de entrada do agente. Este projeto é o **SGO Eletroeletrônica MRS**.
> Repositório: `Gestao_OS_EE_MRS`. Arquivos de contexto ficam na **raiz** do repo.

---

## 📖 Leia antes de agir (raiz do repositório)

1. `00_INDICE.md` — índice mestre
2. `01_IDENTIDADE.md` — quem é o agente, missão e tom
3. `02_CONTEXTO_USUARIO.md` — perfil do Julio
4. `03_HISTORICO_PROJETO.md` — linha do tempo + conquistas
5. `04_ARQUITETURA.md` — stack, fluxo, contrato da API
6. `05_PADROES_TECNICOS.md` — regras inegociáveis
7. `06_PREFERENCIAS_JULIO.md` — estilo de trabalho
8. `07_ROADMAP.md` — em produção / curto prazo / futuro
9. `08_GLOSSARIO_SGO.md` — termos, endpoints, campos

Código-fonte real no repo: **`app.py`** (painel Streamlit) e **`api.py`** (motor FastAPI).

---

## 🎯 Missão

O SGO **não é um apontador de OS** — é um **mecanismo de decisão operacional**
aplicado à malha ferroviária MRS, conectando SAP, ativos, geolocalização,
execução em campo, evidências e governança.

Duas frentes de trabalho:

| Frente | Arquivos | Subagente |
|---|---|---|
| **App SGO** (execução em campo) | `app.py`, `api.py`, PWA offline | `.claude/agents/sgo-dev.md` |
| **Apresentação executiva** (deck v10) | `gerar_pitch_v10.py` | `.claude/agents/pitch-builder.md` |

---

## 🧭 Fluxo de trabalho padrão

1. **Confirme o alvo:** App SGO ou Apresentação v10?
2. **Investigue a estrutura** (o bloco/`#region` atual) antes de propor lógica.
3. **Patch cirúrgico** — corrija **por sessão**, nunca reescreva o arquivo inteiro.
4. **Valide:** `python -m py_compile app.py api.py` + `node --check` na JS do PWA.
5. **Entregue** o bloco completo da sessão alterada, dizendo **onde colar**.

---

## 🚫 Regras de ouro

- ❌ **Não** reescrever `app.py` inteiro.
- ❌ **Não** reintroduzir leitura de **EXIF** / fallback de GPS pela foto.
- ❌ **Não** distribuir via `file://` (quebra geolocation) — sempre **PWA HTTPS**.
- ✅ **GPS obrigatório** pelo navegador (online e offline); coordenada `0,0` → HTTP 400.
- ✅ **Geofence 2,0 km** (Haversine); OS **Muito Alta** trava as menores do grupo (🔒 visível).
- ✅ Tudo que sobrevive a rerun → `st.session_state`.
- ✅ Responder em **PT-BR**, tom didático, com **onde colar** e **tabela antes/depois** quando ajudar.

---

## 🎨 Apresentação (resumo)

- Editar o **gerador Python** (`gerar_pitch_v10.py`), não o HTML final.
- Paleta **v8/dourado**: `#f3b13c` + cyan `#39d6e8` sobre fundo escuro.
- **9 slides**, sem imagem estática sem FX; **acentuação PT-BR** correta.
- Saída: `SGO_Eletroeletronica_MRS_v10.html` (imagens embutidas em base64).

---

## 📌 Estado atual

- **App:** em produção — painel Streamlit em **Streamlit Community Cloud** (`sgomrs.streamlit.app`, Python 3.12) + API FastAPI em **Render** (`gestao-os-ee-mrs-producao.onrender.com`) · Banco Neon · Storage Supabase. São **duas hospedagens diferentes**, cada push no `main` redeploya as duas.
- **Deck:** v10 concluído.
- **Pendências:** hospedagem corporativa MRS + SSO/AD (contato: Bruno Capobiango).

---

## 🔒 Segurança do repositório

- Repositório deve ser **PRIVATE**.
- **Nunca commitar** segredos (`AUTH_TOKEN_SECRET`, API Key, string do Neon) nem `usuarios.db`.
- Segredos vêm de variáveis de ambiente / `.env` (fora do Git).
