# ==============================================================================
# SGO Eletroeletrônica — Gestão_OS (API de produção, FastAPI)
# Autor / Responsável pelo produto: Julio Copaz (julio.paz@mrs.com.br)
# Todos os direitos reservados. Uso, cópia ou distribuição não autorizados
# são proibidos.
# ==============================================================================

import io
import os
import re
import time
import threading
import unicodedata
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Form, HTTPException, UploadFile, File, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, JSONResponse
import uuid
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
import requests

import storage_evidencias

# ==============================================================================
# CONFIGURAÇÕES DE AMBIENTE (PRODUÇÃO)
# ==============================================================================
NEON_POSTGRES_URL = os.environ.get("NEON_POSTGRES_URL")
# Storage das fotos (Cloudflare R2): variáveis R2_* lidas em storage_evidencias.py
API_KEY_SECRET = os.environ.get("API_KEY_SECRET")

if not NEON_POSTGRES_URL:
    raise RuntimeError("Variável de ambiente NEON_POSTGRES_URL não configurada.")

if not API_KEY_SECRET:
    raise RuntimeError("Variável de ambiente API_KEY_SECRET não configurada.")


def _env_int_positivo(nome, padrao):
    # Env var mal preenchida no painel do Render (vazia, "30d", "-5") nao pode quebrar
    # o boot nem virar SQL estranho -- cai no padrao e avisa no log. Fica aqui em cima
    # (e nao junto do bloco PWA) porque o cooldown do banco logo abaixo tambem usa.
    try:
        valor = int(os.environ.get(nome, padrao))
        if valor > 0:
            return valor
    except (TypeError, ValueError):
        pass
    print(f"[ENV] {nome} invalido; usando padrao {padrao}.")
    return padrao


# ==============================================================================
# POOL DE CONEXÕES (THREAD-SAFE PARA PRODUÇÃO, CRIADO SOB DEMANDA)
# Incidente 10/10/2026: o Neon free estourou a cota ("exceeded the compute time
# quota"), init_connection_pool() rodava no import e relancava o erro -> uvicorn
# saia com exit 1 -> Render reiniciava em loop -> TUDO 503, inclusive /health (o
# app.py nem conseguia distinguir "API fora" de "banco fora"). Agora o pool so e
# criado na primeira requisicao que precisa de banco; sem banco, a API sobe, /health
# responde e as rotas de banco devolvem 503 com mensagem clara.
# Cooldown: depois de uma falha de conexao, as proximas requisicoes NAO tentam o
# Neon de novo por COOLDOWN_BANCO_S segundos -- com cota estourada, cada tentativa
# (x tecnicos sincronizando x retries do PWA) so piora a situacao e prende thread
# por ate connect_timeout. Falha rapida sem tocar no Neon e mais barato pra todos.
# ==============================================================================
pool_conexoes = None
_pool_lock = threading.Lock()
# time.monotonic(): imune a ajuste de relogio do servidor (NTP), que poderia
# prolongar ou zerar o cooldown sem querer.
_banco_indisponivel_ate = 0.0
COOLDOWN_BANCO_S = _env_int_positivo("DB_COOLDOWN_S", 30)


class BancoIndisponivel(Exception):
    """Banco (Neon) fora ou em cooldown. Vira HTTP 503 no handler global -- nunca
    deve ser engolida para cair num default de validacao (geofence, coordenacao)."""


def _msg_segura(e) -> str:
    # Mensagem do psycopg2 pode conter o DSN inteiro (com senha) -- e o log do Render
    # e visto por mais gente que o painel de env vars. Mascara antes de imprimir.
    try:
        msg = str(e)
    except Exception:
        msg = repr(type(e))
    if NEON_POSTGRES_URL:
        msg = msg.replace(NEON_POSTGRES_URL, "<dsn>")
    msg = re.sub(r"postgres(ql)?://\S+", "<dsn>", msg)
    msg = re.sub(r"password=\S+", "password=***", msg)
    msg = " ".join(msg.split())
    return msg[:300]


def _marcar_banco_indisponivel(e) -> None:
    global _banco_indisponivel_ate
    _banco_indisponivel_ate = time.monotonic() + COOLDOWN_BANCO_S
    print(f"[DB] Banco indisponivel (cooldown {COOLDOWN_BANCO_S}s): {_msg_segura(e)}")


def _verificar_cooldown() -> None:
    # Checagem barata, sem rede: durante o cooldown nem chega a tocar no Neon.
    if time.monotonic() < _banco_indisponivel_ate:
        raise BancoIndisponivel("cooldown")


def _obter_pool():
    global pool_conexoes
    _verificar_cooldown()
    if pool_conexoes is not None:
        return pool_conexoes
    with _pool_lock:
        # Double-check: varias requisicoes podem chegar juntas no boot frio; so a
        # primeira cria o pool, as outras esperam o lock e reaproveitam (ou pegam o
        # cooldown que a primeira acabou de marcar, sem nova tentativa no Neon).
        _verificar_cooldown()
        if pool_conexoes is not None:
            return pool_conexoes
        # UMA tentativa so (antes eram 3 com sleep): quem tenta de novo e a proxima
        # requisicao depois do cooldown, nao um loop prendendo a thread do request.
        try:
            pool_conexoes = psycopg2.pool.ThreadedConnectionPool(
                1,
                20,
                dsn=NEON_POSTGRES_URL,
                connect_timeout=10
            )
        except psycopg2.OperationalError as e:
            _marcar_banco_indisponivel(e)
            raise BancoIndisponivel("falha ao criar pool") from e
        return pool_conexoes


def init_connection_pool():
    # Mantido por compatibilidade (nome antigo); NAO e mais chamado no import.
    return _obter_pool()


def get_connection():
    p = _obter_pool()
    try:
        conn = p.getconn()
    except psycopg2.pool.PoolError as e:
        # Pool esgotado (20 conexoes em uso) e saturacao momentanea da API, nao banco
        # fora -- 503 sem cooldown, senao um pico de uso travaria todo mundo por 30s.
        raise BancoIndisponivel("pool esgotado") from e
    except psycopg2.OperationalError as e:
        _marcar_banco_indisponivel(e)
        raise BancoIndisponivel("falha ao conectar") from e
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception:
        # Conexao velha (Neon suspende por ociosidade e derruba o socket): descarta e
        # tenta UMA conexao nova. Se a nova tambem falhar, e o banco que esta fora.
        try:
            p.putconn(conn, close=True)
        except Exception:
            pass
    try:
        conn = p.getconn()
    except psycopg2.pool.PoolError as e:
        raise BancoIndisponivel("pool esgotado") from e
    except psycopg2.OperationalError as e:
        _marcar_banco_indisponivel(e)
        raise BancoIndisponivel("falha ao conectar") from e
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception as e:
        # Fecha sempre (nao vaza o slot do pool); so erro de conexao vira cooldown.
        try:
            p.putconn(conn, close=True)
        except Exception:
            pass
        if isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError)):
            _marcar_banco_indisponivel(e)
            raise BancoIndisponivel("conexao sem resposta") from e
        raise


