# 🚂 SGO Eletroeletrônica MRS — Contexto do Agente
## Índice Mestre para o Agente Copilot / Claude

> 📌 **Status atual:** App em produção (Render) ✅ — Apresentação executiva v10 concluída 🎨
> 📅 **Última atualização:** 09/07/2026
> 👤 **Mantenedor:** Julio Cesar de Oliveira Paz
> 🌐 **Distribuição:** PWA em HTTPS (nunca `file://`) · API no Render · Banco Neon

---

## 📂 Arquivos do contexto (leia em ordem)

| # | Arquivo | Conteúdo |
|---|---|---|
| 01 | `01_IDENTIDADE.md` | Quem é o agente, missão e tom |
| 02 | `02_CONTEXTO_USUARIO.md` | Perfil do Julio |
| 03 | `03_HISTORICO_PROJETO.md` | Linha do tempo + conquistas técnicas |
| 04 | `04_ARQUITETURA.md` | Stack, fluxo SAP→Campo→SAP, contrato da API |
| 05 | `05_PADROES_TECNICOS.md` | Regras inegociáveis de código (app.py / api.py / PWA) |
| 06 | `06_PREFERENCIAS_JULIO.md` | Como o Julio gosta de trabalhar |
| 07 | `07_ROADMAP.md` | Em produção · Curto prazo · Futuro |
| 08 | `08_GLOSSARIO_SGO.md` | Termos, endpoints, campos e regras operacionais |

> 🎨 A **apresentação executiva** (deck v10) tem um subagente dedicado:
> `.claude/agents/pitch-builder.md`. O app tem o `.claude/agents/sgo-dev.md`.

---

## 🎯 Como o agente deve agir

### Ao iniciar uma conversa
1. Leia os 8 arquivos de contexto.
2. Confirme o **alvo** da sessão: **App SGO** (`app.py`/`api.py`/PWA) ou **Apresentação v10** (`gerar_pitch_v10.py`).
3. Pergunte por **bloqueios** ou decisões pendentes.
4. Sugira o **próximo passo** mais lógico.

### Ao entregar código (app SGO)
1. **Corrija por sessão** (`#region`/`#endregion`) — nunca reescreva `app.py` inteiro.
2. Indique **onde colar** (sessão exata, ex.: `10.3.3`).
3. Antecipe edge cases (`df_recomendado` vazio, GPS 0,0, rerun/`session_state`).
4. Valide: `py_compile` (app/api) + `node --check` na JS do pacote offline.
5. Entregue o **bloco completo da sessão alterada**.

### Ao entregar a apresentação (deck)
1. Edite o **gerador Python** (`gerar_pitch_v10.py`), não o HTML final.
2. Mantenha a **paleta v10** (dourado `#f3b13c` + cyan `#39d6e8`, fundo escuro).
3. Preserve **acentuação PT-BR** correta.
4. Nada de imagem estática sem FX (spots, sparks, malha pulsante).

### Ao diagnosticar erros
1. Identifique a **causa raiz** antes do fix.
2. Patch **cirúrgico**, não refactor.
3. Documente para não repetir (changelog/guia de correção).

---

## 🚦 Próximo passo imediato
- [ ] Retomar contato TI MRS (hospedagem corporativa / SSO-AD).
- [ ] Evoluções de UX no apontamento de campo.
- [ ] Consolidar dashboards executivos (visibilidade de uso).

---

## 📜 Changelog do agente

| Versão | Data | Mudanças |
|---|---|---|
| 1.0 | 09/07/2026 | Pacote de contexto inicial do SGO (app + apresentação v10) |

---

**🚂 Fim do índice. Bora avançar! ✨**
