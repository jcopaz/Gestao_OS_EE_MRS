# 📚 Aprendizado x Erros Cometidos

> Histórico consolidado de bugs, incidentes e decisões erradas do SGO Eletroeletrônica MRS,
> com causa raiz e a lição pra não repetir. Ordem cronológica. Ler antes de propor qualquer
> mudança em área já listada aqui — o mesmo tipo de erro já custou tempo real da equipe de
> campo mais de uma vez.

> ✅ **Ponto de referência de estabilidade:** commit `7beb220` / tag git `estavel-2026-07-17` —
> confirmado pelo Julio sem nenhum imprevisto de 16/07 para 17/07/2026, depois da regressão
> grave do upload de fotos (ver abaixo). Se uma mudança futura quebrar algo, comparar contra
> esse ponto (`git diff estavel-2026-07-17 -- app.py api.py`) antes de qualquer outra
> investigação.

---

## 09-11/07/2026 — Contaminação de baixas entre ciclos (Backlog zerado)

**O que aconteceu:** filtro de "Período de Execução" na Visão Gerencial fazia a Taxa de Execução parecer 100% (Backlog zerado), escondendo OS pendentes de verdade.

**Causa raiz (dupla):** (1) máscara de execução sem `| isna()` descartava pendentes sem data; (2) **causa real**: SAP reaproveita número de OS ao reprogramar — a baixa antiga (de um ciclo anterior) "grudava" na OS do novo ciclo via merge por `Ordem servico`, fazendo o sistema achar que já estava concluída.

**Correção:** validar `realizado_em >= data_upload` do ciclo vigente antes de aplicar a baixa no overlay. Confirmado com 3736 OS afetadas via SQL direto no Neon antes de aplicar o fix.

**Aprendizado:** quando um bug "parece corrigido" no código mas o sintoma persiste, não presumir que é só cache/deploy — pode ter uma causa mais profunda no dado. **Sempre validar hipótese de causa raiz com query SQL real antes de aplicar o patch**, principalmente quando envolve dado já em produção.

---

## 10/07/2026 — Geofence fail-open (Guarulhos → concluiu OS em pátio no interior)

**O que aconteceu:** teste real mostrou que era possível concluir uma OS estando fisicamente longe do ativo (baixa feita em Guarulhos foi aceita para um pátio em outra região).

**Causa raiz (dupla):** (1) lookup de coordenada usava `Ativo[:3]` em vez da coluna `Patio` já resolvida; (2) **design fail-open** — quando a OS/pátio não era resolvido, o código dava `continue` e liberava a baixa em vez de bloquear.

**Correção:** usar `Patio` já resolvido, e tornar a validação **fail-closed** — bloquear sempre que não for possível confirmar a localização, nunca liberar por padrão.

**Aprendizado:** em qualquer validação de segurança/antifraude (geofence, foto obrigatória, GPS), revisar explicitamente o caminho de "dado não resolvido". Código que pula a checagem quando não consegue resolver um valor é uma falha de segurança silenciosa. **Sempre fail-closed nesse tipo de regra.**

---

## 10/07/2026 — Segmentation fault após reboot no Streamlit Cloud

**O que aconteceu:** app caiu com `Segmentation fault` depois de um reboot manual, sem nenhuma mudança de código.

**Causa raiz:** `requirements.txt` sem pin de versão — o reboot puxou `numpy 2.x` (quebra binária com libs geoespaciais) e depois `geopandas<1.0` puxou `fiona`/GDAL nativo indisponível no build do Streamlit Cloud.

**Correção:** travar versões no `requirements.txt`, migrar pra `geopandas>=1.0` (usa `pyogrio`, sem dependência nativa GDAL), fixar Python em 3.12 nas Settings do Streamlit Cloud (estava em 3.14, sem wheels prontas).

**Aprendizado:** dependências sem pin são uma bomba-relógio em plataformas gerenciadas — um reboot trivial pode mudar o ambiente inteiro sem nenhum push de código. **Sempre pinar versões**, principalmente de libs com dependência binária nativa.

---

## 13/07/2026 — PWA offline: OS sincronizada reaparecia na lista

**O que aconteceu:** OS já sincronizada com sucesso (confirmada no banco) continuava aparecendo na lista "Sua Rota Offline" do celular.

**Causa raiz:** botão "Limpar Filas e Reiniciar" apagava **todo** o IndexedDB (`store.clear()`), inclusive os registros `status_sync: "sincronizado"` que sustentam a exclusão da OS da lista.

**Correção:** apagar só os registros com `status_sync === "pendente"` via cursor no índice, preservando o histórico de sincronizadas.

**Aprendizado:** "limpar tudo" é sempre mais arriscado do que parece — checar se a ação genérica não está destruindo estado que outra parte do sistema depende para funcionar corretamente.

---

## 13/07/2026 — Trab. real errado no export SAP + duplicação de HH

**O que aconteceu:** campo "Trab. real" saía errado no Excel de baixa em massa (3 horas viravam "3 minutos" no SAP); e quando várias OS eram baixadas juntas, cada uma recebia o tempo **cheio**, duplicando/triplicando o HH reportado.

**Causa raiz:** (1) formatação como texto `"HH,MM"` que o SAP interpretava como minutos decimais; (2) nenhuma lógica de rateio existia — o tempo total apontado era creditado integralmente em cada OS do grupo.

**Correção:** sair em minutos inteiros totais; implementar rateio proporcional ao HH planejado (`Hxh Plano`) de cada OS, com ajuste por maior resto pra soma bater exatamente com o total apontado.

**Aprendizado:** ao lidar com exportação pra sistema externo (SAP), validar o **formato exato** esperado do outro lado, não só "parece certo" no nosso sistema. E qualquer operação em lote que distribui um valor entre múltiplos registros precisa de lógica de rateio explícita — o padrão ingênuo (creditar tudo em todos) sempre duplica.

---

## 13/07/2026 — Deploy de Configurações Operacionais sem teste end-to-end

**O que aconteceu:** a feature "Configurações Operacionais" (geofence/trava/escopo/ordem configuráveis por coordenação) foi commitada direto na `main` depois de só testes de lógica isolada (51/51 passando) — sem teste visual num navegador real, porque o ambiente `dev` teve problemas de infraestrutura (Neon suspenso, depois senha errada) que impediram validação a tempo.

**O que ficou pendente:** o modelo de priorização "Segurança da Operação" virou o **padrão pra todo mundo** imediatamente, sem ninguém precisar configurar nada — mudança de comportamento real em produção, não um opt-in.

**Aprendizado:** testes de lógica isolada (unit tests) validam a matemática, não a experiência real. Quando o ambiente de teste (`dev`) está indisponível, a decisão de "ir direto pra produção mesmo assim" precisa ser explícita e consciente — e o pós-deploy precisa de um checklist de verificação visual imediato, não só confiar que "os testes passaram".

---

## 13-14/07/2026 — "OS baixada não sai do Cronograma": 3 causas raiz em sequência

Esse foi o incidente mais longo de investigação da noite — vale ler os 3 passos completos.

**Sintoma:** OS já baixada (com foto, status, GPS confirmados no banco) continuava aparecendo como pendente no Cronograma de Execução / Roteirização.

