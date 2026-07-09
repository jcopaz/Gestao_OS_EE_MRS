# 🔧 Padrões Técnicos

## 🚫 Regras inegociáveis (app.py / api.py)

1. **Estrutura por `#region` / `#endregion`** — `#endregion` é a **última linha** do bloco.
2. **Apenas um `with tab1:` e um `with tab2:`** por caminho de execução.
   - Blocos `10.3.x` usam guard `if tab2 is not None:`.
   - `tab1 = None; tab2 = None` inicializados **ANTES** do roteamento (sessão `10.1`).
3. **4 espaços de indentação** — nunca misturar TAB e espaços.
4. **Remover HTML escapado** (`&lt;`, `&gt;`, `&amp;`) do código final.
5. Tudo que precisa **sobreviver a rerun** vai para **`st.session_state`**.

---

## 🧭 Padrão de Roteirização

```python
# Raio inicial = 1 km. Aplicado só via botão "Filtrar".
raio_aplicado  = st.session_state.get("raio_aplicado", 1.0)
ativo_aplicado = st.session_state.get("ativo_aplicado")

# df_recomendado inicia VAZIO — guarda obrigatória:
if df_recomendado.empty or "Ativo" not in df_recomendado.columns:
    st.info("Nenhuma OS no raio selecionado. Ajuste o raio e clique em Filtrar.")
    return
```

- Cronograma (sessão `10.3.5`) lê `ativo_aplicado`.
- Filtro **CI/SI** disponível também no offline.

---

## 🎯 Padrão de Priorização (VIGENTE)

- OS **Muito Alta** (`Criticidade_rank = 1`) **trava as menores do MESMO grupo** (`Ativo × Tipo de Intervalo`), **independente da data**.
- Filas **CI** e **SI** são **independentes**.
- OS bloqueadas ficam **VISÍVEIS** (sombreado + 🔒). O bloqueio afeta **só a ordenação/backlog**, nunca esconde.

---

## 🛰️ Padrão GPS / Antifraude (CRÍTICO)

| Regra | Valor |
|---|---|
| Fonte de GPS | **SOMENTE navegador** (online e offline) |
| GPS obrigatório | Sem GPS → **não grava** |
| Coordenada `0,0` | API rejeita com **HTTP 400** |
| Leitura de EXIF / fallback pela foto | ❌ **REMOVIDO — nunca reintroduzir** |
| Geofence | **2,0 km** (Haversine) |
| Bypass de teste | `debug_token = "mrs2026"` |

> ⚠️ **Não reencodar/comprimir a foto no cliente** de forma que altere metadados — o padrão atual é GPS do navegador; qualquer fallback antigo por EXIF está descontinuado.

---

## 📴 Padrão Offline / PWA

- Sessões **3.9–3.13** geram HTML/JS em **f-strings** → escapar chaves JS (`{{` / `}}`).
- **IndexedDB** para a fila local; sincroniza via **FormData**.
- `osGravadasSet` atualizado em **3 momentos**: boot, após gravar, após sync (a OS some da lista).
- Distribuição: **"Publicar Rota PWA"** → `POST /publicar_pacote` → abrir `GET /pacote/{id}` **1x online** → usar offline.
- **Nunca `file://`** (bloqueia geolocation).

---

## 🔐 Padrão de Autenticação

```python
# Login em session_state + token HMAC na URL (?sid=), TTL 12h
# Segredo: AUTH_TOKEN_SECRET
# Logout:
st.query_params.clear()
```
- Login **persistente** ao abrir a câmera (não perder sessão).

---

## 🧮 Baixa em massa

- **Horário único** (toggle default **ligado**): 1 Data/Hora Início/Fim replicado às OS selecionadas (online e offline).
- Modo **individual** mantido como alternativa.

---

## 🧪 Validação obrigatória (antes de entregar)

| Alvo | Comando |
|---|---|
| `app.py` | `python -m py_compile app.py` |
| `api.py` | `python -m py_compile api.py` |
| JS do pacote offline | `node --check pacote_offline.js` |

**Roteiro de teste do app:**
1. Login → publicar Rota PWA → abrir pacote 1x online.
2. Filtrar (raio 1 km) → verificar guarda de `df_recomendado` vazio.
3. Baixa com GPS + foto (online) → conferir geofence 2,0 km.
4. Modo offline (sem sinal) → gravar → sincronizar → sem duplicidade.
5. Priorização: OS Muito Alta trava menores do grupo (🔒 visível).

---

## ⚠️ O que o agente deve EVITAR (app)

- ❌ Reescrever `app.py` inteiro.
- ❌ Reintroduzir leitura de EXIF / fallback de GPS pela foto.
- ❌ Inventar novas camadas arquiteturais.
- ❌ Instruções genéricas sem citar a **sessão exata**.

### Saída preferida do agente
- Entregar o **bloco completo da sessão alterada** (ou o trecho exato com contexto suficiente).
- Explicar brevemente o **porquê** e indicar **onde colar**.

---

# 🎨 Padrões da Apresentação (deck v10)

## Paleta (v8 / dourado)
```css
--bg:#040a16; --ink:#eef4ff; --mut:#aebfda;
--gold:#f3b13c; --gold-2:#ffd479;   /* acento primário */
--cyan:#39d6e8; --green:#37e07e; --rail:#ff5a7e;
--blue:#3b82f6; --violet:#9b7bff; --teal:#1ea7b6;
--mrs:#E4002B;
```

## Regras do gerador
- Edite **`gerar_pitch_v10.py`** (Python), **não** o HTML final.
- Imagens e logos **embutidos em base64** (Pillow + numpy) → arquivo único.
- Saída: `SGO_Eletroeletronica_MRS_v10.html`. Rodar: `python gerar_pitch_v10.py` (imagens na mesma pasta).
- **9 `<section class="slide">`**; slide 1 tem `class="slide active"`.
- **Sem imagens estáticas** — sempre FX: `spots`, `sparks`, matrix radial, malha pulsante (`gmark`/`gpulse`), sparks de encerramento.
- **Acentuação PT-BR correta** em todo texto novo (Priorização, Execução, Governança, Inteligência, geográfica…).
- Validar: 9 sections, `node --check` na `<script>`, 0 `&lt;/&gt;`, sem placeholders `__MRS__` remanescentes.

## Componentes-chave do deck
| Classe | Uso |
|---|---|
| `.matrix` / `.mnode` / `.mlink` | Grafo radial (slides "O que é" e "Governança") |
| `.flow4` / `.fnode` / `.logo-chip` | Fluxo com logos oficiais |
| `.imp-maps` / `.imp-map.atual/.sol` | Bloco "Antes / Agora" |
| `.mapwrap` / `.gmark` / `gpulse` | Malha pulsante de fundo |
| `.end-photo` / `.slide-fx` / `fxdash` | Slide de encerramento |
