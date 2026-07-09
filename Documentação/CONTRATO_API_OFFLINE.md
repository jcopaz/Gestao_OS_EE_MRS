# CONTRATO_API_OFFLINE.md

> Atualizado em Julho/2026.

## Serviço
Motor Antifraude / Sincronização Offline do SGO MRS.

## Endpoint principal
`POST /sincronizar_baixa_offline`

## Campos obrigatórios
- `os_id` (Form)
- `ativo_id` (Form)
- `usuario` (Form)
- `lat_browser` (Form)
- `lon_browser` (Form)
- `data_hora_local` (Form)
- `horario_inicio` (Form)
- `horario_fim` (Form)
- `foto` (File / UploadFile)

## Campos opcionais
- `acompanhante` (Form, default vazio)
- `debug_token` (Form, default `None`)

## Regras de negócio conhecidas
1. Se `lat_browser == 0.0` e `lon_browser == 0.0`, a API tenta extrair GPS EXIF da foto.
   - **A leitura do EXIF é feita a partir dos bytes ORIGINAIS da foto**, antes de qualquer
     `exif_transpose`/resize. Portanto, o cliente NÃO pode reencodar/comprimir a foto (canvas)
     quando o navegador não capturou GPS, sob pena de apagar o EXIF e quebrar o fallback.
2. A distância até o ativo é validada por Haversine.
3. Limite geográfico: **2,0 km**.
4. Se `debug_token == "mrs2026"`, o bloqueio geográfico é ignorado para teste.
5. A foto tenta subir para o Supabase; se falhar, a API faz fallback para Base64 em `foto_evidencia`.

## Ordem de resolução do GPS (implementada)
1. **GPS do navegador** (`lat_browser`/`lon_browser`): usado diretamente quando presente.
2. **GPS EXIF da foto**: usado apenas como fallback, quando o navegador envia `0.0 / 0.0`.

## Saídas esperadas
Retorno JSON com status da sincronização e metadados de auditoria
(`status`, `os_id`, `dist_km`, `fonte_gps`, `auditoria`).

## Dependências do fluxo
- PostgreSQL / Neon para persistência de `baixas` e `evidencias`.
- Supabase para storage público das imagens.
- PIL/Pillow para orientação da imagem e compressão.

## Observações para agentes
- O contrato atual exige `foto`; fluxos offline sem evidência não sincronizam pelo endpoint atual.
- Bugs de sincronização devem ser investigados primeiro pela aderência aos nomes dos campos do `FormData`.
- **Cliente offline (regra vigente pós Jul/2026):** enviar foto ORIGINAL (EXIF intacto) quando
  `gpsAtual == null`; comprimir apenas quando há GPS de navegador.

## Endpoints
- POST /sincronizar_baixa_offline — sync de baixa. Obrigatórios: os_id, ativo_id, usuario,
  lat_browser, lon_browser, data_hora_local, horario_inicio, horario_fim, foto. Opcionais:
  acompanhante, debug_token.
- GET  /health — health-check antes de publicar.
- POST /publicar_pacote — persiste HTML do pacote (tabela pwa_pacotes), retorna id.
- GET  /pacote/{id} — serve o HTML em HTTPS (permite GPS no celular).

## Regras vigentes (pós 03/Jul)
1. GPS OBRIGATÓRIO. Se lat/lon == 0,0 → HTTP 400. EXIF REMOVIDO (sem fallback pela foto).
2. Distância Haversine; limite 2,0 km.
3. debug_token == "mrs2026" ignora geofence (teste).
4. Foto sobe ao Supabase; fallback Base64 se falhar.
5. Cliente offline SEMPRE comprime a foto.

## CORS: GET, POST, OPTIONS liberados.
## Banco: baixas ON CONFLICT(os); evidencias ON CONFLICT(ativo,atividade); pwa_pacotes.
## Nota: duplicação de linha vem do merge 1:N na exibição, não do banco (upsert idempotente).
