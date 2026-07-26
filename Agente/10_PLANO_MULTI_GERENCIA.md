# 🗺️ Plano: Hierarquia Multi-Gerência (Gerência Geral → Gerência → Coordenação)

> **Status:** plano aprovado para revisão, execução ainda não iniciada (definido em 26/07/2026, revisado no mesmo dia com achados adicionais).
> **Decisão de arquitetura:** um único código/banco (multi-tenant por hierarquia), não réplicas por Gerência Geral — ver justificativa na seção 1.

---

## 0. Objetivo

Preparar `app.py`/`api.py` para suportar **~22 coordenações**, organizadas em
**Gerências**, organizadas em **Gerências Gerais** (hoje: 2 coordenações, 1
Gerência, dentro da "Gerência Geral SP"). O gatilho concreto é a próxima
expansão real: **Gerência Vale do Paraíba**, que entra **junto** da Gerência
atual dentro da mesma Gerência Geral SP.

Confirmado com o Julio (26/07/2026):
- Estrutura da planilha SAP é **igual** entre Gerências — só o dado muda.
- Regras de negócio (priorização, geofence, classificação) são **as mesmas**
  em todas as Gerências Gerais.
- Cada Gerência Geral terá, no futuro, **um admin próprio** para gerir
  usuários/acessos da sua árvore — não fica centralizado no Julio para sempre.

## 1. Por que um código só (e não um repositório por Gerência Geral)

| | Código único (multi-tenant) | Réplica por Gerência Geral |
|---|---|---|
| Bugs de plataforma (pool de conexão, geofence, etc.) | Corrige 1x | Corrige 4x, risco real de esquecer 1 |
| Regra de negócio nova | 1 lugar | 4 repositórios sincronizados |
| Custo operacional (deploy, secrets, monitoramento) | 1x | 4x |
| Isolamento entre Gerências Gerais | Via escopo/permissão | Via infraestrutura separada |

Como as regras de negócio são **confirmadas iguais**, o único argumento real a
favor de réplicas (evitar acoplamento de regras divergentes) não se aplica
aqui. O isolamento que a "visão por gerência" precisa é alcançável por
**escopo de dados + permissão**, sem duplicar infraestrutura — e a sessão de
revisão de 26/07/2026 já mostrou que bugs sistêmicos (pool de conexão sem
rollback, geofence fail-open) são exatamente o tipo de coisa que se perde
entre réplicas.

## 2. Modelo de dados novo

### 2.1. Tabela `hierarquia_organizacional` (nova)

Fonte única da árvore, substitui as **~12 listas `["Paranapiacaba",
"Piaçaguera"]` hardcoded** hoje espalhadas em `app.py` (upload de OS,
importação IW47, criação/edição de usuário, config operacional, sidebar,
`_mapa_norm`, `sedes_por_escopo`...).

```sql
CREATE TABLE IF NOT EXISTS hierarquia_organizacional (
    coordenacao     VARCHAR(100) PRIMARY KEY,
    gerencia        VARCHAR(100) NOT NULL,
    gerencia_geral  VARCHAR(100) NOT NULL,
    sede_padrao     VARCHAR(100),          -- chave em COORDENADAS_FIXAS (ex.: "IPA")
    ativo           BOOLEAN NOT NULL DEFAULT TRUE
);
```

Seed inicial (dados de hoje, sem mudar nada visível):
```sql
INSERT INTO hierarquia_organizacional (coordenacao, gerencia, gerencia_geral, sede_padrao) VALUES
    ('Paranapiacaba', 'Gerência SP', 'Gerência Geral SP', 'IPA'),
    ('Piaçaguera',    'Gerência SP', 'Gerência Geral SP', 'IPG')
ON CONFLICT (coordenacao) DO NOTHING;
```
Quando o Vale do Paraíba entrar, é **1 INSERT** por coordenação nova — sem
tocar em código.

### 2.2. `usuarios` — novo campo `escopo_nivel`

Hoje `usuarios.escopo` guarda um valor comparado **direto** contra o nome de
uma coordenação, ou a palavra fixa `"Todas"`. Para um usuário poder ver "toda
a Gerência Vale do Paraíba" (várias coordenações) sem listar uma por uma,
precisa saber **em que nível** aquele valor deve ser interpretado:

