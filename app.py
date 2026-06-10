#region SESSÃO 1: Imports, Configurações e Funções de Base
import io
import time
import math
import re
import os
import shutil
import hashlib
import json
import psycopg2
import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from streamlit_js_eval import get_geolocation
from streamlit_echarts import st_echarts, JsCode
from datetime import datetime, timezone, timedelta
from pathlib import Path
from streamlit_calendar import calendar
from psycopg2.extras import execute_values
from psycopg2 import pool
import requests

# --- CONFIGURAÇÕES GLOBAIS ---
st.set_page_config(page_title="Painel de OS Eletroeletrônica", layout="wide", initial_sidebar_state="collapsed")

if not st.session_state.get("logged_in", False):
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 6, 1])
    with col_centro:
        st.markdown("<h1 style='text-align: center;'>⚡ Sistema de Gestão de Ordens de Serviço</h1>", unsafe_allow_html=True)

# --- GERENCIAMENTO DE CONEXÃO NEON (POSTGRES) ---
@st.cache_resource
def init_connection_pool():
    return psycopg2.pool.SimpleConnectionPool(
        1, 20, st.secrets["NEON_POSTGRES_URL"]
    )

pool_conexoes = init_connection_pool()

def get_connection():
    return pool_conexoes.getconn()

def release_connection(conn):
    pool_conexoes.putconn(conn)

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

_status_prazo  = {"REALIZADO"}
_status_atraso = {"REALIZADO FORA DA DATA DE PROGRAMAÇÃO", "REALIZADO FORA DO PRAZO"}
_status_aberto = {"NÃO REALIZADO", "NAO REALIZADO", "PENDENTE", "ATRASADO", ""}

def init_db():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Criação padrão das tabelas...
        cur.execute("""
            CREATE TABLE IF NOT EXISTS baixas (
                os VARCHAR(255) PRIMARY KEY, status VARCHAR(255) NOT NULL, 
                realizado_em VARCHAR(255) NOT NULL, coordenacao VARCHAR(255) NOT NULL, concluido_por VARCHAR(255)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                username VARCHAR(255) PRIMARY KEY, senha_hash VARCHAR(255) NOT NULL, 
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
                id SERIAL PRIMARY KEY,
                ativo VARCHAR(255) NOT NULL,
                atividade VARCHAR(500) NOT NULL,
                foto_url TEXT,
                os_referencia VARCHAR(255),
                concluido_por VARCHAR(255),
                geolocalizacao VARCHAR(255),
                data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ativo, atividade)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mapeamento_patios (
                ativo_chave VARCHAR(500) PRIMARY KEY,
                patio VARCHAR(10) NOT NULL,
                tipo VARCHAR(20) DEFAULT 'Ativo',
                data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # --- ATUALIZAÇÕES AUTOMÁTICAS DE ESTRUTURA (UPGRADE V6 E FASE 2) ---
        try:
            cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS governanca VARCHAR(255) DEFAULT 'Painel Gerencial,Mapa de Campo';")
        except Exception: conn.rollback()
        
        try:
            cur.execute("ALTER TABLE os_programadas ADD COLUMN IF NOT EXISTS coordenacao VARCHAR(100);")
        except Exception: conn.rollback()

        # NOVAS COLUNAS PARA A FASE 2 (Apontamentos e GPS)
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
                INSERT INTO usuarios (username, senha_hash, perfil, escopo, reset_obrigatorio, governanca) 
                VALUES (%s, %s, %s, %s, 1, %s)
            """, ('admin', hash_senha('mrs123'), 'Gerência', 'Todas', 'Painel Gerencial,Mapa de Campo,Upload de Dados,Gestão de Usuários'))
            
        conn.commit()
        cur.close()
    except Exception as e:
        import logging
        logging.warning(f"[init_db] Erro na inicialização do banco: {e}")
    finally:
        if conn is not None:
            release_connection(conn)
init_db()

# --- INICIALIZAÇÃO CENTRALIZADA DE SESSION_STATE ---
_defaults_session = {
    "gps_pending": False,
    "gps_trials": 0,
    "origem_tipo": "BASE",
    "gov_auth_ok": False,
}
for _key, _val in _defaults_session.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

#endregion

#region SESSÃO 1.5: Barreira de Login com Governança e GPS Obrigatório
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": "", "perfil": "", "escopo": "", "governanca": "", "needs_reset": False, "validando_gps": False})

if not st.session_state["logged_in"]:
    st.markdown("<h3 style='text-align: center; color: #475569;'>Acesso Restrito</h3>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    
    with col_l2:
        # ETAPA 3: Reset de Senha (se for o primeiro acesso)
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
            
        # ETAPA 2: Barreira de GPS Obrigatória (Apenas Técnico)
        elif st.session_state.get("validando_gps"):
            st.info("📍 **Para acessar o conteúdo é necessário a ativação do GPS.** Por favor, clique em 'Permitir' no aviso do seu navegador.")
            loc_login = get_geolocation()
            
            if loc_login and isinstance(loc_login, dict) and "coords" in loc_login:
                coords = loc_login.get("coords", {})
                lat_log = coords.get("latitude")
                lon_log = coords.get("longitude")
                
                if lat_log is not None and lon_log is not None:
                    # Grava no banco de dados o log de acesso
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
                    
                    # Concede o acesso final
                    st.session_state.update({
                        "logged_in": True,
                        "username": st.session_state["temp_user"],
                        "perfil": st.session_state["temp_perfil"],
                        "escopo": st.session_state["temp_escopo"],
                        "governanca": st.session_state["temp_gov"]
                    })
                    st.session_state["validando_gps"] = False
                    st.rerun()
                    
            elif loc_login and isinstance(loc_login, dict) and "error" in loc_login:
                st.error("🛑 **Acesso Bloqueado:** O sistema exige a leitura do seu GPS para permitir o login. Verifique se o GPS do seu aparelho está ligado e se o seu navegador tem permissão de localização.")
                if st.button("⬅️ Voltar para o Login"):
                    st.session_state["validando_gps"] = False
                    st.rerun()
                
        # ETAPA 1: Login Padrão
        else:
            with st.form("form_login"):
                user_input = st.text_input("Usuário")
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
                        
                        # --- FILTRO INTELIGENTE DE GPS ---
                        if row[1] == "Técnico":
                            st.session_state["validando_gps"] = True
                        else:
                            st.session_state.update({
                                "logged_in": True,
                                "username": st.session_state["temp_user"],
                                "perfil": st.session_state["temp_perfil"],
                                "escopo": st.session_state["temp_escopo"],
                                "governanca": st.session_state["temp_gov"]
                            })
                        st.rerun()
                        # ---------------------------------
                else: st.error("❌ Usuário ou senha incorretos.")
    st.stop()
#endregion

#region SESSÃO 2: Funções (Lógica, Utilidades, GPS, Distância, Persistência, Export)
# ==========================================
# SESSÃO 2: Funções (Lógica, Utilidades, GPS, Distância, Persistência, Export)
# ==========================================

#region SESSÃO 2.1 ===== Lógica =====
def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    # Agressivo contra sujeiras do SAP: remove \n, \r, espaços extras e deixa maiúsculo
    df.columns = df.columns.astype(str).str.replace('\n', ' ').str.replace('\r', '').str.strip().str.upper()
    return df

def pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def classificar_atividade(atividade: str) -> str:
    s = str(atividade).upper()
    if "_MAN_CONF_" in s:
        return "Confiabilidade e Segurança"
    if "_SEG_" in s:
        return "Segurança"
    if "_CONF_" in s:
        return "Confiabilidade"
    return "Confiabilidade"

def extrair_criticidade(prioridade: str):
    p = str(prioridade).strip()
    m = re.match(r"^\s*([1-4])\s*[-–]?\s*(.*)$", p)
    if m:
        codigo = int(m.group(1))
        mapa = {1: "Muito Alta", 2: "Alta", 3: "Média", 4: "Baixa"}
        return codigo, mapa.get(codigo, "Baixa")

    pu = p.upper()
    if "MUITO" in pu and "ALTA" in pu:
        return 1, "Muito Alta"
    if "ALTA" in pu:
        return 2, "Alta"
    if "MÉDIA" in pu or "MEDIA" in pu:
        return 3, "Média"
    if "BAIXA" in pu:
        return 4, "Baixa"
    return 4, "Baixa"

def calcular_nivel_prioridade(classificacao: str, criticidade_rank: int) -> int:
    # Ordem solicitada:
    # 1) Confiabilidade e Segurança
    # 2) Segurança
    # 3) Confiabilidade
    base_map = {
        "Confiabilidade e Segurança": 1,
        "Segurança": 2,
        "Confiabilidade": 3
    }
    base = base_map.get(classificacao, 3)
    return base * 10 + int(criticidade_rank)

def parse_data_programada(valor):
    if pd.isna(valor):
        return pd.NaT
    try:
        return pd.to_datetime(valor, dayfirst=True, errors="coerce")
    except Exception:
        return pd.NaT

def agora_dt():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br)

