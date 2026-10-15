# ==============================================================================
# SGO Eletroeletrônica — Gestão_OS (Script one-off: fotos base64 -> Cloudflare R2)
# Autor / Responsável pelo produto: Julio Copaz (julio.paz@mrs.com.br)
# Todos os direitos reservados. Uso, cópia ou distribuição não autorizados
# são proibidos.
# ==============================================================================
# Por quê (15/10/2026): 8 linhas de `evidencias` ficaram com foto_url =
# 'data:image/jpeg;base64,...' (~4 MB no total), gravadas pelo fallback antigo do
# PWA (removido do api.py no mesmo dia). Como a tabela é lida inteira com
# frequência, esses ~4 MB eram retransferidos do Neon em TODA leitura de
# evidencias -- egress do plano free (ver Agente/09_APRENDIZADOS_E_ERROS.md,
# entrada de 15/10/2026). Este script sobe cada foto pro R2 e troca o foto_url
# pela URL pública, mantendo data_upload e o resto da linha.
#
# USO (variáveis SÓ de ambiente; este script NUNCA lê .streamlit/secrets.toml):
#   NEON_POSTGRES_URL, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
#   R2_PUBLIC_URL (e R2_BUCKET, opcional, padrão "evidencias").
#
#   py migrar_fotos_base64.py              # dry-run (padrão): só lista, não envia
#   py migrar_fotos_base64.py --executar   # envia ao R2 e faz o UPDATE
#
# ATENÇÃO: execute FORA da pasta do projeto, ou com `py -I` e cwd diferente.
# storage_evidencias._cfg() cai para st.secrets quando a variável de ambiente
# falta, e dentro da pasta do projeto isso leria .streamlit/secrets.toml sem
# aviso. Por isso o script confere o ambiente ANTES de importar
# storage_evidencias e falha com mensagem clara se faltar algo.
# O dry-run só precisa de NEON_POSTGRES_URL; R2_* só são exigidas com --executar.
# Idempotente: o UPDATE só casa linhas que ainda são 'data:%', então rodar duas
# vezes é seguro. Commit por linha; falha numa linha não aborta as demais.
# ==============================================================================

import argparse
import base64
import io
import os
import re
import sys
import unicodedata

_VARS_R2 = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_URL")


def _sanear_nome_arquivo(texto: str) -> str:
    """Mesmo critério do api.py/app.py: remove acentos (NFKD) e força ASCII puro
    para a chave do objeto no R2 e a URL pública ficarem estáveis."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"[^\w\-.]", "_", texto, flags=re.ASCII)


def _comprimir(arquivo_bytes: bytes) -> bytes:
    """Mesma compressão do api.py (upload_foto_storage): 1280 px, JPEG q75,
    exif_transpose. Se o PIL não abrir, segue com o original (não perde a foto)."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(arquivo_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=75, optimize=True)
        return out.getvalue()
    except Exception:
        return arquivo_bytes


def _decodificar_data_uri(data_uri: str) -> bytes:
    """'data:image/jpeg;base64,XXXX' -> bytes."""
    cabecalho, sep, corpo = str(data_uri).partition(",")
    if not sep or ";base64" not in cabecalho:
        raise ValueError("foto_url nao e um data URI base64")
    return base64.b64decode(corpo, validate=False)


def _nome_destino(ativo, os_referencia) -> str:
    return _sanear_nome_arquivo(f"{ativo}_OS{os_referencia}.jpg")


def _exigir_ambiente(precisa_r2: bool) -> str:
    """Confere as variáveis ANTES de importar storage_evidencias. Devolve a URL do Neon."""
    nomes = ["NEON_POSTGRES_URL"] + (list(_VARS_R2) if precisa_r2 else [])
    faltando = [n for n in nomes if not (os.environ.get(n) or "").strip()]
    if faltando:
        # Só os NOMES, nunca os valores.
        raise SystemExit(
            "ERRO: variaveis de ambiente ausentes: " + ", ".join(faltando)
            + ". Defina-as no ambiente (este script nao le secrets.toml) e execute "
              "fora da pasta do projeto."
        )
    return os.environ["NEON_POSTGRES_URL"].strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Migra fotos base64 de evidencias para o R2.")
    ap.add_argument("--executar", action="store_true",
                    help="envia ao R2 e atualiza o banco (sem isso e dry-run)")
    args = ap.parse_args(argv)

    dsn = _exigir_ambiente(precisa_r2=args.executar)

    import psycopg2
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ativo, os_referencia, foto_url FROM evidencias "
                "WHERE foto_url LIKE 'data:%' ORDER BY id"
            )
            linhas = cur.fetchall()
        conn.commit()

        print(f"{len(linhas)} linha(s) com foto base64.")
        if not args.executar:
            for id_, ativo, os_ref, foto in linhas:
                print(f"  id={id_} os={os_ref} ativo={ativo} tamanho={len(foto)} chars "
                      f"-> {_nome_destino(ativo, os_ref)}")
            print("DRY-RUN: nada foi enviado nem atualizado. Use --executar para migrar.")
            return 0

        # Só aqui (ambiente já validado) é seguro importar o módulo de storage.
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import storage_evidencias

        ok, falhas = 0, []
        for id_, ativo, os_ref, foto in linhas:
            nome = _nome_destino(ativo, os_ref)
            try:
                conteudo = _comprimir(_decodificar_data_uri(foto))
                url = storage_evidencias.enviar(conteudo, nome)
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE evidencias SET foto_url=%s WHERE id=%s AND foto_url LIKE 'data:%%'",
                        (url, id_),
                    )
                conn.commit()
                ok += 1
                print(f"  OK id={id_} -> {url} ({len(conteudo)} bytes)")
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                falhas.append(id_)
                print(f"  FALHA id={id_} ({nome}): {type(e).__name__}: {e}")

        print(f"Resumo: {ok} migrada(s), {len(falhas)} falha(s)"
              + (f" (ids: {falhas})" if falhas else "") + ".")
        return 1 if falhas else 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
