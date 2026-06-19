#region SESSÃO 1: Imports, Configurações e Funções de Base

#region 1.1: Imports
import io
import time
import math
import re
import os
import shutil
import hashlib
import json
import psycopg2
import requests
import streamlit as st
import pandas as pd
import numpy as np
import folium
from PIL import Image, ImageOps
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from streamlit_js_eval import get_geolocation
from streamlit_echarts import st_echarts, JsCode
from datetime import datetime, timezone, timedelta
from pathlib import Path
from streamlit_calendar import calendar
from psycopg2.extras import execute_values
from psycopg2 import pool
#endregion 1.1

#region 1.2: Configurações Globais e Estilo Corporativo (Com Imagem)
st.set_page_config(page_title="Painel de OS Eletroeletrônica", layout="wide", initial_sidebar_state="collapsed")

if not st.session_state.get("logged_in", False):
    st.markdown("""
        <style>
        /* Imagem de Fundo com filtro de escurecimento ajustado para legibilidade */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), 
                        url("fundo.png") !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
        }
        
        /* Título com sombra para destacar sobre a imagem */
        .titulo-login {
            text-align: center; 
            color: #FFFFFF !important; 
            text-shadow: 2px 2px 8px rgba(0,0,0,0.8);
            font-size: 3rem !important;
            font-weight: 800 !important;
        }
        
        /* Card de Login translúcido (Vidro) */
        .stForm {
            background-color: rgba(0, 0, 0, 0.5) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 16px !important;
            padding: 40px !important;
            backdrop-filter: blur(8px); /* Efeito Glassmorphism */
        }
        
        /* Labels e Inputs brancos e legíveis */
        label { color: #FFFFFF !important; font-weight: 600 !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
        
        /* Botão Gradiente MRS */
        div.stButton > button {
            background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    col_vazia1, col_centro, col_vazia2 = st.columns([1, 1, 1])
    with col_centro:
        st.markdown("<h1 class='titulo-login'>⚡SGO Eletroeletrônica MRS</h1>", unsafe_allow_html=True)
#endregion 1.2

#region 1.3: Conexão com Banco de Dados e Constantes de Status
@st.cache_resource
def init_connection_pool():
    import time
    max_retries = 10
    
    for tentativa in range(max_retries):
        try:
            # Adicionando um timeout de conexão para não travar o pooler do Neon
            return psycopg2.pool.SimpleConnectionPool(
                1, 20, 
                dsn=st.secrets["NEON_POSTGRES_URL"],
                connect_timeout=10
            )
        except psycopg2.OperationalError as e:
            if tentativa == max_retries - 1:
                raise e # Se falhar 10 vezes, aí sim repassa o erro
            print(f"⚠️ Banco de dados Neon acordando... Tentativa {tentativa + 1} de {max_retries}. Aguardando 4 segundos.")
            time.sleep(4)

pool_conexoes = init_connection_pool()

def get_connection():
    global pool_conexoes # A declaração global OBRIGATORIAMENTE precisa ser a primeira linha
    
    # Tenta pegar a conexão do pool. Se estiver "morta" (fechada pelo Neon), recria o pool.
    try:
        conn = pool_conexoes.getconn()
        # Teste rápido ("ping") para ver se a conexão está realmente viva
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError):
        print("🔄 Conexão perdida ou inválida. Recriando conexão com o banco...")
        st.cache_resource.clear()
        pool_conexoes = init_connection_pool()
        return pool_conexoes.getconn()

def release_connection(conn):
    if pool_conexoes is not None:
        try:
            pool_conexoes.putconn(conn)
        except Exception:
            pass # Ignora erros ao devolver conexões mortas ao pool

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

_status_prazo  = {"REALIZADO"}
_status_atraso = {"REALIZADO FORA DA DATA DE PROGRAMAÇÃO", "REALIZADO FORA DO PRAZO"}
_status_aberto = {"NÃO REALIZADO", "NAO REALIZADO", "PENDENTE", "ATRASADO", ""}
#endregion 1.3

#region 1.4: Inicialização do Banco de Dados (init_db)
def init_db():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS baixas (
                os VARCHAR(255) PRIMARY KEY, status VARCHAR(255) NOT NULL, 
                realizado_em VARCHAR(255) NOT NULL, coordenacao VARCHAR(255) NOT NULL, concluido_por VARCHAR(255)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                username VARCHAR(255) PRIMARY KEY, nome VARCHAR(255), senha_hash VARCHAR(255) NOT NULL, 
                perfil VARCHAR(50) NOT NULL, escopo VARCHAR(50) NOT NULL,
                palavra_recuperacao VARCHAR(255) DEFAULT 'PENDENTE', dica_recuperacao VARCHAR(255) DEFAULT 'PENDENTE', 
                reset_obrigatorio INTEGER DEFAULT 1, coordenacao_padrao VARCHAR(100) DEFAULT 'ICG'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs_acesso (
                id SERIAL PRIMARY KEY, username VARCHAR(255) NOT NULL, data_hora_login TIMESTAMP NOT NULL,
                data_hora_logout TIMESTAMP, geolocalizacao_login VARCHAR(255), sessao_ativa BOOLEAN DEFAULT TRUE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS os_programadas (
                id SERIAL PRIMARY KEY, os VARCHAR(255) UNIQUE NOT NULL, mes_referencia VARCHAR(50),
                dados_completos JSONB, data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS evidencias (
                id SERIAL PRIMARY KEY, ativo VARCHAR(255) NOT NULL, atividade VARCHAR(500) NOT NULL,
                foto_url TEXT, os_referencia VARCHAR(255), concluido_por VARCHAR(255),
                geolocalizacao VARCHAR(255), data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ativo, atividade)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mapeamento_patios (
                ativo_chave VARCHAR(500) PRIMARY KEY, patio VARCHAR(10) NOT NULL,
                tipo VARCHAR(20) DEFAULT 'Ativo', data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # --- ATUALIZAÇÕES AUTOMÁTICAS DE ESTRUTURA ---
        try: cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS governanca VARCHAR(255) DEFAULT 'Painel Gerencial,Mapa de Campo';")
        except Exception: conn.rollback()
        
        try: cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome VARCHAR(255);")
        except Exception: conn.rollback()
        
        try: cur.execute("ALTER TABLE os_programadas ADD COLUMN IF NOT EXISTS coordenacao VARCHAR(100);")
        except Exception: conn.rollback()

        try:
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS geolocalizacao_baixa VARCHAR(255);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS equipe TEXT;")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS data_inicio VARCHAR(50);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS hora_inicio VARCHAR(50);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS data_fim VARCHAR(50);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS hora_fim VARCHAR(50);")
        except Exception: conn.rollback()
        
        # Criar o admin mestre se não existir
        cur.execute("SELECT COUNT(*) FROM usuarios")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO usuarios (username, nome, senha_hash, perfil, escopo, reset_obrigatorio, governanca) 
                VALUES (%s, %s, %s, %s, %s, 1, %s)
            """, ('admin', 'Administrador do Sistema', hash_senha('mrs123'), 'Gerência', 'Todas', 'Painel Gerencial,Mapa de Campo,Upload de Dados,Gestão de Usuários'))
            
        conn.commit()
        cur.close()
    except Exception as e:
        import logging
        logging.warning(f"[init_db] Erro na inicialização do banco: {e}")
    finally:
        if conn is not None: release_connection(conn)
init_db()
#endregion 1.4

#region 1.5: Inicialização Centralizada do Session State
_defaults_session = {
    "gps_pending": False, "gps_trials": 0, "origem_tipo": "BASE", "gov_auth_ok": False,
}
for _key, _val in _defaults_session.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val
#endregion
#endregion SESSÃO 1

#region 2.1: Barreira de Login com Governança e GPS Obrigatório
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": "", "perfil": "", "escopo": "", "governanca": "", "needs_reset": False, "validando_gps": False})

if not st.session_state["logged_in"]:
    st.markdown("<h3 style='text-align: center; color: ##FFFFFF;'>Acesso Restrito</h3>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    
    with col_l2:
#endregion

#region 2.2: Etapa 3 — Reset de Senha
        if st.session_state.get("needs_reset"):
            st.warning("⚠️ Configure sua senha e sua palavra de recuperação.")
            with st.form("form_reset"):
                nova_senha = st.text_input("Nova Senha", type="password")
                conf_senha = st.text_input("Confirmar Nova Senha", type="password")
                palavra_nova = st.text_input("Palavra-Chave de Recuperação")
                if st.form_submit_button("Finalizar Cadastro"):
                    if nova_senha != conf_senha: st.error("As senhas não conferem.")
                    elif not palavra_nova: st.error("Defina uma palavra-chave!")
                    else:
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE usuarios SET senha_hash = %s, palavra_recuperacao = %s, reset_obrigatorio = 0 WHERE username = %s", (hash_senha(nova_senha), palavra_nova.strip(), st.session_state["reset_user"]))
                        conn.commit()
                        cur.close()
                        release_connection(conn)
                        st.success("Concluído! Entre com sua nova senha."); st.session_state["needs_reset"] = False; st.rerun()
            if st.button("⬅️ Voltar"): st.session_state["needs_reset"] = False; st.rerun()
#endregion

#region 2.3: Etapa 2 — GPS Obrigatório
        elif st.session_state.get("validando_gps"):
            st.info("📍 **Para acessar o conteúdo é necessário a ativação do GPS.** Por favor, clique em 'Permitir' no aviso do seu navegador.")
            loc_login = get_geolocation()
            
            if loc_login and isinstance(loc_login, dict) and "coords" in loc_login:
                coords = loc_login.get("coords", {})
                lat_log = coords.get("latitude")
                lon_log = coords.get("longitude")
                
                if lat_log is not None and lon_log is not None:
                    geo_str = f"Lat: {lat_log}, Lon: {lon_log}"
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO logs_acesso (username, data_hora_login, geolocalizacao_login)
                        VALUES (%s, CURRENT_TIMESTAMP, %s)
                    """, (st.session_state["temp_user"], geo_str))
                    conn.commit()
                    cur.close()
                    release_connection(conn)
                    
                    st.session_state.update({
                        "logged_in": True, "username": st.session_state["temp_user"],
                        "perfil": st.session_state["temp_perfil"], "escopo": st.session_state["temp_escopo"],
                        "governanca": st.session_state["temp_gov"]
                    })
                    st.session_state["validando_gps"] = False
                    st.rerun()
                    
            elif loc_login and isinstance(loc_login, dict) and "error" in loc_login:
                st.error("🛑 **Acesso Bloqueado:** O sistema exige a leitura do seu GPS. Verifique se o GPS está ligado e o navegador tem permissão.")
                if st.button("⬅️ Voltar para o Login"):
                    st.session_state["validando_gps"] = False
                    st.rerun()
#endregion

#region 2.4: Etapa 1 — Login Padrão
        else:
            with st.form("form_login"):
                user_input = st.text_input("Matrícula / Usuário")
                pass_input = st.text_input("Senha", type="password")
                submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT senha_hash, perfil, escopo, reset_obrigatorio, governanca FROM usuarios WHERE username = %s", (user_input.strip(),))
                row = cur.fetchone()
                cur.close()
                release_connection(conn)
                
                if row and row[0] == hash_senha(pass_input):
                    if row[3] == 1:
                        st.session_state["needs_reset"] = True
                        st.session_state["reset_user"] = user_input.strip()
                        st.rerun()
                    else:
                        st.session_state["temp_user"] = user_input.strip()
                        st.session_state["temp_perfil"] = row[1]
                        st.session_state["temp_escopo"] = row[2]
                        st.session_state["temp_gov"] = row[4] or "Mapa de Campo"
                        
                        if row[1] == "Técnico": st.session_state["validando_gps"] = True
                        else:
                            st.session_state.update({
                                "logged_in": True, "username": st.session_state["temp_user"],
                                "perfil": st.session_state["temp_perfil"], "escopo": st.session_state["temp_escopo"],
                                "governanca": st.session_state["temp_gov"]
                            })
                        st.rerun()
                else: st.error("❌ Usuário ou senha incorretos.")
    st.stop()
#endregion

#endregion SESSÃO 2

#region SESSÃO 3: Funções (Lógica, Utilidades, GPS, Persistência)

#region 3.1: Lógica

#region 3.1.1: Normalização e Leitura de Colunas
def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.replace('\n', ' ').str.replace('\r', '').str.strip().str.upper()
    return df

def pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns: return c
    return None
#endregion 3.1.1

#region 3.1.2: Classificação de Atividades e Criticidade
def classificar_atividade(atividade: str) -> str:
    s = str(atividade).upper()
    if "_MAN_CONF_" in s: return "Confiabilidade e Segurança"
    if "_SEG_" in s: return "Segurança"
    if "_CONF_" in s: return "Confiabilidade"
    return "Confiabilidade"

def extrair_criticidade(prioridade: str):
    p = str(prioridade).strip()
    m = re.match(r"^\s*([1-4])\s*[-–]?\s*(.*)$", p)
    if m:
        codigo = int(m.group(1))
        mapa = {1: "Muito Alta", 2: "Alta", 3: "Média", 4: "Baixa"}
        return codigo, mapa.get(codigo, "Baixa")

    pu = p.upper()
    if "MUITO" in pu and "ALTA" in pu: return 1, "Muito Alta"
    if "ALTA" in pu: return 2, "Alta"
    if "MÉDIA" in pu or "MEDIA" in pu: return 3, "Média"
    if "BAIXA" in pu: return 4, "Baixa"
    return 4, "Baixa"

def calcular_nivel_prioridade(classificacao: str, criticidade_rank: int) -> int:
    base_map = {"Confiabilidade e Segurança": 1, "Segurança": 2, "Confiabilidade": 3}
    base = base_map.get(classificacao, 3)
    return base * 10 + int(criticidade_rank)
#endregion 3.1.2

#region 3.1.3: Funções de Data/Hora e Status de Execução
def parse_data_programada(valor):
    if pd.isna(valor): return pd.NaT
    try: return pd.to_datetime(valor, dayfirst=True, errors="coerce")
    except Exception: return pd.NaT

def agora_dt():
    return datetime.now(timezone(timedelta(hours=-3)))

def formatar_dt_br(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")

def determinar_status_execucao(data_programada: pd.Timestamp, realizado_em: datetime) -> str:
    if pd.isna(data_programada): return "Realizado"
    data_prog_dia = pd.to_datetime(data_programada).date()
    data_real_dia = realizado_em.date()
    if data_real_dia <= data_prog_dia: return "Realizado"
    return "Realizado Fora da Data de Programação"
#endregion 3.1.3

#region 3.1.4: Cálculo de Distância Geográfica (Haversine)
def haversine_vectorized(lat1, lon1, lat2_series, lon2_series):
    R = 6371.0
    lat1 = np.radians(float(lat1))
    lon1 = np.radians(float(lon1))
    lat2 = np.radians(lat2_series.astype(float).to_numpy())
    lon2 = np.radians(lon2_series.astype(float).to_numpy())
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c
#endregion 3.1.4

#region 3.1.5: Geocodificação e Tratamento KML
@st.cache_data(show_spinner=False)
def reverse_geocode_coordenada(lat: float, lon: float) -> str:
    try:
        geolocator = Nominatim(user_agent="gestao_os_eletro_mrs", timeout=10)
        location = geolocator.reverse((float(lat), float(lon)), exactly_one=True, language="pt-BR", addressdetails=True)
        if not location: return "GPS Local"
        addr = getattr(location, "raw", {}).get("address", {})
        rua = (addr.get("road") or addr.get("pedestrian") or addr.get("residential") or addr.get("footway") or "").strip()
        numero = (addr.get("house_number") or "").strip()
        bairro = (addr.get("suburb") or addr.get("neighbourhood") or "").strip()
        cidade = (addr.get("city") or addr.get("town") or "").strip()
        partes = []
        if rua and numero: partes.append(f"{rua}, {numero}")
        elif rua: partes.append(rua)
        if bairro: partes.append(bairro)
        if cidade: partes.append(cidade)
        endereco_curto = ", ".join([p for p in partes if p])
        return endereco_curto if endereco_curto else "GPS Local"
    except Exception: return "GPS Local"

@st.cache_data(show_spinner=False)
def carregar_malha_cacheada(caminho="malha_mrs.kml"):
    """Lê o KML da malha uma única vez, simplifica os vértices e guarda em RAM."""
    if not os.path.exists(caminho): return None
    import geopandas as gpd
    try:
        gdf = gpd.read_file(caminho, driver="KML")
        # Tolerância de 0.005 reduz drasticamente o peso visual no folium
        gdf.geometry = gdf.geometry.simplify(tolerance=0.005, preserve_topology=True)
        return gdf
    except Exception as e:
        st.warning(f"Erro ao cachear a malha KML: {e}")
        return None
#endregion 3.1.5

#region 3.1.6: Leitura de GPS do Navegador
def tentar_gps_uma_vez():
    loc = get_geolocation()
    if not loc: return False, None, None, "Aguardando resposta do navegador…", None
    if isinstance(loc, dict) and "error" in loc:
        return False, None, None, f"GPS falhou: {loc['error'].get('message')}", None
    if isinstance(loc, dict) and "coords" in loc:
        coords = loc.get("coords", {})
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if lat is not None and lon is not None:
            return True, float(lat), float(lon), "Localização obtida.", coords.get("accuracy")
    return False, None, None, "Não foi possível interpretar o GPS.", None
#endregion

#endregion 3.1.6

#region 3.2: Persistência (SQLite/Neon)
def upsert_baixa(os_id: str, status: str, realizado_em_str: str, coordenacao: str, concluido_por: str,
                 geolocalizacao_baixa: str = "", equipe: str = "", data_inicio: str = "", hora_inicio: str = "",
                 data_fim: str = "", hora_fim: str = ""):
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
    finally: release_connection(conn)

def carregar_baixas_df() -> pd.DataFrame:
    conn = get_connection()
    try: 
        # CORREÇÃO: Adicionamos a foto_evidencia na leitura do Neon!
        df = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa, foto_evidencia FROM baixas", conn)
    except Exception:
        # Fallback caso a coluna ainda não exista em algum ambiente
        df = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa FROM baixas", conn)
    finally: 
        release_connection(conn)
        
    if not df.empty: df["os"] = df["os"].astype(str)
    return df
#endregion

#region 3.3: Supabase Storage (Evidências Fotográficas com Compressão)
def upload_foto_supabase(arquivo_bytes: bytes, nome_arquivo: str) -> str:
    """Faz compressão com PIL antes de enviar ao Supabase e corrige a orientação (EXIF)."""
    url_base = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    upload_url = f"{url_base}/storage/v1/object/evidencias/{nome_arquivo}"
    
    # Compressão Inteligente da Imagem e Correção de Orientação
    try:
        img = Image.open(io.BytesIO(arquivo_bytes))
        
        # CORREÇÃO: Lê o EXIF da câmera e gira a imagem para a posição original (retrato)
        img = ImageOps.exif_transpose(img)
        
        if img.mode != 'RGB': img = img.convert('RGB')
        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=75, optimize=True)
        bytes_comprimidos = out.getvalue()
    except Exception:
        bytes_comprimidos = arquivo_bytes  # Fallback em caso de erro

    headers = {
        "Authorization": f"Bearer {chave}", "apikey": chave,
        "Content-Type": "image/jpeg", "x-upsert": "true"
    }
    resp = requests.post(upload_url, headers=headers, data=bytes_comprimidos)
    if resp.status_code in (200, 201): return f"{url_base}/storage/v1/object/public/evidencias/{nome_arquivo}"
    else: raise Exception(f"Erro Supabase ({resp.status_code}): {resp.text}")

def upsert_evidencia(ativo: str, atividade: str, foto_url: str, os_referencia: str, concluido_por: str, geolocalizacao: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO evidencias (ativo, atividade, foto_url, os_referencia, concluido_por, geolocalizacao, data_upload)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (ativo, atividade) DO UPDATE SET
                foto_url = EXCLUDED.foto_url, os_referencia = EXCLUDED.os_referencia,
                concluido_por = EXCLUDED.concluido_por, geolocalizacao = EXCLUDED.geolocalizacao, data_upload = CURRENT_TIMESTAMP;
        """, (str(ativo), str(atividade), str(foto_url), str(os_referencia), str(concluido_por), str(geolocalizacao)))
        conn.commit()
        cur.close()
    finally: release_connection(conn)

def carregar_evidencias_df() -> pd.DataFrame:
    conn = get_connection()
    try: df = pd.read_sql_query("SELECT ativo, atividade, foto_url, os_referencia, data_upload FROM evidencias", conn)
    finally: release_connection(conn)
    return df

@st.cache_data(show_spinner=False, ttl=600)
def carregar_mapeamento_patios() -> dict:
    conn = get_connection()
    try: df = pd.read_sql_query("SELECT ativo_chave, patio FROM mapeamento_patios", conn)
    finally: release_connection(conn)
    if df.empty: return {}
    df["ativo_chave"] = df["ativo_chave"].astype(str).str.strip().str.upper()
    df["patio"] = df["patio"].astype(str).str.strip().str.upper()
    return dict(zip(df["ativo_chave"], df["patio"]))
#endregion

