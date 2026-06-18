import io
import time
import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import pool
import streamlit as st
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Lógica de Retry para lidar com o "Cold Start" (Banco dormindo) do Neon PostgreSQL
pool_conexoes = None

def get_connection():
    global pool_conexoes
    if pool_conexoes is None:
        for tentativa in range(3):
            try:
                pool_conexoes = psycopg2.pool.SimpleConnectionPool(1, 20, st.secrets["NEON_POSTGRES_URL"])
                break
            except psycopg2.OperationalError as e:
                if tentativa == 2: 
                    raise e
                time.sleep(2) # Espera 2 segundos para o Neon acordar e tenta de novo
    return pool_conexoes.getconn()

def release_connection(conn):
    if pool_conexoes is not None:
        pool_conexoes.putconn(conn)

def formatar_dt_br(dt: datetime) -> str: 
    return dt.strftime("%d/%m/%Y %H:%M")

def haversine_vectorized(lat1, lon1, lat2_series, lon2_series):
    R = 6371.0
    lat1, lon1 = np.radians(float(lat1)), np.radians(float(lon1))
    lat2, lon2 = np.radians(lat2_series.astype(float).to_numpy()), np.radians(lon2_series.astype(float).to_numpy())
    a = np.sin((lat2 - lat1) / 2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2.0)**2
    return R * (2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a)))

# Converte formato graus/min/seg do EXIF para Decimal
def get_decimal_from_dms(dms, ref):
    try:
        degrees = float(dms[0])
        minutes = float(dms[1]) / 60.0
        seconds = float(dms[2]) / 3600.0
        dec = degrees + minutes + seconds
        if ref in ['S', 'W']:
            dec = -dec
        return round(dec, 6)
    except Exception:
        return None

# Extrai Latitude e Longitude da Foto
def extrair_gps_exif(image: Image.Image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return None, None

        gps_info = {}
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]

        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = get_decimal_from_dms(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
            lon = get_decimal_from_dms(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))
            return lat, lon
    except Exception as e:
        print(f"Erro ao ler EXIF: {e}")
    return None, None

def upsert_baixa(os_id, status, realizado_em_str, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO baixas (os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (os) DO UPDATE SET
                status = EXCLUDED.status, realizado_em = EXCLUDED.realizado_em, concluido_por = EXCLUDED.concluido_por,
                geolocalizacao_baixa = EXCLUDED.geolocalizacao_baixa, equipe = EXCLUDED.equipe, data_inicio = EXCLUDED.data_inicio,
                hora_inicio = EXCLUDED.hora_inicio, data_fim = EXCLUDED.data_fim, hora_fim = EXCLUDED.hora_fim;
        """, (str(os_id), str(status), str(realizado_em_str), str(coordenacao), str(concluido_por), str(geolocalizacao_baixa), str(equipe), str(data_inicio), str(hora_inicio), str(data_fim), str(hora_fim)))
        conn.commit()
        cur.close()
    finally: 
        release_connection(conn)

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

app_api = FastAPI(title="SGO MRS - Motor Antifraude")
app_api.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"],  # O "*" significa "Aceitar de qualquer origem, inclusive arquivos locais do celular"
    allow_credentials=True, 
    allow_methods=["*"],  # Aceitar métodos POST, GET, etc.
    allow_headers=["*"]   # Aceitar o cabeçalho FormData que usamos para mandar a foto
)

@app_api.post("/sincronizar_baixa_offline")
async def sincronizar_baixa_offline(
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
    # Lógica de Redundância: Tenta ler o EXIF se o navegador mandou 0.0
    lat_final, lon_final = lat_browser, lon_browser
    fonte_gps = "Navegador"

    if lat_browser == 0.0 and lon_browser == 0.0:
        # Carrega a imagem na memória para extrair metadados
        imagem_bytes = await foto.read()
        imagem_pil = Image.open(io.BytesIO(imagem_bytes))
        
        lat_exif, lon_exif = extrair_gps_exif(imagem_pil)
        if lat_exif is not None and lon_exif is not None:
            lat_final, lon_final = lat_exif, lon_exif
            fonte_gps = "Foto (EXIF)"

    # Validação Antifraude (Distância)
    coordenada_ativo = COORDENADAS_FIXAS.get(ativo_id[:3], COORDENADAS_FIXAS["IPA"])
    lat_ativo, lon_ativo = coordenada_ativo[0], coordenada_ativo[1]
    
    # Se ainda for 0.0 (Sem permissão e foto sem EXIF), a distância será alta e o auditor saberá.
    dist_km = haversine_vectorized(lat_final, lon_final, pd.Series([lat_ativo]), pd.Series([lon_ativo])).iloc[0]
    
    # Validação Antifraude (Tempo)
    hora_envio = datetime.now(timezone(timedelta(hours=-3)))
    hora_apontamento = datetime.fromisoformat(data_hora_local.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-3)))
    delta_minutos = (hora_envio - hora_apontamento).total_seconds() / 60.0
    
    if delta_minutos < 10 and dist_km > 5.0 and fonte_gps != "Navegador":
        raise HTTPException(status_code=403, detail="Fraude detectada: Deslocamento impossível no tempo informado.")
    
    equipe_formatada = acompanhante if acompanhante.strip() else "Sozinho"

    # Salva no Banco de Dados
    upsert_baixa(
        os_id=os_id, 
        status="Realizado", 
        realizado_em_str=formatar_dt_br(hora_apontamento), 
        coordenacao="Sincronização Offline", 
        concluido_por=usuario, 
        geolocalizacao_baixa=f"Offline Sync - {fonte_gps} (Lat: {lat_final:.6f}, Lon: {lon_final:.6f})",
        equipe=equipe_formatada, 
        data_inicio=hora_apontamento.strftime("%d/%m/%Y"), 
        hora_inicio=horario_inicio, 
        data_fim=hora_apontamento.strftime("%d/%m/%Y"), 
        hora_fim=horario_fim
    )

    return {
        "status": "sucesso", 
        "os_id": os_id, 
        "dist_km": round(dist_km, 2), 
        "fonte_gps": fonte_gps, 
        "auditoria": "OK"
    }