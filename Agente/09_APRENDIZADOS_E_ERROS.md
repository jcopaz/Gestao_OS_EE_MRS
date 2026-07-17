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

## Lições transversais (válidas pra qualquer mudança futura)

- **Verificar causa raiz com dado real (SQL/log) antes de aplicar patch** — não assumir, não adivinhar. Vale tanto pra bug de dado quanto pra bug de infraestrutura.
- **Fail-closed em validação de segurança/antifraude** — nunca liberar por padrão quando um dado necessário não pôde ser resolvido.
- **Filtro "de segurança extra" que duplica responsabilidade já garantida em outro lugar é candidato a bug silencioso** — perguntar sempre se ele protege contra algo que não seria pego de outro jeito.
- **Fala informal em reunião não é especificação técnica** — qualquer parâmetro numérico/regra de negócio citado informalmente precisa de validação explícita antes de virar constraint no código.
- **Mudança em comportamento de renderização de widget (mesmo com API oficial) precisa de teste real antes de produção** — não só validação de sintaxe/lógica.
- **Métrica agregada zerada ou anômala é sinal de alerta prioritário**, mesmo sem erro explícito reportado ainda.
- **Dependências sem pin de versão são risco de infraestrutura silencioso** — travar sempre, principalmente libs com binário nativo.
- **Chave de conflito (`ON CONFLICT`/`UNIQUE`) de qualquer tabela ligada a uma execução específica deve usar o identificador único de verdade**, nunca uma combinação de campos descritivos que podem se repetir.