```sql
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS escopo_nivel VARCHAR(20) NOT NULL DEFAULT 'coordenacao';
-- valores: 'coordenacao' | 'gerencia' | 'gerencia_geral' | 'todas'

UPDATE usuarios SET escopo_nivel = 'todas' WHERE escopo = 'Todas';
-- todo o resto já nasce 'coordenacao' (default), que é o comportamento atual — sem quebrar ninguém
```

`escopo` continua guardando o **valor** (nome da coordenação, da gerência ou
da gerência geral); `escopo_nivel` diz **qual nível** aquele nome representa.
Migração 100% aditiva — nenhum usuário existente muda de comportamento até
alguém editar o cadastro dele para um nível diferente.

### 2.3. `os_programadas` / dados de OS

**Sem mudança de schema.** A coordenação de cada OS já é capturada hoje
(`coordenacao` na tabela, resolvida no upload). Ela só passa a ser validada
contra `hierarquia_organizacional` em vez de contra os dois nomes fixos.

## 3. Peça central nova: resolvedor de escopo

Uma função (existe em `app.py`; se o geofence por gerência não for
necessário — confirmado que não é — **não precisa duplicar em `api.py`**):

```python
@st.cache_data(ttl=600)
def carregar_hierarquia_organizacional() -> pd.DataFrame:
    ...  # SELECT * FROM hierarquia_organizacional WHERE ativo

def resolver_coordenacoes_do_escopo(escopo_nivel: str, escopo_valor: str) -> set[str] | None:
    """None = sem filtro (equivalente a 'Todas'). Sempre valor EXATO, nunca substring
    (lição do incidente 20-21/07/2026: 'IPG' in centro classificou Paranapiacaba como Piaçaguera)."""
    df = carregar_hierarquia_organizacional()
    if escopo_nivel == "todas":
        return None
    if escopo_nivel == "coordenacao":
        return {escopo_valor}
    if escopo_nivel == "gerencia":
        return set(df.loc[df["gerencia"] == escopo_valor, "coordenacao"])
    if escopo_nivel == "gerencia_geral":
        return set(df.loc[df["gerencia_geral"] == escopo_valor, "coordenacao"])
    return set()
```

Essa mesma função serve **dois papéis diferentes** (ver seção 5):
- **Leitura:** filtrar o que aparece nas telas (`.isin(coords_permitidas)`).
- **Escrita:** validar se o valor que o usuário está tentando gravar está
  dentro do que ele tem permissão de tocar (`valor in coords_permitidas`,
  bloqueando com erro explícito se não estiver — nunca só descartando).

## 4. Fases de execução (cada uma testável e "promovível" isoladamente)

### Fase 0 — Fundação de dados (risco: nenhum)
- `init_db()` (sessão 1.4): cria `hierarquia_organizacional` + seed das 2
  coordenações atuais (padrão `IF NOT EXISTS`/`ON CONFLICT` já usado em todo
  o `init_db`).
- `usuarios.escopo_nivel` (mesma sessão): `ALTER TABLE ADD COLUMN` + backfill.
- **Nada do comportamento visível muda.** Pode ir pra `main` sozinha.

### Fase 1 — Resolvedor central + dropdowns dinâmicos
- Criar `carregar_hierarquia_organizacional()` + `resolver_coordenacoes_do_escopo()`
  (sessão nova, perto da 4.2 — Config Operacional por coordenação, que já é o
  padrão mais parecido).
- Trocar as listas fixas por dropdown dinâmico nos pontos identificados hoje:
  upload de OS (3.8.1), importação IW47 (3.8.5), Config Operacional (3.8b),
  Gestão de Usuários (3.8c).
- **Ainda sem mudar comportamento** — com só 2 coordenações no banco, o
  dropdown dinâmico mostra exatamente as 2 mesmas opções de hoje.

### Fase 2 — Filtro de escopo (leitura) usando o resolvedor
- `aplicar_filtros_sidebar` (3.6), `carregar_base_sem_overlay`/`aplicar_overlay_baixas`
  (sessão 5) e o filtro de equipe (10.3.3) trocam `if escopo != "Todas": df == escopo`
  por `resolver_coordenacoes_do_escopo(...)` + `.isin(...)`.
- **Teste de regressão obrigatório aqui:** usuário com escopo
  `coordenacao=Paranapiacaba` continua vendo exatamente o mesmo recorte de
  hoje (a mudança é só troca de mecanismo, resultado idêntico com os dados
  atuais).

### Fase 2b — Seletor de nível de detalhe (drill-down), para escopo amplo
> Adicionado em 26/07/2026 a pedido do Julio: "ter as opções para selecionar
> o que pode ser visto nesse nível de detalhe" quando o escopo do usuário
> cobre mais de uma coordenação.