def formatar_dt_br(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")

def determinar_status_execucao(data_programada: pd.Timestamp, realizado_em: datetime) -> str:
    # Realizado = antes ou na data programada
    # Realizado Fora = após a data programada
    # Se data programada estiver vazia, assume Realizado
    if pd.isna(data_programada):
        return "Realizado"

    data_prog_dia = pd.to_datetime(data_programada).date()
    data_real_dia = realizado_em.date()

    if data_real_dia <= data_prog_dia:
        return "Realizado"
    return "Realizado Fora da Data de Programação"

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

@st.cache_data(show_spinner=False)
def geocode_endereco(texto: str):
    geolocator = Nominatim(user_agent="gestao_os_eletro_mrs", timeout=10)
    return geolocator.geocode(texto + ", Brasil")


@st.cache_data(show_spinner=False)
def reverse_geocode_coordenada(lat: float, lon: float) -> str:
    try:
        geolocator = Nominatim(user_agent="gestao_os_eletro_mrs", timeout=10)
        location = geolocator.reverse(
            (float(lat), float(lon)),
            exactly_one=True,
            language="pt-BR",
            addressdetails=True
        )

        if not location:
            return "GPS Local"

        raw = getattr(location, "raw", {}) or {}
        addr = raw.get("address", {}) or {}

        # Componentes principais
        rua = (
            addr.get("road")
            or addr.get("pedestrian")
            or addr.get("residential")
            or addr.get("footway")
            or addr.get("path")
            or ""
        ).strip()

        numero = (
            addr.get("house_number")
            or ""
        ).strip()

        bairro = (
            addr.get("suburb")
            or addr.get("neighbourhood")
            or addr.get("quarter")
            or ""
        ).strip()

        cidade = (
            addr.get("city")
            or addr.get("town")
            or addr.get("municipality")
            or addr.get("village")
            or ""
        ).strip()

        cep = (
            addr.get("postcode")
            or ""
        ).strip()

        partes = []

        if rua and numero:
            partes.append(f"{rua}, {numero}")
        elif rua:
            partes.append(rua)

        if bairro:
            partes.append(bairro)

        if cidade:
            partes.append(cidade)

        if cep:
            partes.append(cep)

        endereco_curto = ", ".join([p for p in partes if p])

        return endereco_curto if endereco_curto else "GPS Local"

    except Exception:
        return "GPS Local"

def tentar_gps_uma_vez():
    loc = get_geolocation()
    if not loc:
        return False, None, None, "Aguardando resposta do navegador…", None
    if isinstance(loc, dict) and "error" in loc:
        code = loc["error"].get("code")
        msg = loc["error"].get("message", "Erro desconhecido de geolocalização.")
        return False, None, None, f"GPS falhou (code {code}): {msg}", None
    if isinstance(loc, dict) and "coords" in loc:
        coords = loc.get("coords", {})
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        acc = coords.get("accuracy")
        if lat is not None and lon is not None:
            return True, float(lat), float(lon), "Localização obtida via GPS.", acc
    return False, None, None, "Não foi possível interpretar a resposta do GPS.", None
#endregion

#region SESSÃO 2.2 ===== Persistência (SQLite) =====

def upsert_baixa(os_id: str, status: str, realizado_em_str: str, coordenacao: str, concluido_por: str,
                 geolocalizacao_baixa: str = "", equipe: str = "",
                 data_inicio: str = "", hora_inicio: str = "",
                 data_fim: str = "", hora_fim: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO baixas (os, status, realizado_em, coordenacao, concluido_por,
                                geolocalizacao_baixa, equipe, data_inicio, hora_inicio,
                                data_fim, hora_fim)
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
        """, (str(os_id), str(status), str(realizado_em_str), str(coordenacao),
              str(concluido_por), str(geolocalizacao_baixa), str(equipe),
              str(data_inicio), str(hora_inicio), str(data_fim), str(hora_fim)))
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)


def carregar_baixas_df() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa FROM baixas", conn)
    finally:
        release_connection(conn)
    if df.empty:
        return df
    df["os"] = df["os"].astype(str)
    return df

#endregion

#region SESSÃO 2.2.1 ===== Supabase Storage (Evidências Fotográficas) =====
def upload_foto_supabase(arquivo_bytes: bytes, nome_arquivo: str) -> str:
    """Faz upload de uma foto para o Supabase Storage (bucket 'evidencias') e retorna a URL pública."""
    url_base = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    upload_url = f"{url_base}/storage/v1/object/evidencias/{nome_arquivo}"
    headers = {
        "Authorization": f"Bearer {chave}",
        "apikey": chave,
        "Content-Type": "image/jpeg",
        "x-upsert": "true"
    }
    resp = requests.post(upload_url, headers=headers, data=arquivo_bytes)
    if resp.status_code in (200, 201):
        return f"{url_base}/storage/v1/object/public/evidencias/{nome_arquivo}"
    else:
        raise Exception(f"Erro Supabase Storage ({resp.status_code}): {resp.text}")

def upsert_evidencia(ativo: str, atividade: str, foto_url: str, os_referencia: str, concluido_por: str, geolocalizacao: str):
    """Grava ou substitui a evidência fotográfica no banco Neon. Chave única = (ativo, atividade)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO evidencias (ativo, atividade, foto_url, os_referencia, concluido_por, geolocalizacao, data_upload)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (ativo, atividade) DO UPDATE SET
                foto_url = EXCLUDED.foto_url,
                os_referencia = EXCLUDED.os_referencia,
                concluido_por = EXCLUDED.concluido_por,
                geolocalizacao = EXCLUDED.geolocalizacao,
                data_upload = CURRENT_TIMESTAMP;
        """, (str(ativo), str(atividade), str(foto_url), str(os_referencia), str(concluido_por), str(geolocalizacao)))
        conn.commit()
        cur.close()
    finally:
        release_connection(conn)

def carregar_evidencias_df() -> pd.DataFrame:
    """Carrega todas as evidências do banco para exibição na Lista Detalhada."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT ativo, atividade, foto_url, os_referencia, data_upload FROM evidencias", conn)
    finally:
        release_connection(conn)
    return df

@st.cache_data(show_spinner=False, ttl=600)
def carregar_mapeamento_patios() -> dict:
    """Carrega o dicionário de mapeamento Ativo → Pátio do banco Neon."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT ativo_chave, patio FROM mapeamento_patios", conn)
    finally:
        release_connection(conn)
    if df.empty:
        return {}
    df["ativo_chave"] = df["ativo_chave"].astype(str).str.strip().str.upper()
    df["patio"] = df["patio"].astype(str).str.strip().str.upper()
    return dict(zip(df["ativo_chave"], df["patio"]))
#endregion

#region SESSÃO 2.3 ===== Export/Salvar Excel (MASTER) =====
def gerar_excel_sap_bytes(df_filtrado_atual: pd.DataFrame) -> bytes:
    # 1. Filtra apenas o que já foi executado
    df_concluidas = df_filtrado_atual[df_filtrado_atual["Status_norm"].isin(_status_prazo | _status_atraso)].copy()
    if df_concluidas.empty:
        return b""

    # 2. Busca no banco os horários reais e a EQUIPE
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
    finally:
        release_connection(conn)

    # 3. Junta os dados do filtro com os dados do banco
    df_sap = df_concluidas.merge(df_detalhes, left_on="Ordem servico", right_on="os", how="inner")

    # --- A MÁGICA DA MULTIPLICAÇÃO (EXPLODE) DE EQUIPE ---
    def montar_lista_equipe(row):
        principal = str(row["concluido_por"]).strip()
        eqp = str(row["equipe"]).strip()
        if eqp and eqp.upper() not in ("SOZINHO", "NAN", ""):
            co_exec = [u.strip() for u in eqp.split(",") if u.strip()]
            todos = [principal] + co_exec
        else:
            todos = [principal]
        return list(dict.fromkeys(todos))  # Remove duplicatas mantendo ordem

    df_sap["_lista_equipe"] = df_sap.apply(montar_lista_equipe, axis=1)
    df_sap_explodido = df_sap.explode("_lista_equipe").rename(columns={"_lista_equipe": "matricula_final"}).reset_index(drop=True)
    df_sap_explodido = df_sap_explodido.drop(columns=["_lista_equipe"], errors="ignore")
    # -----------------------------------------------------

    def calc_trab_real(h_ini, h_fim):
        try:
            t_ini = pd.to_datetime(h_ini, format='%H:%M:%S')
            t_fim = pd.to_datetime(h_fim, format='%H:%M:%S')
            diff = (t_fim - t_ini).total_seconds() / 60.0
            if diff < 0: diff += 24 * 60 
            h = int(diff // 60)
            m = int(diff % 60)
            return f"{h:02d},{m:02d}"
        except Exception:
            return ""

    def get_centro_trab(coord):
        c = str(coord).upper()
        if 'IPG' in c or 'PIAÇAGUERA' in c or 'PIACAGUERA' in c: return 'E.SP.IPG'
        return 'E.SP.IPA'

    def get_centro(coord):
        c = str(coord).upper()
        if 'IPG' in c or 'PIAÇAGUERA' in c or 'PIACAGUERA' in c: return 'CIPG'
        return 'CIPA'

# 4. Construção da Tabela Padrão SAP usando o DataFrame Explodido
    n = len(df_sap_explodido)
    sap_out = pd.DataFrame({
        'A': [""] * n,
        'Ordem': df_sap_explodido['Ordem servico'].values,
        'Operação': ["10"] * n,
        'D': [""] * n,
        'E': [""] * n,
        'F': [""] * n,
        'Trab. real': df_sap_explodido.apply(lambda r: calc_trab_real(r['hora_inicio'], r['hora_fim']), axis=1).values,
        'UN Medida 1': ["MIN"] * n,
        'I': [""] * n,
        'J': [""] * n,
        'K': [""] * n,
        'Centro de Trabalho': df_sap_explodido['coordenacao'].apply(get_centro_trab).values,
        'Centro': df_sap_explodido['coordenacao'].apply(get_centro).values,
        'N': [""] * n,
        'O': [""] * n,
        'P': [""] * n,
        'Matrícula': df_sap_explodido['matricula_final'].values,
        'R': [""] * n,
        'S': [""] * n,
        'UN Medida 2': ["MIN"] * n,
        'U': [""] * n,
        'V': [""] * n,
        'W': [""] * n,
        'X': [""] * n,
        'Data Inicio Real': df_sap_explodido['data_inicio'].astype(str).str.replace('/', '.').values,
        'Hora Inicio Real': df_sap_explodido['hora_inicio'].values,
        'Data Fim Real': df_sap_explodido['data_fim'].astype(str).str.replace('/', '.').values,
        'Hora Fim Real': df_sap_explodido['hora_fim'].values,
    })

    col_names = []
    for i, c in enumerate(sap_out.columns):
        if c in ['A', 'D', 'E', 'F', 'I', 'J', 'K', 'N', 'O', 'P', 'R', 'S', 'U', 'V', 'W', 'X']:
            col_names.append(" " * (i + 1))
        elif c == 'UN Medida 1' or c == 'UN Medida 2':
            col_names.append("UN Medida" + " " * i)
        else:
            col_names.append(c)
    sap_out.columns = col_names

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sap_out.to_excel(writer, index=False, sheet_name="Importacao_SAP")
    output.seek(0)
    
    return output.read()

#region SESSÃO 2.4 ===== Auxiliares: datas/turnos para gráficos gerenciais =====
def parse_datahora_realizado(valor):
    # Espera texto "dd/mm/aaaa hh:mm" ou vazio
    if pd.isna(valor):
        return pd.NaT
    s = str(valor).strip()
    if not s:
        return pd.NaT
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def classificar_turno(dt):
    # Turnos definidos pelo Julio:
    # 00:00–06:59 | 07:00–15:59 | 16:00–23:59
    if pd.isna(dt):
        return None
    h = int(dt.hour)
    if 0 <= h < 7:
        return "00h-07h"
    if 7 <= h < 16:
        return "07h-16h"
    return "16h-00h"
#endregion

#region SESSÃO 2.5 ===== Auxiliares da Sidebar: preparação e filtros =====
def preparar_df_visao(df_base: pd.DataFrame, filtro_visao: str) -> pd.DataFrame:
    df_visao = df_base.copy()

    if filtro_visao != "Todas":
        df_visao = df_visao[
            df_visao["Coordenacao"].str.contains(filtro_visao, case=False, na=False)
        ].copy()

    df_visao["Status_norm"] = df_visao["Status da Operação"].astype(str).str.strip().str.upper()
    df_visao["dt_realizado"] = df_visao["Data/Hora Realizado"].apply(parse_datahora_realizado)
    df_visao["Turno"] = df_visao["dt_realizado"].apply(classificar_turno)
    df_visao["dia_realizado"] = pd.to_datetime(df_visao["dt_realizado"], errors="coerce").dt.normalize()
    df_visao["dt_prog_filtro"] = pd.to_datetime(df_visao["Data inicial programada"], errors="coerce")
    df_visao["Turno_Filtro"] = df_visao["Turno"].fillna("Pendente (Sem Turno)")

    return df_visao

def aplicar_filtros_sidebar(
    df_visao: pd.DataFrame,
    patios_selecionados: list,
    classif_selecionadas: list,
    turnos_selecionados: list,
    start_date,
    end_date,
    status_sel: str
) -> pd.DataFrame:
    df_filtrado = df_visao[
        (df_visao["Patio"].isin(patios_selecionados)) &
        (df_visao["Classificacao"].isin(classif_selecionadas)) &
        (df_visao["Turno_Filtro"].isin(turnos_selecionados)) &
        (df_visao["dt_prog_filtro"].dt.date >= start_date) &
        (df_visao["dt_prog_filtro"].dt.date <= end_date)
    ].copy()

    if status_sel == "Todas Concluídas":
        df_filtrado = df_filtrado[
            df_filtrado["Status_norm"].isin(_status_prazo | _status_atraso)
        ]
    elif status_sel == "Concluídas no Prazo":
        df_filtrado = df_filtrado[
            df_filtrado["Status_norm"].isin(_status_prazo)
        ]
    elif status_sel == "Concluídas com Atraso":
        df_filtrado = df_filtrado[
            df_filtrado["Status_norm"].isin(_status_atraso)
        ]
    elif status_sel == "Pendentes":
        df_filtrado = df_filtrado[
            df_filtrado["Status_norm"].isin(_status_aberto)
        ]

    return df_filtrado
#endregion

#region SESSÃO 2.6 ===== Calendário mensal de demanda por pátio =====
import calendar as pycal
from datetime import date

@st.cache_data(show_spinner=False)
def _preparar_df_calendario(df_base_cal: pd.DataFrame) -> pd.DataFrame:
    if df_base_cal.empty:
        return pd.DataFrame()

    df = df_base_cal.copy()

    if "dt_prog_filtro" not in df.columns:
        df["dt_prog_filtro"] = pd.to_datetime(df["Data inicial programada"], errors="coerce")

    if "Status_norm" not in df.columns:
        df["Status_norm"] = df["Status da Operação"].astype(str).str.strip().str.upper()

    if "Nivel_Prioridade" not in df.columns:
        df["Nivel_Prioridade"] = 999

    df = df.dropna(subset=["dt_prog_filtro", "Patio"]).copy()
    if df.empty:
        return df

    df["Patio"] = df["Patio"].astype(str).str.strip().str.upper()
    df["dia_prog"] = pd.to_datetime(df["dt_prog_filtro"], errors="coerce").dt.date
    df["Nivel_Prioridade"] = pd.to_numeric(df["Nivel_Prioridade"], errors="coerce").fillna(999).astype(int)

    return df


@st.cache_data(show_spinner=False)
def montar_eventos_calendario_patios(
    df_base_cal: pd.DataFrame,
    ano: int,
    mes: int,
    max_patios_visiveis: int = 2,
) -> list[dict]:
    """
    Regras:
    - Vermelho: pátio com backlog vencido aberto em relação ao dia
    - Verde: pátio com demanda do dia ainda pendente
    - Azul: pátio com demanda do dia 100% executada
    - Carry-over: vencidas abertas continuam aparecendo nos dias seguintes
    - Sem repetir pátio no mesmo dia
    - Ordenação por menor Nivel_Prioridade
    - Exibe no máximo N siglas por dia + evento sintético '+N'
    """
    df = _preparar_df_calendario(df_base_cal)
    if df.empty:
        return []

    primeiro_dia = date(int(ano), int(mes), 1)
    ultimo_dia = date(int(ano), int(mes), pycal.monthrange(int(ano), int(mes))[1])

    dias_mes = pd.date_range(primeiro_dia, ultimo_dia, freq="D")
    eventos = []

    for dia_ts in dias_mes:
        dia = dia_ts.date()

        # 1) Backlog vencido aberto até o dia (carry-over)
        df_vencidas_abertas = df[
            (df["dia_prog"] < dia) &
            (df["Status_norm"].isin(_status_aberto))
        ].copy()

        # 2) Demanda programada no próprio dia
        df_hoje = df[df["dia_prog"] == dia].copy()

        patios_dia = []

        # Primeiro: vencidas abertas -> vermelho
        if not df_vencidas_abertas.empty:
            agg_venc = (
                df_vencidas_abertas.groupby("Patio", as_index=False)
                .agg(
                    ordem=("Nivel_Prioridade", "min"),
                    qtd_os=("Patio", "size")
                )
                .sort_values(["ordem", "Patio"])
            )

            for _, row in agg_venc.iterrows():
                patios_dia.append({
                    "patio": str(row["Patio"]),
                    "cor": "#FF4B4B",  # vermelho
                    "ordem": int(row["ordem"]),
                    "rank_status": 0
                })

        patios_ja_incluidos = {item["patio"] for item in patios_dia}

        # Depois: demanda do dia
        if not df_hoje.empty:
            for patio, grp in df_hoje.groupby("Patio"):
                if patio in patios_ja_incluidos:
                    continue

                ordem_patio = int(grp["Nivel_Prioridade"].min())
                todos_realizados = (~grp["Status_norm"].isin(_status_aberto)).all()

                patios_dia.append({
                    "patio": str(patio),
                    "cor": "#3B82F6" if todos_realizados else "#10B981",  # azul / verde
                    "ordem": ordem_patio,
                    "rank_status": 2 if todos_realizados else 1
                })

        if not patios_dia:
            continue

        patios_dia = sorted(patios_dia, key=lambda x: (x["rank_status"], x["ordem"], x["patio"]))

        patios_visiveis = patios_dia[:max_patios_visiveis]
        qtd_extra = max(0, len(patios_dia) - len(patios_visiveis))

        for idx, item in enumerate(patios_visiveis):
            eventos.append({
                "title": item["patio"],
                "start": dia.isoformat(),
                "allDay": True,
                "backgroundColor": item["cor"],
                "borderColor": item["cor"],
                "textColor": "#FFFFFF",
                "displayOrder": idx + 1,
            })

        if qtd_extra > 0:
            eventos.append({
                "title": f"+{qtd_extra}",
                "start": dia.isoformat(),
                "allDay": True,
                "backgroundColor": "#94A3B8",
                "borderColor": "#94A3B8",
                "textColor": "#FFFFFF",
                "displayOrder": 99,
            })

    return eventos


@st.cache_data(show_spinner=False)
def resumir_demanda_calendario(
    df_base_cal: pd.DataFrame,
    ano: int,
    mes: int,
    dia_ref: int | None = None
) -> dict:
    df = _preparar_df_calendario(df_base_cal)

    primeiro_dia = date(int(ano), int(mes), 1)
    ultimo_dia = date(int(ano), int(mes), pycal.monthrange(int(ano), int(mes))[1])

    if dia_ref is None:
        dia_ref = 1

    dia_ref = max(1, min(int(dia_ref), ultimo_dia.day))
    dia_atual_ref = date(int(ano), int(mes), int(dia_ref))

    if df.empty:
        return {
            "dia_ref": dia_atual_ref,
            "qtd_patios": 0,
            "total_os": 0,
            "patio_prioritario": "-",
            "serie_total_os_mes": [0] * ultimo_dia.day,
            "labels_mes": [f"{d:02d}" for d in range(1, ultimo_dia.day + 1)]
        }

    serie_total_os_mes = []
    labels_mes = []

    for d in pd.date_range(primeiro_dia, ultimo_dia, freq="D"):
        dia = d.date()

        backlog_vencido = df[
            (df["dia_prog"] < dia) &
            (df["Status_norm"].isin(_status_aberto))
        ].copy()

        demanda_dia = df[df["dia_prog"] == dia].copy()

        total_os_dia = len(backlog_vencido) + len(demanda_dia)
        serie_total_os_mes.append(int(total_os_dia))
        labels_mes.append(d.strftime("%d"))

    backlog_ref = df[
        (df["dia_prog"] < dia_atual_ref) &
        (df["Status_norm"].isin(_status_aberto))
    ].copy()

    demanda_ref = df[df["dia_prog"] == dia_atual_ref].copy()

    patio_resumo = {}

    if not backlog_ref.empty:
        for patio, grp in backlog_ref.groupby("Patio"):
            patio_resumo[patio] = {
                "ordem": int(grp["Nivel_Prioridade"].min()),
                "qtd_os": int(len(grp)),
                "rank_status": 0
            }

    if not demanda_ref.empty:
        for patio, grp in demanda_ref.groupby("Patio"):
            todos_realizados = (~grp["Status_norm"].isin(_status_aberto)).all()
            rank_status = 2 if todos_realizados else 1

            if patio in patio_resumo:
                patio_resumo[patio]["qtd_os"] += int(len(grp))
                patio_resumo[patio]["ordem"] = min(
                    patio_resumo[patio]["ordem"],
                    int(grp["Nivel_Prioridade"].min())
                )
            else:
                patio_resumo[patio] = {
                    "ordem": int(grp["Nivel_Prioridade"].min()),
                    "qtd_os": int(len(grp)),
                    "rank_status": rank_status
                }

    qtd_patios = len(patio_resumo)
    total_os = sum(v["qtd_os"] for v in patio_resumo.values())

    if patio_resumo:
        patio_prioritario = sorted(
            patio_resumo.items(),
            key=lambda kv: (kv[1]["rank_status"], kv[1]["ordem"], kv[0])
        )[0]
        patio_prioritario_txt = f"{patio_prioritario[0]} ➔ {patio_prioritario[1]['qtd_os']} OS"
    else:
        patio_prioritario_txt = "-"

    return {
        "dia_ref": dia_atual_ref,
        "qtd_patios": int(qtd_patios),
        "total_os": int(total_os),
        "patio_prioritario": patio_prioritario_txt,
        "serie_total_os_mes": serie_total_os_mes,
        "labels_mes": labels_mes
    }

@st.cache_data(show_spinner=False)
def resumir_conclusoes_por_turno_data(
    df_base_cal: pd.DataFrame,
    data_ref
) -> dict:
    if df_base_cal.empty:
        return {
            "labels": ["00h-07h", "07h-16h", "16h-00h"],
            "valores": [0, 0, 0],
            "titulo": "Quantidade de OS Concluídas",
            "subtitulo": "Sem dados"
        }

    df = df_base_cal.copy()

    if "dt_prog_filtro" not in df.columns:
        df["dt_prog_filtro"] = pd.to_datetime(df["Data inicial programada"], errors="coerce")

    if "dt_realizado" not in df.columns:
        df["dt_realizado"] = df["Data/Hora Realizado"].apply(parse_datahora_realizado)

    if "Turno" not in df.columns:
        df["Turno"] = df["dt_realizado"].apply(classificar_turno)

    if "Status_norm" not in df.columns:
        df["Status_norm"] = df["Status da Operação"].astype(str).str.strip().str.upper()

    data_ref = pd.to_datetime(data_ref).date()
    hoje_ref = datetime.now().date()

    df_realizadas = df[df["Status_norm"].isin(_status_prazo | _status_atraso)].copy()

    if df_realizadas.empty:
        return {
            "labels": ["00h-07h", "07h-16h", "16h-00h"],
            "valores": [0, 0, 0],
            "titulo": "Quantidade de OS Concluídas",
            "subtitulo": "Sem dados"
        }

    if data_ref <= hoje_ref:
        df_ref = df_realizadas[
            pd.to_datetime(df_realizadas["dt_realizado"], errors="coerce").dt.date == data_ref
        ].copy()
        subtitulo = f"Concluídas em {data_ref.strftime('%d/%m/%Y')}"
    else:
        df_ref = df_realizadas[
            (pd.to_datetime(df_realizadas["dt_prog_filtro"], errors="coerce").dt.date == data_ref) &
            (pd.to_datetime(df_realizadas["dt_realizado"], errors="coerce").dt.date < data_ref)
        ].copy()
        subtitulo = f"Antecipadas para {data_ref.strftime('%d/%m/%Y')}"

    ordem_turnos = ["00h-07h", "07h-16h", "16h-00h"]
    serie = df_ref.groupby("Turno").size() if not df_ref.empty else pd.Series(dtype=int)
    valores = [int(serie.get(t, 0)) for t in ordem_turnos]

    return {
        "labels": ordem_turnos,
        "valores": valores,
        "titulo": "Quantidade de OS Concluídas",
        "subtitulo": subtitulo
    }

#endregion
#endregion


#region SESSÃO 2.7 ===== Administração de Dados =====

def render_tela_admin():
    st.title("⚙️ Administração de Dados")
    st.markdown("Faça o upload da base de **OS Programadas** para atualizar o sistema central.")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        mes_ref = st.text_input("Mês de Referência (ex: Junho/2026)", placeholder="Mês/Ano")
    with col_up2:
        coord_upload = st.selectbox("Coordenação da Planilha", ["Paranapiacaba", "Piaçaguera"])
    
    arquivo_upload = st.file_uploader("Selecione a planilha Excel ou CSV", type=["csv", "xlsx"])
    
    if arquivo_upload is not None and mes_ref:
        if st.button("🚀 Processar e Salvar no Banco", use_container_width=True, type="primary"):
            
            escopo_user = st.session_state.get("escopo", "Todas")
            if escopo_user != "Todas" and escopo_user != coord_upload:
                st.error(f"⚠️ **ACESSO BLOQUEADO:** Seu perfil está restrito à coordenação **{escopo_user}**.")
                st.stop()

            with st.spinner("Lendo e processando dados..."):
                try:
                    if arquivo_upload.name.endswith('.csv'):
                        df = pd.read_csv(arquivo_upload, sep=';', encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(arquivo_upload)
                    
                    if "Ordem servico" not in df.columns:
                        st.error("❌ A coluna 'Ordem servico' não foi encontrada. Verifique o arquivo.")
                        return
                    
                    df = df.fillna("")
                    total_linhas_arquivo = len(df)
                    
                    def conversor_brasileiro(obj):
                        if isinstance(obj, (pd.Timestamp, datetime)):
                            return obj.strftime('%d/%m/%Y')
                        return str(obj)
                    
                    # --- FASE 1: Preparar registros em memória ---
                    barra = st.progress(0, text="Preparando dados...")
                    registros = []
                    for idx, (_, row) in enumerate(df.iterrows()):
                        os_num = str(row["Ordem servico"]).strip()
                        if os_num:
                            dados_json = json.dumps(row.to_dict(), default=conversor_brasileiro)
                            registros.append((os_num, mes_ref, coord_upload, dados_json))
                        if (idx + 1) % 200 == 0 or (idx + 1) == total_linhas_arquivo:
                            pct = min((idx + 1) / total_linhas_arquivo, 0.5)
                            barra.progress(pct, text=f"Preparando... {idx + 1}/{total_linhas_arquivo} linhas")
                    
                    # --- FASE 2: Gravar no banco em lotes ---
                    barra.progress(0.5, text="Gravando no banco de dados...")
                    conn = get_connection()
                    try:
                        cur = conn.cursor()
                        lote_size = 500
                        for i in range(0, len(registros), lote_size):
                            lote = registros[i:i + lote_size]
                            execute_values(
                                cur,
                                """
                                INSERT INTO os_programadas (os, mes_referencia, coordenacao, dados_completos)
                                VALUES %s
                                ON CONFLICT (os) DO UPDATE 
                                SET mes_referencia = EXCLUDED.mes_referencia,
                                    coordenacao = EXCLUDED.coordenacao,
                                    dados_completos = EXCLUDED.dados_completos,
                                    data_upload = CURRENT_TIMESTAMP
                                """,
                                lote,
                                page_size=lote_size
                            )
                            pct = min(0.5 + (i + len(lote)) / len(registros) * 0.5, 1.0)
                            barra.progress(pct, text=f"Gravando... {min(i + lote_size, len(registros))}/{len(registros)} registros")
                        
                        conn.commit()
                        cur.close()
                    finally:
                        release_connection(conn)

                    barra.progress(1.0, text="Concluído!")
                    st.success(f"✅ Sucesso! {len(registros)} de {total_linhas_arquivo} linhas foram processadas.")
                    st.cache_data.clear()
                    time.sleep(1.5)
                    st.rerun()
                    
                except Exception as e:

                    st.error(f"❌  Ocorreu um erro ao processar o arquivo: {e}")
    elif arquivo_upload is not None:
        st.warning("⚠️ Preencha o Mês e a Coordenação antes de processar.")

    # ==============================================
    # HISTÓRICO DE UPLOADS (aba recolhível)
    # ==============================================
    st.markdown("---")
    with st.expander("📋 Histórico de Uploads", expanded=False):
        perfil_user = st.session_state.get("perfil", "")
        escopo_user = st.session_state.get("escopo", "")
        
        # Define o filtro de visão baseado no perfil
        ver_tudo = perfil_user in ("Gerência",) or escopo_user == "Todas"
        
        conn = get_connection()
        try:
            if ver_tudo:
                query_hist = """
                    SELECT 
                        coordenacao AS "Coordenação",
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
                    SELECT 
                        coordenacao AS "Coordenação",
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
            # Formata a data para o padrão brasileiro
            df_hist["Último Upload"] = pd.to_datetime(df_hist["Último Upload"]).dt.strftime("%d/%m/%Y %H:%M")
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

    # ==============================================
    # UPLOAD DE MAPEAMENTO DE PÁTIOS
    # ==============================================
    st.markdown("---")
    with st.expander("🗺️ Mapeamento de Ativos → Pátios", expanded=False):
        st.markdown("Carregue a planilha **Relação_ativos_SP.xlsx** para atualizar o mapeamento de Ativos e Equipamentos para Pátios.")
        st.caption("A planilha deve ter as abas **Ativos_SP** (coluna A: Local de instalação, coluna K: Pátio) e **Equipamento_SP** (coluna A: Equipamento, coluna G: Pátio).")
        
        arquivo_mapa = st.file_uploader("Selecione a planilha de mapeamento", type=["xlsx"], key="upload_mapeamento_patios")
        
        if arquivo_mapa is not None:
            if st.button("🚀 Processar Mapeamento", use_container_width=True, type="primary"):
                with st.spinner("Processando mapeamento de pátios..."):
                    try:
                        xls = pd.ExcelFile(arquivo_mapa, engine="openpyxl")
                        registros = []
                        
                        # Aba Ativos_SP
                        if "Ativos_SP" in xls.sheet_names:
                            df_at = pd.read_excel(xls, sheet_name="Ativos_SP")
                            col_chave_at = df_at.columns[0]
                            col_patio_at = df_at.columns[10]
                            for _, row in df_at.iterrows():
                                chave = str(row[col_chave_at]).strip()
                                patio = str(row[col_patio_at]).strip()
                                if chave and patio and chave != "nan" and patio != "nan":
                                    registros.append((chave, patio, "Ativo"))
                        
                        # Aba Equipamento_SP (aceita ambos os nomes)
                        for nome_aba in ["Equipamento_SP", "Equipamentos_SP"]:
                            if nome_aba in xls.sheet_names:
                                df_eq = pd.read_excel(xls, sheet_name=nome_aba)
                                col_chave_eq = df_eq.columns[0]
                                col_patio_eq = df_eq.columns[6]
                                for _, row in df_eq.iterrows():
                                    chave = str(row[col_chave_eq]).strip()
                                    patio = str(row[col_patio_eq]).strip()
                                    if chave and patio and chave != "nan" and patio != "nan":
                                        registros.append((chave, patio, "Equipamento"))
                                break
                        
                        if not registros:
                            st.error("❌ Nenhum registro válido encontrado. Verifique a estrutura da planilha.")
                        else:
                            conn = get_connection()
                            try:
                                cur = conn.cursor()
                                lote_size = 500
                                barra = st.progress(0, text="Gravando mapeamento...")
                                for i in range(0, len(registros), lote_size):
                                    lote = registros[i:i + lote_size]
                                    execute_values(
                                        cur,
                                        """
                                        INSERT INTO mapeamento_patios (ativo_chave, patio, tipo)
                                        VALUES %s
                                        ON CONFLICT (ativo_chave) DO UPDATE SET
                                            patio = EXCLUDED.patio,
                                            tipo = EXCLUDED.tipo
                                        """,
                                        lote,
                                        page_size=lote_size
                                    )
                                    pct = min((i + len(lote)) / len(registros), 1.0)
                                    barra.progress(pct, text=f"Gravando... {min(i + lote_size, len(registros))}/{len(registros)}")
                                conn.commit()
                                cur.close()
                            finally:
                                release_connection(conn)
                            
                            barra.progress(1.0, text="Concluído!")
                            st.success(f"✅ Mapeamento atualizado com {len(registros)} registros!")
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao processar: {e}")
        
        # Mostrar status atual do mapeamento
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT patio) FROM mapeamento_patios")
            row_map = cur.fetchone()
            cur.close()
        finally:
            release_connection(conn)
        
        if row_map and row_map[0] > 0:
            st.info(f"📊 **Mapeamento atual:** {row_map[0]:,} ativos/equipamentos → {row_map[1]} pátios".replace(",", "."))
        else:
            st.warning("⚠️ Mapeamento vazio. Faça o upload da planilha para ativar a resolução inteligente de pátios.")

    # --- SESSÃO DE EXPORTAÇÃO SAP ---
    if "Exportar SAP" in st.session_state.get("governanca", ""):
        st.markdown("---")
        st.subheader("⬇️ Exportação SAP")
        st.markdown("Gere o arquivo consolidado com os apontamentos de campo para importação no SAP.")
        with st.spinner("Preparando base de dados para exportação..."):
            df_bruto = carregar_base_sem_overlay(
                usar_sim=False, qtd_sim=0, seed_sim=0,
                escopo_usuario=st.session_state.get("escopo", "Todas"),
                etl_version=ETL_VERSION
            )
            df_completo = aplicar_overlay_baixas(
                df_base_bruto=df_bruto,
                escopo_usuario=st.session_state.get("escopo", "Todas"),
                baixas_mtime=time.time()
            )
            if not df_completo.empty:
                df_completo["Status_norm"] = df_completo["Status da Operação"].astype(str).str.strip().str.upper()
                tem_concluida = df_completo["Status_norm"].isin(_status_prazo | _status_atraso).any()
                if tem_concluida:
                    arquivo_sap = gerar_excel_sap_bytes(df_completo)
                    if arquivo_sap:
                        st.download_button(
                            label="⬇️ Gerar Arquivo SAP (Massa)",
                            data=arquivo_sap,
                            file_name=f"Baixa_Massa_SAP_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=False,
                            type="primary"
                        )
                else:
                    st.info("⚠️ Nenhuma OS concluída encontrada para exportação no momento.")
            else:
                st.warning("A base de dados central está vazia.")
