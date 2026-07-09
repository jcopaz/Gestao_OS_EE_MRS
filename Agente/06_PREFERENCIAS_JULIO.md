# 🎯 Preferências do Julio

## 🗣️ Estilo de comunicação

| Prefere | Evita |
|---|---|
| Linguagem **simples e direta** | Jargão acadêmico desnecessário |
| Exemplos **concretos** | Abstrações vagas |
| **Tabelas antes/depois** | Blocos gigantes de texto |
| Código **bem comentado** | Código sem contexto |
| Saber **onde colar** | "Ajuste conforme necessário" |
| **Micro-sessões** em temas complexos | Refactors gigantes de uma vez |

---

## 🧩 Modo de trabalho (surgical patches)

1. **Validação primeiro** — testa a lógica com caso real antes de escalar.
2. **Patch cirúrgico** — mexe só no necessário; nunca reescreve o app inteiro.
3. **Uma sessão por vez** — corrige/entrega por `#region` / sessão numerada.
4. **Investigar estrutura antes da lógica** — ler o bloco atual antes de propor.
5. **Entregar bloco completo** da sessão alterada, pronto para colar.

---

## 😀 Hierarquia de emojis (para explicações)

| Emoji | Uso |
|---|---|
| 🎯 | Objetivo / meta |
| ✅ | Feito / validado |
| ⚠️ | Atenção / risco |
| ❌ | Não fazer |
| 🔧 | Ajuste técnico |
| 📌 | Ponto importante |
| 💡 | Insight |
| 🚀 | Evolução / próximo passo |

---

## 🖥️ Ambiente

- **VS Code + Pylance** (Windows, `C:\Users\30028203\Documents\Gestão_OS`).
- Python via terminal (`python vs9.py` etc.).
- Git/GitHub para versionamento.
- Abre o deck HTML no **Edge/Chrome** (F11 fullscreen).

---

## 🗨️ Expressões dele (sinais)

| Fala | Significado |
|---|---|
| "Show!" / "Top!" | Aprovado, gostou |
| "Bora avançar" | Sinal verde para o próximo passo |
| "Ficou bom mas vamos ajustar" | Aprovação parcial — vem refinamento |
| "Não veio / veio tudo preto" | Problema de entrega/render — investigar |

---

## ✅ Checklist do agente ao responder

- [ ] Respondi em **PT-BR**, tom didático?
- [ ] Usei **tabela / exemplo** quando ajudava?
- [ ] Indiquei **exatamente onde** aplicar (sessão / arquivo / linha)?
- [ ] Entreguei **bloco pronto para colar**, não fragmentos soltos?
- [ ] **Validei** (py_compile / node --check) quando mexi em código?
- [ ] Fui **cirúrgico** — sem reescrever o que não pediu?
