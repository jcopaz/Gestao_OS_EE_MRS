# 🚀 Roadmap

## ✅ Em produção (hoje)

| Capacidade | Status |
|---|---|
| Roteirização por proximidade (Haversine, raio 1 km + Filtrar) | ✅ |
| GPS obrigatório (navegador, EXIF removido) | ✅ |
| PWA Offline (IndexedDB + sync FormData) | ✅ |
| Integração SAP (IW47, baixas em massa) | ✅ |
| Governança (login, perfil, geofence 2 km, evidência foto) | ✅ |
| Priorização Muito Alta (trava menores do grupo) — modelo Segurança da Operação (TOP1-4) | ✅ |
| Motor Antifraude (FastAPI, geofence, rejeição 0,0) | ✅ |
| Rateio proporcional de HH na baixa em massa (export SAP) | ✅ |
| Configurações Operacionais por coordenação (geofence/trava/escopo/ordem, vigência automática) | 🟡 em homologação (`dev`) |

**Hospedagem atual:** Render.

> 🟡 = pronto e validado, mas ainda **não promovido para `main`/produção** — testando em ambiente `dev` (segundo canal Streamlit) antes do merge.

---

## 🔜 Curto prazo

| Item | Descrição |
|---|---|
| **Hospedagem corporativa MRS** | Migrar do Render para ambiente MRS (contato: Bruno Capobiango) |
| **SSO / AD** | Login integrado ao Active Directory corporativo |
| **API corporativa** | Motor antifraude atrás da infra/segurança MRS |

---

## 🔮 Futuro

| Item | Descrição |
|---|---|
| **Multi-Gerência** (Gerência Geral → Gerência → Coordenação) | Expandir de 2 coordenações para ~22. Plano detalhado em `10_PLANO_MULTI_GERENCIA.md` — gatilho concreto: Gerência Vale do Paraíba (Gerência Geral SP) |
| **Inteligência preditiva** | Antecipar falhas/manutenções a partir do histórico |
| **Recomendação automática de rotas** | Sugestão de sequência ótima de execução |
| **Dashboards executivos** | Observabilidade e indicadores de uso |

---

## 🧭 Princípios de evolução

1. **Consolidar antes de expandir** — endurecer o que já está em campo.
2. **Corporativo primeiro** — hospedagem + SSO destravam adoção institucional.
3. **Dados geram inteligência** — o histórico auditável é a base da predição.
4. **Campo no centro** — toda evolução é validada pela realidade da malha.

> ⚠️ **Médio prazo foi removido do deck** (a pedido do Julio, mantido na v11): o slide 8 mostra apenas **Em produção · Curto prazo · Futuro**.
