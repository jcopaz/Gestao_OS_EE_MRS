# BUGS_CONHECIDOS.md

> Atualizado em 03/Julho/2026. ✅ RESOLVIDO = corrigido no deploy.

## 7. Bloqueio "5655 km do local" ✅ RESOLVIDO / REDESENHADO
GPS não capturado em `file://` (payload 0,0). Fallback antigo por EXIF era frágil (câmera sem
geotag / compressão apagava EXIF). **Decisão vigente:** GPS obrigatório e EXIF REMOVIDO; offline
distribuído via PWA HTTPS. API rejeita 0,0 (HTTP 400).

## 8. Câmera derruba o login ✅ RESOLVIDO
Login vivia só em `st.session_state`; câmera derruba WebSocket. Fix: token HMAC `?sid=` (TTL 12h).
Requer `AUTH_TOKEN_SECRET`.

## 9. KeyError "Ativo" (raio pequeno) ✅ RESOLVIDO
`df_recomendado` vazio no raio 1 km. Fix: guarda `df.empty or "Ativo" not in df.columns`.

## 10. Baixa DUPLICADA ✅ RESOLVIDO (03/Jul)
Merge 1:N de `evidencias` (10.2.4) multiplica linhas. Banco não duplica (upsert idempotente).
Fix: `drop_duplicates(subset=["os_ref_match"], keep="last")` antes do merge.

## 11. OS ainda "disponível" após baixada (online) ✅ RESOLVIDO (03/Jul)
`_hash_baixas` usava COUNT/MAX(os); UPDATE via ON CONFLICT não muda o hash → cache velho.
Fix: incluir `MAX(realizado_em)` no hash.

## 12. OS não some da lista (offline) ✅ RESOLVIDO (03/Jul)
`renderListaOS` reconstrói do JSON sem excluir gravadas. Fix: `osGravadasSet` filtra a lista.

## 13. NameError `tab2 is not None` (Governança) ✅ RESOLVIDO (03/Jul)
`tab1`/`tab2` só definidos no modo dashboard. Fix: `tab1=None; tab2=None` antes do roteamento (10.1).

## 14. Bloqueio "Muito Alta" furado ✅ RESOLVIDO (03/Jul)
Máscara exigia `rank==1 AND dt_prog<=hoje`; data futura/NaT escapava.
Fix: `mask_critica = (Criticidade_rank == 1)` — independe da data. OS bloqueadas visíveis (🔒).

## 15. "Falha ao publicar (404)" ✅ RESOLVIDO (03/Jul)
App chamava `/publicar_pacote` e `/health` inexistentes. Fix: criados `/health`,
`/publicar_pacote`, `/pacote/{id}`; GET no CORS; tabela `pwa_pacotes`.