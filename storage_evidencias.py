# ==============================================================================
# SGO Eletroeletrônica — Gestão_OS (Storage das evidências fotográficas)
# Autor / Responsável pelo produto: Julio Copaz (julio.paz@mrs.com.br)
# Todos os direitos reservados. Uso, cópia ou distribuição não autorizados
# são proibidos.
# ==============================================================================
# Ponto ÚNICO de acesso ao bucket de fotos, usado por app.py (Streamlit) e
# api.py (FastAPI/Render). Destino único: Cloudflare R2.
# Histórico: migração Supabase Storage -> R2 em 04-06/10/2026 (o plano free do
# Supabase, 1 GB, não comporta o regime permanente da retenção CICLO + 30 dias,
# ~550 MB/mês de fotos -> 1,5-3 GB vivos; ver Agente/09_APRENDIZADOS_E_ERROS.md).
# Ramo Supabase REMOVIDO em 15/10/2026: o projeto "SGO EE" foi suspenso por
# limite do plano free (até 19/11) e todas as URLs no Neon já apontam pro R2 --
# manter o fallback só criava um destino morto que "parecia" estar configurado.
#
# Variáveis (env no Render, st.secrets no Streamlit Cloud -- mesmos nomes):
#   R2_ACCOUNT_ID + R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY + R2_PUBLIC_URL
#   (obrigatórias) e R2_BUCKET (opcional, padrão "evidencias").
# Faltando alguma, o IMPORT continua funcionando de propósito (derrubar o import
# derrubaria a API inteira no Render, inclusive baixas que nem usam foto): só as
# operações de storage levantam RuntimeError com os NOMES das variáveis ausentes.
# Rollback: não há mais backend alternativo -- é corrigir as variáveis R2_* ou
# reverter o commit.
#
# A URL pública gravada em evidencias.foto_url é sempre
# "<prefixo_url_publica()><nome do arquivo>" -- as rotinas de limpeza filtram
# por esse prefixo e recuperam o nome com nome_da_url().
# ==============================================================================

import os
import re


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
# Aceita só o Account ID ou o endpoint inteiro colado na variável
# ("https://<id>.r2.cloudflarestorage.com") -- fica só o ID de 32 hex.
if R2_ACCOUNT_ID:
    _m = re.search(r"[0-9a-f]{32}", R2_ACCOUNT_ID)
    if _m:
        R2_ACCOUNT_ID = _m.group(0)
R2_ACCESS_KEY_ID = _cfg("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = _cfg("R2_SECRET_ACCESS_KEY")
R2_BUCKET = _cfg("R2_BUCKET", "evidencias")
R2_PUBLIC_URL = (_cfg("R2_PUBLIC_URL") or "").rstrip("/")

_OBRIGATORIAS = {
    "R2_ACCOUNT_ID": R2_ACCOUNT_ID,
    "R2_ACCESS_KEY_ID": R2_ACCESS_KEY_ID,
    "R2_SECRET_ACCESS_KEY": R2_SECRET_ACCESS_KEY,
    "R2_PUBLIC_URL": R2_PUBLIC_URL,
}
USA_R2 = all(_OBRIGATORIAS.values())

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


def _exigir_r2() -> None:
    # Só os NOMES das variáveis ausentes vão na mensagem -- nunca os valores, porque
    # a exceção acaba no log do Render/Streamlit (visto por mais gente que os segredos).
    if not USA_R2:
        faltando = ", ".join(nome for nome, valor in _OBRIGATORIAS.items() if not valor)
        raise RuntimeError(f"Storage R2 nao configurado: faltam {faltando}")


def configurado() -> bool:
    return USA_R2


def prefixo_url_publica() -> str:
    """Prefixo das URLs públicas no R2 (usado no LIKE das limpezas)."""
    _exigir_r2()
    return f"{R2_PUBLIC_URL}/"


def nome_da_url(url: str) -> str:
    """Nome do arquivo no bucket a partir da URL pública gravada no banco."""
    return str(url).rsplit("/", 1)[-1]


def enviar(conteudo: bytes, nome_arquivo: str) -> str:
    """Envia (sobrescrevendo se já existir) e devolve a URL pública.
    Levanta exceção em caso de falha -- cada chamador decide o que fazer (na baixa
    offline vira 503 e a baixa NÃO é gravada; ver api.py)."""
    _exigir_r2()
    _r2().put_object(Bucket=R2_BUCKET, Key=nome_arquivo, Body=conteudo, ContentType="image/jpeg")
    return f"{R2_PUBLIC_URL}/{nome_arquivo}"


def apagar(nome_arquivo: str) -> None:
    """Apaga um arquivo do bucket. Levanta exceção em caso de falha."""
    _exigir_r2()
    _r2().delete_object(Bucket=R2_BUCKET, Key=nome_arquivo)


def listar() -> list[dict]:
    """Todos os arquivos do bucket como [{"name": str, "created_at": datetime}]."""
    _exigir_r2()
    arquivos: list[dict] = []
    paginador = _r2().get_paginator("list_objects_v2")
    for pagina in paginador.paginate(Bucket=R2_BUCKET):
        for obj in pagina.get("Contents", []):
            arquivos.append({"name": obj["Key"], "created_at": obj["LastModified"]})
    return arquivos