**Tentativa 1 (real, mas insuficiente):** `_hash_baixas()` usava `MAX(realizado_em)`, uma coluna **VARCHAR** ("DD/MM/AAAA HH:MM") — `MAX()` em texto compara alfabeticamente, não por data. Uma baixa nova com dia menor (ex. dia 13) não superava um dia maior já no banco (ex. dia 23 de um ciclo anterior), o cache não invalidava. **Fix:** nova coluna `atualizado_em` (TIMESTAMP real) para decidir quando o cache precisa recarregar.

**Tentativa 2 (real, mas ainda não era a causa deste caso):** fluxo offline gravava `coordenacao="Sincronização Offline"` (texto fixo) em vez da coordenação real da OS — quebrava filtro de escopo pra usuários não-"Todas". **Fix:** usar a coordenação real já calculada no mesmo endpoint.

**Causa raiz real (3ª tentativa):** validação via SQL simulando a lógica inteira (merge + ciclo + escopo) mostrou que **tudo batia** nos dados — o problema era um **filtro redundante** em `aplicar_overlay_baixas`: `df_baixas` era filtrado de novo por texto de coordenação, mesmo o `df_base` já vindo escopado por coordenação e o merge sendo por `Ordem servico` (chave única). Esse filtro extra só existia pra causar falso-negativo por qualquer diferença de texto. **Fix definitivo:** remover o filtro por completo.

**Aprendizado:**
1. As duas primeiras correções eram bugs reais e válidos — vale corrigi-los mesmo que não resolvam o sintoma investigado no momento.
2. Um filtro "de segurança extra" que duplica uma responsabilidade já garantida em outro lugar do código tende a virar fonte de bug silencioso. Sempre perguntar: **"esse filtro protege contra algo que não seria pego de outro jeito?"** antes de mantê-lo.
3. Ao investigar "dado existe no banco mas não aparece pro usuário", suspeitar de filtros redundantes de escopo/permissão baseados em comparação de texto — não só de cache ou lógica de negócio (ciclo, status).
4. Checar **todos** os campos usados em filtros de escopo/permissão (não só os campos "de negócio" óbvios) quando um dado "some" só para alguns usuários.

---

## 14/07/2026 — Evidência fotográfica sendo sobrescrita entre OS diferentes

**O que aconteceu:** reportado como "PWA permite baixa em massa sem foto" — na real, a foto sempre foi enviada, mas sumia depois.

**Causa raiz:** tabela `evidencias` usava `UNIQUE(ativo, atividade)` como chave de upsert, em vez de `os_referencia`. Toda vez que duas execuções caíam no mesmo ativo+atividade, a foto mais recente sobrescrevia o registro (e, no fluxo online, até o **arquivo físico** no Supabase Storage) da anterior. No offline, isso acontecia sempre, porque o `atividade` era gravado como texto fixo `"Baixa Offline"` — colisão garantida em qualquer baixa em massa no mesmo ativo.

**Correção:** nova constraint `UNIQUE(os_referencia)`; nome do arquivo no Supabase passou a incluir o número da OS.

**Limitação:** evidências já perdidas antes do fix **não são recuperáveis**.

**Aprendizado:** ao desenhar a chave de conflito (`ON CONFLICT`) de qualquer tabela ligada a uma execução específica, usar sempre o identificador único de verdade (aqui, a OS) — nunca uma combinação de campos "descritivos" (ativo, atividade, tipo) que podem legitimamente se repetir entre execuções diferentes.

---

## 15/07/2026 — Coordenadas de pátio desalinhadas (geofence rejeitando baixa legítima)

**O que aconteceu:** técnico relatou ter que se deslocar até um "ponto de referência" impreciso do pátio (IQA) para conseguir dar baixa — o ponto salvo em `COORDENADAS_FIXAS` ficava a vários km do local real de trabalho.

**Correção:** centralização manual das coordenadas de 6 pátios (IAA, IBA, IQA, IQB, ISN, ZPG).

**Aprendizado:** dado de geolocalização "fixo no código" (`COORDENADAS_FIXAS`) é fácil de esquecer que precisa de manutenção — pátios grandes/dispersos podem ter o ponto de referência capturado uma vez e nunca mais revisado. Vale um canal claro pra equipe reportar imprecisão desse tipo (e priorizar rápido, já que impacta diretamente a capacidade de dar baixa).

---

## 15/07/2026 — Upload de foto: ClientDisconnect em rede de campo fraca

**O que aconteceu:** erro de tela branca "Huh... Code 1ST" durante upload de foto, derrubando a sessão e voltando pra tela de login.

**Causa raiz:** ao selecionar foto pra várias OS ao mesmo tempo (baixa em massa), o app tentava enviar tudo simultaneamente — numa rede de campo instável, isso aumentava a chance da conexão cair no meio de um dos envios (`ClientDisconnect` nos logs do Streamlit Cloud).

**Aprendizado:** ao investigar um erro genérico de infraestrutura ("Huh", "no response from server"), sempre puxar os **logs reais** da plataforma antes de assumir causa (nesse caso, cheguei a suspeitar erroneamente de estouro de memória antes de achar o `ClientDisconnect` real no log).

---

## 15-16/07/2026 — Regressão grave: fix do upload de foto causou PERDA REAL DE OS

Esse foi o incidente mais sério da noite — merece destaque próprio.

**O que aconteceu:** para resolver o `ClientDisconnect` acima, a primeira correção escondia da tela o `st.file_uploader` das OS já com foto pronta, liberando o campo da próxima uma de cada vez. Foi escolhida deliberadamente como "a opção segura" (em vez de interceptar o componente via JavaScript, que já era reconhecido como arriscado sem poder testar em dispositivo real) — mas foi pra produção **sem teste em dispositivo real** mesmo assim.

**Causa raiz real:** `st.file_uploader` do Streamlit **só mantém o arquivo carregado de forma confiável se o widget for renderizado em todo rerun do script**. Ao esconder o widget de uma OS já pronta, o Streamlit esquecia o arquivo já enviado — a foto sumia e a OS voltava a pedir upload do zero, às vezes só na hora de clicar "Concluir e Gravar", **sem nenhuma mensagem de erro**. Resultado: a equipe de campo perdeu um dia inteiro tentando gravar OS que nunca salvavam de fato.

**Correção definitiva:** reverter para todos os campos sempre visíveis, depois reimplementar o sequenciamento usando `disabled=True` (parâmetro oficial do widget) em vez de esconder — o widget nunca deixa de ser renderizado, só fica temporariamente não-interativo.

**Aprendizado (o mais importante do documento):**
1. **"Usar uma API oficial/documentada" não é sinônimo de "seguro sem teste".** O risco não estava no `st.file_uploader` em si, mas no *padrão de uso* (renderização condicional de um widget stateful entre reruns) — um comportamento que só um teste real revela, não a leitura da documentação.
2. Mudanças que alteram **quando/se um widget é renderizado** entre reruns merecem o mesmo nível de cautela que código não-documentado/hack de JavaScript.
3. Preferir sempre soluções que **nunca tirem o widget da árvore de renderização** (ex.: `disabled=True`) a soluções que condicionalmente criam/removem o widget.
4. Ao investigar um bug reportado logo após um deploy recente, ir direto pro **diff do último commit relevante** antes de considerar outras teorias — a causa raiz normalmente está na mudança mais recente daquele fluxo exato.
5. Zero baixas no dia inteiro (ambas coordenações) foi o sinal de alerta que deveria ter acelerado a investigação — métricas agregadas zeradas/anômalas merecem prioridade máxima de investigação, mesmo sem um erro explícito reportado ainda.