#region 3.4: Export/Salvar Excel (SAP)
def gerar_excel_sap_bytes(df_filtrado_atual: pd.DataFrame) -> bytes:
    df_concluidas = df_filtrado_atual[df_filtrado_atual["Status_norm"].isin(_status_prazo | _status_atraso)].copy()
    if df_concluidas.empty: return b""

    lista_os = df_concluidas["Ordem servico"].astype(str).tolist()
    conn = get_connection()
    try:
        if len(lista_os) == 1:
            query = "SELECT os, data_inicio, hora_inicio, data_fim, hora_fim, concluido_por, equipe, coordenacao FROM baixas WHERE os = %s"
            df_detalhes = pd.read_sql_query(query, conn, params=(lista_os[0],))
        else:
            placeholders = ",".join(["%s"] * len(lista_os))
            query = f"SELECT os, data_inicio, hora_inicio, data_fim, hora_fim, concluido_por, equipe, coordenacao FROM baixas WHERE os IN ({placeholders})"
            df_detalhes = pd.read_sql_query(query, conn, params=tuple(lista_os))
    finally: release_connection(conn)

    df_sap = df_concluidas.merge(df_detalhes, left_on="Ordem servico", right_on="os", how="inner")

    def montar_lista_equipe(row):
        principal = str(row["concluido_por"]).strip()
        eqp = str(row["equipe"]).strip()
        if eqp and eqp.upper() not in ("SOZINHO", "NAN", ""):
            co_exec = [u.strip() for u in eqp.split(",") if u.strip()]
            todos = [principal] + co_exec
        else: todos = [principal]
        return list(dict.fromkeys(todos))

    df_sap["_lista_equipe"] = df_sap.apply(montar_lista_equipe, axis=1)
    df_sap_explodido = df_sap.explode("_lista_equipe").rename(columns={"_lista_equipe": "matricula_final"}).reset_index(drop=True)
    df_sap_explodido = df_sap_explodido.drop(columns=["_lista_equipe"], errors="ignore")

    def calc_trab_real(h_ini, h_fim):
        try:
            t_ini = pd.to_datetime(h_ini, format='%H:%M:%S')
            t_fim = pd.to_datetime(h_fim, format='%H:%M:%S')
            diff = (t_fim - t_ini).total_seconds() / 60.0
            if diff < 0: diff += 24 * 60 
            h, m = int(diff // 60), int(diff % 60)
            return f"{h:02d},{m:02d}"
        except Exception: return ""

    def get_centro_trab(coord):
        c = str(coord).upper()
        return 'E.SP.IPG' if 'IPG' in c or 'PIACAGUERA' in c or 'PIAÇAGUERA' in c else 'E.SP.IPA'

    def get_centro(coord):
        c = str(coord).upper()
        return 'CIPG' if 'IPG' in c or 'PIACAGUERA' in c or 'PIAÇAGUERA' in c else 'CIPA'

    n = len(df_sap_explodido)
    sap_out = pd.DataFrame({
        'A': [""] * n, 'Ordem': df_sap_explodido['Ordem servico'].values, 'Operação': ["10"] * n,
        'D': [""] * n, 'E': [""] * n, 'F': [""] * n,
        'Trab. real': df_sap_explodido.apply(lambda r: calc_trab_real(r['hora_inicio'], r['hora_fim']), axis=1).values,
        'UN Medida 1': ["MIN"] * n, 'I': [""] * n, 'J': [""] * n, 'K': [""] * n,
        'Centro de Trabalho': df_sap_explodido['coordenacao'].apply(get_centro_trab).values,
        'Centro': df_sap_explodido['coordenacao'].apply(get_centro).values,
        'N': [""] * n, 'O': [""] * n, 'P': [""] * n,
        'Matrícula': df_sap_explodido['matricula_final'].values,
        'R': [""] * n, 'S': [""] * n, 'UN Medida 2': ["MIN"] * n,
        'U': [""] * n, 'V': [""] * n, 'W': [""] * n, 'X': [""] * n,
        'Data Inicio Real': df_sap_explodido['data_inicio'].astype(str).str.replace('/', '.').values,
        'Hora Inicio Real': df_sap_explodido['hora_inicio'].values,
        'Data Fim Real': df_sap_explodido['data_fim'].astype(str).str.replace('/', '.').values,
        'Hora Fim Real': df_sap_explodido['hora_fim'].values,
    })

    col_names = []
    for i, c in enumerate(sap_out.columns):
        if c in ['A', 'D', 'E', 'F', 'I', 'J', 'K', 'N', 'O', 'P', 'R', 'S', 'U', 'V', 'W', 'X']: col_names.append(" " * (i + 1))
        elif c == 'UN Medida 1' or c == 'UN Medida 2': col_names.append("UN Medida" + " " * i)
        else: col_names.append(c)
    sap_out.columns = col_names

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer: sap_out.to_excel(writer, index=False, sheet_name="Importacao_SAP")
    return output.getvalue()
#endregion 3.4

#region 3.5: Auxiliares — Datas/Turnos para Gráficos Gerenciais
def parse_datahora_realizado(valor):
    if pd.isna(valor): return pd.NaT
    s = str(valor).strip()
    if not s: return pd.NaT
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def classificar_turno(dt):
    if pd.isna(dt): return None
    h = int(dt.hour)
    m = int(dt.minute)
    wd = dt.weekday() # 0=Seg, 1=Ter, ..., 5=Sab, 6=Dom
    
    # 1. Turno Noite: Todos os dias das 19h as 06h59
    if h >= 19 or h < 7:
        return "Turno Noite (19h-07h)"
        
    # 2. Dias de Semana (Segunda a Sexta)
    if wd < 5:
        # Administrativo: 08:00 as 17:30
        if (h > 8 and h < 17) or (h == 8) or (h == 17 and m <= 30):
            return "Administrativo (08h-17h30)"
        else:
            # Janelas do Revezamento Dia durante a semana (07h as 07h59 e 17h31 as 18h59)
            return "Turno Dia (07h-19h)"
    else:
        # 3. Finais de Semana: Revezamento Dia integral (07h as 18h59)
        return "Turno Dia (07h-19h)"
#endregion

#region 3.6: Auxiliares da Sidebar — Preparação e Filtros (Blindagem)
def preparar_df_visao(df_base: pd.DataFrame, filtro_visao: str) -> pd.DataFrame:
    df_visao = df_base.copy()
    _colunas_obrigatorias = ["Status da Operação", "Data/Hora Realizado", "Data inicial programada"]
    if df_visao.empty or not all(col in df_visao.columns for col in _colunas_obrigatorias):
        return pd.DataFrame()

    # Normalização Defensiva da Coluna de Coordenação
    col_coord = None
    for candidata in ["Coordenacao", "coordenacao", "COORDENACAO"]:
        if candidata in df_visao.columns:
            col_coord = candidata; break

    if col_coord is None: df_visao["Coordenacao"] = "N/D"
    elif col_coord != "Coordenacao": df_visao = df_visao.rename(columns={col_coord: "Coordenacao"})

    _mapa_norm_coord = {
        "PARANAPIACABA": "Paranapiacaba", "PIAÇAGUERA": "Piaçaguera", "PIACAGUERA": "Piaçaguera",
        "IPG": "Piaçaguera", "IPA": "Paranapiacaba", "E.SP.IPG": "Piaçaguera", "E.SP.IPA": "Paranapiacaba",
    }

    # FIX: Limpeza de quebras de linha e espaços duplos escondidos
    def _normalizar_coord(val):
        if pd.isna(val) or str(val).strip() == "": return "N/D"
        v = re.sub(r'\s+', ' ', str(val)).strip().upper()
        return _mapa_norm_coord.get(v, str(val).strip())

    df_visao["Coordenacao"] = df_visao["Coordenacao"].apply(_normalizar_coord)

    # Filtro Exato após a limpeza pesada
    if filtro_visao != "Todas":
        filtro_norm = _normalizar_coord(filtro_visao)
        df_visao = df_visao[df_visao["Coordenacao"] == filtro_norm].copy()

    df_visao["Status_norm"] = df_visao["Status da Operação"].astype(str).str.strip().str.upper()
    df_visao["dt_realizado"] = df_visao["Data/Hora Realizado"].apply(parse_datahora_realizado)
    df_visao["Turno"] = df_visao["dt_realizado"].apply(classificar_turno)
    df_visao["dia_realizado"] = pd.to_datetime(df_visao["dt_realizado"], errors="coerce").dt.normalize()
    df_visao["dt_prog_filtro"] = pd.to_datetime(df_visao["Data inicial programada"], errors="coerce")
    df_visao["Turno_Filtro"] = df_visao["Turno"].fillna("Pendente (Sem Turno)")

    if "TIPO_INTERVALO_CAN" in df_visao.columns and "Tipo_Intervalo" not in df_visao.columns:
        df_visao["Tipo_Intervalo"] = df_visao["TIPO_INTERVALO_CAN"]

    return df_visao

def aplicar_filtros_sidebar(
    df_visao: pd.DataFrame, patios_selecionados: list, classif_selecionadas: list,
    turnos_selecionados: list, start_date, end_date, status_sel: str = "Todos", intervalo_sel: str = "Todas"
) -> pd.DataFrame:
    df = df_visao.copy()
    if "dt_prog_filtro" in df.columns:
        mask_data = ((df["dt_prog_filtro"].dt.date >= start_date) & (df["dt_prog_filtro"].dt.date <= end_date)) | df["dt_prog_filtro"].isna()
        df = df[mask_data]
    if patios_selecionados: 
        df = df[df["Patio"].isin(patios_selecionados)]
    if classif_selecionadas: 
        df = df[df["Classificacao"].isin(classif_selecionadas)]
    if turnos_selecionados and "Turno_Filtro" in df.columns: 
        df = df[df["Turno_Filtro"].isin(turnos_selecionados)]
    if status_sel != "Todos" and "Status_norm" in df.columns:
        if status_sel == "Todas Concluídas": df = df[df["Status_norm"].isin(_status_prazo | _status_atraso)]
        elif status_sel == "Concluídas no Prazo": df = df[df["Status_norm"].isin(_status_prazo)]
        elif status_sel == "Concluídas com Atraso": df = df[df["Status_norm"].isin(_status_atraso)]
        elif status_sel == "Pendentes": df = df[df["Status_norm"].isin(_status_aberto)]
        elif status_sel == "Atrasado": df = df[df["Status_norm"] == "ATRASADO"]
    if intervalo_sel != "Todas" and "Tipo_Intervalo" in df.columns: df = df[df["Tipo_Intervalo"] == intervalo_sel]
    return df
#endregion 3.6

#region 3.7: Calendário Mensal de Demanda por Pátio
import calendar as pycal
from datetime import date

@st.cache_data(show_spinner=False)
def _preparar_df_calendario(df_base_cal: pd.DataFrame) -> pd.DataFrame:
    if df_base_cal.empty: return pd.DataFrame()
    df = df_base_cal.copy()
    if "dt_prog_filtro" not in df.columns: df["dt_prog_filtro"] = pd.to_datetime(df["Data inicial programada"], errors="coerce")
    if "Status_norm" not in df.columns: df["Status_norm"] = df["Status da Operação"].astype(str).str.strip().str.upper()
    if "Nivel_Prioridade" not in df.columns: df["Nivel_Prioridade"] = 999
    df = df.dropna(subset=["dt_prog_filtro", "Patio"]).copy()
    if df.empty: return df
    df["Patio"] = df["Patio"].astype(str).str.strip().str.upper()
    df["dia_prog"] = pd.to_datetime(df["dt_prog_filtro"], errors="coerce").dt.date
    df["Nivel_Prioridade"] = pd.to_numeric(df["Nivel_Prioridade"], errors="coerce").fillna(999).astype(int)
    return df

@st.cache_data(show_spinner=False)
def montar_eventos_calendario_patios(df_base_cal: pd.DataFrame, ano: int, mes: int, max_patios_visiveis: int = 2) -> list[dict]:
    df = _preparar_df_calendario(df_base_cal)
    if df.empty: return []
    primeiro_dia, ultimo_dia = date(int(ano), int(mes), 1), date(int(ano), int(mes), pycal.monthrange(int(ano), int(mes))[1])
    dias_mes, eventos = pd.date_range(primeiro_dia, ultimo_dia, freq="D"), []

    for dia_ts in dias_mes:
        dia = dia_ts.date()
        df_vencidas_abertas = df[(df["dia_prog"] < dia) & (df["Status_norm"].isin(_status_aberto))].copy()
        df_hoje = df[df["dia_prog"] == dia].copy()
        patios_dia = []

        if not df_vencidas_abertas.empty:
            agg_venc = df_vencidas_abertas.groupby("Patio", as_index=False).agg(ordem=("Nivel_Prioridade", "min"), qtd_os=("Patio", "size")).sort_values(["ordem", "Patio"])
            for _, row in agg_venc.iterrows(): patios_dia.append({"patio": str(row["Patio"]), "cor": "#FF4B4B", "ordem": int(row["ordem"]), "rank_status": 0})
        
        patios_ja_incluidos = {item["patio"] for item in patios_dia}
        if not df_hoje.empty:
            for patio, grp in df_hoje.groupby("Patio"):
                if patio in patios_ja_incluidos: continue
                todos_realizados = (~grp["Status_norm"].isin(_status_aberto)).all()
                patios_dia.append({"patio": str(patio), "cor": "#3B82F6" if todos_realizados else "#10B981", "ordem": int(grp["Nivel_Prioridade"].min()), "rank_status": 2 if todos_realizados else 1})

        if not patios_dia: continue
        patios_dia = sorted(patios_dia, key=lambda x: (x["rank_status"], x["ordem"], x["patio"]))
        patios_visiveis, qtd_extra = patios_dia[:max_patios_visiveis], max(0, len(patios_dia) - max_patios_visiveis)

        for idx, item in enumerate(patios_visiveis): eventos.append({"title": item["patio"], "start": dia.isoformat(), "allDay": True, "backgroundColor": item["cor"], "borderColor": item["cor"], "textColor": "#FFFFFF", "displayOrder": idx + 1})
        if qtd_extra > 0: eventos.append({"title": f"+{qtd_extra}", "start": dia.isoformat(), "allDay": True, "backgroundColor": "#94A3B8", "borderColor": "#94A3B8", "textColor": "#FFFFFF", "displayOrder": 99})

    return eventos

@st.cache_data(show_spinner=False)
def resumir_demanda_calendario(df_base_cal: pd.DataFrame, ano: int, mes: int, dia_ref: int | None = None) -> dict:
    df = _preparar_df_calendario(df_base_cal)
    primeiro_dia, ultimo_dia = date(int(ano), int(mes), 1), date(int(ano), int(mes), pycal.monthrange(int(ano), int(mes))[1])
    if dia_ref is None: dia_ref = 1
    dia_ref = max(1, min(int(dia_ref), ultimo_dia.day))
    dia_atual_ref = date(int(ano), int(mes), int(dia_ref))

    if df.empty: return {"dia_ref": dia_atual_ref, "qtd_patios": 0, "total_os": 0, "patio_prioritario": "-", "serie_total_os_mes": [0] * ultimo_dia.day, "labels_mes": [f"{d:02d}" for d in range(1, ultimo_dia.day + 1)]}

    serie_total_os_mes, labels_mes = [], []
    for d in pd.date_range(primeiro_dia, ultimo_dia, freq="D"):
        dia = d.date()
        total_os_dia = len(df[(df["dia_prog"] < dia) & (df["Status_norm"].isin(_status_aberto))]) + len(df[df["dia_prog"] == dia])
        serie_total_os_mes.append(int(total_os_dia)); labels_mes.append(d.strftime("%d"))

    backlog_ref = df[(df["dia_prog"] < dia_atual_ref) & (df["Status_norm"].isin(_status_aberto))].copy()
    demanda_ref = df[df["dia_prog"] == dia_atual_ref].copy()
    patio_resumo = {}

    if not backlog_ref.empty:
        for patio, grp in backlog_ref.groupby("Patio"): patio_resumo[patio] = {"ordem": int(grp["Nivel_Prioridade"].min()), "qtd_os": int(len(grp)), "rank_status": 0}
    if not demanda_ref.empty:
        for patio, grp in demanda_ref.groupby("Patio"):
            todos_realizados = (~grp["Status_norm"].isin(_status_aberto)).all()
            if patio in patio_resumo: patio_resumo[patio]["qtd_os"] += int(len(grp)); patio_resumo[patio]["ordem"] = min(patio_resumo[patio]["ordem"], int(grp["Nivel_Prioridade"].min()))
            else: patio_resumo[patio] = {"ordem": int(grp["Nivel_Prioridade"].min()), "qtd_os": int(len(grp)), "rank_status": 2 if todos_realizados else 1}

    qtd_patios, total_os = len(patio_resumo), sum(v["qtd_os"] for v in patio_resumo.values())
    patio_prioritario_txt = f"{sorted(patio_resumo.items(), key=lambda kv: (kv[1]['rank_status'], kv[1]['ordem'], kv[0]))[0][0]} ➔ {sorted(patio_resumo.items(), key=lambda kv: (kv[1]['rank_status'], kv[1]['ordem'], kv[0]))[0][1]['qtd_os']} OS" if patio_resumo else "-"

    return {"dia_ref": dia_atual_ref, "qtd_patios": int(qtd_patios), "total_os": int(total_os), "patio_prioritario": patio_prioritario_txt, "serie_total_os_mes": serie_total_os_mes, "labels_mes": labels_mes}

@st.cache_data(show_spinner=False)
#endregion

#region 3.7.4: Resumo de Conclusões por Turno
def resumir_conclusoes_por_turno_data(df_base_cal: pd.DataFrame, data_ref) -> dict:
    ordem_turnos = ["Turno Dia (07h-19h)", "Administrativo (08h-17h30)", "Turno Noite (19h-07h)"]
    if df_base_cal.empty: return {"labels": ordem_turnos, "valores": [0, 0, 0], "titulo": "Quantidade de OS Concluídas", "subtitulo": "Sem dados"}
    
    df = df_base_cal.copy()
    if "dt_prog_filtro" not in df.columns: df["dt_prog_filtro"] = pd.to_datetime(df["Data inicial programada"], errors="coerce")
    if "dt_realizado" not in df.columns: df["dt_realizado"] = df["Data/Hora Realizado"].apply(parse_datahora_realizado)
    if "Turno" not in df.columns: df["Turno"] = df["dt_realizado"].apply(classificar_turno)
    if "Status_norm" not in df.columns: df["Status_norm"] = df["Status da Operação"].astype(str).str.strip().str.upper()

    data_ref, hoje_ref = pd.to_datetime(data_ref).date(), datetime.now().date()
    df_realizadas = df[df["Status_norm"].isin(_status_prazo | _status_atraso)].copy()

    if df_realizadas.empty: return {"labels": ordem_turnos, "valores": [0, 0, 0], "titulo": "Quantidade de OS Concluídas", "subtitulo": "Sem dados"}
    if data_ref <= hoje_ref:
        df_ref = df_realizadas[pd.to_datetime(df_realizadas["dt_realizado"], errors="coerce").dt.date == data_ref].copy()
        subtitulo = f"Concluídas em {data_ref.strftime('%d/%m/%Y')}"
    else:
        df_ref = df_realizadas[(pd.to_datetime(df_realizadas["dt_prog_filtro"], errors="coerce").dt.date == data_ref) & (pd.to_datetime(df_realizadas["dt_realizado"], errors="coerce").dt.date < data_ref)].copy()
        subtitulo = f"Antecipadas para {data_ref.strftime('%d/%m/%Y')}"

    serie = df_ref.groupby("Turno").size() if not df_ref.empty else pd.Series(dtype=int)
    return {"labels": ordem_turnos, "valores": [int(serie.get(t, 0)) for t in ordem_turnos], "titulo": "Quantidade de OS Concluídas", "subtitulo": subtitulo}
#endregion 3.7

#region 3.8: Administração de Dados (render_tela_admin)

#region 3.8.0: Renderização da Tela de Administração
def render_tela_admin():
    col_adm_t1, col_adm_t2 = st.columns([8, 2])
    with col_adm_t1: st.title("⚙️ Administração de Dados")
    with col_adm_t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Voltar ao Painel", use_container_width=True): st.session_state["tela_atual"] = "dashboard"; st.rerun()

    if "msg_upload_os" in st.session_state: st.success(st.session_state["msg_upload_os"]); del st.session_state["msg_upload_os"]
    if "msg_upload_mapa" in st.session_state: st.success(st.session_state["msg_upload_mapa"]); del st.session_state["msg_upload_mapa"]

    # --- MANUAL DE PADRONIZAÇÃO DE DADOS (GOVERNANÇA) ---
    with st.expander("📖 MANUAL DE IMPORTAÇÃO (Padrão Exigido para Planilhas)", expanded=True):
        st.markdown("""
        #### 1. Planilha de **OS Programadas** (Carga Inicial)
        Para que o sistema consiga gerar a roteirização e os painéis gerenciais, a planilha deve conter estas colunas (a ordem não importa):
        * `Ordem servico` ou `OS` *(Ex: 23568082)*
        * `Ativo` ou `Equipamento` *(Ex: ICG 30DT N)*
        * `Atividade ativo` ou `Atividade` *(Ex: EE_INS_SEG_...)*
        * `Prioridade` ou `Criticidade` *(Ex: 1-Muito Alta)*
        * `Data inicial programada` *(Formato: DD/MM/AAAA)*
        * `Código Departamento` ou `Concatenar` *(Usado para definir se é Piaçaguera ou Paranapiacaba)*
        * `Descrição Longa` *(Opcional - Texto detalhado do serviço)*

        #### 2. Planilha de **Baixas em Massa (SAP - IW47)**
        Ao exportar do SAP, garanta que o layout da IW47 possua as seguintes colunas visíveis:
        * `Ordem` *(Número da OS)*
        * `Matrícula` ou `Nome` *(Identificação de quem executou)*
        * `Data real do fim de execução` *(Formato: DD/MM/AAAA)*
        * `Hora real do fim de execução` *(Formato: HH:MM)*
        * `Data real de início da execução` *(Opcional)*
        * `Hora real do início da execução` *(Opcional)*
        
        ⚠️ **Atenção:** O sistema é inteligente e ignora as letras das colunas (A, B, C...). Ele procura pelo **nome do cabeçalho**. Portanto, não altere o nome das colunas geradas pelo SAP.
        """)
    st.markdown("---")
#endregion

#region 3.8.1: Upload e Processamento de OS Programadas
    st.markdown("### 📥 Carga de OS Programadas")
    col_up1, col_up2 = st.columns(2)
    with col_up1: mes_ref = st.text_input("Mês de Referência (ex: Junho/2026)", placeholder="Mês/Ano")
    with col_up2: coord_upload_fallback = st.selectbox("Coordenação (fallback caso a planilha não informe)", ["Paranapiacaba", "Piaçaguera"])

    arquivo_upload = st.file_uploader("Selecione a planilha Excel ou CSV", type=["csv", "xlsx"], key="upload_os_prog")
    if arquivo_upload is not None and mes_ref:
        if st.button("🚀 Processar e Salvar no Banco", use_container_width=True, type="primary"):
            escopo_user = st.session_state.get("escopo", "Todas")
            with st.spinner("Lendo e processando dados..."):
                try:
                    df = pd.read_csv(arquivo_upload, sep=';', encoding='utf-8-sig') if arquivo_upload.name.endswith('.csv') else pd.read_excel(arquivo_upload)
                    if "Ordem servico" not in df.columns and "OS" not in [str(c).upper() for c in df.columns]: 
                        st.error("❌ Coluna 'Ordem servico' não encontrada."); return
                    
                    df = df.fillna("")
                    col_depto = next((c for c in df.columns if str(c).strip().upper().replace(" ", "") in ("CODIGODEPARTAMENTO", "CÓDIGODEPARTAMENTO", "CODIGO_DEPARTAMENTO")), None)
                    if not col_depto: col_depto = next((c for c in df.columns if str(c).strip().upper() == "CONCATENAR"), None)

                    if col_depto is not None:
                        df["_coord_auto"] = df[col_depto].apply(lambda v: "Paranapiacaba" if str(v).strip().upper().startswith("E.SP.IPA") else ("Piaçaguera" if str(v).strip().upper().startswith("E.SP.IPG") else None))
                        df = df[df["_coord_auto"].notna()].copy()
                    else: df["_coord_auto"] = coord_upload_fallback

                    if escopo_user != "Todas": df = df[df["_coord_auto"] == escopo_user].copy()

                    barra, registros_por_coord = st.progress(0, text="Preparando dados..."), {}
                    for idx, (_, row) in enumerate(df.iterrows()):
                        col_os_real = "Ordem servico" if "Ordem servico" in df.columns else df.columns[[str(c).upper() == "OS" for c in df.columns]][0]
                        os_num, coord_linha = str(row[col_os_real]).strip(), row["_coord_auto"]
                        if os_num and coord_linha:
                            registros_por_coord.setdefault(coord_linha, []).append((os_num, mes_ref, coord_linha, json.dumps(row.drop(labels=["_coord_auto"], errors="ignore").to_dict(), default=lambda x: x.strftime('%d/%m/%Y') if isinstance(x, (pd.Timestamp, datetime)) else str(x))))
                        if (idx + 1) % 200 == 0: barra.progress(min((idx + 1) / len(df), 0.5), text=f"Preparando... {idx + 1}/{len(df)} linhas")

                    barra.progress(0.5, text="Gravando no banco de dados...")
                    conn = get_connection()
                    try:
                        cur = conn.cursor()
                        todos_registros = [r for regs in registros_por_coord.values() for r in regs]
                        for i in range(0, len(todos_registros), 500):
                            execute_values(cur, "INSERT INTO os_programadas (os, mes_referencia, coordenacao, dados_completos) VALUES %s ON CONFLICT (os) DO UPDATE SET mes_referencia = EXCLUDED.mes_referencia, coordenacao = EXCLUDED.coordenacao, dados_completos = EXCLUDED.dados_completos", todos_registros[i:i + 500], page_size=500)
                            barra.progress(min(0.5 + (i + 500) / len(todos_registros) * 0.5, 1.0), text=f"Gravando... {min(i + 500, len(todos_registros))}/{len(todos_registros)} registros")
                        conn.commit(); cur.close()
                    finally: release_connection(conn)

                    st.session_state["msg_upload_os"] = f"✅ Sucesso! {len(todos_registros)} OS processadas."
                    st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"❌ Erro ao processar o arquivo: {e}")
#endregion 3.8.1
    
#region 3.8.2: Histórico de Uploads
    with st.expander("📋 Histórico de Uploads", expanded=False):
        perfil_user = st.session_state.get("perfil", "")
        escopo_user = st.session_state.get("escopo", "")
        
        # Define o filtro de visão baseado no perfil
        ver_tudo = perfil_user in ("Gerência",) or escopo_user == "Todas"
        
        conn = get_connection()
        try:
            if ver_tudo:
                query_hist = """
                        SELECT coordenacao AS "Coordenação",
                            MAX(data_upload) AS "Último Upload",
                            COUNT(*) AS "Linhas Carregadas"
                        FROM os_programadas
                        GROUP BY coordenacao
                        ORDER BY MAX(data_upload) DESC
                    """
                df_hist = pd.read_sql_query(query_hist, conn)
            else:
                # Filtra pela coordenação do usuário
                filtro_coord = escopo_user if escopo_user else "Paranapiacaba"
                query_hist = """
                        SELECT coordenacao AS "Coordenação",
                            MAX(data_upload) AS "Último Upload",
                            COUNT(*) AS "Linhas Carregadas"
                        FROM os_programadas
                        WHERE coordenacao = %s
                        GROUP BY coordenacao
                        ORDER BY MAX(data_upload) DESC
                    """
                df_hist = pd.read_sql_query(query_hist, conn, params=(filtro_coord,))
        finally:
            release_connection(conn)
        
        if not df_hist.empty:
            # Formata a data e fuso horário direto no Pandas (Evita erro de sintaxe do PostgreSQL)
            df_hist["Último Upload"] = pd.to_datetime(df_hist["Último Upload"])
            if df_hist["Último Upload"].dt.tz is None:
                df_hist["Último Upload"] = df_hist["Último Upload"].dt.tz_localize("UTC")
            df_hist["Último Upload"] = df_hist["Último Upload"].dt.tz_convert("America/Sao_Paulo").dt.strftime("%d/%m/%Y %H:%M")
            
            df_hist["Linhas Carregadas"] = df_hist["Linhas Carregadas"].astype(int)
            
            if ver_tudo:
                st.caption("📊 **Visão Consolidada** (todas as coordenações)")
            else:
                st.caption(f"📊 Visão restrita à coordenação **{escopo_user}**")
            
            st.dataframe(
                df_hist.style.set_properties(**{'text-align': 'center'}).set_table_styles(
                    [{'selector': 'th', 'props': [('text-align', 'center')]}]
                ),
                use_container_width=True,
                hide_index=True
            )
            
            # Totalizador
            total_geral = int(df_hist["Linhas Carregadas"].sum())
            st.info(f"📦 **Total de OS na base:** {total_geral:,} registros".replace(",", "."))
        else:
            st.info("Nenhum upload realizado até o momento.")
    #endregion 3.8.2

#region 3.8.3: Upload de Mapeamento de Pátios
    with st.expander("🗺️ Mapeamento de Ativos → Pátios", expanded=False):
        arquivo_mapa = st.file_uploader("Selecione a planilha de mapeamento", type=["xlsx"], key="upload_mapeamento_patios")
        if arquivo_mapa and st.button("🚀 Processar Mapeamento", use_container_width=True, type="primary"):
            with st.spinner("Processando..."):
                try:
                    xls = pd.ExcelFile(arquivo_mapa, engine="openpyxl")
                    registros = []
                    if "Ativos_SP" in xls.sheet_names:
                        df_at = pd.read_excel(xls, sheet_name="Ativos_SP")
                        for _, row in df_at.iterrows():
                            patio = str(row.iloc[10]).strip()
                            if patio and patio != "nan":
                                if str(row.iloc[0]).strip() != "nan": registros.append((str(row.iloc[0]).strip(), patio, "Ativo"))
                                if str(row.iloc[1]).strip() != "nan" and str(row.iloc[1]).strip() != str(row.iloc[0]).strip(): registros.append((str(row.iloc[1]).strip(), patio, "Ativo_Denom"))
                    for nome_aba in ["Equipamento_SP", "Equipamentos_SP"]:
                        if nome_aba in xls.sheet_names:
                            df_eq = pd.read_excel(xls, sheet_name=nome_aba)
                            for _, row in df_eq.iterrows():
                                patio = str(row.iloc[6]).strip()
                                if patio and patio != "nan":
                                    if str(row.iloc[0]).strip() != "nan": registros.append((str(row.iloc[0]).strip(), patio, "Equipamento"))
                                    if str(row.iloc[1]).strip() != "nan" and str(row.iloc[1]).strip() != str(row.iloc[0]).strip(): registros.append((str(row.iloc[1]).strip(), patio, "Equipamento_Denom"))
                            break

                    chaves_vistas, registros_unicos = set(), []
                    for reg in registros:
                        if reg[0].upper() not in chaves_vistas: chaves_vistas.add(reg[0].upper()); registros_unicos.append(reg)

                    if registros_unicos:
                        conn = get_connection()
                        try:
                            cur = conn.cursor()
                            for i in range(0, len(registros_unicos), 500): execute_values(cur, "INSERT INTO mapeamento_patios (ativo_chave, patio, tipo) VALUES %s ON CONFLICT (ativo_chave) DO UPDATE SET patio = EXCLUDED.patio, tipo = EXCLUDED.tipo", registros_unicos[i:i + 500], page_size=500)
                            conn.commit(); cur.close()
                        finally: release_connection(conn)
                        st.session_state["msg_upload_mapa"] = f"✅ Mapeamento atualizado com {len(registros_unicos)} registros!"
                        st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"❌ Erro: {e}")
    #endregion 3.8.3