#endregion
#endregion

#region SESSÃO 3: Banco de Coordenadas Fixo

#region SESSÃO 3.1 Coordenadas Fixas
COORDENADAS_FIXAS = {
    "FPI": [-23.444413, -46.309269],
    "IAB": [-23.521338, -46.688570],
    "ICG": [-23.767863, -46.343114],
    "ICP": [-23.658495, -46.490753],
    "ICR": [-23.640310, -46.323992],
    "IEF": [-23.477809, -46.360984],
    "IES": [-23.545441, -46.603648],
    "IIP": [-23.564977, -46.604896],
    "ILA": [-23.520217, -46.698082],
    "IMO": [-23.557803, -46.608382],
    "IOF": [-23.658579, -46.338538],
    "IPA": [-23.774399, -46.306769],
    "IPG": [-23.847950, -46.370812],
    "IPR": [-23.537749, -46.625522],
    "IRG": [-23.736705, -46.382241],
    "IRP": [-23.713578, -46.414862],
    "IRS": [-23.828162, -46.363101],
    "ISA": [-23.647553, -46.531007],
    "ISC": [-23.613874, -46.558834],
    "ISL": [-23.752383, -46.389262],
    "ISU": [-23.551210, -46.288671],
    "IUT": [-23.624864, -46.544716],
    "OAR": [-23.500419, -46.339111],
    "OBF": [-23.525591, -46.666726],
    "OBR": [-23.545397, -46.616293],
    "OCE": [-23.484980, -46.481471],
    "OCV": [-23.525061, -46.333701],
    "OEG": [-23.498082, -46.519759],
    "OET": [-23.510887, -46.552273],
    "OGP": [-23.691962, -46.448784],
    "OIC": [-23.479040, -46.367395],
    "OIT": [-23.493970, -46.401392],
    "OLU": [-23.535423, -46.634503],
    "OMA": [-23.667910, -46.462083],
    "OMP": [-23.490530, -46.443668],
    "OPS": [-23.637494, -46.537198],
    "OSU": [-23.534010, -46.308025],
    "OTA": [-23.591863, -46.590075],
    "OTT": [-23.539844, -46.575501],
    "IAA": [-23.862936, -46.398189],
    "IJN": [-23.195297, -46.870829],
    "ZPD": [-22.363436, -48.711002],

    # ✅ CORRIGIDO: PADRÃO UPPER PARA EVITAR MATCH ERROR
    "Sede IPA": [-23.767355, -46.344117],
    "Sede IPG": [-23.850772, -46.371760]
}
#endregion

#region SESSÃO 3.2 Continuação do código da função de obtenção da base padrão do usuário
def obter_base_padrao_usuario():
    username = str(st.session_state.get("username", "")).strip()
    escopo = str(st.session_state.get("escopo", "")).strip()

    # Mapeamento ajustado para conversar com os nós reais da malha
    mapa_normalizacao = {
        "Paranapiacaba": ("IPA", "Sede IPA"),
        "Piaçaguera": ("IPG", "Sede IPG"),
        "Todas": ("IPA", "Sede Padrão (IPA)"),
        "ICG": ("ICG", "Campo Grande (ICG)"),
        "IPA": ("IPA", "Sede IPA"),
        "IPG": ("IPG", "Base IPG"),
        "SEDE IPA": ("IPA", "Sede IPA"),
        "SEDE IPG": ("IPG", "Sede IPG"),
    }

    valor_base = None

    # Busca no banco de usuários
    if username:
        conn = None
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT coordenacao_padrao FROM usuarios WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()
            cur.close()
            if row and row[0]:
                valor_base = str(row[0]).strip()
        except Exception:
            valor_base = None
        finally:
            if conn is not None:
                release_connection(conn)

    # Fallback para o escopo
    if not valor_base:
        valor_base = escopo

    valor_base = str(valor_base).strip()
    valor_base_upper = valor_base.upper()

    # Tradução final
    if valor_base in mapa_normalizacao:
        chave_coord, nome_exibicao = mapa_normalizacao[valor_base]
    elif valor_base_upper in mapa_normalizacao:
        chave_coord, nome_exibicao = mapa_normalizacao[valor_base_upper]
    else:
        chave_coord, nome_exibicao = ("IPA", "Base Padrão (IPA)")

    # Busca coordenada segura
    coord = COORDENADAS_FIXAS.get(chave_coord, COORDENADAS_FIXAS["IPA"])
    lat, lon = coord
    return float(lat), float(lon), nome_exibicao
#endregion
#endregion

#region SESSÃO 4: ETL (Carregamento e Tratamento)
# ==========================================

ETL_VERSION = "v6_leitura_crua_status_avancado"

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
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes no Excel: {', '.join(missing)}")

    df["ATIVO_CAN"] = df[col_ativo].astype(str).str.strip()
    df["ATIVIDADE_CAN"] = df[col_atividade].astype(str).str.strip()
    df["PRIORIDADE_CAN"] = df[col_prioridade].astype(str).str.strip()
    df["HXH_CAN"] = pd.to_numeric(df[col_hxh], errors="coerce").fillna(0) if col_hxh else 0.0
    
    # --- RESOLUÇÃO INTELIGENTE DE PÁTIO (lookup + scan + fallback) ---
    _mapa_patios = carregar_mapeamento_patios()
    _patios_validos = set(COORDENADAS_FIXAS.keys())

    def _resolver_patio(ativo_str: str) -> str:
        ativo_upper = str(ativo_str).strip().upper()

        # 1) Busca exata no mapeamento do banco
        if _mapa_patios and ativo_upper in _mapa_patios:
            return _mapa_patios[ativo_upper]

        # 2) Tenta as 3 primeiras letras
        prefixo = ativo_upper[:3]
        if prefixo in _patios_validos:
            return prefixo

        # 3) Scan: procura qualquer pátio válido dentro do texto do ativo
        for patio_candidato in sorted(_patios_validos, key=len, reverse=True):
            if patio_candidato in ativo_upper:
                return patio_candidato

        # 4) Nada encontrado
        return "N/D"

    df["PATIO_CAN"] = df["ATIVO_CAN"].apply(_resolver_patio)

    df["DATA_PROG_CAN"] = df[col_data_prog].apply(parse_data_programada)
    df["DESC_LONGA_CAN"] = df[col_desc].astype(str).str.strip() if col_desc else ""

    df["Classificacao"] = df["ATIVIDADE_CAN"].apply(classificar_atividade)
    crit = df["PRIORIDADE_CAN"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]
    df["Nivel_Prioridade"] = df.apply(lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]), axis=1)

    hoje_data = datetime.now().date()
    def definir_status_cru(row):
        st_atual = str(row[col_status]).strip().upper() if pd.notna(row[col_status]) and col_status else ""
        
        if "REALIZADO" in st_atual:
            if "FORA" in st_atual or "ATRASO" in st_atual:
                return "Realizado Fora da Data de Programação"
            return "Realizado"
        
        dp = row["DATA_PROG_CAN"]
        if pd.isna(dp):
            return "Pendente"
        
        if dp.date() >= hoje_data:
            return "Pendente"
        else:
            return "Atrasado"

    df["STATUS_CAN"] = df.apply(definir_status_cru, axis=1)

    df_out = pd.DataFrame({
        "Ordem servico": df[col_os].astype(str).str.strip(),
        "Patio": df["PATIO_CAN"],
        "Ativo": df["ATIVO_CAN"],
        "Atividade ativo": df["ATIVIDADE_CAN"],
        "Criticidade": df["Criticidade"],
        "Classificacao": df["Classificacao"],
        "Descrição Longa": df["DESC_LONGA_CAN"],
        "Data inicial programada": df["DATA_PROG_CAN"],
        "Status da Operação": df["STATUS_CAN"],
        "Data/Hora Realizado": "",
        "Concluído por": "",  
        "Hxh Plano": df["HXH_CAN"],
        "Criticidade_rank": df["Criticidade_rank"],
        "Nivel_Prioridade": df["Nivel_Prioridade"],
    })

    return df_out

@st.cache_data
def auto_detect_and_treat(path_ou_bytes):
    if isinstance(path_ou_bytes, bytes):
        df_raw = pd.read_excel(io.BytesIO(path_ou_bytes), engine="openpyxl", header=None)
    else:
        df_raw = pd.read_excel(path_ou_bytes, engine="openpyxl", header=None)
        
    df_raw = df_raw.dropna(how='all')
    df_raw = df_raw.dropna(axis=1, how='all')
    
    if df_raw.empty:
        raise ValueError("O arquivo Excel está completamente sem dados.")
        
    df_raw.columns = df_raw.iloc[0]
    df_tratado = df_raw[1:].reset_index(drop=True)
    return tratar_df_os(df_tratado)

@st.cache_data
def carregar_excel_por_bytes(excel_bytes: bytes, etl_version: str):
    return auto_detect_and_treat(excel_bytes)

@st.cache_data
def carregar_excel_por_path(path_excel: str, etl_version: str):
    return auto_detect_and_treat(path_excel)

@st.cache_data(show_spinner=False)
def carregar_base_sem_overlay(
    usar_sim: bool,
    qtd_sim: int,
    seed_sim: int,
    escopo_usuario: str,
    etl_version: str
) -> pd.DataFrame:
    if usar_sim:
        pct_p = st.session_state.get("sim_pct_pendente", 45)
        pct_ok = st.session_state.get("sim_pct_prazo", 40)
        pct_a = st.session_state.get("sim_pct_atraso", 15)
        return gerar_base_simulada(qtd=qtd_sim, seed=seed_sim, pct_p=pct_p, pct_ok=pct_ok, pct_a=pct_a)

    # 1. Conecta ao Neon e puxa os dados salvos pelo Admin/Assistente
    conn = get_connection()
    try:
        df_raw_db = pd.read_sql_query("SELECT coordenacao, dados_completos FROM os_programadas", conn)
    except Exception as e:
        df_raw_db = pd.DataFrame()
    finally:
        release_connection(conn)

    if df_raw_db.empty:
        return pd.DataFrame()

    dfs_tratados = []
    
    # 2. Agrupa por coordenação e remonta o formato Excel a partir do JSON do banco
    for coord, group in df_raw_db.groupby("coordenacao"):
        lista_linhas = []
        for _, row in group.iterrows():
            dados = row["dados_completos"]
            if isinstance(dados, str):
                dados = json.loads(dados)
            lista_linhas.append(dados)
            
        if lista_linhas:
            df_bruto_coord = pd.DataFrame(lista_linhas)
            try:
                df_tratado_coord = tratar_df_os(df_bruto_coord)
                df_tratado_coord["Coordenacao"] = coord
                dfs_tratados.append(df_tratado_coord)
            except Exception as e:
                import logging
                logging.warning(f"[ETL] Erro ao tratar coordenação '{coord}': {e}")

    if not dfs_tratados:
        return pd.DataFrame()

    df_base_final = pd.concat(dfs_tratados, ignore_index=True)

    # 4. Aplica o filtro de escopo de quem está logado
    if escopo_usuario != "Todas":
        df_base_final = df_base_final[
            df_base_final["Coordenacao"].str.contains(escopo_usuario, case=False, na=False)
        ]

    return df_base_final

@st.cache_data(show_spinner=False)
def aplicar_overlay_baixas(df_base_bruto: pd.DataFrame, escopo_usuario: str, baixas_mtime: float) -> pd.DataFrame:
    df_base = df_base_bruto.copy()
    if df_base.empty: return df_base

    # Correção Ponto 4: Força qualquer status vazio ou nulo a virar "Pendente" antes do cruzamento
    if "Status da Operação" in df_base.columns:
        df_base["Status da Operação"] = df_base["Status da Operação"].replace(["", "nan", "NaN", "None"], "Pendente")

    df_baixas = carregar_baixas_df()
    if df_baixas.empty: return df_base

    df_base["Ordem servico"] = df_base["Ordem servico"].astype(str)

    if escopo_usuario != "Todas":
        df_baixas = df_baixas[df_baixas["coordenacao"].str.contains(escopo_usuario, case=False, na=False)]

    # Correção Ponto 3: Incluindo a geolocalização no cruzamento
    colunas_overlay = ["Status da Operação", "Data/Hora Realizado", "Concluído por", "Geolocalização de Baixa"]
    for col in colunas_overlay:
        if col not in df_base.columns: df_base[col] = ""

    df_baixas = df_baixas.rename(columns={
        "os": "Ordem servico", "status": "Status da Operação", 
        "realizado_em": "Data/Hora Realizado", "concluido_por": "Concluído por",
        "geolocalizacao_baixa": "Geolocalização de Baixa"
    })

    df_base = df_base.merge(
        df_baixas[["Ordem servico"] + colunas_overlay],
        on="Ordem servico", how="left", suffixes=("", "_baixado")
    )

    for col in colunas_overlay:
        df_base[col] = np.where(
            df_base[f"{col}_baixado"].notna() & (df_base[f"{col}_baixado"] != ""),
            df_base[f"{col}_baixado"],
            df_base[col]
        )
        df_base.drop(columns=[f"{col}_baixado"], inplace=True)

    return df_base
