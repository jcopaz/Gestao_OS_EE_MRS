# ==============================================================================
# SGO Eletroeletrônica — Gestão_OS (migração única: fotos Supabase -> R2)
# Autor / Responsável pelo produto: Julio Copaz (julio.paz@mrs.com.br)
# Todos os direitos reservados. Uso, cópia ou distribuição não autorizados
# são proibidos.
# ==============================================================================
# Uso (variáveis de ambiente: NEON_POSTGRES_URL, SUPABASE_URL, R2_ACCOUNT_ID,
# R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_PUBLIC_URL, opcional R2_BUCKET):
#
#   python migrar_fotos_r2.py copiar        # copia p/ o R2 só as fotos que o
#                                           # Neon referencia (órfãs ficam p/ trás).
#                                           # Retomável: pula o que já está no R2.
#   python migrar_fotos_r2.py conferir      # todas as referenciadas existem no R2?
#   python migrar_fotos_r2.py trocar-urls   # UPDATE no Neon: URL Supabase -> R2
#                                           # (recusa se "conferir" não estiver 100%)
#   python migrar_fotos_r2.py reverter-urls # rollback: URL R2 -> Supabase
#
# Só lê do Supabase -- nada é apagado lá. O bucket antigo só deve ser apagado
# à mão, dias depois, com tudo validado em produção.
# ==============================================================================

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
import psycopg2
import requests
from botocore.config import Config
from botocore.exceptions import ClientError

def _env(nome: str, padrao: str | None = None) -> str:
    # .strip(): segredo colado com Enter no final (GitHub/Render) quebrava o
    # endpoint do R2 ("Invalid endpoint: https://<id>\n.r2.cloudflarestorage.com").
    valor = os.environ.get(nome, padrao)
    if valor is None:
        sys.exit(f"Variável de ambiente {nome} não configurada.")
    return valor.strip()


def _account_id() -> str:
    # Aceita só o Account ID ou o endpoint inteiro colado no segredo
    # ("https://<id>.r2.cloudflarestorage.com" virava "https://https:/<id>...").
    valor = _env("R2_ACCOUNT_ID")
    m = re.search(r"[0-9a-f]{32}", valor)
    return m.group(0) if m else valor


NEON_POSTGRES_URL = _env("NEON_POSTGRES_URL")
SUPABASE_URL = _env("SUPABASE_URL").rstrip("/")
R2_BUCKET = _env("R2_BUCKET", "evidencias")
R2_PUBLIC_URL = _env("R2_PUBLIC_URL").rstrip("/")

PREFIXO_SUPABASE = f"{SUPABASE_URL}/storage/v1/object/public/evidencias/"
PREFIXO_R2 = f"{R2_PUBLIC_URL}/"

# (tabela, coluna) que guardam URL pública de foto
COLUNAS_URL = [("evidencias", "foto_url"), ("baixas", "foto_evidencia")]

r2 = boto3.client(
    "s3",
    endpoint_url=f"https://{_account_id()}.r2.cloudflarestorage.com",
    aws_access_key_id=_env("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
    region_name="auto",
    # 1ª execução estourou 1h: pool padrão (10) < 16 threads e sem timeout de
    # leitura uma chamada travada segurava a thread indefinidamente.
    config=Config(max_pool_connections=32, connect_timeout=15, read_timeout=60,
                  retries={"max_attempts": 3, "mode": "standard"}),
)


def colunas_existentes(cur) -> list[tuple[str, str]]:
    cur.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
    )
    existentes = set(cur.fetchall())
    return [tc for tc in COLUNAS_URL if tc in existentes]


def nomes_referenciados(prefixo: str) -> set[str]:
    nomes: set[str] = set()
    with psycopg2.connect(NEON_POSTGRES_URL) as conn, conn.cursor() as cur:
        for tabela, coluna in colunas_existentes(cur):
            cur.execute(f"SELECT DISTINCT {coluna} FROM {tabela} WHERE {coluna} LIKE %s", (prefixo + "%",))
            nomes.update(url[len(prefixo):] for (url,) in cur.fetchall())
    return nomes


def existe_no_r2(nome: str) -> bool:
    try:
        r2.head_object(Bucket=R2_BUCKET, Key=nome)
        return True
    except ClientError:
        return False