- Hoje o único drill-down que existe é o filtro de **Pátio** na sidebar —
  ele não sabe nada sobre Gerência/Gerência Geral.
- Quando `escopo_nivel` do usuário logado for `gerencia` ou `gerencia_geral`
  (ou `todas`), adicionar um filtro opcional na sidebar — "Ver: [Tudo do meu
  escopo ▾]" com as opções intermediárias da própria árvore dele (ex.: um
  usuário com `gerencia_geral=Gerência Geral SP` pode restringir
  temporariamente a visão só pra `Gerência Vale do Paraíba`, ou só pra uma
  coordenação específica, sem precisar de outro login).
- Implementação: mais um `resolver_coordenacoes_do_escopo()`, mas alimentado
  pela seleção do filtro em vez do `escopo` fixo do usuário — o filtro nunca
  pode **ampliar** o escopo real do usuário, só **restringir** dentro dele
  (a lista de opções do dropdown já vem pré-filtrada pela árvore dele).
- Não bloqueia a Fase 4 (o piloto do Vale do Paraíba funciona sem isso), mas
  é a melhoria natural pra quando existir gente com escopo de Gerência Geral
  de verdade — fica marcado aqui pra não esquecer, sem compromisso de data.

### Fase 3 — Guarda de escrita por escopo (3 telas, não só Gestão de Usuários)
> Achado adicional em 26/07/2026, verificado direto no código — ver seção 5
> para as evidências. Não é só a Gestão de Usuários: é um padrão que se
> repete em toda tela que **grava** um dado marcado com uma coordenação.

Princípio único a aplicar nas 3 telas abaixo: **antes de gravar, checar se a
coordenação/escopo escolhido está dentro de `resolver_coordenacoes_do_escopo()`
do usuário logado — se não estiver, bloquear com mensagem explícita.** Nunca
só filtrar silenciosamente depois (é o que a tela de Upload de OS já faz hoje
de forma incompleta, e é confuso — ver 5.1).

- **Upload de OS Programadas** (3.8.1): trocar o descarte silencioso por um
  aviso explícito ("X linhas fora do seu escopo foram ignoradas") e restringir
  o próprio dropdown de fallback às coordenações do usuário.
- **Importação de Baixas IW47** (3.8.5): adicionar a checagem que **não
  existe hoje** — o dropdown "Coordenação" só pode oferecer valores dentro do
  escopo de quem está logado.
- **Configurações Operacionais** (3.8b): idem — `coord_sel` restrito à árvore
  do usuário.
- **Gestão de Usuários** (3.8c, criada em 26/07/2026): ao criar/editar
  usuário, o combo "Escopo (Base)" só pode oferecer coordenações/gerências
  **dentro da árvore do admin logado**.

### Fase 4 — Piloto real: Vale do Paraíba
- Levantar com o Julio: nomes exatos das coordenações do Vale do Paraíba,
  pátios/coordenadas fixas (entram em `COORDENADAS_FIXAS`, igual hoje).
- 1 `INSERT` em `hierarquia_organizacional` por coordenação nova.
- Criar/promover 1 usuário de teste com `escopo_nivel='gerencia'`,
  `escopo='Gerência Vale do Paraíba'` → confirmar que a Visão Gerencial e a
  Roteirização mostram **só** aquelas coordenações, e que Paranapiacaba/
  Piaçaguera continuam intocadas para os usuários de hoje.
- Testar também a Fase 3 (guarda de escrita) com esse usuário: tentar subir
  OS/baixa marcada como Paranapiacaba logado como Vale do Paraíba e confirmar
  que é **bloqueado**, não só descartado.

## 5. Fragilidades identificadas nas telas de escrita (verificado em código, 26/07/2026)

O Julio perguntou: *"se um usuário da coordenação 1 subir dados da IPA, o
sistema aceita?"* — resposta verificada linha a linha: **sim, aceita, em
2 das 3 telas de escrita.** Isso já é verdade **hoje**, com o modelo atual de
2 coordenações — não é um problema que a hierarquia nova cria, é um problema
que ela **expõe e precisa fechar** antes de haver mais gente com acesso.