def release_connection(conn):
    if pool_conexoes is not None and conn is not None:
        try:
            # Sem isso, uma query que falhou no meio (rede, valor invalido) devolvia a
            # conexao ao pool com a transacao ABORTADA -- a PROXIMA sincronizacao (de
            # qualquer tecnico, pool e compartilhado entre todas as requisicoes) pegava
            # essa mesma conexao e levava "current transaction is aborted" sem relacao
            # com o erro original. rollback() em conexao sem transacao pendente e no-op seguro.
            conn.rollback()
            pool_conexoes.putconn(conn)
        except Exception as e:
            # rollback falhou = conexao morta. Antes o except engolia e a conexao nunca
            # voltava ao pool (vazava 1 slot dos 20 por falha). Fecha e devolve o slot.
            # Nunca relanca: release roda em finally e nao pode mascarar o erro original.
            print(f"[DB] Falha ao devolver conexao ao pool; descartando: {_msg_segura(e)}")
            try:
                pool_conexoes.putconn(conn, close=True)
            except Exception as e2:
                print(f"[DB] Falha ao descartar conexao: {_msg_segura(e2)}")


# ==============================================================================
# SEGURANÇA: API KEY VIA HEADER
# ==============================================================================
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def validar_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY_SECRET:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return api_key


# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def formatar_dt_br(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")

def haversine_vectorized(lat1, lon1, lat2_series, lon2_series):
    R = 6371.0
    lat1, lon1 = np.radians(float(lat1)), np.radians(float(lon1))
    lat2 = np.radians(lat2_series.astype(float).to_numpy())
    lon2 = np.radians(lon2_series.astype(float).to_numpy())
    a = (np.sin((lat2 - lat1) / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2.0) ** 2)
    return R * (2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a)))


def get_decimal_from_dms(dms, ref):
    try:
        def _to_float(valor):
            if isinstance(valor, tuple) and len(valor) == 2 and valor[1] != 0:
                return float(valor[0]) / float(valor[1])
            return float(valor)
        graus, minutos, segundos = _to_float(dms[0]), _to_float(dms[1]), _to_float(dms[2])
        dec = graus + (minutos / 60.0) + (segundos / 3600.0)
        if str(ref).upper() in ["S", "W"]:
            dec = -dec
        return round(dec, 6)
    except (ValueError, TypeError, ZeroDivisionError, IndexError):
        return None


def extrair_gps_exif(imagem_pil: Image.Image):
    try:
        exif_data = imagem_pil._getexif()
        if not exif_data:
            return None, None
        gps_info = {}
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t, v in value.items():
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = v
                break
        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = get_decimal_from_dms(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
            lon = get_decimal_from_dms(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))
            if lat is not None and lon is not None:
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
    except Exception as e:
        print(f"[EXIF] Erro ao processar metadados da foto: {e}")
    return None, None