#endregion

#region SESSÃO EXTRA: Simulação de dados (APENAS TESTE - remover depois)
# ==========================================
# SESSÃO EXTRA: Simulação de dados (APENAS TESTE - remover depois)
# ==========================================

#region SESSÃO EXTRA: Gerador de base simulada (para testar KPIs e gráficos)
def gerar_base_simulada(qtd: int = 800, seed: int = 42, pct_p: int = 45, pct_ok: int = 40, pct_a: int = 15) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    patios = ["IAA", "IEF", "OLU", "IPA", "IRS", "IPG", "ICG", "IRG", "IOF", "ISU", "ILA", "IJN", "ZPD", "IIP"]
    prioridades = ["1-Muito Alta", "2-Alta", "3-Média", "4-Baixa"]
    prob_prio = [0.18, 0.32, 0.30, 0.20]
    atividades = ["EE_INS_SEG_C_I_MAQ CHAVE MOLA_1800", "EE_MAN_CONF_C_I_CANALETA SUBESTACAO_0720", "EE_INS_CONF_S_I_BATERIAS_0360"]
    prob_ativ = [0.35, 0.30, 0.35]

    # Normaliza as porcentagens recebidas da Sidebar
    total_pct = pct_p + pct_ok + pct_a
    if total_pct == 0: prob_status = [0.45, 0.40, 0.15]
    else: prob_status = [pct_p / total_pct, pct_ok / total_pct, pct_a / total_pct]

    status_list = ["Não Realizado", "Realizado", "Realizado Fora da Data de Programação"]

    hoje = datetime.now()
    dias_atras = rng.integers(0, 30, size=qtd)
    data_prog = [hoje - pd.Timedelta(days=int(d)) for d in dias_atras]
    data_prog = pd.to_datetime(data_prog).normalize()

    df = pd.DataFrame({
        "Ordem servico": [f"OS-{100000+i}" for i in range(qtd)],
        "Patio": rng.choice(patios, size=qtd),
        "Ativo": [f"{rng.choice(patios)}-ATV-{i:04d}" for i in range(qtd)],
        "Atividade ativo": rng.choice(atividades, size=qtd, p=prob_ativ),
        "Prioridade": rng.choice(prioridades, size=qtd, p=prob_prio),
        "Hxh Plano": np.round(rng.uniform(0.5, 8.0, size=qtd), 1),
        "Data inicial programada": data_prog,
        "Coordenacao": rng.choice(["Paranapiacaba", "Piaçaguera"], size=qtd)
    })

    df["Classificacao"] = df["Atividade ativo"].apply(classificar_atividade)
    crit = df["Prioridade"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]
    df["Nivel_Prioridade"] = df.apply(lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]), axis=1)
    df["Desc_Prioridade"] = df["Classificacao"] + " | " + df["Criticidade"]

    df["Status da Operação"] = rng.choice(status_list, size=qtd, p=prob_status)
    df["Data/Hora Realizado"] = ""

    # --- MOCK: CRIA DADOS DE CAMPO PARA ALIMENTAR A GOVERNANÇA ---
    tecnicos_mock = ["Julio Paz (Sim)", "Carlos Silva (Sim)", "Ana Souza (Sim)", "Roberto Gomes (Sim)"]
    baixas_sim = []

    for i in range(qtd):
        stt = df.at[i, "Status da Operação"]
        if stt == "Não Realizado": continue

        prog = pd.to_datetime(df.at[i, "Data inicial programada"])
        turno = rng.choice(["00h-07h", "07h-16h", "16h-00h"], p=[0.15, 0.60, 0.25])

        if turno == "00h-07h": hh = int(rng.integers(0, 7))
        elif turno == "07h-16h": hh = int(rng.integers(7, 16))
            
        else: hh = int(rng.integers(16, 24))
        mm = int(rng.integers(0, 60))

        if stt == "Realizado":
            delta = int(rng.integers(0, 4))
            real_date = (prog - pd.Timedelta(days=delta)).to_pydatetime()
        else:
            delta = int(rng.integers(1, 11))
            real_date = (prog + pd.Timedelta(days=delta)).to_pydatetime()

        real_dt = real_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
        df.at[i, "Data/Hora Realizado"] = formatar_dt_br(real_dt)

        # Gera Horários de Início e Fim da Baixa
        duracao_mins = int(rng.integers(20, 240))
        ini_dt = real_dt - pd.Timedelta(minutes=duracao_mins)
        tec = rng.choice(tecnicos_mock)
            
        # Simula Fraude de GPS para pegar na Auditoria (10% de chance)
        gps_str = f"Lat: -23.{rng.integers(100,999)}, Lon: -46.{rng.integers(100,999)}"
        if rng.random() < 0.1: gps_str = "Sede IPA (Lat: -23.767, Lon: -46.344)"

        baixas_sim.append({
            "os": df.at[i, "Ordem servico"], "status": stt, "realizado_em": formatar_dt_br(real_dt),
            "coordenacao": df.at[i, "Coordenacao"], "concluido_por": tec, "geolocalizacao_baixa": gps_str,
            "equipe": "", "data_inicio": ini_dt.strftime("%d/%m/%Y"), "hora_inicio": ini_dt.strftime("%H:%M:%S"),
            "data_fim": real_dt.strftime("%d/%m/%Y"), "hora_fim": real_dt.strftime("%H:%M:%S")
        })

    # Armazena logs fakes na sessão para não poluir o banco de dados real
    st.session_state["df_baixas_sim"] = pd.DataFrame(baixas_sim)

    logs_sim = []
    for tec in tecnicos_mock:
        for dia in pd.date_range(end=datetime.now(), periods=15):
            login_dt = dia.replace(hour=int(rng.integers(6,8)), minute=int(rng.integers(0,59)))
            logs_sim.append({"username": tec, "data_hora_login": login_dt})
    st.session_state["df_logs_sim"] = pd.DataFrame(logs_sim)

    return df
#endregion

#region SESSÃO EXTRA: Controle na Sidebar
_DEV_MODE = os.getenv("DEV_MODE", "0") == "1"

if _DEV_MODE:
    def simulacao_sidebar():
        st.sidebar.header("🧪 Simulação (Teste)")
        usar_sim = st.sidebar.checkbox("Usar dados simulados (teste KPIs)", value=False)

        if not usar_sim:
            return False, None

        qtd_sim = st.sidebar.slider("Quantidade de OS simuladas", 100, 4000, 1200, 100)
        seed_sim = st.sidebar.number_input("Seed (repete os mesmos dados)", min_value=1, max_value=999999, value=42, step=1)

        df_sim = gerar_base_simulada(qtd=int(qtd_sim), seed=int(seed_sim))
        st.sidebar.info("✅ Simulação ativa. Excel real NÃO será carregado.")
        return True, df_sim
#endregion
#endregion

#region SESSÃO 5: Sidebar, Navegação, Carga e Filtro

