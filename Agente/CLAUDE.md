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
- ❌ **NUNCA subir `app.py`/`api.py` inteiro pela opção "Add files via upload" da UI web do GitHub** (nem colar o arquivo todo num editor web). É um `git checkout` mascarado — reverte em silêncio tudo que a cópia local não tinha, sem conflito nem aviso. Em 02/09/2026 reverteu ~2 meses de trabalho (v16.1→v18.2). Fluxo correto SEMPRE: `git pull` → editar (patch por `#region`) → `git commit` → `git push`. Ver incidente completo em `09_APRENDIZADOS_E_ERROS.md`.
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
- `dev` = homologação — segundo canal Streamlit Cloud apontando pra essa branch. Features grandes/arriscadas são testadas aqui **antes** de ir pra `main`. Sempre confirmar em qual branch está (`git branch --show-current`) antes de commitar. **Hoje o `dev` está desatualizado numa linha própria — reconciliar antes de usar como base.**
- **Reconciliação pós-rollback:** ao mergear uma branch que desfaz um rollback, `git merge` pode reintroduzir a regressão sem conflito. Depois do merge: `git diff <branch-boa> <destino> -- app.py` **tem que dar vazio**; se der linha, `git checkout <branch-boa> -- app.py`.
- **Tag de referência de estabilidade:** `estavel-2026-09-05` / `v19.0.0` (a antiga `estavel-2026-07-17` continua no doc). Regressão em massa → `git diff estavel-2026-09-05 HEAD -- app.py`.

---

## 📌 Estado atual (05/09/2026)

- **App:** em produção — painel Streamlit em **Streamlit Community Cloud** (`sgomrs.streamlit.app`, Python 3.12) + API FastAPI em **Render** (`gestao-os-ee-mrs-producao.onrender.com`) · Banco Neon · Storage Supabase. Cada push no `main` redeploya as duas.
- **Versão:** **v19.0.x** (reconciliação de 04/09 após o rollback de 02/09; ver `09_APRENDIZADOS_E_ERROS.md`).
- **Configurações Operacionais** por coordenação (incl. toggle "sem expiração / novo padrão"): **em produção**.
- **Deck:** v11 concluído (13/07/2026).
- **Pendências:** hospedagem corporativa MRS + SSO/AD (Bruno Capobiango); pin `streamlit==1.32.0` no `requirements.txt` vs `@st.fragment` usado no código (≥1.37) — conferir versão real; branch `dev` desatualizada.
