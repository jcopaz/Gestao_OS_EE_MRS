#region SESSÃO 1: Imports, Configurações e Funções de Base

#region 1.1: Imports
import io
import time
import math
import re
import os
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
from streamlit_echarts import st_echarts
from datetime import datetime, timezone, timedelta
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
            return psycopg2.pool.SimpleConnectionPool(  # pyright: ignore[reportAttributeAccessIssue]
                1, 20,
                dsn=st.secrets["NEON_POSTGRES_URL"],
                connect_timeout=10
            )
        except psycopg2.OperationalError as e:
            if tentativa == max_retries - 1:
                raise e # Se falhar 10 vezes, aí sim repassa o erro
            print(f"⚠️ Banco de dados Neon acordando... Tentativa {tentativa + 1} de {max_retries}. Aguardando 4 segundos.")
            time.sleep(4)
    raise RuntimeError("Falha ao inicializar o pool de conexões após todas as tentativas.")

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
            # Sem isso, uma query que falhou no meio (coluna inexistente, erro de rede,
            # valor invalido) devolvia a conexao ao pool com a transacao ABORTADA -- o
            # PROXIMO usuario a pegar essa mesma conexao (pool e compartilhado entre todas
            # as sessoes) levava "current transaction is aborted" na primeira query dele,
            # sem relacao alguma com o erro original. rollback() em conexao sem transacao
            # pendente (ja commitada ou nunca usada) e no-op seguro.
            conn.rollback()
            pool_conexoes.putconn(conn)
        except Exception:
            pass # Ignora erros ao devolver conexões mortas ao pool

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

_status_prazo  = {"REALIZADO"}
_status_atraso = {"REALIZADO FORA DA DATA DE PROGRAMAÇÃO", "REALIZADO FORA DO PRAZO"}
# ABER NRAV = vistoria feita a campo, mas atividade não concluída (linha ocupada/desvio).
# A OS continua aberta de fato (por isso soma em _status_aberto -- Roteirização/pendências/
# calendário seguem tratando como tarefa aberta), mas conta como Concluída só para o cálculo
# de Meta na Dashboard/Visão Gerencial (_status_concluida_dashboard / _status_aberto_dashboard).
_status_aberto = {"NÃO REALIZADO", "NAO REALIZADO", "PENDENTE", "ATRASADO", "ABER NRAV", ""}
_status_concluida_dashboard = _status_prazo | _status_atraso | {"ABER NRAV"}
_status_aberto_dashboard = _status_aberto - {"ABER NRAV"}
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes_operacionais (
                coordenacao VARCHAR(100) PRIMARY KEY,
                geofence_km NUMERIC(6,2) NOT NULL DEFAULT 2.0,
                trava_prioridade_ativa BOOLEAN NOT NULL DEFAULT TRUE,
                escopo_dados VARCHAR(50) NOT NULL DEFAULT 'todos',
                ordem_criterios VARCHAR(255) NOT NULL DEFAULT 'seguranca_operacional,criticidade,atraso,proximidade',
                ordem_criticidade VARCHAR(100) NOT NULL DEFAULT 'Muito Alta,Alta,Média,Baixa',
                vigente_desde TIMESTAMP NULL,
                vigente_ate TIMESTAMP NULL,
                atualizado_por VARCHAR(255), atualizado_em TIMESTAMP DEFAULT NOW()
            );
        """)

        # --- ATUALIZAÇÕES AUTOMÁTICAS DE ESTRUTURA ---
        try: cur.execute("ALTER TABLE configuracoes_operacionais ADD COLUMN IF NOT EXISTS vigente_desde TIMESTAMP NULL;")
        except Exception: conn.rollback()

        try: cur.execute("ALTER TABLE configuracoes_operacionais ADD COLUMN IF NOT EXISTS ordem_criticidade VARCHAR(100) NOT NULL DEFAULT 'Muito Alta,Alta,Média,Baixa';")
        except Exception: conn.rollback()

        try: cur.execute("ALTER TABLE configuracoes_operacionais ALTER COLUMN escopo_dados TYPE VARCHAR(50);")
        except Exception: conn.rollback()

        try: cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS governanca VARCHAR(255) DEFAULT 'Painel Gerencial,Mapa de Campo';")
        except Exception: conn.rollback()
        
        try: cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome VARCHAR(255);")
        except Exception: conn.rollback()
        
        try: cur.execute("ALTER TABLE os_programadas ADD COLUMN IF NOT EXISTS coordenacao VARCHAR(100);")
        except Exception: conn.rollback()

        try:
            # UNIQUE(ativo, atividade) fazia a foto de uma OS sobrescrever a de outra sempre que
            # duas execucoes caiam no mesmo ativo+atividade (comum em inspecoes recorrentes, e
            # sempre no caso da baixa offline, que gravava atividade="Baixa Offline" fixo para
            # toda OS do mesmo ativo). A foto era enviada normalmente, so era perdida no upsert.
            # Corrige a chave para os_referencia (uma linha de evidencia por OS de verdade).
            cur.execute("""
                DELETE FROM evidencias a USING evidencias b
                WHERE a.os_referencia = b.os_referencia
                  AND a.os_referencia IS NOT NULL AND a.os_referencia <> ''
                  AND a.id < b.id;
            """)
            cur.execute("ALTER TABLE evidencias DROP CONSTRAINT IF EXISTS evidencias_ativo_atividade_key;")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'evidencias_os_referencia_key') THEN
                        ALTER TABLE evidencias ADD CONSTRAINT evidencias_os_referencia_key UNIQUE (os_referencia);
                    END IF;
                END $$;
            """)
        except Exception: conn.rollback()

        try:
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS geolocalizacao_baixa VARCHAR(255);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS equipe TEXT;")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS data_inicio VARCHAR(50);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS hora_inicio VARCHAR(50);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS data_fim VARCHAR(50);")
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS hora_fim VARCHAR(50);")
            # atualizado_em (TIMESTAMP real) -- realizado_em e VARCHAR "DD/MM/AAAA HH:MM", e MAX()
            # em texto compara alfabeticamente, nao cronologicamente (dia "13" nao supera dia "23"
            # de um mes anterior). Isso fazia o cache de _hash_baixas() nao invalidar quando uma
            # baixa nova/atualizada tinha data lexicograficamente "menor" que o maximo ja no banco,
            # mantendo a OS aparecendo como pendente na Roteirizacao mesmo ja baixada (13/07/2026).
            cur.execute("ALTER TABLE baixas ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP DEFAULT NOW();")
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

#region 1.6: Persistência de Sessão (token HMAC na URL — sobrevive à câmera no mobile)
import hmac, base64

def _auth_secret():
    return st.secrets.get("AUTH_TOKEN_SECRET", "TROQUE-ESTE-SEGREDO-NO-SECRETS")