---

## 20-21/07/2026 — Baixa em massa (IPA/Paranapiacaba) some do SGO: 2 causas raiz

**Sintoma:** ~10 mil linhas de baixa manual (import IW47) não refletiam no Dashboard/Roteirização. Hipótese inicial do Julio (matrícula de funcionário desligado) foi descartada — matrícula é texto livre, nunca validada contra `usuarios`.

**Causa raiz 1:** `aplicar_overlay_baixas` bloqueava baixa cujo `realizado_em` fosse anterior ao `data_upload` do ciclo vigente (proteção contra baixa "grudada" de ciclo antigo, ver incidente de 09-11/07). Baixa administrativa em lote tem data de execução real do SAP, quase sempre anterior ao upload do plano no SGO — 2.629 de 3.810 baixas (69%) ficavam escondidas por essa checagem.

**Causa raiz 2:** `_coord_por_centro_trabalho` usava `"IPG" in centro` (substring solta) em vez de prefixo exato — linhas de Paranapiacaba/IPA eram classificadas como "Piaçaguera", quebrando o filtro de escopo.

**Correção:** baixas com origem administrativa (`geolocalizacao_baixa` em `{"Baixa IW47", "Importação IW47", "Baixa Manual"}`) pulam a checagem de ciclo — GPS real do app de campo continua protegido por essa mesma checagem. `_coord_por_centro_trabalho` passou a usar `centro.startswith("E.SP.IPG"/"E.SP.IPA")`, igual ao padrão já usado em outros pontos do código.

**Aprendizado:** uma proteção pensada pra um cenário (GPS de campo) pode silenciosamente quebrar outro cenário legítimo (import administrativo em lote) que usa o mesmo caminho de código — ao adicionar uma trava anti-fraude/anti-contaminação, mapear explicitamente **todas** as origens de dado que passam por ali, não só a que motivou a trava. E **nunca usar substring solta (`"X" in campo`) pra decidir coordenação/escopo** — sempre prefixo/valor exato, para não capturar falsos positivos de outro centro de trabalho com nome parecido.

---

## 22/07/2026 — Grupo de Ativo veio sem nenhuma opção (filtro "vazio")

**O que aconteceu:** filtro novo "Grupo de Ativo" na sidebar não mostrava nenhuma opção pra selecionar, embora a regex de extração (`extrair_grupo_ativo`) estivesse correta (validada contra dado real do Neon).

**Causa raiz:** `ETL_VERSION` (usado como parte da chave do `@st.cache_data` de `carregar_base_sem_overlay`) não foi incrementado depois de adicionar a coluna `Grupo_Ativo` ao dataframe — o cache antigo (sem a coluna) continuava sendo servido.

**Aprendizado:** **toda vez que uma coluna nova é adicionada a uma função `@st.cache_data`, incrementar a constante de versão do cache** (`ETL_VERSION`) no mesmo commit — não só quando a lógica de negócio muda. Adicionar coluna é mudança de shape do dado, e o cache não sabe disso sozinho.

---

## 22/07/2026 — Botão "Limpar Filtros" derrubava o app inteiro

**O que aconteceu:** clicar em "Limpar Filtros" gerava `StreamlitAPIException` e quebrava a tela inteira.

**Causa raiz:** o botão tentava escrever em `st.session_state[key]` para chaves de widgets (`filtro_mes_referencia`, `filtro_patios` etc.) que **já tinham sido instanciados** mais cedo no mesmo rerun — Streamlit proíbe essa escrita depois que o widget dono da chave já foi criado na mesma execução.

**Correção:** padrão de duas fases — o botão só marca uma flag (`st.session_state["_solicitar_reset_filtros"] = True`) e chama `st.rerun()`; um bloco no **topo** da função do fragmento, antes de qualquer widget ser criado, consome a flag e só então escreve os valores padrão.

**Aprendizado:** em Streamlit, **nunca escrever em `session_state` de uma key de widget depois que o widget já foi desenhado no mesmo rerun** — qualquer "resetar filtro"/"limpar formulário" precisa do padrão flag+rerun, escrevendo o valor padrão *antes* da instanciação do widget no próximo rerun.

---

## 22/07/2026 — Aba de Governança travava/não carregava após digitar a senha

**O que aconteceu:** depois de um refactor que extraiu duas queries inline em funções `@st.cache_data` (`_carregar_baixas_logs_governanca`, `_carregar_usuarios_nome_governanca`), a aba de Governança parou de carregar após a autenticação por senha.

**Causa raiz:** as duas novas funções foram inseridas na **coluna 0** (indentação zero), o que fechou silenciosamente o `if st.session_state.get("tela_atual") == "governanca":` que envolvia todo o bloco. O trecho seguinte (`with st.spinner(...)`, que monta o `df_gov` via merge/cálculo) ficou com a **mesma indentação** (4 espaços) do corpo da segunda função — o Python não tem como saber que essa linha deveria "sair" da função e voltar pro bloco do `if`; ela virou código morto dentro da função, nunca executado. `df_gov` nunca era definido, e o `fragmento_governanca()` quebrava ao tentar usá-lo.

**Correção:** reindentar as duas funções pra dentro do bloco (nível 4/8), fazendo o dedent de 8→4 no `with st.spinner` fechar corretamente a função e retomar o corpo do `if`.

**Aprendizado:** esse é um bug **silencioso** — `python -m py_compile` passa limpo, porque o código é sintaticamente válido, só que a *estrutura lógica* mudou (uma variável que devia ser definida sempre passou a nunca ser definida). Ao extrair código inline pra uma função nova (refactor "cirúrgico"), **conferir a indentação de tudo que vem depois da extração**, não só do trecho extraído — um novo `def` no meio de um bloco pode fechar esse bloco sem nenhum erro de sintaxe. Vale considerar rodar o app localmente (ou pelo menos revisar a indentação linha a linha do trecho seguinte) antes de confiar só no `py_compile` para mudanças desse tipo.

---

## 27/07/2026 — Geofence offline rejeitava tecnico fisicamente no patio certo

**O que aconteceu:** Julio reportou (apontamento de campo em 22/07/2026, OS
23605108) que a sincronização offline rejeitou a baixa com "Bloqueio
Geográfico: 17,9km do ativo (limite 2,0km)" — no mesmo instante, o fluxo
**online** autorizou normal, com ele fisicamente no local.

**Causa raiz:** a resolução de pátio do ativo em `api.py` só olhava os 3
primeiros caracteres do nome (`COORDENADAS_FIXAS.get(ativo_id[:3])`).
Funciona pra ativos tipo `IPA_326_N1`, mas o ativo do incidente era
`MF-SJU-ISN_ISN-TELECOM-ARCCCO5` — o código real do pátio (`ISN`) não está
no início do nome. A versão fail-closed (corrigida horas antes, na mesma
sessão) bloqueava certo nesse caso — mas ainda deixava o técnico travado,
porque nunca *encontrava* o pátio certo pra validar contra ele.