#region SESSÃO 5.1: Identidade visual, navegação e escopo
# 5.1.1 CSS / identidade visual
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #1A202C !important; 
    }
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] h4, [data-testid="stSidebar"] h5, [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] small, [data-testid="stSidebar"] caption {
        color: #F1F5F9 !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 10px 16px !important;
        background-color: transparent !important;
        border-radius: 8px !important;
        margin-bottom: 6px !important;
        transition: all 0.2s ease-in-out !important;
        cursor: pointer !important;
        color: #CBD5E1 !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #FFFFFF !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background-color: rgba(255, 75, 75, 0.2) !important; 
        border-left: 4px solid #FF4B4B !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
        font-weight: bold !important;
        color: #FFFFFF !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox label p, 
    [data-testid="stSidebar"] .stMultiSelect label p,
    [data-testid="stSidebar"] .stDateInput label p {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
        margin-bottom: 4px;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: #FF4B4B !important;
        color: white !important;
        border-radius: 6px !important;
    }
    
    [data-testid="stSidebar"] div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] div[data-baseweb="input"] > div,
    [data-testid="stSidebar"] div[data-baseweb="base-input"] > input {
        background-color: #333D4E !important;
        border-color: #475569 !important;
        border-radius: 6px !important;
        color: white !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] span,
    [data-testid="stSidebar"] div[data-baseweb="input"] input {
        color: white !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stExpander"] details {
        border: 1px solid #FF4B4B !important;
        border-radius: 8px !important;
        overflow: hidden;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background-color: #FF4B4B !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p {
        color: #FFFFFF !important;
        font-weight: 800 !important;
        font-size: 16px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] svg {
        fill: #FFFFFF !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background-color: #1A202C !important;
        padding-top: 15px !important;
    }
    
    [data-testid="stSidebar"] button {
        background-color: #333D4E !important;
        color: #FFFFFF !important;
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
        transition: all 0.2s ease-in-out;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #475569 !important;
        border-color: #cbd5e1 !important;
        color: #FFFFFF !important;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(255, 75, 75, 0.15) !important;
        border-radius: 6px 6px 0px 0px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p {
        font-weight: bold !important;
    }
    button[data-baseweb="tab"]:hover {
        background-color: rgba(255, 75, 75, 0.05) !important;
        border-radius: 6px 6px 0px 0px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 5.1.2 Logotipo
st.sidebar.image("logo_mrs.png", use_container_width=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

# 5.1.3 Navegação Inteligente (Baseada na Governança)
st.sidebar.markdown("### 🧭 Navegação")

if "tela_atual" not in st.session_state:
    st.session_state["tela_atual"] = "dashboard"

gov_usuario = st.session_state.get("governanca", "")

# Cria os botões dependendo do que o usuário tem acesso
col_nav1, col_nav2 = st.sidebar.columns(2)
with col_nav1:
    if "Painel Gerencial" in gov_usuario or "Mapa de Campo" in gov_usuario:
        if st.button("📊 Painel", use_container_width=True): 
            st.session_state["tela_atual"] = "dashboard"
            st.rerun()
with col_nav2:
    if "Upload de Dados" in gov_usuario:
        if st.button("⚙️ Dados", use_container_width=True): 
            st.session_state["tela_atual"] = "admin"
            st.rerun()

# Botão exclusivo para liderança (CORRIGIDO PARA A SIDEBAR)
if "Gestão de Usuários" in gov_usuario or "Exportar SAP" in gov_usuario:
    if st.sidebar.button("🛡️ Governança (Auditoria)", use_container_width=True): 
        st.session_state["tela_atual"] = "governanca"
        st.rerun()

if st.session_state.get("tela_atual") == "admin":
    render_tela_admin()
    st.stop()
    
# --- DEFINIÇÃO DO FILTRO DE VISÃO ---
if "Painel Gerencial" in gov_usuario:
    visao_selecionada = st.sidebar.radio(
        "Selecione a Visão:", ["Gerência", "Paranapiacaba", "Piaçaguera"], 
        label_visibility="collapsed", key="radio_visao_gerencial"
    )
    filtro_visao = "Todas" if visao_selecionada == "Gerência" else visao_selecionada
else:
    filtro_visao = st.session_state.get("escopo", "Todas")
    st.sidebar.info(f"Visão Restrita: {filtro_visao}")
# -------------------------------------------------------

#region SESSÃO 5.2: Carregamento da base operacional
usar_sim = st.session_state.get("chk_sim", False)
qtd_sim = st.session_state.get("qtd_sim", 1200)
seed_sim = st.session_state.get("seed_sim", 42)


# Gera um hash baseado na quantidade real de baixas (só muda quando há novas baixas)
def _hash_baixas():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MAX(os) FROM baixas")
        row = cur.fetchone()
        cur.close()
        return f"{row[0]}_{row[1]}"
    finally:
        release_connection(conn)

baixas_mtime = _hash_baixas()

df_base_bruto = carregar_base_sem_overlay(
    usar_sim=usar_sim, qtd_sim=int(qtd_sim), seed_sim=int(seed_sim),
    escopo_usuario=st.session_state["escopo"],
    etl_version=ETL_VERSION
)

df_base = aplicar_overlay_baixas(
    df_base_bruto=df_base_bruto,
    escopo_usuario=st.session_state["escopo"],
    baixas_mtime=baixas_mtime   # ← agora só invalida quando o banco muda de fato
)

st.session_state["df_os"] = df_base
df_visao = preparar_df_visao(df_base, filtro_visao)
#endregion

#region SESSÃO 5.3: Filtros da sidebar
st.sidebar.markdown("### 📊 Filtros")

valid_dates = df_visao["dt_prog_filtro"].dropna()

if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()
else:
    min_date = datetime.now().date() - pd.Timedelta(days=30)
    max_date = datetime.now().date()

if st.session_state["perfil"] != "Técnico":
    data_selecionada = st.sidebar.date_input(
        "Período de Programação",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"  # <--- Essa linha mágica resolve a exibição visual!
    )

    if isinstance(data_selecionada, tuple):
        if len(data_selecionada) == 2:
            start_date, end_date = data_selecionada
        else:
            start_date = data_selecionada[0]
            end_date = data_selecionada[0]
    else:
        start_date = data_selecionada
        end_date = data_selecionada

    lista_patios = sorted(df_visao["Patio"].dropna().astype(str).unique().tolist())
    patios_selecionados = st.sidebar.multiselect("Pátio", lista_patios, default=lista_patios)

    classif_selecionadas = st.sidebar.multiselect(
        "Classificação",
        ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"],
        default=["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
    )

    lista_turnos = ["00h-07h", "07h-16h", "16h-00h", "Pendente (Sem Turno)"]
    turnos_selecionados = st.sidebar.multiselect("Turno", lista_turnos, default=lista_turnos)

    status_sel = st.sidebar.selectbox(
        "Status da OS",
        ["Todos", "Todas Concluídas", "Concluídas no Prazo", "Concluídas com Atraso", "Pendentes", "Atrasado"]
    )
else:
    st.sidebar.info("💡 Filtros automáticos aplicados de acordo com o seu escopo operacional de campo.")
    start_date = min_date
    end_date = max_date
    patios_selecionados = sorted(df_visao["Patio"].dropna().astype(str).unique().tolist())
    classif_selecionadas = ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
    turnos_selecionados = ["00h-07h", "07h-16h", "16h-00h", "Pendente (Sem Turno)"]
    status_sel = "Todos"

df_filtrado = aplicar_filtros_sidebar(
    df_visao=df_visao,
    patios_selecionados=patios_selecionados,
    classif_selecionadas=classif_selecionadas,
    turnos_selecionados=turnos_selecionados,
    start_date=start_date,
    end_date=end_date,
    status_sel=status_sel
)
#endregion
#endregion
#endregion

#region SESSÃO 6: Sistema, dados e gestão de usuários
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
            if st.button("🔄 Recarregar dados (ETL)", use_container_width=True):
                st.cache_data.clear(); st.rerun()

        st.markdown("<div style='background-color: #FF4B4B; color: #FFFFFF; font-weight: bold; text-align: center; padding: 8px; border-radius: 6px; margin-top: 15px; margin-bottom: 10px;'>Gestão de Usuários</div>", unsafe_allow_html=True)

        if "msg_sucesso_user" in st.session_state:
            st.success(st.session_state["msg_sucesso_user"])
            del st.session_state["msg_sucesso_user"]

        def sedes_por_escopo(escopo: str):
            if escopo == "Paranapiacaba": return ["Sede IPA"]
            elif escopo == "Piaçaguera": return ["Sede IPG"]
            return ["Sede IPA", "Sede IPG"]

        with st.form("form_novo_user", clear_on_submit=True):
            n_user = st.text_input("Login (Nova conta)", key="novo_user_login")
            n_perf = st.selectbox("Perfil", ["Técnico", "Assistente", "Coordenador", "Gerência"], key="novo_user_perfil")
            n_esco = st.selectbox("Escopo (Base)", ["Paranapiacaba", "Piaçaguera", "Todas"], key="novo_user_escopo")
            
            sedes_validas = sedes_por_escopo(n_esco)
            n_sede = st.selectbox("Sede Física", sedes_validas, key="novo_user_sede", format_func=lambda x: x.replace("Sede ", ""))
            
            st.markdown("---")
            st.markdown("**Governança (O que o usuário pode ver/fazer?)**")
            
            # Define marcações automáticas inteligentes com base no perfil escolhido
            if n_perf == "Técnico": def_gov = ["Mapa de Campo"]
            elif n_perf == "Assistente": def_gov = ["Painel Gerencial", "Upload de Dados"]
            elif n_perf == "Coordenador": def_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Exportar SAP"]
            else: def_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Gestão de Usuários", "Exportar SAP"]
            
            opcoes_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Gestão de Usuários", "Exportar SAP"]
            n_gov = st.multiselect("Permissões de Acesso:", opcoes_gov, default=def_gov, key="novo_user_gov")

            if st.form_submit_button("Salvar Novo Usuário"):
                if n_user:
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute(
                            """
                            INSERT INTO usuarios
                            (username, senha_hash, perfil, escopo, palavra_recuperacao, dica_recuperacao, coordenacao_padrao, reset_obrigatorio, governanca)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (n_user.strip(), hash_senha("mrs123"), n_perf, n_esco, "PENDENTE", "PENDENTE", n_sede, 1, ",".join(n_gov))
                        )
                        conn.commit()
                        st.session_state["msg_sucesso_user"] = f"Usuário '{n_user}' criado com sucesso!"
                        st.rerun()
                    except psycopg2.IntegrityError:
                        conn.rollback(); st.error("Erro: Este usuário já existe.")
                    finally:
                        cur.close(); release_connection(conn)
                else: st.warning("Preencha o login do usuário.")

        st.markdown("<br><b style='color: #F8FAFC;'>👥 Gerenciar Usuários</b>", unsafe_allow_html=True)
        conn = get_connection()
        df_usuarios = pd.read_sql_query("SELECT username, perfil, escopo, coordenacao_padrao, governanca FROM usuarios", conn)
        release_connection(conn)

        usr_sel = st.selectbox("Selecione um usuário:", [""] + df_usuarios["username"].tolist())

        if usr_sel != "":
            dados_usr = df_usuarios[df_usuarios["username"] == usr_sel].iloc[0]
            gov_atual_lista = str(dados_usr["governanca"]).split(",") if pd.notna(dados_usr["governanca"]) else []

            st.caption(f"**Perfil:** {dados_usr['perfil']} | **Visão:** {dados_usr['escopo']} | **Sede:** {str(dados_usr['coordenacao_padrao']).replace('Sede ', '')}")

            acao = st.radio("Ação:", ["✏️ Editar Acesso", "🔑 Resetar Senha", "🗑️ Excluir"], horizontal=True)

            if acao == "✏️ Editar Acesso":
                with st.form(f"form_edit_{usr_sel}"):
                    n_perf_edit = st.selectbox("Novo Perfil", ["Técnico", "Assistente", "Coordenador", "Gerência"], index=["Técnico", "Assistente", "Coordenador", "Gerência"].index(dados_usr["perfil"]))
                    n_esco_edit = st.selectbox("Nova Visão", ["Paranapiacaba", "Piaçaguera", "Todas"], index=["Paranapiacaba", "Piaçaguera", "Todas"].index(dados_usr["escopo"]))
                    n_sede_edit = st.selectbox("Sede", sedes_por_escopo(n_esco_edit), format_func=lambda x: x.replace("Sede ", ""))
                    
                    gov_editadas = st.multiselect("Governança:", opcoes_gov, default=[g for g in gov_atual_lista if g in opcoes_gov])

                    if st.form_submit_button("Salvar Alterações"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute(
                            "UPDATE usuarios SET perfil=%s, escopo=%s, coordenacao_padrao=%s, governanca=%s WHERE username=%s",
                            (n_perf_edit, n_esco_edit, n_sede_edit, ",".join(gov_editadas), usr_sel)
                        )
                        conn.commit(); cur.close(); release_connection(conn)
                        st.session_state["msg_sucesso_user"] = f"Acessos de {usr_sel} atualizados!"; st.rerun()

            elif acao == "🔑 Resetar Senha":
                if st.button("Confirmar Reset"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET senha_hash = %s, reset_obrigatorio = 1 WHERE username = %s", (hash_senha("mrs123"), usr_sel))
                    conn.commit(); cur.close(); release_connection(conn)
                    st.session_state["msg_sucesso_user"] = f"Senha de {usr_sel} resetada!"; st.rerun()

            elif acao == "🗑️ Excluir":
                if st.button("Confirmar Exclusão", type="primary"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("DELETE FROM usuarios WHERE username = %s", (usr_sel,))
                    conn.commit(); cur.close(); release_connection(conn)
                    st.session_state["msg_sucesso_user"] = f"Usuário {usr_sel} excluído."; st.rerun()
#endregion

#region SESSÃO 7: DASHBOARD HEADER E KPI METRICS
col_titulo, col_acoes = st.columns([9, 1])

with col_titulo:
    st.title("⚡ Sistema de Gestão de Ordens de Serviço")
    st.markdown(f"<h5 style='color: #475569; margin-top: -10px;'>Olá, <b>{st.session_state.get('username', 'Usuário')}</b> 👋</h5>", unsafe_allow_html=True)

with col_acoes:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()
        
    if st.button("🔑 Trocar", use_container_width=True):
        usr_atual = st.session_state["username"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET reset_obrigatorio = 1 WHERE username = %s", (usr_atual,))
        conn.commit()
        cur.close()
        release_connection(conn)
        
        st.session_state.clear()
        st.session_state["logged_in"] = False
        st.session_state["needs_reset"] = True
        st.session_state["reset_user"] = usr_atual
        st.rerun()
        
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear() 
        st.session_state["logged_in"] = False
        st.rerun()

st.markdown("---")

# CÁLCULO DOS KPIS PARA A SESSÃO 7
total_os = len(df_filtrado)
realizado_prazo = len(df_filtrado[df_filtrado["Status_norm"].isin(_status_prazo)])
realizado_atraso = len(df_filtrado[df_filtrado["Status_norm"].isin(_status_atraso)])
realizado_total = realizado_prazo + realizado_atraso
nao_realizado = len(df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto)])
taxa_conclusao = (realizado_total / total_os * 100) if total_os > 0 else 0.0

st.markdown("""
    <style>
    iframe, .stEcharts, [data-testid="stHtmlBlock"] + div iframe {
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    .kpi-header-wrapper { font-family: "Source Sans Pro", sans-serif; }
    .kpi-header-card {
        font-family: "Source Sans Pro", sans-serif;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px rgba(15, 23, 42, 0.08);
        height: 140px; 
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
        margin-bottom: 15px;
    }
    .kpi-border-gray { border-left: 5px solid #64748B; background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%); }
    .kpi-border-red { border-left: 5px solid #FF4B4B; background: linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%); }
    .kpi-border-green { border-left: 5px solid #10B981; background: linear-gradient(135deg, #F0FDF4 0%, #D1FAE5 100%); }
    .kpi-border-blue { border-left: 5px solid #3B82F6; background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); }
    .kpi-header-title { font-size: 14px; font-weight: 700; color: #1E293B; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-header-val { font-size: 32px; font-weight: 400; color: #0F172A; line-height: 1; }
    .kpi-header-sub { font-size: 12px; font-weight: 400; margin-top: 8px; padding: 4px 10px; border-radius: 20px; display: inline-block; width: fit-content; }
    .badge-gray { background-color: #E2E8F0; color: #475569; }
    .badge-red { background-color: #FECACA; color: #991B1B; }
    .badge-green { background-color: #A7F3D0; color: #065F46; }
    .badge-blue { background-color: #DBEAFE; color: #1E40AF; }
    </style>
""", unsafe_allow_html=True)

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
#endregion

#region SESSÃO 8: Abas e Renderização dos Gráficos

#region 8.1 - ROTEAMENTO PRINCIPAL (CONTROLE DE TELAS)
if st.session_state.get("tela_atual", "dashboard") == "dashboard":
    
    # Apenas 2 Abas! A Governança agora é uma tela separada.
    tab1, tab2 = st.tabs(["📊 Visão Gerencial", "🗺️ Roteirização e Mapa de Campo"])
#endregion

#region 8.2: ABA 1 — Visão Gerencial (Indicadores)
    with tab1:
        if st.session_state["perfil"] == "Técnico":
            st.info("🔒 Seu perfil (Técnico) tem foco operacional. Por favor, utilize a aba 'Roteirização e Mapa de Campo'.")
        else:
            df_visao_base = df_filtrado.copy()

            cor_plan = "#64748B"      
            cor_real = "#3B82F6"      
            cor_prazo = "#10B981"     
            cor_atraso = "#F59E0B"    
            cor_pendente = "#FF4B4B"  

            if taxa_conclusao <= 25: gauge_color = cor_pendente
            elif taxa_conclusao <= 50: gauge_color = cor_atraso
            elif taxa_conclusao <= 80: gauge_color = cor_prazo
            else: gauge_color = cor_real

            with st.expander("Resumo Executivo (Geral)", expanded=True):
                col_g1, col_g2, col_g5 = st.columns(3)

                with col_g1:
                    st.markdown("#### Realizado x Planejado")
                    gauge_options = {
                        "tooltip": {"formatter": "{a} <br/>{b}: {c}%"},
                        "series": [{
                            "name": "Conclusão", "type": "gauge", "min": 0, "max": 100, "radius": "75%",
                            "progress": {"show": True, "width": 14, "itemStyle": {"color": gauge_color}},
                            "axisLine": {
                                "lineStyle": {
                                    "width": 14,
                                    "color": [[0.25, cor_pendente], [0.50, cor_atraso], [0.80, cor_prazo], [1.00, cor_real]]
                                }
                            },
                            "pointer": {"show": True, "length": "60%", "width": 6},
                            "itemStyle": {"color": gauge_color},
                            "title": {"show": True, "offsetCenter": [0, "70%"], "fontSize": 14},
                            "detail": {
                                "valueAnimation": True, "offsetCenter": [0, "40%"],
                                "formatter": f"{taxa_conclusao:.1f}%\n{realizado_total} / {total_os}", "fontSize": 16
                            },
                            "data": [{"value": round(taxa_conclusao, 1), "name": "Realizado"}],
                        }],
                    }
                    st_echarts(options=gauge_options, height="350px", theme="streamlit", key="aba1_gauge")

                with col_g2:
                    st.markdown("#### Distribuição por Status")
                    rosca_options = {
                        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                        "legend": {"orient": "horizontal", "bottom": "0%"},
                        "series": [{
                            "name": "Status", "type": "pie", "radius": ["45%", "75%"],
                            "data": [
                                {"value": realizado_prazo, "name": "No Prazo", "itemStyle": {"color": cor_prazo}},
                                {"value": realizado_atraso, "name": "Atrasado", "itemStyle": {"color": cor_atraso}},
                                {"value": nao_realizado, "name": "Pendentes", "itemStyle": {"color": cor_pendente}},
                            ],
                            "label": {"show": True, "position": "inside", "formatter": "{c}\n({d}%)", "color": "#FFFFFF", "fontWeight": "bold"},
                        }],
                    }
                    st_echarts(options=rosca_options, height="350px", theme="streamlit", key="aba1_rosca")

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

                        area_options = {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"top": "bottom"},
                            "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                            "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
                            "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
                            "xAxis": {"type": "category", "data": [d.strftime("%d/%m") for d in _idx_da]},
                            "yAxis": {"type": "value"},
                            "series": [
                                {"name": "Realizado Acumulado", "type": "line", "smooth": True, "data": _real_acum.tolist(), "areaStyle": {"color": "rgba(59,130,246,0.2)"}, "lineStyle": {"color": cor_real, "width": 3}, "itemStyle": {"color": cor_real}},
                                {"name": "Planejado Acumulado", "type": "line", "smooth": True, "data": _plan_acum.tolist(), "lineStyle": {"color": cor_plan, "width": 3, "type": "dashed"}, "itemStyle": {"color": cor_plan}},
                            ],
                        }
                        st_echarts(options=area_options, height="350px", theme="streamlit", key="aba1_area")
                    else:
                        st.info("Sem datas suficientes para área.")

            with st.expander("Análise Operacional: Matriz de Prioridades e Execução por Categoria", expanded=True):
                col_h1, col_h2 = st.columns([1.2, 1])

                with col_h1:
                    st.markdown("#### Matriz: Prioridade vs Classificação")
                    st.caption("Volume total de OS planejadas (Cor indica concentração)")

                    df_heat = df_visao_base.copy()
                    agg = df_heat.groupby(["Classificacao", "Criticidade"]).size().reset_index(name="Total")

                    ordem_class = ["Confiabilidade", "Segurança", "Confiabilidade e Segurança"]
                    ordem_crit = ["Muito Alta", "Alta", "Média", "Baixa"]

                    if not agg.empty:
                        heat_data = []
                        max_val = 0

                        for _yi, _cls in enumerate(ordem_class):
                            for _xi, _crt in enumerate(ordem_crit):
                                _row = agg[(agg["Classificacao"] == _cls) & (agg["Criticidade"] == _crt)]
                                _val = int(_row["Total"].iloc[0]) if not _row.empty else 0
                                heat_data.append([_xi, _yi, _val])
                                if _val > max_val: max_val = _val

                        heatmap_options = {
                            "tooltip": {"position": "top"},
                            "grid": {"height": "70%", "top": "10%", "left": "25%", "containLabel": True},
                            "xAxis": {"type": "category", "data": ordem_crit, "splitArea": {"show": True}, "axisLine": {"show": False}, "axisTick": {"show": False}},
                            "yAxis": {"type": "category", "data": ordem_class, "splitArea": {"show": True}, "axisLine": {"show": False}, "axisTick": {"show": False}},
                            "visualMap": {"min": 0, "max": max_val if max_val > 0 else 10, "calculable": True, "orient": "horizontal", "left": "center", "bottom": "0%", "inRange": {"color": ["#F1F5F9", "#93C5FD", "#3B82F6", "#1E3A8A"]}},
                            "series": [{"name": "Total de OS", "type": "heatmap", "data": heat_data, "label": {"show": True, "color": "#FFFFFF", "fontWeight": "bold", "formatter": JsCode("function(p){return p.value[2] > 0 ? p.value[2] : '';}")}, "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2}}],
                        }
                        st_echarts(options=heatmap_options, height="380px", theme="streamlit", key="aba1_heatmap_discrete")
                    else:
                        st.info("Sem dados para a Matriz.")

                with col_h2:
                    st.markdown("#### Plan x Realizado por Categoria")
                    st.caption("Comparativo de volume total e execução.")

                    df_bar_cat = df_visao_base.copy()
                    plan_cat = df_bar_cat.groupby("Classificacao").size()
                    real_cat = (df_bar_cat[df_bar_cat["Status_norm"].isin(_status_prazo | _status_atraso)].groupby("Classificacao").size())

                    cats = ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
                    val_plan = [int(plan_cat.get(c, 0)) for c in cats]
                    val_real = [int(real_cat.get(c, 0)) for c in cats]

                    bar_horiz_options = {
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "legend": {"bottom": "0%"},
                        "grid": {"left": "3%", "right": "10%", "bottom": "15%", "top": "10%", "containLabel": True},
                        "xAxis": {"type": "value", "boundaryGap": [0, 0.01]},
                        "yAxis": {"type": "category", "data": cats, "axisLabel": {"interval": 0}},
                        "series": [
                            {"name": "Planejado", "type": "bar", "data": val_plan, "itemStyle": {"color": cor_plan}, "label": {"show": True, "position": "right", "color": "#475569"}},
                            {"name": "Realizado", "type": "bar", "data": val_real, "itemStyle": {"color": cor_real}, "label": {"show": True, "position": "right", "color": "#475569"}}
                        ]
                    }
                    st_echarts(options=bar_horiz_options, height="380px", theme="streamlit", key="aba1_bar_horiz")

            with st.expander("Execução por Turno e Acumulado", expanded=True):
                col_g3, col_g6 = st.columns(2)

                _cor_turno = { "00h-07h": "#4F46E5", "07h-16h": "#3B82F6", "16h-00h": "#06B6D4" }

                with col_g3:
                    st.markdown("#### Realizado por Turno")
                    df_barra_real = df_visao_base[df_visao_base["Status_norm"].isin(_status_prazo | _status_atraso)].copy()
                    x_turnos = ["00h-07h", "07h-16h", "16h-00h"]
                    _cnt_t = df_barra_real.groupby("Turno").size()
                    y_vals = [int(_cnt_t.get(t, 0)) for t in x_turnos]

                    barra_options = {
                        "tooltip": {"trigger": "axis"},
                        "xAxis": {"type": "category", "data": x_turnos},
                        "yAxis": {"type": "value"},
                        "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                        "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "15%", "containLabel": True},
                        "series": [{"type": "bar", "barWidth": "55%", "label": {"show": True, "position": "inside", "formatter": "{c}", "color": "#FFFFFF", "fontWeight": "bold"}, "data": [{"value": v, "name": t, "itemStyle": {"color": _cor_turno.get(t, "#94A3B8")}} for t, v in zip(x_turnos, y_vals)]}],
                    }
                    st_echarts(options=barra_options, height="350px", theme="streamlit", key="aba1_barra")

                with col_g6:
                    st.markdown("#### Realizado Acumulado por Turno")
                    df_linhas_plot = df_visao_base.dropna(subset=["dia_realizado"]).copy()

                    if not df_linhas_plot.empty:
                        _ordem_t = ["00h-07h", "07h-16h", "16h-00h"]
                        _idx_dt = pd.date_range(start=df_linhas_plot["dia_realizado"].min(), end=df_linhas_plot["dia_realizado"].max(), freq="D")

                        _series_t = []
                        for _t in _ordem_t:
                            _s = (df_linhas_plot[df_linhas_plot["Turno"] == _t].groupby("dia_realizado").size().reindex(_idx_dt, fill_value=0).cumsum())
                            _series_t.append({"name": _t, "type": "line", "smooth": True, "data": _s.tolist(), "lineStyle": {"color": _cor_turno[_t], "width": 3}, "itemStyle": {"color": _cor_turno[_t]}})

                        linhas_options = {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"top": "bottom"},
                            "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar", "stack"], "title": {"line": "Linha", "bar": "Barra", "stack": "Empilhado"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                            "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
                            "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
                            "xAxis": {"type": "category", "data": [d.strftime("%d/%m") for d in _idx_dt]},
                            "yAxis": {"type": "value"},
                            "series": _series_t,
                        }
                        st_echarts(options=linhas_options, height="350px", theme="streamlit", key="aba1_linhas")
                    else:
                        st.info("Sem dados cronológicos.")

            st.subheader("📋 Lista Detalhada de OS")
            df_lista = df_visao_base.copy().rename(columns={"Ordem servico": "OS"})

            # --- EVIDÊNCIAS FOTOGRÁFICAS (merge com a tabela de evidências) ---
            try:
                df_evidencias = carregar_evidencias_df()
                if not df_evidencias.empty and "Ativo" in df_lista.columns:
                    col_atividade_lista = "Atividade ativo" if "Atividade ativo" in df_lista.columns else None
                    if col_atividade_lista:
                        df_lista = df_lista.merge(
                            df_evidencias[["ativo", "atividade", "foto_url"]],
                            left_on=["Ativo", col_atividade_lista],
                            right_on=["ativo", "atividade"],
                            how="left"
                        )
                        df_lista["Evidência"] = df_lista["foto_url"].apply(
                            lambda url: str(url) if pd.notna(url) and str(url).startswith("http") else None
                        )
                        df_lista.drop(columns=["ativo", "atividade", "foto_url"], inplace=True, errors="ignore")
                    else:
                        df_lista["Evidência"] = ""
                else:
                    df_lista["Evidência"] = ""
            except Exception:
                df_lista["Evidência"] = ""

            if "Data inicial programada" in df_lista.columns:
                df_lista["Data inicial programada"] = pd.to_datetime(df_lista["Data inicial programada"], errors="coerce").dt.strftime("%d/%m/%Y")

            if "Data/Hora Realizado" in df_lista.columns:
                df_lista["Data/Hora Realizado"] = pd.to_datetime(
                    df_lista["Data/Hora Realizado"], dayfirst=True, errors="coerce"
                ).dt.strftime("%d/%m/%Y %H:%M").fillna("")

            colunas_ordem = ["OS", "Patio", "Ativo", "Criticidade", "Classificacao", "Descrição Longa", "Data inicial programada", "Status da Operação", "Data/Hora Realizado", "Concluído por", "Geolocalização de Baixa", "Evidência"]

            for c in colunas_ordem:
                if c not in df_lista.columns:
                    df_lista[c] = ""

            if not df_lista.empty:
                df_styled = df_lista[colunas_ordem].style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
                st.dataframe(df_styled, use_container_width=True, height=400, hide_index=True, column_config={"Evidência": st.column_config.LinkColumn("📷 Evidência", display_text="📷 Ver Foto")})
#endregion

#region 8.3: ABA 2 — Roteirização e Mapa de Campo
        with tab2:
            # 0. Inicialização de segurança da variável para evitar NameError
            df_recomendado = pd.DataFrame()
            
            # 8.3.1 Calendário mensal
            st.markdown("### 📅 Agenda Mensal de Demanda por Pátio")
            
            # CSS: Fontes e Cartões da Aba 2 com dimensões limpas e elegantes
            st.markdown(
                """
                <style>
                .kpi-wrapper { font-family: "Source Sans Pro", sans-serif; }

                /* Card 1: Azul */
                .kpi-card-blue {
                    background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
                    border-left: 5px solid #3B82F6; 
                    border-radius: 12px;
                    padding: 16px 20px;
                    box-shadow: 0 4px 6px rgba(59, 130, 246, 0.15);
                    height: 140px; 
                    margin-bottom: 16px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    box-sizing: border-box;
                }
                .kpi-title-blue { color: #1E3A8A; font-size: 14px; font-weight: 700; margin-bottom: 6px; text-transform: uppercase; }
                .kpi-val-blue { color: #1E40AF; font-size: 32px; font-weight: 400; line-height: 1; }
                .kpi-sub-blue { color: #3B82F6; font-size: 12px; font-weight: 400; margin-top: 8px;}

                /* Card 2: Verde */
                .kpi-card-green {
                    background: linear-gradient(135deg, #F0FDF4 0%, #D1FAE5 100%);
                    border-left: 5px solid #10B981; 
                    border-radius: 12px;
                    padding: 16px 20px;
                    box-shadow: 0 4px 6px rgba(16, 185, 129, 0.15);
                    height: 140px; 
                    margin-bottom: 16px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    box-sizing: border-box;
                }
                .kpi-title-green { color: #064E3B; font-size: 14px; font-weight: 700; margin-bottom: 6px; text-transform: uppercase; }
                .kpi-val-green { color: #065F46; font-size: 32px; font-weight: 400; line-height: 1; }
                .kpi-badge { 
                    font-size: 12px; font-weight: 400; padding: 4px 10px; border-radius: 20px; 
                    display: inline-block; margin-top: 10px; width: fit-content; 
                }

                /* Card 3: Vermelho */
                .kpi-card-red {
                    background: linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%);
                    border-left: 5px solid #FF4B4B; 
                    border-radius: 12px;
                    padding: 16px 20px;
                    box-shadow: 0 4px 6px rgba(255, 75, 75, 0.15);
                    height: 140px; 
                    margin-bottom: 16px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    box-sizing: border-box;
                }
                .kpi-title-red { color: #7F1D1D; font-size: 14px; font-weight: 700; margin-bottom: 6px; text-transform: uppercase; }
                .kpi-val-red { color: #991B1B; font-size: 24px; font-weight: 400; line-height: 1.2; margin-top: 4px;} 
                .kpi-sub-red { color: #EF4444; font-size: 12px; font-weight: 400; margin-top: 8px;}
                </style>
                """,
                unsafe_allow_html=True
            )

            hoje_ref = datetime.now()

            # Garantir que as variáveis de estado existam
            if "cal_ref_mes" not in st.session_state: st.session_state["cal_ref_mes"] = int(hoje_ref.month)
            if "cal_ref_ano" not in st.session_state: st.session_state["cal_ref_ano"] = int(hoje_ref.year)

            col_cal_ctrl_1, col_cal_ctrl_2, _ = st.columns([1, 1, 4])

            is_tecnico = st.session_state.get("perfil") == "Técnico"

            if is_tecnico:
                st.session_state["cal_ref_mes"] = int(hoje_ref.month)
                st.session_state["cal_ref_ano"] = int(hoje_ref.year)
                with col_cal_ctrl_1: 
                    st.info(f"Mês: {hoje_ref.strftime('%m')}")
                with col_cal_ctrl_2: 
                    st.info(f"Ano: {hoje_ref.year}")
                st.caption(f"📌 **Visão Operacional de Campo:** Calendário fixado no mês vigente ({hoje_ref.strftime('%m/%Y')})")
                st.markdown("<div style='margin-bottom: -10px;'></div>", unsafe_allow_html=True)
            else:
                with col_cal_ctrl_1:
                    mes_opcao = st.selectbox(
                        "Mês",
                        list(range(1, 13)),
                        index=int(st.session_state["cal_ref_mes"]) - 1,
                        format_func=lambda x: f"{x:02d}",
                        key="cal_mes_ref_select"
                    )

                with col_cal_ctrl_2:
                    ano_atual = hoje_ref.year
                    ano_opcao = st.number_input(
                        "Ano",
                        min_value=ano_atual - 2,
                        max_value=ano_atual + 2,
                        value=int(st.session_state["cal_ref_ano"]),
                        step=1,
                        key="cal_ano_ref_input"
                    )

                st.session_state["cal_ref_mes"] = int(mes_opcao)
                st.session_state["cal_ref_ano"] = int(ano_opcao)

            # Preparação dos dados do calendário
            df_calendario = df_visao.copy()
            
            if "patios_selecionados" in locals() and "classif_selecionadas" in locals():
                df_calendario = df_calendario[
                    (df_calendario["Patio"].isin(patios_selecionados)) &
                    (df_calendario["Classificacao"].isin(classif_selecionadas))
                ].copy()

            hoje_real = datetime.now().date()
            if (
                int(st.session_state["cal_ref_ano"]) == hoje_real.year and
                int(st.session_state["cal_ref_mes"]) == hoje_real.month
            ):
                dia_ref_default = hoje_real
            else:
                dia_ref_default = datetime(
                    int(st.session_state["cal_ref_ano"]),
                    int(st.session_state["cal_ref_mes"]),
                    1
                ).date()

            user_limpo = str(st.session_state.get('username', 'usr')).replace(" ", "_").lower()
            cal_key = f"cal_fixo_tecnico_{user_limpo}" if is_tecnico else f"cal_dinamico_{user_limpo}"

            cal_state = st.session_state.get(cal_key)
            data_ref_card = dia_ref_default
            
            if cal_state and isinstance(cal_state, dict):
                if cal_state.get("callback") == "dateClick":
                    data_ref_card = pd.to_datetime(cal_state["dateClick"]["date"]).date()
                elif cal_state.get("callback") == "eventClick":
                    data_ref_card = pd.to_datetime(cal_state["eventClick"]["event"]["start"]).date()
                    
            if data_ref_card.year != int(st.session_state["cal_ref_ano"]) or data_ref_card.month != int(st.session_state["cal_ref_mes"]):
                data_ref_card = dia_ref_default

            mostrar_calendario = st.toggle("📅 Mostrar Agenda Mensal de Demanda por Pátio e Turno", value=False)

            if mostrar_calendario:
                with st.spinner("Carregando agenda..."):
                    calendar_events = montar_eventos_calendario_patios(
                        df_base_cal=df_calendario,
                        ano=int(st.session_state["cal_ref_ano"]),
                        mes=int(st.session_state["cal_ref_mes"]),
                        max_patios_visiveis=2
                    )

                    calendar_options = {
                        "initialView": "dayGridMonth",
                        "initialDate": f"{int(st.session_state['cal_ref_ano']):04d}-{int(st.session_state['cal_ref_mes']):02d}-01",
                        "locale": "pt-br",
                        "height": "auto",
                        "contentHeight": "auto",
                        "headerToolbar": { "left": "", "center": "title", "right": "" },
                        "dayMaxEvents": 2,
                        "eventOrder": "displayOrder,title",
                        "fixedWeekCount": False,
                        "showNonCurrentDates": True,
                        "expandRows": True,
                        "handleWindowResize": True,
                    }

                    calendar_css_base = """
                    .fc { font-size: 14px; background: #FFFFFF; border-radius: 12px; padding: 6px; box-shadow: 0 1px 8px rgba(15, 23, 42, 0.08); }
                    .fc .fc-toolbar { margin-bottom: 0.25rem !important; }
                    .fc .fc-toolbar-title { font-size: 1.4rem !important; font-weight: 800; text-align: center; text-transform: capitalize; color: #1E293B; }
                    .fc .fc-scrollgrid { border-radius: 10px; overflow: hidden; border: 1px solid #E2E8F0; }
                    .fc .fc-scroller, .fc .fc-scroller-liquid-absolute { overflow: hidden !important; }
                    .fc .fc-col-header-cell { background-color: #F8FAFC; }
                    .fc .fc-col-header-cell-cushion { font-size: 14px; font-weight: 800; color: #334155; padding: 6px 2px !important; text-transform: capitalize; }
                    .fc .fc-daygrid-day-number { font-size: 1.1rem; font-weight: 800; padding: 4px 6px !important; color: #334155; }
                    .fc .fc-daygrid-day-frame { min-height: 62px !important; cursor: pointer; transition: background-color 0.2s; }
                    .fc .fc-daygrid-day-frame:hover { background-color: #F8FAFC !important; }
                    .fc .fc-daygrid-event { border-radius: 6px; padding: 3px 5px; font-size: 12.5px !important; line-height: 1.15; font-weight: 800; margin-top: 1px !important; cursor: pointer; }
                    .fc .fc-daygrid-event .fc-event-title { white-space: nowrap !important; overflow: hidden; text-overflow: ellipsis; letter-spacing: 0.2px; }
                    .fc .fc-theme-standard td, .fc .fc-theme-standard th { border-color: #E2E8F0; }
                    """

                    calendar_css_dinamico = f"""
                    {calendar_css_base}
                    .fc-daygrid-day[data-date="{data_ref_card.strftime('%Y-%m-%d')}"] {{
                        background-color: #EFF6FF !important;
                        box-shadow: inset 0 0 0 3px #3B82F6 !important;
                    }}
                    .fc-daygrid-day[data-date="{data_ref_card.strftime('%Y-%m-%d')}"] .fc-daygrid-day-number {{
                        color: #1D4ED8 !important;
                        background-color: #DBEAFE !important;
                        border-radius: 6px;
                        padding: 2px 6px !important;
                    }}
                    """

                    col_calendario, col_cards, col_turno = st.columns([5.8, 2.0, 2.2], gap="large")

                    with col_calendario:
                        calendar_state = calendar(
                            events=calendar_events,
                            options=calendar_options,
                            custom_css=calendar_css_dinamico,
                            callbacks=["dateClick", "eventClick"],
                            key=f"cal_dinamico_{cal_key}_{st.session_state.get('cal_ref_mes')}"
                        )

                    resumo_card = resumir_demanda_calendario(
                        df_base_cal=df_calendario, ano=data_ref_card.year, mes=data_ref_card.month, dia_ref=data_ref_card.day
                    )
                    resumo_turno = resumir_conclusoes_por_turno_data(df_base_cal=df_calendario, data_ref=data_ref_card)

                    with col_cards:
                        st.markdown(
                            f"""
                            <div class="kpi-wrapper kpi-card-blue">
                                <div class="kpi-title-blue">Pátios do Dia</div>
                                <div class="kpi-val-blue">{resumo_card['qtd_patios']} <span style='font-size: 22px;'>📌</span></div>
                                <div class="kpi-sub-blue">Referência: {data_ref_card.strftime('%d/%m/%Y')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        dia_idx = data_ref_card.day - 1
                        serie_mes = resumo_card["serie_total_os_mes"]
                        hoje_total = serie_mes[dia_idx] if dia_idx < len(serie_mes) else 0
                        ontem_total = serie_mes[dia_idx - 1] if dia_idx > 0 else hoje_total

                        if ontem_total > 0: delta_pct = ((hoje_total - ontem_total) / ontem_total) * 100
                        else: delta_pct = 0.0

                        if delta_pct > 0: seta, cor_badge, bg_badge, sinal = "↑", "#065F46", "#A7F3D0", "+"
                        elif delta_pct < 0: seta, cor_badge, bg_badge, sinal = "↓", "#991B1B", "#FECACA", ""
                        else: seta, cor_badge, bg_badge, sinal = "→", "#475569", "#E2E8F0", ""

                        total_os_options = {
                            "backgroundColor": "transparent", "animation": False,
                            "graphic": [
                                {"type": "rect", "left": 0, "top": 0, "shape": {"x": 0, "y": 0, "width": 320, "height": 140, "r": 18}, "style": {"fill": "#F0FDF4"}},
                                {"type": "rect", "left": 0, "top": 0, "shape": {"x": 0, "y": 0, "width": 5, "height": 140, "r": [18, 0, 0, 18]}, "style": {"fill": "#10B981"}},
                                {"type": "text", "left": "6%", "top": "16%", "style": {"text": "TOTAL DE OS DO DIA", "fill": "#064E3B", "font": "700 14px 'Source Sans Pro', sans-serif"}},
                                {"type": "text", "left": "6%", "top": "40%", "style": {"text": f"{hoje_total} 🎯", "fill": "#065F46", "font": "400 32px 'Source Sans Pro', sans-serif"}},
                                {"type": "text", "left": "6%", "top": "72%", "style": {"text": f"{seta} {sinal}{delta_pct:.1f}% vs ontem", "fill": "#10B981", "font": "400 12px 'Source Sans Pro', sans-serif"}}
                            ]
                        }
                        st_echarts(options=total_os_options, height="140px", key="card_total_os_dia")
                        st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

                        st.markdown(
                            f"""
                            <div class="kpi-wrapper kpi-card-red">
                                <div class="kpi-title-red">Pátio Prioritário</div>
                                <div class="kpi-val-red">{resumo_card['patio_prioritario']}</div>
                                <div class="kpi-sub-red">Critério: backlog + prioridade</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with col_turno:
                        _cor_turno_aba2 = { "00h-07h": "#4F46E5", "07h-16h": "#3B82F6", "16h-00h": "#06B6D4" }
                        dados_formatados_turno = [
                            {"value": val, "itemStyle": { "color": _cor_turno_aba2.get(lbl, "#3B82F6"), "borderRadius": [0, 6, 6, 0] }}
                            for lbl, val in zip(resumo_turno["labels"], resumo_turno["valores"])
                        ]
                        with st.container(border=True):
                            concl_turno_options = {
                                "title": {"text": resumo_turno["titulo"], "subtext": resumo_turno["subtitulo"], "left": "center", "top": "5%", "textStyle": { "fontSize": 14, "fontWeight": "bold", "color": "#1E293B", "fontFamily": '"Source Sans Pro", sans-serif' }, "subtextStyle": { "fontSize": 12, "color": "#64748B", "fontFamily": '"Source Sans Pro", sans-serif' }},
                                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                                "grid": { "left": "18%", "right": "10%", "bottom": "12%", "top": "24%", "containLabel": True },
                                "xAxis": { "type": "value", "minInterval": 1, "splitLine": { "lineStyle": { "type": "dashed", "color": "#E2E8F0" } } },
                                "yAxis": { "type": "category", "data": resumo_turno["labels"], "axisLabel": { "fontSize": 12, "fontWeight": "600", "color": "#475569", "fontFamily": '"Source Sans Pro", sans-serif' }, "axisLine": { "show": False }, "axisTick": { "show": False }},
                                "series": [{"name": "OS Concluídas", "type": "bar", "data": dados_formatados_turno, "barWidth": "42%", "label": { "show": True, "position": "right", "color": "#1E293B", "fontWeight": "bold", "fontSize": 13, "fontFamily": '"Source Sans Pro", sans-serif' }}]
                            }
                            st_echarts(options=concl_turno_options, height="435px", theme="streamlit", key="chart_conclusoes_turno_data")

            st.markdown("---")

            # 8.3.2 Navegação geográfica operacional
            st.markdown("### 🗺️ Navegação Geográfica Operacional")

            col_mapa, col_acao = st.columns([6, 4], gap="large")

            if "df_filtrado" in locals():
                df_pendentes_f = df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto)].copy()
            else:
                df_pendentes_f = df_visao[df_visao["Status_norm"].isin(_status_aberto)].copy()

            with col_acao:
                st.markdown("#### ⚙️ Ferramentas de Campo")

                # --- INICIALIZAÇÃO CENTRALIZADA DE SESSION_STATE ---

                if "lat_partida" not in st.session_state:
                    lat_base, lon_base, nome_base = obter_base_padrao_usuario()
                    st.session_state["lat_partida"] = lat_base
                    st.session_state["lon_partida"] = lon_base
                    st.session_state["local_nome"] = nome_base

                GPS_MAX_TRIALS = 10

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📍 Minha Localização", use_container_width=True, key="btn_gps_localizacao"):
                        st.session_state["gps_pending"] = True
                        st.session_state["gps_trials"] = 0
                        st.rerun()
                with c2:
                    if st.button("🏠 Minha Base", use_container_width=True, key="btn_minha_base"):
                        lat_base, lon_base, nome_base = obter_base_padrao_usuario()
                        st.session_state["lat_partida"] = lat_base
                        st.session_state["lon_partida"] = lon_base
                        st.session_state["local_nome"] = nome_base
                        st.session_state["origem_tipo"] = "BASE"
                        st.session_state["gps_pending"] = False
                        st.session_state["gps_trials"] = 0
                        st.rerun()

                if st.session_state.get("gps_pending"):
                    st.info("Aguardando autorização do navegador e captura do GPS...")
                    loc = get_geolocation()

                    if loc and isinstance(loc, dict) and "coords" in loc:
                        coords = loc.get("coords", {})
                        lat, lon = coords.get("latitude"), coords.get("longitude")
                        if lat is not None and lon is not None:
                            st.session_state["lat_partida"] = float(lat)
                            st.session_state["lon_partida"] = float(lon)
                            st.session_state["local_nome"] = reverse_geocode_coordenada(float(lat), float(lon))
                            st.session_state["origem_tipo"] = "GPS"
                            st.session_state["gps_pending"] = False
                            st.session_state["gps_trials"] = 0
                            st.success("GPS ativado com sucesso!")
                            st.rerun()
                    elif loc and isinstance(loc, dict) and "error" in loc:
                        st.session_state["gps_pending"] = False
                        st.session_state["gps_trials"] = 0
                        st.error(f"GPS falhou: {loc['error'].get('message', 'Erro desconhecido')}")
                    else:
                        st.session_state["gps_trials"] += 1
                        if st.session_state["gps_trials"] < GPS_MAX_TRIALS:
                            st.info("Aguardando permissão do navegador...")
                            time.sleep(0.1)
                            st.rerun()
                        else:
                            st.session_state["gps_pending"] = False
                            st.session_state["gps_trials"] = 0
                            st.error("Tempo do GPS esgotado. Tente novamente ou use a Minha Base.")

                st.markdown("---")
                raio_busca_km = st.slider("📏 Raio de Atuação Visual (km):", 0, 50, 10, 5, key="slider_raio_atuacao")

                origem_label = "📍 GPS" if st.session_state.get("origem_tipo") == "GPS" else "🏠 Base"
                st.caption(f"{origem_label}: **{st.session_state['local_nome']}**")

                lat_origem = float(st.session_state["lat_partida"])
                lon_origem = float(st.session_state["lon_partida"])

                if not df_pendentes_f.empty:
                    df_calc = df_pendentes_f.copy()
                    df_calc["lat_patio"] = df_calc["Patio"].map(lambda p: COORDENADAS_FIXAS.get(str(p).strip().upper(), [np.nan, np.nan])[0])
                    df_calc["lon_patio"] = df_calc["Patio"].map(lambda p: COORDENADAS_FIXAS.get(str(p).strip().upper(), [np.nan, np.nan])[1])
                    com_coord = df_calc.dropna(subset=["lat_patio", "lon_patio"]).copy()

                    if not com_coord.empty:
                        hoje_atual = datetime.now().date()
                        com_coord["Ordem_Prazo"] = com_coord["dt_prog_filtro"].apply(
                            lambda dt: 1 if pd.notna(dt) and dt.date() < hoje_atual else (2 if pd.notna(dt) and dt.date() == hoje_atual else 3)
                        )
                        com_coord["Distancia_km"] = haversine_vectorized(lat_origem, lon_origem, com_coord["lat_patio"], com_coord["lon_patio"])
                        df_recomendado = com_coord[com_coord["Distancia_km"] <= raio_busca_km].sort_values(by=["Ordem_Prazo", "Criticidade_rank", "Distancia_km"])

                st.info(f"**{len(df_recomendado)} OS pendentes** encontradas no raio de {raio_busca_km} km.")

                if not df_recomendado.empty:
                    @st.fragment
                    def renderizar_bloco_apontamento():
                        st.markdown("---")
                        st.markdown("#### ✅ Apontamento e Conclusão de OS")
                        
                        lista_os_unicas = df_recomendado["Ordem servico"].astype(str).unique().tolist()
                        os_selecionadas = st.multiselect("1. Selecione as OSs que deseja baixar:", lista_os_unicas)

                        if os_selecionadas:
                            os_distantes = []
                            for os_id in os_selecionadas:
                                dist = df_recomendado.loc[df_recomendado["Ordem servico"].astype(str) == str(os_id), "Distancia_km"].iloc[0]
                                if dist > 5.0: os_distantes.append(f"{os_id} (a {dist:.1f} km)")
                                    
                            if os_distantes:
                                st.error(f"🛑 **Bloqueio Geográfico:** O sistema exige estar em um raio máximo de **5 km** do local.")
                                st.warning(f"Você está muito longe das OSs: **{', '.join(os_distantes)}**.")
                                st.info("💡 Aproxime-se do pátio e atualize sua posição em '📍 Minha Localização'.")
                                return

                            st.markdown("---")
                            st.markdown("#### 📷 Evidências Fotográficas")
                            st.caption("Registre a evidência de **cada OS**. Use a câmera ou selecione da galeria.")
                            fotos_por_os = {}
                            for os_id_ev in os_selecionadas:
                                with st.expander(f"📷 Foto da OS: {os_id_ev}", expanded=True):
                                    col_cam, col_gal = st.columns(2)
                                    with col_cam:
                                        foto_cam = st.camera_input("📸 Câmera", key=f"cam_{os_id_ev}")
                                    with col_gal:
                                        foto_gal = st.file_uploader("🖼️ Galeria", type=["jpg", "jpeg", "png"], key=f"gal_{os_id_ev}")
                                    fotos_por_os[os_id_ev] = foto_cam if foto_cam is not None else foto_gal

                            conn = get_connection()
                            try:
                                df_users_equipe = pd.read_sql_query("SELECT username FROM usuarios", conn)
                            finally:
                                release_connection(conn)
                            lista_equipe_disp = df_users_equipe["username"].tolist()
                            
                            usr_logado = st.session_state.get("username", "")
                            if usr_logado in lista_equipe_disp: lista_equipe_disp.remove(usr_logado)
                            
                            with st.form("form_apontamento_os"):
                                equipe_selecionada = st.multiselect("2. Selecione a sua equipe:", lista_equipe_disp)
                                st.markdown("---")
                                st.markdown("#### ⏳ Apontamento de Tempos Individuais")
                                
                                apontamentos = {}
                                todos_preenchidos = True
                                
                                for os_id in set(os_selecionadas):
                                    st.markdown(f"<b style='color: #3B82F6;'>OS: {os_id}</b>", unsafe_allow_html=True)
                                    c1, c2 = st.columns(2)
                                    with c1: h_ini = st.time_input(f"Horário Início", key=f"time_ini_{os_id}", value=None)
                                    with c2: h_fim = st.time_input(f"Horário Fim", key=f"time_fim_{os_id}", value=None)
                                        
                                    apontamentos[os_id] = {"inicio": h_ini, "fim": h_fim}
                                    if h_ini is None or h_fim is None: todos_preenchidos = False
                                    st.markdown("<hr style='margin: 8px 0; border-color: #333D4E;'>", unsafe_allow_html=True)

                                origem = st.session_state.get("origem_tipo", "BASE")
                                submit_baixa = st.form_submit_button("🚀 Concluir e Gravar OS(s)", use_container_width=True)
                                
                                if submit_baixa:
                                    if origem != "GPS": st.warning("📍 A geolocalização é obrigatória. Atualize sua posição.")
                                    elif not todos_preenchidos: st.warning("⚠️ Preencha os horários de **início e fim** de todas as OSs.")
                                    else:
                                        geo_baixa = f"{st.session_state.get('local_nome', 'Local')} (Lat: {st.session_state.get('lat_partida')}, Lon: {st.session_state.get('lon_partida')})"
                                        equipe_str = ", ".join(equipe_selecionada) if equipe_selecionada else "Sozinho"
                                        data_hoje_br = datetime.now().strftime("%d/%m/%Y")
                                        realizado_dt = agora_dt()
                                        
                                        for os_id in set(os_selecionadas):
                                            hora_ini_str = apontamentos[os_id]["inicio"].strftime("%H:%M:%S")
                                            hora_fim_str = apontamentos[os_id]["fim"].strftime("%H:%M:%S")
                                            
                                            mask = (st.session_state["df_os"]["Ordem servico"].astype(str) == str(os_id))
                                            dt_prog = st.session_state["df_os"].loc[mask, "Data inicial programada"].iloc[0] if len(st.session_state["df_os"].loc[mask]) > 0 else pd.NaT
                                            coord = st.session_state["df_os"].loc[mask, "Coordenacao"].iloc[0] if len(st.session_state["df_os"].loc[mask]) > 0 else "Campo"
                                            novo_status = determinar_status_execucao(pd.to_datetime(dt_prog, errors="coerce"), realizado_dt)

                                            upsert_baixa(
                                                os_id=str(os_id), status=novo_status, realizado_em_str=formatar_dt_br(realizado_dt),
                                                coordenacao=coord, concluido_por=usr_logado, geolocalizacao_baixa=geo_baixa,
                                                equipe=equipe_str, data_inicio=data_hoje_br, hora_inicio=hora_ini_str,
                                                data_fim=data_hoje_br, hora_fim=hora_fim_str
                                            )

                                        # --- UPLOAD DE EVIDÊNCIA FOTOGRÁFICA (1 por OS) ---
                                        fotos_enviadas = 0
                                        for os_id_foto in set(os_selecionadas):
                                            foto_da_os = fotos_por_os.get(str(os_id_foto))
                                            if foto_da_os is None:
                                                continue
                                            with st.spinner(f"📤 Enviando foto da OS {os_id_foto}..."):
                                                try:
                                                    foto_bytes = foto_da_os.getvalue()
                                                    mask_foto = (st.session_state["df_os"]["Ordem servico"].astype(str) == str(os_id_foto))
                                                    df_match = st.session_state["df_os"].loc[mask_foto]
                                                    if df_match.empty:
                                                        continue
                                                    ativo_val = str(df_match["Ativo"].iloc[0]).strip()
                                                    atividade_col = "Atividade ativo" if "Atividade ativo" in df_match.columns else None
                                                    atividade_val = str(df_match[atividade_col].iloc[0]).strip() if atividade_col else "N_A"
                                                    nome_seguro = re.sub(r'[^\w\-.]', '_', f"{ativo_val}__{atividade_val}.jpg")
                                                    url_foto = upload_foto_supabase(foto_bytes, nome_seguro)
                                                    geo_evidencia = f"Lat: {st.session_state.get('lat_partida')}, Lon: {st.session_state.get('lon_partida')}"
                                                    upsert_evidencia(
                                                        ativo=ativo_val,
                                                        atividade=atividade_val,
                                                        foto_url=url_foto,
                                                        os_referencia=str(os_id_foto),
                                                        concluido_por=usr_logado,
                                                        geolocalizacao=geo_evidencia
                                                    )
                                                    fotos_enviadas += 1
                                                except Exception as e_foto:
                                                    st.warning(f"⚠️ Foto da OS {os_id_foto} falhou: {e_foto}")
                                        if fotos_enviadas > 0:
                                            st.info(f"📷 {fotos_enviadas} evidência(s) registrada(s) com sucesso!")

                                        st.success(f"✅ Execução registrada com sucesso!")
                                        time.sleep(2)
                                        st.rerun()

                    renderizar_bloco_apontamento()
                    st.markdown("---")

            with col_mapa:
                SP_MIN_LAT, SP_MAX_LAT = -25.50, -19.50
                SP_MIN_LON, SP_MAX_LON = -53.50, -44.00

                lat_centro = min(max(lat_origem, SP_MIN_LAT), SP_MAX_LAT)
                lon_centro = min(max(lon_origem, SP_MIN_LON), SP_MAX_LON)

                def calcular_zoom_por_raio(raio_km: float, latitude_ref: float) -> int:
                    raio_km = max(float(raio_km), 0.5)
                    lat_rad = math.radians(float(latitude_ref))
                    km_por_grau_lon = 111.320 * max(math.cos(lat_rad), 0.20)
                    largura_graus = (2.0 * raio_km) / km_por_grau_lon
                    zoom = math.log2(360.0 / max(largura_graus, 1e-6))
                    return int(min(18, max(6, round(zoom))))

                zoom_mapa = calcular_zoom_por_raio(raio_busca_km, lat_centro)

                mapa = folium.Map(location=[lat_centro, lon_centro], zoom_start=zoom_mapa, max_bounds=True, min_lat=SP_MIN_LAT, max_lat=SP_MAX_LAT, min_lon=SP_MIN_LON, max_lon=SP_MAX_LON, control_scale=True, tiles="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png", attr="CartoDB", prefer_canvas=True)

                try:
                    import geopandas as gpd
                    from shapely.geometry import LineString, MultiLineString

                    caminho_kml = "malha_mrs.kml"
                    if os.path.exists(caminho_kml):
                        gdf_malha = gpd.read_file(caminho_kml, driver="KML")
                        gdf_malha.geometry = gdf_malha.geometry.simplify(tolerance=0.001, preserve_topology=True)
                        def adicionar_trecho_ferrovia(geom_trecho):
                            folium.GeoJson(geom_trecho.__geo_interface__, style_function=lambda x: {"color": "#2563EB", "weight": 1.5, "opacity": 0.50, "interactive": False}, control=False).add_to(mapa)

                        for _, row in gdf_malha.iterrows():
                            geom = row.geometry
                            if geom is None or geom.is_empty: continue
                            if isinstance(geom, LineString): adicionar_trecho_ferrovia(geom)
                            elif isinstance(geom, MultiLineString):
                                for subgeom in geom.geoms: adicionar_trecho_ferrovia(subgeom)
                except Exception as e:
                    st.warning(f"Traçado não carregado: {e}")

                folium.Marker(location=[lat_origem, lon_origem], tooltip=f"Origem: {st.session_state['local_nome']}", icon=folium.Icon(color="red", icon="home" if st.session_state.get("origem_tipo") != "GPS" else "map-marker", prefix="fa")).add_to(mapa)
                folium.Circle(radius=raio_busca_km * 1000, location=[lat_origem, lon_origem], color="#3B82F6", fill=True, fill_opacity=0.08, weight=2, tooltip=f"Raio de atuação: {raio_busca_km} km").add_to(mapa)

                if not df_recomendado.empty:
                    agg_map = df_recomendado.groupby("Patio", as_index=False).agg(lat_patio=("lat_patio", "first"), lon_patio=("lon_patio", "first"), qtd_os=("Ordem servico", "count"), menor_dist=("Distancia_km", "min")).sort_values(["menor_dist", "Patio"])
                    for _, row in agg_map.iterrows():
                        folium.CircleMarker(location=[row["lat_patio"], row["lon_patio"]], radius=6, color="#1D4ED8", weight=1.5, fill=True, fill_color="#3B82F6", fill_opacity=0.95, tooltip=f"Pátio: {row['Patio']}<br>OS no raio: {row['qtd_os']}<br>Menor distância: {row['menor_dist']:.1f} km").add_to(mapa)

                st_folium(mapa, height=650, use_container_width=True, returned_objects=[], key="mapa_final_limpo")

            st.markdown("---")

            if not df_recomendado.empty:
                df_tabela_campo = df_recomendado.copy().rename(columns={"Ordem servico": "OS", "Classificacao": "Classificação"})
                df_tabela_campo["Data da Programação"] = df_tabela_campo["dt_prog_filtro"].dt.strftime("%d/%m/%Y")
                colunas_exibir = ["OS", "Data da Programação", "Patio", "Ativo", "Criticidade", "Classificação", "Descrição Longa"]

                col_tit_crono, col_btn_crono = st.columns([7.5, 2.5])
                with col_tit_crono:
                    st.markdown("#### 📋 Cronograma de Execução de Campo")
                    st.caption("OS Pendentes recomendadas no raio de atuação visual por prioridade")

                def aplicar_cor_prazo(row):
                    dt = row["dt_prog_filtro"]
                    if pd.isna(dt): return [""] * len(row)
                    d = dt.date()
                    hoje_ref = datetime.now().date()
                    if d < hoje_ref: return ["background-color: #FEE2E2; color: #7F1D1D; font-weight: 500;"] * len(row)
                    elif d == hoje_ref: return ["background-color: #FEF3C7; color: #78350F; font-weight: 500;"] * len(row)
                    return [""] * len(row)

                st.dataframe(df_tabela_campo.style.apply(aplicar_cor_prazo, axis=1), use_container_width=True, height=350, hide_index=True, column_order=colunas_exibir)
            else:
                st.markdown("#### 📋 Cronograma de Execução de Campo")
                st.info("Nenhuma OS pendente localizada dentro do raio de atuação selecionado.")
        #endregion (Fim da Sessão 8.3)
    #endregion (Fim da Sessão 8 Geral)

#region SESSÃO 9: Tela Isolada de Governança e Auditoria

#region 9.1: Controle de acesso
if st.session_state.get("tela_atual") == "governanca":
    
    col_gov_t1, col_gov_t2 = st.columns([8, 2])
    with col_gov_t1:
        st.title("🛡️ Motor de Governança e Auditoria")
    with col_gov_t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Voltar ao Painel", use_container_width=True):
            st.session_state["tela_atual"] = "dashboard"
            st.session_state["gov_auth_ok"] = False 
            st.rerun()
    st.markdown("Análise estatística de eficiência, variabilidade de cronograma, aderência de login e rastreabilidade de campo.")
    st.markdown("---")

    # --- CAMADA DE SEGURANÇA (VERIFICAÇÃO DE SENHA) ---
    if not st.session_state.get("gov_auth_ok", False):
        st.error("🔒 **Acesso Restrito:** Para visualizar métricas de auditoria de pessoas e GPS, confirme sua credencial.")
        col_auth1, col_auth2 = st.columns([1, 2])
        with col_auth1:
            with st.form("form_auth_gov"):
                senha_confirm = st.text_input("Digite sua Senha", type="password")
                if st.form_submit_button("Desbloquear Painel", use_container_width=True):
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT senha_hash FROM usuarios WHERE username = %s", (st.session_state.get("username"),))
                    row = cur.fetchone()
                    cur.close()
                    release_connection(conn)

                    if row and row[0] == hash_senha(senha_confirm):
                        st.session_state["gov_auth_ok"] = True
                        st.rerun()
                    else:
                        st.error("❌ Senha incorreta. Acesso negado.")
        st.stop()
#endregion

#region 9.2: Lógica de Auditoria
    # --- LÓGICA DE AUDITORIA E GRÁFICOS ---
    with st.spinner("Compilando logs de auditoria e telemetria..."):
        if st.session_state.get("chk_sim", False):
            df_baixas_full = st.session_state.get("df_baixas_sim", pd.DataFrame())
            df_logs = st.session_state.get("df_logs_sim", pd.DataFrame())
        else:
            conn = get_connection()
            df_baixas_full = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim FROM baixas", conn)
            df_logs = pd.read_sql_query("SELECT username, data_hora_login FROM logs_acesso", conn)
            release_connection(conn)
        
        df_os_base = st.session_state.get("df_os", pd.DataFrame())
        
        if df_baixas_full.empty or df_os_base.empty:
            st.warning("Não há dados de execução suficientes para gerar os painéis de auditoria.")
            st.stop()
            
        df_gov = df_baixas_full.merge(
            df_os_base[["Ordem servico", "Patio", "Ativo", "Classificacao", "Criticidade_rank", "Nivel_Prioridade", "Criticidade"]], 
            left_on="os", right_on="Ordem servico", how="inner"
        )
        df_gov = df_gov[df_gov["status"].str.upper().isin(["REALIZADO", "REALIZADO FORA DA DATA DE PROGRAMAÇÃO", "REALIZADO FORA DO PRAZO"])]
        
        def calc_duracao(row):
            try:
                ini = pd.to_datetime(row['hora_inicio'], format='%H:%M:%S')
                fim = pd.to_datetime(row['hora_fim'], format='%H:%M:%S')
                diff = (fim - ini).total_seconds() / 60.0
                if diff < 0: diff += 24 * 60 
                return diff
            except: return 0.0
            
        df_gov["Tempo_Minutos"] = df_gov.apply(calc_duracao, axis=1)
        df_gov["Data_Real"] = pd.to_datetime(df_gov["data_inicio"], format="%d/%m/%Y", errors="coerce").dt.date
        df_gov["Via_GPS"] = df_gov["geolocalizacao_baixa"].apply(lambda x: 0 if "Base" in str(x) or "Sede" in str(x) else 1)
        df_gov["Alta_Prioridade"] = df_gov["Criticidade_rank"].apply(lambda x: 1 if x in [1, 2] else 0)

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        tecnicos_disp = sorted(df_gov["concluido_por"].dropna().unique().tolist())
        tec_selecionado = st.multiselect("👤 Filtrar Colaborador(es):", tecnicos_disp, default=tecnicos_disp)
    with col_f2:
        patios_gov = sorted(df_gov["Patio"].dropna().unique().tolist())
        patio_selecionado = st.multiselect("📍 Filtrar Pátio(s):", patios_gov, default=patios_gov)
    with col_f3:
        min_d, max_d = df_gov["Data_Real"].min(), df_gov["Data_Real"].max()
        if pd.isna(min_d): min_d = datetime.now().date()
        if pd.isna(max_d): max_d = datetime.now().date()
        data_gov = st.date_input("📅 Período de Execução:", value=(min_d, max_d), min_value=min_d, max_value=max_d, format="DD/MM/YYYY")

    d_inicio, d_fim = data_gov if isinstance(data_gov, tuple) and len(data_gov) == 2 else (data_gov[0] if isinstance(data_gov, tuple) else data_gov, data_gov[0] if isinstance(data_gov, tuple) else data_gov)
    df_gov_f = df_gov[(df_gov["concluido_por"].isin(tec_selecionado)) & (df_gov["Patio"].isin(patio_selecionado)) & (df_gov["Data_Real"] >= d_inicio) & (df_gov["Data_Real"] <= d_fim)].copy()

    if df_gov_f.empty:
        st.info("Nenhuma execução encontrada para os filtros selecionados.")
        st.stop()

    total_os_gov = len(df_gov_f)
    tme_minutos = df_gov_f["Tempo_Minutos"].mean()
    taxa_gps = (df_gov_f["Via_GPS"].sum() / total_os_gov) * 100 if total_os_gov > 0 else 0
    taxa_prio = (df_gov_f["Alta_Prioridade"].sum() / total_os_gov) * 100 if total_os_gov > 0 else 0

    c_k1, c_k2, c_k3, c_k4 = st.columns(4)
    c_k1.metric("🔧 Volume de Execução", f"{total_os_gov} OS")
    c_k2.metric("⏱️ Tempo Médio / OS (TME)", f"{int(tme_minutos // 60)}h {int(tme_minutos % 60):02d}m" if not pd.isna(tme_minutos) else "0h 00m")
    c_k3.metric("🎯 Aderência à Prioridade", f"{taxa_prio:.1f}%")
    c_k4.metric("📍 Integridade de GPS", f"{taxa_gps:.1f}%")
    
    st.markdown("---")
#endregion

#region 9.3: Gráficos de Governança e Auditoria
    # ==========================================
    # LINHA 1: Volume Diário vs Produtividade Acumulada
    # ==========================================
    col_l1_c1, col_l1_c2 = st.columns(2, gap="large")

    # Cruzamento para obter o Planejado + Backlog da base mestre
    df_real_dia = df_gov_f.groupby("Data_Real").size().reset_index(name="Realizado")
    df_os_base["Data_Prog_Pure"] = pd.to_datetime(df_os_base["Data inicial programada"], errors="coerce").dt.date
    df_plan_dia = df_os_base.groupby("Data_Prog_Pure").size().reset_index(name="Planejado_Backlog")

    df_merge_vol = pd.merge(df_real_dia, df_plan_dia, left_on="Data_Real", right_on="Data_Prog_Pure", how="outer")
    df_merge_vol["Data_Real"] = df_merge_vol["Data_Real"].combine_first(df_merge_vol["Data_Prog_Pure"])
    df_merge_vol["Realizado"] = df_merge_vol["Realizado"].fillna(0)
    df_merge_vol["Planejado_Backlog"] = df_merge_vol["Planejado_Backlog"].fillna(0)
    df_merge_vol = df_merge_vol.sort_values(by="Data_Real")

    eixo_x_l1 = [d.strftime("%d/%m") if hasattr(d, "strftime") else str(d) for d in df_merge_vol["Data_Real"]]

    with col_l1_c1:
        st.markdown("#### 📈 Volume Diário")
        st.caption("Volume diário executado vs total de OS planejadas + backlog do dia.")
        st_echarts(options={
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["Volume Diário", "Planejado + Backlog"], "bottom": "0%"},
            "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
            "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
            "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": eixo_x_l1},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "Volume Diário", "type": "bar", "data": df_merge_vol["Realizado"].tolist(), "itemStyle": {"color": "#3B82F6"}},
                {"name": "Planejado + Backlog", "type": "line", "data": df_merge_vol["Planejado_Backlog"].tolist(), "smooth": True, "lineStyle": {"type": "dashed", "color": "#64748B", "width": 3}, "itemStyle": {"color": "#64748B"}}
            ]
        }, height="350px", theme="streamlit", key="gov_vol_diario_new")

    with col_l1_c2:
        st.markdown("#### 📈 Produtividade Acumulada")
        st.caption("Curva de entrega acumulada vs planejamento acumulado do período.")
        df_merge_vol["Real_Acum"] = df_merge_vol["Realizado"].cumsum()
        df_merge_vol["Plan_Acum"] = df_merge_vol["Planejado_Backlog"].cumsum()
        st_echarts(options={
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["Realizado Acumulado", "Planejado Acumulado"], "bottom": "0%"},
            "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
            "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
            "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": eixo_x_l1},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "Realizado Acumulado", "type": "line", "smooth": True, "data": df_merge_vol["Real_Acum"].tolist(), "areaStyle": {"color": "rgba(59,130,246,0.15)"}, "lineStyle": {"color": "#3B82F6", "width": 3}, "itemStyle": {"color": "#3B82F6"}},
                {"name": "Planejado Acumulado", "type": "line", "smooth": True, "data": df_merge_vol["Plan_Acum"].tolist(), "lineStyle": {"type": "dashed", "color": "#64748B", "width": 3}, "itemStyle": {"color": "#64748B"}}
            ]
        }, height="350px", theme="streamlit", key="gov_prod_acum_new")

    # ==========================================
    # LINHA 2: Produtividade Individual (Criticidade) + Esforço + Heatmap
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    col_l2_c1, col_l2_c2, col_l2_c3 = st.columns(3, gap="medium")

    with col_l2_c1:
        st.markdown("#### 👥 Produtividade Individual")
        st.caption("Distribuição do volume realizado por Criticidade de OS.")
        df_crit = df_gov_f.groupby("Criticidade").size().reset_index(name="Volume")
        st_echarts(options={
            "tooltip": {"trigger": "item"},
            "legend": {"orient": "horizontal", "bottom": "0%"},
            "series": [{
                "type": "pie", "radius": ["40%", "70%"],
                "data": [{"value": int(r["Volume"]), "name": str(r["Criticidade"])} for _, r in df_crit.iterrows()],
                "label": {"show": True, "formatter": "{c}"}
            }]
        }, height="320px", key="gov_donut_criticidade")

    with col_l2_c2:
        st.markdown("#### ⏱️ Esforço x Classificação")
        st.caption("Tempo médio consumido por tipo de classificação.")
        df_classif = df_gov_f.groupby("Classificacao").agg(Tempo_Medio=("Tempo_Minutos", "mean")).reset_index().sort_values("Tempo_Medio", ascending=True)
        st_echarts(options={
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": df_classif["Classificacao"].tolist()},
            "series": [{"type": "bar", "data": df_classif["Tempo_Medio"].round(1).tolist(), "itemStyle": {"color": "#F59E0B"}}]
        }, height="320px", key="gov_esforco_classe_l2")

    with col_l2_c3:
        st.markdown("#### 🔁 Tipo de OS x Frequência")
        st.caption("Concentração de ordens por pátio e classificação.")
        agg_heatmap = df_gov_f.groupby(["Patio", "Classificacao"]).size().reset_index(name="Total")
        p_list, c_list, h_data, max_v = sorted(df_gov_f["Patio"].unique().tolist()), ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"], [], 0
        for yi, c_n in enumerate(c_list):
            for xi, p_n in enumerate(p_list):
                val = int(agg_heatmap[(agg_heatmap["Patio"] == p_n) & (agg_heatmap["Classificacao"] == c_n)]["Total"].iloc[0]) if not agg_heatmap[(agg_heatmap["Patio"] == p_n) & (agg_heatmap["Classificacao"] == c_n)].empty else 0
                h_data.append([xi, yi, val])
                if val > max_v: max_v = val
        st_echarts(options={
            "tooltip": {"position": "top"},
            "grid": {"height": "65%", "top": "5%", "bottom": "20%", "left": "20%"},
            "xAxis": {"type": "category", "data": p_list, "axisLabel": {"interval": 0, "rotate": 45}},
            "yAxis": {"type": "category", "data": c_list},
            "visualMap": {"min": 0, "max": max_v if max_v > 0 else 5, "orient": "horizontal", "left": "center", "bottom": "0%", "inRange": {"color": ["#F8FAFC", "#93C5FD", "#1D4ED8"]}},
            "series": [{"type": "heatmap", "data": h_data, "label": {"show": True}, "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 1.5}}]
        }, height="320px", key="gov_heatmap_l2")

    # ==========================================
    # ==========================================
    # LINHA 3: Aderência + Top Técnicos + Variabilidade (3 colunas)
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    col_l3_c1, col_l3_c2, col_l3_c3 = st.columns(3, gap="medium")

    with col_l3_c1:
        st.markdown("#### \U0001F552 Aderência: Login vs. Apontamento")
        st.caption("Horário de login (Azul) vs primeira baixa (Verde).")
        df_logs["Data_Real_Pure"] = pd.to_datetime(df_logs["data_hora_login"]).dt.date
        df_gov_f["dt_baixa_calc"] = pd.to_datetime(df_gov_f["data_fim"] + " " + df_gov_f["hora_fim"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df_primeira_baixa = df_gov_f.groupby(["concluido_por", "Data_Real"])["dt_baixa_calc"].min().reset_index(name="dt_baixa_1os")
        df_aderencia = df_logs.merge(df_primeira_baixa, left_on=["username", "Data_Real_Pure"], right_on=["concluido_por", "Data_Real"])

        if not df_aderencia.empty:
            df_aderencia["x_date"] = pd.to_datetime(df_aderencia["data_hora_login"]).dt.strftime("%d/%m")
            dt_login = pd.to_datetime(df_aderencia["data_hora_login"])
            df_aderencia["y_login_frac"] = dt_login.dt.hour + dt_login.dt.minute / 60.0
            dt_baixa = pd.to_datetime(df_aderencia["dt_baixa_1os"])
            df_aderencia["y_baixa_frac"] = dt_baixa.dt.hour + dt_baixa.dt.minute / 60.0
            df_aderencia = df_aderencia.sort_values("Data_Real_Pure")
            dates_list = sorted(df_aderencia["x_date"].unique().tolist())
            login_data = [[row["x_date"], round(row["y_login_frac"], 2), row["username"]] for _, row in df_aderencia.iterrows()]
            baixa_data = [[row["x_date"], round(row["y_baixa_frac"], 2), row["username"]] for _, row in df_aderencia.iterrows()]
            st_echarts(options={
                "tooltip": {
                    "trigger": "item",
                    "formatter": JsCode("""function (p) {
                        var hh = Math.floor(p.data[1]);
                        var mm = Math.round((p.data[1] - hh) * 60);
                        if (mm == 60) { hh += 1; mm = 0; }
                        var timeStr = (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm;
                        return '<b>' + p.data[2] + '</b><br>' + p.seriesName + ': ' + timeStr + '<br>Data: ' + p.data[0];
                    }""")
                },
                "legend": {"data": ["Login", "Primeira Baixa"], "bottom": "0%"},
                "toolbox": {"show": True, "feature": {
                    "dataView": {"show": True, "readOnly": True, "title": "Ver Dados",
                        "lang": ["Tabela de Dados", "Fechar", "Atualizar"],
                        "optionToContent": JsCode("""function(opt) {
                            var login = opt.series[0].data;
                            var baixa = opt.series[1].data;
                            var table = '<table style="width:100%;text-align:center;border-collapse:collapse;font-size:12px;"><thead><tr style="background:#F1F5F9;"><th style="padding:6px;border:1px solid #E2E8F0;">Data</th><th style="padding:6px;border:1px solid #E2E8F0;">Login</th><th style="padding:6px;border:1px solid #E2E8F0;">Primeira Baixa</th></tr></thead><tbody>';
                            var map = {};
                            function fmt(v) { var h=Math.floor(v); var m=Math.round((v-h)*60); if(m==60){h++;m=0;} return (h<10?'0':'')+h+':'+(m<10?'0':'')+m; }
                            for (var i=0; i<login.length; i++) { var d=login[i][0]; if(!map[d]) map[d]={l:'-',b:'-'}; map[d].l=fmt(login[i][1]); }
                            for (var i=0; i<baixa.length; i++) { var d=baixa[i][0]; if(!map[d]) map[d]={l:'-',b:'-'}; map[d].b=fmt(baixa[i][1]); }
                            for (var d in map) { table+='<tr><td style="padding:4px;border:1px solid #E2E8F0;">'+d+'</td><td style="padding:4px;border:1px solid #E2E8F0;">'+map[d].l+'</td><td style="padding:4px;border:1px solid #E2E8F0;">'+map[d].b+'</td></tr>'; }
                            table+='</tbody></table>'; return table;
                        }""")
                    },
                    "magicType": {"type": ["line", "scatter"], "title": {"line": "Linha", "scatter": "Dispersão"}},
                    "restore": {"title": "Restaurar"},
                    "saveAsImage": {"title": "Salvar Imagem"}
                }},
                "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
                "grid": {"top": "10%", "bottom": "25%", "left": "12%", "right": "5%"},
                "xAxis": {"type": "category", "data": dates_list},
                "yAxis": {
                    "type": "value", "name": "Horário", "min": 0, "max": 24, "interval": 4,
                    "axisLabel": {
                        "formatter": JsCode("""function(value) {
                            var hh = Math.floor(value);
                            return (hh < 10 ? '0' : '') + hh + ':00';
                        }""")
                    }
                },
                "series": [
                    {"name": "Login", "type": "scatter", "data": login_data, "symbolSize": 10, "itemStyle": {"color": "#3B82F6"}},
                    {"name": "Primeira Baixa", "type": "scatter", "data": baixa_data, "symbolSize": 10, "itemStyle": {"color": "#10B981"}}
                ]
            }, height="400px", theme="streamlit", key="gov_scatter_aderencia_colors")
        else:
            st.info("Dados insuficientes para cruzar login com apontamento.")

    with col_l3_c2:
        st.markdown("#### \U0001F51D Top Técnicos: OS por Pátio")
        st.caption("Distribuição da carga de trabalho por técnico e pátio.")
        df_freq = df_gov_f.groupby(["concluido_por", "Patio"]).size().reset_index(name="Qtd")
        tecnicos_top = df_freq["concluido_por"].unique().tolist()
        patios_top = sorted(df_freq["Patio"].unique().tolist())
        series_top = []
        for patio in patios_top:
            vals = []
            for tec in tecnicos_top:
                row_match = df_freq[(df_freq["concluido_por"] == tec) & (df_freq["Patio"] == patio)]
                vals.append(int(row_match["Qtd"].iloc[0]) if not row_match.empty else 0)
            series_top.append({"name": patio, "type": "bar", "stack": "total", "data": vals, "label": {"show": False}})

        st_echarts(options={
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"bottom": "0%", "textStyle": {"fontSize": 10}},
            "toolbox": {"show": True, "feature": {
                "dataView": {"show": True, "readOnly": True, "title": "Ver Dados", "lang": ["Tabela de Dados", "Fechar", "Atualizar"],
                    "optionToContent": JsCode("""function(opt) {
                        var axisData = opt.xAxis[0].data;
                        var series = opt.series;
                        var table = '<table style="width:100%;text-align:center;border-collapse:collapse;font-size:11px;"><thead><tr style="background:#F1F5F9;"><th style="padding:5px;border:1px solid #E2E8F0;">Técnico</th>';
                        for (var i=0; i<series.length; i++) { table += '<th style="padding:5px;border:1px solid #E2E8F0;">' + series[i].name + '</th>'; }
                        table += '<th style="padding:5px;border:1px solid #E2E8F0;font-weight:bold;">Total</th></tr></thead><tbody>';
                        for (var j=0; j<axisData.length; j++) {
                            table += '<tr><td style="padding:4px;border:1px solid #E2E8F0;font-weight:bold;">' + axisData[j] + '</td>';
                            var rowTotal = 0;
                            for (var i=0; i<series.length; i++) { var v = series[i].data[j] || 0; rowTotal += v; table += '<td style="padding:4px;border:1px solid #E2E8F0;">' + v + '</td>'; }
                            table += '<td style="padding:4px;border:1px solid #E2E8F0;font-weight:bold;">' + rowTotal + '</td></tr>';
                        }
                        table += '</tbody></table>'; return table;
                    }""")
                },
                "restore": {"title": "Restaurar"},
                "saveAsImage": {"title": "Salvar Imagem"}
            }},
            "grid": {"left": "5%", "right": "5%", "bottom": "18%", "top": "10%", "containLabel": True},
            "xAxis": {"type": "category", "data": tecnicos_top, "axisLabel": {"interval": 0, "rotate": 30, "fontSize": 10}},
            "yAxis": {"type": "value"},
            "series": series_top
        }, height="400px", theme="streamlit", key="gov_top_tec_echarts")

    with col_l3_c3:
        st.markdown("#### \U0001F4CA Variabilidade de Execução")
        st.caption("Tempo médio de execução (min) por colaborador.")
        df_var = df_gov_f.groupby("concluido_por")["Tempo_Minutos"].mean().reset_index().sort_values("Tempo_Minutos", ascending=True)
        st_echarts(options={
            "tooltip": {"trigger": "axis"},
            "toolbox": {"show": True, "feature": {
                "dataView": {"show": True, "readOnly": True, "title": "Ver Dados", "lang": ["Tabela de Dados", "Fechar", "Atualizar"]},
                "restore": {"title": "Restaurar"},
                "saveAsImage": {"title": "Salvar Imagem"}
            }},
            "grid": {"left": "5%", "right": "8%", "bottom": "10%", "top": "10%", "containLabel": True},
            "xAxis": {"type": "value", "name": "Minutos"},
            "yAxis": {"type": "category", "data": df_var["concluido_por"].tolist(), "axisLabel": {"fontSize": 10}},
            "series": [{"type": "bar", "data": df_var["Tempo_Minutos"].round(1).tolist(), "itemStyle": {"color": "#8B5CF6"}, "label": {"show": True, "position": "right", "formatter": "{c} min", "fontSize": 10}}]
        }, height="400px", theme="streamlit", key="gov_variab_echarts")


    # LINHA 5: Tabela de Auditoria de Apontamentos (GPS)
    # ==========================================
    st.markdown("---")
    st.markdown("#### 📍 Tabela de Auditoria de Apontamentos (GPS)")
    # ✅ CORREÇÃO 3: rename com "concluido_por" (nome real da coluna)
    df_auditoria = df_gov_f[["Ordem servico", "concluido_por", "data_inicio", "hora_fim", "geolocalizacao_baixa", "equipe", "Tempo_Minutos"]].copy().sort_values(by=["data_inicio", "hora_fim"], ascending=[False, False]).rename(columns={
        "Ordem servico": "OS",
        "concluido_por": "Apontador Principal",
        "data_inicio": "Data",
        "hora_fim": "Hora Apontada",
        "geolocalizacao_baixa": "Localização do Celular",
        "equipe": "Co-Executantes",
        "Tempo_Minutos": "Tempo Gasto (min)"
    })
    df_auditoria["Tempo Gasto (min)"] = df_auditoria["Tempo Gasto (min)"].round(0).astype(int)
    st.dataframe(df_auditoria.style.map(lambda v: 'background-color: #FEE2E2; color: #991B1B; font-weight: bold;' if pd.notna(v) and ('Base' in str(v) or 'Sede' in str(v)) else 'color: #065F46;', subset=["Localização do Celular"]), use_container_width=True, height=300, hide_index=True)
    st.stop()
#endregion
#endregion