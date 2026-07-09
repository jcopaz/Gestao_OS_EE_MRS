#region SESSÃO 1: Imports, Configurações e Funções de Base
import io
import time
import math
import re
import os
import shutil
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from streamlit_js_eval import get_geolocation

import plotly.express as px
import plotly.graph_objects as go
from streamlit_echarts import st_echarts, JsCode

# --- CONFIGURAÇÕES GLOBAIS ---
st.set_page_config(page_title="Painel de OS Eletroeletrônica", layout="wide")

# SÓ MOSTRA O TÍTULO SE NÃO ESTIVER LOGADO
if not st.session_state.get("logged_in", False):
    # Criamos três colunas: as laterais vazias centralizam a do meio
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 6, 1])
    with col_centro:
        st.markdown("<h1 style='text-align: center;'>⚡ Sistema de Gestão de Ordens de Serviço</h1>", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO E PERSISTÊNCIA (Definidas ANTES de serem usadas) ---
def db_path():
    return "baixas_os.db"

def db_users_path():
    return "usuarios.db"

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# Variáveis de status globais
_status_prazo  = {"REALIZADO"}
_status_atraso = {"REALIZADO FORA DA DATA DE PROGRAMAÇÃO", "REALIZADO FORA DO PRAZO"}
_status_aberto = {"NÃO REALIZADO", "NAO REALIZADO", "PENDENTE", "ATRASADO", ""}

def init_db():
    # 1. Banco de Operação (Baixas)
    conn_b = sqlite3.connect(db_path())
    cur_b = conn_b.cursor()
    cur_b.execute("CREATE TABLE IF NOT EXISTS baixas (os TEXT PRIMARY KEY, status TEXT NOT NULL, realizado_em TEXT NOT NULL, coordenacao TEXT NOT NULL, concluido_por TEXT)")
    conn_b.commit(); conn_b.close()
    
    # 2. Banco de Segurança (Usuários)
    conn_u = sqlite3.connect(db_users_path())
    cur_u = conn_u.cursor()
    cur_u.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha_hash TEXT NOT NULL, perfil TEXT NOT NULL, escopo TEXT NOT NULL)")
    conn_u.commit(); conn_u.close()

def atualizar_banco_usuarios():
    # Agora aponta para o banco isolado de usuários
    conn = sqlite3.connect(db_users_path())
    cur = conn.cursor()
    # Adicionamos as colunas extras de segurança
    cols = {
        "palavra_recuperacao": "TEXT", 
        "dica_recuperacao": "TEXT", 
        "reset_obrigatorio": "INTEGER DEFAULT 1", 
        "coordenacao_padrao": "TEXT DEFAULT 'ICG'"
    }
    for col, tipo in cols.items():
        try: cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError: pass
    conn.commit(); conn.close()

# AGORA, como as funções já existem, podemos chamá-las com segurança:
init_db()
atualizar_banco_usuarios()
#endregion

#region SESSÃO 1.5: Barreira de Login Corrigida
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": "", "perfil": "", "escopo": "", "needs_reset": False, "recuperando": False, "trocar_senha": False})

