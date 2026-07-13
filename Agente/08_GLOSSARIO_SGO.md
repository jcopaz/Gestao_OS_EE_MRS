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
| **Geofence / Geofencing** | Cerca operacional — padrão **2,0 km** ao redor do ativo, configurável por coordenação |
| **Haversine** | Fórmula de distância entre coordenadas GPS |
| **Roteirização** | Agrupamento/ordenação de OS por proximidade |
| **Raio de atuação** | Distância de busca de OS (inicial **1 km**) |
| **Evidência** | Foto obrigatória da execução |
| **Segurança da Operação** | Camada composta de priorização: TOP1 (Segurança+Muito Alta) → TOP2 (Confiab.+Seg.+Muito Alta) → TOP3 (Segurança+Alta/Média/Baixa) → TOP4 (demais) |
| **Plano de Guerra** | Cenário operacional excepcional (ex.: Piaçaguera 13/07/2026) que motivou tornar geofence/trava/ordem configuráveis por coordenação |
| **Configurações Operacionais** | Tela admin (aba própria) para ajustar geofence, trava de prioridade, escopo de dados e ordem de critérios por coordenação, com vigência automática |
| **Vigência (vigente_desde / vigente_ate)** | Janela de validade de um override de configuração — fora dela, volta ao padrão sozinho, sem cron |
| **Rateio de HH** | Distribuição proporcional do tempo apontado entre OS baixadas juntas (mesmo horário), conforme o peso do HH planejado de cada uma |

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

## 🛠️ Tabela `configuracoes_operacionais`

| Coluna | Significado |
|---|---|
| `coordenacao` | PK — "Paranapiacaba" ou "Piaçaguera" |
| `geofence_km` | Limite de distância (km); padrão 2,0 |
| `trava_prioridade_ativa` | Liga/desliga o bloqueio de Muito Alta |
| `escopo_dados` | `"todos"` ou o `mes_referencia` exato de um plano (ex.: "Julho/2026") |
| `ordem_criterios` | CSV com a ordem dos critérios (`seguranca_operacional,criticidade,atraso,proximidade` por padrão) |
| `ordem_criticidade` | CSV com a ordem de Muito Alta/Alta/Média/Baixa (padrão nessa ordem) |
| `vigente_desde` / `vigente_ate` | Janela de vigência (data+hora); fora dela, os valores acima são ignorados e o sistema usa o padrão |

Lida por `carregar_config_operacional(coordenacao)` — duplicada em `app.py` e `api.py` (mesmo padrão de duplicação já usado para `COORDENADAS_FIXAS`).

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
| `carregar_config_operacional(coordenacao)` | Lê a config ativa (ou o padrão, se expirada/ausente) — `app.py` e `api.py` |
| `render_tela_config_operacional()` | Página dedicada da tela "Configurações Operacionais" (`tela_atual = "config_operacional"`) |
| `Plano_Mes_Referencia` | Coluna por OS com o "Mês de Referência" do upload (ex.: "Julho/2026"); usada no filtro de Visão Gerencial e no escopo de dados |
| **Perfil "Administrador"** | Novo perfil de usuário; permissão granular `Configurações Operacionais` |

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
| **v11** | Versão atual do deck (`SGO_Eletroeletronica_MRS_v11.html`) — v10 mantido como histórico |
| **Paleta v8** | Esquema dourado (`#f3b13c`) + cyan (`#39d6e8`) sobre fundo escuro |
| **Matrix radial** | Grafo de nós (slides "O que é" e "Governança") |
| **Malha pulsante** | Fundo animado de rede (`gmark` / `gpulse`) |
| **Antes / Agora** | Bloco comparativo do slide da malha |
