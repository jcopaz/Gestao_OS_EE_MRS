# 🗺️ Multi-Gerência (Gerência Geral → Gerência → Coordenação) — Índice

> ## 🚧 NÃO INICIAR A IMPLEMENTAÇÃO AINDA
> Isso é **visão de futuro**, registrada em 26/07/2026 para não se perder —
> **não é** trabalho em andamento nem uma fila pra próxima sessão. Existem
> outras melhorias/alterações previstas **antes** dessa expansão. Só começar
> a codificar qualquer fase quando o **Julio avisar explicitamente** que é
> hora de avançar.

## O que é

Plano para escalar o SGO Eletroeletrônica de **2 coordenações**
(Paranapiacaba, Piaçaguera) para **~22**, organizadas em Gerências, dentro de
4 Gerências Gerais. Gatilho concreto quando chegar a hora: **Gerência Vale do
Paraíba**, dentro da mesma Gerência Geral SP de hoje.

**Decisão de arquitetura já fechada:** um único código/banco (multi-tenant
por hierarquia de escopo), **não** um repositório/banco por Gerência Geral —
bugs de plataforma e regras de negócio se multiplicariam por 4 numa réplica,
e as regras de negócio já são confirmadas iguais entre Gerências Gerais.

## Onde está cada parte

| Arquivo | Conteúdo |
|---|---|
| `11_MULTI_GERENCIA_MODELO_E_FASES.md` | Modelo de dados novo (tabela `hierarquia_organizacional`, `escopo_nivel`), a peça central (`resolver_coordenacoes_do_escopo`), as 5 fases de execução, riscos conhecidos, validação, rollout e o que fica fora de escopo (YAGNI) |
| `12_MULTI_GERENCIA_FRAGILIDADES_ATUAIS.md` | 7 fragilidades encontradas **no código de hoje** (não é sobre o futuro — são gaps que já existem com só 2 coordenações, e que a expansão só torna mais expostos). Uma delas (Retorno SAP) já foi corrigida — ver o próprio arquivo |

## Contexto confirmado com o Julio (26/07/2026)

- Estrutura da planilha SAP é igual entre Gerências — só o dado muda.
- Regras de negócio (priorização, geofence, classificação) são as mesmas em
  todas as Gerências Gerais.
- Cada Gerência Geral terá, no futuro, um admin próprio pra gerir
  usuários/acessos da sua árvore — não fica centralizado no Julio.
- **Há melhorias/alterações previstas no sistema antes dessa expansão** —
  por isso o plano fica só documentado, em arquivos separados, até o aviso.
