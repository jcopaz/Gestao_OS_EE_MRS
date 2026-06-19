import io
import os
import time
import base64
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Form, HTTPException, UploadFile, File, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
import requests

# ==============================================================================
# CONFIGURAÇÕES DE AMBIENTE (PRODUÇÃO)
# ==============================================================================
NEON_POSTGRES_URL = os.environ.get("NEON_POSTGRES_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
API_KEY_SECRET = os.environ.get("API_KEY_SECRET")

if not NEON_POSTGRES_URL:
    raise RuntimeError("Variável de ambiente NEON_POSTGRES_URL não configurada.")

if not API_KEY_SECRET:
    raise RuntimeError("Variável de ambiente API_KEY_SECRET não configurada.")

# ==============================================================================
# POOL DE CONEXÕES (THREAD-SAFE PARA PRODUÇÃO)
# ==============================================================================
pool_conexoes = None

def init_connection_pool():
    global pool_conexoes
    if pool_conexoes is None:
        max_retries = 3
        for tentativa in range(max_retries):
            try:
                pool_conexoes = psycopg2.pool.ThreadedConnectionPool(
                    1,
                    20,
                    dsn=NEON_POSTGRES_URL,
                    connect_timeout=10
                )
                break
            except psycopg2.OperationalError as e:
                if tentativa == max_retries - 1:
                    raise e
                time.sleep(2)


def get_connection():
    global pool_conexoes
    if pool_conexoes is None:
        init_connection_pool()
    conn = pool_conexoes.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception:
        try:
            pool_conexoes.putconn(conn, close=True)
        except Exception:
            pass
        conn = pool_conexoes.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn


def release_connection(conn):
    global pool_conexoes
    if pool_conexoes is not None and conn is not None:
        try:
            pool_conexoes.putconn(conn)
        except Exception:
            pass


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


def upload_foto_supabase(arquivo_bytes: bytes, nome_arquivo: str) -> str:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return ""
    upload_url = f"{SUPABASE_URL}/storage/v1/object/evidencias/{nome_arquivo}"
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
        bytes_comprimidos = arquivo_bytes
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "image/jpeg",
        "x-upsert": "true"
    }
    try:
        resp = requests.post(upload_url, headers=headers, data=bytes_comprimidos, timeout=30)
        if resp.status_code in (200, 201):
            return f"{SUPABASE_URL}/storage/v1/object/public/evidencias/{nome_arquivo}"
    except requests.RequestException:
        pass
    return ""

def upsert_evidencia(ativo: str, atividade: str, foto_url: str, os_referencia: str, concluido_por: str, geolocalizacao: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO evidencias (
                ativo, atividade, foto_url, os_referencia, concluido_por, geolocalizacao, data_upload
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (ativo, atividade) DO UPDATE SET
                foto_url = EXCLUDED.foto_url,
                os_referencia = EXCLUDED.os_referencia,
                concluido_por = EXCLUDED.concluido_por,
                geolocalizacao = EXCLUDED.geolocalizacao,
                data_upload = CURRENT_TIMESTAMP;
            """,
            (str(ativo), str(atividade), str(foto_url), str(os_referencia), str(concluido_por), str(geolocalizacao))
        )
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)

def upsert_baixa(os_id, status, realizado_em_str, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO baixas (
                os, status, realizado_em, coordenacao, concluido_por,
                geolocalizacao_baixa, equipe, data_inicio, hora_inicio,
                data_fim, hora_fim
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (os) DO UPDATE SET
                status = EXCLUDED.status,
                realizado_em = EXCLUDED.realizado_em,
                concluido_por = EXCLUDED.concluido_por,
                geolocalizacao_baixa = EXCLUDED.geolocalizacao_baixa,
                equipe = EXCLUDED.equipe,
                data_inicio = EXCLUDED.data_inicio,
                hora_inicio = EXCLUDED.hora_inicio,
                data_fim = EXCLUDED.data_fim,
                hora_fim = EXCLUDED.hora_fim;
            """,
            (str(os_id), str(status), str(realizado_em_str), str(coordenacao), str(concluido_por), str(geolocalizacao_baixa), str(equipe), str(data_inicio), str(hora_inicio), str(data_fim), str(hora_fim))
        )
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)

