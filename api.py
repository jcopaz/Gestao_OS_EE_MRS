import io
import os
import re
import hmac
import time
import base64
import hashlib
import unicodedata
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Form, HTTPException, UploadFile, File, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse
import uuid
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
# Chave dedicada para o endpoint /auth/validar (integracao SGO Workforce, ver
# ENDPOINT DE AUTENTICACAO abaixo) -- deliberadamente separada de
# API_KEY_SECRET (essa e' distribuida dentro do pacote HTML offline da PWA,
# entao um vazamento dela nunca deveria permitir validar login de usuario).
# Ao contrario de NEON_POSTGRES_URL/API_KEY_SECRET, NAO derruba o processo
# inteiro se estiver ausente -- so desativa esse endpoint especifico (ver
# validar_api_key_workforce), pra um deploy sem a variavel ainda configurada
# no Render nao quebrar /sincronizar_baixa_offline nem o resto da API.
WORKFORCE_API_KEY_SECRET = os.environ.get("WORKFORCE_API_KEY_SECRET")
# MESMO segredo que app.py le de st.secrets["AUTH_TOKEN_SECRET"] (Streamlit
# Cloud) -- precisa ser configurado aqui com o valor IDENTICO, senao o token
# gerado por um lado nunca valida do outro. Usado so para montar o link de
# SSO do EE17 (ver gerar_token_sessao/POST /auth/validar) -- decisao
# 2026-08-07: fica restrito aos dois deploys do proprio SGO (app.py e
# api.py), nunca e' entregue ao SGO Workforce. Tambem opcional no boot
# (mesmo motivo de WORKFORCE_API_KEY_SECRET): sem ela, /auth/validar
# continua validando login normalmente, so nao devolve "sid" na resposta.
AUTH_TOKEN_SECRET = os.environ.get("AUTH_TOKEN_SECRET")
# TTL curto (ver uso em auth_validar) -- nao reaproveita o default de 12h de
# gerar_token_sessao, pensado para outro uso (sobreviver a reconexao da
# camera em app.py). Aqui o token so precisa viver o suficiente pra um
# clique no botao "Abrir apontamento de OS no SGO" ser processado.
TTL_HORAS_SID_SSO = 5 / 60  # 5 minutos

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
    if pool_conexoes is not None and conn is not None:
        try:
            # Sem isso, uma query que falhou no meio (rede, valor invalido) devolvia a
            # conexao ao pool com a transacao ABORTADA -- a PROXIMA sincronizacao (de
            # qualquer tecnico, pool e compartilhado entre todas as requisicoes) pegava
            # essa mesma conexao e levava "current transaction is aborted" sem relacao
            # com o erro original. rollback() em conexao sem transacao pendente e no-op seguro.
            conn.rollback()
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


async def validar_api_key_workforce(api_key: str = Security(api_key_header)):
    # Fail closed: sem WORKFORCE_API_KEY_SECRET configurado no ambiente (Render),
    # NENHUMA chave passa -- nunca cai para trás em "sem checagem".
    if not WORKFORCE_API_KEY_SECRET or api_key != WORKFORCE_API_KEY_SECRET:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return api_key


def hash_senha(senha):
    # Mesma funcao de app.py (SESSAO 2.3, Login Padrao) -- sem import cruzado
    # entre os dois arquivos (deploys separados, ver Agente/09_APRENDIZADOS_E_ERROS.md),
    # mantida em paralelo aqui. Qualquer mudanca de algoritmo de hash em
    # app.py precisa ser replicada aqui manualmente, senao login via
    # /auth/validar para de bater com o hash gravado no cadastro.
    return hashlib.sha256(senha.encode()).hexdigest()