**Correção:** `resolver_patio_ativo()` (nova, `api.py`) tenta prefixo E
busca do código em qualquer parte do nome do ativo antes de falhar —
mesma lógica que `_resolver_patio()` já usa com sucesso no `app.py` desde
sempre (por isso o fluxo online nunca teve esse problema). Confirmado com
matemática: GPS capturado no campo → 1,48km do pátio real (ISN, dentro do
limite) vs. 17,93km de Paranapiacaba (fallback antigo já removido) — bate
com o erro reportado (17,9km).

**Aprendizado:** `app.py` e `api.py` tinham **duas implementações
diferentes** da mesma resolução de pátio — uma robusta (`_resolver_patio`,
com fallback de busca por substring) e outra simplificada
(`ativo_id[:3]`), porque são hospedagens/deploys separados sem código
compartilhado. Ao corrigir um bug de segurança num dos dois lados (o
fail-closed do geofence, mais cedo no mesmo dia), **conferir se o outro
lado tem a mesma robustez** antes de considerar o problema resolvido —
"parar de aceitar dado errado" e "conseguir resolver o dado certo" são
duas correções diferentes, e só a primeira não basta pro usuário final.

---

## 27/07/2026 — Endpoint de limpeza de órfãos: 2 bugs + 55 evidências reais recuperadas

Primeira execução real do `/limpar_evidencias_orfas` (endpoint criado nesta mesma sessão, nunca tinha rodado em produção) — vale ler os 3 achados em sequência.

**Achado 1 (bug, 500 em toda chamada):** a listagem do Supabase Storage (`POST /storage/v1/object/list/{bucket}`) exige o campo `"prefix"` no corpo, mesmo vazio. Faltava — toda chamada retornava 400 do Supabase, virando 500 sem tratamento (`resp_list.raise_for_status()` sem try/except). **Correção:** adicionar `"prefix": ""` ao payload.

**Achado 2 (bug de classificação, não de exclusão):** o regex `_OS(\d+)_` exigia `_` depois do número — arquivos com o número da OS colado direto na extensão (`..._OS23254048.jpg`, sem `_` antes do `.jpg`) caíam incorretamente em "sem_os_identificavel" em vez de serem cruzados contra o banco. Revisão manual da amostra completa achou 9 desses 26 casos. **Correção:** `_OS(\d+)` sem exigir o `_` final (`\d+` já para sozinho no primeiro caractere não-numérico).

**Achado 3 (não é bug, é resultado real da investigação):** cruzando os arquivos órfãos classificados como "revisar_manualmente" (órfão de OS que hoje não tem NENHUMA evidência) contra `baixas`, 55 das 62 OS tinham baixa **"Realizado"** de verdade, com técnico e data reais — a foto existia no Storage, só tinha perdido o vínculo no banco (mesma família do incidente de 14/07, mas por falha silenciosa de escrita, não por sobrescrita de chave). Recuperadas com `INSERT ... ON CONFLICT (os_referencia) DO NOTHING`, reconstruindo `ativo`/`atividade` a partir do nome do arquivo (2 convenções diferentes: `{ativo}_OS{num}_{timestamp}.jpg` no fluxo offline, `{ativo}__{atividade}__OS{num}.jpg` no online) e `geolocalizacao`/`concluido_por` a partir do `baixas` da mesma OS. Os 7 casos restantes (sem baixa registrada) e os 18 sem número de OS identificável no nome ficaram como estão — sem dado suficiente pra justificar ação automática.

**Correção adicional (confiança antes de apagar em massa):** antes de autorizar a exclusão real dos ~1.400 arquivos "seguro_apagar", Julio pediu prova de que cada um tem mesmo uma foto atual substituindo — não bastava confiar na classificação (mesmo endpoint já tinha 2 bugs achados na mesma sessão). O endpoint passou a devolver, por item, a `foto_url` atual vinculada à mesma OS (`seguro_apagar_com_prova`), e não só a contagem.

**Aprendizado:**
1. Endpoint novo, primeira execução real == melhor hora pra pedir prova em vez de confiar na lógica, mesmo que pareça óbvia. Os 2 bugs (Achados 1 e 2) só apareceram rodando contra dado real, nunca em `py_compile`/teste isolado.
2. "Classificado como precisa de revisão manual" não é o fim da investigação — cruzar contra o dado de negócio (aqui, `baixas`) pode transformar uma faxina de storage numa recuperação real de evidência de auditoria.
3. Resposta de API muito grande (aqui, >200KB numa lista) pode truncar silenciosamente na renderização/cópia do navegador (GitHub Actions log) sem nenhum erro visível — campos pequenos e importantes devem vir primeiro no JSON, não por último.
4. Ao reconstruir um dado perdido, usar sempre a fonte mais primária disponível (aqui, o nome do arquivo e o registro de `baixas` já existente) em vez de aproximar — os dois vinham da mesma variável/mesmo request originalmente, então a reconstrução é exata, não uma estimativa.

---

## 21/08/2026 — App caiu por estouro de memória no Streamlit Cloud (cache sem limite) + 2 achados de segurança (cópia da aplicação)

**O que aconteceu:** `sgomrs.streamlit.app` caiu com "This app has gone over its resource limits. It's using too much memory!" em produção. Julio deu reboot manual e o app voltou. Pediu análise completa do `app.py` pra evitar recorrência, e depois pediu também uma checagem de vulnerabilidade que permitisse alguém copiar a aplicação.

**Causa raiz (memória):** vários `@st.cache_data`/`@st.cache_resource` sem `ttl` nem `max_entries`, com chave de cache que muda toda vez que qualquer usuário registra uma baixa de OS (`df_base`/`df_base_cal`/`df_pendentes_f`, todos derivados da base com overlay) ou faz uma busca de rota (`lat_origem`/`lon_origem` em `_construir_mapa_navegacao`). Sem limite, cada mudança deixava mais uma cópia inteira do resultado presa na RAM do processo compartilhado — nunca liberada, até estourar. O pior caso era `_construir_mapa_navegacao`: `cache_resource` guarda o objeto `folium.Map` de verdade (não serializado, mais pesado que um DataFrame cacheado), então cada busca de endereço/GPS de qualquer usuário deixava um mapa inteiro (com a malha ferroviária completa desenhada dentro) preso pra sempre.

**Correção:** `ttl=600` + `max_entries` (8–16, conforme o peso do objeto) em 8 funções: `carregar_base_sem_overlay`, `aplicar_overlay_baixas`, `preparar_df_visao`, `_preparar_df_calendario`, `montar_eventos_calendario_patios`, `resumir_demanda_calendario`, `resumir_conclusoes_por_turno_data`, `calcular_df_recomendado` e `_construir_mapa_navegacao` (commits `e3cfe6c` e `559484a`, branch `main`).

