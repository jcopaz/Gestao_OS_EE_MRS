# 🗺️ Multi-Gerência — Modelo de Dados e Fases de Execução

> 🚧 **Visão de futuro, não iniciar sem aviso explícito do Julio** — ver
> `10_PLANO_MULTI_GERENCIA.md` (índice) para o status e o porquê.

## 1. Modelo de dados novo

### 1.1. Tabela `hierarquia_organizacional` (nova)

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

### 1.2. `usuarios` — novo campo `escopo_nivel`

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

### 1.3. `os_programadas` / dados de OS

**Sem mudança de schema.** A coordenação de cada OS já é capturada hoje
(`coordenacao` na tabela, resolvida no upload). Ela só passa a ser validada
contra `hierarquia_organizacional` em vez de contra os dois nomes fixos.

## 2. Peça central nova: resolvedor de escopo

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

Essa mesma função serve **dois papéis diferentes** (ver
`12_MULTI_GERENCIA_FRAGILIDADES_ATUAIS.md`):
- **Leitura:** filtrar o que aparece nas telas (`.isin(coords_permitidas)`).
- **Escrita:** validar se o valor que o usuário está tentando gravar está
  dentro do que ele tem permissão de tocar (`valor in coords_permitidas`,
  bloqueando com erro explícito se não estiver — nunca só descartando).

## 3. Fases de execução (cada uma testável e "promovível" isoladamente)

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

- Já existe hoje um radio "Selecione a Visão" na sidebar
  (`["Gerência", "Paranapiacaba", "Piaçaguera"]`, `app.py`) — é o mesmo
  mecanismo pedido aqui, só que hardcoded e mostrado a qualquer usuário com
  "Painel Gerencial" independente do escopo (ver
  `12_MULTI_GERENCIA_FRAGILIDADES_ATUAIS.md`, item 5).
- Quando `escopo_nivel` do usuário logado for `gerencia` ou `gerencia_geral`
  (ou `todas`), esse radio passa a ler de `hierarquia_organizacional` +
  `resolver_coordenacoes_do_escopo()` em vez da lista fixa, restrito às
  opções que fazem sentido pro escopo de quem está logado.
- O filtro nunca pode **ampliar** o escopo real do usuário, só **restringir**
  dentro dele (a lista de opções do dropdown já vem pré-filtrada pela árvore
  dele).
- Não bloqueia a Fase 4 (o piloto do Vale do Paraíba funciona sem isso), mas
  é a melhoria natural pra quando existir gente com escopo de Gerência Geral
  de verdade.

### Fase 3 — Guarda de escrita por escopo (4 telas, não só Gestão de Usuários)
> Achado em 26/07/2026, verificado direto no código — ver
> `12_MULTI_GERENCIA_FRAGILIDADES_ATUAIS.md` para as evidências. Não é só a
> Gestão de Usuários: é um padrão que se repete em toda tela que **grava** um
> dado marcado com uma coordenação.

Princípio único a aplicar nas telas abaixo: **antes de gravar, checar se a
coordenação/escopo escolhido está dentro de `resolver_coordenacoes_do_escopo()`
do usuário logado — se não estiver, bloquear com mensagem explícita.** Nunca
só filtrar silenciosamente depois (é o que a tela de Upload de OS já faz hoje
de forma incompleta, e é confuso).

- **Upload de OS Programadas** (3.8.1): trocar o descarte silencioso por um
  aviso explícito ("X linhas fora do seu escopo foram ignoradas") e restringir
  o próprio dropdown de fallback às coordenações do usuário.
- **Importação de Baixas IW47** (3.8.5): adicionar a checagem que **não
  existe hoje** — o dropdown "Coordenação" só pode oferecer valores dentro do
  escopo de quem está logado.
- **Configurações Operacionais** (3.8b): idem — `coord_sel` restrito à árvore
  do usuário. Isso também cobre o botão "🔄 Resetar Padrões" (26/07/2026).