def _sanear_nome_arquivo(texto: str) -> str:
    """Remove acentos (NFKD) e forca ASCII puro -- \\w do Python e Unicode-aware por
    padrao e deixa letras acentuadas passarem (ex.: "RELE"), que o storage (Supabase na
    epoca, hoje R2) rejeitava na chave do objeto com 400 InvalidKey -- mantido no R2 pra
    chave/URL publica ficarem ASCII e estaveis. Mesmo criterio usado em app.py."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"[^\w\-.]", "_", texto, flags=re.ASCII)

def upload_foto_storage(arquivo_bytes: bytes, nome_arquivo: str) -> str:
    # Comprime e envia ao Cloudflare R2 (storage_evidencias.py). Falha de ENVIO ou
    # storage nao configurado PROPAGA a excecao (15/10/2026): antes devolvia "" e o
    # chamador gravava a foto em base64 direto no Neon -- inchava o banco (plano free,
    # incidente de cota de 10/10) e escondia a falha do storage. Quem chama decide.
    try:
        img = Image.open(io.BytesIO(arquivo_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=75, optimize=True)
        bytes_comprimidos = out.getvalue()
    except Exception:
        # Compressao e otimizacao, nao requisito: foto que o PIL nao abre (formato
        # raro, arquivo truncado) sobe como veio em vez de perder a evidencia.
        bytes_comprimidos = arquivo_bytes
    return storage_evidencias.enviar(bytes_comprimidos, nome_arquivo)


# Alias do nome antigo (pre-R2), caso algum script/import externo ainda use.
upload_foto_supabase = upload_foto_storage

# Versoes "_cur" (15/10/2026): executam o SQL num cursor recebido e NAO fazem commit.
# A baixa offline grava evidencia + baixa na MESMA transacao (um commit so): antes eram
# duas conexoes/commits separados e uma falha entre eles deixava evidencia sem baixa
# (OS com foto mas fora da Meta/backlog). As publicas abaixo continuam com a mesma
# assinatura e commit proprio para quem chama uma so (scripts/imports externos).
def _upsert_evidencia_cur(cur, ativo: str, atividade: str, foto_url: str, os_referencia: str, concluido_por: str, geolocalizacao: str):
    cur.execute(
        """
        INSERT INTO evidencias (
            ativo, atividade, foto_url, os_referencia, concluido_por, geolocalizacao, data_upload
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (os_referencia) DO UPDATE SET
            ativo = EXCLUDED.ativo,
            atividade = EXCLUDED.atividade,
            foto_url = EXCLUDED.foto_url,
            concluido_por = EXCLUDED.concluido_por,
            geolocalizacao = EXCLUDED.geolocalizacao,
            data_upload = CURRENT_TIMESTAMP;
        """,
        (str(ativo), str(atividade), str(foto_url), str(os_referencia), str(concluido_por), str(geolocalizacao))
    )


def _upsert_baixa_cur(cur, os_id, status, realizado_em_str, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim, causa_nrav="", texto_confirmacao=""):
    # causa_nrav/texto_confirmacao sempre entram no UPDATE (nao so no INSERT), mesmo vazios --
    # mesma logica do upsert_baixa espelhado em app.py: limpa resquicio de NRAV anterior quando
    # a OS e concluida de verdade depois.
    cur.execute(
        """
        INSERT INTO baixas (
            os, status, realizado_em, coordenacao, concluido_por,
            geolocalizacao_baixa, equipe, data_inicio, hora_inicio,
            data_fim, hora_fim, causa_nrav, texto_confirmacao, atualizado_em
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (os) DO UPDATE SET
            status = EXCLUDED.status,
            realizado_em = EXCLUDED.realizado_em,
            concluido_por = EXCLUDED.concluido_por,
            geolocalizacao_baixa = EXCLUDED.geolocalizacao_baixa,
            equipe = EXCLUDED.equipe,
            data_inicio = EXCLUDED.data_inicio,
            hora_inicio = EXCLUDED.hora_inicio,
            data_fim = EXCLUDED.data_fim,
            hora_fim = EXCLUDED.hora_fim,
            causa_nrav = EXCLUDED.causa_nrav,
            texto_confirmacao = EXCLUDED.texto_confirmacao,
            atualizado_em = NOW();
        """,
        (str(os_id), str(status), str(realizado_em_str), str(coordenacao), str(concluido_por), str(geolocalizacao_baixa), str(equipe), str(data_inicio), str(hora_inicio), str(data_fim), str(hora_fim), str(causa_nrav), str(texto_confirmacao))
    )


def upsert_evidencia(ativo: str, atividade: str, foto_url: str, os_referencia: str, concluido_por: str, geolocalizacao: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _upsert_evidencia_cur(cur, ativo, atividade, foto_url, os_referencia, concluido_por, geolocalizacao)
        conn.commit()
    finally:
        # release_connection faz rollback antes de devolver: se o execute falhou, a
        # conexao nao volta ao pool com transacao abortada.
        release_connection(conn)


def upsert_baixa(os_id, status, realizado_em_str, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim, causa_nrav="", texto_confirmacao=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _upsert_baixa_cur(cur, os_id, status, realizado_em_str, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim, causa_nrav, texto_confirmacao)
        conn.commit()
    finally:
        release_connection(conn)

# ==============================================================================
# COORDENADAS FIXAS
# ==============================================================================
COORDENADAS_FIXAS = {
    "FPI": [-23.444413, -46.309269], "IAA": [-23.862936, -46.398189], "IAB": [-23.521338, -46.688570],
    "IBA": [-23.907681, -46.325638], "ICB": [-23.886147, -46.416167], "ICG": [-23.767863, -46.343114],
    "ICP": [-23.658495, -46.490753], "ICQ": [-23.91531040683147, -46.41890410191962], "ICR": [-23.640310, -46.323992],
    "ICZ": [-23.954824, -46.293306], "IEF": [-23.477809, -46.360984], "IES": [-23.545441, -46.603648],
    "IIP": [-23.564977, -46.604896], "IJN": [-23.195297, -46.870829], "IJU": [-23.889626, -46.338534], 
    "ILA": [-23.520217, -46.698082], "IMO": [-23.557803, -46.608382], "IOF": [-23.658579, -46.338538],
    "IPA": [-23.774399, -46.306769], "IPG": [-23.847950, -46.370812], "IPN": [-23.948095774842265, -46.30579661328678], "IPR": [-23.537749, -46.625522],
    "IQA": [-23.925948, -46.380123], "IQB": [-23.875674, -46.348587], "IQC": [-23.91530182548477, -46.41890965645514], "IRA": [-23.500572, -46.339448], 
    "IRG": [-23.736705, -46.382241], "IRP": [-23.713578, -46.414862], "IRS": [-23.828162, -46.363101],
    "ISA": [-23.647553, -46.531007], "ISC": [-23.613874, -46.558834], "ISL": [-23.752383, -46.389262],
    "ISN": [-23.928399, -46.363015], "ISU": [-23.551210, -46.288671], "IUF": [-23.860615, -46.359726], 
    "IUT": [-23.624864, -46.544716], "IVP": [-23.848139, -46.390430], "OAR": [-23.500419, -46.339111],
    "OBF": [-23.525591, -46.666726], "OBR": [-23.545397, -46.616293], "OCE": [-23.484980, -46.481471],
    "OCV": [-23.525061, -46.333701], "OEG": [-23.498082, -46.519759], "OET": [-23.510887, -46.552273],
    "OGP": [-23.691962, -46.448784], "OIC": [-23.479040, -46.367395], "OIT": [-23.493970, -46.401392],
    "OLU": [-23.535423, -46.634503], "OMA": [-23.667910, -46.462083], "OMP": [-23.490530, -46.443668],
    "OPS": [-23.637494, -46.537198], "OSU": [-23.534010, -46.308025], "OTA": [-23.591863, -46.590075],
    "OTT": [-23.539844, -46.575501], "ZPD": [-22.363436, -48.711002], "ZPG": [-23.874149, -46.411283],
    "Sede IPA": [-23.767355, -46.344117], "Sede IPG": [-23.850772, -46.371760]
}

_PATIOS_VALIDOS = sorted(
    (k for k in COORDENADAS_FIXAS.keys() if not k.startswith("Sede")),
    key=len,
    reverse=True,
)


def resolver_patio_ativo(ativo_id: str) -> str | None:
    """Resolve o codigo de patio (3 letras) a partir do nome do ativo.

    Corrigido em 27/07/2026: a versao anterior so olhava os 3 primeiros
    caracteres (COORDENADAS_FIXAS.get(ativo_id[:3])) -- funciona pra ativos
    tipo "IPA_326_N1", mas falha pra ativos com convencao de nome diferente
    (ex.: "MF-SJU-ISN_ISN-TELECOM-ARCCCO5", onde o codigo do patio "ISN" nao
    esta no inicio). Nesses casos o prefixo nao batia com nada, e a versao
    fail-closed (imediatamente anterior a esta) bloqueava a sincronizacao
    mesmo com o tecnico fisicamente no patio certo -- confirmado em campo
    (22/07/2026): apontamento a 1,48km do patio real (ISN) foi rejeitado por
    medir a distancia contra Paranapiacaba (fallback antigo, ja removido),
    17,9km de distancia. Agora tenta, na ordem: prefixo exato -> busca do
    codigo em qualquer parte do nome (mesma logica de _resolver_patio, em
    app.py) -- so falha (None) se nenhuma das duas encontrar nada.
    """
    ativo_upper = str(ativo_id).strip().upper()
    prefixo = ativo_upper[:3]
    if prefixo in COORDENADAS_FIXAS:
        return prefixo
    for patio_candidato in _PATIOS_VALIDOS:
        if patio_candidato in ativo_upper:
            return patio_candidato
    return None


# ==============================================================================
# CONFIGURAÇÃO OPERACIONAL POR COORDENAÇÃO (Plano de Guerra)
# ==============================================================================
DEFAULTS_CONFIG_OPERACIONAL = {"geofence_km": 2.0, "trava_prioridade_ativa": True}


def carregar_config_operacional(coordenacao: str) -> dict:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT geofence_km, trava_prioridade_ativa, vigente_desde, vigente_ate "
            "FROM configuracoes_operacionais WHERE coordenacao = %s",
            (coordenacao,)
        )
        row = cur.fetchone()
        cur.close()
    except Exception as e:
        # Antes: except engolia e caia no DEFAULT (geofence 2 km) -- com o banco fora, a
        # coordenacao que tem override (ex.: geofence maior) era validada com o limite
        # errado e o tecnico levava "Bloqueio Geografico" falso (ou o contrario). Falha de
        # banco agora vira 503 (handler global): o PWA mantem a baixa e tenta de novo.
        # Default so quando o banco RESPONDEU que nao ha config vigente (abaixo).
        raise BancoIndisponivel("falha ao ler configuracoes_operacionais") from e
    finally:
        if conn is not None: release_connection(conn)

    if row is None:
        return dict(DEFAULTS_CONFIG_OPERACIONAL)

    geofence_km, trava_ativa, vigente_desde, vigente_ate = row
    agora = datetime.now()
    if (vigente_desde is not None and agora < vigente_desde) or (vigente_ate is not None and agora > vigente_ate):
        return dict(DEFAULTS_CONFIG_OPERACIONAL)

    return {"geofence_km": float(geofence_km), "trava_prioridade_ativa": bool(trava_ativa)}


# Valores que o pacote/planilha manda quando a coordenacao nao existe de fato (celula
# vazia virando "nan" no pandas, "N/D" do gerador do pacote etc.). Comparados em
# maiusculas depois do strip -- nunca podem virar nome de coordenacao gravado na baixa.
_COORDENACAO_AUSENTE = {"", "N/D", "NAN", "NONE", "NULL"}


def _coordenacao_valida(v) -> str | None:
    # Nao-str (None, ou o FieldInfo do Form quando a funcao e chamada direto em teste)
    # conta como ausente. Limite de 100 chars: campo vem do cliente (FormData), nao
    # deixa texto arbitrario gigante ir pra coluna coordenacao.
    if not isinstance(v, str):
        return None
    v = v.strip()
    if v.upper() in _COORDENACAO_AUSENTE:
        return None
    return v[:100]


def obter_coordenacao_da_os(os_id: str) -> str | None:
    # Devolve None quando o banco RESPONDEU e a OS nao esta em os_programadas (15/10/2026):
    # antes caia em "Paranapiacaba" fixo e a baixa de OS de outra coordenacao (plano
    # trocado depois do pacote publicado) era gravada e validada (geofence/config) como
    # se fosse de Paranapiacaba. Quem chama decide o fallback (campo do pacote) ou 422.
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT coordenacao FROM os_programadas WHERE os = %s", (str(os_id).strip(),))
        row = cur.fetchone()
        cur.close()
    except Exception as e:
        # Mesmo motivo de carregar_config_operacional: banco fora NAO pode virar "OS fora
        # do plano" (None) -- o chamador cairia no campo do pacote ou num 422 indevido.
        # Falha de banco = 503 (handler global) e o PWA reenvia depois.
        raise BancoIndisponivel("falha ao ler coordenacao da OS") from e
    finally:
        if conn is not None: release_connection(conn)

    if row and row[0]:
        return str(row[0]).strip()
    return None


# ==============================================================================
# APP FASTAPI (PRODUÇÃO)
# ==============================================================================
app_api = FastAPI(title="SGO MRS - API Produção", docs_url=None, redoc_url=None, openapi_url=None)

# OBRIGATÓRIO: Arquivos HTML offline (como o exportado no painel) enviam a requisição
# com "Origin: null". Para permitir a comunicação offline, o CORS deve conter "*".
# A segurança real está na APIKey enviada nos Headers.
app_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)


# ==============================================================================
# BANCO FORA -> 503 PADRONIZADO (em vez de 500 generico / processo morto)
# Chave "detail" de proposito: o PWA offline mostra errJson.detail ao tecnico. 503 +
# Retry-After diz ao cliente "tente de novo depois" -- a baixa fica na fila local do
# aparelho (IndexedDB) e nada se perde.
# ==============================================================================
_MSG_503 = "Banco de dados indisponível no momento. A baixa continua salva no aparelho; tente sincronizar novamente em alguns minutos."


async def _handler_banco_indisponivel(request, exc):
    # Erro de conexao que escapou do get_connection (ex.: Neon caiu no meio da query)
    # tambem arma o cooldown, senao a proxima requisicao martelaria o Neon de novo.
    if isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        _marcar_banco_indisponivel(exc)
    return JSONResponse(
        status_code=503,
        content={"detail": _MSG_503},
        headers={"Retry-After": str(COOLDOWN_BANCO_S)},
    )


async def _handler_pandas_db_error(request, exc):
    # pd.read_sql_query embrulha o erro do driver em pandas.errors.DatabaseError;
    # se a causa for conexao, e banco fora (503). Senao e erro de SQL/dado (500), sem
    # vazar a mensagem do driver na resposta.
    if isinstance(exc.__cause__, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return await _handler_banco_indisponivel(request, exc.__cause__)
    print(f"[DB] Erro em consulta pandas: {_msg_segura(exc)}")
    return JSONResponse(status_code=500, content={"detail": "Erro interno ao consultar o banco."})


for _exc_banco in (BancoIndisponivel, psycopg2.OperationalError, psycopg2.InterfaceError, psycopg2.pool.PoolError):
    app_api.add_exception_handler(_exc_banco, _handler_banco_indisponivel)
app_api.add_exception_handler(pd.errors.DatabaseError, _handler_pandas_db_error)

# Codigos de Justificativa Padrao aceitos no NRAV (IT-ENG-3113) -- so impedimento EXTERNO.
# E001 (Ativo Inativado) e E008 (Plano incompativel com o ativo) ficam de fora de proposito:
# pelo documento oficial sao causa de "Nao se Aplica" (cadastro errado), nao de NRAV (vistoria
# feita, impedimento externo). Mesma lista de app.py (_JUSTIFICATIVAS_NRAV) -- sem import
# cruzado entre os dois arquivos, mantida em paralelo aqui.
CODIGOS_NRAV_VALIDOS = {"E002", "E003", "E004", "E005", "E006", "E007", "E009", "E010", "E011"}

# init_connection_pool() NAO roda mais no import (incidente 10/10/2026, ver bloco do
# pool la em cima): Neon com cota estourada derrubava o boot inteiro. O pool nasce na
# primeira requisicao que precisa de banco (_obter_pool).

# ==============================================================================
# ENDPOINT PRINCIPAL
# ==============================================================================
@app_api.post("/sincronizar_baixa_offline")
async def sincronizar_baixa_offline(
    api_key: str = Security(validar_api_key),
    os_id: str = Form(...),
    ativo_id: str = Form(...),
    usuario: str = Form(...),
    lat_browser: float = Form(...),
    lon_browser: float = Form(...),
    data_hora_local: str = Form(...),
    acompanhante: str = Form(default=""),
    horario_inicio: str = Form(...),
    horario_fim: str = Form(...),
    tipo_baixa: str = Form(default="CONCLUSAO"),
    causa_nrav: str = Form(default=""),
    texto_confirmacao: str = Form(default=""),
    # Coordenacao embutida no pacote PWA na publicacao (15/10/2026). Fallback quando a OS
    # ja nao esta em os_programadas; pacotes antigos nao mandam (default "").
    coordenacao: str = Form(default=""),
    foto: UploadFile = File(...)
):
    # OS sempre como inteiro em texto ("23089830.0" -> "23089830"), mesma regra de
    # normalizar_numero_os em app.py -- pacote PWA gerado antes da correção ainda manda ".0".
    os_id = str(os_id).strip()
    if re.fullmatch(r"\d+\.0+", os_id):
        os_id = os_id.split(".", 1)[0]

    # 1) Origem do GPS: SOMENTE o navegador (localizacao obrigatoria no app).
    #    Redundancia de leitura EXIF removida: o app agora exige a coleta do GPS
    #    (online e offline) antes de gravar a baixa, entao nao ha fallback por foto.
    lat_final, lon_final = lat_browser, lon_browser
    fonte_gps = "Navegador"

    # 2) GPS obrigatorio: rejeita apontamento sem localizacao do navegador.
    if lat_browser == 0.0 and lon_browser == 0.0:
        raise HTTPException(status_code=400, detail="Localizacao obrigatoria nao recebida. Ative o GPS do aparelho e capture a localizacao antes de sincronizar a baixa.")

    # 3) Validação Antifraude por geofencing (limite configurável por coordenação)
    # Fail-closed: se o pátio do ativo não resolver para uma coordenada conhecida, a
    # sincronização é BLOQUEADA -- antes caía num default fixo (IPA), deixando a
    # validação de geofence passar contra o pátio errado (mesma classe de bug já
    # corrigida no fluxo online do app.py, seção 10.3.3). resolver_patio_ativo() tenta
    # prefixo E busca em qualquer parte do nome antes de desistir (ver docstring —
    # sem isso, ativos como "MF-SJU-ISN_..." eram bloqueados mesmo com o técnico
    # fisicamente no pátio certo).
    patio_ativo = resolver_patio_ativo(ativo_id)
    coordenada_ativo = COORDENADAS_FIXAS.get(patio_ativo) if patio_ativo else None
    if coordenada_ativo is None:
        raise HTTPException(status_code=400, detail=f"Não foi possível identificar o pátio do ativo '{ativo_id}' para validar a geolocalização. Contate o suporte antes de sincronizar.")
    lat_ativo, lon_ativo = coordenada_ativo[0], coordenada_ativo[1]

    dist_km = haversine_vectorized(lat_final, lon_final, pd.Series([lat_ativo]), pd.Series([lon_ativo]))[0]

    # Falha de banco aqui = BancoIndisponivel -> 503 ANTES do upload da foto (nao gasta
    # storage nem grava evidencia sem baixa). NUNCA cair em default de coordenacao/
    # geofence por falha de banco: validaria a baixa com a regra errada.
    # Prioridade (15/10/2026): os_programadas (fonte oficial) -> campo do pacote -> 422.
    # Sem nenhuma das duas NAO existe mais default fixo ("Paranapiacaba"): a baixa iria
    # pra coordenacao errada. 422 (nao 503) porque reenviar sozinho nao resolve -- precisa
    # republicar a rota; o PWA mostra o detail ao tecnico.
    coordenacao_banco = _coordenacao_valida(obter_coordenacao_da_os(os_id))
    coordenacao_os = coordenacao_banco or _coordenacao_valida(coordenacao)
    if coordenacao_os is None:
        raise HTTPException(status_code=422, detail=f"OS {os_id} não está no plano atual — republique a rota ou fale com o supervisor.")
    if coordenacao_banco is None:
        # Auditoria: rastrear baixas aceitas so com a coordenacao informada pelo cliente.
        print(f"[COORD] OS {os_id} fora de os_programadas; usando coordenacao do pacote: {coordenacao_os!r}")
    config_op = carregar_config_operacional(coordenacao_os)
    geofence_limite_km = config_op["geofence_km"]

    if dist_km > geofence_limite_km:
        raise HTTPException(status_code=403, detail=f"Bloqueio Geográfico: O apontamento foi realizado a {dist_km:.1f}km do ativo (Limite máximo: {geofence_limite_km:.1f}km). Verifique seu GPS.")

    # 3.1) NRAV (Não Realizado Após Vistoria, IT-ENG-3113, pedido 29/07/2026): fluxo distinto
    # da Conclusão -- valida ANTES do upload da foto (falha rápido, sem gastar upload pro
    # storage à toa). Causa validada contra a lista server-side (não confia só no <select> do
    # cliente) e Observações truncada em 40 chars (limite real do campo "Txt. confirmação" do
    # SAP, corrigido de 38 para 40 em 26/08/2026).
    tipo_baixa_norm = (tipo_baixa or "CONCLUSAO").strip().upper()
    causa_nrav_norm = causa_nrav.strip().upper()
    texto_confirmacao_norm = texto_confirmacao.strip()[:40]
    if tipo_baixa_norm == "NRAV":
        if causa_nrav_norm not in CODIGOS_NRAV_VALIDOS:
            raise HTTPException(status_code=400, detail=f"Causa NRAV inválida ou não informada: '{causa_nrav}'.")
        if not texto_confirmacao_norm:
            raise HTTPException(status_code=400, detail="Observações (Texto de confirmação) obrigatórias para registrar NRAV.")

    # 4) Datas / horários
    hora_apontamento = datetime.fromisoformat(data_hora_local.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-3)))
    equipe_formatada = acompanhante.strip() if acompanhante.strip() else "Sozinho"

    # 5) Leitura da foto
    foto_bytes = await foto.read()

    # 5.1) Evidencia fotografica obrigatoria: mesma logica de bloqueio do GPS (secao 2).
    #      Sem foto (arquivo ausente ou vazio) a baixa nao pode ser gravada.
    if not foto_bytes or len(foto_bytes) == 0:
        raise HTTPException(status_code=400, detail="Evidencia fotografica obrigatoria nao recebida. Anexe a foto antes de sincronizar a baixa.")

    geo_string = f"Offline Sync - {fonte_gps} (Lat: {lat_final:.6f}, Lon: {lon_final:.6f})"

    # 6) Upload ao storage (Cloudflare R2) e Gestão de Evidência
    # Nome fixo por OS (sem timestamp): reenvio da mesma baixa SOBRESCREVE a
    # foto em vez de criar arquivo novo. Com timestamp, cada reenvio virava um
    # órfão no bucket (~500 em out/2026) -- evidencias guarda 1 foto por OS.
    nome_foto = _sanear_nome_arquivo(f"{ativo_id}_OS{os_id}.jpg")
    # Falha no upload = 503 ANTES de gravar evidencia e baixa (15/10/2026). O antigo
    # "fallback emergencial" gravava a foto em base64 na coluna foto_url do Neon: cada
    # foto virava ~100-500 KB de texto no banco (plano free, que ja estourou cota em
    # 24/08 e 10/10) e a limpeza por prefixo de URL nunca apagava essas linhas. Com
    # 503 o PWA mantem a baixa pendente no aparelho (so marca "sincronizado" em 200) e
    # o tecnico reenvia depois -- nada se perde e o banco nao incha.
    try:
        url_foto = upload_foto_storage(foto_bytes, nome_foto)
    except Exception as e:
        # _msg_segura: a mensagem do boto3/RuntimeError nao deve levar nada sensivel
        # pro log; o RuntimeError de config ja traz so NOMES de variaveis.
        print(f"[STORAGE] Falha no upload de {nome_foto} (OS {os_id}): {type(e).__name__}: {_msg_segura(e)}")
        raise HTTPException(
            status_code=503,
            detail="Falha ao salvar a foto da evidência; a baixa NÃO foi gravada e continua salva no aparelho. Tente sincronizar novamente em alguns minutos.",
        )

    # 7) Persistência da baixa (Sem a coluna de foto, respeitando o schema do banco)
    # NRAV: status "ABER NRAV" (conta como Concluída na Meta, mas fica Aberta pro Backlog --
    # já tratado em app.py, região 1.3); Hora Início/Fim Real fixas em "00:00:00" (formato
    # exigido pelo export SAP), Data Início/Fim Real = data do apontamento (mesma data usada
    # na Conclusão normal, não a data de sincronização).
    data_ref_str = hora_apontamento.strftime("%d/%m/%Y")
    if tipo_baixa_norm == "NRAV":
        status_final = "ABER NRAV"
        hora_inicio_final = "00:00:00"
        hora_fim_final = "00:00:00"
        causa_final = causa_nrav_norm
        texto_final = texto_confirmacao_norm
    else:
        status_final = "Realizado"
        hora_inicio_final = horario_inicio
        hora_fim_final = horario_fim
        causa_final = ""
        texto_final = ""

    # 8) Evidencia + baixa numa TRANSACAO UNICA (15/10/2026): antes eram dois commits em
    # conexoes separadas -- se a baixa falhasse depois da evidencia, ficava foto gravada
    # sem baixa. Agora ou grava as duas ou nenhuma; o PWA so marca "sincronizado" em 200
    # e reenvia (UPSERT por OS, idempotente). A foto ja subiu ao R2 com nome fixo por OS,
    # entao o reenvio so sobrescreve o mesmo arquivo, sem orfao.
    # O except relanca a excecao ORIGINAL (sem virar HTTPException generico): erro de
    # conexao (OperationalError/InterfaceError) tem que chegar ao handler global -> 503.
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _upsert_evidencia_cur(cur, ativo=ativo_id, atividade="Baixa Offline", foto_url=url_foto, os_referencia=os_id, concluido_por=usuario, geolocalizacao=geo_string)
            _upsert_baixa_cur(
                cur,
                os_id=os_id,
                status=status_final,
                realizado_em_str=formatar_dt_br(hora_apontamento),
                coordenacao=coordenacao_os,
                concluido_por=usuario,
                geolocalizacao_baixa=geo_string,
                equipe=equipe_formatada,
                data_inicio=data_ref_str,
                hora_inicio=hora_inicio_final,
                data_fim=data_ref_str,
                hora_fim=hora_fim_final,
                causa_nrav=causa_final,
                texto_confirmacao=texto_final,
            )
        conn.commit()
    except Exception:
        # Rollback explicito antes de devolver; se a conexao morreu o rollback tambem
        # falha -- engole so ESSE erro pra nao mascarar o original.
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        release_connection(conn)

    return {"status": "sucesso", "os_id": os_id, "dist_km": round(float(dist_km), 2), "fonte_gps": fonte_gps, "auditoria": "OK"}


# ==============================================================================
# LIMPEZA DE EVIDENCIAS EXPIRADAS (ciclagem de fotos no storage Cloudflare R2)
# Expiracao = Data/Hora Realizado + Ciclo (dias, da planilha de OS Programadas) +
# 30 dias de folga. Sem Ciclo identificavel para a OS -> nunca expira (fail-safe).
# Apaga so o arquivo no Storage; a linha em "evidencias" continua existindo (so
# fica com foto_url vazio) para nao perder o historico/auditoria da baixa.
# dry_run=True por padrao -- so apaga de verdade com ?dry_run=false explicito.
# Bug corrigido em 26/07/2026: dados_completos->>'Ciclo' nunca batia com a coluna
# real da planilha SAP ("CICLO", maiusculo) -- busca de chave em JSON e sensivel
# a caixa, entao TODAS as 2015 evidencias existentes caiam em "sem Ciclo
# identificavel" e a limpeza nunca teve nenhuma candidata de verdade. Agora usa
# COALESCE tentando CICLO/Ciclo/ciclo, sem depender da grafia exata do upload.
# ==============================================================================
@app_api.post("/limpar_evidencias_expiradas")
async def limpar_evidencias_expiradas(
    api_key: str = Security(validar_api_key),
    dry_run: bool = True,
):
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT ev.id, ev.os_referencia, ev.foto_url, b.realizado_em,
                   COALESCE(op.dados_completos ->> 'CICLO', op.dados_completos ->> 'Ciclo', op.dados_completos ->> 'ciclo') AS ciclo_txt
            FROM evidencias ev
            JOIN baixas b ON TRIM(b.os) = TRIM(ev.os_referencia)
            LEFT JOIN os_programadas op ON TRIM(op.os) = TRIM(ev.os_referencia)
            WHERE ev.foto_url LIKE %s
            """,
            conn,
            params=(f"{storage_evidencias.prefixo_url_publica()}%",),
        )
    finally:
        release_connection(conn)

    candidatas, apagadas, erros = [], [], []
    agora_naive = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)

    for _, row in df.iterrows():
        ciclo = pd.to_numeric(row["ciclo_txt"], errors="coerce")
        if pd.isna(ciclo):
            continue  # sem Ciclo identificavel -- nunca expira, nao arrisca

        realizado_dt = pd.to_datetime(row["realizado_em"], dayfirst=True, errors="coerce")
        if pd.isna(realizado_dt):
            continue

        expira_em = realizado_dt.to_pydatetime() + timedelta(days=float(ciclo) + 30)
        if agora_naive < expira_em:
            continue  # ainda dentro da janela de retencao

        nome_arquivo = storage_evidencias.nome_da_url(row["foto_url"])
        candidatas.append({"os": row["os_referencia"], "arquivo": nome_arquivo, "expirou_em": str(expira_em)})

        if not dry_run:
            try:
                # Conexao ANTES de apagar o arquivo: se o banco caiu no meio do loop, o
                # arquivo NAO pode sumir do storage com a linha ainda apontando pra ele
                # (evidencia "fantasma" -- URL quebrada na auditoria).
                conn2 = get_connection()
                try:
                    storage_evidencias.apagar(nome_arquivo)
                    cur = conn2.cursor()
                    cur.execute("UPDATE evidencias SET foto_url = '' WHERE id = %s", (int(row["id"]),))
                    conn2.commit()
                    cur.close()
                finally:
                    release_connection(conn2)
                apagadas.append(row["os_referencia"])
            except BancoIndisponivel:
                # Banco fora: aborta a rodada inteira (503) em vez de acumular N erros
                # identicos e martelar o Neon a cada candidata.
                raise
            except Exception as e:
                erros.append(f"OS {row['os_referencia']}: {e}")

    return {
        "dry_run": dry_run,
        "total_candidatas": len(candidatas),
        "candidatas": candidatas,
        "apagadas": apagadas,
        "erros": erros,
    }