def gerar_token_sessao(username: str, ttl_horas: int = 12) -> str:
    # Copia EXATA de app.py (regiao 1.6, Persistencia de Sessao) -- mesmo
    # formato usuario|validade|HMAC, mesma codificacao base64. Precisa
    # continuar identica dos dois lados: um token gerado aqui so e' aceito
    # por app.py (validar_token_sessao) se AUTH_TOKEN_SECRET e o formato do
    # payload baterem byte a byte. So chamada depois de auth_validar ja ter
    # conferido a senha de verdade -- nunca gera token para um usuario sem
    # antes confirmar a senha dele (decisao 2026-08-07, ver ADR pendente).
    # int() em volta da soma inteira (nao so' time.time()) e' proposital:
    # ttl_horas fracionario (TTL_HORAS_SID_SSO = 5/60, ver uso abaixo) fazia
    # "int + float" virar float em Python - exp gravado como "...940.0" em
    # vez de "...940", e int("...940.0") SEMPRE falha (ValueError), engolido
    # em silencio pelo except Exception de validar_token_sessao (app.py).
    # Bug real: o sid de SSO nunca validou desde o primeiro dia, pra
    # qualquer TTL fracionario - nao era timing nem segredo divergente.
    exp = int(time.time() + ttl_horas * 3600)
    payload = f"{username}|{exp}"
    assin = hmac.new(AUTH_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{assin}".encode()).decode()


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
    padrao e deixa letras acentuadas passarem (ex.: "RELE"), que o Supabase Storage
    rejeita na chave do objeto com 400 InvalidKey. Mesmo criterio usado em app.py."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"[^\w\-.]", "_", texto, flags=re.ASCII)

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
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)

def upsert_baixa(os_id, status, realizado_em_str, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim, causa_nrav="", texto_confirmacao=""):
    # causa_nrav/texto_confirmacao sempre entram no UPDATE (nao so no INSERT), mesmo vazios --
    # mesma logica do upsert_baixa espelhado em app.py: limpa resquicio de NRAV anterior quando
    # a OS e concluida de verdade depois.
    conn = get_connection()
    try:
        cur = conn.cursor()
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
    except Exception:
        row = None
    finally:
        if conn is not None: release_connection(conn)

    if row is None:
        return dict(DEFAULTS_CONFIG_OPERACIONAL)

    geofence_km, trava_ativa, vigente_desde, vigente_ate = row
    agora = datetime.now()
    if (vigente_desde is not None and agora < vigente_desde) or (vigente_ate is not None and agora > vigente_ate):
        return dict(DEFAULTS_CONFIG_OPERACIONAL)

    return {"geofence_km": float(geofence_km), "trava_prioridade_ativa": bool(trava_ativa)}


def obter_coordenacao_da_os(os_id: str) -> str:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT coordenacao FROM os_programadas WHERE os = %s", (str(os_id).strip(),))
        row = cur.fetchone()
        cur.close()
    except Exception:
        row = None
    finally:
        if conn is not None: release_connection(conn)

    if row and row[0]:
        return str(row[0]).strip()
    return "Paranapiacaba"


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