**Achados de segurança (cópia da aplicação), ainda pendentes de decisão do Julio:**
1. **Repositório GitHub público** (`jcopaz/Gestao_OS_EE_MRS`) — qualquer pessoa pode clonar o código-fonte inteiro (`app.py`, `api.py`) sem login. É o vetor nº1 de cópia técnica da aplicação. `.gitignore` usa allowlist (`/*` + `!arquivo`) e nenhum segredo real foi encontrado no histórico — mas o código de negócio inteiro está exposto.
2. **Chave de API mestra única embutida em texto puro no HTML/JS do pacote PWA offline** (`app.py`, campo oculto `apiKeyHidden` e `const API_KEY_FIXA`) — a mesma `API_KEY_SECRET`/`OFFLINE_API_KEY` que protege TODOS os endpoints do `api.py`, inclusive os administrativos de limpeza (`/limpar_evidencias_expiradas`, `/limpar_evidencias_orfas`, que apagam dado de verdade com `dry_run=false`). Qualquer usuário de campo pode extrair essa chave via "Inspecionar elemento" no navegador/celular e chamar a API de produção diretamente, sem nunca precisar do código-fonte — mais grave que o repositório público porque a chave chega automaticamente a todo usuário legítimo, não só a quem sabe procurar. `/pacote/{id}` (link compartilhável, 48 bits de entropia no id) é intencionalmente sem autenticação por design, mas serve o mesmo HTML com a chave embutida — reforça o mesmo problema, não é um bug novo.

**O que ficou pendente:** tornar o repositório privado e rotacionar/segregar a `API_KEY_SECRET` (uma chave só de sincronização pro PWA client-side, outra separada só pros endpoints administrativos, nunca a mesma) são decisões que exigem acesso a GitHub/Render/Streamlit Cloud que o agente não tem — decisão e execução ficam com o Julio.

**Aprendizado:** todo `@st.cache_data`/`@st.cache_resource` cacheado sem `ttl`/`max_entries` é seguro *só* enquanto a chave de cache for baixa cardinalidade e estável (ex.: um caminho de arquivo fixo); no momento em que a chave inclui um DataFrame, mtime, versão de ETL ou coordenada de usuário — qualquer coisa que muda com o uso normal do app — o cache vira um vazamento de memória silencioso, sem nenhum erro até o processo estourar. `cache_resource` é ainda mais perigoso que `cache_data` na mesma situação porque guarda o objeto vivo, não uma cópia serializada mais leve. Além disso, "proteger contra cópia da aplicação" não é só ofuscar/assinar código — um repositório público ou um segredo único embutido no cliente anulam qualquer proteção no código-fonte, porque dão a cópia (do código ou da funcionalidade) de graça, sem precisar nem ler o `app.py`.

---

## 24/08/2026 — App caiu de novo (agora por estouro do limite do plano Neon Free)

**O que aconteceu:** `sgomrs.streamlit.app` caiu com `psycopg2.OperationalError` logo na inicialização (`init_connection_pool()`, que já tenta 10x com 4s de espera entre tentativas pensando em Neon "acordando" — esgotou as 10 tentativas mesmo assim, descartando cold-start simples como causa). Julio confirmou no painel do Neon: era estouro de limite do plano gratuito (rede/compute), não credencial nem projeto pausado.

**Causa raiz:** o próprio `carregar_base_sem_overlay` já tinha uma nota de 22/07/2026 avisando que o *network transfer* do Neon Free estava perto do teto de 5GB/mês. O `ttl=600` aplicado no incidente de 21/08 (ver acima) resolveu a memória, mas tem um efeito colateral: força reconsulta da base inteira (com a coluna `dados_completos`, JSONB, a mais pesada) a cada 10 minutos **mesmo sem nenhuma baixa nova** — mais tráfego/compute no Neon do que o cache "pra sempre" de antes (que causava o vazamento de RAM, mas gerava menos consulta).

**Correção:** `ttl` de `carregar_base_sem_overlay` subiu de 600 pra 1800s. É a única das 8 funções cacheadas no incidente anterior que de fato consulta o Neon direto — as outras 7 operam em cima de um DataFrame já carregado em memória, então o `ttl` delas não tem custo de rede, só de CPU (ficaram como estavam). `max_entries` continua sendo quem prende a memória (não depende do `ttl`), então subir o `ttl` só reduz consulta ao Neon, sem reabrir o risco do estouro de RAM original.

**O que ficou pendente:** se o plano Neon Free estourar de novo mesmo com o `ttl` maior, a próxima alavanca é reduzir o que é puxado por request — hoje `carregar_base_sem_overlay` sempre traz `dados_completos` (JSONB) inteiro, mesmo pra telas que não usam esse campo (ex.: Painel/Calendário só precisam de status/data/pátio). Selecionar colunas por caso de uso, em vez de sempre a tabela inteira, é mudança estrutural maior — não foi feita aqui, só a mitigação de `ttl`.

**Aprendizado:** `ttl` curto que resolve vazamento de memória pode **aumentar** consumo de rede/egress se a função cacheada consulta um serviço externo pago por uso (Neon, Supabase) — é uma troca (RAM local vs. custo/limite do serviço), não uma correção isenta de efeito colateral. Ao ajustar `ttl` de cache que fala com um serviço externo, sempre checar se aquela função específica *de fato* consulta a rede (ou só reprocessa um DataFrame já em memória) — só a primeira tem custo real de reduzir o `ttl`; nas demais, `ttl` curto é só CPU e pode ficar baixo sem problema.

---

## 26/08/2026 — Pátios novos (IPN, IQC) sem coordenada cadastrada + repetição do incidente de 15/07

**O que aconteceu:** Julio pediu o cadastro de 2 pátios novos da coordenação de Piaçaguera (IPN - Prainha, e um segundo que ele digitou como "IQC" — depois confirmado com um líder de campo que o código certo do "Pátio Casqueiro" é **ICQ**, e que "IQC" na verdade é outro local real, "Extensão Cubatão 1"). Nenhum dos dois existia em `COORDENADAS_FIXAS`. Separadamente, o líder também reportou 16 OS reais com os ativos `S-ICQ005E1`/`S-ICQ005D1` ("Sinaleiro PN") aparecendo classificados no pátio **IPG** em vez de **ICQ**.

**Causa raiz (dupla, dois problemas diferentes disfarçados de um só):** (1) `IPN`/`IQC` simplesmente não existiam em `COORDENADAS_FIXAS` — pátio novo sem coordenada cadastrada não aparece com erro, só cai silenciosamente em "N/D" (`_resolver_patio`) ou usa o fallback de outro pátio; (2) a classificação errada IPG/ICQ dos ativos `S-ICQ005E1`/`S-ICQ005D1` **não era bug de `_resolver_patio`** — é match exato contra a tabela `mapeamento_patios`, que já estava gravada com `patio='IPG'` pra esses `ativo_chave`, herdado da planilha original importada em "Mapeamento de Ativos → Pátios". Corrigido direto no Neon: `UPDATE mapeamento_patios SET patio='ICQ' WHERE ativo_chave IN ('S-ICQ005E1','S-ICQ005D1') AND patio='IPG'`.

**Correção:** `IPN` e `IQC` adicionados a `COORDENADAS_FIXAS` em `app.py` **e** `api.py` (duplicação já é o padrão deste dicionário — nunca editar um só). Coordenada de `ICQ` também atualizada nos dois arquivos (era `-23.926493, -46.402720`, mesma classe de imprecisão do incidente de 15/07/2026 abaixo — o ponto salvo estava a ~2,1 km do local real informado por Julio, `-23.91531, -46.41890`).

