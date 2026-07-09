# 📖 Glossário SGO

## 🚂 Termos operacionais

| Termo | Significado |
|---|---|
| **SGO** | Sistema de Gestão de OS Eletroeletrônica — plataforma de inteligência operacional da malha |
| **OS** | Ordem de Serviço (origem SAP) |
| **Ativo** | Equipamento eletroeletrônico na malha, com coordenadas |
| **Pátio** | Ponto operacional georreferenciado |
| **Malha** | Rede ferroviária MRS |
| **Baixa** | Registro de execução/conclusão da OS |
| **Baixa em massa** | Baixa de várias OS de uma vez (horário único) |
| **CI / SI** | Com Intervalo / Sem Intervalo — filas de priorização independentes |
| **Criticidade_rank** | Ranking de criticidade; **1 = Muito Alta** (trava as menores do grupo) |
| **Grupo** | Chave de priorização = `Ativo × Tipo de Intervalo` |
| **Geofence / Geofencing** | Cerca operacional de **2,0 km** ao redor do ativo |
| **Haversine** | Fórmula de distância entre coordenadas GPS |
| **Roteirização** | Agrupamento/ordenação de OS por proximidade |
| **Raio de atuação** | Distância de busca de OS (inicial **1 km**) |
| **Evidência** | Foto obrigatória da execução |

---

## 🔌 Endpoints da API

| Método | Rota | Função |
|---|---|---|
| `POST` | `/sincronizar_baixa_offline` | Sincroniza baixa feita offline |
| `GET` | `/health` | Healthcheck |
| `POST` | `/publicar_pacote` | Publica pacote da Rota PWA |
| `GET` | `/pacote/{id}` | Abre o pacote 1x online antes do uso offline |

### Campos de `/sincronizar_baixa_offline`
**Obrigatórios:** `os_id`, `ativo_id`, `usuario`, `lat_browser`, `lon_browser`, `data_hora_local`, `horario_inicio`, `horario_fim`, `foto`
**Opcionais:** `acompanhante`, `debug_token`

---

## 🔑 Chaves técnicas

| Chave | Significado |
|---|---|
| `raio_aplicado` / `ativo_aplicado` | Filtro aplicado via botão "Filtrar" (session_state) |
| `df_recomendado` | DataFrame de OS recomendadas (inicia **vazio**) |
| `osGravadasSet` | Conjunto de OS já gravadas (evita duplicidade offline) |
| `AUTH_TOKEN_SECRET` | Segredo do token HMAC de login (`?sid=`, TTL 12 h) |
| `debug_token = "mrs2026"` | Bypass do geofence para teste |
| `#region` / `#endregion` | Delimitadores de seção no código |

---

## 🏢 Siglas MRS / SAP

| Sigla | Significado |
|---|---|
| **SAP** | ERP corporativo — origem das OS |
| **IW47** | Transação SAP de confirmação/retorno das OS |
| **PWA** | Progressive Web App (uso offline no celular) |
| **IndexedDB** | Banco local no navegador (fila offline) |
| **SSO / AD** | Single Sign-On / Active Directory (roadmap curto prazo) |
| **EXIF** | Metadados de foto — **descontinuado** como fonte de GPS |
| **GER. IMPLANT. DE OBRAS (FA)** | Área do Julio na MRS |

---

## 🎨 Termos do deck

| Termo | Significado |
|---|---|
| **v10** | Versão atual do deck (`SGO_Eletroeletronica_MRS_v10.html`) |
| **Paleta v8** | Esquema dourado (`#f3b13c`) + cyan (`#39d6e8`) sobre fundo escuro |
| **Matrix radial** | Grafo de nós (slides "O que é" e "Governança") |
| **Malha pulsante** | Fundo animado de rede (`gmark` / `gpulse`) |
| **Antes / Agora** | Bloco comparativo do slide da malha |