def gerar_token_sessao(username: str, ttl_horas: int = 12) -> str:
    exp = int(time.time()) + ttl_horas * 3600
    payload = f"{username}|{exp}"
    assin = hmac.new(_auth_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{assin}".encode()).decode()

def validar_token_sessao(token: str):
    try:
        bruto = base64.urlsafe_b64decode(token.encode()).decode()
        username, exp, assin = bruto.rsplit("|", 2)
        esperada = hmac.new(_auth_secret().encode(), f"{username}|{exp}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(esperada, assin):
            return None
        if int(exp) < int(time.time()):
            return None
        return username
    except Exception:
        return None
#endregion

# Restaura sessão a partir do token da URL (reconexão do WebSocket após a câmera)
if not st.session_state.get("logged_in"):
    _tok = st.query_params.get("sid")
    if _tok:
        _user_tok = validar_token_sessao(_tok)
        if _user_tok:
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT perfil, escopo, governanca FROM usuarios WHERE username = %s", (_user_tok,))
                _row = cur.fetchone()
                cur.close()
            finally:
                release_connection(conn)
            if _row:
                st.session_state.update({
                    "logged_in": True, "username": _user_tok,
                    "perfil": _row[0], "escopo": _row[1],
                    "governanca": _row[2] or "Mapa de Campo",
                    "validando_gps": False, "needs_reset": False,
                })

#region 2.1: Barreira de Login com Governança e GPS Obrigatório
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": "", "perfil": "", "escopo": "", "governanca": "", "needs_reset": False, "validando_gps": False})

if not st.session_state["logged_in"]:
    st.markdown("<h3 style='text-align: center; color: ##FFFFFF;'>Acesso Restrito</h3>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    
    with col_l2:
#endregion
#endregion SESSÃO 1

#region 2: Barreira de Login com Governança e GPS Obrigatório

#region 2.1: Etapa 3 — Reset de Senha
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
                        try:
                            cur = conn.cursor()
                            cur.execute("UPDATE usuarios SET senha_hash = %s, palavra_recuperacao = %s, reset_obrigatorio = 0 WHERE username = %s", (hash_senha(nova_senha), palavra_nova.strip(), st.session_state["reset_user"]))
                            conn.commit()
                            cur.close()
                        finally:
                            release_connection(conn)
                        st.success("Concluído! Entre com sua nova senha."); st.session_state["needs_reset"] = False; st.rerun()
            if st.button("⬅️ Voltar"): st.session_state["needs_reset"] = False; st.rerun()
#endregion

#region 2.2: Etapa 2 — GPS Obrigatório
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
                    try:
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO logs_acesso (username, data_hora_login, geolocalizacao_login)
                            VALUES (%s, CURRENT_TIMESTAMP, %s)
                        """, (st.session_state["temp_user"], geo_str))
                        conn.commit()
                        cur.close()
                    finally:
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

#region 2.3: Etapa 1 — Login Padrão
        else:
            with st.form("form_login"):
                user_input = st.text_input("Matrícula / Usuário")
                pass_input = st.text_input("Senha", type="password")
                submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT senha_hash, perfil, escopo, reset_obrigatorio, governanca FROM usuarios WHERE username = %s", (user_input.strip(),))
                    row = cur.fetchone()
                    cur.close()
                finally:
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
    # Correção de negócio validada com especialistas MRS (21/07/2026): não existe
    # "Confiabilidade e Segurança" -- toda OS é Segurança OU Confiabilidade, nunca as
    # duas. Regra simples por substring: qualquer coisa com "_SEG_" -> Segurança,
    # qualquer coisa com "_CONF_" -> Confiabilidade (default).
    s = str(atividade).upper()
    if "_SEG_" in s: return "Segurança"
    if "_CONF_" in s: return "Confiabilidade"
    return "Confiabilidade"

def extrair_grupo_ativo(atividade: str) -> str:
    # Extrai o "Grupo de Ativo" a partir do código da Atividade Ativo (coluna D da Base de
    # OS): tudo o que vem depois do marcador "_C_I_"/"_S_I_" e antes do próximo "_" (que
    # antecede o código numérico final, ex.: "_0180"). Regra e exceção validadas com o
    # Julio em 22/07/2026 a partir de dado real:
    #   EE_INS_CONF_S_I_CAIXA DE LOCAÇÃO_0180 -> "CAIXA DE LOCAÇÃO"
    #   EE_INS_CONF_C_I_BARRAMENTO 3KV_0360   -> "BARRAMENTO 3KV"
    #   EE_INS_CONF_S_I_AES FIBRA OTICA_0090  -> "FIBRA OTICA" ("AES" é prefixo de
    #     site solto e é descartado -- só quando é a PRIMEIRA palavra isolada do trecho
    #     extraído; em "BAT ESTAC AES-FO" o "AES" faz parte do nome e não é removido).
    s = str(atividade).strip().upper()
    m = re.search(r"_[CS]_I_(.+?)_\d+$", s)
    if not m:
        return "N/D"
    grupo = m.group(1).strip()
    if grupo.startswith("AES "):
        grupo = grupo[4:].strip()
    return grupo or "N/D"

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
    # Segurança sempre à frente de Confiabilidade, em qualquer criticidade (base 1x < 2x);
    # dentro de cada classificação, criticidade_rank (1=Muito Alta..4=Baixa) desempata.
    base_map = {"Segurança": 1, "Confiabilidade": 2}
    base = base_map.get(classificacao, 2)
    return base * 10 + int(criticidade_rank)
#endregion 3.1.2

#region 3.1.3: Funções de Data/Hora e Status de Execução
def parse_data_programada(valor):
    if pd.isna(valor): return pd.NaT
    s = str(valor).strip()
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}', s):          # já ISO -> não inverter
            return pd.to_datetime(s, errors="coerce")
        return pd.to_datetime(s, dayfirst=True, errors="coerce")   # DD/MM/AAAA
    except Exception:
        return pd.NaT

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
def carregar_malha_cacheada(caminho="malha_mrs.kml"):
    """Lê o KML da malha, normaliza CRS, mantém apenas linhas e simplifica."""
    if not os.path.exists(caminho):
        st.warning(f"KML não encontrado: {caminho}")
        return None

    import geopandas as gpd

    try:
        gdf = gpd.read_file(caminho, driver="KML")

        if gdf is None or gdf.empty or "geometry" not in gdf.columns:
            st.warning("KML carregado, mas sem geometrias válidas.")
            return None

        gdf = gdf.dropna(subset=["geometry"]).copy()
        gdf = gdf[~gdf.geometry.is_empty].copy()

        # Normaliza CRS para renderização no Folium
        if gdf.crs is not None:
            gdf = gdf.to_crs("EPSG:4326")

        # Explode geometrias compostas
        try:
            gdf = gdf.explode(index_parts=False).reset_index(drop=True)
        except Exception:
            pass

        # Mantém apenas o que o mapa atual sabe desenhar
        gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()

        if gdf.empty:
            st.warning("O KML foi lido, mas não contém LineString/MultiLineString para desenhar.")
            return None

        # Simplificação visual para performance
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.005, preserve_topology=True)

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

@st.cache_data(show_spinner=False, ttl=3600)
def reverse_geocode_coordenada(lat: float, lon: float) -> str:
    try:
        geolocator = Nominatim(user_agent="sgo_mrs_app")
        location = geolocator.reverse((float(lat), float(lon)), exactly_one=True, timeout=10, language="pt")  # pyright: ignore[reportArgumentType]
        if location and getattr(location, "address", None):
            return str(location.address)  # pyright: ignore[reportAttributeAccessIssue]
        if location and isinstance(location, dict) and location.get("display_name"):
            return str(location.get("display_name"))
    except Exception:
        pass
    return f"{float(lat):.6f}, {float(lon):.6f}"
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
            INSERT INTO baixas (os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim, atualizado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (os) DO UPDATE SET
                status = EXCLUDED.status, realizado_em = EXCLUDED.realizado_em, concluido_por = EXCLUDED.concluido_por,
                geolocalizacao_baixa = EXCLUDED.geolocalizacao_baixa, equipe = EXCLUDED.equipe, data_inicio = EXCLUDED.data_inicio,
                hora_inicio = EXCLUDED.hora_inicio, data_fim = EXCLUDED.data_fim, hora_fim = EXCLUDED.hora_fim, atualizado_em = NOW();
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
        # Fallback caso a coluna ainda não exista em algum ambiente. Sem o rollback, a
        # transacao seguia ABORTADA depois do erro acima -- essa segunda query tambem
        # falharia ("current transaction is aborted"), estourando pra fora da funcao.
        conn.rollback()
        df = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa FROM baixas", conn)
    finally: 
        release_connection(conn)
        
    if not df.empty: df["os"] = df["os"].astype(str)
    return df
#endregion

#region 3.3: Supabase Storage (Evidências Fotográficas com Compressão)
def _sanear_nome_arquivo(texto: str) -> str:
    """Remove acentos (NFKD) e força ASCII puro -- \\w do Python é Unicode-aware por
    padrão e deixa letras acentuadas passarem (ex.: "RELÉ"), que o Supabase Storage
    rejeita na chave do objeto com 400 InvalidKey. Mesma técnica de _normalizar_nome_coluna."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"[^\w\-.]", "_", texto, flags=re.ASCII)

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
            ON CONFLICT (os_referencia) DO UPDATE SET
                ativo = EXCLUDED.ativo, atividade = EXCLUDED.atividade, foto_url = EXCLUDED.foto_url,
                concluido_por = EXCLUDED.concluido_por, geolocalizacao = EXCLUDED.geolocalizacao, data_upload = CURRENT_TIMESTAMP;
        """, (str(ativo), str(atividade), str(foto_url), str(os_referencia), str(concluido_por), str(geolocalizacao)))
        conn.commit()
        cur.close()
    finally: release_connection(conn)

@st.cache_data(show_spinner=False, ttl=300)
def carregar_evidencias_df() -> pd.DataFrame:
    # Cache adicionado em 22/07/2026 -- plano Neon Free (Network transfer perto do teto de
    # 5GB/mes). Sem cache, essa tabela inteira era relida do banco a cada rerun da Lista
    # Detalhada de OS. TTL curto (5min) pra não deixar link de evidência muito desatualizado.
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

    # Rateio de "Trab. real" por grupo de apontamento simultâneo (mesmo executor e mesmo
    # horário de início/fim — caso de "baixa em massa" com um único horário para várias OS).
    # Bug corrigido: o cálculo antigo devolvia "HH,MM" (ex.: "03,48"), que o SAP lê como
    # minutos decimais (3,48 min) já que a coluna UN Medida está em MIN — 3 horas viravam
    # 3 minutos. Agora o campo sempre sai em minutos inteiros totais.
    def _duracao_minutos(h_ini, h_fim):
        try:
            t_ini = pd.to_datetime(h_ini, format='%H:%M:%S')
            t_fim = pd.to_datetime(h_fim, format='%H:%M:%S')
            diff = (t_fim - t_ini).total_seconds() / 60.0
            if diff < 0: diff += 24 * 60
            return diff
        except Exception: return 0.0

    df_sap["_duracao_min"] = df_sap.apply(lambda r: _duracao_minutos(r['hora_inicio'], r['hora_fim']), axis=1)
    df_sap["_hh_plano_min"] = (
        pd.to_numeric(df_sap["Hxh Plano"], errors="coerce").fillna(0.0) * 60.0
        if "Hxh Plano" in df_sap.columns else 0.0
    )

    def _ratear_grupo(grupo: pd.DataFrame) -> pd.Series:
        # Todas as linhas do grupo compartilham o mesmo horário de início/fim -> mesma duração total.
        total_min = round(grupo["_duracao_min"].iloc[0])
        n = len(grupo)
        if n == 1:
            return pd.Series([total_min], index=grupo.index)

        soma_plano = grupo["_hh_plano_min"].sum()
        # Sem HH planejado para ratear (planilha sem "Hxh Plano"): divide o tempo igualmente
        # entre as OS do grupo em vez de creditar o tempo cheio em cada uma.
        pesos = grupo["_hh_plano_min"] / soma_plano if soma_plano > 0 else pd.Series([1.0 / n] * n, index=grupo.index)

        brutos = total_min * pesos
        base = np.floor(brutos).astype(int)
        # Método do maior resto: distribui os minutos que sobraram do arredondamento para as
        # OS com a maior fração fracionária, garantindo que a soma bata exatamente com o total apontado.
        falta = int(total_min) - int(base.sum())
        restos_ordenados = (brutos - base).sort_values(ascending=False).index
        for idx_os in list(restos_ordenados)[:max(falta, 0)]:
            base[idx_os] += 1
        return base

    df_sap["_trab_real_min"] = 0
    _chave_grupo = ["concluido_por", "data_inicio", "hora_inicio", "data_fim", "hora_fim"]
    for _, idxs in df_sap.groupby(_chave_grupo, dropna=False).groups.items():
        df_sap.loc[idxs, "_trab_real_min"] = _ratear_grupo(df_sap.loc[idxs])

    df_sap["_lista_equipe"] = df_sap.apply(montar_lista_equipe, axis=1)
    df_sap_explodido = df_sap.explode("_lista_equipe").rename(columns={"_lista_equipe": "matricula_final"}).reset_index(drop=True)
    df_sap_explodido = df_sap_explodido.drop(columns=["_lista_equipe"], errors="ignore")

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
        'Trab. real': df_sap_explodido['_trab_real_min'].astype(int).astype(str).values,
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
    df_visao["dt_realizado"] = df_visao["Data/Hora Realizado"].apply(parse_datahora_realizado)  # pyright: ignore[reportCallIssue, reportArgumentType]
    df_visao["Turno"] = df_visao["dt_realizado"].apply(classificar_turno)
    df_visao["dia_realizado"] = pd.to_datetime(df_visao["dt_realizado"], errors="coerce").dt.normalize()
    df_visao["dt_prog_filtro"] = pd.to_datetime(df_visao["Data inicial programada"], errors="coerce")
    df_visao["Turno_Filtro"] = df_visao["Turno"].fillna("Pendente (Sem Turno)")

    if "TIPO_INTERVALO_CAN" in df_visao.columns and "Tipo_Intervalo" not in df_visao.columns:
        df_visao["Tipo_Intervalo"] = df_visao["TIPO_INTERVALO_CAN"]

    return df_visao


def aplicar_filtros_sidebar(
    df_visao: pd.DataFrame, patios_selecionados: list, classif_selecionadas: list,
    turnos_selecionados: list, start_date, end_date, status_sel: str = "Todos", intervalo_sel: str = "Todas",
    crit_selecionadas: list | None = None, exec_start_date=None, exec_end_date=None,
    grupos_ativo_selecionados: list | None = None, ativos_selecionados: list | None = None
) -> pd.DataFrame:
    df = df_visao.copy()
    if "dt_prog_filtro" in df.columns:
        mask_data = ((df["dt_prog_filtro"].dt.date >= start_date) & (df["dt_prog_filtro"].dt.date <= end_date)) | df["dt_prog_filtro"].isna()
        df = df[mask_data]
    if exec_start_date is not None and exec_end_date is not None and "dt_realizado" in df.columns:
        _exec = pd.to_datetime(df["dt_realizado"], errors="coerce")
        # Filtro de Execução: mantém OS realizadas dentro do período OU ainda pendentes (dt_realizado NaT).
        # Sem o OR de isna(), OS planejadas mas ainda não executadas eram excluídas quando o filtro de
        # Execução era combinado com o de Programação, zerando o Backlog e inflando a Taxa de Conclusão para 100%.
        mask_exec = ((_exec.dt.date >= exec_start_date) & (_exec.dt.date <= exec_end_date)) | _exec.isna()
        df = df[mask_exec]
    if crit_selecionadas and "Criticidade" in df.columns:
        df = df[df["Criticidade"].isin(crit_selecionadas)]
    if patios_selecionados: 
        df = df[df["Patio"].isin(patios_selecionados)]
    if classif_selecionadas:
        df = df[df["Classificacao"].isin(classif_selecionadas)]
    if grupos_ativo_selecionados and "Grupo_Ativo" in df.columns:
        df = df[df["Grupo_Ativo"].isin(grupos_ativo_selecionados)]
    if ativos_selecionados and "Ativo" in df.columns:
        df = df[df["Ativo"].isin(ativos_selecionados)]
    if turnos_selecionados and "Turno_Filtro" in df.columns:
        df = df[df["Turno_Filtro"].isin(turnos_selecionados)]
    if status_sel != "Todos" and "Status_norm" in df.columns:
        if status_sel == "Todas Concluídas": df = df[df["Status_norm"].isin(_status_concluida_dashboard)]
        elif status_sel == "Concluídas no Prazo": df = df[df["Status_norm"].isin(_status_prazo | {"ABER NRAV"})]
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
    if "dt_realizado" not in df.columns: df["dt_realizado"] = df["Data/Hora Realizado"].apply(parse_datahora_realizado)  # pyright: ignore[reportCallIssue, reportArgumentType]
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
                df_hist.style.set_properties(**{'text-align': 'center'}).set_table_styles(  # pyright: ignore[reportArgumentType]
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
        st.caption(
            "Escolha o período de execução -- a exportação só consulta as OS concluídas "
            "dentro desse intervalo, em vez de puxar a base inteira do Neon a cada geração."
        )

        col_sap_p1, col_sap_p2 = st.columns(2)
        with col_sap_p1:
            sap_data_ini = st.date_input(
                "Período de Execução — Início", value=agora_dt().date() - timedelta(days=7),
                key="sap_export_data_ini", format="DD/MM/YYYY"
            )
        with col_sap_p2:
            sap_data_fim = st.date_input(
                "Período de Execução — Fim", value=agora_dt().date(),
                key="sap_export_data_fim", format="DD/MM/YYYY"
            )

        if st.button("📦 Preparar Arquivo SAP (Massa)", use_container_width=False, type="primary"):
            if sap_data_ini > sap_data_fim:
                st.error("⛔ A data de início não pode ser depois da data de fim.")
            else:
                with st.spinner("Preparando exportação..."):
                    # Consulta enxuta: só as OS com baixa DENTRO do período escolhido, direto
                    # em "baixas" (texto, leve) -- decide o que puxar de os_programadas
                    # (JSONB, o que mais pesa) ANTES de carregar qualquer coisa, em vez de
                    # trazer a base inteira e filtrar depois em memória.
                    conn = get_connection()
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            """
                            SELECT os, status FROM baixas
                            WHERE status IN %s
                              AND TO_TIMESTAMP(realizado_em, 'DD/MM/YYYY HH24:MI') >= %s
                              AND TO_TIMESTAMP(realizado_em, 'DD/MM/YYYY HH24:MI') < %s
                            """,
                            (
                                tuple(_status_prazo | _status_atraso),
                                datetime.combine(sap_data_ini, datetime.min.time()),
                                datetime.combine(sap_data_fim + timedelta(days=1), datetime.min.time()),
                            )
                        )
                        linhas_periodo = cur.fetchall()
                        cur.close()
                    finally:
                        release_connection(conn)

                    if not linhas_periodo:
                        st.info("⚠️ Nenhuma OS concluída no período selecionado.")
                    else:
                        lista_os_periodo = tuple(str(r[0]).strip() for r in linhas_periodo)
                        mapa_status_periodo = {str(r[0]).strip(): str(r[1]).strip().upper() for r in linhas_periodo}

                        df_completo = carregar_base_sem_overlay(
                            st.session_state.get("escopo", "Todas"), ETL_VERSION,
                            lista_os_filtro=lista_os_periodo
                        )

                        if df_completo.empty:
                            st.info("⚠️ Nenhuma OS concluída no período selecionado.")
                        else:
                            df_completo["Status_norm"] = df_completo["Ordem servico"].astype(str).str.strip().map(mapa_status_periodo).fillna("")
                            df_completo = df_completo[df_completo["Status_norm"] != ""]
                            st.session_state["sap_massa_bytes"] = gerar_excel_sap_bytes(df_completo)
                            st.session_state["sap_massa_nome"] = (
                                f"Baixa_Massa_SAP_{sap_data_ini.strftime('%Y%m%d')}_a_{sap_data_fim.strftime('%Y%m%d')}.xlsx"
                            )
                            st.success(f"✅ Arquivo preparado com sucesso ({len(df_completo)} OS).")

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

        # 1. Trata números seriais exportados crus do Excel
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            try:
                numero = float(valor)
                if 20000 <= numero <= 60000:
                    dt = pd.Timestamp("1899-12-30") + pd.to_timedelta(numero, unit="D")
                    return dt.strftime("%d/%m/%Y")
            except Exception:
                pass

        # 2. Se o Excel já entregou como objeto Data (datetime nativo), extraímos no padrão BR
        if hasattr(valor, "strftime"):
            return valor.strftime("%d/%m/%Y")  # pyright: ignore[reportAttributeAccessIssue]

        texto = _limpar_texto(valor).replace(".", "/").replace("-", "/")

        # 3. BLINDAGEM MÁXIMA: Tenta o formato Brasileiro EXPLICITAMENTE primeiro
        try:
            dt = pd.to_datetime(texto, format="%d/%m/%Y")
            return dt.strftime("%d/%m/%Y")
        except Exception:
            pass

        # 4. Fallback: Se for formato com nome de mês (Ex: 26-jun-2026), o Pandas resolve
        dt = pd.to_datetime(texto, dayfirst=True, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%d/%m/%Y")

        return ""

    def _formatar_hora_iw47(valor):
        # ... (Deixe a função _formatar_hora_iw47 exatamente como está no seu código)
        if pd.isna(valor) or str(valor).strip() == "":
            return ""
        if hasattr(valor, "hour") and hasattr(valor, "minute"):
            return f"{int(valor.hour):02d}:{int(valor.minute):02d}:{int(getattr(valor, 'second', 0)):02d}"
        if isinstance(valor, pd.Timedelta):
            total_segundos = int(round(valor.total_seconds())) % 86400
            return f"{total_segundos // 3600:02d}:{(total_segundos % 3600) // 60:02d}:{total_segundos % 60:02d}"
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
            if 0 <= numero < 1:
                total_segundos = int(round(numero * 86400)) % 86400
                return f"{total_segundos // 3600:02d}:{(total_segundos % 3600) // 60:02d}:{total_segundos % 60:02d}"
            if 1 <= numero < 24:
                total_segundos = int(round(numero * 3600)) % 86400
                return f"{total_segundos // 3600:02d}:{(total_segundos % 3600) // 60:02d}:{total_segundos % 60:02d}"
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

        # BLINDAGEM MÁXIMA 2: Como sabemos que a data já saiu em DD/MM/YYYY, 
        # nós amarramos o Pandas para NUNCA inverter!
        return pd.to_datetime(
            f"{data_txt} {hora_txt}",
            format="%d/%m/%Y %H:%M:%S",
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
        # Prefixo exato (mesmo padrão do upload de OS Programadas, seção 3.8.1) -- "contém
        # IPG em qualquer parte do texto" dava falso positivo quando o Centro de Trabalho
        # trazia um código combinado/ambíguo, sobrescrevendo Paranapiacaba (selecionado
        # corretamente no dropdown pelo usuário) por Piaçaguera. Confirmado em 22/07/2026:
        # import de baixas em massa do IPA gravou coordenacao="Piaçaguera" em 3.810 linhas.
        centro = _normalizar_nome_coluna(valor)

        if centro.startswith("E.SP.IPG") or centro.startswith("PIACAGUERA"):
            return "Piaçaguera"

        if centro.startswith("E.SP.IPA") or centro.startswith("PARANAPIACABA"):
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

#region 3.8b: Configurações Operacionais (render_tela_config_operacional)
def render_tela_config_operacional():
    col_cfg_t1, col_cfg_t2 = st.columns([8, 2])
    with col_cfg_t1: st.title("🛠️ Configurações Operacionais")
    with col_cfg_t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Voltar ao Painel", use_container_width=True, key="btn_voltar_config_op"):
            st.session_state["tela_atual"] = "dashboard"; st.rerun()

    st.caption(
        "Ajustes por coordenação para cenários operacionais especiais (ex.: plano de guerra). "
        "Toda configuração salva aqui tem vigência definida — fora da janela, o sistema volta "
        "sozinho aos valores padrão."
    )

    if "msg_sucesso_config_op" in st.session_state:
        st.success(st.session_state["msg_sucesso_config_op"]); del st.session_state["msg_sucesso_config_op"]

    st.markdown("---")

    _rotulos_criterios = {
        "seguranca_operacional": "Segurança da Operação (Segurança Muito Alta > Confiabilidade Muito Alta > Confiabilidade Alta/Média/Baixa > Demais)",
        "criticidade": "Criticidade (desempate dentro do mesmo nível de segurança)",
        "atraso": "Atraso ao vencimento",
        "proximidade": "Proximidade geográfica",
    }
    _chave_por_rotulo = {v: k for k, v in _rotulos_criterios.items()}

    coord_sel = st.selectbox("Coordenação", ["Paranapiacaba", "Piaçaguera"], key="config_op_coord_sel")
    config_atual = carregar_config_operacional(coord_sel)

    conn_status = get_connection()
    try:
        cur_status = conn_status.cursor()
        cur_status.execute(
            "SELECT vigente_desde, vigente_ate FROM configuracoes_operacionais WHERE coordenacao = %s",
            (coord_sel,)
        )
        row_status = cur_status.fetchone()
        cur_status.close()
    finally:
        release_connection(conn_status)

    agora = datetime.now()
    if row_status:
        v_desde, v_ate = row_status
        if v_desde is not None and agora < v_desde:
            st.info(f"🕒 Override de **{coord_sel}** agendado para começar em **{v_desde.strftime('%d/%m/%Y %H:%M')}**.")
        elif v_ate is not None and agora > v_ate:
            st.caption(f"Override de **{coord_sel}** expirou em {v_ate.strftime('%d/%m/%Y %H:%M')} — usando valores padrão.")
        elif v_desde is None and v_ate is None:
            st.caption(f"Nenhum override salvo para **{coord_sel}** — usando valores padrão.")
        else:
            _txt_janela = "sem prazo final" if v_ate is None else f"até **{v_ate.strftime('%d/%m/%Y %H:%M')}**"
            st.warning(f"⚠️ Override **ativo** para **{coord_sel}** {_txt_janela}.")
    else:
        st.caption(f"Nenhum override salvo para **{coord_sel}** — usando valores padrão.")

    # Planos disponíveis (planilhas de OS Programadas importadas) para o escopo de dados.
    conn_planos = get_connection()
    try:
        df_planos = pd.read_sql_query(
            "SELECT mes_referencia, MAX(data_upload) AS ultimo_upload FROM os_programadas "
            "WHERE coordenacao = %s AND mes_referencia IS NOT NULL AND mes_referencia <> '' "
            "GROUP BY mes_referencia ORDER BY ultimo_upload DESC",
            conn_planos, params=(coord_sel,)
        )
    except Exception:
        df_planos = pd.DataFrame(columns=["mes_referencia", "ultimo_upload"])
    finally:
        release_connection(conn_planos)

    planos_disponiveis = df_planos["mes_referencia"].dropna().astype(str).tolist()
    opcoes_escopo = ["Todas as OS Pendentes"] + [f"Plano de {p}" for p in planos_disponiveis]
    escopo_atual_label = (
        "Todas as OS Pendentes" if config_atual["escopo_dados"] == "todos"
        else f"Plano de {config_atual['escopo_dados']}"
    )
    if escopo_atual_label not in opcoes_escopo:
        opcoes_escopo.append(escopo_atual_label)

    with st.form("form_config_operacional"):
        trava_ativa = st.toggle(
            "Trava de prioridade ativa (Muito Alta bloqueia as demais)",
            value=config_atual["trava_prioridade_ativa"], key="config_op_trava"
        )
        geofence_km = st.number_input(
            "Geofence (km)", min_value=0.0, value=float(config_atual["geofence_km"]), step=0.5, key="config_op_geofence"
        )

        st.markdown("**Escopo de dados para as equipes**")
        escopo_dados_label = st.selectbox(
            "Base de OS usada na roteirização/pacote offline", opcoes_escopo,
            index=opcoes_escopo.index(escopo_atual_label), key="config_op_escopo"
        )
        if not planos_disponiveis:
            st.caption("Nenhuma planilha de OS Programadas com Mês de Referência preenchido para esta coordenação ainda.")

        st.markdown("---")
        st.markdown("**Ordem dos critérios de priorização** (clique na ordem desejada)")
        with st.expander("ℹ️ Como funciona a ordem padrão (referência)", expanded=False):
            st.markdown("""
O cascateamento funciona em camadas: o 1º critério decide a ordem primeiro; só quando duas OS
empatam nele é que o critério seguinte entra para desempatar.

| Camada | Critério | O que entra |
|---|---|---|
| 1 | 🔴 **TOP 1** | Segurança + Muito Alta |
| 2 | 🟠 **TOP 2** | Confiabilidade + Muito Alta |
| 3 | 🟡 **TOP 3** | Confiabilidade + Alta / Média / Baixa |
| 4 | ⚪ **TOP 4 (Demais)** | Tudo o que não se encaixa acima |

Dentro de cada TOP: **Criticidade → Atraso ao vencimento → Proximidade geográfica.**

**Tipo de Intervalo não entra nesse cascateamento** — ele é um filtro separado (Com Intervalo /
Sem Intervalo) que o técnico escolhe antes; dentro da fila escolhida, aplica-se o mesmo
cascateamento acima.

Ordem padrão do sistema: `Segurança da Operação → Criticidade → Atraso → Proximidade`.
            """)
        ordem_labels_default = [_rotulos_criterios[c] for c in config_atual["ordem_criterios"] if c in _rotulos_criterios]
        ordem_sel = st.multiselect(
            "Critérios", list(_rotulos_criterios.values()), default=ordem_labels_default,
            key="config_op_ordem", label_visibility="collapsed"
        )

        st.markdown("**Ordem de Criticidade** (filtro paralelo — reordena Muito Alta/Alta/Média/Baixa dentro do critério Criticidade)")
        ordem_crit_sel = st.multiselect(
            "Níveis", NIVEIS_CRITICIDADE_PADRAO, default=config_atual["ordem_criticidade"],
            key="config_op_ordem_criticidade", label_visibility="collapsed"
        )

        st.markdown("---")
        st.markdown("**Vigência** (obrigatória — fora dessa janela, volta ao padrão automaticamente)")
        col_vd1, col_vd2, col_vf1, col_vf2 = st.columns(4)
        with col_vd1:
            vigencia_desde_data = st.date_input("Início — data", value=datetime.now().date(), key="config_op_desde_data")
        with col_vd2:
            vigencia_desde_hora = st.time_input("Início — hora", value=datetime.now().time().replace(microsecond=0), key="config_op_desde_hora")
        with col_vf1:
            vigencia_ate_data = st.date_input("Fim — data", value=datetime.now().date() + pd.Timedelta(days=7), key="config_op_ate_data")
        with col_vf2:
            vigencia_ate_hora = st.time_input("Fim — hora", value=datetime.now().time().replace(microsecond=0), key="config_op_ate_hora")

        st.caption(
            "📶 **Importante:** pacotes offline já publicados (PWA) não leem a configuração nova sozinhos — "
            "eles são um arquivo estático gerado no momento da publicação. É preciso **republicar a rota** "
            "(Publicar Rota PWA) depois de salvar aqui para que os técnicos recebam a mudança offline. "
            "No fluxo online, a mudança já vale na próxima ação do usuário."
        )

        if st.form_submit_button("💾 Salvar Configuração", type="primary", use_container_width=True):
            ordem_final = [_chave_por_rotulo[l] for l in ordem_sel]
            for chave in CRITERIOS_ORDEM_PADRAO:
                if chave not in ordem_final: ordem_final.append(chave)

            ordem_crit_final = list(ordem_crit_sel)
            for nivel in NIVEIS_CRITICIDADE_PADRAO:
                if nivel not in ordem_crit_final: ordem_crit_final.append(nivel)

            escopo_dados_valor = (
                "todos" if escopo_dados_label == "Todas as OS Pendentes"
                else escopo_dados_label.replace("Plano de ", "", 1)
            )
            vigente_desde_dt = datetime.combine(vigencia_desde_data, vigencia_desde_hora)
            vigente_ate_dt = datetime.combine(vigencia_ate_data, vigencia_ate_hora)

            if vigente_ate_dt <= vigente_desde_dt:
                st.error("⛔ A data/hora de Fim precisa ser depois da data/hora de Início.")
            else:
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO configuracoes_operacionais
                            (coordenacao, geofence_km, trava_prioridade_ativa, escopo_dados, ordem_criterios,
                             ordem_criticidade, vigente_desde, vigente_ate, atualizado_por, atualizado_em)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (coordenacao) DO UPDATE SET
                            geofence_km = EXCLUDED.geofence_km, trava_prioridade_ativa = EXCLUDED.trava_prioridade_ativa,
                            escopo_dados = EXCLUDED.escopo_dados, ordem_criterios = EXCLUDED.ordem_criterios,
                            ordem_criticidade = EXCLUDED.ordem_criticidade, vigente_desde = EXCLUDED.vigente_desde,
                            vigente_ate = EXCLUDED.vigente_ate, atualizado_por = EXCLUDED.atualizado_por, atualizado_em = NOW()
                        """, (
                        coord_sel, geofence_km, trava_ativa, escopo_dados_valor, ",".join(ordem_final),
                        ",".join(ordem_crit_final), vigente_desde_dt, vigente_ate_dt,
                        st.session_state.get("username", "")
                    ))
                    conn.commit(); cur.close()
                finally:
                    release_connection(conn)

                st.cache_data.clear()
                st.session_state["msg_sucesso_config_op"] = (
                    f"Configuração de {coord_sel} salva — vigente de "
                    f"{vigente_desde_dt.strftime('%d/%m/%Y %H:%M')} até {vigente_ate_dt.strftime('%d/%m/%Y %H:%M')}."
                )
                st.rerun()
#endregion 3.8b

#region 3.8c: Gestão de Usuários (render_tela_gestao_usuarios)
def render_tela_gestao_usuarios():
    col_usr_t1, col_usr_t2 = st.columns([8, 2])
    with col_usr_t1: st.title("👥 Gestão de Usuários")
    with col_usr_t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬅️ Voltar ao Painel", use_container_width=True, key="btn_voltar_gestao_usuarios"):
            st.session_state["tela_atual"] = "dashboard"; st.rerun()

    st.caption(
        "Cadastro, edição, reset de senha e exclusão de colaboradores — e definição de quais "
        "telas cada perfil pode acessar (Governança)."
    )

    st.markdown("---")

    @st.fragment
    def fragmento_gestao_usuarios():
        if "msg_sucesso_user" in st.session_state: st.success(st.session_state["msg_sucesso_user"]); del st.session_state["msg_sucesso_user"]

        def sedes_por_escopo(escopo: str):
            if escopo == "Paranapiacaba": return ["Sede IPA"]
            elif escopo == "Piaçaguera": return ["Sede IPG"]
            return ["Sede IPA", "Sede IPG"]

        opcoes_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Gestão de Usuários", "Exportar SAP", "Governança", "Configurações Operacionais"]

        #region 8.2.1: Criar Novo Usuário (Formulário)
        with st.form("form_novo_user", clear_on_submit=True):
            n_user = st.text_input("Matrícula / Username", key="novo_user_login")
            n_nome = st.text_input("Nome do Colaborador", key="novo_user_nome")
            n_perf = st.selectbox("Perfil", ["Técnico", "Assistente", "Coordenador", "Gerência", "Administrador"], key="novo_user_perfil")
            n_esco = st.selectbox("Escopo (Base)", ["Paranapiacaba", "Piaçaguera", "Todas"], key="novo_user_escopo")
            sedes_validas = sedes_por_escopo(n_esco)
            n_sede = st.selectbox("Sede Física", sedes_validas, key="novo_user_sede", format_func=lambda x: x.replace("Sede ", ""))
            st.markdown("---")
            st.markdown("**Governança (O que o usuário pode ver/fazer?)**")

            if n_perf == "Técnico": def_gov = ["Mapa de Campo"]
            elif n_perf == "Assistente": def_gov = ["Painel Gerencial", "Upload de Dados", "Exportar SAP"]
            elif n_perf == "Coordenador": def_gov = ["Painel Gerencial", "Mapa de Campo", "Upload de Dados", "Exportar SAP", "Governança"]
            elif n_perf == "Administrador": def_gov = ["Configurações Operacionais"]
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
        try:
            df_usuarios = pd.read_sql_query("SELECT username, nome, perfil, escopo, coordenacao_padrao, governanca FROM usuarios", conn)
        finally:
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
                        n_perf_edit = st.selectbox("Novo Perfil", ["Técnico", "Assistente", "Coordenador", "Gerência", "Administrador"], index=["Técnico", "Assistente", "Coordenador", "Gerência", "Administrador"].index(dados_usr["perfil"]))
                        n_esco_edit = st.selectbox("Nova Visão", ["Paranapiacaba", "Piaçaguera", "Todas"], index=["Paranapiacaba", "Piaçaguera", "Todas"].index(dados_usr["escopo"]))
                        n_sede_edit = st.selectbox("Sede", sedes_por_escopo(n_esco_edit), format_func=lambda x: x.replace("Sede ", ""))
                        gov_editadas = st.multiselect("Governança:", opcoes_gov, default=[g for g in gov_atual_lista if g in opcoes_gov])

                        if st.form_submit_button("Salvar Alterações"):
                            conn = get_connection()
                            try:
                                cur = conn.cursor()
                                cur.execute("UPDATE usuarios SET nome=%s, perfil=%s, escopo=%s, coordenacao_padrao=%s, governanca=%s WHERE username=%s", (n_nome_edit.strip(), n_perf_edit, n_esco_edit, n_sede_edit, ",".join(gov_editadas), usr_sel))
                                conn.commit(); cur.close()
                            finally:
                                release_connection(conn)
                            st.session_state["msg_sucesso_user"] = f"Cadastro de {n_nome_edit} ({usr_sel}) atualizado!"
                            st.rerun(scope="fragment")
                elif acao == "🔑 Resetar Senha":
                    if st.button("Confirmar Reset", key="btn_reset_frag"):
                        conn = get_connection()
                        try:
                            cur = conn.cursor()
                            cur.execute("UPDATE usuarios SET senha_hash = %s, reset_obrigatorio = 1 WHERE username = %s", (hash_senha("mrs123"), usr_sel))
                            conn.commit(); cur.close()
                        finally:
                            release_connection(conn)
                        st.session_state["msg_sucesso_user"] = f"Senha de {dados_usr['nome']} ({usr_sel}) resetada!"
                        st.rerun(scope="fragment")
                elif acao == "🗑️ Excluir":
                    if st.button("Confirmar Exclusão", type="primary", key="btn_excluir_frag"):
                        conn = get_connection()
                        try:
                            cur = conn.cursor()
                            cur.execute("DELETE FROM usuarios WHERE username = %s", (usr_sel,))
                            conn.commit(); cur.close()
                        finally:
                            release_connection(conn)
                        st.session_state["msg_sucesso_user"] = f"Usuário {dados_usr['nome']} ({usr_sel}) excluído."
                        st.rerun(scope="fragment")
        else: st.info("Nenhum usuário cadastrado.")
        #endregion 8.2.2

        #region 8.2.3: Importação em Massa de Colaboradores
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
                            perfis_validos = {"Técnico", "Assistente", "Coordenador", "Gerência", "Administrador"}
                            escopos_validos = {"Paranapiacaba", "Piaçaguera", "Todas"}
                            registros, erros = [], []

                            for idx, row in df_users.iterrows():
                                idx = int(idx)  # pyright: ignore[reportArgumentType]
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
#endregion 3.8c

#region 3.9: Gerador Offline - Produção (HTML/JS completo)
def gerar_html_offline(df_pendentes: pd.DataFrame, usuario: str) -> bytes:
    if df_pendentes.empty:
        return b""

    df_pendentes = df_pendentes.copy()
    if "dt_prog_filtro" in df_pendentes.columns:
        df_pendentes["MesAno"] = pd.to_datetime(df_pendentes["dt_prog_filtro"], errors="coerce").dt.strftime("%m/%Y").fillna("")
    else:
        df_pendentes["MesAno"] = pd.to_datetime(df_pendentes.get("Data inicial programada"), errors="coerce").dt.strftime("%m/%Y").fillna("")  # pyright: ignore[reportCallIssue, reportArgumentType]

    colunas_export = ["Ordem servico", "Ativo", "Atividade ativo", "Patio", "Criticidade", "MesAno"]
    if "Tipo_Intervalo" in df_pendentes.columns:
        colunas_export.append("Tipo_Intervalo")
    else:
        df_pendentes["Tipo_Intervalo"] = "N/D"
        colunas_export.append("Tipo_Intervalo")
    if "Especialidade" in df_pendentes.columns:
        colunas_export.append("Especialidade")
    else:
        df_pendentes["Especialidade"] = "N/D"
        colunas_export.append("Especialidade")
    if "Descrição Longa" in df_pendentes.columns:
        colunas_export.append("Descrição Longa")

    df_export = df_pendentes[colunas_export].fillna("")

    # Sanitização crítica para evitar quebra de HTML/JS
    os_json = df_export.to_json(orient="records", force_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")

    # Equipe/matrícula do pacote offline só traz colegas da MESMA lotação (escopo) do dono
    # do pacote -- Paranapiacaba só vê Paranapiacaba, Piaçaguera só vê Piaçaguera. "Todas"
    # (perfis Gerência/Administrador) continua vendo todo mundo. Lista vazia no dropdown =
    # "Sozinho (Nenhum)" (mesma convenção do multiselect online), por isso não entra aqui.
    usuarios_equipe = []
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT escopo FROM usuarios WHERE username = %s", (usuario,))
        _row_escopo = cur.fetchone()
        escopo_dono = str(_row_escopo[0]).strip() if _row_escopo and _row_escopo[0] else "Todas"
        if escopo_dono == "Todas":
            cur.execute("SELECT username FROM usuarios")
        else:
            cur.execute("SELECT username FROM usuarios WHERE escopo = %s", (escopo_dono,))
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

    api_url_fixa = st.secrets.get(
        "OFFLINE_API_URL",
        "https://gestao-os-ee-mrs-producao.onrender.com/sincronizar_baixa_offline"
    )
    api_key_fixa = st.secrets.get("OFFLINE_API_KEY", "")

    # Trava de prioridade (Muito Alta bloqueia as demais) embutida no momento da publicação
    # do pacote — o HTML offline é um snapshot estático, então mudanças na configuração só
    # valem para pacotes republicados depois da alteração (mesma ressalva do fluxo de sync).
    if "Coordenacao" in df_pendentes.columns and not df_pendentes["Coordenacao"].dropna().empty:
        coordenacao_pacote = str(df_pendentes["Coordenacao"].dropna().mode().iloc[0]).strip()
    else:
        coordenacao_pacote = "Paranapiacaba"
    trava_prioridade_ativa_pacote = carregar_config_operacional(coordenacao_pacote)["trava_prioridade_ativa"]

    html_head = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SGO MRS - Modo Offline ({usuario})</title>
    <link rel="manifest" href="/manifest.webmanifest">
    <meta name="theme-color" content="#1E3A8A">
    <script>
    if ('serviceWorker' in navigator) {{
        window.addEventListener('load', function () {{
        navigator.serviceWorker.register('/sw.js', {{ scope: '/' }}).catch(function () {{}});
        }});
    }}
    </script>
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
        .ms {{ position: relative; }}
        .ms-btn {{ width: 100%; text-align: left; padding: 10px 12px; border: 1px solid #CBD5E1; border-radius: 10px; font-size: 14px; background: #FFFFFF; cursor: pointer; color: #0F172A; }}
        .ms-panel {{ display: none; position: absolute; z-index: 30; top: calc(100% + 4px); left: 0; right: 0; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; box-shadow: 0 8px 20px rgba(15,23,42,0.18); padding: 8px; max-height: 260px; overflow-y: auto; }}
        .ms-panel.open {{ display: block; }}
        .ms-search {{ width: 100%; padding: 8px 10px; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 13px; margin-bottom: 8px; }}
        .ms-option {{ display: flex; align-items: center; gap: 8px; padding: 7px 4px; font-size: 14px; border-radius: 6px; cursor: pointer; }}
        .ms-option:hover {{ background: #F1F5F9; }}
        .ms-option input {{ width: auto; margin: 0; }}
        .ms-empty {{ font-size: 13px; color: #94A3B8; padding: 6px 4px; }}
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
        body.modo-horario-unico .os-time-individual {{ display: none; }}
        .os-meta {{ font-size: 13px; color: #475569; margin: 4px 0; }}
        .desc-box {{ padding: 10px; background: #F8FAFC; border-radius: 10px; border: 1px solid #E2E8F0; font-size: 13px; color: #334155; }}
        .small {{ font-size: 12px; color: #64748B; }}
        .footer-space {{ height: 24px; }}
        @media (max-width: 768px) {{
            .toolbar, .toolbar-3, .os-grid {{ grid-template-columns: 1fr; }}
            .os-header {{ flex-direction: column; align-items: flex-start; }}
        }}
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
                        <label for="filtroEspecialidade">🛠️ Filtrar por Especialidade</label>
                        <select id="filtroEspecialidade">
                            <option value="">Todas as Especialidades</option>
                        </select>
                    </div>
                    <div class="field">
                        <label>🔍 Filtrar por Ativo (vazio = todos)</label>
                        <div class="ms" id="msAtivo">
                            <button type="button" class="ms-btn" id="msAtivoBtn">Todos os Ativos ▾</button>
                            <div class="ms-panel" id="msAtivoPanel">
                                <input type="text" class="ms-search" id="msAtivoSearch" placeholder="Buscar ativo...">
                                <div class="ms-list" id="msAtivoList"></div>
                            </div>
                        </div>
                    </div>
                    <div class="field">
                        <label for="filtroMes">🗓️ Filtrar por Mês</label>
                        <select id="filtroMes">
                            <option value="">Todos os Meses</option>
                        </select>
                    </div>
                    <div class="field">
                        <label>🧰 Tipo de Intervalo</label>
                        <div class="toolbar-3" style="gap:6px;">
                            <button type="button" id="btnIntTodas" class="btn btn-primary">Todas</button>
                            <button type="button" id="btnIntCI" class="btn btn-secondary">CI</button>
                            <button type="button" id="btnIntSI" class="btn btn-secondary">SI</button>
                        </div>
                    </div>
                    <div class="field">
                        <label>👥 Acompanhante / Equipe (aplica a todas as OS — vazio = sozinho)</label>
                        <div class="ms" id="msEquipe">
                            <button type="button" class="ms-btn" id="msEquipeBtn">Sozinho (Nenhum) ▾</button>
                            <div class="ms-panel" id="msEquipePanel">
                                <input type="text" class="ms-search" id="msEquipeSearch" placeholder="Buscar pessoa...">
                                <div class="ms-list" id="msEquipeList"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="field" style="margin-top: 12px;">
                    <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                        <input type="checkbox" id="horarioUnicoGlobal" checked style="width:auto; transform: scale(1.3);">
                        ⏱️ Usar um único horário para todas as OS (baixa em massa)
                    </label>
                </div>
                <div id="blocoHorarioUnico" class="os-grid" style="margin-top: 10px;">
                    <div class="field">
                        <label for="dataIniGlobal">Data Início (todas)</label>
                        <input id="dataIniGlobal" type="date">
                    </div>
                    <div class="field">
                        <label for="horaIniGlobal">Horário Início (todas)</label>
                        <input id="horaIniGlobal" type="time">
                    </div>
                    <div class="field">
                        <label for="dataFimGlobal">Data Fim (todas)</label>
                        <input id="dataFimGlobal" type="date">
                    </div>
                    <div class="field">
                        <label for="horaFimGlobal">Horário Fim (todas)</label>
                        <input id="horaFimGlobal" type="time">
                    </div>
                </div>

                <div id="criticaAlert" class="info-box info-yellow" style="display:none;">
                    ⚠️ <strong>Foco Operacional:</strong> Existem OS Críticas (Muito Alta). As demais do <strong>mesmo tipo de intervalo</strong> ficam bloqueadas até que estas sejam concluídas (Com Intervalo e Sem Intervalo são filas independentes).
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
    const TRAVA_PRIORIDADE_ATIVA = {json.dumps(trava_prioridade_ativa_pacote)};

    const DB_NAME = "sgo_mrs_offline_prod";
    const STORE_NAME = "apontamentos";
    let db = null;
    let gpsAtual = null;
    let filtroIntervalo = "";
    // OS ja gravadas na fila local (pendentes ou sincronizadas). Usado para NAO reexibir
    // uma OS baixada quando a lista e reconstruida (troca de filtro / reabertura do pacote).
    let osGravadasSet = new Set();

    async function carregarOsGravadas() {{
        return new Promise((resolve) => {{
            try {{
                const req = txStore("readonly").getAllKeys();
                req.onsuccess = () => {{
                    osGravadasSet = new Set((req.result || []).map((k) => String(k).trim()));
                    resolve(osGravadasSet);
                }};
                req.onerror = () => resolve(osGravadasSet);
            }} catch (e) {{ resolve(osGravadasSet); }}
        }});
    }}

    // Data local (considera o fuso do aparelho) no formato AAAA-MM-DD para os inputs de data.
    const HOJE_ISO = (function () {{
        const d = new Date();
        const off = d.getTimezoneOffset() * 60000;
        return new Date(d - off).toISOString().slice(0, 10);
    }})();

    function setFiltroIntervalo(val) {{
        filtroIntervalo = val;
        const ativos = {{ "": "btnIntTodas", "Com Intervalo": "btnIntCI", "Sem Intervalo": "btnIntSI" }};
        ["btnIntTodas", "btnIntCI", "btnIntSI"].forEach((id) => {{
            const b = document.getElementById(id);
            if (b) b.className = "btn " + (ativos[val] === id ? "btn-primary" : "btn-secondary");
        }});
        renderListaOS();
    }}

    function abrirDB() {{
        return new Promise((resolve, reject) => {{
            const req = indexedDB.open(DB_NAME, 2);
            req.onupgradeneeded = (event) => {{
                const database = event.target.result;
                if (database.objectStoreNames.contains(STORE_NAME)) {{
                    database.deleteObjectStore(STORE_NAME);
                }}
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

    // Dropdown de multisseleção pesquisável/recolhível (autorizado em reunião com os
    // Gestores). Reaproveitado tanto no filtro de Ativo quanto no de Equipe/Acompanhante --
    // fecha ao clicar fora, filtra por texto digitado, e o botão mostra um resumo da seleção.
    function criarMultiSelectDropdown(prefixo, placeholderVazio, onChange) {{
        const btn = document.getElementById(prefixo + "Btn");
        const panel = document.getElementById(prefixo + "Panel");
        const busca = document.getElementById(prefixo + "Search");
        const lista = document.getElementById(prefixo + "List");
        let opcoesAtuais = [];
        const selecionados = new Set();

        function atualizarBotao() {{
            if (selecionados.size === 0) btn.textContent = placeholderVazio + " ▾";
            else if (selecionados.size === 1) btn.textContent = [...selecionados][0] + " ▾";
            else btn.textContent = selecionados.size + " selecionados ▾";
        }}

        function renderLista(filtroTexto) {{
            const termo = String(filtroTexto || "").trim().toLowerCase();
            lista.innerHTML = "";
            const filtradas = opcoesAtuais.filter((op) => !termo || op.toLowerCase().includes(termo));
            if (filtradas.length === 0) {{
                const vazio = document.createElement("div");
                vazio.className = "ms-empty";
                vazio.textContent = "Nenhum resultado.";
                lista.appendChild(vazio);
                return;
            }}
            filtradas.forEach((op) => {{
                const linha = document.createElement("label");
                linha.className = "ms-option";
                const chk = document.createElement("input");
                chk.type = "checkbox";
                chk.checked = selecionados.has(op);
                chk.addEventListener("change", () => {{
                    if (chk.checked) selecionados.add(op); else selecionados.delete(op);
                    atualizarBotao();
                    if (onChange) onChange();
                }});
                const txt = document.createElement("span");
                txt.textContent = op;
                linha.appendChild(chk);
                linha.appendChild(txt);
                lista.appendChild(linha);
            }});
        }}

        btn.addEventListener("click", (e) => {{
            e.stopPropagation();
            const abrindo = !panel.classList.contains("open");
            panel.classList.toggle("open", abrindo);
            if (abrindo) {{ busca.value = ""; renderLista(""); busca.focus(); }}
        }});
        busca.addEventListener("input", () => renderLista(busca.value));
        busca.addEventListener("click", (e) => e.stopPropagation());
        document.addEventListener("click", (e) => {{
            if (!panel.contains(e.target) && e.target !== btn) panel.classList.remove("open");
        }});

        return {{
            setOptions(novasOpcoes) {{
                opcoesAtuais = novasOpcoes.slice();
                [...selecionados].forEach((s) => {{ if (!opcoesAtuais.includes(s)) selecionados.delete(s); }});
                atualizarBotao();
                renderLista(busca.value);
            }},
            getSelected() {{ return [...selecionados]; }}
        }};
    }}

    let msAtivo = null;
    let msEquipe = null;

    function popularEquipe() {{
        if (!msEquipe) return;
        msEquipe.setOptions(USUARIOS_EQUIPE.slice());
    }}

    function popularFiltroAtivos() {{
        if (!msAtivo) return;
        const ativosUnicos = [...new Set(
            OS_DATA.map(item => String(item.Ativo || "").trim()).filter(v => v)
        )].sort((a, b) => a.localeCompare(b, "pt-BR"));
        msAtivo.setOptions(ativosUnicos);
    }}

    function popularFiltroMeses() {{
        const sel = document.getElementById("filtroMes");
        if (!sel) return;

        sel.innerHTML = '<option value="">Todos os Meses</option>';

        const mesesUnicos = [...new Set(
            OS_DATA.map(item => String(item.MesAno || "").trim()).filter(v => v)
        )].sort((a, b) => {{
            const pa = a.split("/");
            const pb = b.split("/");
            return (pa[1] + pa[0]).localeCompare(pb[1] + pb[0]);
        }});

        mesesUnicos.forEach((mes) => {{
            const opt = document.createElement("option");
            opt.value = mes;
            opt.textContent = mes;
            sel.appendChild(opt);
        }});
    }}

    function popularFiltroEspecialidades() {{
        const sel = document.getElementById("filtroEspecialidade");
        if (!sel) return;

        sel.innerHTML = '<option value="">Todas as Especialidades</option>';

        const especialidadesUnicas = [...new Set(
            OS_DATA.map(item => String(item.Especialidade || "").trim()).filter(v => v && v.toUpperCase() !== "N/D")
        )].sort((a, b) => a.localeCompare(b, "pt-BR"));

        especialidadesUnicas.forEach((especialidade) => {{
            const opt = document.createElement("option");
            opt.value = especialidade;
            opt.textContent = especialidade;
            sel.appendChild(opt);
        }});
    }}

    function gruposCriticosBloqueados(lista) {{
        // Um grupo = (Ativo | Tipo de Intervalo). Só bloqueia as demais OS do MESMO
        // grupo. Assim, Muito Alta "Com Intervalo" não trava as "Sem Intervalo" e vice-versa.
        const grupos = new Set();
        lista.forEach((os) => {{
            if (String(os.Criticidade || "").trim().toUpperCase() === "MUITO ALTA") {{
                const ativo = String(os.Ativo || "").trim().toUpperCase();
                const intervalo = String(os.Tipo_Intervalo || "N/D").trim().toUpperCase();
                grupos.add(ativo + " | " + intervalo);
            }}
        }});
        return grupos;
    }}

    function contextoLocalInseguro() {{
        return !window.isSecureContext || !/^https?:$/i.test(window.location.protocol);
    }}

    function renderListaOS() {{
        // Multisseleção de Ativos: conjunto vazio = sem filtro (Todos os Ativos).
        const filtroSet = new Set(
            (msAtivo ? msAtivo.getSelected() : []).map(v => String(v || "").trim().toUpperCase())
        );
        const filtroMes = String(document.getElementById("filtroMes").value || "").trim();
        const filtroEspecialidadeEl = document.getElementById("filtroEspecialidade");
        const filtroEspecialidade = filtroEspecialidadeEl ? String(filtroEspecialidadeEl.value || "").trim().toUpperCase() : "";
        const osList = document.getElementById("osList");
        osList.innerHTML = "";

        const listaBase = OS_DATA
            .map((item, originalIdx) => ({{ ...item, _origIdx: originalIdx }}))
            .filter((item) => {{
                const ativo = String(item.Ativo || "").trim().toUpperCase();
                const mes = String(item.MesAno || "").trim();
                const interv = String(item.Tipo_Intervalo || "N/D").trim();
                const especialidade = String(item.Especialidade || "").trim().toUpperCase();
                const osId = String(item["Ordem servico"] || "").trim();
                return !osGravadasSet.has(osId)
                    && (filtroSet.size === 0 || filtroSet.has(ativo))
                    && (!filtroMes || mes === filtroMes)
                    && (!filtroIntervalo || interv === filtroIntervalo)
                    && (!filtroEspecialidade || especialidade === filtroEspecialidade);
            }});

        const gruposBloq = gruposCriticosBloqueados(listaBase);
        const criticaAlertEl = document.getElementById("criticaAlert");
        if (gruposBloq.size > 0 && TRAVA_PRIORIDADE_ATIVA) {{
            criticaAlertEl.className = "info-box info-yellow";
            criticaAlertEl.innerHTML = "⚠️ <strong>Foco Operacional:</strong> Existem OS Críticas (Muito Alta). As demais do <strong>mesmo tipo de intervalo</strong> ficam bloqueadas até que estas sejam concluídas (Com Intervalo e Sem Intervalo são filas independentes).";
            criticaAlertEl.style.display = "block";
        }} else if (gruposBloq.size > 0 && !TRAVA_PRIORIDADE_ATIVA) {{
            criticaAlertEl.className = "info-box info-blue";
            criticaAlertEl.innerHTML = "ℹ️ <strong>Foco Operacional (informativo):</strong> existem OS Críticas (Muito Alta) pendentes, mas a trava de bloqueio está desativada para esta coordenação (plano de guerra).";
            criticaAlertEl.style.display = "block";
        }} else {{
            criticaAlertEl.style.display = "none";
        }}

        listaBase.forEach((item) => {{
            const idx = item._origIdx;
            const osId = String(item["Ordem servico"] || "").trim();
            const ativo = String(item.Ativo || "").trim();
            const atividade = String(item["Atividade ativo"] || "").trim();
            const patio = String(item.Patio || "").trim();
            const criticidade = String(item.Criticidade || "").trim();
            const intervalo = String(item.Tipo_Intervalo || "N/D").trim();
            const especialidadeItem = String(item.Especialidade || "").trim();
            const desc = String(item["Descrição Longa"] || "").trim();
            const isCritica = criticidade.toUpperCase() === "MUITO ALTA";
            const grupoItem = ativo.toUpperCase() + " | " + intervalo.toUpperCase();
            const locked = !isCritica && gruposBloq.has(grupoItem) && TRAVA_PRIORIDADE_ATIVA;

            const wrapper = document.createElement("div");
            wrapper.className = "os-item" + (locked ? " locked" : "");
            wrapper.id = `card_os_${{idx}}`;

            wrapper.innerHTML = `
                <div class="os-header">
                    <div class="os-title">${{locked ? "🔒 " : ""}}OS ${{osId}}</div>
                    <div class="chip ${{isCritica ? "chip-critical" : ""}}">${{criticidade || "Sem criticidade"}}</div>
                </div>
                ${{locked ? `<div class="os-meta" style="color:#94A3B8;"><em>🔒 Bloqueada: conclua a OS Muito Alta do mesmo Ativo e tipo de intervalo para liberar.</em></div>` : ""}}

                <div class="os-meta"><strong>Ativo:</strong> ${{ativo}}</div>
                <div class="os-meta"><strong>Atividade:</strong> ${{atividade}}</div>
                <div class="os-meta"><strong>Pátio:</strong> ${{patio}}</div>
                ${{especialidadeItem && especialidadeItem.toUpperCase() !== "N/D" ? `<div class="os-meta"><strong>Especialidade:</strong> ${{especialidadeItem}}</div>` : ""}}
                ${{desc ? `<div class="desc-box" style="margin: 10px 0;"><strong>Descrição:</strong><br>${{desc}}</div>` : ""}}

                <div class="os-grid os-time-individual" style="margin-top: 10px;">
                    <div class="field">
                        <label for="dini_${{idx}}">Data Início</label>
                        <input id="dini_${{idx}}" type="date" value="${{HOJE_ISO}}" max="${{HOJE_ISO}}" ${{locked ? "disabled" : ""}}>
                    </div>
                    <div class="field">
                        <label for="ini_${{idx}}">Horário Início</label>
                        <input id="ini_${{idx}}" type="time" ${{locked ? "disabled" : ""}}>
                    </div>
                    <div class="field">
                        <label for="dfim_${{idx}}">Data Fim</label>
                        <input id="dfim_${{idx}}" type="date" value="${{HOJE_ISO}}" max="${{HOJE_ISO}}" ${{locked ? "disabled" : ""}}>
                    </div>
                    <div class="field">
                        <label for="fim_${{idx}}">Horário Fim</label>
                        <input id="fim_${{idx}}" type="time" ${{locked ? "disabled" : ""}}>
                    </div>
                </div>

                <div class="field">
                    <label for="foto_${{idx}}">📷 Evidência Fotográfica</label>
                    <input id="foto_${{idx}}" type="file" accept="image/jpeg,image/png" ${{locked ? "disabled" : ""}}>
                    <div class="small">Use a câmera ou a galeria pelo seletor do aparelho. Evitamos forçar a câmera para reduzir reinicialização por memória no Android.</div>
                </div>
            `;
            osList.appendChild(wrapper);
        }});
    }}

    async function capturarGPS() {{
        return new Promise((resolve) => {{
            if (contextoLocalInseguro()) {{
                gpsAtual = null;
                setGpsInfo(
                    "⛔ GPS indisponível: abra o pacote pelo atalho HTTPS/PWA (não pelo arquivo local). A localização é OBRIGATÓRIA para gravar a baixa.",
                    "red"
                );
                return resolve(null);
            }}

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
                    gpsAtual = null;
                    setGpsInfo(
                        `⛔ GPS falhou: ${{err.message}}. Ative a localização do aparelho e tente novamente. A localização é OBRIGATÓRIA para gravar a baixa.`,
                        "red"
                    );
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

    async function comprimirImagemArquivo(file) {{
        if (!file) return null;

        return new Promise((resolve) => {{
            try {{
                const url = URL.createObjectURL(file);
                const img = new Image();

                img.onload = () => {{
                    const maxW = 1600;
                    const maxH = 1600;
                    let w = img.width;
                    let h = img.height;

                    const scale = Math.min(maxW / w, maxH / h, 1);
                    w = Math.round(w * scale);
                    h = Math.round(h * scale);

                    const canvas = document.createElement("canvas");
                    canvas.width = w;
                    canvas.height = h;
                    const ctx = canvas.getContext("2d", {{ alpha: false }});
                    ctx.drawImage(img, 0, 0, w, h);

                    canvas.toBlob((blob) => {{
                        URL.revokeObjectURL(url);
                        if (!blob) {{
                            resolve(file);
                            return;
                        }}

                        const nomeBase = (file.name || "evidencia").replace(/\\.[^/.]+$/, "");
                        const novoArquivo = new File(
                            [blob],
                            `${{nomeBase}}.jpg`,
                            {{ type: "image/jpeg", lastModified: Date.now() }}
                        );
                        resolve(novoArquivo);
                    }}, "image/jpeg", 0.72);
                }};

                img.onerror = () => {{
                    URL.revokeObjectURL(url);
                    resolve(file);
                }};

                img.src = url;
            }} catch (e) {{
                resolve(file);
            }}
        }});
    }}
"""
#endregion 3.11

#region 3.12: Gerador Offline - Lógica JS de Lote / Persistência
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
        // GPS OBRIGATORIO: sem localizacao do navegador nao ha gravacao (removida a
        // dependencia do EXIF da foto). Tenta capturar na hora se ainda nao houver.
        if (!gpsAtual) {{
            await capturarGPS();
        }}
        if (!gpsAtual) {{
            alert("⛔ Localização obrigatória. Toque em '📍 Atualizar GPS Atual' com a localização do aparelho ativada antes de gravar. Se estiver no arquivo local, abra o pacote pelo atalho HTTPS/PWA.");
            return;
        }}

        const acompanhanteGlobal = (msEquipe ? msEquipe.getSelected() : []).join(", ");

        // Horario unico (baixa em massa): um horario replica para TODAS as OS com foto.
        const chkUnico = document.getElementById("horarioUnicoGlobal");
        const modoHorarioUnico = chkUnico ? chkUnico.checked : false;
        const gHoraIni = (document.getElementById("horaIniGlobal") || {{}}).value || "";
        const gHoraFim = (document.getElementById("horaFimGlobal") || {{}}).value || "";
        const gDataIni = (document.getElementById("dataIniGlobal") || {{}}).value || "";
        const gDataFim = (document.getElementById("dataFimGlobal") || {{}}).value || "";

        if (modoHorarioUnico && !(gHoraIni && gHoraFim)) {{
            alert("⏱️ Modo horário único ativo: preencha o Horário Início e o Horário Fim que serão aplicados a todas as OS.");
            return;
        }}

        const selecionadas = [];
        const indicesParaLimpar = [];
        let horariosSemFoto = 0;

        for (let i = 0; i < OS_DATA.length; i += 1) {{
            // So considera cards efetivamente renderizados (dentro do filtro atual). No modo
            // horario unico os campos de horario ficam sempre preenchidos; sem este guard,
            // OS fora do filtro seriam contabilizadas indevidamente.
            if (!document.getElementById(`card_os_${{i}}`)) continue;

            const elIni = document.getElementById(`ini_${{i}}`);
            const elFim = document.getElementById(`fim_${{i}}`);
            const elDIni = document.getElementById(`dini_${{i}}`);
            const elDFim = document.getElementById(`dfim_${{i}}`);
            const inicio = modoHorarioUnico ? gHoraIni : (elIni ? elIni.value : "");
            const fim = modoHorarioUnico ? gHoraFim : (elFim ? elFim.value : "");
            const dataIni = modoHorarioUnico ? gDataIni : (elDIni ? elDIni.value : "");
            const dataFim = modoHorarioUnico ? gDataFim : (elDFim ? elDFim.value : "");
            const fileInput = document.getElementById(`foto_${{i}}`);
            const fotoOriginal = (fileInput && fileInput.files && fileInput.files.length > 0) ? fileInput.files[0] : null;
            const osItem = OS_DATA[i];

            if (inicio && fim && !fotoOriginal) {{
                horariosSemFoto += 1;
                continue;
            }}

            if (!(inicio && fim && fotoOriginal)) continue;

            // Validação de datas/horas: permite dia anterior (turno que cruza a meia-noite),
            // mas bloqueia lançamento no futuro e fim anterior ao início.
            const iniHHMM = inicio.length === 5 ? inicio : inicio.slice(0, 5);
            const fimHHMM = fim.length === 5 ? fim : fim.slice(0, 5);
            const startDt = new Date(`${{dataIni || HOJE_ISO}}T${{iniHHMM}}:00`);
            const endDt = new Date(`${{dataFim || HOJE_ISO}}T${{fimHHMM}}:00`);
            const agoraDt = new Date();
            if (isNaN(startDt.getTime()) || isNaN(endDt.getTime())) {{
                alert(`OS ${{osItem["Ordem servico"]}}: informe data e hora de início e fim.`);
                return;
            }}
            if (endDt < startDt) {{
                alert(`OS ${{osItem["Ordem servico"]}}: o Fim (data/hora) é anterior ao Início.`);
                return;
            }}
            if (startDt > agoraDt || endDt > agoraDt) {{
                alert(`OS ${{osItem["Ordem servico"]}}: não é permitido lançar data/hora no futuro.`);
                return;
            }}
            const brData = (iso) => {{ const p = String(iso || "").split("-"); return p.length === 3 ? `${{p[2]}}/${{p[1]}}/${{p[0]}}` : ""; }};

            const duracaoHoras = calcularDuracaoHoras(inicio, fim);
            if (duracaoHoras !== null && duracaoHoras > 12) {{
                const ok = confirm(
                    `A duração calculada da OS ${{osItem["Ordem servico"]}} é de ${{duracaoHoras.toFixed(1)}}h. Confirma gravar mesmo assim?`
                );
                if (!ok) return;
            }}

            // GPS do navegador e obrigatorio (garantido no inicio da funcao), portanto NAO
            // dependemos mais do EXIF da foto. Comprimimos sempre para manter o payload leve.
            const fotoTratada = await comprimirImagemArquivo(fotoOriginal);

            selecionadas.push({{
                os_id: String(osItem["Ordem servico"] || "").trim(),
                ativo_id: String(osItem["Ativo"] || "").trim(),
                usuario: USUARIO_LOGADO,
                acompanhante: acompanhanteGlobal,
                horario_inicio: inicio.length === 5 ? `${{inicio}}:00` : inicio,
                horario_fim: fim.length === 5 ? `${{fim}}:00` : fim,
                data_inicio_exec: brData(dataIni),
                data_fim_exec: brData(dataFim),
                data_hora_local: endDt.toISOString(),
                lat_browser: gpsAtual.lat,
                lon_browser: gpsAtual.lon,
                criticidade: String(osItem["Criticidade"] || "").trim(),
                status_sync: "pendente",
                foto_blob: fotoTratada,
                foto_nome: fotoTratada && fotoTratada.name ? fotoTratada.name : "evidencia.jpg",
                criado_em: new Date().toISOString()
            }});

            indicesParaLimpar.push(i);
        }}

        if (!selecionadas.length) {{
            if (horariosSemFoto > 0) {{
                alert(`Existem ${{horariosSemFoto}} OS com horário preenchido, mas sem foto anexada. Anexe a evidência antes de gravar.`);
            }} else {{
                alert("Nenhuma OS preenchida para gravação.");
            }}
            return;
        }}

        await Promise.all(
            selecionadas.map((item) => new Promise((resolve, reject) => {{
                const req = txStore("readwrite").put(item);
                req.onsuccess = () => resolve(true);
                req.onerror = () => reject(req.error);
            }}))
        );

        selecionadas.forEach((it) => osGravadasSet.add(String(it.os_id).trim()));

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
        const ok = confirm("Deseja realmente apagar a fila de pendentes locais? OS ja sincronizadas continuam ocultas da lista.");
        if (!ok) return;

        // Apaga somente os registros "pendente". Preserva os "sincronizado", pois
        // osGravadasSet depende deles para nao reexibir uma OS ja baixada (bug: OS
        // sincronizada reaparecendo na lista apos "Limpar Filas e Reiniciar").
        await new Promise((resolve, reject) => {{
            const store = txStore("readwrite");
            const idx = store.index("status_sync");
            const req = idx.openCursor(IDBKeyRange.only("pendente"));
            req.onsuccess = (event) => {{
                const cursor = event.target.result;
                if (cursor) {{
                    cursor.delete();
                    cursor.continue();
                }} else {{
                    resolve(true);
                }}
            }};
            req.onerror = () => reject(req.error);
        }});

        await atualizarFila();
        setSyncMsg("Fila de pendentes apagada com sucesso.", "yellow");
    }}
"""
#endregion 3.12

#region 3.13: Gerador Offline - Lógica JS de Sincronização e Fechamento
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
                formData.append("data_inicio_exec", item.data_inicio_exec || "");
                formData.append("data_fim_exec", item.data_fim_exec || "");
                formData.append("foto", item.foto_blob, item.foto_nome || "evidencia.jpg");

                const resp = await fetch(apiUrl, {{
                    method: "POST",
                    headers: {{
                        "x-api-key": apiKey
                    }},
                    body: formData
                }});

                if (!resp.ok) {{
                    let msgErro = "Falha na comunicação com o servidor.";
                    try {{
                        const errJson = await resp.json();
                        if (errJson.detail) {{
                            msgErro = errJson.detail;
                        }} else {{
                            msgErro = JSON.stringify(errJson);
                        }}
                    }} catch (parseErr) {{
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
        await carregarOsGravadas();
        setStatusOnline();
        msAtivo = criarMultiSelectDropdown("msAtivo", "Todos os Ativos", renderListaOS);
        msEquipe = criarMultiSelectDropdown("msEquipe", "Sozinho (Nenhum)", null);
        popularEquipe();
        popularFiltroEspecialidades();
        popularFiltroAtivos();
        popularFiltroMeses();
        renderListaOS();
        await atualizarFila();

        window.addEventListener("online", setStatusOnline);
        window.addEventListener("offline", setStatusOnline);

        document.getElementById("filtroEspecialidade").addEventListener("change", renderListaOS);
        document.getElementById("filtroMes").addEventListener("change", renderListaOS);
        document.getElementById("btnIntTodas").addEventListener("click", () => setFiltroIntervalo(""));
        document.getElementById("btnIntCI").addEventListener("click", () => setFiltroIntervalo("Com Intervalo"));
        document.getElementById("btnIntSI").addEventListener("click", () => setFiltroIntervalo("Sem Intervalo"));
        document.getElementById("btnCapturarGps").addEventListener("click", capturarGPS);
        document.getElementById("btnSalvarLote").addEventListener("click", salvarSelecionadasNoLote);
        document.getElementById("btnSync").addEventListener("click", sincronizarFila);
        document.getElementById("btnClear").addEventListener("click", limparFila);

        // Horario unico (baixa em massa): default = ativado. Um horario replica p/ todas as OS.
        const diG = document.getElementById("dataIniGlobal");
        const dfG = document.getElementById("dataFimGlobal");
        if (diG) {{ diG.value = HOJE_ISO; diG.max = HOJE_ISO; }}
        if (dfG) {{ dfG.value = HOJE_ISO; dfG.max = HOJE_ISO; }}
        const chkUnico = document.getElementById("horarioUnicoGlobal");
        if (chkUnico) {{
            chkUnico.addEventListener("change", aplicarModoHorarioUnico);
            aplicarModoHorarioUnico();
        }}
    }}

    function aplicarModoHorarioUnico() {{
        const chk = document.getElementById("horarioUnicoGlobal");
        const ativo = chk ? chk.checked : true;
        document.body.classList.toggle("modo-horario-unico", ativo);
        const bloco = document.getElementById("blocoHorarioUnico");
        if (bloco) bloco.style.display = ativo ? "grid" : "none";
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
#endregion 3

#region SESSÃO 4: Banco de Coordenadas Fixo

#region 4.1: Coordenadas Fixa
COORDENADAS_FIXAS = {
    "FPI": [-23.444413, -46.309269], "IAA": [-23.867675, -46.400270], "IAB": [-23.521338, -46.688570],
    "IBA": [-23.915135, -46.321495], "ICB": [-23.886147, -46.416167], "ICG": [-23.767863, -46.343114],
    "ICP": [-23.658495, -46.490753], "ICQ": [-23.926493, -46.402720], "ICR": [-23.640310, -46.323992],
    "ICZ": [-23.954824, -46.293306], "IEF": [-23.477809, -46.360984], "IES": [-23.545441, -46.603648],
    "IIP": [-23.564977, -46.604896], "IJN": [-23.195297, -46.870829], "IJU": [-23.889626, -46.338534], 
    "ILA": [-23.520217, -46.698082], "IMO": [-23.557803, -46.608382], "IOF": [-23.658579, -46.338538],
    "IPA": [-23.774399, -46.306769], "IPG": [-23.847950, -46.370812], "IPR": [-23.537749, -46.625522],
    "IQA": [-23.928445, -46.363900], "IQB": [-23.876744, -46.347839], "IRA": [-23.500572, -46.339448], 
    "IRG": [-23.736705, -46.382241], "IRP": [-23.713578, -46.414862], "IRS": [-23.828162, -46.363101],
    "ISA": [-23.647553, -46.531007], "ISC": [-23.613874, -46.558834], "ISL": [-23.752383, -46.389262],
    "ISN": [-23.929330, -46.356448], "ISU": [-23.551210, -46.288671], "IUF": [-23.860615, -46.359726],  
    "IUT": [-23.624864, -46.544716], "IVP": [-23.848139, -46.390430], "OAR": [-23.500419, -46.339111],
    "OBF": [-23.525591, -46.666726], "OBR": [-23.545397, -46.616293], "OCE": [-23.484980, -46.481471],
    "OCV": [-23.525061, -46.333701], "OEG": [-23.498082, -46.519759], "OET": [-23.510887, -46.552273],
    "OGP": [-23.691962, -46.448784], "OIC": [-23.479040, -46.367395], "OIT": [-23.493970, -46.401392],
    "OLU": [-23.535423, -46.634503], "OMA": [-23.667910, -46.462083], "OMP": [-23.490530, -46.443668],
    "OPS": [-23.637494, -46.537198], "OSU": [-23.534010, -46.308025], "OTA": [-23.591863, -46.590075],
    "OTT": [-23.539844, -46.575501], "ZPD": [-22.363436, -48.711002], "ZPG": [-23.871816, -46.413018],
    "Sede IPA": [-23.767355, -46.344117], "Sede IPG": [-23.850772, -46.371760]
}
#endregion 4.1

#region 4.2: Configuração Operacional por Coordenação (Plano de Guerra)
CRITERIOS_ORDEM_PADRAO = ["seguranca_operacional", "criticidade", "atraso", "proximidade"]
NIVEIS_CRITICIDADE_PADRAO = ["Muito Alta", "Alta", "Média", "Baixa"]

DEFAULTS_CONFIG_OPERACIONAL = {
    "geofence_km": 2.0,
    "trava_prioridade_ativa": True,
    "escopo_dados": "todos",
    "ordem_criterios": list(CRITERIOS_ORDEM_PADRAO),
    "ordem_criticidade": list(NIVEIS_CRITICIDADE_PADRAO),
}

@st.cache_data(ttl=30)
def carregar_config_operacional(coordenacao: str) -> dict:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT geofence_km, trava_prioridade_ativa, escopo_dados, ordem_criterios, ordem_criticidade, "
            "vigente_desde, vigente_ate FROM configuracoes_operacionais WHERE coordenacao = %s",
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

    geofence_km, trava_ativa, escopo_dados, ordem_criterios, ordem_criticidade, vigente_desde, vigente_ate = row
    agora = datetime.now()
    # Config fora da janela de vigência (ainda não começou ou já passou) -> age como padrão.
    if (vigente_desde is not None and agora < vigente_desde) or (vigente_ate is not None and agora > vigente_ate):
        return dict(DEFAULTS_CONFIG_OPERACIONAL)

    return {
        "geofence_km": float(geofence_km),
        "trava_prioridade_ativa": bool(trava_ativa),
        "escopo_dados": escopo_dados or "todos",
        "ordem_criterios": [c.strip() for c in (ordem_criterios or "").split(",") if c.strip()] or list(CRITERIOS_ORDEM_PADRAO),
        "ordem_criticidade": [c.strip() for c in (ordem_criticidade or "").split(",") if c.strip()] or list(NIVEIS_CRITICIDADE_PADRAO),
    }
#endregion 4.2

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
ETL_VERSION = "v9_grupo_ativo"

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
    # Coluna "STATUS" (crua, coluna G da Base de OS) carrega códigos como ABER/ABER NRAV/CONC.
    # Em layouts que também têm "STATUS DA OPERAÇÃO" (sempre "Liberado" nesse formato), col_status
    # acima resolve para essa coluna morta -- por isso lemos "STATUS" separadamente aqui.
    col_status_raw = pick_first_existing(df, ["STATUS"])
    col_desc = pick_first_existing(df, ["DESCRIÇÃO LONGA", "DESCRICAO LONGA", "TEXTO LONGO"])
    # Cabeçalho real varia por coordenação ("ESPECIALIDADE IPA", "ESPECIALIDADE IPG", etc.) --
    # pega qualquer coluna que COMECE com "ESPECIALIDADE", em vez de exigir nome exato.
    col_especialidade = next((c for c in df.columns if str(c).strip().upper().startswith("ESPECIALIDADE")), None)

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
    df["DATA_PROG_CAN"] = df[col_data_prog].apply(parse_data_programada)  # pyright: ignore[reportCallIssue, reportArgumentType]
    df["DESC_LONGA_CAN"] = df[col_desc].astype(str).str.strip() if col_desc else ""
    df["ESPECIALIDADE_CAN"] = df[col_especialidade].astype(str).str.strip() if col_especialidade else "N/D"
    
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
    df["GRUPO_ATIVO_CAN"] = df["ATIVIDADE_CAN"].apply(extrair_grupo_ativo)
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
        st_raw = str(row[col_status_raw]).strip().upper() if col_status_raw and pd.notna(row[col_status_raw]) else ""
        if st_raw == "ABER NRAV": return "ABER NRAV"
        dp = row["DATA_PROG_CAN"]
        if pd.isna(dp): return "Pendente"
        if dp.date() >= hoje_data: return "Pendente"
        else: return "Atrasado"

    df["STATUS_CAN"] = df.apply(definir_status_cru, axis=1)

    df_out = pd.DataFrame({
        "Ordem servico": df[col_os].astype(str).str.strip(),
        "Patio": df["PATIO_CAN"], "Ativo": df["ATIVO_CAN"], "Atividade ativo": df["ATIVIDADE_CAN"],
        "Grupo_Ativo": df["GRUPO_ATIVO_CAN"],
        "Criticidade": df["Criticidade"], "Classificacao": df["Classificacao"], "Descrição Longa": df["DESC_LONGA_CAN"],
        "Data inicial programada": df["DATA_PROG_CAN"], "Status da Operação": df["STATUS_CAN"],
        "Data/Hora Realizado": "", "Concluído por": "", "Hxh Plano": df["HXH_CAN"],
        "Criticidade_rank": df["Criticidade_rank"], "Nivel_Prioridade": df["Nivel_Prioridade"],
        "TIPO_INTERVALO_CAN": df["TIPO_INTERVALO_CAN"], "Especialidade": df["ESPECIALIDADE_CAN"],
    })
    return df_out

@st.cache_data
def carregar_base_sem_overlay(escopo_usuario: str, etl_version: str, lista_os_filtro: tuple | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        # lista_os_filtro (opcional): restringe a consulta a um conjunto pequeno de OS --
        # usado pela Exportação SAP por período (região 3.8.4) pra não puxar dados_completos
        # (JSONB, o que mais pesa em transferência) da base inteira a cada exportação.
        if lista_os_filtro:
            placeholders = ",".join(["%s"] * len(lista_os_filtro))
            query_prog = f"SELECT os, coordenacao, dados_completos, data_upload, mes_referencia FROM os_programadas WHERE os IN ({placeholders})"
            df_raw_db = pd.read_sql_query(query_prog, conn, params=tuple(lista_os_filtro))
        else:
            df_raw_db = pd.read_sql_query("SELECT os, coordenacao, dados_completos, data_upload, mes_referencia FROM os_programadas", conn)
    except Exception: df_raw_db = pd.DataFrame()
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

    # Mapeia, por OS, o timestamp real de quando o ciclo vigente foi importado do SAP
    # (data_upload). Usado depois em aplicar_overlay_baixas para validar se uma baixa
    # pertence ao ciclo atual sem depender da "Data inicial programada" (que é a data-alvo
    # do serviço, não o momento de entrada do ciclo no sistema).
    _mapa_data_upload_ciclo = (
        df_raw_db.assign(os=df_raw_db["os"].astype(str).str.strip())
        .set_index("os")["data_upload"]
        .to_dict()
    )
    # Converte para datetime64 (em vez de deixar objetos datetime.datetime "crus" do psycopg2
    # misturados com NaN numa coluna object) -- coluna object com tipos mistos nesse ponto
    # trafega para dentro do cache_data de aplicar_overlay_baixas (que hasheia o DataFrame
    # inteiro), e coincidiu com Segmentation fault no Streamlit Cloud logo após o deploy.
    df_base_final["_data_upload_ciclo"] = pd.to_datetime(
        df_base_final["Ordem servico"].astype(str).str.strip().map(_mapa_data_upload_ciclo),
        errors="coerce"
    )

    # Mapeia, por OS, o "Mês de Referência" informado no upload (ex.: "Julho/2026"), para
    # permitir filtrar a Visão Gerencial apenas pelas OS de uma planilha/ciclo específico,
    # independente do período de programação/execução selecionado nos filtros de data.
    _mapa_mes_referencia = (
        df_raw_db.assign(os=df_raw_db["os"].astype(str).str.strip())
        .set_index("os")["mes_referencia"]
        .to_dict()
    )
    df_base_final["Plano_Mes_Referencia"] = (
        df_base_final["Ordem servico"].astype(str).str.strip().map(_mapa_mes_referencia)
    )

    if escopo_usuario != "Todas":
        escopo_norm = _mapa_norm.get(escopo_usuario.strip().upper(), escopo_usuario.strip())
        df_base_final = df_base_final[df_base_final["Coordenacao"].apply(lambda x: str(x).strip().upper() == escopo_norm.upper() if pd.notna(x) else False)]

    return df_base_final

@st.cache_data(show_spinner=False)
def aplicar_overlay_baixas(df_base_bruto: pd.DataFrame, escopo_usuario: str, baixas_mtime: str) -> pd.DataFrame:
    df_base = df_base_bruto.copy()
    if df_base.empty: return df_base

    if "Status da Operação" in df_base.columns:
        df_base["Status da Operação"] = df_base["Status da Operação"].replace(["", "nan", "NaN", "None"], "Pendente")

    df_baixas = carregar_baixas_df()
    if df_baixas.empty: return df_base
    df_base["Ordem servico"] = df_base["Ordem servico"].astype(str)

    # REMOVIDO (14/07/2026): filtro redundante de df_baixas por texto de coordenacao/escopo.
    # df_base ja vem escopado por coordenacao (carregar_base_sem_overlay), e o merge abaixo e
    # por "Ordem servico" (PRIMARY KEY em baixas) -- entao esse filtro extra nao protegia nada,
    # so causava falso-negativo: qualquer diferenca de acentuacao/espaco/maiuscula em
    # baixas.coordenacao (ou o valor "Sincronizacao Offline" gravado pelo fluxo antigo do PWA)
    # descartava a baixa inteira antes do merge, deixando a OS aparecer como pendente mesmo
    # ja concluida, para qualquer usuario logado com escopo != "Todas".
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

    # CORREÇÃO: valida se a baixa encontrada pertence ao MESMO ciclo de programação da OS atual.
    # Sem essa checagem, uma OS recorrente já baixada em um ciclo anterior (ex.: programada em
    # 17/06/2026 e concluída em 01/07/2026) que o SAP reprograma para um novo ciclo (ex.: nova
    # "Data inicial programada" em julho/2026, com "os" reaproveitado) continuava herdando a
    # "Data/Hora Realizado" e o "Status da Operação" da baixa antiga via merge por "Ordem servico".
    # Resultado: a OS aparecia como Realizada quando, no ciclo vigente, ainda está pendente —
    # zerando o Backlog assim que o filtro de Período de Execução era restringido.
    # Reaproveita parse_datahora_realizado (dayfirst=True, já corrigido) para evitar o mesmo bug
    # de inversão de data que já foi corrigido em parse_data_programada.
    if "_data_upload_ciclo" in df_base.columns:
        _dt_upload_ciclo = pd.to_datetime(df_base["_data_upload_ciclo"], errors="coerce")
    else:
        _dt_upload_ciclo = pd.Series(pd.NaT, index=df_base.index)
    _dt_realizado_baixa = df_base["Data/Hora Realizado_baixado"].apply(parse_datahora_realizado)  # pyright: ignore[reportCallIssue, reportArgumentType]
    # Baixa é válida quando: tem data de realização E (não há timestamp de importação do ciclo atual
    # para comparar OU a baixa ocorreu depois que o ciclo vigente foi importado do SAP). Usamos
    # "data_upload" (quando o ciclo entrou no sistema) em vez da "Data inicial programada" (data-alvo)
    # porque o time de campo frequentemente executa a OS ANTES da data-alvo dentro do mesmo ciclo --
    # comparar contra a data-alvo derrubava baixas reais e recentes (com foto/GPS confirmados),
    # tratando "adiantou o serviço" como "baixa velha de ciclo já fechado". Ver histórico de
    # investigação de 11/07/2026 (SQL direto no Neon confirmou >100 OS afetadas).
    #
    # EXCEÇÃO (22/07/2026): baixas administrativas (Baixa IW47 / Importação IW47 / Baixa Manual)
    # pulam essa checagem de data. São catch-up de backlog: o trabalho de campo costuma ter sido
    # executado ANTES do plano do mês ser (re)carregado no SGO, o que derrubava >2/3 de um import
    # em massa real (confirmado via SQL: 2.629 de 3.810 baixas do IPA bloqueadas em 22/07/2026).
    # Baixas com GPS/foto reais do app continuam 100% sujeitas à checagem de data -- e mesmo essas
    # já são protegidas contra sobrescrita pelo IW47 por uma trava separada no INSERT (upsert_baixa
    # só atualiza se ainda não houver foto/evidência/geolocalização real registrada para a OS).
    _geo_baixado = df_base.get("Geolocalização de Baixa_baixado", pd.Series("", index=df_base.index)).astype(str).str.strip()
    _baixa_administrativa = _geo_baixado.isin({"Baixa IW47", "Importação IW47", "Baixa Manual"})
    baixa_do_ciclo_atual = _dt_realizado_baixa.notna() & (
        _baixa_administrativa
        | _dt_upload_ciclo.isna()
        | (_dt_realizado_baixa.dt.normalize() >= _dt_upload_ciclo.dt.normalize())
    )

    for col in colunas_overlay:
        tem_baixado_valido = df_base[f"{col}_baixado"].notna() & (df_base[f"{col}_baixado"] != "") & baixa_do_ciclo_atual
        df_base[col] = np.where(tem_baixado_valido, df_base[f"{col}_baixado"], df_base[col])
        df_base.drop(columns=[f"{col}_baixado"], inplace=True)

    # Salva a foto na base final limpa (só quando a baixa pertence ao ciclo vigente)
    if "foto_evidencia_baixado" in df_base.columns:
        _foto_base = df_base["foto_evidencia"] if "foto_evidencia" in df_base.columns else ""
        df_base["foto_evidencia"] = np.where(baixa_do_ciclo_atual, df_base["foto_evidencia_baixado"], _foto_base)
        df_base.drop(columns=["foto_evidencia_baixado"], inplace=True)

    # _data_upload_ciclo é preservada (não derrubada aqui) porque a roteirização usa essa
    # coluna para o filtro de "Escopo de dados: Somente o ciclo mais recente" (config
    # operacional por coordenação) — ver seção de Roteirização e Mapa de Campo.

    return df_base
#endregion
#endregion SESSÃO 5

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
st.sidebar.caption("SGO Eletroeletrônica • v11")
st.sidebar.markdown("<br>", unsafe_allow_html=True)

st.sidebar.markdown("### 🧭 Navegação")
if "tela_atual" not in st.session_state: st.session_state["tela_atual"] = "dashboard"

gov_usuario = st.session_state.get("governanca", "")
tem_painel = "Painel Gerencial" in gov_usuario or "Mapa de Campo" in gov_usuario
tem_dados = "Upload de Dados" in gov_usuario
tem_gestao_usuarios = "Gestão de Usuários" in gov_usuario
tem_governanca = "Governança" in gov_usuario
tem_config_operacional = "Configurações Operacionais" in gov_usuario

_nav_botoes = []
if tem_painel: _nav_botoes.append(("📊 Painel", "dashboard"))
if tem_dados: _nav_botoes.append(("⚙️ Dados", "admin"))
if tem_gestao_usuarios: _nav_botoes.append(("👥 Usuários", "usuarios"))
if tem_config_operacional: _nav_botoes.append(("🛠️ Configurações", "config_operacional"))

if len(_nav_botoes) >= 2:
    _cols_nav = st.sidebar.columns(len(_nav_botoes))
    for _col_nav, (_label_nav, _tela_nav) in zip(_cols_nav, _nav_botoes):
        with _col_nav:
            if st.button(_label_nav, use_container_width=True, key=f"navbtn_{_tela_nav}"):
                st.session_state["tela_atual"] = _tela_nav; st.rerun()
elif len(_nav_botoes) == 1:
    _label_nav, _tela_nav = _nav_botoes[0]
    if st.sidebar.button(_label_nav, use_container_width=True, key=f"navbtn_{_tela_nav}"):
        st.session_state["tela_atual"] = _tela_nav; st.rerun()

if tem_governanca:
    if st.sidebar.button("🛡️ Governança (Auditoria)", use_container_width=True): st.session_state["tela_atual"] = "governanca"; st.rerun()

if st.session_state.get("tela_atual") == "admin":
    render_tela_admin()
    st.stop()

if st.session_state.get("tela_atual") == "config_operacional":
    render_tela_config_operacional()
    st.stop()

if st.session_state.get("tela_atual") == "usuarios":
    render_tela_gestao_usuarios()
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
def _hash_baixas():
    conn = get_connection()
    try:
        cur = conn.cursor()
        # ON CONFLICT (os) DO UPDATE NAO altera COUNT nem MAX(os): re-baixa de uma OS ja
        # existente mantinha o hash igual -> cache do overlay ficava velho -> a OS baixada
        # continuava aparecendo como disponivel. MAX(atualizado_em) (TIMESTAMP real, nao texto)
        # detecta qualquer INSERT/UPDATE de forma cronologicamente confiavel -- MAX(realizado_em)
        # (VARCHAR "DD/MM/AAAA HH:MM") comparava alfabeticamente e podia nao mudar (13/07/2026).
        cur.execute("SELECT COUNT(*), COALESCE(MAX(os),''), COALESCE(MAX(atualizado_em)::text,'') FROM baixas")
        row = cur.fetchone()
        cur.close()
        return f"{row[0]}_{row[1]}_{row[2]}"
    finally: release_connection(conn)

baixas_mtime = _hash_baixas()
df_base_bruto = carregar_base_sem_overlay(escopo_usuario=st.session_state["escopo"], etl_version=ETL_VERSION)
df_base = aplicar_overlay_baixas(df_base_bruto=df_base_bruto, escopo_usuario=st.session_state["escopo"], baixas_mtime=baixas_mtime)

st.session_state["df_os"] = df_base
df_visao = preparar_df_visao(df_base, filtro_visao)

if df_visao.empty or "dt_prog_filtro" not in df_visao.columns:
    st.info("📋 Nenhuma OS encontrada. Faça o upload das planilhas em **⚙️ Dados** para começar.")
    st.stop()
#endregion 7.2

#region 7.3: Filtros da Sidebar
valid_dates = df_visao["dt_prog_filtro"].dropna()
# Calendário restrito ao ano vigente (pedido 24/07/2026): prioriza min/max só das OS
# programadas no ano corrente -- evita navegar pelo histórico inteiro (ex.: 2023-2026).
# Sem dado no ano vigente (base de teste, por exemplo), cai pro min/max de toda a base.
valid_dates_ano_vigente = valid_dates[valid_dates.dt.year == datetime.now().year]
if not valid_dates_ano_vigente.empty: min_date, max_date = valid_dates_ano_vigente.min().date(), valid_dates_ano_vigente.max().date()
elif not valid_dates.empty: min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
else: min_date, max_date = datetime.now().date() - pd.Timedelta(days=30), datetime.now().date()

lista_patios = sorted(df_visao["Patio"].dropna().astype(str).unique().tolist())
lista_grupos_ativo = (
    sorted(df_visao["Grupo_Ativo"].dropna().astype(str).unique().tolist())
    if "Grupo_Ativo" in df_visao.columns else []
)
# Cascata (pedido de 22/07/2026): se algum(s) Grupo(s) de Ativo já estiver(em) selecionado(s)
# (do último "Aplicar Filtros"), a lista de Ativo mostra só os ativos daqueles grupos --
# evita o gestor ter que procurar o ativo específico numa lista com todos os grupos juntos.
# Se um reset ("Limpar Filtros") estiver pendente, ignora a seleção antiga (senão o próprio
# "Limpar" herdaria a lista de Ativo já estreitada pelo Grupo de Ativo anterior).
_grupos_ativo_sel_atual = (
    list(lista_grupos_ativo)
    if st.session_state.get("_solicitar_reset_filtros", False)
    else st.session_state.get("filtro_grupos_ativo", list(lista_grupos_ativo))
)
if _grupos_ativo_sel_atual and "Grupo_Ativo" in df_visao.columns:
    _df_para_lista_ativos = df_visao[df_visao["Grupo_Ativo"].isin(_grupos_ativo_sel_atual)]
else:
    _df_para_lista_ativos = df_visao
lista_ativos = (
    sorted(_df_para_lista_ativos["Ativo"].dropna().astype(str).unique().tolist())
    if "Ativo" in df_visao.columns else []
)
lista_planos_mes = (
    sorted(df_visao["Plano_Mes_Referencia"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist())
    if "Plano_Mes_Referencia" in df_visao.columns else []
)
lista_classificacoes = ["Segurança", "Confiabilidade"]
lista_criticidades = ["Muito Alta", "Alta", "Média", "Baixa"]
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

    # Aplica o reset ANTES de qualquer widget desta função ser instanciado nesta execução --
    # o Streamlit proíbe escrever em st.session_state[key] depois que o widget dono dessa
    # key já foi criado no mesmo rerun (StreamlitAPIException). O botão "Limpar Filtros"
    # (mais abaixo) só marca esse pedido e chama st.rerun(); quem de fato reseta é este
    # bloco, que roda primeiro na execução seguinte.
    #
    # Reset AUTOMÁTICO ao trocar de escopo (pedido 24/07/2026): _sanear_lista_filtro
    # (abaixo) só remove da seleção o que não existe mais nas opções atuais -- pensada
    # pra opção sumir aos poucos, não pro universo inteiro trocar de uma vez. Ao mudar
    # de escopo (Piaçaguera/Paranapiacaba/Gerência), a seleção antiga vira uma
    # interseção residual e por acaso com a lista nova (ex.: "só 2 pátios"), em vez de
    # continuar representando "tudo selecionado". Detectar a troca de escopo e disparar
    # o mesmo reset do botão "Limpar Filtros" resolve isso sem exigir clique manual.
    _escopo_mudou = st.session_state.get("escopo") != st.session_state.get("_escopo_dos_filtros")
    if st.session_state.pop("_solicitar_reset_filtros", False) or _escopo_mudou:
        st.session_state["filtro_mes_referencia"] = "Todos"
        st.session_state["filtro_start_date"] = min_date
        st.session_state["filtro_end_date"] = max_date
        st.session_state["filtro_exec_start_date"] = min_date
        st.session_state["filtro_exec_end_date"] = max_date
        st.session_state["filtro_patios"] = list(lista_patios)
        st.session_state["filtro_classificacoes"] = list(lista_classificacoes)
        st.session_state["filtro_grupos_ativo"] = list(lista_grupos_ativo)
        st.session_state["filtro_ativos"] = list(lista_ativos)
        st.session_state["filtro_criticidades"] = list(lista_criticidades)
        st.session_state["filtro_turnos"] = list(lista_turnos)
        st.session_state["filtro_intervalo_sel"] = "Todas"
        st.session_state["filtro_status_sel"] = "Todos"
    st.session_state["_escopo_dos_filtros"] = st.session_state.get("escopo")

    if _escopo_mudou:
        # lista_ativos (fora desta função, calculada mais acima) segue a cascata de
        # Grupo de Ativo -- ela já rodou neste script ANTES do reset acima acontecer,
        # então ainda reflete a seleção antiga por um render. Um st.rerun() aqui força
        # essa lista a ser recalculada já com filtro_grupos_ativo resetado (mesmo
        # comportamento que o botão "Limpar Filtros" já tem, só que automático).
        st.rerun()

    st.markdown("### 📊 Filtros")
    
    with st.form("form_filtros"):
        # Plano (Mês de Referência): filtra pela planilha de OS Programadas importada (ex.: "Julho/2026"),
        # independente do período de data escolhido abaixo — usado para isolar os cards/gráficos
        # gerenciais apenas às OS daquele ciclo específico.
        st.selectbox("📋 Plano (Mês de Referência)", ["Todos"] + lista_planos_mes, key="filtro_mes_referencia")

        # Datas
        start_padrao = st.session_state.get("filtro_start_date", min_date)
        end_padrao = st.session_state.get("filtro_end_date", max_date)
        data_selecionada = st.date_input("Período de Programação", value=(start_padrao, end_padrao), min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

        exec_start_padrao = st.session_state.get("filtro_exec_start_date", min_date)
        exec_end_padrao = st.session_state.get("filtro_exec_end_date", max_date)
        data_exec_selecionada = st.date_input("Período de Execução", value=(exec_start_padrao, exec_end_padrao), min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

        
        # Pátios, Classificação, Turno
        patios_default = _sanear_lista_filtro("filtro_patios", lista_patios, lista_patios)
        st.multiselect("Pátio", lista_patios, default=patios_default, key="filtro_patios")
        
        classif_default = _sanear_lista_filtro("filtro_classificacoes", lista_classificacoes, lista_classificacoes)
        st.multiselect("Classificação", lista_classificacoes, default=classif_default, key="filtro_classificacoes")

        crit_default = _sanear_lista_filtro("filtro_criticidades", lista_criticidades, lista_criticidades)
        st.multiselect("Criticidade", lista_criticidades, default=crit_default, key="filtro_criticidades")

        # Grupo de Ativo e Ativo (pedido de 22/07/2026): dá visão pro gestor filtrar por
        # tipo de equipamento (Grupo de Ativo, extraído da Atividade Ativo) ou por um
        # Ativo específico, sem depender de Pátio/Classificação.
        grupo_ativo_default = _sanear_lista_filtro("filtro_grupos_ativo", lista_grupos_ativo, lista_grupos_ativo)
        st.multiselect("Grupo de Ativo", lista_grupos_ativo, default=grupo_ativo_default, key="filtro_grupos_ativo")

        ativos_default = _sanear_lista_filtro("filtro_ativos", lista_ativos, lista_ativos)
        st.multiselect("Ativo", lista_ativos, default=ativos_default, key="filtro_ativos")

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
        if isinstance(data_exec_selecionada, tuple) and len(data_exec_selecionada) == 2:
            st.session_state["filtro_exec_start_date"], st.session_state["filtro_exec_end_date"] = data_exec_selecionada
        st.rerun()

    # Fora do form (senão precisaria de outro clique em "Aplicar Filtros" pra valer) --
    # volta todos os filtros pro padrão "tudo selecionado / período inteiro", exatamente
    # como no primeiro carregamento. Pedido de 22/07/2026. Só marca o pedido e reinicia --
    # quem de fato reseta é o bloco no topo da função (ver comentário lá) para não violar
    # a regra do Streamlit de não escrever em st.session_state[key] após o widget dono
    # dessa key já ter sido instanciado neste rerun.
    if st.button("🧹 Limpar Filtros", use_container_width=True):
        st.session_state["_solicitar_reset_filtros"] = True
        st.rerun()
#endregion 7.3

with st.sidebar: fragmento_filtros_sidebar_seguro()

crit_selecionadas = st.session_state.get("filtro_criticidades", list(lista_criticidades))
exec_start_date = st.session_state.get("filtro_exec_start_date", min_date)
exec_end_date = st.session_state.get("filtro_exec_end_date", max_date)
# Só aplica o filtro de Execução (restringe pelas realizadas, mantendo as pendentes/NaT) quando o usuário estreita o range padrão.
if not ((exec_start_date > min_date) or (exec_end_date < max_date)):
    exec_start_date = exec_end_date = None
start_date = st.session_state.get("filtro_start_date", min_date)
end_date = st.session_state.get("filtro_end_date", max_date)
patios_selecionados = st.session_state.get("filtro_patios", list(lista_patios))
classif_selecionadas = st.session_state.get("filtro_classificacoes", list(lista_classificacoes))
grupos_ativo_selecionados = st.session_state.get("filtro_grupos_ativo", list(lista_grupos_ativo))
ativos_selecionados = st.session_state.get("filtro_ativos", list(lista_ativos))
turnos_selecionados = st.session_state.get("filtro_turnos", list(lista_turnos))
status_sel = st.session_state.get("filtro_status_sel", "Todos")
intervalo_sel = st.session_state.get("filtro_intervalo_sel", "Todas")

# Base dos 4 cards do topo (região 9.3/9.4): sempre o Último Plano/Ciclo (maior
# _data_upload_ciclo por Plano_Mes_Referencia, mesmo critério da query de planos_disponiveis,
# linha ~1994), respeitando Pátio/Classificação/Criticidade/Turno/Status/Intervalo já
# selecionados na sidebar -- só o Período de Programação/Execução e o seletor de Plano
# (Mês de Referência) são ignorados aqui de propósito (pedido 24/07/2026). Calculado sobre
# df_visao ainda SEM o filtro de Plano abaixo, para não herdar uma escolha manual do usuário.
if "Plano_Mes_Referencia" in df_visao.columns and "_data_upload_ciclo" in df_visao.columns:
    _upload_por_plano = (
        df_visao.dropna(subset=["Plano_Mes_Referencia"])
        .groupby("Plano_Mes_Referencia")["_data_upload_ciclo"].max()
        .dropna()
        .sort_values(ascending=False)
    )
    ultimo_plano = _upload_por_plano.index[0] if not _upload_por_plano.empty else None
else:
    ultimo_plano = None

if ultimo_plano is not None:
    df_visao_ultimo_plano = df_visao[df_visao["Plano_Mes_Referencia"].astype(str).str.strip() == str(ultimo_plano).strip()]
    _datas_prog_ultimo = df_visao_ultimo_plano["dt_prog_filtro"].dropna()
    _start_ultimo = _datas_prog_ultimo.min().date() if not _datas_prog_ultimo.empty else min_date
    _end_ultimo = _datas_prog_ultimo.max().date() if not _datas_prog_ultimo.empty else max_date
    df_kpi_topo = aplicar_filtros_sidebar(
        df_visao=df_visao_ultimo_plano, patios_selecionados=patios_selecionados,
        classif_selecionadas=classif_selecionadas, turnos_selecionados=turnos_selecionados,
        start_date=_start_ultimo, end_date=_end_ultimo, status_sel=status_sel, intervalo_sel=intervalo_sel,
        crit_selecionadas=crit_selecionadas, exec_start_date=None, exec_end_date=None,
        grupos_ativo_selecionados=grupos_ativo_selecionados, ativos_selecionados=ativos_selecionados
    )
else:
    df_kpi_topo = None  # sem dado de ciclo/upload -- região 9.3 cai para df_filtrado

plano_mes_sel = st.session_state.get("filtro_mes_referencia", "Todos")
if plano_mes_sel != "Todos" and "Plano_Mes_Referencia" in df_visao.columns:
    df_visao = df_visao[df_visao["Plano_Mes_Referencia"].astype(str).str.strip() == plano_mes_sel].copy()

df_filtrado = aplicar_filtros_sidebar(
    df_visao=df_visao, patios_selecionados=patios_selecionados,
    classif_selecionadas=classif_selecionadas, turnos_selecionados=turnos_selecionados,
    start_date=start_date, end_date=end_date, status_sel=status_sel, intervalo_sel=intervalo_sel,
    crit_selecionadas=crit_selecionadas, exec_start_date=exec_start_date, exec_end_date=exec_end_date,
    grupos_ativo_selecionados=grupos_ativo_selecionados, ativos_selecionados=ativos_selecionados
)
#endregion 7.3
#endregion

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
        try:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET reset_obrigatorio = 1 WHERE username = %s", (usr_atual,))
            conn.commit(); cur.close()
        finally:
            release_connection(conn)
        
        st.session_state.clear()
        st.session_state.update({"logged_in": False, "needs_reset": True, "reset_user": usr_atual})
        st.query_params.clear()
        st.rerun()
        
    if st.button("🚪 Sair", use_container_width=True):
        keys_manter = {"gps_pending", "gps_trials", "origem_tipo"}
        for key in list(st.session_state.keys()):
            if key not in keys_manter: del st.session_state[key]
        st.session_state["logged_in"] = False
        st.query_params.clear()
        st.rerun()

st.markdown("---")
#endregion 9.2

#region 9.3: Cálculo dos KPIs + CSS dos Cards (Dark Mode)
# Cards travados no Último Plano/Ciclo (ver bloco df_kpi_topo, região 7.3) -- cai para
# df_filtrado só se não houver dado de ciclo/upload disponível (base antiga/sem upload).
df_kpi_base = df_kpi_topo if df_kpi_topo is not None else df_filtrado
total_os = len(df_kpi_base)
realizado_prazo = len(df_kpi_base[df_kpi_base["Status_norm"].isin(_status_prazo | {"ABER NRAV"})])
realizado_atraso = len(df_kpi_base[df_kpi_base["Status_norm"].isin(_status_atraso)])
realizado_total = realizado_prazo + realizado_atraso
nao_realizado = len(df_kpi_base[df_kpi_base["Status_norm"].isin(_status_aberto_dashboard)])
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

if st.session_state.get("logged_in") and "sid" not in st.query_params:
    st.query_params["sid"] = gerar_token_sessao(st.session_state["username"])
tab1 = None
tab2 = None
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

                        # Datas canônicas para o gráfico
                        df_area["dia_programado"] = pd.to_datetime(
                            df_area["Data inicial programada"],
                            errors="coerce"
                        ).dt.normalize()

                        df_area["dia_realizado"] = pd.to_datetime(
                            df_area["dia_realizado"],
                            errors="coerce"
                        ).dt.normalize()

                        # O filtro lateral é de Período de Programação.
                        # Para evitar eixo fora do período selecionado, o gráfico
                        # fica travado explicitamente em start_date/end_date.
                        data_ini_graf = pd.to_datetime(start_date).normalize()
                        data_fim_graf = pd.to_datetime(end_date).normalize()

                        # Planejado: conta somente OS programadas dentro do período visual.
                        df_plan_area = df_area[
                            (df_area["dia_programado"] >= data_ini_graf)
                            & (df_area["dia_programado"] <= data_fim_graf)
                        ].copy()

                        planejado_diario_a = (
                            df_plan_area
                            .groupby("dia_programado")
                            .size()
                            .rename("Planejado_Dia")
                        )

                        # Realizado: conta somente realizações dentro do mesmo período visual.
                        # Isso evita que uma OS programada em maio/junho, mas realizada fora
                        # desse intervalo, estique o eixo do gráfico.
                        df_real_area = df_area[
                            df_area["Status_norm"].isin(_status_concluida_dashboard)
                        ].copy()

                        df_real_area = df_real_area[
                            (df_real_area["dia_realizado"] >= data_ini_graf)
                            & (df_real_area["dia_realizado"] <= data_fim_graf)
                        ].copy()

                        realizado_diario_a = (
                            df_real_area
                            .groupby("dia_realizado")
                            .size()
                            .rename("Realizado_Dia")
                        )

                        _idx_da = pd.date_range(
                            start=data_ini_graf,
                            end=data_fim_graf,
                            freq="D"
                        )

                        if len(_idx_da) > 0:
                            _real_acum = (
                                realizado_diario_a
                                .reindex(_idx_da, fill_value=0)
                                .cumsum()
                            )

                            _plan_acum = (
                                planejado_diario_a
                                .reindex(_idx_da, fill_value=0)
                                .cumsum()
                            )

                            st_echarts(
                                options={
                                    "tooltip": {"trigger": "axis"},
                                    "legend": {"top": "bottom"},
                                    "toolbox": {
                                        "show": True,
                                        "feature": {
                                            "magicType": {
                                                "type": ["line", "bar"],
                                                "title": {
                                                    "line": "Linha",
                                                    "bar": "Barra"
                                                }
                                            },
                                            "restore": {"title": "Restaurar"},
                                            "saveAsImage": {"title": "Salvar Imagem"}
                                        }
                                    },
                                    "dataZoom": [
                                        {
                                            "type": "slider",
                                            "show": True,
                                            "xAxisIndex": [0],
                                            "start": 0,
                                            "end": 100,
                                            "bottom": "5%"
                                        }
                                    ],
                                    "grid": {
                                        "left": "5%",
                                        "right": "5%",
                                        "bottom": "25%",
                                        "top": "15%",
                                        "containLabel": True
                                    },
                                    "xAxis": {
                                        "type": "category",
                                        "data": [d.strftime("%d/%m") for d in _idx_da]
                                    },
                                    "yAxis": {"type": "value"},
                                    "series": [
                                        {
                                            "name": "Realizado Acumulado",
                                            "type": "line",
                                            "smooth": True,
                                            "data": _real_acum.tolist(),
                                            "areaStyle": {
                                                "color": "rgba(59,130,246,0.2)"
                                            },
                                            "lineStyle": {
                                                "color": cor_real,
                                                "width": 3
                                            },
                                            "itemStyle": {
                                                "color": cor_real
                                            }
                                        },
                                        {
                                            "name": "Planejado Acumulado",
                                            "type": "line",
                                            "smooth": True,
                                            "data": _plan_acum.tolist(),
                                            "lineStyle": {
                                                "color": cor_plan,
                                                "width": 3,
                                                "type": "dashed"
                                            },
                                            "itemStyle": {
                                                "color": cor_plan
                                            }
                                        },
                                    ],
                                },
                                height="350px",
                                theme="streamlit",
                                key="aba1_area"
                            )
                        else:
                            st.info("Sem datas suficientes para área.")
                #endregion 10.2.1

#region 10.2.2: Análise Operacional (Matriz de Prioridades)
                with st.expander("Análise Operacional: Matriz de Prioridades e Execução por Categoria", expanded=True):
                    col_h1, col_h2 = st.columns([1.2, 1])
                    with col_h1:
                        st.markdown("#### Matriz: Prioridade vs Classificação")
                        st.caption("Volume total de OS planejadas (Cor indica concentração)")
                        agg = df_visao_base.copy().groupby(["Classificacao", "Criticidade"]).size().reset_index(name="Total")
                        ordem_class = ["Confiabilidade", "Segurança"]
                        ordem_crit = ["Muito Alta", "Alta", "Média", "Baixa"]

                        if not agg.empty:
                            heat_data, max_val = [], 0
                            for _yi, _cls in enumerate(ordem_class):
                                for _xi, _crt in enumerate(ordem_crit):
                                    _row = agg[(agg["Classificacao"] == _cls) & (agg["Criticidade"] == _crt)]
                                    _val = int(_row["Total"].iloc[0]) if not _row.empty else 0
                                    # Sem JsCode: para valor 0, some o rotulo via override por item
                                    # (label.show=False) em vez de formatter em JS -- JsCode parou de
                                    # ser serializado apos a nuvem forcar upgrade do Streamlit.
                                    if _val > 0:
                                        heat_data.append([_xi, _yi, _val])
                                    else:
                                        heat_data.append({"value": [_xi, _yi, _val], "label": {"show": False}})
                                    max_val = max(max_val, _val)

                            st_echarts(options={
                                "tooltip": {"position": "top"}, "grid": {"height": "70%", "top": "10%", "left": "25%", "containLabel": True},
                                "xAxis": {"type": "category", "data": ordem_crit, "splitArea": {"show": True}, "axisLine": {"show": False}, "axisTick": {"show": False}},
                                "yAxis": {"type": "category", "data": ordem_class, "splitArea": {"show": True}, "axisLine": {"show": False}, "axisTick": {"show": False}},
                                "visualMap": {"min": 0, "max": max_val if max_val > 0 else 10, "calculable": True, "orient": "horizontal", "left": "center", "bottom": "0%", "inRange": {"color": ["#F1F5F9", "#93C5FD", "#3B82F6", "#1E3A8A"]}},
                                "series": [{"name": "Total de OS", "type": "heatmap", "data": heat_data, "label": {"show": True, "color": "#FFFFFF", "fontWeight": "bold"}, "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2}}],
                            }, height="380px", theme="streamlit", key="aba1_heatmap_discrete")
                        else: st.info("Sem dados para a Matriz.")

                    with col_h2:
                        st.markdown("#### Plan x Realizado por Categoria")
                        st.caption("Comparativo de volume total e execução.")
                        df_bar_cat = df_visao_base.copy()
                        plan_cat = df_bar_cat.groupby("Classificacao").size()
                        real_cat = (df_bar_cat[df_bar_cat["Status_norm"].isin(_status_concluida_dashboard)].groupby("Classificacao").size())
                        cats = ["Segurança", "Confiabilidade"]
                        val_plan, val_real = [int(plan_cat.get(c, 0)) for c in cats], [int(real_cat.get(c, 0)) for c in cats]
                        # Representatividade: % do Realizado sobre o Planejado da própria categoria.
                        data_real_cat = [
                            {
                                "value": v,
                                "label": {
                                    "show": True, "position": "right", "color": "#475569",
                                    "formatter": f"{v} ({(v / p * 100):.1f}%)" if p > 0 else f"{v} (0%)",
                                },
                            }
                            for v, p in zip(val_real, val_plan)
                        ]

                        st_echarts(options={
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}}, "legend": {"bottom": "0%"},
                            "grid": {"left": "3%", "right": "14%", "bottom": "15%", "top": "10%", "containLabel": True},
                            "xAxis": {"type": "value", "boundaryGap": [0, 0.01]}, "yAxis": {"type": "category", "data": cats, "axisLabel": {"interval": 0}},
                            "series": [
                                {"name": "Planejado", "type": "bar", "data": val_plan, "itemStyle": {"color": cor_plan}, "label": {"show": True, "position": "right", "color": "#475569"}},
                                {"name": "Realizado", "type": "bar", "data": data_real_cat, "itemStyle": {"color": cor_real}}
                            ]
                        }, height="380px", theme="streamlit", key="aba1_bar_horiz")
                #endregion 10.2.2

#region 10.2.2b: Aderência Ponderada da Meta (Segurança / Prioridade 1 / Prioridade 2,3,4)
                with st.expander("Aderência Ponderada da Meta (Segurança / Prioridade)", expanded=True):
                    st.caption("Peso fixo por bucket, igual para todas as coordenações: Segurança 40% · Prioridade 1 (Muito Alta) 25% · Prioridade 2, 3 e 4 35%.")
                    df_meta = df_visao_base.copy()
                    _classif_meta = df_meta.get("Classificacao", pd.Series("Confiabilidade", index=df_meta.index)).astype(str)
                    _crit_meta = df_meta.get("Criticidade", pd.Series("", index=df_meta.index)).astype(str)
                    _mask_seguranca = _classif_meta == "Segurança"
                    _mask_prio1 = (_classif_meta == "Confiabilidade") & (_crit_meta == "Muito Alta")
                    _mask_prio234 = (_classif_meta == "Confiabilidade") & (_crit_meta.isin(["Alta", "Média", "Baixa"]))
                    _mask_realizado_meta = df_meta["Status_norm"].isin(_status_concluida_dashboard)

                    _buckets_meta = [
                        ("Segurança", _mask_seguranca, 40.0),
                        ("Prioridade 1 (Muito Alta)", _mask_prio1, 25.0),
                        ("Prioridade 2, 3 e 4", _mask_prio234, 35.0),
                    ]
                    _linhas_meta = []
                    for _nome, _mask, _peso in _buckets_meta:
                        _ordens = int(_mask.sum())
                        _realizado = int((_mask & _mask_realizado_meta).sum())
                        _aderencia = (_realizado / _ordens * 100) if _ordens > 0 else 0.0
                        _resultado = _aderencia * _peso / 100.0
                        _linhas_meta.append({
                            "bucket": _nome, "ordens": _ordens, "realizado": _realizado,
                            "nao_realizado": _ordens - _realizado, "aderencia": _aderencia,
                            "peso": _peso, "resultado": _resultado,
                        })
                    _resultado_total = sum(l["resultado"] for l in _linhas_meta)

                    col_meta1, col_meta2 = st.columns(2, gap="medium")
                    with col_meta1:
                        st.markdown("#### Ordens x Realizado por Bucket")
                        st_echarts(options={
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                            "legend": {"bottom": "0%"},
                            "grid": {"left": "3%", "right": "5%", "bottom": "18%", "top": "10%", "containLabel": True},
                            "xAxis": {"type": "category", "data": [l["bucket"] for l in _linhas_meta], "axisLabel": {"interval": 0, "fontSize": 11}},
                            "yAxis": {"type": "value"},
                            "series": [
                                {"name": "Ordens (Plano)", "type": "bar", "data": [l["ordens"] for l in _linhas_meta], "itemStyle": {"color": cor_plan}, "label": {"show": True, "position": "top"}},
                                {"name": "Realizado", "type": "bar", "data": [l["realizado"] for l in _linhas_meta], "itemStyle": {"color": cor_real}, "label": {"show": True, "position": "top"}},
                            ],
                        }, height="360px", theme="streamlit", key="aba1_meta_bar")

                    with col_meta2:
                        st.markdown("#### Aderência Ponderada (Resultado)")
                        st.metric("Resultado Ponderado Total", f"{_resultado_total:.2f}%")
                        _cores_bucket_meta = ["#3B82F6", "#F59E0B", "#8B5CF6"]
                        st_echarts(options={
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "formatter": "{b}: {c}%"},
                            "grid": {"left": "5%", "right": "5%", "bottom": "10%", "top": "12%", "containLabel": True},
                            "xAxis": {"type": "category", "data": [l["bucket"] for l in _linhas_meta], "axisLabel": {"interval": 0, "fontSize": 11}},
                            "yAxis": {"type": "value", "name": "Resultado (%)", "max": 40},
                            "series": [{
                                "type": "bar",
                                "barWidth": "50%",
                                "data": [
                                    {"value": round(l["resultado"], 2), "itemStyle": {"color": _cores_bucket_meta[i]}}
                                    for i, l in enumerate(_linhas_meta)
                                ],
                                "label": {"show": True, "position": "top", "formatter": "{c}%", "fontWeight": "bold", "color": "#334155"},
                            }],
                        }, height="300px", theme="streamlit", key="aba1_meta_bar_resultado")

                        for l in _linhas_meta:
                            st.caption(
                                f"**{l['bucket']}**: {l['ordens']} ordens · {l['realizado']} realizado · "
                                f"Aderência {l['aderencia']:.2f}% × Peso {l['peso']:.0f}% = **{l['resultado']:.2f}%**"
                            )
#endregion 10.2.2b

#region 10.2.3: Execução por Turno e Acumulado
                with st.expander("Execução por Turno e Acumulado", expanded=True):
                    col_g3, col_g6 = st.columns(2)
                    _cor_turno = { "Turno Dia (07h-19h)": "#F59E0B", "Administrativo (08h-17h30)": "#3B82F6", "Turno Noite (19h-07h)": "#4F46E5" }
                    with col_g3:
                        st.markdown("#### Realizado por Turno")
                        x_turnos = ["Turno Dia (07h-19h)", "Administrativo (08h-17h30)", "Turno Noite (19h-07h)"]
                        _cnt_t = df_visao_base[df_visao_base["Status_norm"].isin(_status_concluida_dashboard)].groupby("Turno").size()
                        y_vals = [int(_cnt_t.get(t, 0)) for t in x_turnos]
                        # Representatividade: % que o turno representa do total Realizado (soma dos 3 turnos).
                        _total_turnos = sum(y_vals)
                        data_turno = [
                            {
                                "value": v, "name": t, "itemStyle": {"color": _cor_turno.get(t, "#94A3B8")},
                                "label": {
                                    "show": True, "position": "inside", "color": "#FFFFFF", "fontWeight": "bold",
                                    "formatter": f"{v} ({(v / _total_turnos * 100):.1f}%)" if _total_turnos > 0 else f"{v} (0%)",
                                },
                            }
                            for t, v in zip(x_turnos, y_vals)
                        ]
                        st_echarts(options={
                            "tooltip": {"trigger": "axis"}, "xAxis": {"type": "category", "data": x_turnos, "axisLabel": {"interval": 0, "fontSize": 10}}, "yAxis": {"type": "value"},
                            "toolbox": {"show": True, "feature": {"magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}}, "restore": {"title": "Restaurar"}, "saveAsImage": {"title": "Salvar Imagem"}}},
                            "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "15%", "containLabel": True},
                            "series": [{"type": "bar", "barWidth": "55%", "data": data_turno}],
                        }, height="350px", theme="streamlit", key="aba1_barra")

                        with col_g6:
                            st.markdown("#### Realizado Acumulado por Turno")

                            # O filtro lateral é de Período de Programação, mas este gráfico é cronológico.
                            # Para evitar datas fora da janela visual selecionada, limitamos o eixo X
                            # explicitamente ao intervalo start_date/end_date.
                            df_linhas_plot = df_visao_base[
                                df_visao_base["Status_norm"].isin(_status_concluida_dashboard)
                            ].dropna(subset=["dia_realizado"]).copy()

                            if not df_linhas_plot.empty:
                                df_linhas_plot["dia_realizado"] = pd.to_datetime(
                                    df_linhas_plot["dia_realizado"],
                                    errors="coerce"
                                ).dt.normalize()

                                data_ini_graf = pd.to_datetime(start_date).normalize()
                                data_fim_graf = pd.to_datetime(end_date).normalize()

                                # Trava visual: não deixa o acumulado abrir eixo fora do período selecionado.
                                df_linhas_plot = df_linhas_plot[
                                    (df_linhas_plot["dia_realizado"] >= data_ini_graf)
                                    & (df_linhas_plot["dia_realizado"] <= data_fim_graf)
                                ].copy()

                                _idx_dt = pd.date_range(
                                    start=data_ini_graf,
                                    end=data_fim_graf,
                                    freq="D"
                                )

                                _series_t = [
                                    {
                                        "name": _t,
                                        "type": "line",
                                        "smooth": True,
                                        "data": (
                                            df_linhas_plot[df_linhas_plot["Turno"] == _t]
                                            .groupby("dia_realizado")
                                            .size()
                                            .reindex(_idx_dt, fill_value=0)
                                            .cumsum()
                                        ).tolist(),
                                        "lineStyle": {
                                            "color": _cor_turno[_t],
                                            "width": 3
                                        },
                                        "itemStyle": {
                                            "color": _cor_turno[_t]
                                        }
                                    }
                                    for _t in x_turnos
                                ]

                                st_echarts(
                                    options={
                                        "tooltip": {"trigger": "axis"},
                                        "legend": {"top": "bottom"},
                                        "toolbox": {
                                            "show": True,
                                            "feature": {
                                                "magicType": {
                                                    "type": ["line", "bar", "stack"],
                                                    "title": {
                                                        "line": "Linha",
                                                        "bar": "Barra",
                                                        "stack": "Empilhado"
                                                    }
                                                },
                                                "restore": {"title": "Restaurar"},
                                                "saveAsImage": {"title": "Salvar Imagem"}
                                            }
                                        },
                                        "dataZoom": [
                                            {
                                                "type": "slider",
                                                "show": True,
                                                "xAxisIndex": [0],
                                                "start": 0,
                                                "end": 100,
                                                "bottom": "5%"
                                            }
                                        ],
                                        "grid": {
                                            "left": "5%",
                                            "right": "5%",
                                            "bottom": "25%",
                                            "top": "15%",
                                            "containLabel": True
                                        },
                                        "xAxis": {
                                            "type": "category",
                                            "data": [d.strftime("%d/%m") for d in _idx_dt]
                                        },
                                        "yAxis": {"type": "value"},
                                        "series": _series_t,
                                    },
                                    height="350px",
                                    theme="streamlit",
                                    key="aba1_linhas"
                                )

                            else:
                                st.info("Sem dados cronológicos.")
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
                        # Uma OS pode ter varias linhas em 'evidencias' (chave e ativo+atividade).
                        # Deduplica por OS antes do merge para NAO multiplicar linhas da lista (baixa duplicada).
                        df_evidencias = df_evidencias.drop_duplicates(subset=["os_ref_match"], keep="last")
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

                # --- APLICA O FILTRO DA PESQUISA (drilldown: sugestões enquanto digita) ---
                # Pedido de 22/07/2026: em vez de só filtrar a tabela por "contém", mostra as
                # sugestões (OS/Pátio/Ativo que batem com o texto) numa lista pra escolher -- a
                # pessoa pode digitar um trecho parcial e drilar até o valor exato antes de ver
                # a tabela filtrada por ele.
                if busca_os:
                    b_up = busca_os.upper()
                    mask_busca = (
                        df_lista["OS"].astype(str).str.upper().str.contains(b_up, na=False)
                        | df_lista["Patio"].astype(str).str.upper().str.contains(b_up, na=False)
                        | df_lista["Ativo"].astype(str).str.upper().str.contains(b_up, na=False)
                    )
                    df_candidatos_busca = df_lista[mask_busca]

                    sugestoes_busca = sorted({
                        v for v in (
                            df_candidatos_busca["OS"].astype(str).tolist()
                            + df_candidatos_busca["Patio"].astype(str).tolist()
                            + df_candidatos_busca["Ativo"].astype(str).tolist()
                        )
                        if b_up in v.upper()
                    })

                    opcao_drilldown = st.selectbox(
                        f"🔎 {len(sugestoes_busca)} sugestão(ões) — selecione pra filtrar exatamente, "
                        "ou deixe em \"Todos os resultados\" pra ver tudo que bateu com a busca:",
                        ["(Todos os resultados da busca)"] + sugestoes_busca,
                        key="drilldown_lista_os"
                    )

                    if opcao_drilldown != "(Todos os resultados da busca)":
                        df_lista = df_lista[
                            (df_lista["OS"].astype(str) == opcao_drilldown)
                            | (df_lista["Patio"].astype(str) == opcao_drilldown)
                            | (df_lista["Ativo"].astype(str) == opcao_drilldown)
                        ]
                    else:
                        df_lista = df_candidatos_busca

                if not df_lista.empty:
                    # Tabela nativa do Streamlit (ordenação por clique na coluna já é nativa) em vez de
                    # HTML/JS cru via components.html -- essa era a causa raiz recorrente do
                    # Segmentation fault (crash nativo sem traceback Python) apos o upgrade forcado
                    # do Streamlit pela nuvem. LinkColumn renderiza o link de evidência sem precisar
                    # de HTML cru.
                    df_display = df_lista[colunas_ordem].copy()

                    # Exportação em ";" (não ","): "Descrição Longa" e "Geolocalização de Baixa"
                    # ("Lat: X, Lon: Y") trazem vírgula dentro do próprio texto -- CSV separado por
                    # vírgula quebra a organização das colunas ao abrir/ordenar no Excel. O ícone
                    # nativo do st.dataframe (canto da tabela) continua exportando em ",".
                    csv_lista_os = df_display.to_csv(index=False, sep=";").encode("utf-8-sig")
                    st.download_button(
                        "⬇️ Baixar CSV (separado por ;)",
                        data=csv_lista_os,
                        file_name="lista_detalhada_os.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        hide_index=True,
                        height=450,
                        column_config={
                            "Evidência": st.column_config.LinkColumn("Evidência", display_text="🔗 Abrir Foto"),
                        }
                    )
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

            expander_mapa = st.expander("🗺️ Mapa de Navegação Geográfica", expanded=True)
            col_mapa = expander_mapa.container()

            expander_ferramentas = st.expander("⚙️ Ferramentas de Campo e Filtros", expanded=True)
            col_acao = expander_ferramentas.container()

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

                # Estado APLICADO: só muda ao clicar em "Filtrar" (sem recálculo automático)
                if "raio_aplicado" not in st.session_state:
                    st.session_state["raio_aplicado"] = 1
                if "ativo_aplicado" not in st.session_state:
                    st.session_state["ativo_aplicado"] = []

                # Slider agora é só ENTRADA (default 1 km); não dispara cálculo sozinho
                st.slider("📏 Raio de Atuação Visual (km):", 0, 50, 1, 1, key="slider_raio_atuacao")

                if st.button("🔎 Filtrar", use_container_width=True, type="primary", key="btn_filtrar_rota"):
                    st.session_state["raio_aplicado"] = int(st.session_state["slider_raio_atuacao"])
                    st.session_state["ativo_aplicado"] = st.session_state.get("campo_filtro_ativo_os", [])
                    st.rerun()

                # Mapa + cronograma usam SEMPRE o raio já aplicado
                raio_busca_km = int(st.session_state["raio_aplicado"])

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

                        # Coordenação de referência para a config operacional: a do escopo do
                        # usuário logado; se o escopo for "Todas", usa a mais frequente na lista.
                        _escopo_usr = st.session_state.get("escopo", "")
                        if _escopo_usr and _escopo_usr != "Todas":
                            coordenacao_rota = _escopo_usr
                        elif "Coordenacao" in com_coord.columns and not com_coord["Coordenacao"].dropna().empty:
                            coordenacao_rota = str(com_coord["Coordenacao"].dropna().mode().iloc[0]).strip()
                        else:
                            coordenacao_rota = "Paranapiacaba"
                        config_rota = carregar_config_operacional(coordenacao_rota)

                        # Escopo de dados: quando configurado para um plano específico (ex.: "Julho/2026",
                        # escolhido na tela de Configurações Operacionais como "Plano de Julho/2026"),
                        # mantém só as OS daquele Mês de Referência — evita mostrar backlog de outros ciclos.
                        if config_rota["escopo_dados"] != "todos" and "Plano_Mes_Referencia" in com_coord.columns:
                            com_coord = com_coord[com_coord["Plano_Mes_Referencia"].astype(str).str.strip() == config_rota["escopo_dados"]].copy()
                            if not com_coord.empty:
                                com_coord["Ordem_Prazo"] = com_coord["dt_prog_filtro"].apply(lambda dt: 1 if pd.notna(dt) and dt.date() < hoje_atual else (2 if pd.notna(dt) and dt.date() == hoje_atual else 3))
                                com_coord["Distancia_km"] = haversine_vectorized(lat_origem, lon_origem, com_coord["lat_patio"], com_coord["lon_patio"])

                        if com_coord.empty:
                            df_recomendado = com_coord
                        else:
                            # "Segurança da Operação": camada composta (classificação + criticidade),
                            # não um cascateamento simples. Correção de negócio validada com
                            # especialistas MRS (21/07/2026): não existe "Confiabilidade e Segurança" --
                            # toda OS é Segurança OU Confiabilidade. Rank0=Segurança+MuitoAlta (toda OS
                            # de Segurança já nasce Muito Alta, não existe Segurança+Alta/Média/Baixa na
                            # prática), Rank1=Confiabilidade+MuitoAlta, Rank2=Confiabilidade+demais
                            # níveis, Rank3=todo o resto (default/fallback). Tipo de Intervalo NÃO entra
                            # aqui: já é filtrado à parte (filtro_intervalo_sel) antes da roteirização
                            # chegar neste ponto.
                            classif_col = com_coord.get("Classificacao", pd.Series("Confiabilidade", index=com_coord.index)).astype(str)
                            crit_col = com_coord.get("Criticidade", pd.Series("", index=com_coord.index)).astype(str)
                            com_coord["_rank_seguranca_operacional"] = np.select(
                                [
                                    (classif_col == "Segurança") & (crit_col == "Muito Alta"),
                                    (classif_col == "Confiabilidade") & (crit_col == "Muito Alta"),
                                    (classif_col == "Confiabilidade") & (crit_col.isin(["Alta", "Média", "Baixa"])),
                                ],
                                [0, 1, 2],
                                default=3
                            )

                            # Ordem de Criticidade (filtro paralelo): reordena Muito Alta/Alta/Média/Baixa
                            # dentro do critério "criticidade" sem afetar o Criticidade_rank fixo usado
                            # pela trava de bloqueio (que continua identificando "Muito Alta" normalmente).
                            _mapa_ordem_crit = {nivel: idx for idx, nivel in enumerate(config_rota["ordem_criticidade"])}
                            com_coord["_rank_criticidade_custom"] = com_coord.get("Criticidade", pd.Series("", index=com_coord.index)).map(_mapa_ordem_crit).fillna(99)

                            _mapa_criterio_coluna = {
                                "seguranca_operacional": "_rank_seguranca_operacional",
                                "criticidade": "_rank_criticidade_custom",
                                "atraso": "Ordem_Prazo", "proximidade": "Distancia_km",
                            }
                            ordem_sort = [_mapa_criterio_coluna[c] for c in config_rota["ordem_criterios"] if c in _mapa_criterio_coluna]
                            if not ordem_sort:
                                ordem_sort = ["_rank_seguranca_operacional", "_rank_criticidade_custom", "Ordem_Prazo", "Distancia_km"]

                            df_recomendado = com_coord[com_coord["Distancia_km"] <= raio_busca_km].sort_values(by=ordem_sort)

                st.info(f"**{len(df_recomendado)} OS pendentes** encontradas no raio de {raio_busca_km} km.")

                # --- ENTREGA OFFLINE: PWA em HTTPS (único caminho — resolve GPS offline sem file://) ---
                if not df_recomendado.empty:
                    pacote_html_bytes = gerar_html_offline(df_recomendado, st.session_state.get("username", "tecnico"))

                    base_api = st.secrets.get(
                        "OFFLINE_API_URL",
                        "https://gestao-os-ee-mrs-producao.onrender.com/sincronizar_baixa_offline"
                    ).rsplit("/", 1)[0]
                    if st.button("🌐 Publicar Rota PWA (abrir online 1x no celular)", use_container_width=True, type="primary"):
                        try:
                            usuario_pwa = st.session_state.get("username", "tecnico")
                            # Pré-ping: acorda a API (cold start do Render) antes de publicar
                            with st.spinner("Acordando o servidor..."):
                                try:
                                    requests.get(f"{base_api}/health", timeout=30)
                                except Exception:
                                    pass
                            resp_pub = requests.post(
                                f"{base_api}/publicar_pacote",
                                data={"usuario": usuario_pwa},
                                # "html" vai como arquivo (nao campo de formulario) -- campos de
                                # formulario comuns tem teto de 1MB no Starlette; sem o limite de
                                # 100 OS por pacote, o HTML pode passar disso facilmente.
                                files={"html": ("pacote.html", pacote_html_bytes, "text/html")},
                                headers={"x-api-key": st.secrets.get("OFFLINE_API_KEY", "")},
                                timeout=30,
                            )
                            if resp_pub.status_code == 200:
                                rota = resp_pub.json().get("url", "")
                                st.session_state["rota_pwa_url"] = f"{base_api}{rota}"
                            else:
                                st.session_state.pop("rota_pwa_url", None)
                                st.error(f"Falha ao publicar ({resp_pub.status_code}): {resp_pub.text}")
                        except Exception as e:
                            st.session_state.pop("rota_pwa_url", None)
                            st.error(f"Erro ao publicar rota: {e}")

                    # Fora do "if st.button" para o link sobreviver aos reruns seguintes
                    # (ex.: o técnico mexe em outro campo) -- st.button só é True no ciclo
                    # em que foi clicado, então guardamos a URL publicada em session_state.
                    if st.session_state.get("rota_pwa_url"):
                        st.success("✅ Rota publicada! Toque para abrir 1x ONLINE no celular, depois use offline:")
                        st.link_button(
                            "🔗 Abrir Rota no Celular",
                            st.session_state["rota_pwa_url"],
                            use_container_width=True,
                            type="primary",
                        )
                        st.caption(f"Link (reserva, caso o botão não abra): {st.session_state['rota_pwa_url']}")
#endregion 10.3.2

#region 10.3.3: Apontamento + Cronograma (fragment unificado)
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

def _aplicar_filtros_cronograma(df_in: pd.DataFrame) -> pd.DataFrame:
    dfx = df_in.copy()
    especialidade_s = st.session_state.get("campo_filtro_especialidade_os", "Todas as Especialidades")
    if especialidade_s != "Todas as Especialidades" and "Especialidade" in dfx.columns:
        dfx = dfx[dfx["Especialidade"].astype(str).str.strip() == str(especialidade_s).strip()]
    ativos_s = st.session_state.get("campo_filtro_ativo_os", [])
    if ativos_s and "Ativo" in dfx.columns:
        _ativos_sel = {str(a).strip() for a in ativos_s}
        dfx = dfx[dfx["Ativo"].astype(str).str.strip().isin(_ativos_sel)]
    mes_s = st.session_state.get("campo_filtro_mes_os", "Todos os Meses")
    if mes_s != "Todos os Meses" and "dt_prog_filtro" in dfx.columns:
        _dtm = pd.to_datetime(dfx["dt_prog_filtro"], errors="coerce")
        dfx = dfx[_dtm.dt.strftime("%m/%Y") == mes_s]
    return dfx.copy()

def gerar_pdf_cronograma_bytes(df_pdf: pd.DataFrame, titulo: str = "Cronograma de Execução de Campo") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
    story.append(Spacer(1, 10))

    colunas_pdf = ["Ordem servico", "Data Prog.", "Ativo", "Patio", "Criticidade", "Classificacao", "Descrição Longa"]
    df_local = df_pdf.reindex(columns=colunas_pdf).fillna("").copy()

    data = [colunas_pdf]
    for _, row in df_local.iterrows():
        data.append([Paragraph(str(row[c]), styles["BodyText"]) for c in colunas_pdf])  # pyright: ignore[reportArgumentType]

    tabela = Table(
        data,
        repeatRows=1,
        colWidths=[70, 70, 80, 55, 70, 85, 300]
    )

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163A70")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(tabela)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# Mesmo layout de card usado no pacote offline (gerar_html_offline, classes .os-item/.chip/
# .desc-box) -- reaproveitado aqui (prefixo "sgo-" para não colidir com CSS interno do
# Streamlit) para a tela online mostrar o mesmo contexto da OS (Ativo, Atividade, Pátio,
# Especialidade, Descrição) antes do técnico anexar a evidência.
_CSS_CARD_OS = """
<style>
    .sgo-os-item { border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px; background: #FFFFFF; margin-bottom: 6px; }
    .sgo-os-header { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 10px; }
    .sgo-os-title { font-size: 16px; font-weight: 800; color: #0F172A; }
    .sgo-chip { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #E2E8F0; color: #334155; }
    .sgo-chip-critical { background: #FEE2E2; color: #991B1B; }
    .sgo-os-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; margin-bottom: 10px; }
    .sgo-os-meta { font-size: 13px; color: #475569; margin: 2px 0; }
    .sgo-desc-box { padding: 10px; background: #F8FAFC; border-radius: 10px; border: 1px solid #E2E8F0; font-size: 13px; color: #334155; }
    @media (max-width: 768px) {
        .sgo-os-grid { grid-template-columns: 1fr; }
        .sgo-os-header { flex-direction: column; align-items: flex-start; }
    }
</style>
"""

def _card_os_html(row) -> str:
    import html
    os_id = html.escape(str(row.get("Ordem servico", "")).strip())
    criticidade = html.escape(str(row.get("Criticidade", "")).strip())
    chip_cls = "sgo-chip sgo-chip-critical" if criticidade == "Muito Alta" else "sgo-chip"
    ativo = html.escape(str(row.get("Ativo", "")).strip())
    atividade = html.escape(str(row.get("Atividade ativo", "")).strip())
    patio = html.escape(str(row.get("Patio", "")).strip())
    especialidade = html.escape(str(row.get("Especialidade", "")).strip())
    descricao = html.escape(str(row.get("Descrição Longa", "")).strip()) or "—"
    return f"""
    <div class="sgo-os-item">
        <div class="sgo-os-header">
            <span class="sgo-os-title">OS {os_id}</span>
            <span class="{chip_cls}">{criticidade}</span>
        </div>
        <div class="sgo-os-grid">
            <div class="sgo-os-meta"><strong>Ativo:</strong> {ativo}</div>
            <div class="sgo-os-meta"><strong>Atividade:</strong> {atividade}</div>
            <div class="sgo-os-meta"><strong>Pátio:</strong> {patio}</div>
            <div class="sgo-os-meta"><strong>Especialidade:</strong> {especialidade}</div>
        </div>
        <div class="sgo-desc-box"><strong>Descrição:</strong><br>{descricao}</div>
    </div>
    """

def _render_apontamento(df_recomendado_ui: pd.DataFrame):
    # Retry só das OS que falharam (evidência não gravou -> baixa não foi gravada, ver
    # laço de submit mais abaixo): precisa reescrever session_state["campo_os_selecionadas"]
    # ANTES do st.multiselect ser instanciado neste run (senão o Streamlit acusa
    # StreamlitAPIException) -- mesmo padrão já usado pelo reset de filtros da sidebar
    # (_solicitar_reset_filtros).
    if st.session_state.pop("_apontamento_retry_falhas", False):
        st.session_state["campo_os_selecionadas"] = st.session_state.pop("_apontamento_os_falhas", [])
    _falhas_anteriores = st.session_state.pop("_apontamento_falhas_relatorio", None)

    st.markdown("---")
    st.markdown("#### ✅ Apontamento e Conclusão de OS")
    if _falhas_anteriores:
        st.error(f"⛔ {len(_falhas_anteriores)} OS NÃO foram gravadas (evidência falhou) — corrija a foto e reenvie:")
        for _os_falha, _motivo in _falhas_anteriores:
            st.warning(f"OS {_os_falha}: {_motivo}")
    if df_recomendado_ui.empty:
        st.info("Nenhuma OS encontrada para os filtros selecionados.")
        return

    # Grupo de bloqueio = (Ativo × Tipo de Intervalo). O foco nas OS Muito Alta é
    # isolado por tipo de intervalo: uma Muito Alta "Com Intervalo" só bloqueia as
    # demais "Com Intervalo" do mesmo ativo; idem para "Sem Intervalo". Assim o
    # colaborador não fica parado — pode atuar na outra fila enquanto prioriza a crítica.
    _ativo_g = df_recomendado_ui["Ativo"].astype(str).str.strip()
    if "Tipo_Intervalo" in df_recomendado_ui.columns:
        _int_g = df_recomendado_ui["Tipo_Intervalo"].fillna("N/D").astype(str).str.strip()
    else:
        _int_g = pd.Series("N/D", index=df_recomendado_ui.index)
    _grupo_bloq = _ativo_g + " | " + _int_g

    # BLOQUEIO POR MUITO ALTA (alinhado ao pacote offline): QUALQUER OS Muito Alta
    # pendente no grupo (Ativo x Intervalo) trava as de menor criticidade do mesmo grupo,
    # INDEPENDENTE da data de programacao. A condicao anterior "dt_prog <= hoje" deixava
    # passar Muito Alta com data futura OU sem data (NaT -> comparacao False), permitindo
    # baixar uma Alta antes da Muito Alta. O backlog (atraso) ja e priorizado na ordenacao
    # do df_recomendado (Ordem_Prazo), entao aqui basta garantir a prioridade da Muito Alta.
    mask_critica = (df_recomendado_ui["Criticidade_rank"] == 1)

    grupos_bloqueados = set(_grupo_bloq[mask_critica].unique())

    # Trava configurável por coordenação (modo "Plano de Guerra"): quando desativada para a
    # coordenação da OS, o bloqueio não se aplica àquela linha — mas o aviso abaixo continua
    # informando quais são as OS Muito Alta pendentes, sem impedir a seleção.
    if "Coordenacao" in df_recomendado_ui.columns:
        _coord_row = df_recomendado_ui["Coordenacao"].fillna("Paranapiacaba").astype(str).str.strip()
    else:
        _coord_row = pd.Series("Paranapiacaba", index=df_recomendado_ui.index)
    _trava_por_coord = {c: carregar_config_operacional(c)["trava_prioridade_ativa"] for c in _coord_row.unique()}
    _trava_ativa_row = _coord_row.map(_trava_por_coord).fillna(True)

    if grupos_bloqueados:
        if _trava_ativa_row.any() and (~_trava_ativa_row).any():
            st.warning(
                "⚠️ **Foco Operacional Ativo:** Conclua as OS Críticas (Muito Alta) para liberar as demais "
                "**do mesmo tipo de intervalo** (Com Intervalo e Sem Intervalo são filas independentes). "
                "Trava desativada para parte das OS listadas (plano de guerra)."
            )
        elif _trava_ativa_row.any():
            st.warning(
                "⚠️ **Foco Operacional Ativo:** Conclua as OS Críticas (Muito Alta) para liberar as demais "
                "**do mesmo tipo de intervalo** (Com Intervalo e Sem Intervalo são filas independentes)."
            )
        else:
            st.info(
                "ℹ️ **Foco Operacional (informativo):** existem OS Muito Alta pendentes nos grupos abaixo, "
                "mas a trava de bloqueio está desativada para esta coordenação (plano de guerra)."
            )
        # Libera a OS se ela própria for crítica, se o grupo (Ativo × Intervalo) dela não tem crítica
        # pendente, ou se a trava está desativada para a coordenação daquela OS.
        mask_liberada = mask_critica | (~_grupo_bloq.isin(grupos_bloqueados)) | (~_trava_ativa_row)
        opcoes_os = df_recomendado_ui[mask_liberada]["Ordem servico"].astype(str).unique().tolist()

        # OS bloqueadas ficam VISÍVEIS (sombreadas, com cadeado) para o técnico entender
        # o porquê, mas não entram no multiselect (não podem ser baixadas ainda).
        df_bloqueadas = df_recomendado_ui[~mask_liberada].copy()
        if not df_bloqueadas.empty:
            with st.expander(f"🔒 OS bloqueadas ({len(df_bloqueadas)}) — conclua a Muito Alta do grupo para liberar", expanded=True):
                _linhas_bloq = []
                for _, _r in df_bloqueadas.iterrows():
                    _os = str(_r.get("Ordem servico", "")).strip()
                    _at = str(_r.get("Ativo", "")).strip()
                    _cr = str(_r.get("Criticidade", "")).strip()
                    _iv = str(_r.get("Tipo_Intervalo", "N/D")).strip()
                    _linhas_bloq.append(
                        "<div style=\"display:flex;align-items:center;gap:10px;padding:8px 12px;margin:6px 0;"
                        "border:1px solid #E2E8F0;border-left:4px solid #94A3B8;border-radius:10px;"
                        "background:#F1F5F9;color:#64748B;opacity:0.85;\">"
                        "<span style=\"font-size:18px;\">🔒</span>"
                        f"<span><strong>OS {_os}</strong> &nbsp;·&nbsp; {_at} &nbsp;·&nbsp; "
                        f"<em>{_cr}</em> &nbsp;·&nbsp; {_iv}</span></div>"
                    )
                st.markdown("".join(_linhas_bloq), unsafe_allow_html=True)
                st.caption("🔓 Estas OS serão liberadas automaticamente após a conclusão da OS Muito Alta do mesmo Ativo e tipo de intervalo.")
    else:
        opcoes_os = df_recomendado_ui["Ordem servico"].astype(str).unique().tolist()

    os_selecionadas = st.multiselect(
        "1. Selecione as OSs que deseja baixar:",
        opcoes_os,
        key="campo_os_selecionadas"
    )

    if not os_selecionadas:
        return

    conn = get_connection()
    try:
        df_users_equipe = pd.read_sql_query("SELECT username, escopo FROM usuarios", conn)
    finally:
        release_connection(conn)

    # Equipe/matrícula só pode indicar colegas da MESMA lotação (escopo) do usuário logado --
    # Paranapiacaba só vê Paranapiacaba, Piaçaguera só vê Piaçaguera. "Todas" (perfis
    # Gerência/Administrador) continua vendo todo mundo, sem restrição.
    escopo_logado = st.session_state.get("escopo", "Todas")
    if escopo_logado != "Todas" and "escopo" in df_users_equipe.columns:
        df_users_equipe = df_users_equipe[df_users_equipe["escopo"].astype(str).str.strip() == str(escopo_logado).strip()]

    lista_equipe_disp = df_users_equipe["username"].dropna().astype(str).tolist()
    usr_logado = st.session_state.get("username", "")
    if usr_logado in lista_equipe_disp:
        lista_equipe_disp.remove(usr_logado)

    equipe_selecionada = st.multiselect(
        "2. Selecione a sua equipe:",
        lista_equipe_disp,
        key="campo_equipe_selecionada"
    )

    st.markdown("---")
    st.markdown("#### 📷 Evidências Fotográficas")
    st.caption("Registre a evidência de cada OS. A imagem será comprimida automaticamente.")
    st.markdown(_CSS_CARD_OS, unsafe_allow_html=True)

    # Sequenciamento por DESABILITAR, nao por esconder (16/07/2026): a tentativa
    # anterior (commit 90648b1) removia da tela o file_uploader das OS ja prontas
    # para liberar o da proxima -- isso fazia o Streamlit ESQUECER o arquivo ja
    # enviado, porque o file_uploader so mantem o valor de forma confiavel quando
    # renderizado em TODO rerun (causou perda real de OS em 16/07/2026, revertido
    # no commit 40f9148). Desta vez TODOS os campos continuam sendo renderizados
    # sempre (mesma chave, nunca somem) -- so o "disabled" muda, que e um
    # parametro oficial do widget e nao afeta a identidade/valor guardado.
    fotos_por_os = {}
    _bloqueado = False
    for _idx_foto, _os_id_raw in enumerate(os_selecionadas, start=1):
        _os_id_foto = str(_os_id_raw).strip()
        _linha_card = df_recomendado_ui.loc[
            df_recomendado_ui["Ordem servico"].astype(str).str.strip() == _os_id_foto
        ]
        if not _linha_card.empty:
            st.markdown(_card_os_html(_linha_card.iloc[0]), unsafe_allow_html=True)
        _arquivo = st.file_uploader(
            f"📸 Evidência da OS {_os_id_foto} ({_idx_foto}/{len(os_selecionadas)})",
            type=["jpg", "jpeg", "png"],
            key=f"foto_{_os_id_foto}",
            disabled=_bloqueado
        )
        fotos_por_os[_os_id_foto] = _arquivo
        if _arquivo is None and not _bloqueado:
            # Essa e a proxima pendente -- trava as OS seguintes ate ela ser preenchida.
            _bloqueado = True

    # Toggle FORA do form (para re-renderizar ao alternar): 1 horario que replica p/ todas as OS.
    usar_horario_unico = st.toggle(
        "⏱️ Usar um único horário para todas as OS selecionadas (baixa em massa)",
        value=True,
        key="campo_horario_unico"
    )

    with st.form("form_apontamento_os"):
        apontamentos = {}
        todos_preenchidos = True
        hoje_ref = agora_dt().date()

        if usar_horario_unico:
            st.markdown("#### ⏳ Apontamento de Tempo (aplicado a TODAS as OS selecionadas)")
            cg1, cg2, cg3, cg4 = st.columns(4)
            with cg1:
                d_ini_g = st.date_input("Data Início", key="date_ini_geral", value=hoje_ref, max_value=hoje_ref, format="DD/MM/YYYY")
            with cg2:
                h_ini_g = st.time_input("Horário Início", key="time_ini_geral", value=None)
            with cg3:
                d_fim_g = st.date_input("Data Fim", key="date_fim_geral", value=hoje_ref, max_value=hoje_ref, format="DD/MM/YYYY")
            with cg4:
                h_fim_g = st.time_input("Horário Fim", key="time_fim_geral", value=None)

            for os_id_raw in os_selecionadas:
                os_id = str(os_id_raw).strip()
                apontamentos[os_id] = {"data_ini": d_ini_g, "inicio": h_ini_g, "data_fim": d_fim_g, "fim": h_fim_g}

            if h_ini_g is None or h_fim_g is None:
                todos_preenchidos = False
        else:
            st.markdown("#### ⏳ Apontamento de Tempos Individuais")
            for os_id_raw in os_selecionadas:
                os_id = str(os_id_raw).strip()

                st.markdown(f"**OS: {os_id}**")
                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    d_ini = st.date_input(
                        "Data Início",
                        key=f"date_ini_{os_id}",
                        value=hoje_ref,
                        max_value=hoje_ref,
                        format="DD/MM/YYYY"
                    )
                with c2:
                    h_ini = st.time_input(
                        "Horário Início",
                        key=f"time_ini_{os_id}",
                        value=None
                    )
                with c3:
                    d_fim = st.date_input(
                        "Data Fim",
                        key=f"date_fim_{os_id}",
                        value=hoje_ref,
                        max_value=hoje_ref,
                        format="DD/MM/YYYY"
                    )
                with c4:
                    h_fim = st.time_input(
                        "Horário Fim",
                        key=f"time_fim_{os_id}",
                        value=None
                    )

                apontamentos[os_id] = {"data_ini": d_ini, "inicio": h_ini, "data_fim": d_fim, "fim": h_fim}

                if h_ini is None or h_fim is None:
                    todos_preenchidos = False

        st.markdown(
            """
            <style>
            .st-key-btn_concluir_gravar_os button {
                background-color: #16A34A !important;
                color: #FFFFFF !important;
                border-color: #16A34A !important;
            }
            .st-key-btn_concluir_gravar_os button:hover {
                background-color: #15803D !important;
                border-color: #15803D !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        submit_execucao = st.form_submit_button(
            "🚀 Concluir e Gravar OS(s)",
            use_container_width=True,
            key="btn_concluir_gravar_os"
        )

        if submit_execucao:
            origem = st.session_state.get("origem_tipo", "BASE")

            if origem != "GPS":
                st.warning("📍 A geolocalização é obrigatória. Atualize sua posição.")
                return

            if not todos_preenchidos:
                st.warning("⚠️ Preencha os horários de início e fim de todas as OSs.")
                return

            # Evidência fotográfica obrigatória: mesma trava do GPS acima. Sem foto anexada
            # para alguma OS selecionada, a baixa NÃO pode ser gravada (nem no banco, nem a
            # evidência), evitando concluir OS só com geolocalização.
            os_sem_foto = [
                os_id_raw for os_id_raw in os_selecionadas
                if fotos_por_os.get(str(os_id_raw).strip()) is None
            ]
            if os_sem_foto:
                st.warning(
                    "📷 Evidência fotográfica obrigatória. Anexe a foto antes de concluir a(s) OS: "
                    + ", ".join(str(o) for o in os_sem_foto)
                )
                return

            # Geofence 2,0km (Haversine): mesma trava aplicada no fluxo Offline (api.py).
            # O fluxo Online gravava a baixa direto no banco (upsert_baixa) sem nunca checar
            # a distância até o ativo — por isso conseguia concluir OS fora do raio permitido.
            lat_atual = st.session_state.get("lat_partida")
            lon_atual = st.session_state.get("lon_partida")
            os_fora_raio = []
            os_sem_geo = []
            for os_id_raw in os_selecionadas:
                os_id_geo = str(os_id_raw).strip()
                df_match_geo = st.session_state["df_os"].loc[
                    st.session_state["df_os"]["Ordem servico"].astype(str).str.strip() == os_id_geo
                ]
                # Fail-closed: se a OS não for localizada em df_os ou o pátio não resolver para uma
                # coordenada conhecida, a baixa é BLOQUEADA (não liberada) — antes o código dava
                # "continue" nesses casos, deixando a validação de geofence passar em branco.
                if df_match_geo.empty or lat_atual is None or lon_atual is None:
                    os_sem_geo.append(os_id_geo)
                    continue
                patio_geo = str(df_match_geo["Patio"].iloc[0]).strip().upper() if "Patio" in df_match_geo.columns else ""
                coord_ativo = COORDENADAS_FIXAS.get(patio_geo)
                if coord_ativo is None:
                    os_sem_geo.append(os_id_geo)
                    continue
                coord_os = str(df_match_geo["Coordenacao"].iloc[0]).strip() if "Coordenacao" in df_match_geo.columns else "Paranapiacaba"
                geofence_limite = carregar_config_operacional(coord_os)["geofence_km"]
                dist_km = haversine_vectorized(lat_atual, lon_atual, pd.Series([coord_ativo[0]]), pd.Series([coord_ativo[1]]))[0]
                if dist_km > geofence_limite:
                    os_fora_raio.append(f"{os_id_geo} ({dist_km:.1f}km, limite {geofence_limite:.1f}km)")

            if os_sem_geo:
                st.error(
                    "⛔ Não foi possível confirmar a localização do pátio para a(s) OS: "
                    + ", ".join(os_sem_geo) + ". Contate o suporte antes de concluir."
                )
                return

            if os_fora_raio:
                st.error(
                    "⛔ Bloqueio Geográfico: a conclusão só é permitida dentro do limite configurado para a coordenação (Haversine). "
                    "Fora do raio: " + ", ".join(os_fora_raio)
                )
                return

            geo_baixa = (
                f"{st.session_state.get('local_nome', 'Local')} "
                f"(Lat: {st.session_state.get('lat_partida')}, Lon: {st.session_state.get('lon_partida')})"
            )

            equipe_str = ", ".join(equipe_selecionada) if equipe_selecionada else "Sozinho"
            agora_ref = agora_dt().replace(tzinfo=None)

            # Validação de datas/horas: permite dia anterior (turno da noite que cruza a meia-noite),
            # mas bloqueia lançamento no futuro e fim anterior ao início.
            erros_dt = []
            for os_id_raw in os_selecionadas:
                os_id = str(os_id_raw).strip()
                ap = apontamentos[os_id]
                ini_dt = datetime.combine(ap["data_ini"], ap["inicio"])
                fim_dt = datetime.combine(ap["data_fim"], ap["fim"])
                if fim_dt < ini_dt:
                    erros_dt.append(f"OS {os_id}: o Fim (data/hora) é anterior ao Início.")
                elif ini_dt > agora_ref or fim_dt > agora_ref:
                    erros_dt.append(f"OS {os_id}: não é permitido lançar data/hora no futuro.")
            if erros_dt:
                for _e in erros_dt:
                    st.error("⛔ " + _e)
                return

            # Evidência ANTES da baixa, por OS (pedido 24/07/2026, incidente da madrugada
            # de 22-23/07/2026: OS 23613736/37/38 foram gravadas em "baixas" com
            # foto_evidencia = null porque a baixa era gravada num laço separado, ANTES
            # do upload da foto -- se a foto falhasse depois (ex.: acento no nome do
            # arquivo, ver _sanear_nome_arquivo), a OS ficava "concluída" sem evidência,
            # sem ninguém perceber além de um st.warning() que some da tela. Agora: sobe
            # a foto -> grava evidência -> só então grava a baixa DESSA OS. Se qualquer
            # etapa falhar, a OS entra em os_com_falha e o laço segue pras próximas --
            # nenhuma OS boa é perdida por causa de uma ruim.
            fotos_enviadas = 0
            os_com_falha = []  # [(os_id, motivo), ...]

            for os_id_raw in os_selecionadas:
                os_id = str(os_id_raw).strip()
                foto_da_os = fotos_por_os.get(os_id)

                if foto_da_os is None:
                    os_com_falha.append((os_id, "Evidência fotográfica não encontrada."))
                    continue

                try:
                    df_match = st.session_state["df_os"].loc[
                        st.session_state["df_os"]["Ordem servico"].astype(str).str.strip() == os_id
                    ]
                    if df_match.empty:
                        os_com_falha.append((os_id, "OS não encontrada na base carregada."))
                        continue

                    ativo_val = str(df_match["Ativo"].iloc[0]).strip()
                    atividade_val = (
                        str(df_match["Atividade ativo"].iloc[0]).strip()
                        if "Atividade ativo" in df_match.columns else "N_A"
                    )

                    nome_foto = _sanear_nome_arquivo(f"{ativo_val}__{atividade_val}__OS{os_id}.jpg")
                    url_foto = upload_foto_supabase(foto_da_os.getvalue(), nome_foto)

                    upsert_evidencia(
                        ativo=ativo_val,
                        atividade=atividade_val,
                        foto_url=url_foto,
                        os_referencia=os_id,
                        concluido_por=usr_logado,
                        geolocalizacao=(
                            f"Lat: {st.session_state.get('lat_partida')}, "
                            f"Lon: {st.session_state.get('lon_partida')}"
                        )
                    )

                    # Evidência OK -- só agora grava a baixa desta OS.
                    dt_prog = df_match["Data inicial programada"].iloc[0]
                    coord = df_match["Coordenacao"].iloc[0] if "Coordenacao" in df_match.columns else "Campo"

                    ap = apontamentos[os_id]
                    fim_dt = datetime.combine(ap["data_fim"], ap["fim"])

                    upsert_baixa(
                        os_id=os_id,
                        status=determinar_status_execucao(pd.to_datetime(dt_prog, errors="coerce"), fim_dt),
                        realizado_em_str=formatar_dt_br(fim_dt),
                        coordenacao=coord,
                        concluido_por=usr_logado,
                        geolocalizacao_baixa=geo_baixa,
                        equipe=equipe_str,
                        data_inicio=ap["data_ini"].strftime("%d/%m/%Y"),
                        hora_inicio=ap["inicio"].strftime("%H:%M:%S"),
                        data_fim=ap["data_fim"].strftime("%d/%m/%Y"),
                        hora_fim=ap["fim"].strftime("%H:%M:%S")
                    )
                    fotos_enviadas += 1

                except Exception as e_foto:
                    os_com_falha.append((os_id, str(e_foto)))

            if fotos_enviadas > 0:
                st.info(f"📷 {fotos_enviadas} OS concluída(s) e evidência(s) registrada(s) com sucesso!")

            if os_com_falha:
                # Persiste em session_state pro aviso e o retry (só das OS que falharam)
                # sobreviverem ao st.rerun() -- não gravar a baixa sem evidência é a regra,
                # mas o técnico não pode perder as OS que já sincronizaram certo.
                st.session_state["_apontamento_falhas_relatorio"] = os_com_falha
                st.session_state["_apontamento_retry_falhas"] = True
                st.session_state["_apontamento_os_falhas"] = [_os for _os, _ in os_com_falha]
            else:
                st.success("✅ Execução registrada com sucesso!")

            time.sleep(1.5)
            st.rerun()

def _render_cronograma(df_recomendado: pd.DataFrame):
    st.markdown("### 🗓️ Cronograma de Execução de Campo")
    st.caption("OS Pendentes recomendadas no raio de atuação visual por prioridade")
    if not df_recomendado.empty:
        df_tabela_campo = _aplicar_filtros_cronograma(df_recomendado)
        df_tabela_campo["Data Prog."] = pd.to_datetime(df_tabela_campo["dt_prog_filtro"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")

        if df_tabela_campo.empty:
            st.info("Nenhuma OS pendente encontrada no cronograma para os filtros selecionados.")
        else:
            col_cro_1, col_cro_2 = st.columns([8, 2])

            with col_cro_2:
                pdf_bytes = gerar_pdf_cronograma_bytes(df_tabela_campo)
                st.download_button(
                    "📄 Gerar Impressão PDF",
                    data=pdf_bytes,
                    file_name="cronograma_execucao_campo.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            df_exibicao = df_tabela_campo[
                ["Ordem servico", "Data Prog.", "Ativo", "Patio", "Criticidade", "Classificacao", "Descrição Longa"]
            ].fillna("").copy()


            st.dataframe(
                df_exibicao,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ordem servico": st.column_config.TextColumn("OS", width="small"),
                    "Data Prog.": st.column_config.TextColumn("Data Prog.", width="small"),
                    "Ativo": st.column_config.TextColumn("Ativo", width="small"),
                    "Patio": st.column_config.TextColumn("Pátio", width="small"),
                    "Criticidade": st.column_config.TextColumn("Criticidade", width="small"),
                    "Classificacao": st.column_config.TextColumn("Classificação", width="small"),
                    "Descrição Longa": st.column_config.TextColumn("Descrição Longa", width="large"),
                }
            )
    else:
        st.info("Sem OS pendentes para exibir no cronograma.")

@st.fragment
def bloco_roteirizacao_interativo():
    if not df_recomendado.empty:
        _especialidades_disp = (
            sorted(df_recomendado["Especialidade"].dropna().astype(str).str.strip().unique().tolist())
            if "Especialidade" in df_recomendado.columns else []
        )
        _ativos_disp = sorted(df_recomendado["Ativo"].dropna().astype(str).str.strip().unique().tolist())
        _dt_meses = pd.to_datetime(df_recomendado["dt_prog_filtro"], errors="coerce").dropna()
        _meses_disp = sorted(_dt_meses.dt.strftime("%m/%Y").unique().tolist(), key=lambda mv: (mv[3:], mv[:2]))
    else:
        _especialidades_disp = []
        _ativos_disp = []
        _meses_disp = []
    _opcoes_especialidades = ["Todas as Especialidades"] + [e for e in _especialidades_disp if e and e != "N/D"]
    _opcoes_meses = ["Todos os Meses"] + _meses_disp

    if st.session_state.get("campo_filtro_especialidade_os") not in _opcoes_especialidades:
        st.session_state["campo_filtro_especialidade_os"] = "Todas as Especialidades"
    # Multiseleção de Ativos (autorizado em reunião — colaborador pode filtrar e dar baixa
    # em massa em mais de um Ativo ao mesmo tempo). Lista vazia = sem filtro (Todos os Ativos).
    st.session_state["campo_filtro_ativo_os"] = [
        a for a in st.session_state.get("campo_filtro_ativo_os", []) if a in _ativos_disp
    ]
    if st.session_state.get("campo_filtro_mes_os") not in _opcoes_meses:
        st.session_state["campo_filtro_mes_os"] = "Todos os Meses"

    with col_acao:
        st.markdown("---")
        col_f_especialidade, col_f_ativo, col_f_mes = st.columns(3)
        with col_f_especialidade:
            st.selectbox("🛠️ Filtrar por Especialidade:", _opcoes_especialidades, key="campo_filtro_especialidade_os")
        with col_f_ativo:
            st.multiselect(
                "🔍 Filtrar OS do cronograma por Ativo (vazio = todos):",
                _ativos_disp,
                key="campo_filtro_ativo_os"
            )
        with col_f_mes:
            st.selectbox("🗓️ Filtrar por Mês (programação):", _opcoes_meses, key="campo_filtro_mes_os")

    df_recomendado_ui = _aplicar_filtros_cronograma(df_recomendado)
    _render_apontamento(df_recomendado_ui)
    st.markdown("---")
    _render_cronograma(df_recomendado)

if tab2 is not None:
    with tab2:
        bloco_roteirizacao_interativo()
        st.markdown("---")
#endregion 10.3.3

#region 10.3.4: Mapa Interativo Otimizado (Cache da Malha)
if tab2 is not None:
  with col_mapa:  # pyright: ignore[reportGeneralTypeIssues]
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
            if geom is None or geom.is_empty:
                continue
            if geom.geom_type == 'LineString':
                adicionar_trecho(geom)
            elif geom.geom_type == 'MultiLineString':
                for subgeom in geom.geoms:
                    adicionar_trecho(subgeom)

    folium.Marker(location=[lat_origem, lon_origem], tooltip=f"Origem: {st.session_state['local_nome']}", icon=folium.Icon(color="red", icon="home" if st.session_state.get("origem_tipo") != "GPS" else "map-marker", prefix="fa")).add_to(mapa)
    folium.Circle(radius=raio_busca_km * 1000, location=[lat_origem, lon_origem], color="#3B82F6", fill=True, fill_opacity=0.08, weight=2, tooltip=f"Raio: {raio_busca_km} km").add_to(mapa)

    if not df_recomendado.empty:
        agg_map = df_recomendado.groupby("Patio", as_index=False).agg(lat_patio=("lat_patio", "first"), lon_patio=("lon_patio", "first"), qtd_os=("Ordem servico", "count"), menor_dist=("Distancia_km", "min"))
        for _, row in agg_map.iterrows():
            folium.CircleMarker(location=[row["lat_patio"], row["lon_patio"]], radius=6, color="#1D4ED8", weight=1.5, fill=True, fill_color="#3B82F6", fill_opacity=0.95, tooltip=f"Pátio: {row['Patio']}<br>OS: {row['qtd_os']}<br>Distância: {row['menor_dist']:.1f} km").add_to(mapa)

    st_folium(mapa, height=650, use_container_width=True, returned_objects=[], key="mapa_final_limpo")
    st.markdown("---")
    #endregion 10.3.4

#region 10.3.5: (movido para 10.3.3 - fragment unificado)
# O Cronograma de Execução agora é renderizado dentro de bloco_roteirizacao_interativo (região 10.3.3),
# no mesmo fragment do Apontamento, para que o filtro Ativo/Mês não reconstrua o mapa (10.3.4).
#endregion 10.3.5

#region 10.3.6: Relatório de OS Concluídas (Fim de Turno)

def gerar_pdf_concluidas_bytes(df_pdf, titulo="OS Concluídas - Fim de Turno"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{titulo}</b>", styles["Title"]), Spacer(1, 10)]
    colunas_pdf = ["OS", "Data Prog. (Data Inicial Programada)", "Patio", "Ativo", "Criticidade", "Classificação", "Data/Hora Realizado"]
    df_local = df_pdf.reindex(columns=colunas_pdf).fillna("").copy()
    data = [colunas_pdf]
    for _, row in df_local.iterrows():
        data.append([Paragraph(str(row[c]), styles["BodyText"]) for c in colunas_pdf])  # pyright: ignore[reportArgumentType]
    tabela = Table(data, repeatRows=1, colWidths=[65, 140, 60, 100, 75, 90, 110])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163A70")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabela)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

if tab2 is not None:
    with tab2:
        st.markdown("---")
        st.markdown("### 🏁 Relatório de OS Concluídas (Fim de Turno)")
        st.caption("PDF das OS concluídas para conferência ao final do turno.")
        _status_concluido_rel = _status_prazo | _status_atraso
        if "Status_norm" in df_filtrado.columns:
            df_conc = df_filtrado[df_filtrado["Status_norm"].isin(_status_concluido_rel)].copy()
        else:
            df_conc = df_filtrado.iloc[0:0].copy()

        usuario_atual = str(st.session_state.get("username", "")).strip()
        somente_minhas = st.checkbox("Mostrar apenas as OS que EU concluí", value=True, key="chk_rel_minhas")
        if somente_minhas and usuario_atual and "Concluído por" in df_conc.columns:
            df_conc = df_conc[df_conc["Concluído por"].astype(str).str.strip().str.casefold() == usuario_atual.casefold()]

        # Filtro por data de execução (turno): usa "dt_realizado", já calculado uma vez
        # em df_visao (linha ~908) e preservado até aqui por aplicar_filtros_sidebar --
        # é um filtro em memória sobre dado já carregado, sem nova consulta ao banco.
        data_turno_sel = st.date_input(
            "📅 Data de execução (turno)",
            value=agora_dt().date(),
            key="data_rel_turno",
            format="DD/MM/YYYY",
        )
        if "dt_realizado" in df_conc.columns:
            df_conc = df_conc[pd.to_datetime(df_conc["dt_realizado"], errors="coerce").dt.date == data_turno_sel]

        if df_conc.empty:
            st.info("Nenhuma OS concluída encontrada para os filtros atuais.")
        else:
            df_rel = pd.DataFrame({
                "OS": df_conc["Ordem servico"].astype(str),
                "Data Prog. (Data Inicial Programada)": pd.to_datetime(df_conc["dt_prog_filtro"], errors="coerce").dt.strftime("%d/%m/%Y").fillna(""),
                "Patio": df_conc["Patio"].astype(str),
                "Ativo": df_conc["Ativo"].astype(str),
                "Criticidade": df_conc["Criticidade"].astype(str),
                "Classificação": df_conc["Classificacao"].astype(str),
                "Data/Hora Realizado": pd.to_datetime(df_conc["Data/Hora Realizado"], dayfirst=True, errors="coerce").dt.strftime("%d/%m/%Y %H:%M").fillna(""),
            })
            st.success(f"✅ {len(df_rel)} OS concluída(s) no período/filtros atuais.")
            col_rel_1, col_rel_2 = st.columns([8, 2])
            with col_rel_2:
                pdf_conc_bytes = gerar_pdf_concluidas_bytes(df_rel)
                st.download_button("📄 Gerar Relatório PDF", data=pdf_conc_bytes,
                    file_name=f"OS_Concluidas_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", use_container_width=True)
            st.dataframe(df_rel, use_container_width=True, hide_index=True)
#endregion 10.3.6

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
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT senha_hash FROM usuarios WHERE username = %s", (st.session_state.get("username"),))
                        row = cur.fetchone()
                        cur.close()
                    finally:
                        release_connection(conn)
                    if row and row[0] == hash_senha(senha_confirm): st.session_state["gov_auth_ok"] = True; st.rerun()
                    else: st.error("❌ Senha incorreta. Acesso negado.")
        st.stop()
#endregion 11.1

#region 11.2: Carregamento de dados de auditoria
    @st.cache_data(show_spinner=False, ttl=300)
    def _carregar_baixas_logs_governanca():
        # Cache adicionado em 22/07/2026 -- plano Neon Free perto do teto de Network transfer
        # (5GB/mes). Sem cache, a tabela "baixas" inteira era relida a cada rerun (inclusive ao
        # clicar em "Aplicar Filtros" na sidebar, que forca rerun completo do app). TTL de 5min
        # é aceitável pra uma tela de auditoria/governança.
        conn = get_connection()
        try:
            df_b = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por, geolocalizacao_baixa, equipe, data_inicio, hora_inicio, data_fim, hora_fim FROM baixas", conn)
            df_l = pd.read_sql_query("SELECT username, data_hora_login, geolocalizacao_login FROM logs_acesso", conn)
        finally:
            release_connection(conn)
        return df_b, df_l

    @st.cache_data(show_spinner=False, ttl=300)
    def _carregar_usuarios_nome_governanca():
        conn = get_connection()
        try: return pd.read_sql_query("SELECT username, nome FROM usuarios", conn)
        finally: release_connection(conn)

    with st.spinner("Compilando logs de auditoria e telemetria..."):
        df_baixas_full, df_logs = _carregar_baixas_logs_governanca()

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
        df_gov["Data_Real_DT"] = pd.to_datetime(df_gov["data_fim"], dayfirst=True, errors="coerce")
        df_gov["Data_Real"] = df_gov["Data_Real_DT"].dt.date
        
        df_gov["Via_GPS"] = df_gov["geolocalizacao_baixa"].apply(lambda x: 0 if "Base" in str(x) or "Sede" in str(x) else 1)
        df_gov["Alta_Prioridade"] = df_gov["Criticidade_rank"].apply(lambda x: 1 if x in [1, 2] else 0)

        df_users_gov = _carregar_usuarios_nome_governanca()

        mapa_nome_usuario_gov = {}
        if not df_users_gov.empty:
            df_users_gov["username_key"] = df_users_gov["username"].astype(str).str.strip()
            df_users_gov["nome_clean"] = df_users_gov["nome"].fillna("").astype(str).str.strip()
            mapa_nome_usuario_gov = dict(zip(df_users_gov["username_key"], df_users_gov["nome_clean"]))

        def label_colaborador_gov(valor):
            matricula = str(valor).strip()
            if not matricula or matricula.lower() in ("nan", "none", "null"): return "Não informado"
            nome = str(mapa_nome_usuario_gov.get(matricula, "")).strip()
            return f"{nome} ({matricula})" if nome else matricula

        df_gov["Colaborador"] = df_gov["concluido_por"].apply(label_colaborador_gov)
#endregion 11.2

#region 11.3: Fragmento de Governança (@st.fragment)
    @st.fragment
    def fragmento_governanca():
        
        df_gov_local = df_gov.copy()

        # Garante que existe uma coluna de exibição para colaborador
        if "Colaborador" not in df_gov_local.columns:
            df_gov_local["Colaborador"] = df_gov_local["concluido_por"].astype(str).str.strip()

        # Participantes = executante (Colaborador) + co-executantes (campo "equipe", texto
        # livre separado por vírgula). Antes o filtro só olhava "Colaborador" (executante) --
        # quem entrava só como equipe/co-executante não aparecia na lista de opções nem
        # batia no filtro, mesmo tendo participado da OS de fato (feedback de 22/07/2026).
        def _lista_equipe_gov(valor):
            texto = str(valor).strip()
            if not texto or texto.lower() in ("nan", "none", "null", "sozinho", "sozinho (nenhum)"):
                return []
            return [p.strip() for p in texto.split(",") if p.strip()]

        df_gov_local["Equipe_labels"] = df_gov_local.get("equipe", pd.Series("", index=df_gov_local.index)).apply(
            lambda v: [label_colaborador_gov(m) for m in _lista_equipe_gov(v)]
        )
        df_gov_local["Participantes"] = df_gov_local.apply(
            lambda r: [r["Colaborador"]] + r["Equipe_labels"], axis=1
        )

        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            _todos_participantes = set()
            for _lst in df_gov_local["Participantes"]:
                _todos_participantes.update(p for p in _lst if p)
            tecnicos_disp = sorted(_todos_participantes)

            tec_selecionado = st.multiselect(
                "👤 Filtrar Colaborador(es) (executante ou co-executante):",
                tecnicos_disp,
                default=tecnicos_disp
            )

        with col_f2:
            patios_gov = sorted(
                df_gov_local["Patio"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            patio_selecionado = st.multiselect(
                "📍 Filtrar Pátio(s):",
                patios_gov,
                default=patios_gov
            )

        with col_f3:
            datas_validas = df_gov_local["Data_Real"].dropna()

            if not datas_validas.empty:
                min_d = datas_validas.min()
                max_d = datas_validas.max()
            else:
                min_d = max_d = datetime.now().date()

            data_gov = st.date_input(
                "📅 Período de Execução:",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                format="DD/MM/YYYY"
            )

        if isinstance(data_gov, tuple) and len(data_gov) == 2:
            d_inicio, d_fim = data_gov
        elif isinstance(data_gov, tuple) and len(data_gov) == 1:
            d_inicio = d_fim = data_gov[0]
        else:
            d_inicio = d_fim = data_gov

        df_gov_f = df_gov_local[
            (df_gov_local["Participantes"].apply(lambda lst: any(p in tec_selecionado for p in lst)))
            & (df_gov_local["Patio"].isin(patio_selecionado))
            & (df_gov_local["Data_Real"] >= d_inicio)
            & (df_gov_local["Data_Real"] <= d_fim)
        ].copy()

        #region 11.3.1: Helper de Eixo Temporal da Governança
        data_ini_gov = pd.to_datetime(d_inicio).normalize()
        data_fim_gov = pd.to_datetime(d_fim).normalize()

        idx_gov = pd.date_range(
            start=data_ini_gov,  # pyright: ignore[reportArgumentType]
            end=data_fim_gov,  # pyright: ignore[reportArgumentType]
            freq="D"
        )

        def serie_time_gov(serie):
            """
            Converte uma Series indexada por data em pares [YYYY-MM-DD, valor],
            formato correto para ECharts com xAxis type='time'.
            """
            return [
                [idx.strftime("%Y-%m-%d"), int(valor)]
                for idx, valor in serie.items()
            ]

        eixo_time_gov = {
            "type": "time",
            "min": data_ini_gov.strftime("%Y-%m-%d"),
            "max": data_fim_gov.strftime("%Y-%m-%d"),
            "axisLabel": {
                # Template nativo do eixo "time" do ECharts (sem JS) -- JsCode parou de
                # ser serializado apos a nuvem forcar upgrade do Streamlit.
                "formatter": "{dd}/{MM}"
            }
        }

        chave_periodo_gov = (
            f"{data_ini_gov.strftime('%Y%m%d')}_"
            f"{data_fim_gov.strftime('%Y%m%d')}"
        )
        #endregion 11.3.1

        if df_gov_f.empty:
            st.info("Nenhuma execução encontrada para os filtros selecionados.")
            return

        total_os_gov = len(df_gov_f)
        tme_minutos = df_gov_f["Tempo_Minutos"].fillna(0).mean()
        taxa_gps = (df_gov_f["Via_GPS"].sum() / total_os_gov) * 100 if total_os_gov > 0 else 0
        taxa_prio = (df_gov_f["Alta_Prioridade"].sum() / total_os_gov) * 100 if total_os_gov > 0 else 0

        c_k1, c_k2, c_k3, c_k4 = st.columns(4)
        c_k1.metric("🔧 Volume de Execução", f"{total_os_gov} OS")
        c_k2.metric(
            "⏱️ Tempo Médio / OS (TME)",
            f"{int(tme_minutos // 60)}h {int(tme_minutos % 60):02d}m"
            if not pd.isna(tme_minutos)
            else "0h 00m"
        )
        c_k3.metric("🎯 Aderência à Prioridade", f"{taxa_prio:.1f}%")
        c_k4.metric("📍 Integridade de GPS", f"{taxa_gps:.1f}%")
        st.markdown("---")
#endregion 11.3

#region 11.4: Volume Diário e Produtividade Acumulada
        col_l1_c1, col_l1_c2 = st.columns(2, gap="large")

        # -----------------------------
        # REALIZADO DIÁRIO
        # -----------------------------
        df_real_base = df_gov_f.copy()

        # Já convertido na 11.2 nativamente
        df_real_base["Data_Real_DT"] = df_real_base["Data_Real_DT"].dt.normalize()

        df_real_base = df_real_base[
            (df_real_base["Data_Real_DT"] >= data_ini_gov)
            & (df_real_base["Data_Real_DT"] <= data_fim_gov)
        ].copy()

        real_diario_gov = (
            df_real_base
            .groupby("Data_Real_DT")
            .size()
            .reindex(idx_gov, fill_value=0)
            .rename("Realizado")
        )

        # -----------------------------
        # PLANEJADO / BACKLOG DIÁRIO
        # -----------------------------
        df_plan_base = df_os_base.copy()

        # O SEGREDO DA ABA 1 (SEM dayfirst=True para planilhas do SAP)
        df_plan_base["Data_Prog_DT"] = pd.to_datetime(df_plan_base["Data inicial programada"], errors="coerce").dt.normalize()

        if "Patio" in df_plan_base.columns:
            df_plan_base = df_plan_base[df_plan_base["Patio"].astype(str).isin([str(p) for p in patio_selecionado])].copy()

        df_plan_base = df_plan_base[
            (df_plan_base["Data_Prog_DT"] >= data_ini_gov)
            & (df_plan_base["Data_Prog_DT"] <= data_fim_gov)
        ].copy()

        plan_diario_gov = (
            df_plan_base
            .groupby("Data_Prog_DT")
            .size()
            .reindex(idx_gov, fill_value=0)
            .rename("Planejado_Backlog")
        )

        with col_l1_c1:
            st.markdown("#### 📈 Volume Diário")

            st_echarts(
                options={
                    "tooltip": {"trigger": "axis"},
                    "legend": {
                        "data": ["Volume Diário", "Planejado + Backlog"],
                        "bottom": "0%"
                    },
                    "toolbox": {
                        "show": True,
                        "feature": {
                            "magicType": {
                                "type": ["line", "bar"],
                                "title": {
                                    "line": "Linha",
                                    "bar": "Barra"
                                }
                            },
                            "restore": {"title": "Restaurar"},
                            "saveAsImage": {"title": "Salvar Imagem"}
                        }
                    },
                    "dataZoom": [
                        {
                            "type": "slider",
                            "show": True,
                            "xAxisIndex": [0],
                            "start": 0,
                            "end": 100,
                            "bottom": "5%",
                            "filterMode": "none"
                        }
                    ],
                    "grid": {
                        "left": "5%",
                        "right": "5%",
                        "bottom": "25%",
                        "top": "15%",
                        "containLabel": True
                    },
                    "xAxis": eixo_time_gov,
                    "yAxis": {"type": "value"},
                    "series": [
                        {
                            "name": "Volume Diário",
                            "type": "bar",
                            "data": serie_time_gov(real_diario_gov),
                            "itemStyle": {"color": "#3B82F6"}
                        },
                        {
                            "name": "Planejado + Backlog",
                            "type": "line",
                            "data": serie_time_gov(plan_diario_gov),
                            "smooth": True,
                            "lineStyle": {
                                "type": "dashed",
                                "color": "#64748B",
                                "width": 3
                            },
                            "itemStyle": {"color": "#64748B"}
                        }
                    ]
                },
                height="350px",
                theme="streamlit",
                key=f"gov_vol_diario_{chave_periodo_gov}"
            )

        with col_l1_c2:
            st.markdown("#### 📈 Produtividade Acumulada")

            real_acum_gov = real_diario_gov.cumsum()
            plan_acum_gov = plan_diario_gov.cumsum()

            st_echarts(
                options={
                    "tooltip": {"trigger": "axis"},
                    "legend": {
                        "data": ["Realizado Acumulado", "Planejado Acumulado"],
                        "bottom": "0%"
                    },
                    "toolbox": {
                        "show": True,
                        "feature": {
                            "magicType": {
                                "type": ["line", "bar"],
                                "title": {
                                    "line": "Linha",
                                    "bar": "Barra"
                                }
                            },
                            "restore": {"title": "Restaurar"},
                            "saveAsImage": {"title": "Salvar Imagem"}
                        }
                    },
                    "dataZoom": [
                        {
                            "type": "slider",
                            "show": True,
                            "xAxisIndex": [0],
                            "start": 0,
                            "end": 100,
                            "bottom": "5%",
                            "filterMode": "none"
                        }
                    ],
                    "grid": {
                        "left": "5%",
                        "right": "5%",
                        "bottom": "25%",
                        "top": "15%",
                        "containLabel": True
                    },
                    "xAxis": eixo_time_gov,
                    "yAxis": {"type": "value"},
                    "series": [
                        {
                            "name": "Realizado Acumulado",
                            "type": "line",
                            "smooth": True,
                            "data": serie_time_gov(real_acum_gov),
                            "areaStyle": {
                                "color": "rgba(59,130,246,0.15)"
                            },
                            "lineStyle": {
                                "color": "#3B82F6",
                                "width": 3
                            },
                            "itemStyle": {
                                "color": "#3B82F6"
                            }
                        },
                        {
                            "name": "Planejado Acumulado",
                            "type": "line",
                            "smooth": True,
                            "data": serie_time_gov(plan_acum_gov),
                            "lineStyle": {
                                "type": "dashed",
                                "color": "#64748B",
                                "width": 3
                            },
                            "itemStyle": {
                                "color": "#64748B"
                            }
                        }
                    ]
                },
                height="350px",
                theme="streamlit",
                key=f"gov_prod_acum_{chave_periodo_gov}"
            )
#endregion 11.4

#region 11.5: Produtividade Individual, Esforço, Tipo de OS x Frequência e Aderência (2 colunas)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        col_l2_c1, col_l2_c2 = st.columns(2, gap="medium")

        with col_l2_c1:
            st.markdown("#### 👥 Produtividade Individual")
            df_crit = df_gov_f.groupby("Criticidade").size().reset_index(name="Volume")

            st_echarts(
                options={
                    "tooltip": {"trigger": "item"},
                    "legend": {"orient": "horizontal", "bottom": "0%", "textStyle": {"fontSize": 11}},
                    "series": [
                        {
                            "type": "pie",
                            "radius": ["38%", "62%"],
                            "center": ["50%", "42%"],
                            "data": [
                                {
                                    "value": int(r["Volume"]),
                                    "name": str(r["Criticidade"])
                                }
                                for _, r in df_crit.iterrows()
                            ],
                            "label": {"show": True, "formatter": "{c}"}
                        }
                    ]
                },
                height="380px",
                key="gov_donut_criticidade"
            )

        with col_l2_c2:
            st.markdown("#### ⏱️ Esforço x Classificação")

            df_classif = (
                df_gov_f
                .groupby("Classificacao")
                .agg(Tempo_Medio=("Tempo_Minutos", "mean"))
                .fillna(0)
                .reset_index()
                .sort_values("Tempo_Medio", ascending=True)
            )

            st_echarts(
                options={
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": "3%", "right": "8%", "bottom": "6%", "top": "5%", "containLabel": True},
                    "xAxis": {"type": "value"},
                    "yAxis": {
                        "type": "category",
                        "data": df_classif["Classificacao"].tolist(),
                        "axisLabel": {"fontSize": 11}
                    },
                    "series": [
                        {
                            "type": "bar",
                            "data": df_classif["Tempo_Medio"].round(1).tolist(),
                            "itemStyle": {"color": "#F59E0B"},
                            "label": {"show": True, "position": "right", "color": "#475569", "fontSize": 11}
                        }
                    ]
                },
                height="380px",
                key="gov_esforco_classe"
            )

        st.markdown("<br>", unsafe_allow_html=True); st.markdown("---")
        st.markdown("#### 🔁 Tipo de OS x Frequência")

        agg_heatmap = (
            df_gov_f
            .groupby(["Patio", "Classificacao"])
            .size()
            .reset_index(name="Total")
        )

        p_list = sorted(df_gov_f["Patio"].dropna().unique().tolist())
        c_list = ["Segurança", "Confiabilidade"]

        h_data = []
        max_v = 0

        for yi, c_n in enumerate(c_list):
            for xi, p_n in enumerate(p_list):
                filtro_h = agg_heatmap[
                    (agg_heatmap["Patio"] == p_n)
                    & (agg_heatmap["Classificacao"] == c_n)
                ]

                val = int(filtro_h["Total"].iloc[0]) if not filtro_h.empty else 0
                h_data.append([xi, yi, val])
                max_v = max(max_v, val)

        st_echarts(
            options={
                "tooltip": {"position": "top"},
                "grid": {
                    "height": "65%",
                    "top": "5%",
                    "bottom": "20%",
                    "left": "10%",
                    "right": "5%",
                    "containLabel": True
                },
                "xAxis": {
                    "type": "category",
                    "data": p_list,
                    "axisLabel": {"interval": 0, "rotate": 45}
                },
                "yAxis": {
                    "type": "category",
                    "data": c_list
                },
                "visualMap": {
                    "min": 0,
                    "max": max_v if max_v > 0 else 5,
                    "orient": "horizontal",
                    "left": "center",
                    "bottom": "0%",
                    "inRange": {
                        "color": ["#F8FAFC", "#93C5FD", "#1D4ED8"]
                    }
                },
                "series": [
                    {
                        "type": "heatmap",
                        "data": h_data,
                        "label": {"show": True},
                        "itemStyle": {
                            "borderColor": "#FFFFFF",
                            "borderWidth": 1.5
                        }
                    }
                ]
            },
            height="420px",
            key="gov_heatmap_freq"
        )

        # Aderência em linha própria, largura cheia (pedido de 22/07/2026) --
        # antes dividia coluna com "Tipo de OS x Frequência", ficando apertado.
        st.markdown("<br>", unsafe_allow_html=True); st.markdown("---")
        st.markdown("#### 🕒 Aderência: Login vs. Apontamento")

        df_logs_local = df_logs.copy()
        df_logs_local["dt_login_calc"] = pd.to_datetime(df_logs_local["data_hora_login"], errors="coerce")
        df_logs_local["Data_Real_Pure"] = df_logs_local["dt_login_calc"].dt.date

        # Junta Data e Hora como Strings e converte nativamente com dayfirst=True
        df_gov_f["dt_baixa_calc"] = pd.to_datetime(df_gov_f["data_fim"].astype(str).str.strip() + " " + df_gov_f["hora_fim"].astype(str).str.strip(), dayfirst=True, errors="coerce")

        # idxmin (em vez de min) pra trazer junto a geolocalizacao_baixa do registro exato da
        # primeira baixa do dia -- necessario pro tooltip do grafico de Aderencia mostrar a
        # localizacao real, e nao so o horario (pedido de 22/07/2026).
        _idx_primeira_baixa = df_gov_f.dropna(subset=["dt_baixa_calc"]).groupby(["concluido_por", "Data_Real"])["dt_baixa_calc"].idxmin()
        df_primeira_baixa = (
            df_gov_f.loc[_idx_primeira_baixa, ["concluido_por", "Data_Real", "dt_baixa_calc", "geolocalizacao_baixa"]]
            .rename(columns={"dt_baixa_calc": "dt_baixa_1os"})
            .reset_index(drop=True)
        )

        # >> O DATAFRAME DA ADERÊNCIA RENASCE AQUI <<
        df_aderencia = df_logs_local.merge(df_primeira_baixa, left_on=["username", "Data_Real_Pure"], right_on=["concluido_por", "Data_Real"])

        if not df_aderencia.empty:
            dt_login = df_aderencia["dt_login_calc"]
            dt_baixa = df_aderencia["dt_baixa_1os"]

            df_aderencia["x_date"] = dt_login.dt.strftime("%d/%m")
            df_aderencia["y_login_frac"] = dt_login.dt.hour + dt_login.dt.minute / 60.0
            df_aderencia["y_baixa_frac"] = dt_baixa.dt.hour + dt_baixa.dt.minute / 60.0

            df_aderencia = df_aderencia.dropna(subset=["y_login_frac", "y_baixa_frac"]).sort_values("Data_Real_Pure")

            if not df_aderencia.empty:
                # Categorias do eixo X em ordem CRONOLÓGICA de verdade (Data_Real_Pure), não
                # ordem de texto -- "sorted()" na string "dd/mm" colocava 26/06 e 29/06 depois
                # de 22/07 (bug encontrado em 22/07/2026 ao implementar o sombreamento abaixo,
                # que depende da data real de cada categoria pra saber se é fim de semana).
                _datas_unicas = (
                    df_aderencia[["Data_Real_Pure", "x_date"]]
                    .drop_duplicates()
                    .sort_values("Data_Real_Pure")
                )
                # Sábado/Domingo em negrito/vermelho no rótulo do eixo X -- o markArea vertical
                # por categoria (tentativa anterior) não pintava a coluna de forma confiável no
                # ECharts, então a marcação de fim de semana passou a ser feita diretamente no
                # rótulo da data (pedido de 22/07/2026).
                categorias_x = [
                    {"value": _r["x_date"], "textStyle": {"color": "#DC2626", "fontWeight": "bold"}}
                    if _r["Data_Real_Pure"].weekday() >= 5  # 5=Sábado, 6=Domingo
                    else _r["x_date"]
                    for _, _r in _datas_unicas.iterrows()
                ]
                # Sombreamento horizontal do período noturno 00:00-06:00 (pedido de 22/07/2026).
                area_madrugada = [
                    {"yAxis": 0, "itemStyle": {"color": "#F59E0B", "opacity": 0.14}},
                    {"yAxis": 6}
                ]

                # Tooltip pre-formatado em Python, no campo "name" de cada ponto -- "{@[3]}"
                # (dimensao por indice) parou de ser interpretado pelo ECharts apos a nuvem
                # forcar upgrade do Streamlit (mesmo tipo de quebra que ja tinha acontecido
                # com JsCode antes). "{b}" (nome do dado) e um token basico e estavel do
                # formatter, entao usamos ele em vez de depender de sintaxe de dimensao.
                # Texto em linha unica, sem tags HTML (<b>/<br> vinham sendo exibidos como
                # texto literal em vez de renderizar -- feedback de 22/07/2026), e com a
                # localizacao (lat/lon) no lugar da data, que ja aparece no eixo X.
                def _local_legivel(valor):
                    texto = str(valor).strip()
                    if not texto or texto.lower() in ("nan", "none", "null"): return "Localização não registrada"
                    # geolocalizacao_baixa vem como "Endereço/Nome do Local (Lat: X, Lon: Y)" --
                    # extrai só o "Lat: X, Lon: Y", descartando o endereço (pedido de 22/07/2026).
                    m = re.search(r"Lat:\s*-?\d+\.?\d*,\s*Lon:\s*-?\d+\.?\d*", texto)
                    return m.group(0) if m else texto

                login_data = [
                    {
                        "value": [row["x_date"], round(row["y_login_frac"], 2)],
                        "name": f'{row["username"]} — Login: {row["dt_login_calc"].strftime("%H:%M")} — {_local_legivel(row.get("geolocalizacao_login"))}'
                    }
                    for _, row in df_aderencia.iterrows()
                ]
                baixa_data = [
                    {
                        "value": [row["x_date"], round(row["y_baixa_frac"], 2)],
                        "name": f'{row["username"]} — Primeira Baixa: {row["dt_baixa_1os"].strftime("%H:%M")} — {_local_legivel(row.get("geolocalizacao_baixa"))}'
                    }
                    for _, row in df_aderencia.iterrows()
                ]

                st_echarts(options={
                    "tooltip": {
                        "trigger": "item",
                        "formatter": "{b}"
                    },
                    "legend": {"data": ["Login", "Primeira Baixa"], "bottom": "0%"},
                    "dataZoom": [{"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}],
                    "grid": {"top": "10%", "bottom": "25%", "left": "6%", "right": "3%", "containLabel": True},
                    "xAxis": {"type": "category", "data": categorias_x},
                    "yAxis": { "type": "value", "name": "Horário", "min": 0, "max": 24, "interval": 1, "axisLabel": { "formatter": "{value}:00" } },
                    "series": [
                        {
                            "name": "Login", "type": "scatter", "data": login_data, "symbolSize": 10,
                            "itemStyle": {"color": "#3B82F6"},
                            "markArea": {"silent": True, "data": [area_madrugada]}
                        },
                        {"name": "Primeira Baixa", "type": "scatter", "data": baixa_data, "symbolSize": 10, "itemStyle": {"color": "#10B981"}}
                    ]
                }, height="480px", theme="streamlit", key="gov_scatter_aderencia")
            else:
                st.info("Dados de horário insuficientes para plotar o gráfico de aderência.")
        else:
            st.info("Dados insuficientes para cruzar login com apontamento.")
#endregion 11.5

#region 11.6: Top Técnicos e Variabilidade (2 colunas)
        st.markdown("<br>", unsafe_allow_html=True); st.markdown("---")
        col_l3_c1, col_l3_c2 = st.columns(2, gap="medium")

        with col_l3_c1:
            st.markdown("#### 🔝 Top Técnicos: OS por Pátio")
            # "Colaborador" (Nome (matrícula), com fallback pra matrícula crua) em vez de
            # "concluido_por" cru -- pedido de 22/07/2026 pra facilitar leitura do gráfico.
            df_freq = df_gov_f.groupby(["Colaborador", "Patio"]).size().reset_index(name="Qtd")
            patios_top = sorted(df_freq["Patio"].unique().tolist())
            # Ordena por volume total (desc) -- facilita achar quem mais concluiu de cara,
            # em vez da ordem crua de aparição no dataframe.
            tecnicos_top = (
                df_freq.groupby("Colaborador")["Qtd"].sum().sort_values(ascending=False).index.tolist()
            )
            series_top = [{"name": patio, "type": "bar", "stack": "total", "data": [int(df_freq[(df_freq["Colaborador"] == tec) & (df_freq["Patio"] == patio)]["Qtd"].iloc[0]) if not df_freq[(df_freq["Colaborador"] == tec) & (df_freq["Patio"] == patio)].empty else 0 for tec in tecnicos_top], "label": {"show": False}} for patio in patios_top]
            # Com muitos técnicos, o eixo X fica ilegível mesmo rotacionado -- dataZoom mostra
            # só os ~12 primeiros (já os de maior volume, por causa da ordenação acima) e
            # permite arrastar/rolar pra ver o resto, em vez de espremer tudo de uma vez.
            _qtd_tec = len(tecnicos_top)
            _end_zoom = round(min(100, (12 / _qtd_tec) * 100), 1) if _qtd_tec > 0 else 100
            st_echarts(options={
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "legend": {"bottom": "12%", "textStyle": {"fontSize": 10}},
                "grid": {"left": "5%", "right": "5%", "bottom": "28%", "top": "10%", "containLabel": True},
                "xAxis": {"type": "category", "data": tecnicos_top, "axisLabel": {"interval": 0, "rotate": 45, "fontSize": 10}},
                "yAxis": {"type": "value"},
                "dataZoom": [
                    {"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": _end_zoom, "bottom": "0%"},
                    {"type": "inside", "xAxisIndex": [0], "start": 0, "end": _end_zoom}
                ],
                "series": series_top
            }, height="480px", theme="streamlit", key="gov_top_tec")

        with col_l3_c2:
            st.markdown("#### 📊 Variabilidade de Execução")
            df_var = df_gov_f.groupby("Colaborador")["Tempo_Minutos"].mean().fillna(0).reset_index().sort_values("Tempo_Minutos", ascending=True)
            st_echarts(options={ "tooltip": {"trigger": "axis"}, "grid": {"left": "5%", "right": "8%", "bottom": "10%", "top": "10%", "containLabel": True}, "xAxis": {"type": "value", "name": "Minutos"}, "yAxis": {"type": "category", "data": df_var["Colaborador"].tolist(), "axisLabel": {"fontSize": 10}}, "series": [{"type": "bar", "data": df_var["Tempo_Minutos"].round(1).tolist(), "itemStyle": {"color": "#8B5CF6"}, "label": {"show": True, "position": "right", "formatter": "{c} min", "fontSize": 10}}] }, height="440px", theme="streamlit", key="gov_variab")
#endregion 11.6

#region 11.7: Tabela de Auditoria GPS
        st.markdown("---")
        st.markdown("#### 📍 Tabela de Auditoria de Apontamentos (GPS)")

        try:
            conn = get_connection()
            df_users_auditoria = pd.read_sql_query(
                "SELECT username, nome FROM usuarios",
                conn
            )
        finally:
            release_connection(conn)

        if not df_users_auditoria.empty:
            df_users_auditoria["username_key"] = (
                df_users_auditoria["username"]
                .astype(str)
                .str.strip()
            )

            df_users_auditoria["nome_clean"] = (
                df_users_auditoria["nome"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            mapa_nome_usuario_auditoria = dict(
                zip(
                    df_users_auditoria["username_key"],
                    df_users_auditoria["nome_clean"]
                )
            )
        else:
            mapa_nome_usuario_auditoria = {}

        def label_apontador_principal(valor):
            matricula = str(valor).strip()

            if not matricula or matricula.lower() in ("nan", "none", "null"):
                return "Não informado"

            nome = str(mapa_nome_usuario_auditoria.get(matricula, "")).strip()

            if nome:
                return f"{nome} ({matricula})"

            return matricula

        def label_equipe_coexecutantes(valor):
            texto = str(valor).strip()

            if not texto or texto.lower() in ("nan", "none", "null", "sozinho"):
                return "Sozinho"

            partes = [
                p.strip()
                for p in texto.split(",")
                if p.strip()
            ]

            nomes_formatados = []

            for item in partes:
                nome = str(mapa_nome_usuario_auditoria.get(item, "")).strip()

                if nome:
                    nomes_formatados.append(f"{nome} ({item})")
                else:
                    nomes_formatados.append(item)

            return ", ".join(nomes_formatados) if nomes_formatados else "Sozinho"

        df_auditoria_base = df_gov_f.copy()

        df_auditoria_base["Apontador Principal"] = (
            df_auditoria_base["concluido_por"]
            .apply(label_apontador_principal)
        )

        df_auditoria_base["Co-Executantes"] = (
            df_auditoria_base["equipe"]
            .apply(label_equipe_coexecutantes)
        )

        df_auditoria = (
            df_auditoria_base[
                [
                    "Ordem servico",
                    "Apontador Principal",
                    "data_fim",     # MUDANÇA: Usando Data do Fim de Execução (IW47)
                    "hora_fim",     # Hora Apontada (IW47)
                    "geolocalizacao_baixa",
                    "Co-Executantes",
                    "Tempo_Minutos"
                ]
            ]
            .copy()
        )

        # 1. Cria a coluna de ordenação cronológica com Pandas Nativo usando data_fim
        df_auditoria["Data_Sort"] = pd.to_datetime(df_auditoria["data_fim"], dayfirst=True, errors="coerce")
        
        # 2. Para exibição, garante o formato visual BR estrito (DD/MM/YYYY)
        df_auditoria["data_fim"] = df_auditoria["Data_Sort"].dt.strftime("%d/%m/%Y").fillna("N/D")

        df_auditoria = (
            df_auditoria.sort_values(
                by=["Data_Sort", "hora_fim"],
                ascending=[False, False]
            )
            .drop(columns=["Data_Sort"])
            .rename(columns={
                "Ordem servico": "OS",
                "data_fim": "Data",
                "hora_fim": "Hora Apontada",
                "geolocalizacao_baixa": "Localização do Celular",
                "Tempo_Minutos": "Tempo Gasto (min)"
            })
        )

        df_auditoria["Tempo Gasto (min)"] = (
            df_auditoria["Tempo Gasto (min)"]
            .fillna(0)
            .round(0)
            .astype(int)
        )

        def estilo_gps(v):
            if pd.notna(v) and ("Base" in str(v) or "Sede" in str(v)):
                return (
                    "background-color: #FEE2E2; "
                    "color: #991B1B; "
                    "font-weight: bold;"
                )

            return "color: #065F46;"

        # Exportação em ";" (não ","): "Localização do Celular" traz "Lat: X, Lon: Y" com
        # vírgula dentro do próprio texto -- CSV separado por vírgula quebra a organização
        # das colunas ao abrir/ordenar no Excel. O botão nativo de download do st.dataframe
        # (ícone no canto da tabela) continua exportando em "," -- usar este botão abaixo.
        csv_auditoria = df_auditoria.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "⬇️ Baixar CSV (separado por ;)",
            data=csv_auditoria,
            file_name="auditoria_apontamentos_gps.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.dataframe(
            df_auditoria
            .style
            .map(estilo_gps, subset=["Localização do Celular"]),
            use_container_width=True,
            height=400,
            hide_index=True
        )
#endregion 11.7
    fragmento_governanca()
    st.stop()
#endregion
#endregion