#region 3.8.4: Exportação SAP
    if "Exportar SAP" in st.session_state.get("governanca", ""):
        st.markdown("---"); st.subheader("⬇️ Exportação SAP")
        if st.button("📦 Preparar Arquivo SAP (Massa)", use_container_width=False, type="primary"):
            with st.spinner("Preparando exportação..."):
                conn = get_connection()
                try: cur = conn.cursor(); cur.execute("SELECT COUNT(*), MAX(os) FROM baixas"); row = cur.fetchone(); baixas_hash_export = f"{row[0]}_{row[1]}"; cur.close()
                finally: release_connection(conn)

                df_bruto = carregar_base_sem_overlay(False, 0, 0, st.session_state.get("escopo", "Todas"), ETL_VERSION)
                df_completo = aplicar_overlay_baixas(df_bruto, st.session_state.get("escopo", "Todas"), baixas_hash_export)

                if not df_completo.empty and df_completo["Status da Operação"].astype(str).str.strip().str.upper().isin(_status_prazo | _status_atraso).any():
                    df_completo["Status_norm"] = df_completo["Status da Operação"].astype(str).str.strip().str.upper()
                    st.session_state["sap_massa_bytes"] = gerar_excel_sap_bytes(df_completo)
                    st.session_state["sap_massa_nome"] = f"Baixa_Massa_SAP_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    st.success("✅ Arquivo preparado com sucesso.")
                else: st.info("⚠️ Nenhuma OS concluída.")

        if st.session_state.get("sap_massa_bytes"):
            st.download_button("⬇️ Baixar Arquivo SAP", data=st.session_state["sap_massa_bytes"], file_name=st.session_state["sap_massa_nome"], mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    #endregion 3.8.4

#region 3.8.5: Importação de Baixas em Massa (IW47)
    st.markdown("---")
    st.subheader("📥 Importação de Baixas em Massa (IW47)")

    coord_baixa = st.selectbox(
        "Coordenação",
        ["Paranapiacaba", "Piaçaguera"],
        key="coord_baixa_iw47"
    )

    arquivo_iw47 = st.file_uploader(
        "Selecione a planilha IW47",
        type=["xlsx", "csv"],
        key="upload_iw47_baixas_massa"
    )

    def _normalizar_nome_coluna(col):
        import unicodedata

        texto = str(col).replace("\n", " ").replace("\r", " ").strip().upper()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        texto = re.sub(r"\s+", " ", texto)
        return texto

    def _pick_coluna(df, candidatos):
        mapa = {c: _normalizar_nome_coluna(c) for c in df.columns}
        candidatos_norm = [_normalizar_nome_coluna(c) for c in candidatos]

        # 1) Match exato normalizado
        for candidato in candidatos_norm:
            for col_original, col_norm in mapa.items():
                if col_norm == candidato:
                    return col_original

        # 2) Match por substring
        for candidato in candidatos_norm:
            for col_original, col_norm in mapa.items():
                if candidato in col_norm:
                    return col_original

        return None

    def _limpar_texto(valor):
        if pd.isna(valor):
            return ""

        texto = str(valor).replace("\u00a0", " ")
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    def _normalizar_os(valor):
        texto = _limpar_texto(valor)

        if not texto or texto.lower() in ("nan", "none", "null"):
            return ""

        if re.fullmatch(r"\d+\.0+", texto):
            texto = texto.split(".")[0]
        elif re.fullmatch(r"\d+\.\d+", texto):
            try:
                numero = float(texto)
                if numero.is_integer():
                    texto = str(int(numero))
            except Exception:
                pass

        texto = re.sub(r"\D", "", texto)

        if texto:
            texto = texto.lstrip("0") or "0"

        return texto

    def _normalizar_matricula(valor):
        texto = _limpar_texto(valor)

        if not texto or texto.lower() in ("nan", "none", "null"):
            return ""

        if re.fullmatch(r"\d+\.0+", texto):
            texto = texto.split(".")[0]
        elif re.fullmatch(r"\d+\.\d+", texto):
            try:
                numero = float(texto)
                if numero.is_integer():
                    texto = str(int(numero))
            except Exception:
                pass

        matricula = re.sub(r"\D", "", texto)
        return matricula if matricula else texto

    def _formatar_data_iw47(valor):
        if pd.isna(valor) or str(valor).strip() == "":
            return ""

        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            try:
                numero = float(valor)
                if 20000 <= numero <= 60000:
                    dt = pd.Timestamp("1899-12-30") + pd.to_timedelta(numero, unit="D")
                    return dt.strftime("%d/%m/%Y")
            except Exception:
                pass

        texto = _limpar_texto(valor).replace(".", "/")
        dt = pd.to_datetime(texto, dayfirst=True, errors="coerce")

        if pd.isna(dt):
            return ""

        return dt.strftime("%d/%m/%Y")

    def _formatar_hora_iw47(valor):
        if pd.isna(valor) or str(valor).strip() == "":
            return ""

        if hasattr(valor, "hour") and hasattr(valor, "minute"):
            return (
                f"{int(valor.hour):02d}:"
                f"{int(valor.minute):02d}:"
                f"{int(getattr(valor, 'second', 0)):02d}"
            )

        if isinstance(valor, pd.Timedelta):
            total_segundos = int(round(valor.total_seconds())) % 86400
            return (
                f"{total_segundos // 3600:02d}:"
                f"{(total_segundos % 3600) // 60:02d}:"
                f"{total_segundos % 60:02d}"
            )

        texto = _limpar_texto(valor).replace(",", ".")

        if ":" in texto:
            try:
                partes = texto.split(":")
                hora = int(float(partes[0])) % 24
                minuto = int(float(partes[1])) if len(partes) > 1 else 0
                segundo = int(float(partes[2])) if len(partes) > 2 else 0

                if 0 <= minuto <= 59 and 0 <= segundo <= 59:
                    return f"{hora:02d}:{minuto:02d}:{segundo:02d}"
            except Exception:
                return ""

        try:
            numero = float(texto)

            # Fração de dia do Excel/SAP: 0.5 = 12:00:00
            if 0 <= numero < 1:
                total_segundos = int(round(numero * 86400)) % 86400
                return (
                    f"{total_segundos // 3600:02d}:"
                    f"{(total_segundos % 3600) // 60:02d}:"
                    f"{total_segundos % 60:02d}"
                )

            # Hora decimal: 9.5 = 09:30:00
            if 1 <= numero < 24:
                total_segundos = int(round(numero * 3600)) % 86400
                return (
                    f"{total_segundos // 3600:02d}:"
                    f"{(total_segundos % 3600) // 60:02d}:"
                    f"{total_segundos % 60:02d}"
                )

            # Formato compacto: 940, 0940, 094000
            inteiro = str(int(numero)).zfill(4)
            if len(inteiro) in (4, 6):
                hora = int(inteiro[:2])
                minuto = int(inteiro[2:4])
                segundo = int(inteiro[4:6]) if len(inteiro) == 6 else 0

                if 0 <= hora <= 23 and 0 <= minuto <= 59 and 0 <= segundo <= 59:
                    return f"{hora:02d}:{minuto:02d}:{segundo:02d}"

        except Exception:
            pass

        dt = pd.to_datetime(valor, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%H:%M:%S")

        return ""

    def _montar_datetime_iw47(data_valor, hora_valor):
        data_txt = _formatar_data_iw47(data_valor)
        hora_txt = _formatar_hora_iw47(hora_valor)

        if not data_txt or not hora_txt:
            return pd.NaT

        return pd.to_datetime(
            f"{data_txt} {hora_txt}",
            dayfirst=True,
            errors="coerce"
        )

    def _trabalho_real_minutos(valor):
        if pd.isna(valor) or str(valor).strip() == "":
            return None

        texto = _limpar_texto(valor).replace(",", ".")

        try:
            return float(texto)
        except Exception:
            return None

    def _coord_por_centro_trabalho(valor, coord_fallback):
        centro = _normalizar_nome_coluna(valor)

        if "IPG" in centro or "PIACAGUERA" in centro:
            return "Piaçaguera"

        if "IPA" in centro or "PARANAPIACABA" in centro:
            return "Paranapiacaba"

        return coord_fallback

    if arquivo_iw47 and st.button(
        "🚀 Processar Baixas em Massa",
        type="primary",
        key="btn_processar_iw47_baixas"
    ):
        with st.spinner("Processando baixas da IW47..."):
            try:
                # 1. Leitura
                if arquivo_iw47.name.lower().endswith(".csv"):
                    df_iw = pd.read_csv(
                        arquivo_iw47,
                        sep=None,
                        engine="python",
                        encoding="utf-8-sig",
                        dtype=object
                    )
                else:
                    df_iw = pd.read_excel(
                        arquivo_iw47,
                        engine="openpyxl",
                        dtype=object
                    )

                df_iw.columns = [str(c).strip() for c in df_iw.columns]

                if df_iw.empty:
                    st.warning("⚠️ A planilha IW47 está vazia.")
                    st.stop()

                # 2. Mapeamento de colunas por cabeçalho
                col_matricula = _pick_coluna(df_iw, [
                    "Matrícula",
                    "Matricula",
                    "Nº pessoal",
                    "N° pessoal",
                    "No pessoal",
                    "Numero pessoal",
                    "Número pessoal"
                ])

                col_nome = _pick_coluna(df_iw, [
                    "Nome do empregado",
                    "Nome empregado",
                    "Nome"
                ])

                col_ordem = _pick_coluna(df_iw, [
                    "Ordem",
                    "Ordem servico",
                    "Ordem serviço",
                    "OS"
                ])

                col_dt_ini = _pick_coluna(df_iw, [
                    "Data real de início da execução",
                    "Data real de inicio da execucao",
                    "Data de início de execução real",
                    "Data de inicio de execucao real",
                    "Data início",
                    "Data inicio"
                ])

                col_hr_ini = _pick_coluna(df_iw, [
                    "Hora real do início da execução",
                    "Hora real do inicio da execucao",
                    "Hora de início de execução real",
                    "Hora de inicio de execucao real",
                    "Hora início",
                    "Hora inicio"
                ])

                col_dt_fim = _pick_coluna(df_iw, [
                    "Data real do fim de execução",
                    "Data real do fim de execucao",
                    "Data real de fim da execução",
                    "Data real de fim da execucao",
                    "Data fim",
                    "Data final"
                ])

                col_hr_fim = _pick_coluna(df_iw, [
                    "Hora real do fim de execução",
                    "Hora real do fim de execucao",
                    "Hora real de fim da execução",
                    "Hora real de fim da execucao",
                    "Hora fim",
                    "Hora final"
                ])

                col_trabalho = _pick_coluna(df_iw, [
                    "Trabalho real",
                    "Trab. real",
                    "Trab real"
                ])

                col_centro = _pick_coluna(df_iw, [
                    "Centro de Trabalho",
                    "Centro trab.(real)",
                    "Centro trab",
                    "Centro trabalho",
                    "Centro"
                ])

                obrigatorias = {
                    "Ordem": col_ordem,
                    "Matrícula / Nº pessoal": col_matricula,
                    "Data inicial": col_dt_ini,
                    "Hora inicial": col_hr_ini,
                    "Data final": col_dt_fim,
                    "Hora final": col_hr_fim,
                    "Centro de Trabalho": col_centro,
                }

                faltantes = [nome for nome, coluna in obrigatorias.items() if coluna is None]

                if faltantes:
                    st.error(
                        "❌ Colunas obrigatórias não encontradas: "
                        + ", ".join(faltantes)
                    )
                    st.caption("Colunas lidas na planilha:")
                    st.write(list(df_iw.columns))
                    st.stop()

                # 3. Normalização base
                df_iw["_os"] = df_iw[col_ordem].apply(_normalizar_os)
                df_iw["_matricula"] = df_iw[col_matricula].apply(_normalizar_matricula)

                df_iw = df_iw[
                    df_iw["_os"].ne("")
                    & df_iw["_os"].str.lower().ne("nan")
                ].copy()

                if df_iw.empty:
                    st.warning("⚠️ Nenhuma OS válida encontrada na planilha.")
                    st.stop()

                # 4. Datas e horas calculadas
                df_iw["_dt_ini_calc"] = df_iw.apply(
                    lambda r: _montar_datetime_iw47(r[col_dt_ini], r[col_hr_ini]),
                    axis=1
                )

                df_iw["_dt_fim_calc"] = df_iw.apply(
                    lambda r: _montar_datetime_iw47(r[col_dt_fim], r[col_hr_fim]),
                    axis=1
                )

                df_iw["_trabalho_min"] = (
                    df_iw[col_trabalho].apply(_trabalho_real_minutos)
                    if col_trabalho
                    else None
                )

                df_iw["_coord"] = df_iw[col_centro].apply(
                    lambda v: _coord_por_centro_trabalho(v, coord_baixa)
                )

                # 5. Consolidação por OS
                registros_baixa = []
                alertas = []

                for os_id, grp in df_iw.groupby("_os", sort=False):
                    grp = grp.copy()

                    grp_ini_valido = grp.dropna(subset=["_dt_ini_calc"])
                    grp_fim_valido = grp.dropna(subset=["_dt_fim_calc"])

                    if grp_ini_valido.empty and grp_fim_valido.empty:
                        alertas.append(f"OS {os_id}: data/hora inválida. Registro ignorado.")
                        continue

                    if not grp_ini_valido.empty:
                        dt_ini = grp_ini_valido["_dt_ini_calc"].min()
                    else:
                        dt_ini = pd.NaT

                    if not grp_fim_valido.empty:
                        dt_fim = grp_fim_valido["_dt_fim_calc"].max()
                        linha_fim = grp_fim_valido.sort_values("_dt_fim_calc").iloc[-1]
                    else:
                        dt_fim = pd.NaT
                        linha_fim = grp.iloc[0]

                    trabalho_min = None
                    if "_trabalho_min" in grp.columns:
                        trabalhos_validos = [
                            x for x in grp["_trabalho_min"].tolist()
                            if x is not None and pd.notna(x) and float(x) > 0
                        ]
                        if trabalhos_validos:
                            trabalho_min = max(trabalhos_validos)

                    # Recuperação quando uma das pontas está faltando
                    if pd.isna(dt_ini) and pd.notna(dt_fim) and trabalho_min is not None:
                        dt_ini = dt_fim - timedelta(minutes=float(trabalho_min))
                        alertas.append(
                            f"OS {os_id}: início inferido pelo Trabalho real ({trabalho_min:.0f} min)."
                        )

                    if pd.notna(dt_ini) and pd.isna(dt_fim) and trabalho_min is not None:
                        dt_fim = dt_ini + timedelta(minutes=float(trabalho_min))
                        alertas.append(
                            f"OS {os_id}: fim inferido pelo Trabalho real ({trabalho_min:.0f} min)."
                        )

                    if pd.isna(dt_ini) or pd.isna(dt_fim):
                        alertas.append(f"OS {os_id}: data/hora incompleta. Registro ignorado.")
                        continue

                    duracao_min = (dt_fim - dt_ini).total_seconds() / 60.0

                    if duracao_min <= 0 or duracao_min > 14 * 60:
                        if trabalho_min is not None and 0 < trabalho_min <= 14 * 60:
                            dt_fim = dt_ini + timedelta(minutes=float(trabalho_min))
                            duracao_min = float(trabalho_min)
                            alertas.append(
                                f"OS {os_id}: duração incoerente ajustada pelo Trabalho real ({trabalho_min:.0f} min)."
                            )
                        else:
                            alertas.append(
                                f"OS {os_id}: duração incoerente sem Trabalho real válido. Registro ignorado."
                            )
                            continue

                    execs = (
                        grp[["_matricula"] + ([col_nome] if col_nome else [])]
                        .dropna(subset=["_matricula"])
                        .drop_duplicates(subset=["_matricula"])
                        .copy()
                    )

                    execs = execs[
                        execs["_matricula"].astype(str).str.strip().ne("")
                    ].copy()

                    if execs.empty:
                        alertas.append(f"OS {os_id}: sem matrícula válida. Registro ignorado.")
                        continue

                    matriculas = execs["_matricula"].astype(str).str.strip().tolist()
                    matriculas = list(dict.fromkeys(matriculas))

                    concluido_por = matriculas[0]
                    equipe = ", ".join(matriculas[1:]) if len(matriculas) > 1 else "Sozinho"

                    coord_final = str(linha_fim.get("_coord", coord_baixa)).strip() or coord_baixa

                    registros_baixa.append({
                        "os": str(os_id).strip(),
                        "realizado_em": dt_fim.strftime("%d/%m/%Y %H:%M"),
                        "coordenacao": coord_final,
                        "concluido_por": concluido_por,
                        "geolocalizacao_baixa": "Baixa IW47",
                        "equipe": equipe,
                        "data_inicio": dt_ini.strftime("%d/%m/%Y"),
                        "hora_inicio": dt_ini.strftime("%H:%M:%S"),
                        "data_fim": dt_fim.strftime("%d/%m/%Y"),
                        "hora_fim": dt_fim.strftime("%H:%M:%S"),
                    })

                if not registros_baixa:
                    st.warning("⚠️ Nenhum registro válido encontrado para importação.")
                    if alertas:
                        with st.expander("Ver alertas da importação IW47", expanded=True):
                            for alerta in alertas[:300]:
                                st.write(f"- {alerta}")
                    st.stop()

                # 6. Carrega datas programadas para definir status no prazo/fora
                lista_os_importacao = [r["os"] for r in registros_baixa]
                mapa_dt_prog = {}

                conn = get_connection()
                try:
                    if len(lista_os_importacao) == 1:
                        df_prog = pd.read_sql_query(
                            """
                            SELECT
                                os,
                                dados_completos->>'Data inicial programada' AS dt_prog
                            FROM os_programadas
                            WHERE os = %s
                            """,
                            conn,
                            params=(lista_os_importacao[0],)
                        )
                    else:
                        placeholders = ",".join(["%s"] * len(lista_os_importacao))
                        df_prog = pd.read_sql_query(
                            f"""
                            SELECT
                                os,
                                dados_completos->>'Data inicial programada' AS dt_prog
                            FROM os_programadas
                            WHERE os IN ({placeholders})
                            """,
                            conn,
                            params=tuple(lista_os_importacao)
                        )
                finally:
                    release_connection(conn)

                if not df_prog.empty:
                    for _, row_prog in df_prog.iterrows():
                        mapa_dt_prog[str(row_prog["os"]).strip()] = pd.to_datetime(
                            row_prog["dt_prog"],
                            dayfirst=True,
                            errors="coerce"
                        )

                # 7. Monta lote final para UPSERT
                lote_valores = []

                for r in registros_baixa:
                    os_key = str(r["os"]).strip()

                    dt_prog = mapa_dt_prog.get(os_key, pd.NaT)
                    dt_exec = pd.to_datetime(
                        r["data_fim"],
                        format="%d/%m/%Y",
                        errors="coerce"
                    )

                    status_final = (
                        "Realizado Fora da Data de Programação"
                        if pd.notna(dt_prog)
                        and pd.notna(dt_exec)
                        and dt_exec.date() > dt_prog.date()
                        else "Realizado"
                    )

                    lote_valores.append((
                        os_key,
                        status_final,
                        str(r["realizado_em"]).strip(),
                        str(r["coordenacao"]).strip(),
                        str(r["concluido_por"]).strip(),
                        str(r["geolocalizacao_baixa"]).strip(),
                        str(r["equipe"]).strip(),
                        str(r["data_inicio"]).strip(),
                        str(r["hora_inicio"]).strip(),
                        str(r["data_fim"]).strip(),
                        str(r["hora_fim"]).strip()
                    ))

                # 8. Gravação em lote TURBO no Neon com trava de governança
                conn = get_connection()
                try:
                    cur = conn.cursor()

                    execute_values(
                        cur,
                        """
                        INSERT INTO baixas (
                            os,
                            status,
                            realizado_em,
                            coordenacao,
                            concluido_por,
                            geolocalizacao_baixa,
                            equipe,
                            data_inicio,
                            hora_inicio,
                            data_fim,
                            hora_fim
                        )
                        VALUES %s
                        ON CONFLICT (os) DO UPDATE SET
                            status = EXCLUDED.status,
                            realizado_em = EXCLUDED.realizado_em,
                            coordenacao = EXCLUDED.coordenacao,
                            concluido_por = EXCLUDED.concluido_por,
                            geolocalizacao_baixa = EXCLUDED.geolocalizacao_baixa,
                            equipe = EXCLUDED.equipe,
                            data_inicio = EXCLUDED.data_inicio,
                            hora_inicio = EXCLUDED.hora_inicio,
                            data_fim = EXCLUDED.data_fim,
                            hora_fim = EXCLUDED.hora_fim
                        WHERE
                            COALESCE(baixas.foto_evidencia, '') = ''
                            AND COALESCE(baixas.geolocalizacao_baixa, '') IN (
                                '',
                                'Baixa IW47',
                                'Importação IW47',
                                'Baixa Manual'
                            )
                            AND NOT EXISTS (
                                SELECT 1
                                FROM evidencias ev
                                WHERE TRIM(CAST(ev.os_referencia AS TEXT)) = TRIM(CAST(EXCLUDED.os AS TEXT))
                            );
                        """,
                        lote_valores,
                        page_size=1000
                    )

                    conn.commit()
                    cur.close()

                except Exception:
                    conn.rollback()
                    raise

                finally:
                    release_connection(conn)

                if alertas:
                    st.warning(f"⚠️ Importação concluída com {len(alertas)} alerta(s).")
                    with st.expander("Ver alertas da importação IW47", expanded=False):
                        for alerta in alertas[:300]:
                            st.write(f"- {alerta}")
                        if len(alertas) > 300:
                            st.write(f"... e mais {len(alertas) - 300} alerta(s).")

                st.success(
                    f"✅ {len(lote_valores)} OS processadas pela IW47. "
                    "OS com evidência/foto/GPS operacional foram preservadas pela trava SQL."
                )

                st.cache_data.clear()
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erro ao processar a planilha IW47: {e}")
    #endregion 3.8.5
#endregion 3.8

#region 3.9: Gerador Offline - Produção (HTML/JS completo)
def gerar_html_offline(df_pendentes: pd.DataFrame, usuario: str) -> bytes:
    if df_pendentes.empty:
        return b""

    colunas_export = ["Ordem servico", "Ativo", "Atividade ativo", "Patio", "Criticidade"]
    if "Descrição Longa" in df_pendentes.columns:
        colunas_export.append("Descrição Longa")

    df_export = df_pendentes.head(100)[colunas_export].fillna("")
    
    # Sanitização crítica para evitar que o JS quebre
    os_json = df_export.to_json(orient="records", force_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")

    usuarios_equipe = ["Sozinho (Nenhum)"]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT username FROM usuarios")
        for row in cur.fetchall():
            username = str(row[0]).strip()
            if username and username != usuario:
                usuarios_equipe.append(username)
        cur.close()
    except Exception:
        pass
    finally:
        release_connection(conn)

    usuarios_json = json.dumps(usuarios_equipe, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")

    api_url_fixa = st.secrets.get("OFFLINE_API_URL", "https://gestao-os-ee-mrs-producao.onrender.com/sincronizar_baixa_offline")
    api_key_fixa = st.secrets.get("OFFLINE_API_KEY", "")

    html_head = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SGO MRS - Modo Offline ({usuario})</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #F8FAFC; color: #0F172A; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 16px; }}
        .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; padding: 12px 16px; border-radius: 12px; background: #FFFFFF; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08); }}
        .title {{ margin: 0; font-size: 22px; font-weight: 700; color: #1E3A8A; }}
        .subtitle {{ margin: 4px 0 0 0; font-size: 14px; color: #475569; }}
        .status-badge {{ padding: 8px 12px; border-radius: 999px; font-size: 13px; font-weight: 700; color: #FFFFFF; white-space: nowrap; }}
        .status-online {{ background: #16A34A; }}
        .status-offline {{ background: #DC2626; }}
        .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
        .card {{ background: #FFFFFF; border-radius: 12px; padding: 16px; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08); }}
        .card h2 {{ margin-top: 0; margin-bottom: 10px; font-size: 18px; color: #1E293B; }}
        .toolbar {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        .toolbar-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
        .field {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }}
        .field label {{ font-size: 13px; color: #334155; font-weight: 600; }}
        .field input, .field select {{ width: 100%; padding: 10px 12px; border: 1px solid #CBD5E1; border-radius: 10px; font-size: 14px; background: #FFFFFF; }}
        .field input[readonly] {{ background: #E2E8F0; color: #475569; }}
        .btn {{ width: 100%; border: none; border-radius: 10px; padding: 12px 14px; cursor: pointer; font-size: 14px; font-weight: 700; }}
        .btn-primary {{ background: #1D4ED8; color: #FFFFFF; }}
        .btn-success {{ background: #059669; color: #FFFFFF; }}
        .btn-danger {{ background: #DC2626; color: #FFFFFF; }}
        .btn-secondary {{ background: #E2E8F0; color: #0F172A; }}
        .info-box {{ padding: 12px; border-radius: 10px; margin-bottom: 12px; font-size: 14px; }}
        .info-blue {{ background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }}
        .info-yellow {{ background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; }}
        .info-red {{ background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; }}
        .queue-counter {{ font-size: 28px; font-weight: 800; color: #0F172A; margin: 0; }}
        .os-list {{ display: grid; gap: 12px; }}
        .os-item {{ border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px; background: #FFFFFF; }}
        .os-item.locked {{ background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; opacity: 0.75; }}
        .os-header {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 10px; }}
        .os-title {{ font-size: 16px; font-weight: 800; color: #0F172A; }}
        .chip {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #E2E8F0; color: #334155; }}
        .chip-critical {{ background: #FEE2E2; color: #991B1B; }}
        .os-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        .os-meta {{ font-size: 13px; color: #475569; margin: 4px 0; }}
        .desc-box {{ padding: 10px; background: #F8FAFC; border-radius: 10px; border: 1px solid #E2E8F0; font-size: 13px; color: #334155; }}
        .small {{ font-size: 12px; color: #64748B; }}
        .footer-space {{ height: 24px; }}
        @media (max-width: 768px) {{ .toolbar, .toolbar-3, .os-grid {{ grid-template-columns: 1fr; }} .os-header {{ flex-direction: column; align-items: flex-start; }} }}
    </style>
</head>
<body>
"""
#endregion 3.9

#region 3.10: Gerador Offline - Estrutura do Corpo (HTML)
    html_body = f"""
    <div class="container">
        <div class="topbar">
            <div>
                <h1 class="title">⚡ Sistema de Gestão de Ordens de Serviço</h1>
                <p class="subtitle">Modo Offline de Produção • Operador: <strong>{usuario}</strong></p>
            </div>
            <div id="statusOnline" class="status-badge status-offline">📡 Offline</div>
        </div>

        <div class="grid">
            <div class="card">
                <h2>🔄 Sincronização e Fila</h2>
                <div class="toolbar-3">
                    <div>
                        <p class="small">OS aguardando envio</p>
                        <p class="queue-counter" id="filaCount">0</p>
                    </div>
                    <div class="field">
                        <label for="apiUrl">API Produção</label>
                        <input id="apiUrl" type="text" value="{api_url_fixa}" readonly>
                    </div>
                    <div class="field">
                        <label>X-API-Key</label>
                        <input type="password" value="••••••••••••••••" readonly>
                        <input id="apiKeyHidden" type="hidden" value="{api_key_fixa}">
                    </div>
                </div>

                <div class="toolbar" style="margin-top: 12px;">
                    <button id="btnSync" class="btn btn-success">Enviar Dados Localizados</button>
                    <button id="btnClear" class="btn btn-danger">🗑️ Limpar Filas e Reiniciar</button>
                </div>

                <div id="syncMsg" class="info-box info-blue" style="margin-top: 12px;">
                    O pacote salva as OS localmente e envia quando houver conexão disponível.
                </div>
            </div>

            <div class="card">
                <h2>🧭 Dados Operacionais</h2>
                <div class="toolbar">
                    <div class="field">
                        <label for="filtroAtivo">🔍 Filtrar por Ativo</label>
                        <input id="filtroAtivo" type="text" list="listaAtivos" placeholder="Todos os Ativos na Rota">
                        <datalist id="listaAtivos"></datalist>
                    </div>
                    <div class="field">
                        <label for="acompanhanteGlobal">👥 Acompanhante / Equipe (aplica a todas as OS)</label>
                        <select id="acompanhanteGlobal"></select>
                    </div>
                </div>

                <div id="criticaAlert" class="info-box info-yellow" style="display:none;">
                    ⚠️ <strong>Foco Operacional:</strong> Existem OS Críticas (Muito Alta). As demais ficam bloqueadas até que estas sejam concluídas.
                </div>

                <div class="toolbar">
                    <button id="btnSalvarLote" class="btn btn-primary">💾 Gravar OS(s) Preenchida(s)</button>
                    <button id="btnCapturarGps" class="btn btn-secondary">📍 Atualizar GPS Atual</button>
                </div>

                <div id="gpsInfo" class="info-box info-blue" style="margin-top: 12px;">
                    GPS ainda não capturado.
                </div>
            </div>

            <div class="card">
                <h2>📋 Sua Rota Offline</h2>
                <div id="osList" class="os-list"></div>
            </div>
        </div>

        <div class="footer-space"></div>
    </div>
"""
#endregion 3.10

#region 3.11: Gerador Offline - Lógica JS Core (Banco Local e Renderização)
    js_core = f"""
<script>
    const OS_DATA = {os_json};
    const USUARIOS_EQUIPE = {usuarios_json};
    const USUARIO_LOGADO = {json.dumps(usuario, ensure_ascii=False)};
    const API_URL_FIXA = {json.dumps(api_url_fixa, ensure_ascii=False)};
    const API_KEY_FIXA = {json.dumps(api_key_fixa, ensure_ascii=False)};

    const DB_NAME = "sgo_mrs_offline_prod";
    const STORE_NAME = "apontamentos";
    let db = null;
    let gpsAtual = null;

    function abrirDB() {{
        return new Promise((resolve, reject) => {{
            // Versão 2: Força o upgrade do banco para usar a OS como chave única
            const req = indexedDB.open(DB_NAME, 2); 
            req.onupgradeneeded = (event) => {{
                const database = event.target.result;
                if (database.objectStoreNames.contains(STORE_NAME)) {{
                    database.deleteObjectStore(STORE_NAME);
                }}
                // Transforma o os_id na chave primária (Impede duplicações na fila)
                const store = database.createObjectStore(STORE_NAME, {{ keyPath: "os_id" }});
                store.createIndex("status_sync", "status_sync", {{ unique: false }});
            }};
            req.onsuccess = () => {{
                db = req.result;
                resolve(db);
            }};
            req.onerror = () => reject(req.error);
        }});
    }}

    function txStore(mode) {{
        mode = mode || "readonly";
        const tx = db.transaction(STORE_NAME, mode);
        return tx.objectStore(STORE_NAME);
    }}

    function setStatusOnline() {{
        const el = document.getElementById("statusOnline");
        if (navigator.onLine) {{
            el.textContent = "📡 Online";
            el.className = "status-badge status-online";
        }} else {{
            el.textContent = "📡 Offline";
            el.className = "status-badge status-offline";
        }}
    }}

    function setSyncMsg(texto, tipo) {{
        tipo = tipo || "blue";
        const el = document.getElementById("syncMsg");
        el.textContent = texto;
        el.className = "info-box " + (tipo === "red" ? "info-red" : tipo === "yellow" ? "info-yellow" : "info-blue");
    }}

    function setGpsInfo(texto, tipo) {{
        tipo = tipo || "blue";
        const el = document.getElementById("gpsInfo");
        el.textContent = texto;
        el.className = "info-box " + (tipo === "red" ? "info-red" : tipo === "yellow" ? "info-yellow" : "info-blue");
    }}

    function popularEquipe() {{
        const sel = document.getElementById("acompanhanteGlobal");
        sel.innerHTML = "";
        USUARIOS_EQUIPE.forEach((nome) => {{
            const opt = document.createElement("option");
            opt.value = nome;
            opt.textContent = nome;
            sel.appendChild(opt);
        }});
    }}

    function popularListaAtivos() {{
        const datalist = document.getElementById("listaAtivos");
        if (!datalist) return;

        const ativosUnicos = [...new Set(
            OS_DATA.map(item => String(item.Ativo || "").trim()).filter(v => v)
        )].sort((a, b) => a.localeCompare(b, "pt-BR"));

        datalist.innerHTML = "";
        ativosUnicos.forEach((ativo) => {{
            const option = document.createElement("option");
            option.value = ativo;
            datalist.appendChild(option);
        }});
    }}

    function haOSCriticaPendente(lista) {{
        return lista.some((os) => String(os.Criticidade || "").trim().toUpperCase() === "MUITO ALTA");
    }}

    function renderListaOS() {{
        const filtro = document.getElementById("filtroAtivo").value.trim().toUpperCase();
        const osList = document.getElementById("osList");
        osList.innerHTML = "";

        const listaBase = OS_DATA
            .map((item, originalIdx) => ({{ ...item, _origIdx: originalIdx }}))
            .filter((item) => {{
                const ativo = String(item.Ativo || "").toUpperCase();
                const atividade = String(item["Atividade ativo"] || "").toUpperCase();
                const osId = String(item["Ordem servico"] || "").toUpperCase();
                return !filtro || ativo.includes(filtro) || atividade.includes(filtro) || osId.includes(filtro);
            }});

        const temCritica = haOSCriticaPendente(listaBase);
        document.getElementById("criticaAlert").style.display = temCritica ? "block" : "none";

        listaBase.forEach((item) => {{
            const idx = item._origIdx;
            const osId = String(item["Ordem servico"] || "").trim();
            const ativo = String(item.Ativo || "").trim();
            const atividade = String(item["Atividade ativo"] || "").trim();
            const patio = String(item.Patio || "").trim();
            const criticidade = String(item.Criticidade || "").trim();
            const desc = String(item["Descrição Longa"] || "").trim();
            const isCritica = criticidade.toUpperCase() === "MUITO ALTA";
            const locked = temCritica && !isCritica;

            const wrapper = document.createElement("div");
            wrapper.className = "os-item" + (locked ? " locked" : "");
            // Adicionando um ID para podermos manipular o card depois
            wrapper.id = `card_os_${{idx}}`;

            wrapper.innerHTML = `
                <div class="os-header">
                    <div class="os-title">OS ${{osId}}</div>
                    <div class="chip ${{isCritica ? "chip-critical" : ""}}">${{criticidade || "Sem criticidade"}}</div>
                </div>

                <div class="os-meta"><strong>Ativo:</strong> ${{ativo}}</div>
                <div class="os-meta"><strong>Atividade:</strong> ${{atividade}}</div>
                <div class="os-meta"><strong>Pátio:</strong> ${{patio}}</div>
                ${{desc ? `<div class="desc-box" style="margin: 10px 0;"><strong>Descrição:</strong><br>${{desc}}</div>` : ""}}

                <div class="os-grid" style="margin-top: 10px;">
                    <div class="field">
                        <label for="ini_${{idx}}">Horário Início</label>
                        <input id="ini_${{idx}}" type="time" ${{locked ? "disabled" : ""}}>
                    </div>
                    <div class="field">
                        <label for="fim_${{idx}}">Horário Fim</label>
                        <input id="fim_${{idx}}" type="time" ${{locked ? "disabled" : ""}}>
                    </div>
                </div>

                <div class="field">
                    <label for="foto_${{idx}}">📷 Evidência Fotográfica</label>
                    <input id="foto_${{idx}}" type="file" accept=".jpg,.jpeg,.png,image/*" capture="environment" ${{locked ? "disabled" : ""}}>
                </div>
            `;
            osList.appendChild(wrapper);
        }});
    }}

    async function capturarGPS() {{
        return new Promise((resolve) => {{
            if (!navigator.geolocation) {{
                setGpsInfo("Este navegador não suporta geolocalização.", "red");
                return resolve(null);
            }}

            navigator.geolocation.getCurrentPosition(
                (pos) => {{
                    gpsAtual = {{
                        lat: Number(pos.coords.latitude),
                        lon: Number(pos.coords.longitude),
                        accuracy: pos.coords.accuracy || null,
                        timestamp: new Date().toISOString()
                    }};
                    setGpsInfo(`GPS capturado: Lat ${{gpsAtual.lat.toFixed(6)}}, Lon ${{gpsAtual.lon.toFixed(6)}}`, "blue");
                    resolve(gpsAtual);
                }},
                (err) => {{
                    setGpsInfo(`Falha ao capturar GPS: ${{err.message}}`, "red");
                    resolve(null);
                }},
                {{
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 0
                }}
            );
        }});
    }}
"""
#endregion 3.11

#region 3.12: Gerador Offline - Lógica JS de Lote / Persistência
    # REMOVIDO a tag <script> daqui, ele continua a execução do js_core diretamente
    js_lote = f"""
    function calcularDuracaoHoras(inicio, fim) {{
        if (!inicio || !fim) return null;

        const [hi, mi] = inicio.split(":").map(Number);
        const [hf, mf] = fim.split(":").map(Number);

        let minsIni = hi * 60 + mi;
        let minsFim = hf * 60 + mf;

        if (minsFim < minsIni) {{
            minsFim += 24 * 60;
        }}

        return (minsFim - minsIni) / 60.0;
    }}

    async function salvarSelecionadasNoLote() {{
        const acompanhanteGlobal = document.getElementById("acompanhanteGlobal").value || "Sozinho (Nenhum)";
        const selecionadas = [];
        const indicesParaLimpar = []; // Guarda quem devemos apagar da tela depois de salvar

        for (let i = 0; i < OS_DATA.length; i += 1) {{
            const elIni = document.getElementById(`ini_${{i}}`);
            const elFim = document.getElementById(`fim_${{i}}`);
            const inicio = elIni ? elIni.value : "";
            const fim = elFim ? elFim.value : "";
            const fileInput = document.getElementById(`foto_${{i}}`);
            const foto = (fileInput && fileInput.files && fileInput.files.length > 0) ? fileInput.files[0] : null;
            const osItem = OS_DATA[i];

            if (!(inicio && fim && foto)) continue;

            const duracaoHoras = calcularDuracaoHoras(inicio, fim);
            if (duracaoHoras !== null && duracaoHoras > 12) {{
                const ok = confirm(
                    `A duração calculada da OS ${{osItem["Ordem servico"]}} é de ${{duracaoHoras.toFixed(1)}}h. Confirma gravar mesmo assim?`
                );
                if (!ok) return;
            }}

            selecionadas.push({{
                os_id: String(osItem["Ordem servico"] || "").trim(),
                ativo_id: String(osItem["Ativo"] || "").trim(),
                usuario: USUARIO_LOGADO,
                acompanhante: acompanhanteGlobal === "Sozinho (Nenhum)" ? "" : acompanhanteGlobal,
                horario_inicio: inicio.length === 5 ? `${{inicio}}:00` : inicio,
                horario_fim: fim.length === 5 ? `${{fim}}:00` : fim,
                data_hora_local: new Date().toISOString(),
                lat_browser: gpsAtual ? gpsAtual.lat : 0.0,
                lon_browser: gpsAtual ? gpsAtual.lon : 0.0,
                criticidade: String(osItem["Criticidade"] || "").trim(),
                status_sync: "pendente",
                foto_blob: foto,
                criado_em: new Date().toISOString()
            }});
            
            indicesParaLimpar.push(i);
        }}

        if (!selecionadas.length) {{
            alert("Nenhuma OS preenchida para gravação.");
            return;
        }}

        await Promise.all(
            selecionadas.map((item) => new Promise((resolve, reject) => {{
                const req = txStore("readwrite").put(item);
                req.onsuccess = () => resolve(true);
                req.onerror = () => reject(req.error);
            }}))
        );

        // UPDATE: Remoção Visual do Card (A OS sai da lista!)
        // Assim o técnico sabe visualmente que aquela OS já foi para a fila.
        indicesParaLimpar.forEach((i) => {{
            const cardOS = document.getElementById(`card_os_${{i}}`);
            if (cardOS) {{
                cardOS.style.display = "none";
            }}
        }});

        await atualizarFila();
        setSyncMsg(`${{selecionadas.length}} OS gravada(s) localmente com sucesso.`, "blue");
        alert(`✅ ${{selecionadas.length}} OS movida(s) para a fila de envio.`);
    }}

    async function atualizarFila() {{
        return new Promise((resolve, reject) => {{
            const req = txStore("readonly").getAll();
            req.onsuccess = () => {{
                const registros = req.result || [];
                const pendentes = registros.filter((r) => r.status_sync === "pendente");
                document.getElementById("filaCount").textContent = String(pendentes.length);
                resolve(pendentes.length);
            }};
            req.onerror = () => reject(req.error);
        }});
    }}

    async function limparFila() {{
        const ok = confirm("Deseja realmente apagar toda a fila local e reiniciar o pacote offline?");
        if (!ok) return;

        await new Promise((resolve, reject) => {{
            const req = txStore("readwrite").clear();
            req.onsuccess = () => resolve(true);
            req.onerror = () => reject(req.error);
        }});

        await atualizarFila();
        setSyncMsg("Fila local apagada com sucesso.", "yellow");
    }}
"""
#endregion 3.12

#region 3.13: Gerador Offline - Lógica JS de Sincronização e Fechamento
    # Lógica de Sincronização com tratamento de erros (UX Limpa)
    js_sync = f"""
    async function sincronizarFila() {{
        const apiUrl = API_URL_FIXA;
        const apiKey = API_KEY_FIXA;

        if (!apiUrl) {{
            alert("URL da API offline não configurada no pacote.");
            return;
        }}
        if (!apiKey) {{
            alert("API Key offline não configurada no pacote.");
            return;
        }}
        if (!navigator.onLine) {{
            alert("Sem internet. Conecte-se antes de sincronizar.");
            return;
        }}

        const registros = await new Promise((resolve, reject) => {{
            const req = txStore("readonly").getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error);
        }});

        const pendentes = registros.filter((r) => r.status_sync === "pendente");
        if (!pendentes.length) {{
            setSyncMsg("Nenhuma OS pendente para sincronizar.", "yellow");
            return;
        }}

        let sucesso = 0;
        let falha = 0;
        const detalhesFalha = [];

        for (const item of pendentes) {{
            try {{
                const formData = new FormData();
                formData.append("os_id", item.os_id);
                formData.append("ativo_id", item.ativo_id);
                formData.append("usuario", item.usuario);
                formData.append("lat_browser", String(item.lat_browser || 0.0));
                formData.append("lon_browser", String(item.lon_browser || 0.0));
                formData.append("data_hora_local", item.data_hora_local);
                formData.append("acompanhante", item.acompanhante || "");
                formData.append("horario_inicio", item.horario_inicio);
                formData.append("horario_fim", item.horario_fim);
                formData.append("foto", item.foto_blob, `${{item.ativo_id}}_${{item.os_id}}.jpg`);

                const resp = await fetch(apiUrl, {{
                    method: "POST",
                    headers: {{
                        "x-api-key": apiKey
                    }},
                    body: formData
                }});

                // --- ATUALIZAÇÃO UX: Tratamento de Erros Limpo ---
                if (!resp.ok) {{
                    let msgErro = "Falha na comunicação com o servidor.";
                    try {{
                        const errJson = await resp.json();
                        // Se a API mandar o erro dentro de 'detail', extrai só o texto
                        if (errJson.detail) {{
                            msgErro = errJson.detail;
                        }} else {{
                            msgErro = JSON.stringify(errJson);
                        }}
                    }} catch (parseErr) {{
                        // Se não for JSON, pega o texto puro ou o código do erro
                        msgErro = await resp.text() || `Erro no servidor (Código ${{resp.status}})`;
                    }}
                    throw new Error(msgErro);
                }}

                await new Promise((resolve, reject) => {{
                    const reqUpdate = txStore("readwrite").put({{
                        ...item,
                        status_sync: "sincronizado",
                        sincronizado_em: new Date().toISOString()
                    }});
                    reqUpdate.onsuccess = () => resolve(true);
                    reqUpdate.onerror = () => reject(reqUpdate.error);
                }});

                sucesso += 1;
            }} catch (e) {{
                console.error("Falha na sincronização da OS", item.os_id, e);
                falha += 1;
                // e.message agora contém apenas o texto limpo, sem "HTTP 403"
                detalhesFalha.push(`OS ${{item.os_id}}: ${{e.message || "Erro desconhecido"}}`);
            }}
        }}

        await atualizarFila();

        if (falha === 0) {{
            setSyncMsg(`Sincronização concluída com sucesso. ${{sucesso}} OS enviada(s).`, "blue");
        }} else {{
            const detalhe = detalhesFalha.length ? ` Motivo: ${{detalhesFalha[0]}}` : "";
            setSyncMsg(`Sincronização parcial. ${{sucesso}} enviada(s) e ${{falha}} falha(s).${{detalhe}}`, "yellow");
        }}
    }}

    async function bootstrap() {{
        await abrirDB();
        setStatusOnline();
        popularEquipe();
        popularListaAtivos();
        renderListaOS();
        await atualizarFila();

        window.addEventListener("online", setStatusOnline);
        window.addEventListener("offline", setStatusOnline);

        document.getElementById("filtroAtivo").addEventListener("input", renderListaOS);
        document.getElementById("btnCapturarGps").addEventListener("click", capturarGPS);
        document.getElementById("btnSalvarLote").addEventListener("click", salvarSelecionadasNoLote);
        document.getElementById("btnSync").addEventListener("click", sincronizarFila);
        document.getElementById("btnClear").addEventListener("click", limparFila);
    }}

    bootstrap().catch((err) => {{
        console.error(err);
        alert("Falha ao inicializar o pacote offline.");
    }});
</script>
</body>
</html>
"""

    html_final = html_head + html_body + js_core + js_lote + js_sync
    return html_final.encode("utf-8")
#endregion 3.13
#endregion

#region SESSÃO 4: Banco de Coordenadas Fixo

#region 4.1: Coordenadas Fixa
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

def obter_base_padrao_usuario():
    username = str(st.session_state.get("username", "")).strip()
    escopo = str(st.session_state.get("escopo", "")).strip()

    mapa_normalizacao = {
        "Paranapiacaba": ("IPA", "Sede IPA"), "Piaçaguera": ("IPG", "Sede IPG"),
        "Todas": ("IPA", "Sede Padrão (IPA)"), "ICG": ("ICG", "Campo Grande (ICG)"),
        "IPA": ("IPA", "Sede IPA"), "IPG": ("IPG", "Base IPG"),
        "SEDE IPA": ("IPA", "Sede IPA"), "SEDE IPG": ("IPG", "Sede IPG"),
    }
    valor_base = None
    if username:
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT coordenacao_padrao FROM usuarios WHERE username = %s", (username,))
            row = cur.fetchone()
            cur.close()
            if row and row[0]: valor_base = str(row[0]).strip()
        except Exception: valor_base = None
        finally:
            if conn is not None: release_connection(conn)

    if not valor_base: valor_base = escopo
    valor_base = str(valor_base).strip()
    valor_base_upper = valor_base.upper()

    if valor_base in mapa_normalizacao: chave_coord, nome_exibicao = mapa_normalizacao[valor_base]
    elif valor_base_upper in mapa_normalizacao: chave_coord, nome_exibicao = mapa_normalizacao[valor_base_upper]
    else: chave_coord, nome_exibicao = ("IPA", "Base Padrão (IPA)")

    coord = COORDENADAS_FIXAS.get(chave_coord, COORDENADAS_FIXAS["IPA"])
    return float(coord[0]), float(coord[1]), nome_exibicao
#endregion SESSÃO 4
#endregion

#region SESSÃO 5: ETL (Carregamento e Tratamento)
ETL_VERSION = "v6_leitura_crua_status_avancado"

#region 5.1: Tratamento Principal (tratar_df_os + _resolver_patio)
def tratar_df_os(df: pd.DataFrame):
    df = normalize_cols(df)
    col_os = pick_first_existing(df, ["ORDEM SERVICO", "ORDEM SERVIÇO", "OS"])
    col_ativo = pick_first_existing(df, ["ATIVO", "EQUIPAMENTO"])
    col_atividade = pick_first_existing(df, ["ATIVIDADE ATIVO", "ATIVIDADE_ATIVO", "ATIVIDADE"])
    col_prioridade = pick_first_existing(df, ["PRIORIDADE", "CRITICIDADE"])
    col_hxh = pick_first_existing(df, ["HXH PLANO", "HXH_PLANO"])
    col_data_prog = pick_first_existing(df, ["DATA INICIAL PROGRAMADA", "DATA PROGRAMADA"])
    col_status = pick_first_existing(df, ["STATUS DA OPERAÇÃO", "STATUS", "STATUS_OPERACAO"])
    col_desc = pick_first_existing(df, ["DESCRIÇÃO LONGA", "DESCRICAO LONGA", "TEXTO LONGO"])

    missing = []
    if not col_os: missing.append("ORDEM SERVICO")
    if not col_ativo: missing.append("ATIVO")
    if not col_atividade: missing.append("ATIVIDADE ATIVO")
    if not col_prioridade: missing.append("PRIORIDADE")
    if not col_data_prog: missing.append("DATA INICIAL PROGRAMADA")
    if missing: raise ValueError(f"Colunas obrigatórias ausentes no Excel: {', '.join(missing)}")

    df["ATIVO_CAN"] = df[col_ativo].astype(str).str.strip()
    df["ATIVIDADE_CAN"] = df[col_atividade].astype(str).str.strip()
    df["PRIORIDADE_CAN"] = df[col_prioridade].astype(str).str.strip()
    df["HXH_CAN"] = pd.to_numeric(df[col_hxh], errors="coerce").fillna(0) if col_hxh else 0.0
    
    _mapa_patios = carregar_mapeamento_patios()
    _patios_validos = set(k for k in COORDENADAS_FIXAS.keys() if not k.startswith("Sede"))

    def _resolver_patio(ativo_str: str) -> str:
        ativo_upper = str(ativo_str).strip().upper()
        if _mapa_patios and ativo_upper in _mapa_patios: return _mapa_patios[ativo_upper]
        prefixo = ativo_upper[:3]
        if prefixo in _patios_validos: return prefixo
        if _mapa_patios:
            for chave_mapa, patio_mapa in _mapa_patios.items():
                if chave_mapa in ativo_upper or ativo_upper in chave_mapa: return patio_mapa
        for patio_candidato in sorted(_patios_validos, key=len, reverse=True):
            if patio_candidato in ativo_upper: return patio_candidato
        return "N/D"

    df["PATIO_CAN"] = df["ATIVO_CAN"].apply(_resolver_patio)
    df["DATA_PROG_CAN"] = df[col_data_prog].apply(parse_data_programada)
    df["DESC_LONGA_CAN"] = df[col_desc].astype(str).str.strip() if col_desc else ""
    
    col_sem_int = pick_first_existing(df, ["SEM INTERVALO", "S_I", "SEM_INTERVALO"])
    col_com_int = pick_first_existing(df, ["COM INTERVALO", "C_I", "COM_INTERVALO"])
    def _classificar_intervalo(row):
        si = str(row[col_sem_int]).strip().upper() if col_sem_int and pd.notna(row.get(col_sem_int)) else ""
        ci = str(row[col_com_int]).strip().upper() if col_com_int and pd.notna(row.get(col_com_int)) else ""
        if si in ("S_I", "SI", "S"): return "Sem Intervalo"
        if ci in ("C_I", "CI", "C"): return "Com Intervalo"
        return "N/D"
    df["TIPO_INTERVALO_CAN"] = df.apply(_classificar_intervalo, axis=1) if (col_sem_int or col_com_int) else "N/D"

    df["Classificacao"] = df["ATIVIDADE_CAN"].apply(classificar_atividade)
    crit = df["PRIORIDADE_CAN"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]
    df["Nivel_Prioridade"] = df.apply(lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]), axis=1)

    hoje_data = datetime.now().date()
    def definir_status_cru(row):
        st_atual = str(row[col_status]).strip().upper() if pd.notna(row[col_status]) and col_status else ""
        if "REALIZADO" in st_atual:
            if "FORA" in st_atual or "ATRASO" in st_atual: return "Realizado Fora da Data de Programação"
            return "Realizado"
        dp = row["DATA_PROG_CAN"]
        if pd.isna(dp): return "Pendente"
        if dp.date() >= hoje_data: return "Pendente"
        else: return "Atrasado"

    df["STATUS_CAN"] = df.apply(definir_status_cru, axis=1)

    df_out = pd.DataFrame({
        "Ordem servico": df[col_os].astype(str).str.strip(),
        "Patio": df["PATIO_CAN"], "Ativo": df["ATIVO_CAN"], "Atividade ativo": df["ATIVIDADE_CAN"],
        "Criticidade": df["Criticidade"], "Classificacao": df["Classificacao"], "Descrição Longa": df["DESC_LONGA_CAN"],
        "Data inicial programada": df["DATA_PROG_CAN"], "Status da Operação": df["STATUS_CAN"],
        "Data/Hora Realizado": "", "Concluído por": "", "Hxh Plano": df["HXH_CAN"],
        "Criticidade_rank": df["Criticidade_rank"], "Nivel_Prioridade": df["Nivel_Prioridade"],
        "TIPO_INTERVALO_CAN": df["TIPO_INTERVALO_CAN"],
    })
    return df_out

@st.cache_data
def carregar_base_sem_overlay(usar_sim: bool, qtd_sim: int, seed_sim: int, escopo_usuario: str, etl_version: str) -> pd.DataFrame:
    if usar_sim:
        pct_p = st.session_state.get("sim_pct_pendente", 45)
        pct_ok = st.session_state.get("sim_pct_prazo", 40)
        pct_a = st.session_state.get("sim_pct_atraso", 15)
        return gerar_base_simulada(qtd=qtd_sim, seed=seed_sim, pct_p=pct_p, pct_ok=pct_ok, pct_a=pct_a)

    conn = get_connection()
    try: df_raw_db = pd.read_sql_query("SELECT os, coordenacao, dados_completos FROM os_programadas", conn)
    except Exception as e: df_raw_db = pd.DataFrame()
    finally: release_connection(conn)

    if df_raw_db.empty: return pd.DataFrame()

    _mapa_depto_fallback = {"E.SP.IPA": "Paranapiacaba", "E.SP.IPG": "Piaçaguera"}

    def _resolver_coord_null(row):
        coord = row["coordenacao"]
        if pd.notna(coord) and str(coord).strip() != "": return str(coord).strip()
        dados = row["dados_completos"]
        if isinstance(dados, str):
            try: dados = json.loads(dados)
            except Exception: return "N/D"
        if isinstance(dados, dict):
            for chave in ["Codigo departamento", "CODIGO DEPARTAMENTO", "Concatenar", "CONCATENAR"]:
                val = str(dados.get(chave, "")).strip().upper()
                if val:
                    for prefixo, coord_nome in _mapa_depto_fallback.items():
                        if val.startswith(prefixo): return coord_nome
        return "N/D"

    df_raw_db["coordenacao"] = df_raw_db.apply(_resolver_coord_null, axis=1)

    _mapa_norm = {
        "PARANAPIACABA": "Paranapiacaba", "PIAÇAGUERA": "Piaçaguera", "PIACAGUERA": "Piaçaguera",
        "IPG": "Piaçaguera", "IPA": "Paranapiacaba", "E.SP.IPG": "Piaçaguera", "E.SP.IPA": "Paranapiacaba",
    }
    df_raw_db["coordenacao"] = df_raw_db["coordenacao"].apply(
        lambda v: _mapa_norm.get(re.sub(r'\s+', ' ', str(v)).strip().upper(), str(v).strip()) if pd.notna(v) and str(v).strip() != "" else "N/D"
    )

    dfs_tratados = []
    for coord, group in df_raw_db.groupby("coordenacao", dropna=False):
        coord_str = str(coord).strip() if pd.notna(coord) else "N/D"
        coord_str = _mapa_norm.get(coord_str.upper(), coord_str)
        lista_linhas = []
        for _, row in group.iterrows():
            dados = row["dados_completos"]
            if isinstance(dados, str):
                try: dados = json.loads(dados)
                except Exception: continue
            lista_linhas.append(dados)

        if lista_linhas:
            df_bruto_coord = pd.DataFrame(lista_linhas)
            try:
                df_tratado_coord = tratar_df_os(df_bruto_coord)
                df_tratado_coord["Coordenacao"] = coord_str
                dfs_tratados.append(df_tratado_coord)
            except Exception as e:
                import logging
                logging.error(f"[ETL] ERRO ao tratar coordenação '{coord_str}': {e}")

    if not dfs_tratados: return pd.DataFrame()
    df_base_final = pd.concat(dfs_tratados, ignore_index=True)

    if escopo_usuario != "Todas":
        escopo_norm = _mapa_norm.get(escopo_usuario.strip().upper(), escopo_usuario.strip())
        df_base_final = df_base_final[df_base_final["Coordenacao"].apply(lambda x: str(x).strip().upper() == escopo_norm.upper() if pd.notna(x) else False)]

    return df_base_final

@st.cache_data(show_spinner=False)
def aplicar_overlay_baixas(df_base_bruto: pd.DataFrame, escopo_usuario: str, baixas_mtime: float) -> pd.DataFrame:
    df_base = df_base_bruto.copy()
    if df_base.empty: return df_base

    if "Status da Operação" in df_base.columns:
        df_base["Status da Operação"] = df_base["Status da Operação"].replace(["", "nan", "NaN", "None"], "Pendente")

    df_baixas = carregar_baixas_df()
    if df_baixas.empty: return df_base
    df_base["Ordem servico"] = df_base["Ordem servico"].astype(str)

    if escopo_usuario != "Todas":
        df_baixas = df_baixas[df_baixas["coordenacao"].str.contains(escopo_usuario, case=False, na=False, regex=False)]

    colunas_overlay = ["Status da Operação", "Data/Hora Realizado", "Concluído por", "Geolocalização de Baixa"]
    for col in colunas_overlay:
        if col not in df_base.columns: df_base[col] = ""

    df_baixas = df_baixas.rename(columns={
        "os": "Ordem servico", "status": "Status da Operação", 
        "realizado_em": "Data/Hora Realizado", "concluido_por": "Concluído por", "geolocalizacao_baixa": "Geolocalização de Baixa"
    })

    # CORREÇÃO: Adiciona a foto_evidencia na lista de coisas que serão mescladas
    cols_merge = ["Ordem servico"] + colunas_overlay
    if "foto_evidencia" in df_baixas.columns:
        cols_merge.append("foto_evidencia")

    df_base = df_base.merge(df_baixas[cols_merge], on="Ordem servico", how="left", suffixes=("", "_baixado"))
    
    for col in colunas_overlay:
        df_base[col] = np.where(df_base[f"{col}_baixado"].notna() & (df_base[f"{col}_baixado"] != ""), df_base[f"{col}_baixado"], df_base[col])
        df_base.drop(columns=[f"{col}_baixado"], inplace=True)
        
    # Salva a foto na base final limpa
    if "foto_evidencia_baixado" in df_base.columns:
        df_base["foto_evidencia"] = df_base["foto_evidencia_baixado"]
        df_base.drop(columns=["foto_evidencia_baixado"], inplace=True)

    return df_base
#endregion 5.4
#endregion SESSÃO 5

#region SESSÃO 6: Simulação de Dados (Ambiente de Teste)
def gerar_base_simulada(qtd: int = 800, seed: int = 42, pct_p: int = 45, pct_ok: int = 40, pct_a: int = 15) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    patios = ["IAA", "IEF", "OLU", "IPA", "IRS", "IPG", "ICG", "IRG", "IOF", "ISU", "ILA", "IJN", "ZPD", "IIP"]
    prioridades = ["1-Muito Alta", "2-Alta", "3-Média", "4-Baixa"]
    prob_prio = [0.18, 0.32, 0.30, 0.20]
    atividades = ["EE_INS_SEG_C_I_MAQ CHAVE MOLA_1800", "EE_MAN_CONF_C_I_CANALETA SUBESTACAO_0720", "EE_INS_CONF_S_I_BATERIAS_0360"]
    prob_ativ = [0.35, 0.30, 0.35]

    total_pct = pct_p + pct_ok + pct_a
    if total_pct == 0: prob_status = [0.45, 0.40, 0.15]
    else: prob_status = [pct_p / total_pct, pct_ok / total_pct, pct_a / total_pct]

    status_list = ["Não Realizado", "Realizado", "Realizado Fora da Data de Programação"]
    hoje = datetime.now()
    dias_atras = rng.integers(0, 30, size=qtd)
    data_prog = [hoje - pd.Timedelta(days=int(d)) for d in dias_atras]
    data_prog = pd.to_datetime(data_prog).normalize()

    df = pd.DataFrame({
        "Ordem servico": [f"OS-{100000+i}" for i in range(qtd)], "Patio": rng.choice(patios, size=qtd),
        "Ativo": [f"{rng.choice(patios)}-ATV-{i:04d}" for i in range(qtd)],
        "Atividade ativo": rng.choice(atividades, size=qtd, p=prob_ativ), "Prioridade": rng.choice(prioridades, size=qtd, p=prob_prio),
        "Hxh Plano": np.round(rng.uniform(0.5, 8.0, size=qtd), 1), "Data inicial programada": data_prog,
        "Coordenacao": rng.choice(["Paranapiacaba", "Piaçaguera"], size=qtd)
    })

    df["Classificacao"] = df["Atividade ativo"].apply(classificar_atividade)
    crit = df["Prioridade"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]
    df["Nivel_Prioridade"] = df.apply(lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]), axis=1)
    df["Status da Operação"] = rng.choice(status_list, size=qtd, p=prob_status)
    df["Data/Hora Realizado"] = ""

    tecnicos_mock = ["Julio Paz (Sim)", "Carlos Silva (Sim)", "Ana Souza (Sim)", "Roberto Gomes (Sim)"]
    baixas_sim, logs_sim = [], []

    for i in range(qtd):
        stt = df.at[i, "Status da Operação"]
        if stt == "Não Realizado": continue
        prog = pd.to_datetime(df.at[i, "Data inicial programada"])
        
        if stt == "Realizado": delta = int(rng.integers(0, 4)); real_date = (prog - pd.Timedelta(days=delta)).to_pydatetime()
        else: delta = int(rng.integers(1, 11)); real_date = (prog + pd.Timedelta(days=delta)).to_pydatetime()

        # --- NOVA LÓGICA DE SIMULAÇÃO DOS TURNOS ---
        turno_alvo = rng.choice(["Administrativo", "Turno Dia", "Turno Noite"], p=[0.45, 0.35, 0.20])
        
        if turno_alvo == "Administrativo":
            # Força dia de semana para o Administrativo
            while real_date.weekday() >= 5: real_date -= pd.Timedelta(days=1)
            hh, mm = int(rng.integers(8, 16)), int(rng.integers(0, 59))
        elif turno_alvo == "Turno Noite":
            # Qualquer dia, mas horário noturno
            hh, mm = int(rng.choice([19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6])), int(rng.integers(0, 59))
        else:
            # Turno Dia: Força fim de semana para garantir que o sistema leia como "Turno Dia" puro
            while real_date.weekday() < 5: real_date += pd.Timedelta(days=1)
            hh, mm = int(rng.integers(7, 18)), int(rng.integers(0, 59))

        real_dt = real_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
        df.at[i, "Data/Hora Realizado"] = formatar_dt_br(real_dt)
        duracao_mins = int(rng.integers(20, 240))
        ini_dt = real_dt - pd.Timedelta(minutes=duracao_mins)
        tec = rng.choice(tecnicos_mock)
        
        # Simula Fraude de GPS (para pegar na Governança)
        gps_str = f"Lat: -23.{rng.integers(100,999)}, Lon: -46.{rng.integers(100,999)}"
        if rng.random() < 0.1: gps_str = "Sede IPA (Lat: -23.767, Lon: -46.344)"

        baixas_sim.append({
            "os": df.at[i, "Ordem servico"], "status": stt, "realizado_em": formatar_dt_br(real_dt), "coordenacao": df.at[i, "Coordenacao"],
            "concluido_por": tec, "geolocalizacao_baixa": gps_str, "equipe": "", "data_inicio": ini_dt.strftime("%d/%m/%Y"),
            "hora_inicio": ini_dt.strftime("%H:%M:%S"), "data_fim": real_dt.strftime("%d/%m/%Y"), "hora_fim": real_dt.strftime("%H:%M:%S")
        })

    st.session_state["df_baixas_sim"] = pd.DataFrame(baixas_sim)
    for tec in tecnicos_mock:
        for dia in pd.date_range(end=datetime.now(), periods=15):
            login_dt = dia.replace(hour=int(rng.integers(6,8)), minute=int(rng.integers(0,59)))
            logs_sim.append({"username": tec, "data_hora_login": login_dt})
    st.session_state["df_logs_sim"] = pd.DataFrame(logs_sim)

    return df

_DEV_MODE = os.getenv("DEV_MODE", "0") == "1"
if _DEV_MODE:
    def simulacao_sidebar():
        st.sidebar.header("🧪 Simulação (Teste)")
        usar_sim = st.sidebar.checkbox("Usar dados simulados (teste KPIs)", value=False)
        if not usar_sim: return False, None
        qtd_sim = st.sidebar.slider("Quantidade de OS simuladas", 100, 4000, 1200, 100)
        seed_sim = st.sidebar.number_input("Seed (repete os mesmos dados)", min_value=1, max_value=999999, value=42, step=1)
        df_sim = gerar_base_simulada(qtd=int(qtd_sim), seed=int(seed_sim))
        st.sidebar.info("✅ Simulação ativa. Excel real NÃO será carregado.")
        return True, df_sim
#endregion SESSÃO 6

#region SESSÃO 7: Sidebar, Navegação, Carga e Filtro

#region SESSÃO 7: Sidebar, Navegação, Carga e Filtro

#region 7.1: Identidade visual, navegação e escopo
st.markdown("""
    <style>
    /* 1. FORÇANDO O FUNDO DA SIDEBAR PARA DARK/PRETO */
    [data-testid="stSidebar"], 
    [data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebarContent"] { 
        background-color: #0F172A !important; 
    }
    
    /* 2. TEXTOS DA SIDEBAR EM BRANCO/CINZA CLARO */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] h4, [data-testid="stSidebar"] h5, [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] small, [data-testid="stSidebar"] caption { color: #F8FAFC !important; }
    
    /* 3. ESTILIZAÇÃO DOS WIDGETS DA SIDEBAR */
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 10px 16px !important; background-color: transparent !important;
        border-radius: 8px !important; margin-bottom: 6px !important;
        transition: all 0.2s ease-in-out !important; cursor: pointer !important; color: #CBD5E1 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background-color: rgba(255, 255, 255, 0.08) !important; color: #FFFFFF !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) { background-color: rgba(255, 75, 75, 0.2) !important; border-left: 4px solid #FF4B4B !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p { font-weight: bold !important; color: #FFFFFF !important; }
    [data-testid="stSidebar"] .stSelectbox label p, [data-testid="stSidebar"] .stMultiSelect label p, [data-testid="stSidebar"] .stDateInput label p {
        font-size: 14px !important; font-weight: 700 !important; color: #F8FAFC !important; margin-bottom: 4px;
    }
    .stMultiSelect [data-baseweb="tag"] { background-color: #FF4B4B !important; color: white !important; border-radius: 6px !important; }
    [data-testid="stSidebar"] div[data-baseweb="select"] > div, [data-testid="stSidebar"] div[data-baseweb="input"] > div, [data-testid="stSidebar"] div[data-baseweb="base-input"] > input {
        background-color: #1E293B !important; border-color: #475569 !important; border-radius: 6px !important; color: white !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] span, [data-testid="stSidebar"] div[data-baseweb="input"] input { color: white !important; }
    
    /* 4. EXPANDERS (Painel Retrátil na Sidebar) */
    [data-testid="stSidebar"] [data-testid="stExpander"] details { border: 1px solid #FF4B4B !important; border-radius: 8px !important; overflow: hidden; }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary { background-color: #FF4B4B !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p { color: #FFFFFF !important; font-weight: 800 !important; font-size: 16px !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] svg { fill: #FFFFFF !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] { background-color: #0F172A !important; padding-top: 15px !important; }
    
    /* ============================================================================== */
    /* 5. BOTÕES EM GRADIENTE (GLOBAL PARA TODO O APLICATIVO) */
    /* ============================================================================== */
    
    /* Botões Secundários (Gerais / Navegação) -> Gradiente Azul Profundo */
    button[kind="secondary"] {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.3s ease !important;
        font-weight: 600 !important;
    }
    button[kind="secondary"]:hover {
        background: linear-gradient(135deg, #2563EB 0%, #60A5FA 100%) !important;
        box-shadow: 0 6px 12px rgba(59, 130, 246, 0.4) !important;
        transform: translateY(-2px) !important;
        color: #FFFFFF !important;
    }

    /* Botões Primários (Ações Fortes / Aplicar / Salvar) -> Gradiente Rubi/Vermelho */
    button[kind="primary"] {
        background: linear-gradient(135deg, #991B1B 0%, #EF4444 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.3s ease !important;
        font-weight: 700 !important;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(135deg, #DC2626 0%, #F87171 100%) !important;
        box-shadow: 0 6px 12px rgba(239, 68, 68, 0.4) !important;
        transform: translateY(-2px) !important;
        color: #FFFFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

st.sidebar.image("logo_mrs.png", use_container_width=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

st.sidebar.markdown("### 🧭 Navegação")
if "tela_atual" not in st.session_state: st.session_state["tela_atual"] = "dashboard"

gov_usuario = st.session_state.get("governanca", "")
tem_painel = "Painel Gerencial" in gov_usuario or "Mapa de Campo" in gov_usuario
tem_dados = "Upload de Dados" in gov_usuario
tem_governanca = "Gestão de Usuários" in gov_usuario or "Governança" in gov_usuario

if tem_painel and tem_dados:
    col_nav1, col_nav2 = st.sidebar.columns(2)
    with col_nav1:
        if st.button("📊 Painel", use_container_width=True): st.session_state["tela_atual"] = "dashboard"; st.rerun()
    with col_nav2:
        if st.button("⚙️ Dados", use_container_width=True): st.session_state["tela_atual"] = "admin"; st.rerun()
elif tem_painel:
    if st.sidebar.button("📊 Painel", use_container_width=True): st.session_state["tela_atual"] = "dashboard"; st.rerun()
elif tem_dados:
    if st.sidebar.button("⚙️ Dados", use_container_width=True): st.session_state["tela_atual"] = "admin"; st.rerun()

if tem_governanca:
    if st.sidebar.button("🛡️ Governança (Auditoria)", use_container_width=True): st.session_state["tela_atual"] = "governanca"; st.rerun()

if st.session_state.get("tela_atual") == "admin":
    render_tela_admin()
    st.stop()

# --- BLINDAGEM DO PERFIL TÉCNICO ---
is_tecnico = st.session_state.get("perfil") == "Técnico"

# Só exibe o menu de visão gerencial se tiver a governança E NÃO for Técnico
if "Painel Gerencial" in gov_usuario and not is_tecnico:
    visao_selecionada = st.sidebar.radio(
        "Selecione a Visão:", 
        ["Gerência", "Paranapiacaba", "Piaçaguera"], 
        label_visibility="collapsed", 
        key="radio_visao_gerencial"
    )
    filtro_visao = "Todas" if visao_selecionada == "Gerência" else visao_selecionada
else:
    filtro_visao = st.session_state.get("escopo", "Todas")
    if not is_tecnico:
        st.sidebar.info(f"Visão Restrita: {filtro_visao}")
#endregion 7.1

#region 7.2: Carregamento da Base Operacional
usar_sim = st.session_state.get("chk_sim", False)
qtd_sim = st.session_state.get("qtd_sim", 1200)
seed_sim = st.session_state.get("seed_sim", 42)

def _hash_baixas():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MAX(os) FROM baixas")
        row = cur.fetchone()
        cur.close()
        return f"{row[0]}_{row[1]}"
    finally: release_connection(conn)

baixas_mtime = _hash_baixas()
df_base_bruto = carregar_base_sem_overlay(usar_sim=usar_sim, qtd_sim=int(qtd_sim), seed_sim=int(seed_sim), escopo_usuario=st.session_state["escopo"], etl_version=ETL_VERSION)
df_base = aplicar_overlay_baixas(df_base_bruto=df_base_bruto, escopo_usuario=st.session_state["escopo"], baixas_mtime=baixas_mtime)

st.session_state["df_os"] = df_base
df_visao = preparar_df_visao(df_base, filtro_visao)

if df_visao.empty or "dt_prog_filtro" not in df_visao.columns:
    st.info("📋 Nenhuma OS encontrada. Faça o upload das planilhas em **⚙️ Dados** para começar.")
    st.stop()
#endregion 7.2

#region 7.3: Filtros da Sidebar
valid_dates = df_visao["dt_prog_filtro"].dropna()
if not valid_dates.empty: min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
else: min_date, max_date = datetime.now().date() - pd.Timedelta(days=30), datetime.now().date()

lista_patios = sorted(df_visao["Patio"].dropna().astype(str).unique().tolist())
lista_classificacoes = ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
lista_turnos = ["Turno Dia (07h-19h)", "Administrativo (08h-17h30)", "Turno Noite (19h-07h)", "Pendente (Sem Turno)"]
status_opcoes = ["Todos", "Todas Concluídas", "Concluídas no Prazo", "Concluídas com Atraso", "Pendentes", "Atrasado"]

def _sanear_lista_filtro(chave: str, opcoes: list[str], padrao: list[str]):
    # Pega o que o usuário selecionou no st.multiselect
    atuais = st.session_state.get(chave, list(padrao))
    
    # Validação: mantém apenas itens que realmente existem nas opções disponíveis
    atuais = [item for item in atuais if item in opcoes]
    
    # A MUDANÇA: Se a lista ficar vazia, não vamos forçar o retorno ao padrão.
    # Vamos deixar retornar vazia, o que para o seu sistema significa "sem filtros aplicados".
    st.session_state[chave] = atuais
    return atuais

#region 7.3: Função de Renderização dos Filtros na Sidebar
@st.fragment
def fragmento_filtros_sidebar_seguro():
    # --- OCULTA TUDO PARA O TÉCNICO (Inclusive o título e o botão) ---
    if st.session_state.get("perfil") == "Técnico":
        return # Interrompe a função aqui, não desenha nada na sidebar!

    st.markdown("### 📊 Filtros")
    
    with st.form("form_filtros"):
        # Datas
        start_padrao = st.session_state.get("filtro_start_date", min_date)
        end_padrao = st.session_state.get("filtro_end_date", max_date)
        data_selecionada = st.date_input("Período de Programação", value=(start_padrao, end_padrao), format="DD/MM/YYYY")
        
        # Pátios, Classificação, Turno
        patios_default = _sanear_lista_filtro("filtro_patios", lista_patios, lista_patios)
        st.multiselect("Pátio", lista_patios, default=patios_default, key="filtro_patios")
        
        classif_default = _sanear_lista_filtro("filtro_classificacoes", lista_classificacoes, lista_classificacoes)
        st.multiselect("Classificação", lista_classificacoes, default=classif_default, key="filtro_classificacoes")
        
        turnos_default = _sanear_lista_filtro("filtro_turnos", lista_turnos, lista_turnos)
        st.multiselect("Turno", lista_turnos, default=turnos_default, key="filtro_turnos")

        # Intervalo e Status
        st.selectbox("Tipo de Intervalo", ["Todas", "Com Intervalo", "Sem Intervalo"], key="filtro_intervalo_sel")
        st.selectbox("Status da OS", status_opcoes, key="filtro_status_sel")
    
        # O botão fica DENTRO do form e SÓ para quem não é técnico
        submit_filtros = st.form_submit_button("✅ Aplicar Filtros", use_container_width=True, type="primary")

    if submit_filtros:
        if isinstance(data_selecionada, tuple) and len(data_selecionada) == 2:
            st.session_state["filtro_start_date"], st.session_state["filtro_end_date"] = data_selecionada
        st.rerun()
#endregion 7.3

with st.sidebar: fragmento_filtros_sidebar_seguro()

start_date = st.session_state.get("filtro_start_date", min_date)
end_date = st.session_state.get("filtro_end_date", max_date)
patios_selecionados = st.session_state.get("filtro_patios", list(lista_patios))
classif_selecionadas = st.session_state.get("filtro_classificacoes", list(lista_classificacoes))
turnos_selecionados = st.session_state.get("filtro_turnos", list(lista_turnos))
status_sel = st.session_state.get("filtro_status_sel", "Todos")
intervalo_sel = st.session_state.get("filtro_intervalo_sel", "Todas")

df_filtrado = aplicar_filtros_sidebar(
    df_visao=df_visao, patios_selecionados=patios_selecionados,
    classif_selecionadas=classif_selecionadas, turnos_selecionados=turnos_selecionados,
    start_date=start_date, end_date=end_date, status_sel=status_sel, intervalo_sel=intervalo_sel
)
#endregion 7.3
#endregion SESSÃO 7

#region SESSÃO 8: Sistema, Dados e Gestão de Usuários

#region 8.1: Controles de Simulação e Recarga ETL
if "Gestão de Usuários" in st.session_state.get("governanca", ""):
    with st.sidebar.expander("⚙️ Sistema, Dados e Gestão", expanded=False):
        st.checkbox("🧪 Usar dados simulados (teste rápido)", key="chk_sim")
        if st.session_state.get("chk_sim"):
            st.slider("Volume de OS simuladas", 100, 4000, 1200, 100, key="qtd_sim")
            st.number_input("Seed (repete mesmos dados)", value=42, key="seed_sim")
            st.markdown("<small style='color: #CBD5E1;'>Distribuição da Simulação</small>", unsafe_allow_html=True)
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1: st.number_input("% Pendente", min_value=0, max_value=100, value=45, key="sim_pct_pendente")
            with col_s2: st.number_input("% No Prazo", min_value=0, max_value=100, value=40, key="sim_pct_prazo")
            with col_s3: st.number_input("% Atrasado", min_value=0, max_value=100, value=15, key="sim_pct_atraso")
        else:
            if st.button("🔄 Recarregar dados (ETL)", use_container_width=True): st.cache_data.clear(); st.rerun()
#endregion 8.1

#region 8.2: Gestão de Usuários (@st.fragment)
        @st.fragment
        def fragmento_gestao_usuarios():
            st.markdown("<div style='background-color: #FF4B4B; color: #FFFFFF; font-weight: bold; text-align: center; padding: 8px; border-radius: 6px; margin-top: 15px; margin-bottom: 10px;'>Gestão de Usuários</div>", unsafe_allow_html=True)
            if "msg_sucesso_user" in st.session_state: st.success(st.session_state["msg_sucesso_user"]); del st.session_state["msg_sucesso_user"]

            def sedes_por_escopo(escopo: str):
                if escopo == "Paranapiacaba": return ["Sede IPA"]
                elif escopo == "Piaçaguera": return ["Sede IPG"]
                return ["Sede IPA", "Sede IPG"]

            opcoes_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Gestão de Usuários", "Exportar SAP", "Governança"]

            #region 8.2.1: Criar Novo Usuário (Formulário)
            with st.form("form_novo_user", clear_on_submit=True):
                n_user = st.text_input("Matrícula / Username", key="novo_user_login")
                n_nome = st.text_input("Nome do Colaborador", key="novo_user_nome")
                n_perf = st.selectbox("Perfil", ["Técnico", "Assistente", "Coordenador", "Gerência"], key="novo_user_perfil")
                n_esco = st.selectbox("Escopo (Base)", ["Paranapiacaba", "Piaçaguera", "Todas"], key="novo_user_escopo")
                sedes_validas = sedes_por_escopo(n_esco)
                n_sede = st.selectbox("Sede Física", sedes_validas, key="novo_user_sede", format_func=lambda x: x.replace("Sede ", ""))
                st.markdown("---")
                st.markdown("**Governança (O que o usuário pode ver/fazer?)**")

                if n_perf == "Técnico": def_gov = ["Mapa de Campo"]
                elif n_perf == "Assistente": def_gov = ["Painel Gerencial", "Upload de Dados", "Exportar SAP"]
                elif n_perf == "Coordenador": def_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Exportar SAP", "Governança"]
                else: def_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Gestão de Usuários", "Exportar SAP", "Governança"]

                n_gov = st.multiselect("Permissões de Acesso:", opcoes_gov, default=def_gov, key="novo_user_gov")

                if st.form_submit_button("Salvar Novo Usuário"):
                    if n_user and n_nome:
                        conn = get_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute("""
                                INSERT INTO usuarios (username, nome, senha_hash, perfil, escopo, palavra_recuperacao, dica_recuperacao, coordenacao_padrao, reset_obrigatorio, governanca)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (n_user.strip(), n_nome.strip(), hash_senha("mrs123"), n_perf, n_esco, "PENDENTE", "PENDENTE", n_sede, 1, ",".join(n_gov)))
                            conn.commit()
                            st.session_state["msg_sucesso_user"] = f"Usuário '{n_nome}' ({n_user}) criado com sucesso!"
                            st.rerun(scope="fragment")
                        except psycopg2.IntegrityError: conn.rollback(); st.error("Erro: Esta matrícula/usuário já existe.")
                        finally: cur.close(); release_connection(conn)
                    else: st.warning("Preencha a matrícula e o nome do colaborador.")
            #endregion 8.2.1

            #region 8.2.2: Gerenciar Existentes
            st.markdown("**👥 Gerenciar Usuários**", unsafe_allow_html=True)
            conn = get_connection()
            df_usuarios = pd.read_sql_query("SELECT username, nome, perfil, escopo, coordenacao_padrao, governanca FROM usuarios", conn)
            release_connection(conn)

            if not df_usuarios.empty:
                df_usuarios["label_exibicao"] = df_usuarios.apply(lambda r: f"{str(r['nome']).strip()} ({str(r['username']).strip()})" if pd.notna(r["nome"]) and str(r["nome"]).strip() else str(r["username"]).strip(), axis=1)
                mapa_label_para_user = dict(zip(df_usuarios["label_exibicao"], df_usuarios["username"]))
                usr_label_sel = st.selectbox("Selecione um usuário:", [""] + df_usuarios["label_exibicao"].tolist(), key="sel_usr_frag")

                if usr_label_sel != "":
                    usr_sel = mapa_label_para_user[usr_label_sel]
                    dados_usr = df_usuarios[df_usuarios["username"] == usr_sel].iloc[0]
                    gov_atual_lista = str(dados_usr["governanca"]).split(",") if pd.notna(dados_usr["governanca"]) else []

                    st.caption(f"**Nome:** {dados_usr['nome']} | **Matrícula:** {dados_usr['username']} | **Perfil:** {dados_usr['perfil']} | **Visão:** {dados_usr['escopo']} | **Sede:** {str(dados_usr['coordenacao_padrao']).replace('Sede ', '')}")
                    acao = st.radio("Ação:", ["✏️ Editar Acesso", "🔑 Resetar Senha", "🗑️ Excluir"], horizontal=True, key="radio_acao_frag")

                    if acao == "✏️ Editar Acesso":
                        with st.form(f"form_edit_{usr_sel}"):
                            n_nome_edit = st.text_input("Nome do Colaborador", value=str(dados_usr["nome"]).strip() if pd.notna(dados_usr["nome"]) else "")
                            n_perf_edit = st.selectbox("Novo Perfil", ["Técnico", "Assistente", "Coordenador", "Gerência"], index=["Técnico", "Assistente", "Coordenador", "Gerência"].index(dados_usr["perfil"]))
                            n_esco_edit = st.selectbox("Nova Visão", ["Paranapiacaba", "Piaçaguera", "Todas"], index=["Paranapiacaba", "Piaçaguera", "Todas"].index(dados_usr["escopo"]))
                            n_sede_edit = st.selectbox("Sede", sedes_por_escopo(n_esco_edit), format_func=lambda x: x.replace("Sede ", ""))
                            gov_editadas = st.multiselect("Governança:", opcoes_gov, default=[g for g in gov_atual_lista if g in opcoes_gov])

                            if st.form_submit_button("Salvar Alterações"):
                                conn = get_connection(); cur = conn.cursor()
                                cur.execute("UPDATE usuarios SET nome=%s, perfil=%s, escopo=%s, coordenacao_padrao=%s, governanca=%s WHERE username=%s", (n_nome_edit.strip(), n_perf_edit, n_esco_edit, n_sede_edit, ",".join(gov_editadas), usr_sel))
                                conn.commit(); cur.close(); release_connection(conn)
                                st.session_state["msg_sucesso_user"] = f"Cadastro de {n_nome_edit} ({usr_sel}) atualizado!"
                                st.rerun(scope="fragment")
                    elif acao == "🔑 Resetar Senha":
                        if st.button("Confirmar Reset", key="btn_reset_frag"):
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute("UPDATE usuarios SET senha_hash = %s, reset_obrigatorio = 1 WHERE username = %s", (hash_senha("mrs123"), usr_sel))
                            conn.commit(); cur.close(); release_connection(conn)
                            st.session_state["msg_sucesso_user"] = f"Senha de {dados_usr['nome']} ({usr_sel}) resetada!"
                            st.rerun(scope="fragment")
                    elif acao == "🗑️ Excluir":
                        if st.button("Confirmar Exclusão", type="primary", key="btn_excluir_frag"):
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute("DELETE FROM usuarios WHERE username = %s", (usr_sel,))
                            conn.commit(); cur.close(); release_connection(conn)
                            st.session_state["msg_sucesso_user"] = f"Usuário {dados_usr['nome']} ({usr_sel}) excluído."
                            st.rerun(scope="fragment")
            else: st.info("Nenhum usuário cadastrado.")
            #endregion 8.2.2

            #region 8.2.3: Importação em Massa de Colaboradores (RESTAURADA)
            st.markdown("---")
            st.markdown("**📥 Importação em Massa de Colaboradores**")
            st.caption("A planilha deve conter exatamente as colunas: `username`, `Nome`, `perfil`, `escopo`, `coordenacao_padrao`, `governanca`.")

            arquivo_users = st.file_uploader("Selecione a planilha de colaboradores (.xlsx ou .csv)", type=["xlsx", "csv"], key="upload_users_massa")

            if arquivo_users is not None:
                if st.button("🚀 Processar Cadastro em Massa", use_container_width=True, type="primary", key="btn_users_massa"):
                    with st.spinner("Processando colaboradores..."):
                        try:
                            if arquivo_users.name.lower().endswith(".csv"): df_users = pd.read_csv(arquivo_users, sep=None, engine="python", encoding="utf-8-sig")
                            else: df_users = pd.read_excel(arquivo_users)

                            df_users.columns = [str(c).strip() for c in df_users.columns]
                            colunas_obrigatorias = ["username", "Nome", "perfil", "escopo", "coordenacao_padrao", "governanca"]
                            faltantes = [c for c in colunas_obrigatorias if c not in df_users.columns]

                            if faltantes: st.error(f"❌ Colunas obrigatórias ausentes: {', '.join(faltantes)}")
                            else:
                                df_users = df_users.fillna("")
                                perfis_validos = {"Técnico", "Assistente", "Coordenador", "Gerência"}
                                escopos_validos = {"Paranapiacaba", "Piaçaguera", "Todas"}
                                registros, erros = [], []

                                for idx, row in df_users.iterrows():
                                    matricula = str(row["username"]).strip()
                                    nome = str(row["Nome"]).strip()
                                    perfil = str(row["perfil"]).strip()
                                    escopo = str(row["escopo"]).strip()
                                    coordenacao_padrao = str(row["coordenacao_padrao"]).strip()
                                    governanca = str(row["governanca"]).strip()

                                    if not matricula: erros.append(f"Linha {idx + 2}: username/matrícula vazio."); continue
                                    if not nome: erros.append(f"Linha {idx + 2}: Nome vazio."); continue
                                    if perfil not in perfis_validos: erros.append(f"Linha {idx + 2}: perfil inválido ({perfil})."); continue
                                    if escopo not in escopos_validos: erros.append(f"Linha {idx + 2}: escopo inválido ({escopo})."); continue
                                    if not coordenacao_padrao: erros.append(f"Linha {idx + 2}: coordenacao_padrao vazio."); continue

                                    registros.append((matricula, nome, hash_senha("mrs123"), perfil, escopo, "PENDENTE", "PENDENTE", coordenacao_padrao, 1, governanca))

                                if erros:
                                    st.error("❌ Foram encontrados erros na planilha:")
                                    for e in erros[:20]: st.write(f"- {e}")
                                    if len(erros) > 20: st.write(f"... e mais {len(erros) - 20} erro(s).")
                                elif not registros: st.warning("⚠️ Nenhum registro válido encontrado.")
                                else:
                                    conn = get_connection()
                                    try:
                                        cur = conn.cursor()
                                        execute_values(cur, """
                                            INSERT INTO usuarios (username, nome, senha_hash, perfil, escopo, palavra_recuperacao, dica_recuperacao, coordenacao_padrao, reset_obrigatorio, governanca)
                                            VALUES %s
                                            ON CONFLICT (username) DO UPDATE SET
                                                nome = EXCLUDED.nome, perfil = EXCLUDED.perfil, escopo = EXCLUDED.escopo, coordenacao_padrao = EXCLUDED.coordenacao_padrao, governanca = EXCLUDED.governanca
                                            """, registros, page_size=500)
                                        conn.commit(); cur.close()
                                    finally: release_connection(conn)

                                    st.session_state["msg_sucesso_user"] = f"✅ Importação concluída! {len(registros)} colaborador(es) processado(s)."
                                    st.rerun(scope="fragment")
                        except Exception as e: st.error(f"❌ Erro ao processar a planilha: {e}")
            #endregion 8.2.3

        fragmento_gestao_usuarios()
#endregion 8.2
#endregion SESSÃO 8

#region SESSÃO 9: Dashboard Header e KPI Metrics

#region 9.1: Header do Dashboard (Título + Saudação)
col_titulo, col_acoes = st.columns([9, 1])

with col_titulo:
    st.title("⚡ Sistema de Gestão de Ordens de Serviço")
    st.markdown(f"<h5 style='color: #475569; margin-top: -10px;'>Olá, <b>{st.session_state.get('username', 'Usuário')}</b> 👋</h5>", unsafe_allow_html=True)

with col_acoes:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
#endregion 9.1

#region 9.2: Botões de Ação (Atualizar / Trocar Senha / Sair)
    if st.button("🔄 Atualizar", use_container_width=True): st.rerun()
        
    if st.button("🔑 Trocar", use_container_width=True):
        usr_atual = st.session_state["username"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET reset_obrigatorio = 1 WHERE username = %s", (usr_atual,))
        conn.commit(); cur.close(); release_connection(conn)
        
        st.session_state.clear()
        st.session_state.update({"logged_in": False, "needs_reset": True, "reset_user": usr_atual})
        st.rerun()
        
    if st.button("🚪 Sair", use_container_width=True):
        keys_manter = {"gps_pending", "gps_trials", "origem_tipo"}
        for key in list(st.session_state.keys()):
            if key not in keys_manter: del st.session_state[key]
        st.session_state["logged_in"] = False
        st.rerun()

st.markdown("---")
#endregion 9.2

#region 9.3: Cálculo dos KPIs + CSS dos Cards (Dark Mode)
total_os = len(df_filtrado)
realizado_prazo = len(df_filtrado[df_filtrado["Status_norm"].isin(_status_prazo)])
realizado_atraso = len(df_filtrado[df_filtrado["Status_norm"].isin(_status_atraso)])
realizado_total = realizado_prazo + realizado_atraso
nao_realizado = len(df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto)])
taxa_conclusao = (realizado_total / total_os * 100) if total_os > 0 else 0.0

st.markdown("""
    <style>
    iframe, .stEcharts, [data-testid="stHtmlBlock"] + div iframe { border-radius: 12px !important; overflow: hidden !important; }
    .kpi-header-wrapper { font-family: "Source Sans Pro", sans-serif; }
    .kpi-header-card {
        font-family: "Source Sans Pro", sans-serif; border-radius: 12px; padding: 16px 20px;
        background-color: #1A202C; border: 1px solid #333D4E;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); height: 140px; display: flex;
        flex-direction: column; justify-content: center; box-sizing: border-box; margin-bottom: 15px;
    }
    .kpi-border-gray { border-left: 4px solid #64748B; }
    .kpi-border-red { border-left: 4px solid #EF4444; }
    .kpi-border-green { border-left: 4px solid #10B981; }
    .kpi-border-blue { border-left: 4px solid #3B82F6; }
    
    .kpi-header-title { font-size: 14px; font-weight: 700; color: #94A3B8; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-header-val { font-size: 32px; font-weight: 600; color: #F8FAFC; line-height: 1; }
    .kpi-header-sub { font-size: 12px; font-weight: 600; margin-top: 8px; padding: 4px 10px; border-radius: 20px; display: inline-block; width: fit-content; }
    
    .badge-gray { background-color: rgba(100, 116, 139, 0.2); color: #CBD5E1; }
    .badge-red { background-color: rgba(239, 68, 68, 0.2); color: #FCA5A5; }
    .badge-green { background-color: rgba(16, 185, 129, 0.2); color: #6EE7B7; }
    .badge-blue { background-color: rgba(59, 130, 246, 0.2); color: #93C5FD; }
    </style>
""", unsafe_allow_html=True)
#endregion 9.3

#region 9.4: Renderização dos Cards KPI
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.markdown(f"""
        <div class="kpi-header-wrapper kpi-header-card kpi-border-gray">
            <div class="kpi-header-title">📋 Planejado (OS)</div>
            <div class="kpi-header-val">{total_os}</div>
            <div class="kpi-header-sub badge-gray">Total de O.S do período</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi2:
    st.markdown(f"""
        <div class="kpi-header-wrapper kpi-header-card kpi-border-red">
            <div class="kpi-header-title">🔴 Backlog (Não Realizado)</div>
            <div class="kpi-header-val">{nao_realizado}</div>
            <div class="kpi-header-sub badge-red">↑ {nao_realizado} pendentes</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi3:
    st.markdown(f"""
        <div class="kpi-header-wrapper kpi-header-card kpi-border-green">
            <div class="kpi-header-title">🟢 Realizado (Total)</div>
            <div class="kpi-header-val">{realizado_total}</div>
            <div class="kpi-header-sub badge-green">↑ {realizado_prazo} no prazo / {realizado_atraso} atrasado</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi4:
    st.markdown(f"""
        <div class="kpi-header-wrapper kpi-header-card kpi-border-blue">
            <div class="kpi-header-title">📈 Taxa de Conclusão</div>
            <div class="kpi-header-val">{taxa_conclusao:.1f}%</div>
            <div class="kpi-header-sub badge-blue">Aproveitamento geral</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")
#endregion 9.4
#endregion SESSÃO 9

#region SESSÃO 10: Abas e Renderização dos Gráficos

#region 10.1: Roteamento Principal (Controle de Telas)
if st.session_state.get("tela_atual", "dashboard") == "dashboard":
    tem_mapa_campo = "Mapa de Campo" in st.session_state.get("governanca", "")
    tem_painel_gerencial = "Painel Gerencial" in st.session_state.get("governanca", "")

    if tem_painel_gerencial and tem_mapa_campo: tab1, tab2 = st.tabs(["📊 Visão Gerencial", "🗺️ Roteirização e Mapa de Campo"])
    elif tem_mapa_campo: tab1, tab2 = None, st.tabs(["🗺️ Roteirização e Mapa de Campo"])[0]
    elif tem_painel_gerencial: tab1, tab2 = st.tabs(["📊 Visão Gerencial"])[0], None
    else: tab1, tab2 = st.tabs(["📊 Visão Gerencial"])[0], None
#endregion

#region 10.2: ABA 1 — Visão Gerencial (Indicadores)
    if tab1 is not None:
        with tab1:
            if st.session_state["perfil"] == "Técnico": st.info("🔒 Seu perfil tem foco operacional. Utilize a aba 'Roteirização e Mapa de Campo'.")
            else:
                df_visao_base = df_filtrado.copy()
                cor_plan, cor_real, cor_prazo, cor_atraso, cor_pendente = "#64748B", "#3B82F6", "#10B981", "#F59E0B", "#FF4B4B"

                if taxa_conclusao <= 25: gauge_color = cor_pendente
                elif taxa_conclusao <= 50: gauge_color = cor_atraso
                elif taxa_conclusao <= 80: gauge_color = cor_prazo
                else: gauge_color = cor_real

#region 10.2.1: Resumo Executivo (Gauge + Rosca + Área)
                with st.expander("Resumo Executivo (Geral)", expanded=True):
                    col_g1, col_g2, col_g5 = st.columns(3)
                    with col_g1:
                        st.markdown("#### Realizado x Planejado")
                        st_echarts(options={
                            "tooltip": {"formatter": "{a} <br/>{b}: {c}%"},
                            "series": [{
                                "name": "Conclusão", "type": "gauge", "min": 0, "max": 100, "radius": "75%",
                                "progress": {"show": True, "width": 14, "itemStyle": {"color": gauge_color}},
                                "axisLine": {"lineStyle": {"width": 14, "color": [[0.25, cor_pendente], [0.50, cor_atraso], [0.80, cor_prazo], [1.00, cor_real]]}},
                                "pointer": {"show": True, "length": "60%", "width": 6}, "itemStyle": {"color": gauge_color},
                                "title": {"show": True, "offsetCenter": [0, "70%"], "fontSize": 14},
                                "detail": {"valueAnimation": True, "offsetCenter": [0, "40%"], "formatter": f"{taxa_conclusao:.1f}%\n{realizado_total} / {total_os}", "fontSize": 16},
                                "data": [{"value": round(taxa_conclusao, 1), "name": "Realizado"}],
                            }],
                        }, height="350px", theme="streamlit", key="aba1_gauge")

                    with col_g2:
                        st.markdown("#### Distribuição por Status")
                        st_echarts(options={
                            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"}, "legend": {"orient": "horizontal", "bottom": "0%"},
                            "series": [{
                                "name": "Status", "type": "pie", "radius": ["45%", "75%"],
                                "data": [
                                    {"value": realizado_prazo, "name": "No Prazo", "itemStyle": {"color": cor_prazo}},
                                    {"value": realizado_atraso, "name": "Atrasado", "itemStyle": {"color": cor_atraso}},
                                    {"value": nao_realizado, "name": "Pendentes", "itemStyle": {"color": cor_pendente}},
                                ],
                                "label": {"show": True, "position": "inside", "formatter": "{c}\n({d}%)", "color": "#FFFFFF", "fontWeight": "bold"},
                            }],
                        }, height="350px", theme="streamlit", key="aba1_rosca")

                    with col_g5:
                        st.markdown("#### Plan x Real Acumulado")
                        df_area = df_visao_base.copy()
                        df_area["dia_programado"] = pd.to_datetime(df_area["Data inicial programada"], errors="coerce").dt.normalize()
                        realizado_diario_a = (df_area[df_area["Status_norm"].isin(_status_prazo | _status_atraso)].groupby("dia_realizado").size().rename("Realizado_Dia"))
                        planejado_diario_a = (df_area.groupby("dia_programado").size().rename("Planejado_Dia"))

                        _datas_a = pd.Index([]).union(realizado_diario_a.index).union(planejado_diario_a.index)
                        if len(_datas_a) > 0:
                            _idx_da = pd.date_range(start=_datas_a.min(), end=_datas_a.max(), freq="D")
                            _real_acum = realizado_diario_a.reindex(_idx_da, fill_value=0).cumsum()
                            _plan_acum = planejado_diario_a.reindex(_idx_da, fill_value=0).cumsum()
                            st_echarts(options={
                                "tooltip": {"trigger": "axis"}, "legend": {"top": "bottom"},
                                "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                                "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
                                "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
                                "xAxis": {"type": "category", "data": [d.strftime("%d/%m") for d in _idx_da]}, "yAxis": {"type": "value"},
                                "series": [
                                    {"name": "Realizado Acumulado", "type": "line", "smooth": True, "data": _real_acum.tolist(), "areaStyle": {"color": "rgba(59,130,246,0.2)"}, "lineStyle": {"color": cor_real, "width": 3}, "itemStyle": {"color": cor_real}},
                                    {"name": "Planejado Acumulado", "type": "line", "smooth": True, "data": _plan_acum.tolist(), "lineStyle": {"color": cor_plan, "width": 3, "type": "dashed"}, "itemStyle": {"color": cor_plan}},
                                ],
                            }, height="350px", theme="streamlit", key="aba1_area")
                        else: st.info("Sem datas suficientes para área.")
                #endregion 10.2.1

#region 10.2.2: Análise Operacional (Matriz de Prioridades)
                with st.expander("Análise Operacional: Matriz de Prioridades e Execução por Categoria", expanded=True):
                    col_h1, col_h2 = st.columns([1.2, 1])
                    with col_h1:
                        st.markdown("#### Matriz: Prioridade vs Classificação")
                        st.caption("Volume total de OS planejadas (Cor indica concentração)")
                        agg = df_visao_base.copy().groupby(["Classificacao", "Criticidade"]).size().reset_index(name="Total")
                        ordem_class = ["Confiabilidade", "Segurança", "Confiabilidade e Segurança"]
                        ordem_crit = ["Muito Alta", "Alta", "Média", "Baixa"]

                        if not agg.empty:
                            heat_data, max_val = [], 0
                            for _yi, _cls in enumerate(ordem_class):
                                for _xi, _crt in enumerate(ordem_crit):
                                    _row = agg[(agg["Classificacao"] == _cls) & (agg["Criticidade"] == _crt)]
                                    _val = int(_row["Total"].iloc[0]) if not _row.empty else 0
                                    heat_data.append([_xi, _yi, _val]); max_val = max(max_val, _val)

                            st_echarts(options={
                                "tooltip": {"position": "top"}, "grid": {"height": "70%", "top": "10%", "left": "25%", "containLabel": True},
                                "xAxis": {"type": "category", "data": ordem_crit, "splitArea": {"show": True}, "axisLine": {"show": False}, "axisTick": {"show": False}},
                                "yAxis": {"type": "category", "data": ordem_class, "splitArea": {"show": True}, "axisLine": {"show": False}, "axisTick": {"show": False}},
                                "visualMap": {"min": 0, "max": max_val if max_val > 0 else 10, "calculable": True, "orient": "horizontal", "left": "center", "bottom": "0%", "inRange": {"color": ["#F1F5F9", "#93C5FD", "#3B82F6", "#1E3A8A"]}},
                                "series": [{"name": "Total de OS", "type": "heatmap", "data": heat_data, "label": {"show": True, "color": "#FFFFFF", "fontWeight": "bold", "formatter": JsCode("function(p){return p.value[2] > 0 ? p.value[2] : '';}")}, "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2}}],
                            }, height="380px", theme="streamlit", key="aba1_heatmap_discrete")
                        else: st.info("Sem dados para a Matriz.")

                    with col_h2:
                        st.markdown("#### Plan x Realizado por Categoria")
                        st.caption("Comparativo de volume total e execução.")
                        df_bar_cat = df_visao_base.copy()
                        plan_cat = df_bar_cat.groupby("Classificacao").size()
                        real_cat = (df_bar_cat[df_bar_cat["Status_norm"].isin(_status_prazo | _status_atraso)].groupby("Classificacao").size())
                        cats = ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
                        val_plan, val_real = [int(plan_cat.get(c, 0)) for c in cats], [int(real_cat.get(c, 0)) for c in cats]

                        st_echarts(options={
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, "legend": {"bottom": "0%"},
                            "grid": {"left": "3%", "right": "10%", "bottom": "15%", "top": "10%", "containLabel": True},
                            "xAxis": {"type": "value", "boundaryGap": [0, 0.01]}, "yAxis": {"type": "category", "data": cats, "axisLabel": {"interval": 0}},
                            "series": [
                                {"name": "Planejado", "type": "bar", "data": val_plan, "itemStyle": {"color": cor_plan}, "label": {"show": True, "position": "right", "color": "#475569"}},
                                {"name": "Realizado", "type": "bar", "data": val_real, "itemStyle": {"color": cor_real}, "label": {"show": True, "position": "right", "color": "#475569"}}
                            ]
                        }, height="380px", theme="streamlit", key="aba1_bar_horiz")
                #endregion 10.2.2

#region 10.2.3: Execução por Turno e Acumulado
                with st.expander("Execução por Turno e Acumulado", expanded=True):
                    col_g3, col_g6 = st.columns(2)
                    _cor_turno = { "Turno Dia (07h-19h)": "#F59E0B", "Administrativo (08h-17h30)": "#3B82F6", "Turno Noite (19h-07h)": "#4F46E5" }
                    with col_g3:
                        st.markdown("#### Realizado por Turno")
                        x_turnos = ["Turno Dia (07h-19h)", "Administrativo (08h-17h30)", "Turno Noite (19h-07h)"]
                        _cnt_t = df_visao_base[df_visao_base["Status_norm"].isin(_status_prazo | _status_atraso)].groupby("Turno").size()
                        y_vals = [int(_cnt_t.get(t, 0)) for t in x_turnos]
                        st_echarts(options={
                            "tooltip": {"trigger": "axis"}, "xAxis": {"type": "category", "data": x_turnos, "axisLabel": {"interval": 0, "fontSize": 10}}, "yAxis": {"type": "value"},
                            "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                            "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "15%", "containLabel": True},
                            "series": [{"type": "bar", "barWidth": "55%", "label": {"show": True, "position": "inside", "formatter": "{c}", "color": "#FFFFFF", "fontWeight": "bold"}, "data": [{"value": v, "name": t, "itemStyle": {"color": _cor_turno.get(t, "#94A3B8")}} for t, v in zip(x_turnos, y_vals)]}],
                        }, height="350px", theme="streamlit", key="aba1_barra")

                    with col_g6:
                        st.markdown("#### Realizado Acumulado por Turno")
                        df_linhas_plot = df_visao_base.dropna(subset=["dia_realizado"]).copy()
                        if not df_linhas_plot.empty:
                            _idx_dt = pd.date_range(start=df_linhas_plot["dia_realizado"].min(), end=df_linhas_plot["dia_realizado"].max(), freq="D")
                            _series_t = [{"name": _t, "type": "line", "smooth": True, "data": (df_linhas_plot[df_linhas_plot["Turno"] == _t].groupby("dia_realizado").size().reindex(_idx_dt, fill_value=0).cumsum()).tolist(), "lineStyle": {"color": _cor_turno[_t], "width": 3}, "itemStyle": {"color": _cor_turno[_t]}} for _t in x_turnos]
                            st_echarts(options={
                                "tooltip": {"trigger": "axis"}, "legend": {"top": "bottom"},
                                "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar", "stack"], "title": {"line": "Linha", "bar": "Barra", "stack": "Empilhado"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                                "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
                                "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
                                "xAxis": {"type": "category", "data": [d.strftime("%d/%m") for d in _idx_dt]}, "yAxis": {"type": "value"}, "series": _series_t,
                            }, height="350px", theme="streamlit", key="aba1_linhas")
                        else: st.info("Sem dados cronológicos.")
                #endregion 10.2.3

#region 10.2.4: Lista Detalhada de OS (com Evidências)
                st.subheader("📋 Lista Detalhada de OS")
                
                # --- NOVIDADE: BARRA DE PESQUISA ---
                col_busca, _ = st.columns([4, 6])
                with col_busca:
                    busca_os = st.text_input("🔍 Pesquisar por N° da OS, Pátio ou Ativo:")

                df_lista = df_visao_base.copy().rename(columns={"Ordem servico": "OS"})
                try:
                    df_evidencias = carregar_evidencias_df()
                    if not df_evidencias.empty and "OS" in df_lista.columns:
                        df_lista["OS_match"] = df_lista["OS"].astype(str).str.strip()
                        df_evidencias["os_ref_match"] = df_evidencias["os_referencia"].astype(str).str.strip()
                        df_lista = df_lista.merge(df_evidencias[["os_ref_match", "foto_url"]], left_on="OS_match", right_on="os_ref_match", how="left")
                    else: 
                        df_lista["foto_url"] = None

                    def obter_link(row):
                        if "foto_url" in row and pd.notna(row["foto_url"]) and str(row["foto_url"]).startswith("http"):
                            return str(row["foto_url"])
                        return None
                    df_lista["Evidência"] = df_lista.apply(obter_link, axis=1)
                    df_lista.drop(columns=["OS_match", "os_ref_match", "foto_url", "ativo", "atividade"], inplace=True, errors="ignore")
                except Exception: 
                    df_lista["Evidência"] = None

                if "Data inicial programada" in df_lista.columns: df_lista["Data inicial programada"] = pd.to_datetime(df_lista["Data inicial programada"], errors="coerce").dt.strftime("%d/%m/%Y")
                if "Data/Hora Realizado" in df_lista.columns: df_lista["Data/Hora Realizado"] = pd.to_datetime(df_lista["Data/Hora Realizado"], dayfirst=True, errors="coerce").dt.strftime("%d/%m/%Y %H:%M").fillna("")

                colunas_ordem = ["OS", "Patio", "Ativo", "Criticidade", "Classificacao", "Descrição Longa", "Data inicial programada", "Status da Operação", "Data/Hora Realizado", "Concluído por", "Geolocalização de Baixa", "Evidência"]
                for c in colunas_ordem:
                    if c not in df_lista.columns: df_lista[c] = ""

                # --- APLICA O FILTRO DA PESQUISA ---
                if busca_os:
                    b_up = busca_os.upper()
                    mask = (df_lista["OS"].astype(str).str.upper().str.contains(b_up)) | (df_lista["Patio"].astype(str).str.upper().str.contains(b_up)) | (df_lista["Ativo"].astype(str).str.upper().str.contains(b_up))
                    df_lista = df_lista[mask]

                if not df_lista.empty:
                    # 1. Formatar a coluna de link para HTML nativo (abre em nova aba)
                    def formatar_link(url):
                        if pd.notna(url) and str(url).startswith("http"):
                            return f'<a href="{url}" target="_blank" style="color: #3B82F6; font-weight: bold; text-decoration: none;">🔗 Abrir Foto</a>'
                        return ""
                    df_lista["Evidência"] = df_lista["Evidência"].apply(formatar_link)
                    
                    # 2. Gerar HTML com Pandas Styler
                    df_html = df_lista[colunas_ordem].copy()
                    tabela_html = df_html.style.hide(axis="index").set_properties(**{'text-align': 'center'}).to_html(escape=False)
                    
                    # 3. Injetar a tabela em um Iframe Interativo com Motor JS de Ordenação
                    html_code = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                    <style>
                    body {{ margin: 0; font-family: "Source Sans Pro", sans-serif; background-color: #FFFFFF; }}
                    .tabela-dash {{ width: 100%; border-collapse: collapse; font-size: 13px; color: #0F172A; }}
                    .tabela-dash th {{ 
                        background-color: #1E293B; color: #F8FAFC; position: sticky; top: 0; z-index: 1; 
                        padding: 10px; text-align: center; border-bottom: 2px solid #3B82F6; white-space: nowrap; 
                        cursor: pointer; user-select: none; transition: background-color 0.2s;
                    }}
                    .tabela-dash th:hover {{ background-color: #333D4E; }}
                    .tabela-dash th::after {{ content: ' ↕'; font-size: 11px; color: #94A3B8; padding-left: 5px; }}
                    .tabela-dash td {{ padding: 8px 10px; border-bottom: 1px solid #E2E8F0; text-align: center; vertical-align: middle; white-space: nowrap; }}
                    .tabela-dash td:nth-child(6) {{ text-align: left; min-width: 500px; white-space: pre-wrap; word-wrap: break-word; }}
                    .tabela-dash td:nth-child(11) {{ text-align: left; min-width: 300px; white-space: pre-wrap; word-wrap: break-word; }}
                    </style>
                    </head>
                    <body>
                    {tabela_html.replace('<table', '<table class="tabela-dash"')}
                    
                    <script>
                    // Motor de Ordenação JavaScript Vanilla
                    const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;
                    const comparer = (idx, asc) => (a, b) => ((v1, v2) => 
                        v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2)
                        )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));
                    document.querySelectorAll('th').forEach(th => th.addEventListener('click', function() {{
                        const table = th.closest('table');
                        const tbody = table.querySelector('tbody');
                        Array.from(tbody.querySelectorAll('tr'))
                            .sort(comparer(Array.from(th.parentNode.children).indexOf(th), this.asc = !this.asc))
                            .forEach(tr => tbody.appendChild(tr));
                    }}));
                    </script>
                    </body>
                    </html>
                    """
                    import streamlit.components.v1 as components
                    components.html(html_code, height=450, scrolling=True)
                else:
                    st.info("Nenhuma OS encontrada para a pesquisa.")
#endregion 10.2.4
#endregion 10.2

#region 10.3: ABA 2 — Roteirização e Mapa de Campo
    if tab2 is not None:
        with tab2:
            df_recomendado = pd.DataFrame()
            
#region 10.3.1: CSS + Calendário Mensal + Cards + Turno
            st.markdown("### 📅 Agenda Mensal de Demanda por Pátio")
            st.markdown("""
                <style>
                .kpi-wrapper { font-family: "Source Sans Pro", sans-serif; }
                .kpi-card-blue, .kpi-card-green, .kpi-card-red {
                    background-color: #1A202C; border: 1px solid #333D4E; border-radius: 12px; padding: 16px 20px; 
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); height: 140px; margin-bottom: 16px; 
                    display: flex; flex-direction: column; justify-content: center; box-sizing: border-box;
                }
                .kpi-card-blue { border-left: 4px solid #3B82F6; }
                .kpi-card-green { border-left: 4px solid #10B981; }
                .kpi-card-red { border-left: 4px solid #EF4444; }
                
                .kpi-title-blue, .kpi-title-green, .kpi-title-red { color: #94A3B8; font-size: 14px; font-weight: 700; margin-bottom: 6px; text-transform: uppercase; }
                .kpi-val-blue, .kpi-val-green { color: #F8FAFC; font-size: 32px; font-weight: 600; line-height: 1; }
                .kpi-val-red { color: #F8FAFC; font-size: 24px; font-weight: 600; line-height: 1.2; margin-top: 4px; } 
                .kpi-sub-blue, .kpi-sub-green, .kpi-sub-red { color: #CBD5E1; font-size: 12px; font-weight: 600; margin-top: 8px;}
                </style>
            """, unsafe_allow_html=True)

            hoje_ref = datetime.now()
            if "cal_ref_mes" not in st.session_state: st.session_state["cal_ref_mes"] = int(hoje_ref.month)
            if "cal_ref_ano" not in st.session_state: st.session_state["cal_ref_ano"] = int(hoje_ref.year)
            col_cal_ctrl_1, col_cal_ctrl_2, _ = st.columns([1, 1, 4])
            is_tecnico = st.session_state.get("perfil") == "Técnico"

            if is_tecnico:
                st.session_state["cal_ref_mes"], st.session_state["cal_ref_ano"] = int(hoje_ref.month), int(hoje_ref.year)
                with col_cal_ctrl_1: st.info(f"Mês: {hoje_ref.strftime('%m')}")
                with col_cal_ctrl_2: st.info(f"Ano: {hoje_ref.year}")
                st.caption(f"📌 **Visão Operacional:** Calendário fixado ({hoje_ref.strftime('%m/%Y')})")
            else:
                with col_cal_ctrl_1: mes_opcao = st.selectbox("Mês", list(range(1, 13)), index=int(st.session_state["cal_ref_mes"]) - 1, format_func=lambda x: f"{x:02d}", key="cal_mes_ref_select")
                with col_cal_ctrl_2: ano_opcao = st.number_input("Ano", min_value=hoje_ref.year - 2, max_value=hoje_ref.year + 2, value=int(st.session_state["cal_ref_ano"]), step=1, key="cal_ano_ref_input")
                st.session_state["cal_ref_mes"], st.session_state["cal_ref_ano"] = int(mes_opcao), int(ano_opcao)

            df_calendario = df_visao.copy()
            if "patios_selecionados" in locals() and "classif_selecionadas" in locals(): df_calendario = df_calendario[(df_calendario["Patio"].isin(patios_selecionados)) & (df_calendario["Classificacao"].isin(classif_selecionadas))].copy()

            hoje_real = datetime.now().date()
            if (int(st.session_state["cal_ref_ano"]) == hoje_real.year and int(st.session_state["cal_ref_mes"]) == hoje_real.month): dia_ref_default = hoje_real
            else: dia_ref_default = datetime(int(st.session_state["cal_ref_ano"]), int(st.session_state["cal_ref_mes"]), 1).date()

            user_limpo = str(st.session_state.get('username', 'usr')).replace(" ", "_").lower()
            cal_key = f"cal_fixo_tecnico_{user_limpo}" if is_tecnico else f"cal_dinamico_{user_limpo}"
            cal_state = st.session_state.get(cal_key)
            data_ref_card = dia_ref_default
            
            if cal_state and isinstance(cal_state, dict):
                if cal_state.get("callback") == "dateClick": data_ref_card = pd.to_datetime(cal_state["dateClick"]["date"]).date()
                elif cal_state.get("callback") == "eventClick": data_ref_card = pd.to_datetime(cal_state["eventClick"]["event"]["start"]).date()
            if data_ref_card.year != int(st.session_state["cal_ref_ano"]) or data_ref_card.month != int(st.session_state["cal_ref_mes"]): data_ref_card = dia_ref_default

            st.markdown("#### 🔧 Tipo de OS")
            if "filtro_intervalo_campo" not in st.session_state: st.session_state["filtro_intervalo_campo"] = "Todas"
            col_int1, col_int2, col_int3 = st.columns(3)
            with col_int1:
                if st.button("📋 Todas", use_container_width=True, type="primary" if st.session_state["filtro_intervalo_campo"] == "Todas" else "secondary"): st.session_state["filtro_intervalo_campo"] = "Todas"; st.rerun()
            with col_int2:
                if st.button("🔒 Com Intervalo", use_container_width=True, type="primary" if st.session_state["filtro_intervalo_campo"] == "Com Intervalo" else "secondary"): st.session_state["filtro_intervalo_campo"] = "Com Intervalo"; st.rerun()
            with col_int3:
                if st.button("🔓 Sem Intervalo", use_container_width=True, type="primary" if st.session_state["filtro_intervalo_campo"] == "Sem Intervalo" else "secondary"): st.session_state["filtro_intervalo_campo"] = "Sem Intervalo"; st.rerun()
            st.markdown("---")

            _filtro_int_campo = st.session_state.get("filtro_intervalo_campo", "Todas")
            base_rota = df_filtrado.copy() if "df_filtrado" in locals() else df_visao.copy()

            if _filtro_int_campo != "Todas" and "Tipo_Intervalo" in base_rota.columns:
                base_rota = base_rota[base_rota["Tipo_Intervalo"] == _filtro_int_campo].copy()

            df_calendario = base_rota.copy()
            if "df_filtrado" in locals():
                df_filtrado = base_rota.copy()

            mostrar_calendario = st.toggle("📅 Mostrar Agenda Mensal de Demanda", value=False)
            
            if mostrar_calendario:
                if not df_calendario.empty:
                    with st.spinner("Carregando agenda..."):
                        calendar_events = montar_eventos_calendario_patios(df_base_cal=df_calendario, ano=int(st.session_state["cal_ref_ano"]), mes=int(st.session_state["cal_ref_mes"]), max_patios_visiveis=2)
                        calendar_options = { "initialView": "dayGridMonth", "initialDate": f"{int(st.session_state['cal_ref_ano']):04d}-{int(st.session_state['cal_ref_mes']):02d}-01", "locale": "pt-br", "height": "auto", "contentHeight": "auto", "headerToolbar": { "left": "", "center": "title", "right": "" }, "dayMaxEvents": 2, "eventOrder": "displayOrder,title", "fixedWeekCount": False, "showNonCurrentDates": True, "expandRows": True, "handleWindowResize": True }
                        calendar_css_base = """ .fc { font-size: 14px; background: #FFFFFF; border-radius: 12px; padding: 6px; box-shadow: 0 1px 8px rgba(15, 23, 42, 0.08); } .fc .fc-toolbar-title { font-size: 1.4rem !important; font-weight: 800; text-transform: capitalize; color: #1E293B; } .fc .fc-daygrid-day-frame:hover { background-color: #F8FAFC !important; } .fc .fc-daygrid-event { border-radius: 6px; padding: 3px 5px; font-weight: 800; cursor: pointer; } """
                        calendar_css_dinamico = f"{calendar_css_base} .fc-daygrid-day[data-date='{data_ref_card.strftime('%Y-%m-%d')}'] {{ background-color: #EFF6FF !important; box-shadow: inset 0 0 0 3px #3B82F6 !important; }}"

                        col_calendario, col_cards, col_turno = st.columns([5.8, 2.0, 2.2], gap="large")
                        with col_calendario: calendar(events=calendar_events, options=calendar_options, custom_css=calendar_css_dinamico, callbacks=["dateClick", "eventClick"], key=f"cal_dinamico_{cal_key}_{st.session_state.get('cal_ref_mes')}")

                        resumo_card = resumir_demanda_calendario(df_base_cal=df_calendario, ano=data_ref_card.year, mes=data_ref_card.month, dia_ref=data_ref_card.day)
                        resumo_turno = resumir_conclusoes_por_turno_data(df_base_cal=df_calendario, data_ref=data_ref_card)

                        with col_cards:
                            st.markdown(f"<div class='kpi-wrapper kpi-card-blue'><div class='kpi-title-blue'>Pátios do Dia</div><div class='kpi-val-blue'>{resumo_card['qtd_patios']} 📌</div><div class='kpi-sub-blue'>Ref: {data_ref_card.strftime('%d/%m/%Y')}</div></div>", unsafe_allow_html=True)
                            dia_idx = data_ref_card.day - 1
                            serie_mes = resumo_card["serie_total_os_mes"]
                            hoje_total = serie_mes[dia_idx] if dia_idx < len(serie_mes) else 0
                            ontem_total = serie_mes[dia_idx - 1] if dia_idx > 0 else hoje_total
                            delta_pct = ((hoje_total - ontem_total) / ontem_total) * 100 if ontem_total > 0 else 0.0
                            seta, sinal = ("↑", "+") if delta_pct > 0 else ("↓", "") if delta_pct < 0 else ("→", "")
                            
                            # --- CARD DO ECHARTS NO MODO DARK ---
                            st_echarts(options={
                                "graphic": [
                                    {"type": "rect", "shape": {"width": 320, "height": 140, "r": 12}, "style": {"fill": "#1A202C", "stroke": "#333D4E", "lineWidth": 1}}, 
                                    {"type": "rect", "shape": {"width": 4, "height": 140, "r": [12, 0, 0, 12]}, "style": {"fill": "#10B981"}}, 
                                    {"type": "text", "left": "6%", "top": "16%", "style": {"text": "TOTAL DE OS DO DIA", "fill": "#94A3B8", "font": "700 14px 'Source Sans Pro', sans-serif"}}, 
                                    {"type": "text", "left": "6%", "top": "40%", "style": {"text": f"{hoje_total} 🎯", "fill": "#F8FAFC", "font": "600 32px 'Source Sans Pro', sans-serif"}}, 
                                    {"type": "text", "left": "6%", "top": "72%", "style": {"text": f"{seta} {sinal}{delta_pct:.1f}% vs ontem", "fill": "#10B981" if delta_pct >= 0 else "#EF4444", "font": "600 12px 'Source Sans Pro', sans-serif"}}
                                ]
                            }, height="140px", key="card_total_os_dia")
                            
                            st.markdown(f"<div style='margin-bottom: 16px;'></div><div class='kpi-wrapper kpi-card-red'><div class='kpi-title-red'>Pátio Prioritário</div><div class='kpi-val-red'>{resumo_card['patio_prioritario']}</div><div class='kpi-sub-red'>Critério: backlog + prioridade</div></div>", unsafe_allow_html=True)

                        with col_turno:
                            _cor_turno_aba2 = { "Turno Dia (07h-19h)": "#F59E0B", "Administrativo (08h-17h30)": "#3B82F6", "Turno Noite (19h-07h)": "#4F46E5" }
                            dados_formatados_turno = [{"value": val, "itemStyle": { "color": _cor_turno_aba2.get(lbl, "#3B82F6"), "borderRadius": [0, 6, 6, 0] }} for lbl, val in zip(resumo_turno["labels"], resumo_turno["valores"])]
                else:
                    st.info("ℹ️ Nenhuma OS encontrada para os filtros selecionados (Data, Pátio ou Tipo de Intervalo). Modifique os filtros para exibir a agenda.")
            st.markdown("---")
            #endregion 10.3.1

#region 10.3.2: Navegação Geográfica Operacional (GPS + Raio)
            st.markdown("### 🗺️ Navegação Geográfica Operacional")
            col_mapa, col_acao = st.columns([6, 4], gap="large")

            if "df_filtrado" in locals(): df_pendentes_f = df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto)].copy()
            else: df_pendentes_f = df_visao[df_visao["Status_norm"].isin(_status_aberto)].copy()

            with col_acao:
                st.markdown("#### ⚙️ Ferramentas de Campo")
                if "lat_partida" not in st.session_state:
                    lat_base, lon_base, nome_base = obter_base_padrao_usuario()
                    st.session_state.update({"lat_partida": lat_base, "lon_partida": lon_base, "local_nome": nome_base})

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📍 Minha Localização", use_container_width=True, key="btn_gps_localizacao"):
                        st.session_state.update({"gps_pending": True, "gps_trials": 0}); st.rerun()
                with c2:
                    if st.button("🏠 Minha Base", use_container_width=True, key="btn_minha_base"):
                        lat_base, lon_base, nome_base = obter_base_padrao_usuario()
                        st.session_state.update({"lat_partida": lat_base, "lon_partida": lon_base, "local_nome": nome_base, "origem_tipo": "BASE", "gps_pending": False, "gps_trials": 0})
                        st.rerun()

                if st.session_state.get("gps_pending"):
                    st.info("Aguardando autorização do navegador e captura do GPS...")
                    loc = get_geolocation()
                    if loc and isinstance(loc, dict) and "coords" in loc:
                        coords = loc.get("coords", {})
                        lat, lon = coords.get("latitude"), coords.get("longitude")
                        if lat is not None and lon is not None:
                            st.session_state.update({"lat_partida": float(lat), "lon_partida": float(lon), "local_nome": reverse_geocode_coordenada(float(lat), float(lon)), "origem_tipo": "GPS", "gps_pending": False, "gps_trials": 0})
                            st.success("GPS ativado com sucesso!"); st.rerun()
                    elif loc and isinstance(loc, dict) and "error" in loc:
                        st.session_state.update({"gps_pending": False, "gps_trials": 0})
                        st.error(f"GPS falhou: {loc['error'].get('message', 'Erro desconhecido')}")
                    else:
                        st.session_state["gps_trials"] += 1
                        if st.session_state["gps_trials"] < 10: time.sleep(0.3); st.rerun()
                        else:
                            st.session_state.update({"gps_pending": False, "gps_trials": 0})
                            st.error("Tempo do GPS esgotado. Tente novamente ou use a Minha Base.")

                st.markdown("---")
                raio_busca_km = st.slider("📏 Raio de Atuação Visual (km):", 0, 50, 10, 1, key="slider_raio_atuacao")
                origem_label = "📍 GPS" if st.session_state.get("origem_tipo") == "GPS" else "🏠 Base"
                st.caption(f"{origem_label}: **{st.session_state['local_nome']}**")

                lat_origem, lon_origem = float(st.session_state["lat_partida"]), float(st.session_state["lon_partida"])

                # CÁLCULO DO RAIO (Acontece antes agora)
                if not df_pendentes_f.empty:
                    df_calc = df_pendentes_f.copy()
                    df_calc["lat_patio"] = df_calc["Patio"].map(lambda p: COORDENADAS_FIXAS.get(str(p).strip().upper(), [np.nan, np.nan])[0])
                    df_calc["lon_patio"] = df_calc["Patio"].map(lambda p: COORDENADAS_FIXAS.get(str(p).strip().upper(), [np.nan, np.nan])[1])
                    com_coord = df_calc.dropna(subset=["lat_patio", "lon_patio"]).copy()

                    if not com_coord.empty:
                        hoje_atual = datetime.now().date()
                        com_coord["Ordem_Prazo"] = com_coord["dt_prog_filtro"].apply(lambda dt: 1 if pd.notna(dt) and dt.date() < hoje_atual else (2 if pd.notna(dt) and dt.date() == hoje_atual else 3))
                        com_coord["Distancia_km"] = haversine_vectorized(lat_origem, lon_origem, com_coord["lat_patio"], com_coord["lon_patio"])
                        df_recomendado = com_coord[com_coord["Distancia_km"] <= raio_busca_km].sort_values(by=["Ordem_Prazo", "Criticidade_rank", "Distancia_km"])

                st.info(f"**{len(df_recomendado)} OS pendentes** encontradas no raio de {raio_busca_km} km.")
                
                # --- BOTÃO OFFLINE AGORA USA O DF_RECOMENDADO (Raio já aplicado!) ---
                if not df_recomendado.empty:
                    pacote_html_bytes = gerar_html_offline(df_recomendado, st.session_state.get("username", "tecnico"))
                    st.download_button(
                        label="📴 Baixar Pacote de OS para Área de Sombra",
                        data=pacote_html_bytes, file_name=f"Rota_Offline_{datetime.now().strftime('%Y%m%d')}.html",
                        mime="text/html", use_container_width=True, type="primary"
                    )
#endregion 10.3.2

 #region 10.3.3: Formulário de Baixa de OS + Evidências (fragment)
                    @st.fragment
                    def renderizar_bloco_apontamento():
                        st.markdown("---")
                        st.markdown("#### ✅ Apontamento e Conclusão de OS")
                        
                        # --- TRAVA DE PRIORIDADE NO SELECT DO DESKTOP ---
                        hoje_atual = datetime.now().date()
                        mask_critica = (df_recomendado["Criticidade_rank"] == 1) & (df_recomendado["dt_prog_filtro"].dt.date <= hoje_atual)
                        
                        if mask_critica.any():
                            st.warning("⚠️ **Foco Operacional Ativo:** Conclua as OS Críticas (Muito Alta) para liberar as demais.")
                            opcoes_os = df_recomendado[mask_critica]["Ordem servico"].astype(str).unique().tolist()
                        else:
                            opcoes_os = df_recomendado["Ordem servico"].astype(str).unique().tolist()

                        os_selecionadas = st.multiselect("1. Selecione as OSs que deseja baixar:", opcoes_os)

                        if os_selecionadas:
                            os_distantes = [os_id for os_id in os_selecionadas if df_recomendado.loc[df_recomendado["Ordem servico"].astype(str) == str(os_id), "Distancia_km"].iloc[0] > 2.0]
                            if os_distantes:
                                st.error(f"🛑 **Bloqueio Geográfico:** O sistema exige estar em um raio máximo de **2 km** do local.")
                                st.warning(f"Você está muito longe das OSs: **{', '.join(os_distantes)}**.")
                                st.info("💡 Aproxime-se do pátio e atualize sua posição em '📍 Minha Localização'.")
                                return

                            st.markdown("---")
                            st.markdown("#### 📷 Evidências Fotográficas")
                            st.caption("Registre a evidência de **cada OS**. A imagem será comprimida automaticamente.")
                            fotos_por_os = {os_id: st.file_uploader("📸 Tirar Foto ou 🖼️ Galeria", type=["jpg", "jpeg", "png"], key=f"foto_{os_id}") for os_id in os_selecionadas}

                            conn = get_connection()
                            try: df_users_equipe = pd.read_sql_query("SELECT username FROM usuarios", conn)
                            finally: release_connection(conn)
                            
                            lista_equipe_disp = df_users_equipe["username"].tolist()
                            usr_logado = st.session_state.get("username", "")
                            if usr_logado in lista_equipe_disp: lista_equipe_disp.remove(usr_logado)
                            
                            with st.form("form_apontamento_os"):
                                equipe_selecionada = st.multiselect("2. Selecione a sua equipe:", lista_equipe_disp)
                                st.markdown("---")
                                st.markdown("#### ⏳ Apontamento de Tempos Individuais")
                                apontamentos, todos_preenchidos = {}, True
                                
                                for os_id in set(os_selecionadas):
                                    st.markdown(f"<b style='color: #3B82F6;'>OS: {os_id}</b>", unsafe_allow_html=True)
                                    c1, c2 = st.columns(2)
                                    with c1: h_ini = st.time_input(f"Horário Início", key=f"time_ini_{os_id}", value=None)
                                    with c2: h_fim = st.time_input(f"Horário Fim", key=f"time_fim_{os_id}", value=None)
                                    apontamentos[os_id] = {"inicio": h_ini, "fim": h_fim}
                                    if h_ini is None or h_fim is None: todos_preenchidos = False
                                    st.markdown("<hr style='margin: 8px 0; border-color: #333D4E;'>", unsafe_allow_html=True)

                                origem = st.session_state.get("origem_tipo", "BASE")
                                if st.form_submit_button("🚀 Concluir e Gravar OS(s)", use_container_width=True):
                                    if origem != "GPS": st.warning("📍 A geolocalização é obrigatória. Atualize sua posição.")
                                    elif not todos_preenchidos: st.warning("⚠️ Preencha os horários de **início e fim** de todas as OSs.")
                                    else:
                                        # --- PREPARAÇÃO DE DADOS (SEM BLOQUEIO DE TEMPO) ---
                                        geo_baixa = f"{st.session_state.get('local_nome', 'Local')} (Lat: {st.session_state.get('lat_partida')}, Lon: {st.session_state.get('lon_partida')})"
                                        equipe_str = ", ".join(equipe_selecionada) if equipe_selecionada else "Sozinho"
                                        realizado_dt = agora_dt()
                                        
                                        for os_id in set(os_selecionadas):
                                            mask = (st.session_state["df_os"]["Ordem servico"].astype(str) == str(os_id))
                                            dt_prog = st.session_state["df_os"].loc[mask, "Data inicial programada"].iloc[0] if len(st.session_state["df_os"].loc[mask]) > 0 else pd.NaT
                                            coord = st.session_state["df_os"].loc[mask, "Coordenacao"].iloc[0] if len(st.session_state["df_os"].loc[mask]) > 0 else "Campo"
                                            
                                            h_i = apontamentos[os_id]["inicio"]
                                            h_f = apontamentos[os_id]["fim"]
                                            
                                            # --- CORREÇÃO AUTOMÁTICA DE DATA PARA O SAP (CRUZAMENTO DE MADRUGADA) ---
                                            if h_f < h_i:
                                                data_inicio_str = (realizado_dt - timedelta(days=1)).strftime("%d/%m/%Y")
                                            else:
                                                data_inicio_str = realizado_dt.strftime("%d/%m/%Y")
                                                
                                            data_fim_str = realizado_dt.strftime("%d/%m/%Y")
                                            
                                            upsert_baixa(
                                                os_id=str(os_id), 
                                                status=determinar_status_execucao(pd.to_datetime(dt_prog, errors="coerce"), realizado_dt),
                                                realizado_em_str=formatar_dt_br(realizado_dt), 
                                                coordenacao=coord, 
                                                concluido_por=usr_logado,
                                                geolocalizacao_baixa=geo_baixa, 
                                                equipe=equipe_str, 
                                                data_inicio=data_inicio_str,      # Data tratada (ontem se cruzou a meia noite)
                                                hora_inicio=h_i.strftime("%H:%M:%S"), 
                                                data_fim=data_fim_str,            # Data tratada (hoje)
                                                hora_fim=h_f.strftime("%H:%M:%S")
                                            )

                                        fotos_enviadas = 0
                                        for os_id_foto in set(os_selecionadas):
                                            foto_da_os = fotos_por_os.get(str(os_id_foto))
                                            if foto_da_os is None: continue
                                            with st.spinner(f"📤 Comprimindo e enviando foto da OS {os_id_foto}..."):
                                                try:
                                                    df_match = st.session_state["df_os"].loc[st.session_state["df_os"]["Ordem servico"].astype(str) == str(os_id_foto)]
                                                    if df_match.empty: continue
                                                    ativo_val = str(df_match["Ativo"].iloc[0]).strip()
                                                    atividade_val = str(df_match["Atividade ativo"].iloc[0]).strip() if "Atividade ativo" in df_match.columns else "N_A"
                                                    url_foto = upload_foto_supabase(foto_da_os.getvalue(), re.sub(r'[^\w\-.]', '_', f"{ativo_val}__{atividade_val}.jpg"))
                                                    upsert_evidencia(ativo=ativo_val, atividade=atividade_val, foto_url=url_foto, os_referencia=str(os_id_foto), concluido_por=usr_logado, geolocalizacao=f"Lat: {st.session_state.get('lat_partida')}, Lon: {st.session_state.get('lon_partida')}")
                                                    fotos_enviadas += 1
                                                except Exception as e_foto: st.warning(f"⚠️ Foto da OS {os_id_foto} falhou: {e_foto}")
                                        
                                        if fotos_enviadas > 0: st.info(f"📷 {fotos_enviadas} evidência(s) registrada(s) com sucesso!")
                                        st.success(f"✅ Execução registrada com sucesso!")
                                        time.sleep(2); st.rerun()

                    renderizar_bloco_apontamento()
                    st.markdown("---")
            #endregion 10.3.3

 #region 10.3.4: Mapa Interativo Otimizado (Cache da Malha)
            with col_mapa:
                lat_centro = min(max(lat_origem, -25.50), -19.50)
                lon_centro = min(max(lon_origem, -53.50), -44.00)
                zoom_mapa = int(min(18, max(6, round(math.log2(360.0 / max((2.0 * max(float(raio_busca_km), 0.5)) / (111.320 * max(math.cos(math.radians(float(lat_centro))), 0.20)), 1e-6))))))

                mapa = folium.Map(location=[lat_centro, lon_centro], zoom_start=zoom_mapa, max_bounds=True, min_lat=-25.50, max_lat=-19.50, min_lon=-53.50, max_lon=-44.00, control_scale=True, tiles="CartoDB positron", prefer_canvas=True)

                # FIX: USO DO KML CACHEADO DA MEMÓRIA
                gdf_malha_cache = carregar_malha_cacheada()
                if gdf_malha_cache is not None:
                    def adicionar_trecho(geom): folium.GeoJson(geom.__geo_interface__, style_function=lambda x: {"color": "#2563EB", "weight": 2, "opacity": 0.70}, control=False).add_to(mapa)
                    for _, row in gdf_malha_cache.iterrows():
                        geom = row.geometry
                        if geom is None or geom.is_empty: continue
                        if geom.geom_type == 'LineString': adicionar_trecho(geom)
                        elif geom.geom_type == 'MultiLineString':
                            for subgeom in geom.geoms: adicionar_trecho(subgeom)

                folium.Marker(location=[lat_origem, lon_origem], tooltip=f"Origem: {st.session_state['local_nome']}", icon=folium.Icon(color="red", icon="home" if st.session_state.get("origem_tipo") != "GPS" else "map-marker", prefix="fa")).add_to(mapa)
                folium.Circle(radius=raio_busca_km * 1000, location=[lat_origem, lon_origem], color="#3B82F6", fill=True, fill_opacity=0.08, weight=2, tooltip=f"Raio: {raio_busca_km} km").add_to(mapa)

                if not df_recomendado.empty:
                    agg_map = df_recomendado.groupby("Patio", as_index=False).agg(lat_patio=("lat_patio", "first"), lon_patio=("lon_patio", "first"), qtd_os=("Ordem servico", "count"), menor_dist=("Distancia_km", "min"))
                    for _, row in agg_map.iterrows(): folium.CircleMarker(location=[row["lat_patio"], row["lon_patio"]], radius=6, color="#1D4ED8", weight=1.5, fill=True, fill_color="#3B82F6", fill_opacity=0.95, tooltip=f"Pátio: {row['Patio']}<br>OS: {row['qtd_os']}<br>Distância: {row['menor_dist']:.1f} km").add_to(mapa)

                st_folium(mapa, height=650, use_container_width=True, returned_objects=[], key="mapa_final_limpo")
            st.markdown("---")
            #endregion 10.3.4

#region 10.3.5: Cronograma de Execução de Campo (Tabela/PDF)
            if not df_recomendado.empty:
                df_tabela_campo = df_recomendado.copy()
                
                df_tabela_campo = df_tabela_campo.rename(columns={"Ordem servico": "OS", "Classificacao": "Classificação"})
                df_tabela_campo["Data da Programação"] = df_tabela_campo["dt_prog_filtro"].dt.strftime("%d/%m/%Y")
                colunas_exibir = ["OS", "Data da Programação", "Patio", "Ativo", "Criticidade", "Classificação", "Descrição Longa"]

                col_tit_crono, col_btn_crono = st.columns([7.5, 2.5])
                with col_btn_crono:
                    st.markdown("<br>", unsafe_allow_html=True)
                    try:
                        from reportlab.lib.pagesizes import A4, landscape; from reportlab.lib import colors; from reportlab.lib.units import mm
                        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer; from reportlab.lib.styles import getSampleStyleSheet
                        def gerar_pdf_cronograma(df_pdf, colunas):
                            buf = io.BytesIO()
                            doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10*mm, rightMargin=10*mm, topMargin=15*mm, bottomMargin=15*mm)
                            styles, elementos = getSampleStyleSheet(), [Paragraph("📋 Cronograma de Execução de Campo", getSampleStyleSheet()["Title"]), Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Origem: {st.session_state.get('local_nome', 'N/A')} | Raio: {raio_busca_km} km", getSampleStyleSheet()["Normal"]), Spacer(1, 6*mm)]
                            data_rows = [[str(c) for c in colunas]]
                            style_cell = styles["Normal"]; style_cell.fontSize, style_cell.leading = 7, 9
                            for _, row in df_pdf[colunas].iterrows(): 
                                data_rows.append([Paragraph(str(v).replace('\n', '<br/>').replace('\r', ''), style_cell) for v in row.values])
                            col_widths = [45, 45, 35, 90, 45, 70, landscape(A4)[0] - 20*mm - 330]
                            tabela = Table(data_rows, colWidths=col_widths, repeatRows=1)
                            tabela.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, 0), 8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
                            elementos.append(tabela); doc.build(elementos); buf.seek(0)
                            return buf.getvalue()

                        st.download_button("🖨️ Gerar Impressão PDF", data=gerar_pdf_cronograma(df_tabela_campo, colunas_exibir), file_name=f"Crono_Campo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf", mime="application/pdf", use_container_width=True)
                    except ImportError: st.warning("⚠️ 'reportlab' não instalada.")
                
                with col_tit_crono: 
                    st.markdown("#### 📋 Cronograma de Execução de Campo\n<small>OS Pendentes recomendadas no raio de atuação visual por prioridade</small>", unsafe_allow_html=True)
                
                def aplicar_cor_foco(row):
                    hoje_atual = datetime.now().date()
                    tem_critica_no_raio = (df_recomendado["Criticidade_rank"] == 1) & (df_recomendado["dt_prog_filtro"].dt.date <= hoje_atual)
                    
                    if tem_critica_no_raio.any():
                        if row["Criticidade"] == "Muito Alta":
                            return ["background-color: #FEF2F2; color: #991B1B; font-weight: bold; border-bottom: 1px solid #FECACA;"] * len(row)
                        else:
                            return ["background-color: #F8FAFC; color: #94A3B8; border-bottom: 1px solid #E2E8F0;"] * len(row) 
                    
                    dt = row["dt_prog_filtro"]
                    if pd.isna(dt): return ["border-bottom: 1px solid #E2E8F0;"] * len(row)
                    if dt.date() < hoje_atual: return ["background-color: #FEE2E2; color: #7F1D1D; font-weight: 500; border-bottom: 1px solid #FECACA;"] * len(row)
                    elif dt.date() == hoje_atual: return ["background-color: #FEF3C7; color: #78350F; font-weight: 500; border-bottom: 1px solid #FDE68A;"] * len(row)
                    return ["border-bottom: 1px solid #E2E8F0;"] * len(row)
                
                df_estilizado = df_tabela_campo[colunas_exibir].style.apply(aplicar_cor_foco, axis=1).hide(axis="index")
                tabela_html = df_estilizado.to_html(escape=False)
                
                html_code = f"""<style>
.scroll-rota {{ width: 100%; max-height: 400px; overflow: auto; border: 1px solid #E2E8F0; border-radius: 8px; }}
.tabela-rota {{ width: 100%; border-collapse: collapse; font-family: "Source Sans Pro", sans-serif; font-size: 13px; background-color: #FFFFFF; color: #0F172A; }}
.tabela-rota th {{ background-color: #1E293B; color: #F8FAFC; position: sticky; top: 0; z-index: 1; padding: 10px; text-align: left; border-bottom: 2px solid #3B82F6; white-space: nowrap; }}
.tabela-rota td {{ padding: 8px 10px; vertical-align: middle; white-space: nowrap; }}
.tabela-rota td:nth-child(7) {{ min-width: 500px; white-space: pre-wrap; word-wrap: break-word; }}
</style>
<div class="scroll-rota">
{tabela_html.replace('<table', '<table class="tabela-rota"')}
</div>"""
                st.markdown(html_code, unsafe_allow_html=True)
            else: 
                st.info("Nenhuma OS pendente localizada dentro do raio de atuação selecionado.")
#endregion 10.3.5
#endregion 10.3
#endregion SESSÃO 10

#region SESSÃO 11: Tela Isolada de Governança e Auditoria

#region 11.0: Cabeçalho e Navegação
if st.session_state.get("tela_atual") == "governanca":
    col_gov_t1, col_gov_t2 = st.columns([8, 2])
    with col_gov_t1: st.title("🛡️ Motor de Governança e Auditoria")
    with col_gov_t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Voltar ao Painel", use_container_width=True): st.session_state.update({"tela_atual": "dashboard", "gov_auth_ok": False}); st.rerun()
    st.markdown("Análise estatística de eficiência, variabilidade de cronograma, aderência de login e rastreabilidade de campo.")
    st.markdown("---")
#endregion 11.0

#region 11.1: Controle de acesso e segurança
    if not st.session_state.get("gov_auth_ok", False):
        st.error("🔒 **Acesso Restrito:** Confirme sua credencial para métricas de auditoria.")
        col_auth1, _ = st.columns([1, 2])
        with col_auth1:
            with st.form("form_auth_gov"):
                senha_confirm = st.text_input("Digite sua Senha", type="password")
                if st.form_submit_button("Desbloquear Painel", use_container_width=True):
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT senha_hash FROM usuarios WHERE username = %s", (st.session_state.get("username"),))
                    row = cur.fetchone()
                    cur.close(); release_connection(conn)
                    if row and row[0] == hash_senha(senha_confirm): st.session_state["gov_auth_ok"] = True; st.rerun()
                    else: st.error("❌ Senha incorreta. Acesso negado.")
        st.stop()
#endregion 11.1

#region 11.2: Carregamento de dados de auditoria
    with st.spinner("Compilando logs de auditoria e telemetria..."):
        if st.session_state.get("chk_sim", False): df_baixas_full, df_logs = st.session_state.get("df_baixas_sim", pd.DataFrame()), st.session_state.get("df_logs_sim", pd.DataFrame())
        else:
            conn = get_connection()
            df_baixas_full = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim FROM baixas", conn)
            df_logs = pd.read_sql_query("SELECT username, data_hora_login FROM logs_acesso", conn)
            release_connection(conn)

        df_os_base = st.session_state.get("df_os", pd.DataFrame())
        if df_baixas_full.empty or df_os_base.empty: st.warning("Não há dados suficientes para auditoria."); st.stop()

        df_gov = df_baixas_full.merge(df_os_base[["Ordem servico", "Patio", "Ativo", "Classificacao", "Criticidade_rank", "Nivel_Prioridade", "Criticidade"]], left_on="os", right_on="Ordem servico", how="inner")
        df_gov = df_gov[df_gov["status"].str.upper().isin(["REALIZADO", "REALIZADO FORA DA DATA DE PROGRAMAÇÃO", "REALIZADO FORA DO PRAZO"])]

        def calc_duracao(row):
            try:
                diff = (pd.to_datetime(row['hora_fim'], format='%H:%M:%S') - pd.to_datetime(row['hora_inicio'], format='%H:%M:%S')).total_seconds() / 60.0
                return diff + (24 * 60) if diff < 0 else diff
            except: return 0.0

        df_gov["Tempo_Minutos"] = df_gov.apply(calc_duracao, axis=1)
        df_gov["Data_Real"] = pd.to_datetime(df_gov["data_inicio"], format="%d/%m/%Y", errors="coerce").dt.date
        df_gov["Via_GPS"] = df_gov["geolocalizacao_baixa"].apply(lambda x: 0 if "Base" in str(x) or "Sede" in str(x) else 1)
        df_gov["Alta_Prioridade"] = df_gov["Criticidade_rank"].apply(lambda x: 1 if x in [1, 2] else 0)
#endregion 11.2

#region 11.3: Fragmento de Governança (@st.fragment)
    @st.fragment
    def fragmento_governanca():
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: 
            tecnicos_disp = sorted(df_gov["concluido_por"].dropna().unique().tolist())
            tec_selecionado = st.multiselect("👤 Filtrar Colaborador(es):", tecnicos_disp, default=tecnicos_disp)
        with col_f2: 
            patios_gov = sorted(df_gov["Patio"].dropna().unique().tolist())
            patio_selecionado = st.multiselect("📍 Filtrar Pátio(s):", patios_gov, default=patios_gov)
        with col_f3:
            # --- CORREÇÃO AQUI: Remove os campos vazios antes de calcular min e max ---
            datas_validas = df_gov["Data_Real"].dropna()
            
            if not datas_validas.empty:
                min_d, max_d = datas_validas.min(), datas_validas.max()
            else:
                min_d = max_d = datetime.now().date()
                
            data_gov = st.date_input("📅 Período de Execução:", value=(min_d, max_d), min_value=min_d, max_value=max_d, format="DD/MM/YYYY")

        d_inicio, d_fim = data_gov if isinstance(data_gov, tuple) and len(data_gov) == 2 else (data_gov[0] if isinstance(data_gov, tuple) else data_gov, data_gov[0] if isinstance(data_gov, tuple) else data_gov)
        df_gov_f = df_gov[(df_gov["concluido_por"].isin(tec_selecionado)) & (df_gov["Patio"].isin(patio_selecionado)) & (df_gov["Data_Real"] >= d_inicio) & (df_gov["Data_Real"] <= d_fim)].copy()

        if df_gov_f.empty: 
            st.info("Nenhuma execução encontrada para os filtros selecionados.")
            return

        total_os_gov = len(df_gov_f)
        tme_minutos = df_gov_f["Tempo_Minutos"].fillna(0).mean() 
        taxa_gps = (df_gov_f["Via_GPS"].sum() / total_os_gov) * 100 if total_os_gov > 0 else 0
        taxa_prio = (df_gov_f["Alta_Prioridade"].sum() / total_os_gov) * 100 if total_os_gov > 0 else 0

        c_k1, c_k2, c_k3, c_k4 = st.columns(4)
        c_k1.metric("🔧 Volume de Execução", f"{total_os_gov} OS")
        c_k2.metric("⏱️ Tempo Médio / OS (TME)", f"{int(tme_minutos // 60)}h {int(tme_minutos % 60):02d}m" if not pd.isna(tme_minutos) else "0h 00m")
        c_k3.metric("🎯 Aderência à Prioridade", f"{taxa_prio:.1f}%")
        c_k4.metric("📍 Integridade de GPS", f"{taxa_gps:.1f}%")
        st.markdown("---")
#endregion

#region 11.4: Volume Diário e Produtividade Acumulada
        col_l1_c1, col_l1_c2 = st.columns(2, gap="large")
        df_real_dia = df_gov_f.groupby("Data_Real").size().reset_index(name="Realizado")
        df_os_base["Data_Prog_Pure"] = pd.to_datetime(df_os_base["Data inicial programada"], errors="coerce").dt.date
        df_plan_dia = df_os_base.groupby("Data_Prog_Pure").size().reset_index(name="Planejado_Backlog")

        df_merge_vol = pd.merge(df_real_dia, df_plan_dia, left_on="Data_Real", right_on="Data_Prog_Pure", how="outer")
        df_merge_vol["Data_Real"] = df_merge_vol["Data_Real"].combine_first(df_merge_vol["Data_Prog_Pure"])
        df_merge_vol = df_merge_vol.fillna(0).sort_values(by="Data_Real")
        eixo_x_l1 = [d.strftime("%d/%m") if hasattr(d, "strftime") else str(d) for d in df_merge_vol["Data_Real"]]

        with col_l1_c1:
            st.markdown("#### 📈 Volume Diário")
            st_echarts(options={ "tooltip": {"trigger": "axis"}, "legend": {"data": ["Volume Diário", "Planejado + Backlog"], "bottom": "0%"}, "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}}, "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}], "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True}, "xAxis": {"type": "category", "data": eixo_x_l1}, "yAxis": {"type": "value"}, "series": [ {"name": "Volume Diário", "type": "bar", "data": df_merge_vol["Realizado"].tolist(), "itemStyle": {"color": "#3B82F6"}}, {"name": "Planejado + Backlog", "type": "line", "data": df_merge_vol["Planejado_Backlog"].tolist(), "smooth": True, "lineStyle": {"type": "dashed", "color": "#64748B", "width": 3}, "itemStyle": {"color": "#64748B"}} ] }, height="350px", theme="streamlit", key="gov_vol_diario")

        with col_l1_c2:
            st.markdown("#### 📈 Produtividade Acumulada")
            df_merge_vol["Real_Acum"], df_merge_vol["Plan_Acum"] = df_merge_vol["Realizado"].cumsum(), df_merge_vol["Planejado_Backlog"].cumsum()
            st_echarts(options={ "tooltip": {"trigger": "axis"}, "legend": {"data": ["Realizado Acumulado", "Planejado Acumulado"], "bottom": "0%"}, "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}}, "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}], "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True}, "xAxis": {"type": "category", "data": eixo_x_l1}, "yAxis": {"type": "value"}, "series": [ {"name": "Realizado Acumulado", "type": "line", "smooth": True, "data": df_merge_vol["Real_Acum"].tolist(), "areaStyle": {"color": "rgba(59,130,246,0.15)"}, "lineStyle": {"color": "#3B82F6", "width": 3}, "itemStyle": {"color": "#3B82F6"}}, {"name": "Planejado Acumulado", "type": "line", "smooth": True, "data": df_merge_vol["Plan_Acum"].tolist(), "lineStyle": {"type": "dashed", "color": "#64748B", "width": 3}, "itemStyle": {"color": "#64748B"}} ] }, height="350px", theme="streamlit", key="gov_prod_acum")
 #endregion 11.4

#region 11.5: Produtividade Individual, Esforço e Heatmap
        st.markdown("<br>", unsafe_allow_html=True); st.markdown("---")
        col_l2_c1, col_l2_c2, col_l2_c3 = st.columns(3, gap="medium")

        with col_l2_c1:
            st.markdown("#### 👥 Produtividade Individual")
            df_crit = df_gov_f.groupby("Criticidade").size().reset_index(name="Volume")
            st_echarts(options={ "tooltip": {"trigger": "item"}, "legend": {"orient": "horizontal", "bottom": "0%"}, "series": [{ "type": "pie", "radius": ["40%", "70%"], "data": [{"value": int(r["Volume"]), "name": str(r["Criticidade"])} for _, r in df_crit.iterrows()], "label": {"show": True, "formatter": "{c}"} }] }, height="320px", key="gov_donut_criticidade")

        with col_l2_c2:
            st.markdown("#### ⏱️ Esforço x Classificação")
            df_classif = df_gov_f.groupby("Classificacao").agg(Tempo_Medio=("Tempo_Minutos", "mean")).fillna(0).reset_index().sort_values("Tempo_Medio", ascending=True)
            st_echarts(options={ "tooltip": {"trigger": "axis"}, "xAxis": {"type": "value"}, "yAxis": {"type": "category", "data": df_classif["Classificacao"].tolist()}, "series": [{"type": "bar", "data": df_classif["Tempo_Medio"].round(1).tolist(), "itemStyle": {"color": "#F59E0B"}}] }, height="320px", key="gov_esforco_classe")

        with col_l2_c3:
            st.markdown("#### 🔁 Tipo de OS x Frequência")
            agg_heatmap = df_gov_f.groupby(["Patio", "Classificacao"]).size().reset_index(name="Total")
            p_list, c_list = sorted(df_gov_f["Patio"].unique().tolist()), ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
            h_data, max_v = [], 0
            for yi, c_n in enumerate(c_list):
                for xi, p_n in enumerate(p_list):
                    val = int(agg_heatmap[(agg_heatmap["Patio"] == p_n) & (agg_heatmap["Classificacao"] == c_n)]["Total"].iloc[0]) if not agg_heatmap[(agg_heatmap["Patio"] == p_n) & (agg_heatmap["Classificacao"] == c_n)].empty else 0
                    h_data.append([xi, yi, val]); max_v = max(max_v, val)
            st_echarts(options={ "tooltip": {"position": "top"}, "grid": {"height": "65%", "top": "5%", "bottom": "20%", "left": "20%"}, "xAxis": {"type": "category", "data": p_list, "axisLabel": {"interval": 0, "rotate": 45}}, "yAxis": {"type": "category", "data": c_list}, "visualMap": {"min": 0, "max": max_v if max_v > 0 else 5, "orient": "horizontal", "left": "center", "bottom": "0%", "inRange": {"color": ["#F8FAFC", "#93C5FD", "#1D4ED8"]}}, "series": [{"type": "heatmap", "data": h_data, "label": {"show": True}, "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 1.5}}] }, height="320px", key="gov_heatmap_freq")
#endregion 11.5

#region 11.6: Aderência, Top Técnicos e Variabilidade
        st.markdown("<br>", unsafe_allow_html=True); st.markdown("---")
        col_l3_c1, col_l3_c2, col_l3_c3 = st.columns(3, gap="medium")

        with col_l3_c1:
            st.markdown("#### 🕒 Aderência: Login vs. Apontamento")
            df_logs["Data_Real_Pure"] = pd.to_datetime(df_logs["data_hora_login"]).dt.date
            df_gov_f["dt_baixa_calc"] = pd.to_datetime(df_gov_f["data_fim"] + " " + df_gov_f["hora_fim"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
            df_primeira_baixa = df_gov_f.groupby(["concluido_por", "Data_Real"])["dt_baixa_calc"].min().reset_index(name="dt_baixa_1os")
            df_aderencia = df_logs.merge(df_primeira_baixa, left_on=["username", "Data_Real_Pure"], right_on=["concluido_por", "Data_Real"])

            if not df_aderencia.empty:
                df_aderencia["x_date"] = pd.to_datetime(df_aderencia["data_hora_login"]).dt.strftime("%d/%m")
                dt_login, dt_baixa = pd.to_datetime(df_aderencia["data_hora_login"]), pd.to_datetime(df_aderencia["dt_baixa_1os"])
                
                df_aderencia["y_login_frac"] = dt_login.dt.hour + dt_login.dt.minute / 60.0
                df_aderencia["y_baixa_frac"] = dt_baixa.dt.hour + dt_baixa.dt.minute / 60.0
                
                # --- CORREÇÃO AQUI: Remove os NaNs antes de criar as listas do JSON ---
                df_aderencia = df_aderencia.dropna(subset=["y_login_frac", "y_baixa_frac"]).sort_values("Data_Real_Pure")
                
                # Só monta o gráfico se ainda sobrar dados após a limpeza
                if not df_aderencia.empty:
                    login_data = [[row["x_date"], round(row["y_login_frac"], 2), row["username"]] for _, row in df_aderencia.iterrows()]
                    baixa_data = [[row["x_date"], round(row["y_baixa_frac"], 2), row["username"]] for _, row in df_aderencia.iterrows()]
                    
                    st_echarts(options={ 
                        "tooltip": { 
                            "trigger": "item", 
                            "formatter": JsCode("""function (p) { var hh = Math.floor(p.data[1]); var mm = Math.round((p.data[1] - hh) * 60); if (mm == 60) { hh += 1; mm = 0; } return '<b>' + p.data[2] + '</b><br>' + p.seriesName + ': ' + (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm + '<br>Data: ' + p.data[0]; }""") 
                        }, 
                        "legend": {"data": ["Login", "Primeira Baixa"], "bottom": "0%"}, 
                        "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}], 
                        "grid": {"top": "10%", "bottom": "25%", "left": "12%", "right": "5%"}, 
                        "xAxis": {"type": "category", "data": sorted(df_aderencia["x_date"].unique().tolist())}, 
                        "yAxis": { "type": "value", "name": "Horário", "min": 0, "max": 24, "interval": 4, "axisLabel": { "formatter": JsCode("""function(value) { var hh = Math.floor(value); return (hh < 10 ? '0' : '') + hh + ':00'; }""") } }, 
                        "series": [ 
                            {"name": "Login", "type": "scatter", "data": login_data, "symbolSize": 10, "itemStyle": {"color": "#3B82F6"}}, 
                            {"name": "Primeira Baixa", "type": "scatter", "data": baixa_data, "symbolSize": 10, "itemStyle": {"color": "#10B981"}} 
                        ] 
                    }, height="400px", theme="streamlit", key="gov_scatter_aderencia")
                else:
                    st.info("Dados de horário insuficientes para plotar o gráfico de aderência.")
            else: 
                st.info("Dados insuficientes para cruzar login com apontamento.")

        with col_l3_c2:
            st.markdown("#### 🔝 Top Técnicos: OS por Pátio")
            df_freq = df_gov_f.groupby(["concluido_por", "Patio"]).size().reset_index(name="Qtd")
            tecnicos_top, patios_top = df_freq["concluido_por"].unique().tolist(), sorted(df_freq["Patio"].unique().tolist())
            series_top = [{"name": patio, "type": "bar", "stack": "total", "data": [int(df_freq[(df_freq["concluido_por"] == tec) & (df_freq["Patio"] == patio)]["Qtd"].iloc[0]) if not df_freq[(df_freq["concluido_por"] == tec) & (df_freq["Patio"] == patio)].empty else 0 for tec in tecnicos_top], "label": {"show": False}} for patio in patios_top]
            st_echarts(options={ "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, "legend": {"bottom": "0%", "textStyle": {"fontSize": 10}}, "grid": {"left": "5%", "right": "5%", "bottom": "18%", "top": "10%", "containLabel": True}, "xAxis": {"type": "category", "data": tecnicos_top, "axisLabel": {"interval": 0, "rotate": 30, "fontSize": 10}}, "yAxis": {"type": "value"}, "series": series_top }, height="400px", theme="streamlit", key="gov_top_tec")

        with col_l3_c3:
            st.markdown("#### 📊 Variabilidade de Execução")
            df_var = df_gov_f.groupby("concluido_por")["Tempo_Minutos"].mean().fillna(0).reset_index().sort_values("Tempo_Minutos", ascending=True)
            st_echarts(options={ "tooltip": {"trigger": "axis"}, "grid": {"left": "5%", "right": "8%", "bottom": "10%", "top": "10%", "containLabel": True}, "xAxis": {"type": "value", "name": "Minutos"}, "yAxis": {"type": "category", "data": df_var["concluido_por"].tolist(), "axisLabel": {"fontSize": 10}}, "series": [{"type": "bar", "data": df_var["Tempo_Minutos"].round(1).tolist(), "itemStyle": {"color": "#8B5CF6"}, "label": {"show": True, "position": "right", "formatter": "{c} min", "fontSize": 10}}] }, height="400px", theme="streamlit", key="gov_variab")
#endregion 11.6

#region 11.7: Tabela de Auditoria GPS
        st.markdown("---")
        st.markdown("#### 📍 Tabela de Auditoria de Apontamentos (GPS)")
        df_auditoria = df_gov_f[["Ordem servico", "concluido_por", "data_inicio", "hora_fim", "geolocalizacao_baixa", "equipe", "Tempo_Minutos"]].copy().sort_values(by=["data_inicio", "hora_fim"], ascending=[False, False]).rename(columns={"Ordem servico": "OS", "concluido_por": "Apontador Principal", "data_inicio": "Data", "hora_fim": "Hora Apontada", "geolocalizacao_baixa": "Localização do Celular", "equipe": "Co-Executantes", "Tempo_Minutos": "Tempo Gasto (min)"})
        df_auditoria["Tempo Gasto (min)"] = df_auditoria["Tempo Gasto (min)"].fillna(0).round(0).astype(int)
        
        def estilo_gps(v):
            if pd.notna(v) and ('Base' in str(v) or 'Sede' in str(v)):
                return 'background-color: #FEE2E2; color: #991B1B; font-weight: bold; border-bottom: 1px solid #FECACA;'
            return 'color: #065F46; border-bottom: 1px solid #E2E8F0;'
            
        df_estilizado = df_auditoria.style.map(estilo_gps, subset=["Localização do Celular"]).hide(axis="index")
        tabela_html = df_estilizado.to_html(escape=False)
        
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        body {{ margin: 0; font-family: "Source Sans Pro", sans-serif; background-color: #FFFFFF; }}
        .tabela-gov {{ width: 100%; border-collapse: collapse; font-size: 13px; color: #0F172A; }}
        .tabela-gov th {{ 
            background-color: #1E293B; color: #F8FAFC; position: sticky; top: 0; z-index: 1; 
            padding: 10px; text-align: left; border-bottom: 2px solid #3B82F6; white-space: nowrap; 
            cursor: pointer; user-select: none; transition: background-color 0.2s;
        }}
        .tabela-gov th:hover {{ background-color: #333D4E; }}
        .tabela-gov th::after {{ content: ' ↕'; font-size: 11px; color: #94A3B8; padding-left: 5px; }}
        .tabela-gov td {{ padding: 8px 10px; vertical-align: middle; white-space: nowrap; border-bottom: 1px solid #E2E8F0; }}
        .tabela-gov td:nth-child(5) {{ min-width: 400px; white-space: pre-wrap; word-wrap: break-word; }}
        .tabela-gov td:nth-child(6) {{ min-width: 200px; white-space: pre-wrap; word-wrap: break-word; }}
        </style>
        </head>
        <body>
        {tabela_html.replace('<table', '<table class="tabela-gov"')}
        
        <script>
        const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;
        const comparer = (idx, asc) => (a, b) => ((v1, v2) => 
            v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2)
            )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));
        document.querySelectorAll('th').forEach(th => th.addEventListener('click', function() {{
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            Array.from(tbody.querySelectorAll('tr'))
                .sort(comparer(Array.from(th.parentNode.children).indexOf(th), this.asc = !this.asc))
                .forEach(tr => tbody.appendChild(tr));
        }}));
        </script>
        </body>
        </html>
        """
        import streamlit.components.v1 as components
        components.html(html_code, height=400, scrolling=True)
#endregion 11.7
        
    fragmento_governanca()
    st.stop()
#endregion SESSÃO 11
#endregion