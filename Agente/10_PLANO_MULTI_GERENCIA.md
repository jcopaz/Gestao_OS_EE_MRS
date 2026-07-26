# 🗺️ Plano: Hierarquia Multi-Gerência (Gerência Geral → Gerência → Coordenação)

> **Status:** plano aprovado para revisão, execução ainda não iniciada (definido em 26/07/2026).
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

Todo filtro de escopo do sistema passa a chamar isso em vez de comparar
string direto. É a única peça de lógica nova de fato — o resto do plano é
**trocar comparações hardcoded por chamadas a essa função**, e alimentar os
`selectbox`/`multiselect` com `carregar_hierarquia_organizacional()` em vez
de listas fixas.

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

### Fase 2 — Filtro de escopo usando o resolvedor
- `aplicar_filtros_sidebar` (3.6), `carregar_base_sem_overlay`/`aplicar_overlay_baixas`
  (sessão 5) e o filtro de equipe (10.3.3) trocam `if escopo != "Todas": df == escopo`
  por `resolver_coordenacoes_do_escopo(...)` + `.isin(...)`.
- **Teste de regressão obrigatório aqui:** usuário com escopo
  `coordenacao=Paranapiacaba` continua vendo exatamente o mesmo recorte de
  hoje (a mudança é só troca de mecanismo, resultado idêntico com os dados
  atuais).

### Fase 3 — Guarda de admin delegado (Gestão de Usuários)
- Tela `render_tela_gestao_usuarios` (3.8c, criada em 26/07/2026): ao
  criar/editar usuário, o combo "Escopo (Base)" só pode oferecer
  coordenações/gerências **dentro da árvore do admin logado** (hoje qualquer
  admin pode atribuir qualquer escopo a qualquer um — não é problema com 1
  admin só, passa a ser quando existir mais de um).
- Sem isso, um admin delegado da Gerência Vale do Paraíba poderia (por erro
  ou não) criar um usuário com escopo em Paranapiacaba.

### Fase 4 — Piloto real: Vale do Paraíba
- Levantar com o Julio: nomes exatos das coordenações do Vale do Paraíba,
  pátios/coordenadas fixas (entram em `COORDENADAS_FIXAS`, igual hoje).
- 1 `INSERT` em `hierarquia_organizacional` por coordenação nova.
- Criar/promover 1 usuário de teste com `escopo_nivel='gerencia'`,
  `escopo='Gerência Vale do Paraíba'` → confirmar que a Visão Gerencial e a
  Roteirização mostram **só** aquelas coordenações, e que Paranapiacaba/
  Piaçaguera continuam intocadas para os usuários de hoje.

## 5. Riscos já conhecidos que este plano tem que respeitar

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

## 6. Validação

- `python -m py_compile app.py api.py` em cada fase.
- Cada fase testada primeiro em `dev` com o usuário `admin` (escopo "Todas")
  e depois logado como um usuário `escopo_nivel='coordenacao'` (garantir que
  o recorte de hoje não mudou).
- Fase 4 é o primeiro teste real com `escopo_nivel != 'coordenacao'/'todas'`
  — validar visualmente a Visão Gerencial e a Roteirização antes de dar
  qualquer acesso real a alguém do Vale do Paraíba.

## 7. Rollout

- Cada fase = 1 commit (ou poucos) em `dev`, testada, só depois promovida
  pra `main` respeitando a janela (seg-sex, a partir das 12h).
- Versão da sidebar: Fases 0-2 (fundação, sem mudar comportamento visível
  pra ninguém) = **MINOR**. Fase 3 (guarda de permissão nova) e Fase 4
  (Gerência nova operando de verdade) = **MAJOR**.

## 8. Fora de escopo agora (YAGNI)

- Config operacional por Gerência/Gerência Geral (regras confirmadas iguais
  — só por coordenação, como já é hoje, resolve).
- Repositório/banco separado por Gerência Geral (seção 1).
- Qualquer coisa em `api.py` alem de manter `COORDENADAS_FIXAS` atualizado.