if not st.session_state["logged_in"]:
    st.markdown("<h3 style='text-align: center; color: #475569;'>Acesso Restrito</h3>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    
    with col_l2:
        # 1. FLUXO DE RESET OBRIGATÓRIO (Troca de senha + Definição de Palavra-Chave)
        if st.session_state.get("needs_reset"):
            st.warning("⚠️ Bem-vindo! Configure sua senha e sua palavra de recuperação.")
            with st.form("form_reset"):
                nova_senha = st.text_input("Nova Senha", type="password")
                conf_senha = st.text_input("Confirmar Nova Senha", type="password")
                palavra_nova = st.text_input("Definir sua Palavra-Chave de Recuperação")
                
                if st.form_submit_button("Finalizar Cadastro"):
                    if nova_senha != conf_senha:
                        st.error("As senhas não conferem.")
                    elif not palavra_nova:
                        st.error("Você precisa definir uma palavra-chave!")
                    else:
                        conn = sqlite3.connect(db_users_path())
                        # Agora atualizamos a senha, a palavra-chave e tiramos a obrigatoriedade
                        conn.cursor().execute("""
                            UPDATE usuarios 
                            SET senha_hash = ?, palavra_recuperacao = ?, reset_obrigatorio = 0 
                            WHERE username = ?
                        """, (hash_senha(nova_senha), palavra_nova.strip(), st.session_state["reset_user"]))
                        conn.commit(); conn.close()
                        st.success("Configuração concluída! Entre com sua nova senha."); st.session_state["needs_reset"] = False; st.rerun()
            if st.button("⬅️ Voltar"):
                st.session_state["needs_reset"] = False; st.rerun()

        # 2. FLUXO DE RECUPERAÇÃO (Esqueci a senha)
        elif st.session_state.get("recuperando"):
            st.info("Digite seu login e a palavra-chave.")
            with st.form("form_recuperar"):
                user_rec = st.text_input("Login")
                palavra_rec = st.text_input("Palavra-Chave")
                submit_rec = st.form_submit_button("Validar")
            
            # O botão de voltar deve ficar FORA do form
            if submit_rec:
                conn = sqlite3.connect(db_users_path())
                cur = conn.cursor()
                cur.execute("SELECT palavra_recuperacao FROM usuarios WHERE username = ?", (user_rec.strip(),))
                row = cur.fetchone(); conn.close()
                if row and row[0] == palavra_rec.strip():
                    st.session_state["needs_reset"] = True
                    st.session_state["reset_user"] = user_rec.strip()
                    st.session_state["recuperando"] = False
                    st.rerun()
                else: st.error("Dados incorretos.")
                
            if st.button("⬅️ Voltar ao Login"): 
                st.session_state["recuperando"] = False; st.rerun()

        # 3. FLUXO DE LOGIN PADRÃO
        else:
            with st.form("form_login"):
                user_input = st.text_input("Usuário")
                pass_input = st.text_input("Senha", type="password")
                submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                # AQUI ESTAVA O ERRO! CORRIGIDO PARA db_users_path()
                conn = sqlite3.connect(db_users_path())
                cur = conn.cursor()
                cur.execute("SELECT senha_hash, perfil, escopo, reset_obrigatorio FROM usuarios WHERE username = ?", (user_input.strip(),))
                row = cur.fetchone(); conn.close()
                if row and row[0] == hash_senha(pass_input):
                    if row[3] == 1:
                        st.session_state["needs_reset"] = True
                        st.session_state["reset_user"] = user_input.strip()
                        st.rerun()
                    else:
                        st.session_state.update({"logged_in": True, "username": user_input.strip(), "perfil": row[1], "escopo": row[2]})
                        st.rerun()
                else: st.error("❌ Usuário ou senha incorretos.")
            
            if st.button("Esqueci minha senha"): st.session_state["recuperando"] = True; st.rerun()
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
    return datetime.now()

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

def upsert_baixa(os_id: str, status: str, realizado_em_str: str, coordenacao: str, concluido_por: str):
    conn = sqlite3.connect(db_path())
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO baixas (os, status, realizado_em, coordenacao, concluido_por)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(os) DO UPDATE SET
            status=excluded.status,
            realizado_em=excluded.realizado_em,
            concluido_por=excluded.concluido_por
    """, (str(os_id), str(status), str(realizado_em_str), str(coordenacao), str(concluido_por)))
    conn.commit()
    conn.close()

def carregar_baixas_df() -> pd.DataFrame:
    # A inicialização do banco (init_db) já ocorreu globalmente na Sessão 1
    conn = sqlite3.connect(db_path())
    df = pd.read_sql_query("SELECT os, status, realizado_em, coordenacao, concluido_por FROM baixas", conn)
    conn.close()
    if df.empty:
        return df
    df["os"] = df["os"].astype(str)
    return df

#endregion

#region SESSÃO 2.3 ===== Export/Salvar Excel (MASTER) =====
def gerar_excel_bytes(df_export: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    df_to_save = df_export.copy()

    # Data programada como dd/mm/aaaa
    if "Data inicial programada" in df_to_save.columns:
        df_to_save["Data inicial programada"] = pd.to_datetime(
            df_to_save["Data inicial programada"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

    # Data/Hora Realizado já é texto dd/mm/aaaa hh:mm
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_to_save.to_excel(writer, index=False, sheet_name="OS")

    output.seek(0)
    return output.read()

def _acquire_lock(lock_path: str, timeout_sec: int = 15):
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - start > timeout_sec:
                return False
            time.sleep(0.5)

def _release_lock(lock_path: str):
    try:
        os.remove(lock_path)
    except Exception:
        pass

def salvar_excel_com_backup_bytes(excel_bytes: bytes, destino: Path, max_tentativas: int = 5):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    lock_path = str(destino) + ".lock"
    if not _acquire_lock(lock_path, timeout_sec=20):
        raise RuntimeError("Não foi possível obter lock do arquivo. Talvez outro usuário esteja salvando agora.")

    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = destino.with_name(f"{destino.stem}_backup_{ts}{destino.suffix}")
        tmp_path = destino.with_suffix(destino.suffix + f".tmp_{ts}")

        # Backup do arquivo atual (se existir)
        if destino.exists():
            shutil.copy2(destino, backup_path)

        # Escrita segura em arquivo temporário + replace atômico
        tentativa = 0
        while True:
            try:
                with open(tmp_path, "wb") as f:
                    f.write(excel_bytes)
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(tmp_path, destino)  # substitui de forma atômica
                return str(backup_path)
            except PermissionError:
                tentativa += 1
                if tentativa >= max_tentativas:
                    raise
                time.sleep(1.0)
            finally:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
    finally:
        _release_lock(lock_path)
#endregion

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
#endregion

#region SESSÃO 3: Banco de Coordenadas Fixo

#region SESSÃO 3.1 Coordenadas Fixas
COORDENADAS_FIXAS = {
    "IAA":[-23.862936, -46.398189],
    "IEF":[-23.478373, -46.361580],
    "OLU":[-23.533829, -46.638487],
    "IPA":[-23.777009, -46.302837],
    "IRS":[-23.829653, -46.363524],
    "IPG":[-23.848363, -46.371212],
    "ICG":[-23.767355, -46.344117],
    "IRG":[-23.743597, -46.391209],
    "IOF":[-23.681450, -46.360191],
    "ISU":[-23.550703, -46.288168],
    "ILA":[-23.515341, -46.708494],
    "IJN":[-23.195297, -46.870829],
    "ZPD":[-22.363436, -48.711002],
    "IIP":[-23.578880, -46.597936],
    "Sede IPA":[-23.767355, -46.344117],
    "Sede IPG":[-23.850772,-46.37176]
}
#endregion

#region SESSÃO 3.2 Continuação do código da função de obtenção da base padrão do usuário (com normalização de nomes e fallback)
def obter_base_padrao_usuario():
    username = str(st.session_state.get("username", "")).strip()
    escopo = str(st.session_state.get("escopo", "")).strip()

    # Mapeia valores possíveis (antigos e novos) para a chave real do dicionário
    mapa_normalizacao = {
        "Paranapiacaba": ("Sede IPA", "Sede IPA"),
        "Piaçaguera": ("Sede IPG", "Sede IPG"),
        "Todas": ("Sede IPA", "Sede IPA"),
        "ICG": ("ICG", "Campo Grande (ICG)"),
        "Sede IPA": ("Sede IPA", "Sede IPA"),
        "Sede IPG": ("Sede IPG", "Sede IPG")
    }

    valor_base = None

    # 1) Tenta buscar primeiro a coordenacao_padrao do usuário logado no banco
    if username:
        try:
            conn = sqlite3.connect(db_users_path())
            cur = conn.cursor()
            cur.execute(
                "SELECT coordenacao_padrao FROM usuarios WHERE username = ?",
                (username,)
            )
            row = cur.fetchone()
            conn.close()

            if row and row[0]:
                valor_base = str(row[0]).strip()
        except Exception:
            valor_base = None

    # 2) Se não vier nada do banco, cai para o escopo do usuário
    if not valor_base:
        valor_base = escopo

    # 3) Resolve a chave final da base
    chave_coord, nome_exibicao = mapa_normalizacao.get(
        valor_base,
        ("Sede IPA", "Sede IPA")
    )

    lat, lon = COORDENADAS_FIXAS.get(chave_coord, COORDENADAS_FIXAS["Sede IPA"])
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
    
    # Extração do Pátio (3 primeiras letras do Ativo)
    df["PATIO_CAN"] = df["ATIVO_CAN"].str[:3].str.upper()

    df["DATA_PROG_CAN"] = df[col_data_prog].apply(parse_data_programada)
    df["DESC_LONGA_CAN"] = df[col_desc].astype(str).str.strip() if col_desc else ""

    # Classificação + Criticidade
    df["Classificacao"] = df["ATIVIDADE_CAN"].apply(classificar_atividade)
    crit = df["PRIORIDADE_CAN"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]
    df["Nivel_Prioridade"] = df.apply(lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]), axis=1)

    # Nova lógica inteligente de Status
    hoje_data = datetime.now().date()
    def definir_status_cru(row):
        st_atual = str(row[col_status]).strip().upper() if pd.notna(row[col_status]) and col_status else ""
        
        # Se já estiver realizado na base
        if "REALIZADO" in st_atual:
            if "FORA" in st_atual or "ATRASO" in st_atual:
                return "Realizado Fora da Data de Programação"
            return "Realizado"
        
        # Se estiver em branco/pendente, cruza com a data
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
        "Criticidade": df["Criticidade"],
        "Classificacao": df["Classificacao"],
        "Descrição Longa": df["DESC_LONGA_CAN"],
        "Data inicial programada": df["DATA_PROG_CAN"],
        "Status da Operação": df["STATUS_CAN"],
        "Data/Hora Realizado": "",
        "Concluído por": "",  # Nova coluna exigida
        "Hxh Plano": df["HXH_CAN"],
        "Criticidade_rank": df["Criticidade_rank"],
        "Nivel_Prioridade": df["Nivel_Prioridade"],
    })

    return df_out

@st.cache_data
def auto_detect_and_treat(path_ou_bytes):
    # Lê o Excel ignorando completamente os cabeçalhos originais
    if isinstance(path_ou_bytes, bytes):
        df_raw = pd.read_excel(io.BytesIO(path_ou_bytes), engine="openpyxl", header=None)
    else:
        df_raw = pd.read_excel(path_ou_bytes, engine="openpyxl", header=None)
        
    # 1. Joga fora as linhas que estiverem 100% vazias (ex: a Linha 1 inteira em branco)
    df_raw = df_raw.dropna(how='all')
    
    # 2. Joga fora as colunas que estiverem 100% vazias (ex: a Coluna A inteira em branco)
    df_raw = df_raw.dropna(axis=1, how='all')
    
    if df_raw.empty:
        raise ValueError("O arquivo Excel está completamente sem dados.")
        
    # 3. Como limpamos o lixo, a PRIMEIRA linha que sobreviveu é obrigatoriamente o cabeçalho real
    df_raw.columns = df_raw.iloc[0]
    
    # 4. Remove a linha que virou cabeçalho do meio dos dados e reseta a tabela
    df_tratado = df_raw[1:].reset_index(drop=True)
    
    # 5. Envia para a nossa função de tratamento
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
        return gerar_base_simulada(qtd=qtd_sim, seed=seed_sim)

    pasta_bases = Path("bases_os")
    pasta_bases.mkdir(exist_ok=True)

    arquivos = [f for f in pasta_bases.glob("*.xlsx") if not f.name.startswith("~$")]
    if not arquivos:
        return pd.DataFrame()

    dfs = []
    for arq in arquivos:
        df_temp = carregar_excel_por_path(str(arq), etl_version)
        nome_coord = arq.stem.replace("OS_", "").replace("_", " ").strip()
        df_temp["Coordenacao"] = nome_coord
        dfs.append(df_temp)

    df_base_bruto = pd.concat(dfs, ignore_index=True)

    if escopo_usuario != "Todas":
        df_base_bruto = df_base_bruto[
            df_base_bruto["Coordenacao"].str.contains(escopo_usuario, case=False, na=False)
        ]

    return df_base_bruto


@st.cache_data(show_spinner=False)
def aplicar_overlay_baixas(
    df_base_bruto: pd.DataFrame,
    escopo_usuario: str,
    baixas_mtime: float
) -> pd.DataFrame:
    df_base = df_base_bruto.copy()

    if df_base.empty:
        return df_base

    init_db()
    df_baixas = carregar_baixas_df()

    if df_baixas.empty:
        return df_base

    df_base["Ordem servico"] = df_base["Ordem servico"].astype(str)

    if escopo_usuario != "Todas":
        df_baixas = df_baixas[
            df_baixas["coordenacao"].str.contains(escopo_usuario, case=False, na=False)
        ]

    df_baixas = df_baixas.rename(columns={
        "os": "Ordem servico",
        "status": "Status da Operação",
        "realizado_em": "Data/Hora Realizado",
        "concluido_por": "Concluído por"
    })

    df_base = df_base.merge(
        df_baixas[["Ordem servico", "Status da Operação", "Data/Hora Realizado", "Concluído por"]],
        on="Ordem servico",
        how="left",
        suffixes=("", "_baixado")
    )

    df_base["Status da Operação"] = np.where(
        df_base["Status da Operação_baixado"].notna(),
        df_base["Status da Operação_baixado"],
        df_base["Status da Operação"]
    )

    df_base["Data/Hora Realizado"] = np.where(
        df_base["Data/Hora Realizado_baixado"].notna(),
        df_base["Data/Hora Realizado_baixado"],
        df_base["Data/Hora Realizado"]
    )

    df_base["Concluído por"] = np.where(
        df_base["Concluído por_baixado"].notna(),
        df_base["Concluído por_baixado"],
        df_base["Concluído por"]
    )

    df_base.drop(
        columns=["Status da Operação_baixado", "Data/Hora Realizado_baixado", "Concluído por_baixado"],
        inplace=True
    )

    return df_base
#endregion

#region SESSÃO EXTRA: Simulação de dados (APENAS TESTE - remover depois)
# ==========================================
# SESSÃO EXTRA: Simulação de dados (APENAS TESTE - remover depois)
# ==========================================

#region SESSÃO EXTRA: Gerador de base simulada (para testar KPIs e gráficos)
def gerar_base_simulada(qtd: int = 800, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    patios = [
        "IAA", "IEF", "OLU", "IPA", "IRS", "IPG", "ICG",
        "IRG", "IOF", "ISU", "ILA", "IJN", "ZPD", "IIP"
]

    prioridades = ["1-Muito Alta", "2-Alta", "3-Média", "4-Baixa"]
    prob_prio = [0.18, 0.32, 0.30, 0.20]

    atividades = [
        "EE_INS_SEG_C_I_MAQ CHAVE MOLA_1800",
        "EE_MAN_CONF_C_I_CANALETA SUBESTACAO_0720",
        "EE_INS_CONF_S_I_BATERIAS_0360"
    ]
    prob_ativ = [0.35, 0.30, 0.35]

    status_list = ["Não Realizado", "Realizado", "Realizado Fora da Data de Programação"]
    prob_status = [0.45, 0.40, 0.15]

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
        "Coordenacao": rng.choice(["Paranapiacaba", "Piaçaguera"], size=qtd) # ✅ CORREÇÃO: Coluna adicionada
    })

    # Classificação / Criticidade / Nível (mesma lógica do app)
    df["Classificacao"] = df["Atividade ativo"].apply(classificar_atividade)

    crit = df["Prioridade"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]

    df["Nivel_Prioridade"] = df.apply(
        lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]),
        axis=1
    )
    df["Desc_Prioridade"] = df["Classificacao"] + " | " + df["Criticidade"]

    # Status e Data/Hora Realizado simulados
    df["Status da Operação"] = rng.choice(status_list, size=qtd, p=prob_status)
    df["Data/Hora Realizado"] = ""

    # Preenche Data/Hora Realizado para os realizados
    for i in range(qtd):
        stt = df.at[i, "Status da Operação"]
        if stt == "Não Realizado":
            continue

        prog = pd.to_datetime(df.at[i, "Data inicial programada"])
        turno = rng.choice(["00h-07h", "07h-16h", "16h-00h"], p=[0.15, 0.60, 0.25])

        if turno == "00h-07h":
            hh = int(rng.integers(0, 7))
        elif turno == "07h-16h":
            hh = int(rng.integers(7, 16))
        else:
            hh = int(rng.integers(16, 24))
        mm = int(rng.integers(0, 60))

        if stt == "Realizado":
            delta = int(rng.integers(0, 4))  # até 3 dias antes
            real_date = (prog - pd.Timedelta(days=delta)).to_pydatetime()
        else:
            delta = int(rng.integers(1, 11))  # 1 a 10 dias depois
            real_date = (prog + pd.Timedelta(days=delta)).to_pydatetime()

        real_dt = real_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
        df.at[i, "Data/Hora Realizado"] = formatar_dt_br(real_dt)

    return df
#endregion

#region SESSÃO EXTRA: Controle na Sidebar (retorna DF simulado quando ativado)
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
    /* Fundo da Barra Lateral */
    [data-testid="stSidebar"] {
        background-color: #1A202C !important; 
    }
    
    /* Textos da Sidebar em branco/cinza claro */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] h4, [data-testid="stSidebar"] h5, [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] small, [data-testid="stSidebar"] caption {
        color: #F1F5F9 !important;
    }

    /* Esconde a bolinha padrão do radio button */
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    
    /* NAVEGAÇÃO: Estilo dos botões */
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 10px 16px !important;
        background-color: transparent !important;
        border-radius: 8px !important;
        margin-bottom: 6px !important;
        transition: all 0.2s ease-in-out !important;
        cursor: pointer !important;
        color: #CBD5E1 !important;
    }
    
    /* NAVEGAÇÃO: Hover (ao passar o mouse) */
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #FFFFFF !important;
    }
    
    /* NAVEGAÇÃO: Item Selecionado (Fundo sombreado vermelho coral) */
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background-color: rgba(255, 75, 75, 0.2) !important; 
        border-left: 4px solid #FF4B4B !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
        font-weight: bold !important;
        color: #FFFFFF !important;
    }
    
    /* FILTROS: Títulos Maiores e em Negrito */
    [data-testid="stSidebar"] .stSelectbox label p, 
    [data-testid="stSidebar"] .stMultiSelect label p,
    [data-testid="stSidebar"] .stDateInput label p {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
        margin-bottom: 4px;
    }

    /* FILTROS: Cor das tags selecionadas (Vermelho/Coral) */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #FF4B4B !important;
        color: white !important;
        border-radius: 6px !important;
    }
    
    /* GERAL SIDEBAR: Fundo escuro das caixas de seleção (Date, Multi, Select, Input) */
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
    
    /* EXPANDERS NA SIDEBAR: Fundo Vermelho e Letras Brancas/Negrito no Título */
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
    
    /* BOTÕES NA SIDEBAR */
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
    
    /* Ajuste de tamanho dos KPIs principais */
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
    }
    
    /* ABAS (TABS): Fundo vermelho com opacidade na aba selecionada */
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

# 5.1.3 Navegação e definição do escopo visual
st.sidebar.markdown("### 🧭 Navegação")
if st.session_state["perfil"] == "Gerência":
    visao_selecionada = st.sidebar.radio("Selecione a Visão:", ["Gerência", "Paranapiacaba", "Piaçaguera"], label_visibility="collapsed")
    filtro_visao = "Todas" if visao_selecionada == "Gerência" else visao_selecionada
else:
    filtro_visao = st.session_state["escopo"]
    st.sidebar.info(f"Visão Restrita: {filtro_visao}")

st.sidebar.markdown("---")
#endregion

#region SESSÃO 5.2: Carregamento da base operacional
# 5.2.1 Parâmetros de carga / simulação
usar_sim = st.session_state.get("chk_sim", False)
qtd_sim = st.session_state.get("qtd_sim", 1200)
seed_sim = st.session_state.get("seed_sim", 42)

# 5.2.2 Assinatura de atualização do overlay
baixas_mtime = os.path.getmtime(db_path()) if os.path.exists(db_path()) else 0.0

# 5.2.3 Carga da base sem overlay
df_base_bruto = carregar_base_sem_overlay(
    usar_sim=usar_sim,
    qtd_sim=int(qtd_sim),
    seed_sim=int(seed_sim),
    escopo_usuario=st.session_state["escopo"],
    etl_version=ETL_VERSION
)

if df_base_bruto.empty and not usar_sim:
    pasta_bases = Path("bases_os")
    st.error(f"Nenhuma planilha encontrada na pasta '{pasta_bases.absolute()}'.")
    st.stop()

# 5.2.4 Overlay das baixas
df_base = aplicar_overlay_baixas(
    df_base_bruto=df_base_bruto,
    escopo_usuario=st.session_state["escopo"],
    baixas_mtime=baixas_mtime
)

# 5.2.5 Persistência e preparação da visão
st.session_state["df_os"] = df_base
df_visao = preparar_df_visao(df_base, filtro_visao)
#endregion

#region SESSÃO 5.3: Filtros da sidebar
# 5.3.1 Título da área de filtros
st.sidebar.markdown("### 📊 Filtros")

# 5.3.2 Filtro de período de programação
valid_dates = df_visao["dt_prog_filtro"].dropna()

if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()
else:
    min_date = datetime.now().date() - pd.Timedelta(days=30)
    max_date = datetime.now().date()

data_selecionada = st.sidebar.date_input(
    "Período de Programação",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
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

# 5.3.3 Filtro de pátio
lista_patios = sorted(df_visao["Patio"].dropna().astype(str).unique().tolist())
patios_selecionados = st.sidebar.multiselect("Pátio", lista_patios, default=lista_patios)

# 5.3.4 Filtro de classificação
classif_selecionadas = st.sidebar.multiselect(
    "Classificação",
    ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"],
    default=["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
)

# 5.3.5 Filtro de turno
lista_turnos = ["00h-07h", "07h-16h", "16h-00h", "Pendente (Sem Turno)"]
turnos_selecionados = st.sidebar.multiselect("Turno", lista_turnos, default=lista_turnos)

# 5.3.6 Filtro de status
status_sel = st.sidebar.selectbox(
    "Status da OS",
    ["Todos", "Todas Concluídas", "Concluídas no Prazo", "Concluídas com Atraso", "Pendentes"]
)

# 5.3.7 Aplicação final dos filtros
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

#region SESSÃO 6: Sistema, dados e gestão de usuários
st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Sistema, Dados e Gestão", expanded=False):


#region SESSÃO 6.1: Sistema e dados
# 6.1.1 Controle de simulação
    st.checkbox("🧪 Usar dados simulados (teste rápido)", key="chk_sim")

    if st.session_state.get("chk_sim"):
        st.slider(
            "Volume de OS simuladas",
            min_value=100,
            max_value=4000,
            value=1200,
            step=100,
            key="qtd_sim"
        )
        st.number_input(
            "Seed (repete mesmos dados)",
            value=42,
            key="seed_sim"
        )
    else:
    # 6.1.2 Recarregamento manual do ETL
        if st.button("🔄 Recarregar dados (ETL)", use_container_width=True, key="btn_recarregar_etl"):
            st.cache_data.clear()
            st.rerun()
#endregion

#region SESSÃO 6.2: Gestão de usuários
    if st.session_state["perfil"] == "Gerência":
        st.markdown(
            "<div style='background-color: #FF4B4B; color: #FFFFFF; font-weight: bold; text-align: center; padding: 8px; border-radius: 6px; margin-top: 15px; margin-bottom: 10px; font-size: 16px;'>"
            "Gestão de Usuários"
            "</div>",
            unsafe_allow_html=True
        )

        def sedes_por_escopo(escopo: str):
            escopo = str(escopo).strip()
            if escopo == "Paranapiacaba":
                return ["Sede IPA"]
            elif escopo == "Piaçaguera":
                return ["Sede IPG"]
            elif escopo == "Todas":
                return ["Sede IPA", "Sede IPG"]
            return ["Sede IPA"]

        # 6.2.1 Cadastro de novo usuário
        with st.form("form_novo_user", clear_on_submit=True):
            n_user = st.text_input("Login (Nova conta)", key="novo_user_login")
            n_perf = st.selectbox(
                "Perfil",
                ["Técnico", "Coordenador", "Gerência"],
                key="novo_user_perfil"
            )
            n_esco = st.selectbox(
                "Escopo",
                ["Paranapiacaba", "Piaçaguera", "Todas"],
                key="novo_user_escopo"
            )

            sedes_validas = sedes_por_escopo(n_esco)

            sede_default = {
                "Paranapiacaba": "Sede IPA",
                "Piaçaguera": "Sede IPG",
                "Todas": "Sede IPA"
            }.get(n_esco, "Sede IPA")

            idx_sede_default = (
                sedes_validas.index(sede_default)
                if sede_default in sedes_validas else 0
            )

            n_sede = st.selectbox(
                "Sede",
                sedes_validas,
                index=idx_sede_default,
                key="novo_user_sede",
                format_func=lambda x: x.replace("Sede ", "")
            )

            st.caption("A senha inicial padrão será definida automaticamente como **mrs123**.")

            if st.form_submit_button("Salvar Novo Usuário"):
                if n_user:
                    conn = sqlite3.connect(db_users_path())
                    try:
                        conn.cursor().execute(
                            """
                            INSERT INTO usuarios
                            (username, senha_hash, perfil, escopo, palavra_recuperacao, dica_recuperacao, coordenacao_padrao, reset_obrigatorio)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                n_user.strip(),
                                hash_senha("mrs123"),
                                n_perf,
                                n_esco,
                                "PENDENTE",
                                "PENDENTE",
                                n_sede,
                                1
                            )
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Usuário {n_user} criado com a senha 'mrs123'!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        conn.close()
                        st.error("Erro: Este usuário já existe.")
                else:
                    st.warning("Preencha o login do usuário.")

        # 6.2.2 Seleção de usuário existente
        st.markdown("<br><b style='color: #F8FAFC;'>👥 Gerenciar Usuários</b>", unsafe_allow_html=True)

        conn = sqlite3.connect(db_users_path())
        df_usuarios = pd.read_sql_query(
            "SELECT username, perfil, escopo, coordenacao_padrao FROM usuarios",
            conn
        )
        conn.close()

        lista_users = df_usuarios["username"].tolist()

        usr_sel = st.selectbox(
            "Selecione um usuário para gerenciar:",
            [""] + lista_users,
            key="gerenciar_usuario_select"
        )

        if usr_sel != "":
            dados_usr = df_usuarios[df_usuarios["username"] == usr_sel].iloc[0]

            st.caption(
                f"**Perfil Atual:** {dados_usr['perfil']} | "
                f"**Visão:** {dados_usr['escopo']} | "
                f"**Sede Atual:** {str(dados_usr['coordenacao_padrao']).replace('Sede ', '')}"
            )

            acao = st.radio(
                "Escolha a ação:",
                ["✏️ Editar Acesso", "🔑 Resetar Senha", "🗑️ Excluir"],
                horizontal=True,
                key=f"acao_usuario_{usr_sel}"
            )

            # 6.2.3 Edição de acesso
            if acao == "✏️ Editar Acesso":
                with st.form(f"form_edit_{usr_sel}"):
                    perfis_validos = ["Técnico", "Coordenador", "Gerência"]
                    escopos_validos = ["Paranapiacaba", "Piaçaguera", "Todas"]

                    idx_perf = (
                        perfis_validos.index(dados_usr["perfil"])
                        if dados_usr["perfil"] in perfis_validos else 0
                    )
                    idx_esco = (
                        escopos_validos.index(dados_usr["escopo"])
                        if dados_usr["escopo"] in escopos_validos else 0
                    )

                    n_perf_edit = st.selectbox(
                        "Novo Perfil",
                        perfis_validos,
                        index=idx_perf,
                        key=f"edit_perf_{usr_sel}"
                    )

                    n_esco_edit = st.selectbox(
                        "Nova Visão",
                        escopos_validos,
                        index=idx_esco,
                        key=f"edit_escopo_{usr_sel}"
                    )

                    sedes_validas_edit = sedes_por_escopo(n_esco_edit)

                    sede_atual = (
                        str(dados_usr["coordenacao_padrao"]).strip()
                        if pd.notna(dados_usr["coordenacao_padrao"])
                        else "Sede IPA"
                    )

                    idx_sede = (
                        sedes_validas_edit.index(sede_atual)
                        if sede_atual in sedes_validas_edit else 0
                    )

                    n_sede_edit = st.selectbox(
                        "Sede",
                        sedes_validas_edit,
                        index=idx_sede,
                        key=f"edit_sede_{usr_sel}",
                        format_func=lambda x: x.replace("Sede ", "")
                    )

                    if st.form_submit_button("Salvar Alterações"):
                        conn = sqlite3.connect(db_users_path())
                        conn.cursor().execute(
                            """
                            UPDATE usuarios
                            SET perfil = ?, escopo = ?, coordenacao_padrao = ?
                            WHERE username = ?
                            """,
                            (n_perf_edit, n_esco_edit, n_sede_edit, usr_sel)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Permissões de {usr_sel} atualizadas!")
                        st.rerun()

            # 6.2.4 Reset de senha
            elif acao == "🔑 Resetar Senha":
                st.warning("A senha voltará para 'mrs123' e o usuário será forçado a criar uma nova.")
                if st.button("Confirmar Reset", key=f"btn_reset_{usr_sel}"):
                    conn = sqlite3.connect(db_users_path())
                    senha_provisoria_hash = hash_senha("mrs123")
                    conn.cursor().execute(
                        "UPDATE usuarios SET senha_hash = ?, reset_obrigatorio = 1 WHERE username = ?",
                        (senha_provisoria_hash, usr_sel)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Senha de {usr_sel} resetada com sucesso!")
                    st.rerun()

            # 6.2.5 Exclusão de usuário
            elif acao == "🗑️ Excluir":
                if usr_sel == st.session_state["username"]:
                    st.error("Você não pode excluir a si mesmo para evitar bloqueio do sistema.")
                else:
                    st.warning("O acesso será removido. O histórico de OS continuará intacto.")
                    if st.button("Confirmar Exclusão", key=f"btn_del_{usr_sel}", type="primary"):
                        conn = sqlite3.connect(db_users_path())
                        conn.cursor().execute(
                            "DELETE FROM usuarios WHERE username = ?",
                            (usr_sel,)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Usuário {usr_sel} excluído permanentemente.")
                        st.rerun()
#endregion
#endregion

#region SESSÃO 7: DASHBOARD HEADER E KPI METRICS
# ==========================================

# --- CABEÇALHO INTEGRADO ---
# Usamos [9, 1] - O título ocupa quase tudo, e os botões ficam em uma coluna fina à direita
col_titulo, col_acoes = st.columns([9, 1])

with col_titulo:
    st.title("⚡ Sistema de Gestão de Ordens de Serviço")
    st.markdown(f"<h5 style='color: #475569; margin-top: -10px;'>Olá, <b>{st.session_state.get('username', 'Usuário')}</b> 👋</h5>", unsafe_allow_html=True)

with col_acoes:
    # Ajuste fino para descer um pouco os botões e alinhar com o título
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    
    # Empilhados um embaixo do outro
    if st.button("🔑 Trocar", use_container_width=True):
        usr_atual = st.session_state["username"]
        conn = sqlite3.connect(db_users_path())
        conn.cursor().execute("UPDATE usuarios SET reset_obrigatorio = 1 WHERE username = ?", (usr_atual,))
        conn.commit(); conn.close()
        
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

# --- TRAVA DE SEGURANÇA (Evita erros se a base estiver vazia) ---
if 'df_filtrado' not in locals() or df_filtrado.empty:
    df_filtrado = pd.DataFrame(columns=["Status_norm", "Data inicial programada"])
if "Status_norm" not in df_filtrado.columns: 
    df_filtrado["Status_norm"] = ""

# --- CÁLCULO DOS KPIS ---
total_os = len(df_filtrado)
realizado_prazo = int((df_filtrado["Status_norm"].isin(_status_prazo)).sum()) if total_os > 0 else 0
realizado_atraso = int((df_filtrado["Status_norm"].isin(_status_atraso)).sum()) if total_os > 0 else 0
realizado_total = realizado_prazo + realizado_atraso
nao_realizado = int((df_filtrado["Status_norm"].isin(_status_aberto)).sum()) if total_os > 0 else 0
taxa_conclusao = (realizado_total / total_os * 100.0) if total_os > 0 else 0.0

# --- EXIBIÇÃO DO PERÍODO ---
if not df_filtrado.empty and "Data inicial programada" in df_filtrado.columns:
    datas_validas = pd.to_datetime(df_filtrado["Data inicial programada"], errors="coerce").dropna()
    if not datas_validas.empty:
        dt_min = datas_validas.min().strftime("%d/%m/%Y")
        dt_max = datas_validas.max().strftime("%d/%m/%Y")
        st.markdown(f"<p style='color: #475569; font-size: 15px; margin-bottom: 15px;'><b>Período Analisado:</b> {dt_min} a {dt_max}</p>", unsafe_allow_html=True)
    else:
        st.markdown("<p style='color: #475569; font-size: 15px; margin-bottom: 15px;'><b>Período Analisado:</b> Datas indisponíveis</p>", unsafe_allow_html=True)
else:
    st.markdown("<p style='color: #475569; font-size: 15px; margin-bottom: 15px;'><b>Período Analisado:</b> Sem dados</p>", unsafe_allow_html=True)

# --- RENDERIZAÇÃO DAS MÉTRICAS ---
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
col_kpi1.metric("📋 Planejado (OS)", f"{total_os}")
col_kpi2.metric("🔴 Backlog (Não Realizado)", f"{nao_realizado}", delta=f"{nao_realizado} pendentes", delta_color="inverse")
col_kpi3.metric("🟢 Realizado (Total)", f"{realizado_total}", delta=f"{realizado_prazo} no prazo / {realizado_atraso} atrasado")
col_kpi4.metric("📈 Taxa de Conclusão", f"{taxa_conclusao:.1f}%")

st.markdown("---")
#endregion

#region SESSÃO 8: ABAS E RENDERIZAÇÃO DOS GRÁFICOS COMPLETOS
# ==========================================
tab1, tab2 = st.tabs(["📊 Visão Gerencial (Indicadores)", "🗺️ Roteirização e Mapa de Campo"])

# --- ABA 1: VISÃO GERENCIAL COMPLETA ---
with tab1:
    if st.session_state["perfil"] == "Técnico":
        st.info("🔒 Seu perfil (Técnico) tem foco operacional. Por favor, utilize a aba 'Roteirização e Mapa de Campo'.")
    else:
        df_visao_base = df_filtrado.copy()
        
        # Paleta Harmonizada
        cor_plan = "#64748B" # Cinza Ardósia
        cor_real = "#3B82F6" # Azul Royal
        cor_prazo = "#10B981" # Verde Esmeralda
        cor_atraso = "#F59E0B" # Laranja Âmbar
        cor_pendente = "#FF4B4B" # Vermelho Coral 
        
        if taxa_conclusao <= 25: gauge_color = cor_pendente
        elif taxa_conclusao <= 50: gauge_color = cor_atraso
        elif taxa_conclusao <= 80: gauge_color = cor_prazo
        else: gauge_color = cor_real

        # CAMADA 1: GAUGE, ROSCA E ÁREA ACUMULADA
        with st.expander("Resumo Executivo (Geral)", expanded=True):
            col_g1, col_g2, col_g5 = st.columns(3)

            with col_g1:
                st.markdown("#### Realizado x Planejado")
                gauge_options = {
                    "tooltip": {"formatter": "{a} <br/>{b}: {c}%"},
                    "series": [{
                        "name": "Conclusão", "type": "gauge", 
                        "min": 0, "max": 100, 
                        "radius": "75%", # Ajustado para parear com a rosca
                        "progress": {"show": True, "width": 14, "itemStyle": {"color": gauge_color}},
                        "axisLine": {"lineStyle": {"width": 14, "color": [[0.25, cor_pendente], [0.50, cor_atraso], [0.80, cor_prazo], [1.00, cor_real]]}},
                        "pointer": {"show": True, "length": "60%", "width": 6},
                        "itemStyle": {"color": gauge_color},
                        "title": {"show": True, "offsetCenter": [0, "70%"], "fontSize": 14},
                        "detail": {
                            "valueAnimation": True, "offsetCenter": [0, "40%"], 
                            "formatter": f"{taxa_conclusao:.1f}%\n{realizado_total} / {total_os}", # Capado com 1 casa decimal
                            "fontSize": 16
                        },
                        "data": [{"value": round(taxa_conclusao, 1), "name": "Realizado"}],
                    }],
                }
                st_echarts(options=gauge_options, height="350px", theme="streamlit", key="aba1_gauge")

            with col_g2:
                st.markdown("#### Distribuição por Status")
                rosca_options = {
                    "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                    "legend":  {"orient": "horizontal", "bottom": "0%"},
                    "series": [{
                        "name": "Status", "type": "pie", 
                        "radius": ["45%", "75%"], # Aumentado para equiparar ao gauge
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
                realizado_diario_a = df_area[df_area["Status_norm"].isin(_status_prazo | _status_atraso)].groupby("dia_realizado").size().rename("Realizado_Dia")
                planejado_diario_a = df_area.groupby("dia_programado").size().rename("Planejado_Dia")

                _datas_a = pd.Index([]).union(realizado_diario_a.index).union(planejado_diario_a.index)
                if len(_datas_a) > 0:
                    _idx_da   = pd.date_range(start=_datas_a.min(), end=_datas_a.max(), freq="D")
                    _real_acum = realizado_diario_a.reindex(_idx_da, fill_value=0).cumsum()
                    _plan_acum = planejado_diario_a.reindex(_idx_da, fill_value=0).cumsum()
                    
                    area_options = {
                        "tooltip": {"trigger": "axis"}, 
                        "legend": {"top": "bottom"},
                        "toolbox": { # Botões interativos do topo direito
                            "show": True,
                            "feature": {
                                "magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}},
                                "restore": {"title": "Restaurar"},
                                "saveAsImage": {"title": "Salvar Imagem"}
                            }
                        },
                        "dataZoom": [ # Barra de navegação temporal
                            {"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}
                        ],
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

        # CAMADA 2: HEATMAP DISCRETO E BARRAS HORIZONTAIS
        with st.expander("Análise Operacional: Matriz de Prioridades e Execução por Categoria", expanded=True):
            col_h1, col_h2 = st.columns([1.2, 1])
            
            with col_h1:
                st.markdown("#### Matriz: Prioridade vs Classificação")
                st.caption("Volume total de OS planejadas (Cor indica concentração)")
                
                df_heat = df_visao_base.copy()
                agg = df_heat.groupby(["Classificacao", "Criticidade"]).size().reset_index(name="Total")
                
                ordem_class = ["Confiabilidade", "Segurança", "Confiabilidade e Segurança"]
                ordem_crit  = ["Muito Alta", "Alta", "Média", "Baixa"]
                
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
                        "xAxis": {
                            "type": "category", "data": ordem_crit, 
                            "splitArea": {"show": True},
                            "axisLine": {"show": False}, "axisTick": {"show": False}
                        },
                        "yAxis": {
                            "type": "category", "data": ordem_class, 
                            "splitArea": {"show": True},
                            "axisLine": {"show": False}, "axisTick": {"show": False}
                        },
                        "visualMap": {
                            "min": 0, "max": max_val if max_val > 0 else 10,
                            "calculable": True, "orient": "horizontal", "left": "center", "bottom": "0%",
                            "inRange": {"color": ["#F1F5F9", "#93C5FD", "#3B82F6", "#1E3A8A"]} 
                        },
                        "series": [{
                            "name": "Total de OS", "type": "heatmap", "data": heat_data,
                            "label": {
                                "show": True, 
                                "color": "#FFFFFF", 
                                "fontWeight": "bold",
                                "formatter": JsCode("function(p){return p.value[2] > 0 ? p.value[2] : '';}")
                            },
                            "itemStyle": {"borderColor": "#FFFFFF", "borderWidth": 2}
                        }],
                    }
                    st_echarts(options=heatmap_options, height="380px", theme="streamlit", key="aba1_heatmap_discrete")
                else:
                    st.info("Sem dados para a Matriz.")

            with col_h2:
                st.markdown("#### Plan x Realizado por Categoria")
                st.caption("Comparativo de volume total e execução.")
                
                df_bar_cat = df_visao_base.copy()
                plan_cat = df_bar_cat.groupby("Classificacao").size()
                real_cat = df_bar_cat[df_bar_cat["Status_norm"].isin(_status_prazo | _status_atraso)].groupby("Classificacao").size()
                
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
                        {
                            "name": "Planejado", "type": "bar",
                            "data": val_plan,
                            "itemStyle": {"color": cor_plan}, 
                            "label": {"show": True, "position": "right", "color": "#475569"}
                        },
                        {
                            "name": "Realizado", "type": "bar",
                            "data": val_real,
                            "itemStyle": {"color": cor_real}, 
                            "label": {"show": True, "position": "right", "color": "#475569"}
                        }
                    ]
                }
                st_echarts(options=bar_horiz_options, height="380px", theme="streamlit", key="aba1_bar_horiz")

        # CAMADA 3: GRÁFICOS DE TURNO (BARRA E LINHA COM TOOLBOX)
        with st.expander("Execução por Turno e Acumulado", expanded=True):
            col_g3, col_g6 = st.columns(2)
            
            _cor_turno = {"00h-07h": "#4F46E5", "07h-16h": "#3B82F6", "16h-00h": "#06B6D4"}

            with col_g3:
                st.markdown("#### Realizado por Turno")
                df_barra_real = df_visao_base[df_visao_base["Status_norm"].isin(_status_prazo | _status_atraso)].copy()
                x_turnos = ["00h-07h", "07h-16h", "16h-00h"]
                _cnt_t   = df_barra_real.groupby("Turno").size()
                y_vals   = [int(_cnt_t.get(t, 0)) for t in x_turnos]

                barra_options = {
                    "tooltip": {"trigger": "axis"}, 
                    "xAxis": {"type": "category", "data": x_turnos}, 
                    "yAxis": {"type": "value"},
                    "toolbox": { 
                        "show": True,
                        "feature": {
                            "magicType": {"type": ["line", "bar"], "title": {"line": "Linha", "bar": "Barra"}},
                            "restore": {"title": "Restaurar"},
                            "saveAsImage": {"title": "Salvar Imagem"}
                        }
                    },
                    "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "15%", "containLabel": True},
                    "series": [{
                        "type": "bar", "barWidth": "55%", "label": {"show": True, "position": "inside", "formatter": "{c}", "color": "#FFFFFF", "fontWeight": "bold"},
                        "data": [{"value": v, "name": t, "itemStyle": {"color": _cor_turno.get(t, "#94A3B8")}} for t, v in zip(x_turnos, y_vals)],
                    }],
                }
                st_echarts(options=barra_options, height="350px", theme="streamlit", key="aba1_barra")

            with col_g6:
                st.markdown("#### Realizado Acumulado por Turno")
                df_linhas_plot = df_visao_base.dropna(subset=["dia_realizado"]).copy()
                if not df_linhas_plot.empty:
                    _ordem_t  = ["00h-07h", "07h-16h", "16h-00h"]
                    _idx_dt   = pd.date_range(start=df_linhas_plot["dia_realizado"].min(), end=df_linhas_plot["dia_realizado"].max(), freq="D")
                    
                    _series_t = []
                    for _t in _ordem_t:
                        _s = (df_linhas_plot[df_linhas_plot["Turno"] == _t].groupby("dia_realizado").size().reindex(_idx_dt, fill_value=0).cumsum())
                        _series_t.append({"name": _t, "type": "line", "smooth": True, "data": _s.tolist(), "lineStyle": {"color": _cor_turno[_t], "width": 3}, "itemStyle": {"color": _cor_turno[_t]}})

                    linhas_options = {
                        "tooltip": {"trigger": "axis"}, 
                        "legend": {"top": "bottom"},
                        "toolbox": { 
                            "show": True,
                            "feature": {
                                "magicType": {"type": ["line", "bar", "stack"], "title": {"line": "Linha", "bar": "Barra", "stack": "Empilhado"}},
                                "restore": {"title": "Restaurar"},
                                "saveAsImage": {"title": "Salvar Imagem"}
                            }
                        },
                        "dataZoom": [ 
                            {"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100, "bottom": "5%"}
                        ],
                        "grid": {"left": "5%", "right": "5%", "bottom": "25%", "top": "15%", "containLabel": True},
                        "xAxis": {"type": "category", "data": [d.strftime("%d/%m") for d in _idx_dt]}, 
                        "yAxis": {"type": "value"},
                        "series": _series_t,
                    }
                    st_echarts(options=linhas_options, height="350px", theme="streamlit", key="aba1_linhas")
                else:
                    st.info("Sem dados cronológicos.")

        # TABELA GERENCIAL CENTRALIZADA
        st.subheader("📋 Lista Detalhada de OS")
        df_lista = df_visao_base.copy().rename(columns={"Ordem servico": "OS"})
        if "Data inicial programada" in df_lista.columns:
            df_lista["Data inicial programada"] = pd.to_datetime(df_lista["Data inicial programada"], errors="coerce").dt.strftime("%d/%m/%Y")
        if "Data/Hora Realizado" in df_lista.columns:
            df_lista["Data/Hora Realizado"] = pd.to_datetime(df_lista["Data/Hora Realizado"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M").fillna("")

        colunas_ordem = ["OS", "Patio", "Ativo", "Criticidade", "Classificacao", "Descrição Longa", "Data inicial programada", "Status da Operação", "Data/Hora Realizado","Concluído por"]
        for c in colunas_ordem:
            if c not in df_lista.columns: df_lista[c] = ""
            
        if not df_lista.empty:
            df_styled = df_lista[colunas_ordem].style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            st.dataframe(df_styled, use_container_width=True, height=400, hide_index=True)

# --- ABA 2: ROTEIRIZAÇÃO E MAPA DE CAMPO COMPACTO ---
with tab2:
    st.markdown("### 🗺️ Navegação Geográfica Operacional")
    
    col_mapa, col_acao = st.columns([6, 4], gap="large")
    df_pendentes_f = df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto)].copy()
    df_recomendado = pd.DataFrame()

    with col_acao:
        st.markdown("#### ⚙️ Ferramentas de Campo")
        
# --- CONTROLE DE ORIGEM E GPS ---

        if "lat_partida" not in st.session_state:
            lat_base, lon_base, nome_base = obter_base_padrao_usuario()
            st.session_state["lat_partida"] = lat_base
            st.session_state["lon_partida"] = lon_base
            st.session_state["local_nome"] = nome_base

        if "gps_pending" not in st.session_state:
            st.session_state["gps_pending"] = False

        if "gps_trials" not in st.session_state:
            st.session_state["gps_trials"] = 0

        # Botões organizados lado a lado
        c1, c2 = st.columns(2)

        with c1:
            if st.button("📍 Minha Localização", use_container_width=True, key="btn_gps_localizacao"):
                st.session_state["gps_pending"] = True
                st.session_state["gps_trials"] = 0

        with c2:
            if st.button("🏠 Minha Base", use_container_width=True, key="btn_minha_base"):
                lat_base, lon_base, nome_base = obter_base_padrao_usuario()
                st.session_state["lat_partida"] = lat_base
                st.session_state["lon_partida"] = lon_base
                st.session_state["local_nome"] = nome_base
                st.session_state["gps_pending"] = False
                st.session_state["gps_trials"] = 0
                st.rerun()

        # Polling do GPS
        if st.session_state.get("gps_pending"):
            loc = get_geolocation()

            if loc and isinstance(loc, dict) and "coords" in loc:
                coords = loc.get("coords", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")

                if lat is not None and lon is not None:
                    lat_f = float(lat)
                    lon_f = float(lon)

                    st.session_state["lat_partida"] = lat_f
                    st.session_state["lon_partida"] = lon_f
                    st.session_state["local_nome"] = reverse_geocode_coordenada(lat_f, lon_f)

                    st.session_state["gps_pending"] = False
                    st.session_state["gps_trials"] = 0
                    st.success("GPS Ativado!")
                    st.rerun()

            elif loc and isinstance(loc, dict) and "error" in loc:
                code = loc["error"].get("code", "N/A")
                msg = loc["error"].get("message", "Erro desconhecido de geolocalização.")
                st.session_state["gps_pending"] = False
                st.session_state["gps_trials"] = 0
                st.error(f"GPS falhou (code {code}): {msg}")

            else:
                st.session_state["gps_trials"] += 1

                if st.session_state["gps_trials"] < 8:
                    st.info("Aguardando permissão do navegador...")
                    st.rerun()
                else:
                    st.session_state["gps_pending"] = False
                    st.session_state["gps_trials"] = 0
                    st.error("Tempo do GPS esgotado.")

        st.markdown("---")

        raio_busca_km = st.slider(
            "📏 Raio de Atuação Visual (km):",
            0, 50, 10, 5,
            key="slider_raio_atuacao"
        )

        st.caption(f"📌 Origem: **{st.session_state['local_nome']}**")

        lat_origem = float(st.session_state["lat_partida"])
        lon_origem = float(st.session_state["lon_partida"])
        
        if not df_pendentes_f.empty:
            df_calc = df_pendentes_f.copy()
            df_calc["lat_patio"] = df_calc["Patio"].map(
                lambda p: COORDENADAS_FIXAS.get(str(p), [np.nan, np.nan])[0]
            )
            df_calc["lon_patio"] = df_calc["Patio"].map(
                lambda p: COORDENADAS_FIXAS.get(str(p), [np.nan, np.nan])[1]
            )
            com_coord = df_calc.dropna(subset=["lat_patio", "lon_patio"]).copy()

            if not com_coord.empty:
                hoje_atual = datetime.now().date()

                
                # MOTOR DE BLOCOS DE PRAZO: 1 = Atrasado, 2 = Hoje, 3 = Futuro
                com_coord["Ordem_Prazo"] = com_coord["dt_prog_filtro"].apply(
                    lambda dt: 1 if pd.notna(dt) and dt.date() < hoje_atual else (2 if pd.notna(dt) and dt.date() == hoje_atual else 3)
                )
                
                com_coord["Distancia_km"] = haversine_vectorized(lat_origem, lon_origem, com_coord["lat_patio"], com_coord["lon_patio"])
                
                # CRITÉRIO DE ORDENAÇÃO: Primeiro o bloco de prazos, depois o ranking de criticidade (1 a 4)
                df_recomendado = com_coord[com_coord["Distancia_km"] <= raio_busca_km].sort_values(by=["Ordem_Prazo", "Criticidade_rank", "Distancia_km"])

        st.info(f"**{len(df_recomendado)} OS pendentes** encontradas no raio de {raio_busca_km}km.")

        if not df_recomendado.empty:
            st.markdown("---")
            st.markdown("#### ✅ Confirmar Execução")
            os_selecionada = st.selectbox("Escolha a OS concluída:", df_recomendado["Ordem servico"].astype(str).tolist())
            if st.button("Gravar Baixa no Sistema", use_container_width=True, type="primary"):
                realizado_dt = agora_dt()
                usr = st.session_state["username"]
                mask = (st.session_state["df_os"]["Ordem servico"].astype(str) == str(os_selecionada))
                dt_prog = st.session_state["df_os"].loc[mask, "Data inicial programada"].iloc[0] if len(st.session_state["df_os"].loc[mask]) > 0 else pd.NaT
                novo_status = determinar_status_execucao(dt_prog, realizado_dt)
                coord = st.session_state["df_os"].loc[mask, "Coordenacao"].iloc[0]

                upsert_baixa(str(os_selecionada), novo_status, formatar_dt_br(realizado_dt), coord, usr)
                st.toast(f"OS {os_selecionada} baixada com sucesso!")
                st.rerun()

    # --- MAPA ---
    with col_mapa:
        # Limites aproximados do estado de SP (para travar a câmera)
        SP_MIN_LAT, SP_MAX_LAT = -25.50, -19.50
        SP_MIN_LON, SP_MAX_LON = -53.50, -44.00

        # Centro do mapa "clipado" para não estourar fora da área operacional
        lat_centro = min(max(lat_origem, SP_MIN_LAT), SP_MAX_LAT)
        lon_centro = min(max(lon_origem, SP_MIN_LON), SP_MAX_LON)

        # Zoom dinâmico baseado no raio + latitude (trigonometria)
        def calcular_zoom_por_raio(raio_km: float, latitude_ref: float) -> int:
            raio_km = max(float(raio_km), 0.5)  # evita divisão/log extremos
            lat_rad = math.radians(float(latitude_ref))

            # Comprimento aproximado de 1 grau de longitude na latitude corrente
            km_por_grau_lon = 111.320 * max(math.cos(lat_rad), 0.20)

            # Queremos enxergar cerca de 2x o raio na largura do mapa
            largura_graus = (2.0 * raio_km) / km_por_grau_lon

            # Aproximação de zoom WebMercator/Leaflet
            zoom = math.log2(360.0 / max(largura_graus, 1e-6))

            # Faixa segura para uso operacional em SP
            return int(min(18, max(6, round(zoom))))

        zoom_mapa = calcular_zoom_por_raio(raio_busca_km, lat_centro)

        mapa = folium.Map(
            location=[lat_centro, lon_centro],
            zoom_start=zoom_mapa,
            max_bounds=True,
            min_lat=SP_MIN_LAT,
            max_lat=SP_MAX_LAT,
            min_lon=SP_MIN_LON,
            max_lon=SP_MAX_LON,
            control_scale=True
        )

        folium.Marker(
            [lat_origem, lon_origem],
            popup="Sua Posição",
            icon=folium.Icon(color="red", icon="play")
        ).add_to(mapa)

        folium.Circle(
            [lat_origem, lon_origem],
            radius=raio_busca_km * 1000.0,
            color="blue",
            fill=True,
            fill_opacity=0.08
        ).add_to(mapa)

        if not df_recomendado.empty:
            for _, row in df_recomendado.iterrows():
                folium.Marker(
                    [row["lat_patio"], row["lon_patio"]],
                    popup=f"OS: {row['Ordem servico']}",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(mapa)

        st_folium(
            mapa,
            height=650,
            use_container_width=True,
            key="mapa_final_limpo"
        )

    # --- NOVA TABELA DE CRONOGRAMA DE CAMPO (ABAIXO DO MAPA) ---
    st.markdown("---")
    st.markdown("#### 📋 Cronograma de Execução de Campo (OS Pendentes no Raio)")
    
    if not df_recomendado.empty:
        df_tabela_campo = df_recomendado.copy()
        
        # Estrutura e renomeação de colunas solicitadas
        df_tabela_campo = df_tabela_campo.rename(columns={
            "Ordem servico": "OS",
            "Patio": "Patio",
            "Classificacao": "Classificação"
        })
        df_tabela_campo["Data da Programação"] = df_tabela_campo["dt_prog_filtro"].dt.strftime("%d/%m/%Y")
        
        # Função interna para aplicar os sombreados condicionados por linha
        def aplicar_cor_prazo(row):
            dt = row["dt_prog_filtro"]
            if pd.isna(dt):
                return [""] * len(row)
            
            d = dt.date()
            hoje_ref = datetime.now().date()
            
            if d < hoje_ref:
                return ["background-color: #FEE2E2; color: #7F1D1D; font-weight: 500;"] * len(row)  # Sombreado Vermelho Suave
            elif d == hoje_ref:
                return ["background-color: #FEF3C7; color: #78350F; font-weight: 500;"] * len(row)  # Sombreado Amarelo Suave
            return [""] * len(row)  # Sem cor (Padrão)

        df_estilizado = df_tabela_campo.style.apply(aplicar_cor_prazo, axis=1)
        
        colunas_exibir = ["OS", "Data da Programação", "Patio", "Ativo", "Criticidade", "Classificação", "Descrição Longa"]
        
        st.dataframe(
            df_estilizado, 
            use_container_width=True, 
            height=350, 
            hide_index=True,
            column_order=colunas_exibir
        )
    else:
        st.info("Nenhuma OS pendente localizada dentro do raio de atuação selecionado.")
#endregion