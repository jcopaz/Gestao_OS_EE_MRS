# 🗺️ Multi-Gerência — Fragilidades Já Existentes no Código (26/07/2026)

> ⚠️ Diferente do resto do plano multi-gerência, este arquivo **não é sobre o
> futuro** — são gaps que já existem **hoje**, com só 2 coordenações. A
> hierarquia nova não os cria, só os expõe mais (mais gente, mais
> coordenações, admins delegados). Corrigir cada um pode acontecer
> independente da expansão, quando fizer sentido na fila de trabalho.

O Julio perguntou: *"se um usuário da coordenação 1 subir dados da IPA, o
sistema aceita?"* — resposta verificada linha a linha no código: **sim,
aceita, em 2 de 3 telas de escrita** (na época da checagem).

## 1. Upload de OS Programadas — tem checagem, mas falha calada
`app.py:1164`: `if escopo_user != "Todas": df = df[df["_coord_auto"] == escopo_user]`.
Linhas fora do escopo do usuário são **descartadas sem aviso**. Se um usuário
de Paranapiacaba sobe uma planilha só de Piaçaguera, o resultado é
"✅ Sucesso! 0 OS processadas" — sem explicar que 100% das linhas foram
rejeitadas por escopo. Risco: **confusão**, não vazamento de dado (o filtro
existe e funciona).
**Status:** não corrigido.

## 2. Importação de Baixas em Massa (IW47) — sem checagem nenhuma
`app.py:1376` (`coord_baixa = st.selectbox("Coordenação", [...])`), usado no
mapeamento por Centro de Trabalho e no fallback de coordenação final.
**Nenhum ponto do fluxo compara `coord_baixa` contra o escopo de quem está
logado.** Um usuário de qualquer coordenação pode importar baixas em massa
marcadas como pertencentes a **qualquer outra** coordenação, hoje mesmo, com
2 coordenações. Risco: **real**, é escrita direta na tabela `baixas` (dado
operacional, não só cadastro).
**Status:** não corrigido.

## 3. Configurações Operacionais — sem checagem nenhuma
`coord_sel = st.selectbox("Coordenação", [...])` (região 3.8b). Mesma
ausência de checagem — inclui o botão "🔄 Resetar Padrões" adicionado em
26/07/2026, que herda o mesmo gap por estar na mesma tela/formulário.
Inofensivo hoje (só existe 1 admin, com escopo "Todas" mesmo), mas se
tornaria um risco real no dia em que existir um admin delegado por Gerência
(confirmado como plano futuro pelo Julio) — ele conseguiria reconfigurar ou
resetar geofence/trava de uma coordenação que não é a dele.
**Status:** não corrigido.

### Causa raiz comum (itens 1-3)
Nenhuma das 3 telas verifica **"o valor que estou gravando pertence à minha
própria árvore de escopo?"** — elas checam permissão de *funcionalidade*
(`governanca`: pode acessar esta tela?), nunca permissão de *dado* (pode
gravar *para esta coordenação específica*?). A Fase 3 do plano principal
(`11_MULTI_GERENCIA_MODELO_E_FASES.md`) fecha isso com a mesma peça central
do resolvedor de escopo, usada como guarda de escrita em vez de filtro de
leitura.

## 4. ✅ CORRIGIDO (26/07/2026) — Retorno SAP mapeava qualquer coordenação nova para o centro de Paranapiacaba
`gerar_excel_sap_bytes`, versão antiga:
```python
def get_centro_trab(coord):
    c = str(coord).upper()
    return 'E.SP.IPG' if 'IPG' in c or 'PIACAGUERA' in c or 'PIAÇAGUERA' in c else 'E.SP.IPA'

def get_centro(coord):
    c = str(coord).upper()
    return 'CIPG' if 'IPG' in c or 'PIACAGUERA' in c or 'PIAÇAGUERA' in c else 'CIPA'
```
Essa era a etapa final do fluxo "SAP → Motor SGO → Campo → Banco → **Retorno
SAP**" (ver `04_ARQUITETURA.md`). Qualquer coordenação que não contivesse
"IPG" ou "Piaçaguera" caía no `else` e recebia os códigos de **Paranapiacaba**
('E.SP.IPA'/'CIPA') — silenciosamente, sem erro. Além disso usava substring
solta (`'IPG' in c`) — mesma causa raiz do incidente de 20-21/07/2026, em
uma função diferente que não tinha sido corrigida junto na época. Era o item
de maior risco real de todo o plano: com o Vale do Paraíba, o arquivo
devolvido ao SAP lançaria horas trabalhadas no centro de trabalho errado, um
problema que só apareceria dentro do SAP corporativo da MRS, bem depois e
difícil de rastrear até a causa.

