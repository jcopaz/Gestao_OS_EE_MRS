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
| **Apresentação executiva** (deck v11) | `gerar_pitch_v11.py` | `.claude/agents/pitch-builder.md` |

---

## 🧭 Fluxo de trabalho padrão

1. **Confirme o alvo:** App SGO ou Apresentação v11?
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

## 🌿 Branches e fluxo Git (INEGOCIÁVEL — ver incidente 02–04/09/2026 em `Agente/09_APRENDIZADOS_E_ERROS.md`)

- `main` = produção (redeploya Streamlit Cloud + Render a cada push).
- `dev` = homologação — segundo canal Streamlit Cloud apontando pra essa branch. Features grandes/arriscadas são testadas aqui **antes** de ir pra `main`. Sempre confirmar em qual branch está (`git branch --show-current`) antes de commitar. **Obs.: o `dev` hoje está desatualizado numa linha própria — não usar como referência de "código bom" sem antes reconciliar.**
- ❌ **NUNCA** subir `app.py`/`api.py` inteiro pela opção **"Add files via upload"** da UI web do GitHub (nem colar o arquivo inteiro num editor web). O repo recebe commits de várias origens (web, Copilot, Claude, Streamlit Cloud) e qualquer cópia local desatualiza em dias — um "upload" é um `git checkout` mascarado que **reverte em silêncio** tudo que a cópia não tinha, sem conflito nem aviso. Em 02/09/2026 isso reverteu ~2 meses de trabalho (v16.1→v18.2).
- ✅ Fluxo correto, sempre: `git pull` → editar (patch cirúrgico por `#region`) → `git commit` → `git push`. Alteração pontual direto na web só via edição da linha específica sobre a versão atual, nunca substituindo o arquivo.
- ✅ Commit "Add files via upload" (ou qualquer commit) com **centenas de linhas removidas** = abrir o diff (`git show <sha> --stat` + hunks) antes de confiar.
- ✅ Ao **mergear uma branch que corrige um rollback/regressão em massa**, `git merge` pode reintroduzir a regressão sem conflito (resolve a favor do lado que "mudou" relativo ao ancestral comum). Depois do merge, SEMPRE `git diff <branch-boa> <destino> -- app.py` — tem que dar **vazio** onde deveria; se der linha, `git checkout <branch-boa> -- app.py` antes de fechar o merge.
- ✅ **Tag de "última versão boa conhecida":** `estavel-2026-07-17` (antiga) e **`estavel-2026-09-05` / `v19.0.0`** (atual). Ao primeiro sinal de regressão em massa: `git diff estavel-2026-09-05 HEAD -- app.py`.

---

## 📌 Estado atual (05/09/2026)

- **App:** em produção — painel Streamlit em **Streamlit Community Cloud** (`sgomrs.streamlit.app`, Python 3.12) + API FastAPI em **Render** (`gestao-os-ee-mrs-producao.onrender.com`) · Banco Neon · Storage Supabase. São **duas hospedagens diferentes**, cada push no `main` redeploya as duas.
- **Versão em produção:** **v19.0.x** — reconciliação de 04/09 (base v18.2.0 + correções de datas + parser de Data Inicial Programada + flag da Agenda Mensal) depois do rollback de 02/09. Tag `estavel-2026-09-05`.
- **Configurações Operacionais** por coordenação (geofence/trava/escopo/ordem, vigência automática **+ toggle "sem expiração / novo padrão"**): **em produção**.
- **Deck:** v11 concluído (13/07/2026).
- **Pendências:** hospedagem corporativa MRS + SSO/AD (contato: Bruno Capobiango); `requirements.txt` pina `streamlit==1.32.0` mas o código usa `@st.fragment` (≥1.37) — conferir a versão real e corrigir o pin; branch `dev` desatualizada numa linha própria (reconciliar antes de usar).

---

## 🔒 Segurança do repositório

- Repositório deve ser **PRIVATE**.
- **Nunca commitar** segredos (`AUTH_TOKEN_SECRET`, API Key, string do Neon) nem `usuarios.db`.
- Segredos vêm de variáveis de ambiente / `.env` (fora do Git).