# ==============================================================================
# LIMPEZA DE EVIDENCIAS ORFAS (arquivo existe no Storage, mas nenhuma linha em
# "evidencias" aponta mais pra ele -- sobra de uploads duplicados/substituidos,
# achado em 26/07/2026: o botao "Sincronizar" do PWA offline nao tinha trava
# contra clique duplo, e cada toque extra reenviava a mesma foto com um nome
# novo. Corrigido no app.py; este endpoint e faxina pontual do que ja acumulou,
# nao precisa virar cron diario.
#
# Criterio diferente do endpoint acima (que usa Ciclo+30 dias): orfao nao tem
# mais "os_referencia" em evidencias, entao nao ha como calcular Ciclo pra ele
# -- o criterio aqui e "essa OS ja tem QUALQUER evidencia hoje?":
#   - Nome do arquivo tem "_OS<numero>_" E essa OS TEM linha em evidencias
#     (apontando pra outro arquivo, mais novo) -> seguro apagar, e redundante.
#   - Nome tem "_OS<numero>_" mas essa OS NAO TEM nenhuma linha em evidencias
#     -> pode ser a UNICA evidencia dessa OS (upload deu certo, gravacao no
#     banco falhou depois) -- NAO apaga, so lista pra revisao manual.
#   - Nome nao tem numero de OS identificavel (convencao antiga de nome) ->
#     NAO apaga, so lista separado (sem como verificar nada).
# Arquivo com menos de 24h de idade nunca entra em nenhum grupo -- pode ser
# upload em andamento (evidencia ainda nao gravada no banco).
# dry_run=True por padrao -- so apaga (grupo "seguro") de verdade com
# ?dry_run=false explicito.
# ==============================================================================
@app_api.post("/limpar_evidencias_orfas")
async def limpar_evidencias_orfas(
    api_key: str = Security(validar_api_key),
    dry_run: bool = True,
):
    conn = get_connection()
    try:
        df_ref = pd.read_sql_query(
            "SELECT foto_url, os_referencia FROM evidencias WHERE foto_url LIKE %s",
            conn,
            params=(f"{storage_evidencias.prefixo_url_publica()}%",),
        )
    finally:
        release_connection(conn)

    arquivos_referenciados = set(
        df_ref["foto_url"].astype(str).apply(storage_evidencias.nome_da_url)
    )
    # OS que ja tem QUALQUER evidencia hoje (mesmo que aponte pra outro arquivo) --
    # decide se um orfao foi substituido com seguranca ou e risco real.
    os_com_evidencia_atual = set(df_ref["os_referencia"].astype(str).str.strip())
    # os_referencia e UNIQUE em evidencias (ON CONFLICT (os_referencia) no upsert),
    # entao 1 foto_url atual por OS -- usado so pra prova/auditoria de que
    # "seguro_apagar" tem mesmo uma foto atual substituindo a orfa (pedido do
    # Julio em 27/07/2026 antes de autorizar a exclusao real dos 1.337).
    foto_atual_por_os = dict(zip(
        df_ref["os_referencia"].astype(str).str.strip(),
        df_ref["foto_url"].astype(str),
    ))

    todos_arquivos = storage_evidencias.listar()

    agora_utc = datetime.now(timezone.utc)
    # Sem exigir "_" depois do numero: revisao manual da amostra em 27/07/2026
    # achou pelo menos 9 arquivos com OS no final do nome, colada direto na
    # extensao (ex.: "..._OS23254048.jpg", sem "_" antes do ".jpg") -- o
    # padrao antigo (`_OS(\d+)_`) classificava esses como sem_os_identificavel
    # por engano. \d+ ja para sozinho no primeiro caractere nao-digito.
    padrao_os = re.compile(r"_OS(\d+)")

    seguro_apagar, revisar_manualmente, sem_os_identificavel = [], [], []

    for arq in todos_arquivos:
        nome = arq.get("name") or ""
        if not nome or nome == ".emptyFolderPlaceholder":
            continue
        if nome in arquivos_referenciados:
            continue  # tem dono hoje, nao e orfao

        criado_em = pd.to_datetime(arq.get("created_at"), errors="coerce", utc=True)
        if pd.isna(criado_em):
            continue  # sem data confiavel -- nao arrisca
        if agora_utc - criado_em.to_pydatetime() < timedelta(hours=24):
            continue  # upload recente demais -- pode estar em andamento, nao arrisca

        match_os = padrao_os.search(nome)
        if not match_os:
            sem_os_identificavel.append(nome)
            continue

        if match_os.group(1) in os_com_evidencia_atual:
            seguro_apagar.append({
                "arquivo_orfao": nome,
                "os": match_os.group(1),
                "foto_atual_da_mesma_os": foto_atual_por_os.get(match_os.group(1), ""),
            })
        else:
            revisar_manualmente.append(nome)

    apagadas, erros = [], []
    if not dry_run:
        for item in seguro_apagar:
            nome = item["arquivo_orfao"]
            try:
                storage_evidencias.apagar(nome)
                apagadas.append(nome)
            except Exception as e:
                erros.append(f"{nome}: {e}")

    return {
        "dry_run": dry_run,
        "total_no_bucket": len(todos_arquivos),
        "total_referenciados_hoje": len(arquivos_referenciados),
        "seguro_apagar": len(seguro_apagar),
        "revisar_manualmente": len(revisar_manualmente),
        "sem_os_identificavel": len(sem_os_identificavel),
        "apagadas": apagadas,
        "erros": erros,
        # Sem corte real pra revisar_manualmente/sem_os_identificavel: sao os
        # grupos que exigem revisao humana, response pequena (dezenas). Ficam
        # ANTES do campo gigante abaixo de proposito -- resposta grande demais
        # pra renderizar/copiar no navegador (achado em 27/07/2026: busca no
        # log do GitHub Actions nao encontrava nada depois do corte), entao o
        # que importa revisar tem que vir primeiro na resposta.
        "amostra_revisar_manualmente": revisar_manualmente[:500],
        "amostra_sem_os_identificavel": sem_os_identificavel[:500],
        # Lista completa (nao amostra) com o par arquivo-orfao / foto-atual-da-OS,
        # pra dar pra conferir individualmente que cada exclusao tem mesmo uma
        # evidencia atual substituindo -- nao e so a classificacao "confiar no
        # codigo", e a prova em si. Deliberadamente por ultimo (ver comentario
        # acima): e o campo mais pesado da resposta, de longe.
        "seguro_apagar_com_prova": seguro_apagar,
    }