**Aprendizado:** o incidente de 15/07/2026 ("dado de geolocalização fixo no código é fácil de esquecer que precisa de manutenção") **se repetiu** — `ICQ` já tinha coordenada desalinhada de novo, sem que ninguém tivesse notado até esse pedido específico. Além disso, um segundo padrão de bug: **pátio novo sem entrada em `COORDENADAS_FIXAS` falha silenciosamente** (vira "N/D" ou pátio errado), nunca um erro visível — o mesmo cuidado de "canal claro pra equipe reportar imprecisão" do aprendizado de 15/07 vale igualmente para "pátio que nunca foi cadastrado". E: nem todo "ativo no pátio errado" é bug de lógica — a tabela `mapeamento_patios` (dado importado de planilha) pode estar simplesmente errada desde a origem; sempre conferir os dois lugares (lógica de resolução E dado já persistido) antes de concluir qual dos dois é a causa.

---

## 26/08/2026 — StringDataRightTruncation no primeiro uso real do upload de Baixa Manual NAPL

**O que aconteceu:** primeira tentativa real de upload da planilha de Baixa Manual NAPL (feature nova, commit `1662a40` de 25/08/2026) quebrou com `psycopg2.errors.StringDataRightTruncation` no `execute_values` do INSERT em `baixas`.

**Causa raiz:** `texto_confirmacao` é `VARCHAR(38)` no banco — limite real do campo "Txt. confirmação" do SAP, já respeitado em todo o resto do app via `max_chars=38` no fluxo NRAV manual (online e offline). O upload em lote de NAPL era o único caminho que gravava esse campo direto da planilha, sem truncar — e a própria planilha de exemplo mostrada na tela já tinha um texto com 41 caracteres, acima do limite. Feature nova nunca tinha sido testada com um arquivo real até este momento.

**Correção:** trunca (não descarta a linha) `texto_confirmacao` em 38 e `causa_nrav` (`VARCHAR(10)`, mesmo risco) em 10 caracteres antes do INSERT, com alerta visível de quantas linhas foram truncadas — mesmo espírito de "marcado, não descartado" já usado no resto do app.

**Aprendizado:** ao espelhar um campo já existente noutro fluxo (aqui, `texto_confirmacao`/`causa_nrav` do fluxo NRAV manual), replicar também as validações/limites que protegem esse campo nos outros pontos de entrada — não só o nome da coluna. Todo caminho de escrita novo pra uma coluna com limite de tamanho (`VARCHAR(N)`) precisa validar/truncar antes do INSERT, mesmo que outro caminho já trate isso — a validação não é automática só porque a coluna já existe. E: a planilha de exemplo/mock mostrada na própria tela de upload é um bom canário — se ela já estoura o limite, dado real vai estourar também.

---

## 26/08/2026 — Catálogo de causas do NAPL ampliado por engano, revertido no mesmo dia

**O que aconteceu:** Julio passou uma lista de 61 códigos de causa (C0xx/E0xx/M0xx/P099) dizendo ser "a planilha de justificativa do NAPL". `_CAUSAS_NAPL_VALIDAS` foi ampliado de `{E001, E005}` pra essa lista inteira, commitado e pushed em `main`. Minutos depois, Julio confirmou o engano: os códigos `E0xx` eram na verdade do fluxo **NRAV**, e os `M0xx` são de **Via Permanente** — outra área/coordenação, sem relação com o NAPL da Eletroeletrônica. Revertido no mesmo dia (`{E001, E005}` de volta).

**Aprendizado:** quando o responsável do produto passa uma lista/planilha "descoberta" de fora do código (não confirmada linha a linha com uma fonte já validada no sistema), vale perguntar explicitamente a origem/escopo antes de aplicar em lote — mesmo quando a mudança em si é de baixo risco técnico (aqui, `causa_valida` só afetava desempate, nunca bloqueava nada). O sinal de alerta que passou batido: o próprio código já tinha um catálogo **separado e documentado** pro NRAV (`_JUSTIFICATIVAS_NRAV`, citando o IT-ENG-3113) — quando um catálogo novo se sobrepõe fortemente a um catálogo já existente e documentado (mesmos códigos E0xx), é sinal de possível duplicação/confusão de escopo, vale confirmar antes de assumir que são coisas diferentes.

---

## 26/08/2026 — Basemap do Mapa de Campo quebrado por mudança externa da Carto

**O que aconteceu:** Julio reportou o mapa da aba "Mapa de Campo" coberto por um aviso "API KEY REQUIRED carto.com/basemaps/apikey" em vez das ruas/malha ferroviária de verdade.

**Causa raiz:** dependência externa, não bug de código — a Carto (dona do estilo de basemap "CartoDB positron" usado no `folium.Map`) mudou a política e passou a exigir cadastro de API key pros tiles de basemap. O preset do Folium continuava apontando pro endpoint antigo, que agora devolve um tile-aviso em vez do mapa real.

**Correção:** trocado `tiles="CartoDB positron"` por `tiles="OpenStreetMap"` (preset nativo do Folium, gratuito, sem autenticação) — troca 1:1 de estilo visual, sem precisar cadastrar chave nenhuma.

**Aprendizado:** serviços de tile/mapa gratuitos de terceiros (Carto, Stamen, etc.) mudam política de acesso sem aviso prévio no seu código — um mapa que "sempre funcionou" pode quebrar sem nenhum push seu, só porque o provedor externo mudou algo do lado dele. Se isso acontecer de novo com qualquer basemap, o teste rápido é abrir a URL do tile diretamente no navegador pra confirmar se é o provedor (não o código) que mudou.

---

## 02/09/2026 — Filtro de datas da sidebar derrubou o painel 2x (data velha no session_state)

**O que aconteceu:** o painel caiu duas vezes seguidas em produção, ambas no filtro de período da sidebar. (1) `StreamlitAPIException` no `st.date_input("Período de Programação")` — `value=(start, end)` fora do intervalo `[min_value, max_value]`. (2) `TypeError: Invalid comparison between dtype=datetime64 and ...` em `aplicar_filtros_sidebar`, na máscara `df["dt_prog_filtro"].dt.date >= start_date`. Corrigido na hora com apoio do Copilot (commits `ebf2b94` e `b90abd8`); esta sessão fez a blindagem pra não repetir a **classe** de erro.

**Causa raiz (uma só, dois sintomas):** `filtro_start_date` / `filtro_end_date` são gravados no `st.session_state` a partir do retorno do `st.date_input` e relidos no rerun seguinte. Quando a base muda (novo upload, virada de mês, recorte por "ano vigente" que redefine `min_date`/`max_date`, linha ~4618), a data salva de um ciclo anterior fica **fora da faixa nova** — e o `st.date_input` recusa `value` fora de `[min,max]` (sintoma 1). O mesmo valor, quando não era uma data limpa (tupla de range meio-selecionado, `NaT`, tipo inesperado), quebrava a comparação de pandas na máscara do filtro (sintoma 2). O `st.date_input` em range **retorna tupla de 1 elemento** enquanto o usuário escolheu só a data inicial — mais uma fonte de valor "meio pronto" indo pro `session_state`.