- **Gestão de Usuários** (3.8c, criada em 26/07/2026): ao criar/editar
  usuário, o combo "Escopo (Base)" só pode oferecer coordenações/gerências
  **dentro da árvore do admin logado**.

### Fase 4 — Piloto real: Vale do Paraíba
- Levantar com o Julio: nomes exatos das coordenações do Vale do Paraíba,
  pátios/coordenadas fixas (entram em `COORDENADAS_FIXAS`, igual hoje) e os
  códigos de Centro/Centro de Trabalho SAP (entram em `MAPA_CENTRO_SAP`,
  ver `12_MULTI_GERENCIA_FRAGILIDADES_ATUAIS.md`, item 5.4).
- 1 `INSERT` em `hierarquia_organizacional` por coordenação nova.
- Criar/promover 1 usuário de teste com `escopo_nivel='gerencia'`,
  `escopo='Gerência Vale do Paraíba'` → confirmar que a Visão Gerencial e a
  Roteirização mostram **só** aquelas coordenações, e que Paranapiacaba/
  Piaçaguera continuam intocadas para os usuários de hoje.
- Testar também a Fase 3 (guarda de escrita) com esse usuário: tentar subir
  OS/baixa marcada como Paranapiacaba logado como Vale do Paraíba e confirmar
  que é **bloqueado**, não só descartado.
- Testar uma exportação SAP com OS do Vale do Paraíba e confirmar que o
  Centro/Centro de Trabalho sai correto no Excel gerado.

## 4. Outros riscos já conhecidos que este plano tem que respeitar

- **Nunca substring solta para decidir coordenação/gerência** — sempre
  comparação exata (lição de 20-21/07/2026, causou baixa em massa some do
  SGO; mesma causa raiz corrigida em 26/07/2026 no Retorno SAP). O
  resolvedor da seção 2 já nasce assim.
- **`app.py` (Streamlit Cloud) e `api.py` (Render) são hospedagens
  diferentes** — como o geofence/antifraude não muda por gerência (regras
  iguais confirmadas), `api.py` **não precisa** da tabela de hierarquia; só
  precisa que `COORDENADAS_FIXAS` tenha as coordenadas dos pátios novos, que
  é manutenção já esperada e não uma camada nova.
- **PWA offline é snapshot estático** — pacotes publicados antes da migração
  continuam funcionando (a hierarquia só afeta escopo de *visualização/
  cadastro*, não o payload da baixa).

## 5. Validação

- `python -m py_compile app.py api.py` em cada fase.
- Cada fase testada primeiro em `dev` com o usuário `admin` (escopo "Todas")
  e depois logado como um usuário `escopo_nivel='coordenacao'` (garantir que
  o recorte de hoje não mudou).
- Fase 3: testar explicitamente uma tentativa de gravação **fora** do escopo
  em cada uma das telas e confirmar bloqueio com mensagem clara, não só
  contagem zerada.
- Fase 4 é o primeiro teste real com `escopo_nivel != 'coordenacao'/'todas'`
  — validar visualmente a Visão Gerencial e a Roteirização antes de dar
  qualquer acesso real a alguém do Vale do Paraíba.

## 6. Rollout

- Cada fase = 1 commit (ou poucos) em `dev`, testada, só depois promovida
  pra `main` respeitando a janela (seg-sex, a partir das 12h).
- Versão da sidebar: Fases 0-2 (fundação, sem mudar comportamento visível
  pra ninguém) = **MINOR**. Fase 2b, Fase 3 (guarda de permissão nova) e
  Fase 4 (Gerência nova operando de verdade) = **MAJOR**.

## 7. Fora de escopo agora (YAGNI)

- Config operacional por Gerência/Gerência Geral (regras confirmadas iguais
  — só por coordenação, como já é hoje, resolve).
- Repositório/banco separado por Gerência Geral (ver índice, decisão de
  arquitetura).
- Qualquer coisa em `api.py` além de manter `COORDENADAS_FIXAS` atualizado.
