# SECRETS_TEMPLATE.md

## Streamlit / App
NEON_POSTGRES_URL=
SUPABASE_URL=
SUPABASE_KEY=
OFFLINE_API_URL=
OFFLINE_API_KEY=
AUTH_TOKEN_SECRET=

## API / Render
NEON_POSTGRES_URL=
SUPABASE_URL=
SUPABASE_KEY=
OFFLINE_API_KEY=

- AUTH_TOKEN_SECRET: segredo do token HMAC (?sid=). Deve ser FIXO entre reinícios.
- Não subir chaves reais; distinguir erro de código de erro de configuração.