# ==============================================================================
# HEALTHCHECK (pre-ping para acordar o Render antes de publicar/sincronizar)
# ==============================================================================
@app_api.get("/health")
async def health():
    return {"status": "ok"}


# ==============================================================================
# READINESS (o Render esta de pe E o banco responde?)
# Uso EXCLUSIVO do botao de publicar Rota PWA no app.py: confirma o Neon antes de
# mandar um HTML de varios MB, em vez de descobrir no meio do upload (503).
# NUNCA apontar monitor externo (UptimeRobot etc.) para /ready -- cada ping acorda
# o Neon free e queima as horas de compute do plano. Monitor, se houver, usa /health,
# que continua sem tocar no banco.
# ==============================================================================
@app_api.get("/ready")
def ready():
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok"}
    except Exception as e:
        # Log so no servidor; a resposta nao vaza DSN/host/mensagem do driver.
        print(f"[READY] Banco indisponivel: {_msg_segura(e)}")
        return JSONResponse(status_code=503, content={"status": "banco indisponivel"})
    finally:
        release_connection(conn)


# ==============================================================================
# PUBLICACAO DO PACOTE PWA
# Armazena o HTML self-contained e devolve uma URL HTTPS. Abrir a URL 1x online
# entrega o pacote em contexto seguro (isSecureContext=True) -> geolocation do
# navegador funciona, atendendo a regra de GPS obrigatorio (online e offline).
# ==============================================================================
def _garantir_tabela_pwa():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pwa_pacotes (
                id TEXT PRIMARY KEY,
                usuario TEXT,
                html TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)