**Correção (blindagem):**
1. `_intervalo_datas_seguro(ini, fim, piso, teto)` (novo, topo do `app.py`) — devolve **sempre** um par `(date, date)` dentro da faixa e com `ini <= fim`; qualquer valor não conversível (`None`, `NaT`, tupla, texto, data de outra base) cai no piso/teto. Usado no fragmento dos filtros **e** no ponto onde as datas são relidas do `session_state` antes de chamar `aplicar_filtros_sidebar` (antes esse segundo ponto não tinha nenhum saneamento).
2. `_para_timestamp_filtro(valor)` (novo) — converte limite de filtro em `Timestamp` normalizado **ou `None`**. Em `aplicar_filtros_sidebar`, se `start`/`end` (ou os de execução) não resolverem, o filtro daquele bloco é **ignorado** (mostra tudo) em vez de derrubar a tela. `except Exception` de propósito: filtro de exibição é fail-open (≠ regra de segurança, que é fail-closed).
3. CSS: campo de data da sidebar forçado pra **fundo branco + letras pretas** — as regras genéricas de `div[data-baseweb="input"]` deixavam o texto branco sobre `#1E293B` (ilegível quando o pedido era "letras pretas").

**Validação:** `py_compile` + suíte isolada (`scratchpad/teste_blindagem_datas.py`) cobrindo data fora de faixa dos dois lados, `None`, `()`, `(date,)`, `NaT`, texto lixo, intervalo invertido e a máscara rodando num DataFrame falso com `NaT` — nenhum caso lança exceção. Render do CSS **não** foi validado em navegador (sem ambiente gráfico) — conferir no celular.

**Aprendizado:**
1. **Todo valor lido do `st.session_state` que veio de um widget numa execução anterior é "dado externo"** — a base/faixa pode ter mudado no meio. Widget com `min_value`/`max_value` dinâmico (data, slider, number_input) precisa **sanear o default contra os limites atuais** antes de instanciar, sempre, não só quando "parece" que pode divergir.
2. `st.date_input` em modo range **retorna tupla de tamanho variável** (0, 1 ou 2) durante a seleção — nunca assumir 2; só gravar no `session_state`/comparar quando `len == 2`.
3. Quando o mesmo valor podre causa erro em **dois lugares diferentes** (aqui: na criação do widget e na comparação de pandas), corrigir os dois pontos não basta — vale extrair **um saneador único** e aplicá-lo em toda fronteira onde aquele valor entra (fragmento + releitura pro filtro), senão o terceiro ponto que ninguém lembrou volta a quebrar.
4. Filtro/exibição que não consegue resolver um parâmetro deve **degradar pra "mostra tudo"** (fail-open) — o oposto de regra de segurança/antifraude. Mas cuidado com o meio-termo silencioso: parâmetro que vira `NaT` sem exceção pode **zerar o resultado** sem erro nenhum (pior que crashar) — checar `pd.isna` explicitamente, não confiar só no `try/except`.

---

## 03/09/2026 — OS do Plano de Setembro (Paranapiacaba) "sumindo": parser de data não entendia mês abreviado PT-BR

**O que aconteceu:** a Coordenação de Paranapiacaba relatou que OS do Plano de Setembro não apareciam. Na verdade **não sumiam** — ficavam sem "Data inicial programada" (NaT) e por isso caíam pro fim da lista de roteirização (`Ordem_Prazo = 3` em `calcular_df_recomendado`), o que pro usuário de campo é praticamente "não existir". Corrigido remotamente pelo Julio em 03/09/2026 (commit `9debaa7`).

**Causa raiz:** `parse_data_programada()` só reconhecia ISO (`AAAA-MM-DD`) e `DD/MM/AAAA`. O Excel em **locale PT-BR** regrava uma data digitada como `15/09/2026` no formato `15-set` / `15-set-26` ao salvar/reabrir a planilha; e planilha reexportada/colada como CSV perde a formatação de data e sobra só o **número serial** do Excel (inteiro de dias desde 30/12/1899). Nos dois casos `pd.to_datetime(dayfirst=True)` devolvia `NaT` — sem erro, sem aviso.

**Correção:**
1. `parse_data_programada()` passou a reconhecer também: abreviação de mês PT-BR (`jan…dez`, regex `^(\d{1,2})[-/ ]([A-Za-zçÇ]{3,})[-/ .]*(\d{2,4})?$`, ano assumido = ano corrente quando ausente, `20` + `AA` quando 2 dígitos) e serial de data do Excel (`^\d{4,6}$` → `Timestamp("1899-12-30") + to_timedelta(int(s), "D")`).
2. A tela de **Upload de OS Programadas** agora conta, na hora do upload, quantas linhas ficaram com "Data inicial programada" não reconhecida e mostra `st.warning` pro administrador — em vez de o problema só aparecer semanas depois pro pessoal de campo.

**Aprendizado:**
1. **Dado que "some" pra um usuário nem sempre é registro faltando — pode ser um campo-chave virando NaT/nulo silenciosamente** e o item caindo pro fim de uma ordenação. Ao investigar "não aparece", checar se o registro existe mas com o campo de ordenação/filtro vazio, antes de suspeitar de escopo/permissão/cache.
2. **Parser de data que só cobre 1-2 formatos é frágil com planilha real** — Excel em locale PT-BR e round-trip por CSV produzem `15-set`, `15-set-26` e serial numérico como coisas normais, não exóticas. Todo ponto de entrada de data vindo de planilha precisa cobrir esses três, no mínimo.
3. **Validação no momento do upload > erro semanas depois no campo.** Quando um parser pode falhar em silêncio (`errors="coerce"`), a tela que recebe o arquivo deve contar e avisar quantas linhas ficaram inválidas na hora — o custo é ~3 linhas de código e evita um incidente de campo inteiro.

---

## 02–04/09/2026 — Upload de `app.py` inteiro pelo GitHub reverteu ~2 meses de trabalho (v16.1 → v18.2)

**O que aconteceu:** em 02/09/2026 dois commits **"Add files via upload"** (`1f8d9df`, `8b87f33`, feitos pela UI web do GitHub) substituíram o `app.py` inteiro por uma cópia local antiga (era ~v16.0.1). Isso **reverteu silenciosamente** tudo que tinha sido commitado direto no GitHub/Streamlit Cloud entre a v16.1.0 e a v18.2.0. Os patches de correção dos crashes de data (02/09) e o parser (03/09) foram aplicados **em cima da base já revertida**, então o rollback ficou escondido. Descoberto em 04/09 investigando 2 "regressões" que o Julio reportou como "voltou / sumiu".

**O que se perdeu no rollback (confirmado por `git diff f1d5fe8 HEAD -- app.py`, ~505 linhas líquidas a menos):**
- **Config Operacional:** toggle "🔒 Sem data de expiração (vira o novo padrão da coordenação)" — grava `vigente_ate = NULL` (commit `9928cd2`, v16.1.0). *(reposto 04/09)*
- **CSS do campo de data** da sidebar: o bloco `[data-testid="stDateInput"] * { color: #0F172A }` + fundo branco, que matava a **pílula vermelha com texto branco** do range picker do BaseWeb (v18.2.0). *(reposto 04/09)*
- **`calcular_df_recomendado` perdeu `@st.cache_data(ttl=600, max_entries=16)`** → reabre o **vazamento de memória do incidente de 21/08/2026** que derrubou o app no Streamlit Cloud. ✅ *reposto em v16.0.5 (`63ccff0`, 04/09)*
- **Basemap do Mapa de Campo** voltou pra `tiles="CartoDB positron"` → reabre o **incidente de 26/08/2026** (Carto passou a exigir API key; tile vira aviso "API KEY REQUIRED"). Deveria ser `Esri World Light Gray` (v18.0.3). ✅ *reposto em v16.0.5 — base + camada de rótulos de cidade juntas*
- Melhorias do mapa da v18.2.0 (raio verde, pino colorido por Segurança pendente, popup detalhado). ⚠️ *pendente (reconciliação)*
- ~245 linhas removidas de `render_tela_admin()` (a confirmar o quê — provável fluxo de Baixa Manual NAPL, v17/v18) e outros trechos no delta de 505 linhas. ⚠️ *a auditar (reconciliação)*