def copiar_um(nome: str) -> str | None:
    if existe_no_r2(nome):
        return None
    resp = requests.get(PREFIXO_SUPABASE + nome, timeout=60)
    resp.raise_for_status()
    r2.put_object(Bucket=R2_BUCKET, Key=nome, Body=resp.content, ContentType="image/jpeg")
    return nome


def copiar() -> None:
    nomes = sorted(nomes_referenciados(PREFIXO_SUPABASE))
    print(f"{len(nomes)} fotos referenciadas no Neon apontando pro Supabase.")
    copiadas, erros = 0, []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futuros = {pool.submit(copiar_um, n): n for n in nomes}
        for i, fut in enumerate(as_completed(futuros), 1):
            try:
                if fut.result():
                    copiadas += 1
            except Exception as e:
                erros.append(f"{futuros[fut]}: {e}")
            if i % 250 == 0:
                print(f"  {i}/{len(nomes)} processadas -- copiadas agora: {copiadas}, erros: {len(erros)}")
    print(f"Copiadas agora: {copiadas} | já estavam no R2: {len(nomes) - copiadas - len(erros)} | erros: {len(erros)}")
    for e in erros[:50]:
        print("  ERRO", e)
    if erros:
        sys.exit("Rode 'copiar' de novo -- ele retoma só o que faltou.")


def existe_no_supabase(nome: str) -> bool | None:
    """True/False = existe ou não na origem; None = não deu pra saber (timeout etc.)."""
    try:
        resp = requests.head(PREFIXO_SUPABASE + nome, timeout=60)
    except requests.RequestException:
        return None
    if resp.status_code == 200:
        return True
    if resp.status_code in (400, 404):  # Supabase responde 400 pra objeto inexistente
        return False
    return None


def conferir() -> bool:
    nomes = nomes_referenciados(PREFIXO_SUPABASE) | nomes_referenciados(PREFIXO_R2)
    with ThreadPoolExecutor(max_workers=16) as pool:
        faltando = [n for n, ok in zip(nomes, pool.map(existe_no_r2, nomes)) if not ok]
        origem = list(pool.map(existe_no_supabase, faltando))
    # Foto que o Neon referencia mas que JÁ não existia no Supabase (link quebrado
    # antes da migração, ex.: convenção de nome antiga) não tem como ser copiada --
    # não bloqueia a virada; a URL continua quebrada, igual a hoje.
    quebradas = [n for n, o in zip(faltando, origem) if o is False]
    pendentes = [n for n, o in zip(faltando, origem) if o is not False]
    print(f"{len(nomes)} fotos referenciadas | faltando no R2: {len(pendentes)} | "
          f"já quebradas na origem (ignoradas): {len(quebradas)}")
    for n in quebradas[:50]:
        print("  QUEBRADA NA ORIGEM", n)
    for n in pendentes[:50]:
        print("  FALTA", n)
    return not pendentes


def trocar(de: str, para: str) -> None:
    with psycopg2.connect(NEON_POSTGRES_URL) as conn, conn.cursor() as cur:
        # Tudo numa transação só: ou troca todas as colunas, ou nenhuma.
        for tabela, coluna in colunas_existentes(cur):
            cur.execute(
                f"UPDATE {tabela} SET {coluna} = %s || substr({coluna}, %s) WHERE {coluna} LIKE %s",
                (para, len(de) + 1, de + "%"),
            )
            print(f"{tabela}.{coluna}: {cur.rowcount} URL(s) atualizadas")
    print("Commit feito.")


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else ""
    if acao == "copiar":
        copiar()
    elif acao == "conferir":
        if not conferir():
            sys.exit("Há fotos referenciadas que não estão no R2.")
    elif acao == "trocar-urls":
        if not conferir():
            sys.exit("Abortado: há fotos referenciadas que não estão no R2. Rode 'copiar' antes.")
        trocar(PREFIXO_SUPABASE, PREFIXO_R2)
    elif acao == "reverter-urls":
        trocar(PREFIXO_R2, PREFIXO_SUPABASE)
    else:
        sys.exit(__doc__ or "Ações: copiar | conferir | trocar-urls | reverter-urls")