# Roda UMA vez no boot (e a unica tentativa de banco no import: cria o pool sob
# demanda; se o Neon estiver fora, falha rapido, arma o cooldown e o boot segue). A
# chamada fica aqui porque a funcao so existe a partir deste ponto do modulo. Antes rodava a
# cada publicacao: um CREATE TABLE IF NOT EXISTS extra no Neon por clique, justo no
# momento mais pesado (upload de varios MB). Falha aqui NAO derruba o boot: o resto
# da API (sincronizacao, fotos) nao depende desta tabela; se ela nao existir, so a
# publicacao falha e o erro aparece no log abaixo.
# _tabela_pwa_ok: com o banco fora no boot (incidente 10/10/2026), a tentativa abaixo
# falha e a API sobe mesmo assim; a flag faz a PRIMEIRA publicacao depois que o banco
# voltar garantir a tabela (uma vez so), em vez de depender de um novo deploy.
# _env_int_positivo foi movida para o topo do arquivo (usada tambem pelo cooldown).
_tabela_pwa_ok = False
try:
    _garantir_tabela_pwa()
    _tabela_pwa_ok = True
except Exception as e:
    print(f"[PWA] Falha ao garantir tabela pwa_pacotes no boot: {_msg_segura(e)}")


# Teto do HTML publicado: o Render free tem 512 MB e o pacote passa inteiro pela
# memoria (bytes + str decodificada + parametro do INSERT ~= 3x o tamanho). Acima
# disso o processo pode morrer por OOM e o usuario so ve 503, sem explicacao.
PWA_MAX_HTML_MB = _env_int_positivo("PWA_MAX_HTML_MB", 8)
# Retencao dos pacotes: cada publicacao grava o HTML inteiro e nada apagava -- o Neon
# free tem 0,5 GB no total. Pacote antigo ja foi baixado pelo tecnico (fica offline
# no aparelho); se precisar de novo, basta republicar a rota. 1 dia (decisao do Julio,
# 15/10/2026): os tecnicos republicam a rota todo dia, entao pacote de ontem nao serve
# mais pra nada. A limpeza roda a cada publicacao, sem cron.
PWA_RETENCAO_DIAS = _env_int_positivo("PWA_RETENCAO_DIAS", 1)