### 5.1. Upload de OS Programadas — tem checagem, mas falha calada
`app.py:1164`: `if escopo_user != "Todas": df = df[df["_coord_auto"] == escopo_user]`.
Linhas fora do escopo do usuário são **descartadas sem aviso**. Se um usuário
de Paranapiacaba sobe uma planilha só de Piaçaguera, o resultado é
"✅ Sucesso! 0 OS processadas" — sem explicar que 100% das linhas foram
rejeitadas por escopo. Risco: **confusão**, não vazamento de dado (o filtro
existe e funciona).

### 5.2. Importação de Baixas em Massa (IW47) — sem checagem nenhuma
`app.py:1376` (`coord_baixa = st.selectbox("Coordenação", [...])`), usado em
`app.py:1738` e `app.py:1829`. **Nenhum ponto do fluxo compara `coord_baixa`
contra o escopo de quem está logado.** Um usuário de qualquer coordenação
pode importar baixas em massa marcadas como pertencentes a **qualquer outra**
coordenação, hoje mesmo, com 2 coordenações. Risco: **real**, é escrita direta
na tabela `baixas` (dado operacional, não só cadastro).

### 5.3. Configurações Operacionais — sem checagem nenhuma
`app.py:2040` (`coord_sel = st.selectbox("Coordenação", [...])`). Mesma
ausência de checagem. Inofensivo hoje (só existe 1 admin, com escopo "Todas"
mesmo), mas se tornaria um risco real no dia em que existir um admin
delegado por Gerência (confirmado como plano futuro pelo Julio) — ele
conseguiria reconfigurar geofence/trava de uma coordenação que não é a dele.

### Causa raiz comum
Nenhuma das 3 telas verifica **"o valor que estou gravando pertence à minha
própria árvore de escopo?"** — elas checam permissão de *funcionalidade*
(`governanca`: pode acessar esta tela?), nunca permissão de *dado* (pode
gravar *para esta coordenação específica*?). A Fase 3 (seção 4) fecha isso
com a mesma peça central da seção 3, usada como guarda de escrita em vez de
filtro de leitura.

### 5.4. 🔴 CRÍTICO — Retorno SAP mapeia qualquer coordenação nova para o centro de Paranapiacaba
`gerar_excel_sap_bytes`, `app.py:832-838`:
```python
def get_centro_trab(coord):
    c = str(coord).upper()
    return 'E.SP.IPG' if 'IPG' in c or 'PIACAGUERA' in c or 'PIAÇAGUERA' in c else 'E.SP.IPA'

def get_centro(coord):
    c = str(coord).upper()
    return 'CIPG' if 'IPG' in c or 'PIACAGUERA' in c or 'PIAÇAGUERA' in c else 'CIPA'
```
Essa é a etapa final do fluxo "SAP → Motor SGO → Campo → Banco → **Retorno
SAP**" (ver `04_ARQUITETURA.md`). Qualquer coordenação que não contenha "IPG"
ou "Piaçaguera" cai no `else` e recebe os códigos de **Paranapiacaba**
('E.SP.IPA'/'CIPA') — silenciosamente, sem erro. Com o Vale do Paraíba (ou
qualquer uma das ~22), o arquivo devolvido ao SAP lançaria horas trabalhadas
no **centro de trabalho errado**, um problema que só apareceria dentro do
SAP corporativo da MRS, bem depois e difícil de rastrear até a causa. Além
disso usa substring solta (`'IPG' in c`) — mesma causa raiz do incidente de
20-21/07/2026, em uma função diferente que não foi corrigida junto na época.
**Este é o item de maior risco real de todo o plano** — precisa de mapeamento
explícito (coordenação → Centro/Centro de Trabalho SAP) por coordenação,
com falha explícita (não default) quando uma coordenação não tiver mapeamento
cadastrado, antes de qualquer coordenação nova ir para produção.

### 5.5. Seletor de "Visão" na sidebar já existe — é o mesmo pedido da Fase 2b, mas incompleto
`app.py:4037-4045`:
```python
visao_selecionada = st.sidebar.radio("Selecione a Visão:", ["Gerência", "Paranapiacaba", "Piaçaguera"], ...)
filtro_visao = "Todas" if visao_selecionada == "Gerência" else visao_selecionada
```
Bom achado: o drill-down da Fase 2b **não precisa ser criado do zero** — já
existe, só está hardcoded e aparece pra **qualquer** usuário com "Painel
Gerencial", independente do escopo dele (um usuário só de Paranapiacaba já
vê hoje as 3 opções, incluindo "Piaçaguera", que renderiza vazio pra ele).
Fase 2b passa a ser: generalizar esse rádio pra ler de
`hierarquia_organizacional` + `resolver_coordenacoes_do_escopo()`, restrito
às opções que fazem sentido pro escopo de quem está logado.

