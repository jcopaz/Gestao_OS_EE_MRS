# 🚂 SGO Eletroeletrônica MRS

> **Inteligência Operacional Aplicada à Malha**
> Plataforma que conecta **SAP, ativos ferroviários, geolocalização, execução em campo, evidências e governança** em uma única camada digital.

O SGO **não é um apontador de OS** — é um **mecanismo de decisão operacional**: organiza a execução, prioriza críticas, roteiriza por proximidade, controla aderência, registra evidências e integra o retorno ao SAP.

---

## ✨ Principais capacidades

| Capacidade | Descrição |
|---|---|
| 🗺️ **Roteirização** | Agrupamento de OS por proximidade (Haversine), raio inicial de 1 km + botão *Filtrar* |
| 🎯 **Priorização** | OS *Muito Alta* trava as menores do mesmo grupo (Ativo × Tipo de Intervalo) |
| 🛰️ **GPS obrigatório** | Validação pelo hardware do aparelho (navegador), geofencing de 2,0 km |
| 📷 **Evidência fotográfica** | Foto obrigatória por baixa, com usuário/data/hora/localização |
| 📴 **PWA Offline** | Opera sem sinal (IndexedDB), sincroniza depois, sem duplicidade |
| 🔐 **Governança** | Login controlado, perfil de acesso, rejeição de coordenada `0,0` |
| 🔄 **Integração SAP** | Retorno via IW47 e baixas em massa |

---

## 🔄 Fluxo ponta a ponta

```
SAP  →  Motor SGO  →  Campo  →  Banco / Evidências  →  Retorno SAP
```

| Etapa | O que faz |
|---|---|
| **SAP** | OS programadas + plano de manutenção |
| **Motor SGO** | Priorização, regras, geografia, governança |
| **Campo** | GPS, foto, modo offline, baixa da OS |
| **Banco / Evidências** | Histórico auditável + storage de fotos |
| **Retorno SAP** | IW47, baixas em massa, dados estruturados |

---

## 💻 Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Frontend / Painel | Streamlit (+ ECharts, Folium) |
| Motor Antifraude / API | FastAPI (Render) |
| Banco de dados | PostgreSQL (Neon) |
| Storage de fotos | Supabase Storage |
| Modo Offline | PWA + IndexedDB |
| Segurança | HTTPS + API Key · token HMAC na URL |
| Geolocalização | GPS HTML5 + Haversine |
| ERP | SAP / IW47 |

> ⚠️ Distribuído como **PWA em HTTPS — nunca `file://`** (o navegador bloqueia geolocation).

---

## 📂 Estrutura do repositório

```
.
├── app.py                              # Painel Streamlit (execução em campo)
├── api.py                              # Motor Antifraude (FastAPI)
├── gerar_pitch_v10.py                  # Gerador da apresentação executiva
├── SGO_Eletroeletronica_MRS_v10.html   # Apresentação (deck v10, standalone)
├── Agente/                             # Pacote de contexto para agentes de IA
│   ├── CLAUDE.md                       #   → ponto de entrada do agente
│   ├── 00_INDICE.md ... 08_GLOSSARIO_SGO.md
│   └── .claude/agents/                 #   → subagentes (sgo-dev, pitch-builder)
└── README.md
```

---

## 🎬 Apresentação executiva (deck v10)

Deck HTML5 premium (escuro/tech, paleta dourada), usado como **abertura antes da demonstração ao vivo**.

```bash
# Gera o HTML standalone (imagens embutidas em base64)
python gerar_pitch_v10.py
# Saída: SGO_Eletroeletronica_MRS_v10.html  → abrir no navegador (F11 fullscreen)
```

**Dependências do gerador:** `pip install pillow numpy`

**9 slides:** Capa → Problema → O que é o SGO → Fluxo → Inteligência na malha → Priorização → Governança → Arquitetura & Roadmap → Ponte para a demo.

---

## 🤖 Pasta `Agente/` — contexto para IA (Claude Code / Copilot)

Pacote de contexto que ensina um agente de IA a trabalhar neste projeto seguindo os padrões corretos.

**Como usar no VS Code:**
1. Copie `Agente/CLAUDE.md` para a **raiz** (ou renomeie para `.github/copilot-instructions.md` no Copilot).
2. Abra o **Claude Code** no repositório — ele lê o `CLAUDE.md` e carrega os subagentes automaticamente:
   - `sgo-dev` — desenvolvimento do app (Streamlit / FastAPI / PWA)
   - `pitch-builder` — ajustes na apresentação v10

---

## 🚀 Roadmap

| Fase | Itens |
|---|---|
| ✅ **Em produção** | Roteirização · GPS obrigatório · PWA Offline · SAP · Governança · Priorização |
| 🔜 **Curto prazo** | Hospedagem corporativa MRS · SSO/AD · API corporativa |
| 🔮 **Futuro** | Inteligência preditiva · Recomendação automática de rotas · Dashboards executivos |

---

## ⚙️ Regras de desenvolvimento (resumo)

- Corrigir **por sessão** (`#region` / `#endregion`) — nunca reescrever `app.py` inteiro.
- **GPS somente do navegador** — coordenada `0,0` é rejeitada (HTTP 400). Não usar EXIF.
- Tudo que sobrevive a rerun → `st.session_state`.
- Validar: `python -m py_compile app.py api.py` + `node --check` na JS do pacote offline.

> 📘 Detalhes completos em [`Agente/`](Agente/).

---

<div align="center">

**MRS Logística S.A.** · Gerência de Implantação de Obras
*A camada digital entre planejamento, malha, campo, governança e SAP.*

</div>