@app_api.post("/publicar_pacote")
async def publicar_pacote(
    api_key: str = Security(validar_api_key),
    usuario: str = Form(...),
    html: UploadFile = File(...),
):
    # "html" vem como arquivo, nao campo de formulario -- campos de formulario comuns tem
    # teto de 1MB no Starlette/python-multipart; sem o limite de 100 OS por pacote (removido
    # a pedido), o HTML de uma rota grande passa disso facilmente.
    html_bytes = await html.read()
    # Checado ANTES do decode/INSERT: barra a rota gigante com mensagem clara (413) em vez
    # de triplicar o tamanho na memoria e arriscar OOM/503 no Render free.
    if len(html_bytes) > PWA_MAX_HTML_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Rota grande demais para publicar — reduza o raio de busca.",
        )
    html_str = html_bytes.decode("utf-8")

    pacote_id = uuid.uuid4().hex[:12]

    global _tabela_pwa_ok
    if not _tabela_pwa_ok:
        _garantir_tabela_pwa()
        _tabela_pwa_ok = True

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO pwa_pacotes (id, usuario, html) VALUES (%s, %s, %s);",
            (pacote_id, str(usuario), html_str),
        )
        # Limpeza dos pacotes vencidos na mesma transacao (sem job/cron extra -- o Render
        # free dorme). SAVEPOINT depois do INSERT: se o DELETE falhar, o ROLLBACK TO
        # desfaz so ele e a transacao NAO fica abortada -- a publicacao segue e commita.
        # O pacote recem-inserido tem criado_em = agora, entao nunca cai no filtro.
        # Dias vem de int validado (_env_int_positivo) e ainda assim vai como parametro.
        cur.execute("SAVEPOINT limpeza_pwa;")
        try:
            cur.execute(
                "DELETE FROM pwa_pacotes WHERE criado_em < NOW() - (%s * INTERVAL '1 day');",
                (PWA_RETENCAO_DIAS,),
            )
            cur.execute("RELEASE SAVEPOINT limpeza_pwa;")
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT limpeza_pwa;")
            print(f"[PWA] Falha ao limpar pacotes antigos (publicacao segue): {_msg_segura(e)}")
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)

    return {"status": "sucesso", "url": f"/pacote/{pacote_id}"}


@app_api.get("/pacote/{pacote_id}", response_class=HTMLResponse)
async def servir_pacote(pacote_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT html FROM pwa_pacotes WHERE id = %s;", (str(pacote_id),))
        row = cur.fetchone()
        cur.close()
    finally:
        release_connection(conn)

    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Pacote não encontrado ou expirado — peça para republicar a rota.")

    return HTMLResponse(content=row[0], status_code=200)
