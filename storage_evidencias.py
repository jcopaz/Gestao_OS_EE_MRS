# ==============================================================================
# SGO Eletroeletrônica — Gestão_OS (Storage das evidências fotográficas)
# Autor / Responsável pelo produto: Julio Copaz (julio.paz@mrs.com.br)
# Todos os direitos reservados. Uso, cópia ou distribuição não autorizados
# são proibidos.
# ==============================================================================
# Ponto ÚNICO de acesso ao bucket de fotos, usado por app.py (Streamlit) e
# api.py (FastAPI/Render). Migração Supabase Storage -> Cloudflare R2
# (04/10/2026): o plano free do Supabase (1 GB) não comporta o regime
# permanente da retenção CICLO + 30 dias (~550 MB/mês de fotos -> 1,5-3 GB
# vivos), ver Agente/09_APRENDIZADOS_E_ERROS.md.
#
# Backend escolhido pelas variáveis de ambiente (Render) ou st.secrets
# (Streamlit Cloud) -- mesmos nomes nos dois:
#   - R2_ACCOUNT_ID + R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY + R2_PUBLIC_URL
#     presentes -> Cloudflare R2 (bucket R2_BUCKET, padrão "evidencias")
#   - senão -> Supabase Storage (SUPABASE_URL + SUPABASE_KEY), comportamento
#     de antes da migração. Rollback = apagar as variáveis R2_* e reverter o
#     UPDATE de URLs no Neon.
#
# A URL pública gravada em evidencias.foto_url é sempre
# "<prefixo_url_publica()><nome do arquivo>" -- as rotinas de limpeza filtram
# por esse prefixo e recuperam o nome com nome_da_url().
# ==============================================================================

import os

import requests

_TIMEOUT = 30


def _cfg(nome: str, padrao: str | None = None) -> str | None:
    """Variável de ambiente (Render) ou st.secrets (Streamlit Cloud)."""
    # .strip(): segredo colado com Enter no final quebra o endpoint do R2
    valor = (os.environ.get(nome) or "").strip()
    if valor:
        return valor
    try:
        import streamlit as st
        valor = st.secrets.get(nome, padrao)
        return valor.strip() if isinstance(valor, str) else valor
    except Exception:
        return padrao


R2_ACCOUNT_ID = _cfg("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = _cfg("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = _cfg("R2_SECRET_ACCESS_KEY")
R2_BUCKET = _cfg("R2_BUCKET", "evidencias")
R2_PUBLIC_URL = (_cfg("R2_PUBLIC_URL") or "").rstrip("/")

SUPABASE_URL = (_cfg("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = _cfg("SUPABASE_KEY")

USA_R2 = all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_PUBLIC_URL])

_cliente_r2 = None


def _r2():
    global _cliente_r2
    if _cliente_r2 is None:
        import boto3
        _cliente_r2 = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
    return _cliente_r2


def _headers_supabase() -> dict:
    return {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}


def configurado() -> bool:
    return USA_R2 or bool(SUPABASE_URL and SUPABASE_KEY)


def prefixo_url_publica() -> str:
    """Prefixo das URLs públicas do backend ativo (usado no LIKE das limpezas)."""
    if USA_R2:
        return f"{R2_PUBLIC_URL}/"
    return f"{SUPABASE_URL}/storage/v1/object/public/evidencias/"


def nome_da_url(url: str) -> str:
    """Nome do arquivo no bucket a partir da URL pública gravada no banco."""
    return str(url).rsplit("/", 1)[-1]


def enviar(conteudo: bytes, nome_arquivo: str) -> str:
    """Envia (sobrescrevendo se já existir) e devolve a URL pública.
    Levanta exceção em caso de falha -- cada chamador decide o fallback."""
    if USA_R2:
        _r2().put_object(Bucket=R2_BUCKET, Key=nome_arquivo, Body=conteudo, ContentType="image/jpeg")
        return f"{R2_PUBLIC_URL}/{nome_arquivo}"

    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/evidencias/{nome_arquivo}",
        headers={**_headers_supabase(), "Content-Type": "image/jpeg", "x-upsert": "true"},
        data=conteudo,
        timeout=_TIMEOUT,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Erro Supabase ({resp.status_code}): {resp.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/evidencias/{nome_arquivo}"


def apagar(nome_arquivo: str) -> None:
    """Apaga um arquivo do bucket. Levanta exceção em caso de falha."""
    if USA_R2:
        _r2().delete_object(Bucket=R2_BUCKET, Key=nome_arquivo)
        return

    resp = requests.delete(
        f"{SUPABASE_URL}/storage/v1/object/evidencias/{nome_arquivo}",
        headers=_headers_supabase(),
        timeout=_TIMEOUT,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Supabase {resp.status_code} - {resp.text}")


def listar() -> list[dict]:
    """Todos os arquivos do bucket como [{"name": str, "created_at": datetime|str}]."""
    arquivos: list[dict] = []

    if USA_R2:
        paginador = _r2().get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=R2_BUCKET):
            for obj in pagina.get("Contents", []):
                arquivos.append({"name": obj["Key"], "created_at": obj["LastModified"]})
        return arquivos

    offset, pagina_tam = 0, 1000
    while True:
        resp = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/list/evidencias",
            headers=_headers_supabase(),
            json={"prefix": "", "limit": pagina_tam, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        pagina = resp.json()
        if not pagina:
            break
        arquivos.extend({"name": a.get("name") or "", "created_at": a.get("created_at")} for a in pagina)
        if len(pagina) < pagina_tam:
            break
        offset += pagina_tam
    return arquivos