# Codigos de Justificativa Padrao aceitos no NRAV (IT-ENG-3113) -- so impedimento EXTERNO.
# E001 (Ativo Inativado) e E008 (Plano incompativel com o ativo) ficam de fora de proposito:
# pelo documento oficial sao causa de "Nao se Aplica" (cadastro errado), nao de NRAV (vistoria
# feita, impedimento externo). Mesma lista de app.py (_JUSTIFICATIVAS_NRAV) -- sem import
# cruzado entre os dois arquivos, mantida em paralelo aqui.
CODIGOS_NRAV_VALIDOS = {"E002", "E003", "E004", "E005", "E006", "E007", "E009", "E010", "E011"}

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
    tipo_baixa: str = Form(default="CONCLUSAO"),
    causa_nrav: str = Form(default=""),
    texto_confirmacao: str = Form(default=""),
    foto: UploadFile = File(...)
):
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

    coordenacao_os = obter_coordenacao_da_os(os_id)
    config_op = carregar_config_operacional(coordenacao_os)
    geofence_limite_km = config_op["geofence_km"]

    if dist_km > geofence_limite_km:
        raise HTTPException(status_code=403, detail=f"Bloqueio Geográfico: O apontamento foi realizado a {dist_km:.1f}km do ativo (Limite máximo: {geofence_limite_km:.1f}km). Verifique seu GPS.")

    # 3.1) NRAV (Não Realizado Após Vistoria, IT-ENG-3113, pedido 29/07/2026): fluxo distinto
    # da Conclusão -- valida ANTES do upload da foto (falha rápido, sem gastar upload pro
    # Supabase à toa). Causa validada contra a lista server-side (não confia só no <select> do
    # cliente) e Observações truncada em 38 chars (limite do campo "Txt. confirmação" do SAP).
    tipo_baixa_norm = (tipo_baixa or "CONCLUSAO").strip().upper()
    causa_nrav_norm = causa_nrav.strip().upper()
    texto_confirmacao_norm = texto_confirmacao.strip()[:38]
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

    # 6) Upload ao Supabase e Gestão de Evidência
    nome_foto = _sanear_nome_arquivo(f"{ativo_id}_OS{os_id}_{int(time.time())}.jpg")
    url_supabase = upload_foto_supabase(foto_bytes, nome_foto)

    if url_supabase:
        upsert_evidencia(ativo=ativo_id, atividade="Baixa Offline", foto_url=url_supabase, os_referencia=os_id, concluido_por=usuario, geolocalizacao=geo_string)
    else:
        # Fallback emergencial: Salva direto e APENAS na tabela de evidencias.
        foto_b64 = f"data:image/jpeg;base64,{base64.b64encode(foto_bytes).decode('utf-8')}"
        upsert_evidencia(ativo=ativo_id, atividade="Baixa Offline", foto_url=foto_b64, os_referencia=os_id, concluido_por=usuario, geolocalizacao=geo_string)

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

    upsert_baixa(
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

    return {"status": "sucesso", "os_id": os_id, "dist_km": round(float(dist_km), 2), "fonte_gps": fonte_gps, "auditoria": "OK"}


# ==============================================================================
# LIMPEZA DE EVIDENCIAS EXPIRADAS (ciclagem de fotos no Supabase Storage)
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
            params=(f"{SUPABASE_URL}/storage/v1/object/public/evidencias/%",),
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

        nome_arquivo = str(row["foto_url"]).rsplit("/evidencias/", 1)[-1]
        candidatas.append({"os": row["os_referencia"], "arquivo": nome_arquivo, "expirou_em": str(expira_em)})

        if not dry_run:
            try:
                resp = requests.delete(
                    f"{SUPABASE_URL}/storage/v1/object/evidencias/{nome_arquivo}",
                    headers={"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY},
                    timeout=30,
                )
                if resp.status_code in (200, 204):
                    conn2 = get_connection()
                    try:
                        cur = conn2.cursor()
                        cur.execute("UPDATE evidencias SET foto_url = '' WHERE id = %s", (int(row["id"]),))
                        conn2.commit()
                        cur.close()
                    finally:
                        release_connection(conn2)
                    apagadas.append(row["os_referencia"])
                else:
                    erros.append(f"OS {row['os_referencia']}: Supabase {resp.status_code} - {resp.text}")
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
            params=(f"{SUPABASE_URL}/storage/v1/object/public/evidencias/%",),
        )
    finally:
        release_connection(conn)

    arquivos_referenciados = set(
        df_ref["foto_url"].astype(str).apply(lambda u: u.rsplit("/evidencias/", 1)[-1])
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

    todos_arquivos = []
    offset = 0
    pagina_tam = 1000
    while True:
        resp_list = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/list/evidencias",
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY},
            json={"prefix": "", "limit": pagina_tam, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
            timeout=30,
        )
        resp_list.raise_for_status()
        pagina = resp_list.json()
        if not pagina:
            break
        todos_arquivos.extend(pagina)
        if len(pagina) < pagina_tam:
            break
        offset += pagina_tam

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
                resp_del = requests.delete(
                    f"{SUPABASE_URL}/storage/v1/object/evidencias/{nome}",
                    headers={"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY},
                    timeout=30,
                )
                if resp_del.status_code in (200, 204):
                    apagadas.append(nome)
                else:
                    erros.append(f"{nome}: Supabase {resp_del.status_code} - {resp_del.text}")
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
# ENDPOINT DE AUTENTICACAO (integracao SGO Workforce, app irmao separado)
#
# Reaproveita a MESMA tabela `usuarios` do SGO (perfil/escopo/governanca) sem
# o Workforce precisar guardar a connection string do Postgres de producao --
# o Workforce so conhece WORKFORCE_API_KEY_SECRET (chave dedicada, nunca a
# credencial do banco). A comparacao de senha e' identica a' de app.py
# (SESSAO 2.3): compara hash_senha(senha) com usuarios.senha_hash, nunca
# devolve a resposta "usuario nao existe" separada de "senha errada" (evita
# enumeracao de usuario). senha_hash NUNCA entra na resposta.
# ==============================================================================
@app_api.post("/auth/validar")
async def auth_validar(
    api_key: str = Security(validar_api_key_workforce),
    username: str = Form(...),
    senha: str = Form(...),
):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT senha_hash, nome, perfil, escopo, reset_obrigatorio, governanca "
            "FROM usuarios WHERE username = %s",
            (username.strip(),),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        release_connection(conn)

    if not row or row[0] != hash_senha(senha):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    _senha_hash, nome, perfil, escopo, reset_obrigatorio, governanca = row
    if reset_obrigatorio == 1:
        # Mesma regra de app.py (SESSAO 2.3): usuario com senha pendente de
        # troca nao completa o login ate resetar -- o Workforce nao tem tela
        # de reset propria, entao recusa aqui em vez de deixar logar com
        # senha provisoria (fail closed).
        raise HTTPException(
            status_code=403,
            detail="Senha pendente de troca. Acesse o SGO para definir uma nova senha antes de entrar no Workforce.",
        )

    resposta = {
        "username": username.strip(),
        "nome": nome,
        "perfil": perfil,
        "escopo": escopo,
        "governanca": (governanca or "Mapa de Campo").split(","),
    }
    if AUTH_TOKEN_SECRET:
        # TTL curto de proposito (revisao de seguranca 2026-08-07): o sid
        # viaja na query string (?sid=...) do link aberto pelo EE17 do
        # Workforce, que fica gravado no historico do navegador e em logs
        # de acesso -- diferente do uso original em app.py (12h, token
        # sobrevive a reconexao da camera dentro da mesma sessao), aqui e'
        # so a ponte de um clique so entre os dois apps. Corrigir de vez
        # (cookie HttpOnly + endpoint de troca em app.py) fica para uma
        # decisao maior, registrada no ADR-0062 como pendente.
        resposta["sid"] = gerar_token_sessao(username.strip(), ttl_horas=TTL_HORAS_SID_SSO)
    return resposta


# ==============================================================================
# LISTAGEM DE USUARIOS CADASTRADOS (integracao SGO Workforce, feature
# "Equipe da jornada", 2026-08-12) -- usada pelo Workforce pra oferecer uma
# selecao de matricula real (em vez de texto livre) de quem mais participou
# da jornada. Protegida pela MESMA chave de /auth/validar
# (WORKFORCE_API_KEY_SECRET) -- nao exige senha de ninguem, so a chave de
# integracao.
#
# NOTA DE PRIVACIDADE: essa chave e' client-embedded (visivel no JS publico
# do Workforce, mesmo padrao ja documentado em configSgo.js -- nao e'
# segredo de verdade). Isso significa que qualquer pessoa que leia o
# codigo-fonte do site do Workforce consegue listar nome+matricula de TODO
# colaborador cadastrado no SGO. Por isso a resposta aqui e' deliberadamente
# minima -- nunca perfil/escopo/governanca (que revelariam cargo/lotacao),
# so o suficiente pra popular uma lista de selecao.
# ==============================================================================
@app_api.get("/usuarios")
async def listar_usuarios(api_key: str = Security(validar_api_key_workforce)):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT username, nome FROM usuarios ORDER BY nome")
        linhas = cur.fetchall()
        cur.close()
    finally:
        release_connection(conn)

    return [{"username": username, "nome": nome} for username, nome in linhas]


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
    html_str = html_bytes.decode("utf-8")

    _garantir_tabela_pwa()
    pacote_id = uuid.uuid4().hex[:12]

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO pwa_pacotes (id, usuario, html) VALUES (%s, %s, %s);",
            (pacote_id, str(usuario), html_str),
        )
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
        raise HTTPException(status_code=404, detail="Pacote nao encontrado ou expirado.")

    return HTMLResponse(content=row[0], status_code=200)
