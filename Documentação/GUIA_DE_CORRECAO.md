# GUIA_DE_CORRECAO.md

> Atualizado em 03/Julho/2026.

## Objetivo do agente
Auxiliar na correção e evolução do SGO MRS sem quebrar a arquitetura existente.

## Protocolo obrigatório de resposta
1. **Estrutura antes da lógica.** Validar primeiro:
   - duplicação de `with tab1:` / `with tab2:`
   - `#endregion` fora do lugar
   - HTML escapado no código
   - mistura de TAB com espaços
   - **variáveis usadas em blocos guardados (ex.: `tab1`/`tab2`) inicializadas ANTES do roteamento**
2. **Corrigir por sessão/subsessão.** Sempre indicar o bloco afetado.
3. **Mudança pequena primeiro.** Evitar reescrita ampla.
4. **Preservar estado.** Se a interação precisa sobreviver ao rerun, usar `st.session_state` e,
   quando necessário, `st.rerun()`.
5. **Separar sempre:** causa raiz → patch → impacto esperado → risco de regressão.
6. **Validar antes de entregar:** `py_compile` (app.py e api.py) e, no offline, extrair a JS das
   f-strings (`{{`→`{`, `}}`→`}`, interpolações → literal) e rodar `node --check`.

## Regras especiais
### Online (Streamlit)
- Python puro.
- Não usar `{{ }}` em dicionários/listas Python.
- Todo `st.form(...)` precisa conter `st.form_submit_button(...)`.
- Widgets dentro de `@st.fragment` só rerodam o fragment: se outro bloco depende da seleção,
  aplicar via `st.session_state` + botão/`st.rerun()` (ver caso do cronograma).
- Cache: `@st.cache_data` só invalida se a chave/hash mudar. Hashes de overlay (ex.: `_hash_baixas`)
  devem incluir um timestamp (`MAX(realizado_em)`) para captar UPDATEs via `ON CONFLICT`.
- Merges de overlay 1:N (evidências) exigem `drop_duplicates` antes do `merge` (evita linhas dobradas).

### Offline (Sessões 3.9 a 3.13)
- JavaScript e HTML vivem dentro de f-strings Python; toda chave estrutural de JS deve ser `{{`/`}}`.
- Não deixar `&lt;`, `&gt;`, `&amp;` no arquivo final.
- **GPS OBRIGATÓRIO e SEM EXIF:** a foto é sempre comprimida; `salvarSelecionadasNoLote` bloqueia
  gravação sem `gpsAtual`. Não reintroduzir fallback de EXIF.
- IndexedDB: manter `osGravadasSet` sincronizado (boot / após gravar / após sync) para a OS sumir
  da lista (`renderListaOS`).
- `file://` não tem contexto seguro → geolocation bloqueada. Offline só via **PWA HTTPS**
  (`/publicar_pacote` → `/pacote/{id}`).

## Estratégia de diagnóstico
### 1. Erro visual / tela branca / layout quebrado
Verificar: colagem em sessão errada, CSS fora de string tripla, `#endregion` fundido, keys duplicadas.

### 2. NameError em blocos guardados (ex.: `tab2 is not None`)
Variável só definida em um ramo de `if tela_atual==...`. Inicializar `None` antes do roteamento (10.1).

### 3. Erro de apontamento / rerun / estado sumindo
Verificar: ausência de `st.session_state`; form sem `st.form_submit_button`; filtro sem persistência;
login perdido ao abrir câmera → token de sessão (`?sid=`) e `AUTH_TOKEN_SECRET`.

### 4. Erro no offline / sync que "não vai"
Verificar: escape das chaves JS; contrato do `/sincronizar_baixa_offline`; nomes dos campos do
`FormData`; **GPS presente (obrigatório)**; `osGravadasSet` atualizado; se o offline foi aberto via
PWA HTTPS (e não `file://`).

### 5. Registro duplicado / OS ainda disponível após baixa
Duplicação → merge 1:N sem `drop_duplicates`. OS "fantasma" disponível → hash de cache sem
`MAX(realizado_em)`.

### 6. Bloqueio de prioridade furado
`mask_critica` deve ser apenas `Criticidade_rank == 1` (independe de data). Grupo = Ativo × Tipo de
Intervalo; CI/SI independentes.

### 7. KeyError "Ativo" em DataFrame de rota
`df_recomendado` inicia vazio. Checar `df.empty` E `"<coluna>" in df.columns`. Atenção com raio 1 km.

### 8. 404 em ação do app contra a API
Conferir se a rota chamada existe na `api.py` e se o método está liberado no CORS
(ex.: `/publicar_pacote`, `/pacote/{id}`, `/health`).

## Padrões vigentes (pós 03/Jul)
- Raio inicial 1 km; raio/ativo via botão **"Filtrar"** (`raio_aplicado`/`ativo_aplicado`).
- Cronograma (10.3.5) lê `ativo_aplicado`.
- Filtro CI/SI disponível também no offline.
- **GPS obrigatório (online e offline); EXIF removido.**
- **Horário único na baixa em massa** (toggle default ligado; individual mantido).
- **OS bloqueadas visíveis** (sombreado + 🔒).
- Baixa preferencial: ONLINE; offline (PWA HTTPS) como contingência.

## O que o agente deve evitar
- Reescrever `app.py` inteiro.
- Reintroduzir leitura de EXIF / fallback de GPS pela foto.
- Inventar novas camadas arquiteturais.
- Usar instruções genéricas sem citar a sessão exata.

## Saída preferida do agente
- Entregar o bloco completo da sessão alterada (ou o trecho exato com contexto suficiente).
- Explicar brevemente o porquê da mudança.
- Separar claramente: causa raiz, patch, impacto esperado e risco de regressão.