### 5.6. Colisão de nome: "Gerência" já significa 3 coisas diferentes no sistema
1. Um **perfil/cargo** de usuário (`["Técnico", "Assistente", "Coordenador", "Gerência", "Administrador"]`).
2. O **rótulo "ver tudo"** no rádio da seção 5.5 (não se refere a uma gerência específica).
3. A partir deste plano, também vai nomear um **nível real da hierarquia**
   (ex.: "Gerência Vale do Paraíba").

Efeito colateral concreto do item 1: `app.py:1196`,
```python
ver_tudo = perfil_user in ("Gerência",) or escopo_user == "Todas"
```
No Histórico de Uploads (3.8.2), **qualquer usuário cujo cargo seja
"Gerência" vê o histórico de upload de todas as coordenações, ignorando o
escopo dele** — um gerente delegado do Vale do Paraíba veria o histórico de
Paranapiacaba também, só pelo cargo. Ao implementar a Fase 3, revisar esse
bypass: `ver_tudo` deveria depender só de `escopo_nivel`/`resolver_coordenacoes_do_escopo`,
nunca do cargo. Vale considerar renomear um dos três usos antes da expansão
para reduzir confusão em código e conversas futuras (sugestão: manter
"Gerência" só para a hierarquia nova, e revisar o nome do perfil/rótulo).

### 5.7. Mesma classe de fallback-pra-IPA em `obter_base_padrao_usuario`
`app.py:3573-3599` (`mapa_normalizacao`) tem o mesmo padrão das outras ~12
listas: qualquer valor de `coordenacao_padrao`/`escopo` não reconhecido cai
no fallback `("IPA", "Base Padrão (IPA)")`. Risco menor que os anteriores —
só afeta o ponto de partida padrão do GPS/mapa (o técnico corrige clicando
em "📍 Minha Localização"), não integridade de dado — mas entra no mesmo
lote de listas a generalizar na Fase 1.

## 6. Outros riscos já conhecidos que este plano tem que respeitar

- **Nunca substring solta para decidir coordenação/gerência** — sempre
  comparação exata (lição de 20-21/07/2026, causou baixa em massa some do
  SGO). O resolvedor da seção 3 já nasce assim.
- **`app.py` (Streamlit Cloud) e `api.py` (Render) são hospedagens
  diferentes** — como o geofence/antifraude não muda por gerência (regras
  iguais confirmadas), `api.py` **não precisa** da tabela de hierarquia; só
  precisa que `COORDENADAS_FIXAS` tenha as coordenadas dos pátios novos, que
  é manutenção já esperada e não uma camada nova.
- **PWA offline é snapshot estático** — pacotes publicados antes da migração
  continuam funcionando (a hierarquia só afeta escopo de *visualização/
  cadastro*, não o payload da baixa).

## 7. Validação

- `python -m py_compile app.py api.py` em cada fase.
- Cada fase testada primeiro em `dev` com o usuário `admin` (escopo "Todas")
  e depois logado como um usuário `escopo_nivel='coordenacao'` (garantir que
  o recorte de hoje não mudou).
- Fase 3: testar explicitamente uma tentativa de gravação **fora** do escopo
  em cada uma das 3 telas (5.1/5.2/5.3) e confirmar bloqueio com mensagem
  clara, não só contagem zerada.
- Fase 4 é o primeiro teste real com `escopo_nivel != 'coordenacao'/'todas'`
  — validar visualmente a Visão Gerencial e a Roteirização antes de dar
  qualquer acesso real a alguém do Vale do Paraíba.

## 8. Rollout

- Cada fase = 1 commit (ou poucos) em `dev`, testada, só depois promovida
  pra `main` respeitando a janela (seg-sex, a partir das 12h).
- Versão da sidebar: Fases 0-2 (fundação, sem mudar comportamento visível
  pra ninguém) = **MINOR**. Fase 2b, Fase 3 (guarda de permissão nova) e
  Fase 4 (Gerência nova operando de verdade) = **MAJOR**.

## 9. Fora de escopo agora (YAGNI)

- Config operacional por Gerência/Gerência Geral (regras confirmadas iguais
  — só por coordenação, como já é hoje, resolve).
- Repositório/banco separado por Gerência Geral (seção 1).
- Qualquer coisa em `api.py` alem de manter `COORDENADAS_FIXAS` atualizado.