**Correção aplicada:** novo dicionário explícito `MAPA_CENTRO_SAP`
(coordenação → `{centro_trabalho, centro}`), correspondência **exata** (nunca
substring). Coordenação sem entrada no mapa é **excluída** da exportação —
nunca exportada com código adivinhado — e a tela mostra um aviso explícito
listando as OS excluídas e o motivo. Testado com 3 cenários (só coordenações
conhecidas / mistura de conhecida e desconhecida / tudo desconhecido) antes
do commit. **Ao cadastrar o Vale do Paraíba (Fase 4 do plano principal): não
esquecer de adicionar a entrada dele em `MAPA_CENTRO_SAP`** — sem isso, a
exportação SAP dele sairá vazia com aviso, em vez de errada silenciosamente
(comportamento seguro, mas ainda exige essa ação manual).

**Validado contra dado real de produção (26/07/2026):** o Julio rodou no
Neon a contagem de `coordenacao` distintas em `baixas` — **13.888 linhas
"Piaçaguera" + 11.554 "Paranapiacaba", 25.442 no total, zero linhas fora
dessas duas grafias exatas**. Ou seja: a correção não exclui nenhuma OS
histórica da exportação — o risco era só pra coordenação futura ainda não
cadastrada, exatamente como o plano previa.

## 5. Seletor de "Visão" na sidebar já existe — é o mesmo pedido da Fase 2b, mas incompleto
```python
visao_selecionada = st.sidebar.radio("Selecione a Visão:", ["Gerência", "Paranapiacaba", "Piaçaguera"], ...)
filtro_visao = "Todas" if visao_selecionada == "Gerência" else visao_selecionada
```
Bom achado, não um problema a corrigir isoladamente: o drill-down da Fase 2b
**não precisa ser criado do zero** — já existe, só está hardcoded e aparece
pra **qualquer** usuário com "Painel Gerencial", independente do escopo dele
(um usuário só de Paranapiacaba já vê hoje as 3 opções, incluindo
"Piaçaguera", que renderiza vazio pra ele). Vira trabalho da Fase 2b:
generalizar esse rádio pra ler de `hierarquia_organizacional` +
`resolver_coordenacoes_do_escopo()`.
**Status:** não corrigido (baixo risco — UX confusa, não vazamento de dado).

## 6. Colisão de nome: "Gerência" já significa 3 coisas diferentes no sistema
1. Um **perfil/cargo** de usuário (`Técnico, Assistente, Coordenador,
   Especialista, Gerência, Administrador`).
2. O **rótulo "ver tudo"** no rádio do item 5 (não se refere a uma gerência
   específica).
3. A partir do plano multi-gerência, também vai nomear um **nível real da
   hierarquia** (ex.: "Gerência Vale do Paraíba").

Efeito colateral concreto do item 1: `app.py:1196`,
```python
ver_tudo = perfil_user in ("Gerência",) or escopo_user == "Todas"
```
No Histórico de Uploads (3.8.2), **qualquer usuário cujo cargo seja
"Gerência" vê o histórico de upload de todas as coordenações, ignorando o
escopo dele** — um gerente delegado do Vale do Paraíba veria o histórico de
Paranapiacaba também, só pelo cargo. Ao implementar a Fase 3, revisar esse
bypass: `ver_tudo` deveria depender só de `escopo_nivel`/
`resolver_coordenacoes_do_escopo`, nunca do cargo. Vale considerar renomear
um dos três usos antes da expansão para reduzir confusão em código e
conversas futuras.
**Status:** não corrigido.

## 7. Mesma classe de fallback-pra-IPA em `obter_base_padrao_usuario`
`mapa_normalizacao` (função `obter_base_padrao_usuario`) tem o mesmo padrão
das outras ~12 listas: qualquer valor de `coordenacao_padrao`/`escopo` não
reconhecido cai no fallback `("IPA", "Base Padrão (IPA)")`. Risco menor que
os anteriores — só afeta o ponto de partida padrão do GPS/mapa (o técnico
corrige clicando em "📍 Minha Localização"), não integridade de dado — mas
entra no mesmo lote de listas a generalizar na Fase 1.
**Status:** não corrigido.