# ==============================================================================
# COORDENADAS FIXAS
# ==============================================================================
COORDENADAS_FIXAS = {
    "FPI": [-23.444413, -46.309269], "IAA": [-23.862936, -46.398189], "IAB": [-23.521338, -46.688570],
    "IBA": [-23.907681, -46.325638], "ICB": [-23.886147, -46.416167], "ICG": [-23.767863, -46.343114],
    "ICP": [-23.658495, -46.490753], "ICQ": [-23.926493, -46.402720], "ICR": [-23.640310, -46.323992],
    "ICZ": [-23.954824, -46.293306], "IEF": [-23.477809, -46.360984], "IES": [-23.545441, -46.603648],
    "IIP": [-23.564977, -46.604896], "IJN": [-23.195297, -46.870829], "IJU": [-23.889626, -46.338534], 
    "ILA": [-23.520217, -46.698082], "IMO": [-23.557803, -46.608382], "IOF": [-23.658579, -46.338538],
    "IPA": [-23.774399, -46.306769], "IPG": [-23.847950, -46.370812], "IPR": [-23.537749, -46.625522],
    "IQA": [-23.925948, -46.380123], "IQB": [-23.875674, -46.348587], "IRA": [-23.500572, -46.339448], 
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
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"]
)

init_connection_pool()

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
    foto: UploadFile = File(...)
):
    # 1) Origem inicial do GPS
    lat_final, lon_final = lat_browser, lon_browser
    fonte_gps = "Navegador"

    # 2) Fallback EXIF se navegador vier zerado
    if lat_browser == 0.0 and lon_browser == 0.0:
        imagem_bytes = await foto.read()
        imagem_pil = Image.open(io.BytesIO(imagem_bytes))
        lat_exif, lon_exif = extrair_gps_exif(imagem_pil)

        if lat_exif is not None and lon_exif is not None:
            lat_final, lon_final = lat_exif, lon_exif
            fonte_gps = "Foto (EXIF)"

        await foto.seek(0)

    # 3) Validação Antifraude por geofencing
    coordenada_ativo = COORDENADAS_FIXAS.get(ativo_id[:3], COORDENADAS_FIXAS["IPA"])
    lat_ativo, lon_ativo = coordenada_ativo[0], coordenada_ativo[1]

    dist_km = haversine_vectorized(lat_final, lon_final, pd.Series([lat_ativo]), pd.Series([lon_ativo]))[0]

    if dist_km > 2.0:
        raise HTTPException(status_code=403, detail=f"Bloqueio Geográfico: O apontamento foi realizado a {dist_km:.1f}km do ativo (Limite máximo: 2.0km). Verifique seu GPS.")

    # 4) Datas / horários
    hora_apontamento = datetime.fromisoformat(data_hora_local.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-3)))
    equipe_formatada = acompanhante.strip() if acompanhante.strip() else "Sozinho"

    # 5) Leitura da foto
    foto_bytes = await foto.read()
    geo_string = f"Offline Sync - {fonte_gps} (Lat: {lat_final:.6f}, Lon: {lon_final:.6f})"

    # 6) Upload ao Supabase e Gestão de Evidência
    nome_foto = f"{ativo_id}_OS{os_id}_{int(time.time())}.jpg".replace(" ", "_")
    url_supabase = upload_foto_supabase(foto_bytes, nome_foto)

    if url_supabase:
        upsert_evidencia(ativo=ativo_id, atividade="Baixa Offline", foto_url=url_supabase, os_referencia=os_id, concluido_por=usuario, geolocalizacao=geo_string)
    else:
        # Fallback emergencial: Salva direto e APENAS na tabela de evidencias.
        foto_b64 = f"data:image/jpeg;base64,{base64.b64encode(foto_bytes).decode('utf-8')}"
        upsert_evidencia(ativo=ativo_id, atividade="Baixa Offline", foto_url=foto_b64, os_referencia=os_id, concluido_por=usuario, geolocalizacao=geo_string)

    # 7) Persistência da baixa (Sem a coluna de foto, respeitando o schema do banco)
    upsert_baixa(
        os_id=os_id,
        status="Realizado",
        realizado_em_str=formatar_dt_br(hora_apontamento),
        coordenacao="Sincronização Offline",
        concluido_por=usuario,
        geolocalizacao_baixa=geo_string,
        equipe=equipe_formatada,
        data_inicio=hora_apontamento.strftime("%d/%m/%Y"),
        hora_inicio=horario_inicio,
        data_fim=hora_apontamento.strftime("%d/%m/%Y"),
        hora_fim=horario_fim
    )

    return {"status": "sucesso", "os_id": os_id, "dist_km": round(float(dist_km), 2), "fonte_gps": fonte_gps, "auditoria": "OK"}