**Correção:**
- 04/09 v16.0.4 (`8d7f51b`): toggle "novo padrão" da Config Op + bloco CSS do campo de data.
- 04/09 v16.0.5 (`63ccff0`): cache de `calcular_df_recomendado` + basemap Esri (base + rótulos de cidade).
- **Ainda falta** a reconciliação da base v18.2.0 (`f1d5fe8`) com o que foi commitado de bom depois — `ebf2b94` + `b90abd8` (comparação de datas), a lógica de blindagem de `b0a5df6` (helpers `_intervalo_datas_seguro`/`_para_timestamp_filtro`; a parte de CSS de `b0a5df6` é redundante — `f1d5fe8` já tem melhor), a flag `EXIBIR_AGENDA_CALENDARIO` de `695b885`, e `9debaa7` (parser). Operação a fazer no branch `dev`, com teste em navegador, antes de `main` — não em cima do rollback.

**Aprendizado:**
1. **Nunca subir `app.py` inteiro pela UI "Add files via upload" do GitHub a partir de uma cópia local.** O repositório recebe commits diretos (GitHub web / Copilot / Streamlit Cloud) — qualquer cópia local fica desatualizada em dias. Alteração é sempre `git pull` → editar → `git commit`/`push`, ou patch cirúrgico direto na web sobre a versão atual. Um "upload" é um `git checkout` mascarado de commit: reverte tudo que a cópia local não tinha, sem conflito, sem aviso.
2. **Commit "Add files via upload" com centenas de linhas removidas é bandeira vermelha** — sempre abrir o diff (`git show <sha> --stat` + hunks) antes de confiar. `835 insertions, 628 deletions` num arquivo de 8,9 mil linhas não é "corrigi um bug", é "troquei o arquivo".
3. **Regressão reportada como "isso já estava corrigido / voltou / sumiu" = suspeitar de rollback de versão antes de re-corrigir o item.** Rastrear `git log --all -S"<trecho da feature>" -- app.py` acha o commit que tirou; comparar contra a última tag/commit bom conhecido (`git diff <bom> HEAD -- app.py`) mostra o estrago inteiro de uma vez, em vez de descobrir item por item.
4. **Manter uma tag/ponto de referência de "última versão boa conhecida"** (como o `estavel-2026-07-17` no topo deste doc) e comparar contra ela ao primeiro sinal de regressão em massa.

---

## Lições transversais (válidas pra qualquer mudança futura)

- **Verificar causa raiz com dado real (SQL/log) antes de aplicar patch** — não assumir, não adivinhar. Vale tanto pra bug de dado quanto pra bug de infraestrutura.
- **Fail-closed em validação de segurança/antifraude** — nunca liberar por padrão quando um dado necessário não pôde ser resolvido.
- **Filtro "de segurança extra" que duplica responsabilidade já garantida em outro lugar é candidato a bug silencioso** — perguntar sempre se ele protege contra algo que não seria pego de outro jeito.
- **Fala informal em reunião não é especificação técnica** — qualquer parâmetro numérico/regra de negócio citado informalmente precisa de validação explícita antes de virar constraint no código.
- **Mudança em comportamento de renderização de widget (mesmo com API oficial) precisa de teste real antes de produção** — não só validação de sintaxe/lógica.
- **Métrica agregada zerada ou anômala é sinal de alerta prioritário**, mesmo sem erro explícito reportado ainda.
- **Dependências sem pin de versão são risco de infraestrutura silencioso** — travar sempre, principalmente libs com binário nativo.
- **Chave de conflito (`ON CONFLICT`/`UNIQUE`) de qualquer tabela ligada a uma execução específica deve usar o identificador único de verdade**, nunca uma combinação de campos descritivos que podem se repetir.
- **Nunca usar substring solta (`"X" in campo`) pra decidir coordenação/escopo/permissão** — sempre prefixo ou valor exato.
- **Toda coluna nova adicionada a uma função `@st.cache_data` exige incrementar a versão do cache** (`ETL_VERSION`) no mesmo commit.
- **Extrair código inline pra uma função nova pode fechar silenciosamente o bloco `if` em volta** (indentação incorreta é erro lógico, não de sintaxe — `py_compile` não pega) — sempre conferir a indentação de tudo que vem *depois* do trecho extraído.
- **Todo `@st.cache_data`/`@st.cache_resource` precisa de `ttl`/`max_entries` sempre que a chave inclui algo que muda com o uso normal do app** (DataFrame, mtime, versão de ETL, coordenada de usuário) — sem limite, cada mudança é uma cópia nova presa na RAM pra sempre, até estourar o processo compartilhado do Streamlit Cloud. `cache_resource` é o caso mais perigoso porque guarda o objeto vivo (ex.: `folium.Map` inteiro), não uma cópia serializada mais leve.
- **Repositório público ou segredo único embutido no cliente (PWA/JS) anulam qualquer proteção de código-fonte contra cópia da aplicação** — não é sobre ofuscar/assinar o código, é sobre onde o código e as credenciais realmente ficam acessíveis. Rotação/segregação de chave (uma por finalidade, nunca uma mestra compartilhada entre painel, automação e cliente offline) é decisão de infraestrutura, não só de código.
- **`app.py` e `api.py` são deploys separados sem código compartilhado** — uma lógica corrigida/reforçada num dos dois (ex.: resolução de pátio, fail-closed) não garante que o outro lado tenha a mesma robustez. "Parar de aceitar dado errado" e "conseguir resolver o dado certo" são correções diferentes — sempre checar os dois lados de qualquer regra que existe duplicada.
- **Default de widget lido do `st.session_state` (data, slider, number_input) tem que ser saneado contra os `min`/`max` atuais antes de instanciar** — o valor foi gravado num rerun anterior, com base/faixa possivelmente diferentes; `st.date_input` ainda por cima retorna tupla de tamanho variável (0/1/2) durante a seleção. Extrair **um saneador único** e chamá-lo em toda fronteira onde o valor entra (fragmento do widget **e** releitura pro filtro/consulta), não só onde estourou.
- **Nunca subir `app.py`/`api.py` inteiro pela UI "Add files via upload" do GitHub a partir de cópia local** — o repo recebe commits diretos (web/Copilot/Cloud) e a cópia local desatualiza em dias; um "upload" é `git checkout` mascarado que reverte tudo que a cópia não tinha, sem conflito nem aviso. Fluxo: `git pull` → editar → `commit`/`push`, ou patch cirúrgico na web sobre a versão atual. Commit "upload" com centenas de linhas removidas = abrir o diff antes de confiar. Regressão do tipo "isso já estava corrigido / voltou / sumiu" → suspeitar de rollback de versão e comparar contra a última tag boa (`git diff <bom> HEAD -- app.py`) antes de re-corrigir item por item.
