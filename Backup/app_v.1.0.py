# ==========================================
#region SESSÃO 1: Imports & Configuração da Página
# ==========================================

import io
import time
import math
import re
import os
import shutil
import sqlite3
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

st.set_page_config(page_title="Painel de OS Eletroeletrônica", layout="wide")
st.title("⚡ Sistema de Gestão de Ordens de Serviço - Eletroeletrônica")

#endregion

#region SESSÃO 2: Funções (Lógica, Utilidades, GPS, Distância, Persistência, Export)
# ==========================================
# SESSÃO 2: Funções (Lógica, Utilidades, GPS, Distância, Persistência, Export)
# ==========================================

#region SESSÃO 2.1 ===== Lógica =====
def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.strip().str.upper()
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
def db_path():
    return "baixas_os.db"

def init_db():
    conn = sqlite3.connect(db_path())
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS baixas (
            os TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            realizado_em TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def upsert_baixa(os_id: str, status: str, realizado_em_str: str):
    conn = sqlite3.connect(db_path())
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO baixas (os, status, realizado_em)
        VALUES (?, ?, ?)
        ON CONFLICT(os) DO UPDATE SET
            status=excluded.status,
            realizado_em=excluded.realizado_em
    """, (str(os_id), str(status), str(realizado_em_str)))
    conn.commit()
    conn.close()

def carregar_baixas_df() -> pd.DataFrame:
    init_db()
    conn = sqlite3.connect(db_path())
    df = pd.read_sql_query("SELECT os, status, realizado_em FROM baixas", conn)
    conn.close()
    if df.empty:
        return df
    df["os"] = df["os"].astype(str)
    df["realizado_em"] = df["realizado_em"].astype(str)
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

#endregion

#region SESSÃO 3: Banco de Coordenadas Fixo
# ==========================================
# SESSÃO 3: Banco de Coordenadas Fixo
# ==========================================

#region SESSÃO 3.1 ===== Coordenadas Fixas =====
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
  "Base IPA":[-23.777009, -46.302837]
}
#endregion

#endregion

#region SESSÃO 4: ETL (Carregamento e Tratamento)
# ==========================================
# SESSÃO 4: ETL (Carregamento e Tratamento)
# ==========================================

ETL_VERSION = "v5_status_datahora_descLonga_2026-05-27"

def tratar_df_os(df: pd.DataFrame):
    df = normalize_cols(df)

    col_os = pick_first_existing(df, ["ORDEM SERVICO", "ORDEM SERVIÇO", "OS", "ORDEM_DE_SERVICO"])
    col_ativo = pick_first_existing(df, ["ATIVO", "EQUIPAMENTO"])
    col_atividade = pick_first_existing(df, ["ATIVIDADE ATIVO", "ATIVIDADE_ATIVO", "ATIVIDADE"])
    col_prioridade = pick_first_existing(df, ["PRIORIDADE", "CRITICIDADE"])
    col_hxh = pick_first_existing(df, ["HXH PLANO", "HXH_PLANO"])
    col_patio = pick_first_existing(df, ["PATIO", "PÁTIO"])
    col_data_prog = pick_first_existing(df, ["DATA INICIAL PROGRAMADA", "DATA_INICIAL_PROGRAMADA", "DATA PROGRAMADA", "DATA"])

    # NOVO: descrição longa (tolerante a nomes)
    col_desc = pick_first_existing(df, [
        "DESCRIÇÃO LONGA", "DESCRICAO LONGA", "DESCRIÇÃO", "DESCRICAO",
        "DESCRICAO DO SERVICO", "DESCRIÇÃO DO SERVIÇO", "DESCRICAO SERVICO", "TEXTO LONGO"
    ])

    missing = []
    if not col_os: missing.append("ORDEM SERVICO")
    if not col_ativo: missing.append("ATIVO")
    if not col_atividade: missing.append("ATIVIDADE ATIVO")
    if not col_prioridade: missing.append("PRIORIDADE")
    if not col_hxh: missing.append("HXH PLANO")
    if not col_data_prog: missing.append("DATA INICIAL PROGRAMADA")
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes no Excel: {', '.join(missing)}")

    df["ATIVO_CAN"] = df[col_ativo].astype(str).str.strip()
    df["ATIVIDADE_CAN"] = df[col_atividade].astype(str).str.strip()
    df["PRIORIDADE_CAN"] = df[col_prioridade].astype(str).str.strip()
    df["HXH_CAN"] = pd.to_numeric(df[col_hxh], errors="coerce").fillna(0)

    if col_patio:
        df["PATIO_CAN"] = df[col_patio].astype(str).str.strip().str.upper()
    else:
        df["PATIO_CAN"] = df["ATIVO_CAN"].str[:3].str.strip().str.upper()

    df["DATA_PROG_CAN"] = df[col_data_prog].apply(parse_data_programada)

    # Descrição longa (se não existir, fica vazio)
    if col_desc:
        df["DESC_LONGA_CAN"] = df[col_desc].astype(str).str.strip()
    else:
        df["DESC_LONGA_CAN"] = ""

    # Classificação + Criticidade
    df["Classificacao"] = df["ATIVIDADE_CAN"].apply(classificar_atividade)
    crit = df["PRIORIDADE_CAN"].apply(extrair_criticidade)
    df["Criticidade_rank"] = [c[0] for c in crit]
    df["Criticidade"] = [c[1] for c in crit]
    df["Nivel_Prioridade"] = df.apply(
        lambda r: calcular_nivel_prioridade(r["Classificacao"], r["Criticidade_rank"]),
        axis=1
    )
    df["Desc_Prioridade"] = df["Classificacao"] + " | " + df["Criticidade"]

    # Status default do mês
    df["STATUS_CAN"] = "Não Realizado"
    df["REALIZADO_EM_CAN"] = ""

    df_out = pd.DataFrame({
        "Ordem servico": df[col_os].astype(str).str.strip(),
        "Patio": df["PATIO_CAN"],
        "Ativo": df["ATIVO_CAN"],
        "Criticidade": df["Criticidade"],
        "Classificacao": df["Classificacao"],
        "Descrição Longa": df["DESC_LONGA_CAN"],
        "Data inicial programada": df["DATA_PROG_CAN"],
        "Status da Operação": df["STATUS_CAN"],
        "Data/Hora Realizado": df["REALIZADO_EM_CAN"],
        "Hxh Plano": df["HXH_CAN"],

        # mantém também para roteirização/sort
        "Criticidade_rank": df["Criticidade_rank"],
        "Nivel_Prioridade": df["Nivel_Prioridade"],
        "Desc_Prioridade": df["Desc_Prioridade"],
        "Prioridade": df["PRIORIDADE_CAN"],
        "Atividade ativo": df["ATIVIDADE_CAN"],
    })

    return df_out


@st.cache_data
def carregar_excel_por_bytes(excel_bytes: bytes, etl_version: str):
    bio = io.BytesIO(excel_bytes)
    df = pd.read_excel(bio, engine="openpyxl")
    return tratar_df_os(df)


@st.cache_data
def carregar_excel_por_path(path_excel: str, etl_version: str):
    df = pd.read_excel(path_excel, engine="openpyxl")
    return tratar_df_os(df)

#endregion

#region SESSÃO 10: Simulação de dados (APENAS TESTE - remover depois)
# ==========================================
# SESSÃO 10: Simulação de dados (APENAS TESTE - remover depois)
# ==========================================

#region SESSÃO 10.1: Gerador de base simulada (para testar KPIs e gráficos)
def gerar_base_simulada(qtd: int = 800, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    patios = list(COORDENADAS_FIXAS.keys())

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


#region SESSÃO 10.2: Controle na Sidebar (retorna DF simulado quando ativado)
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

#region SESSÃO 5: Fonte de Dados + Overlay das Baixas + Exportar + Modo Master (Salvar com Backup)
# ==========================================
# SESSÃO 5: Fonte de Dados + Overlay das Baixas + Exportar + Modo Master (Salvar com Backup)
# ==========================================

# Variáveis-base da sessão
base_path = None
df_base = pd.DataFrame()

#region SESSÃO 5.1: Escolha da fonte de dados (Simulação ou Excel real)
st.sidebar.header("📥 Fonte de Dados")

# Tenta simulação primeiro
usar_sim, df_sim = simulacao_sidebar()
#endregion

#region SESSÃO 5.2: Montagem do df_base via Simulação
if usar_sim:
    df_base = df_sim.copy()
    st.session_state["df_os"] = df_base
    base_path = None  # em simulação não existe arquivo-base físico
#endregion

#region SESSÃO 5.3: Montagem do df_base via Excel real
else:
    default_path_str = st.session_state.get("base_path_str", str(Path("teste1.xlsx")))
    base_path_str = st.sidebar.text_input("Caminho do Excel base:", value=default_path_str)
    st.session_state["base_path_str"] = base_path_str

    base_path = Path(base_path_str)

    if st.sidebar.button("🔄 Recarregar dados (ETL)", use_container_width=True):
        st.cache_data.clear()
        if "df_os" in st.session_state:
            del st.session_state["df_os"]
        st.rerun()

    if not base_path.exists():
        st.sidebar.error(f"Arquivo não encontrado: {base_path}")
        st.stop()

    # Carrega base tratada pelo ETL
    df_base_bruto = carregar_excel_por_path(str(base_path), ETL_VERSION)

    # Inicializa e carrega banco das baixas
    init_db()
    df_baixas = carregar_baixas_df()

    df_base = df_base_bruto.copy()
#endregion

#region SESSÃO 5.4: Overlay das baixas persistidas (SQLite)
    if not df_baixas.empty:
        df_base["Ordem servico"] = df_base["Ordem servico"].astype(str)

        df_baixas = df_baixas.rename(columns={
            "os": "Ordem servico",
            "status": "Status da Operação",
            "realizado_em": "Data/Hora Realizado"
        })

        df_base = df_base.merge(
            df_baixas,
            on="Ordem servico",
            how="left",
            suffixes=("", "_baixado")
        )

        # Sobrescreve somente quando existir baixa registrada
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

        df_base.drop(
            columns=["Status da Operação_baixado", "Data/Hora Realizado_baixado"],
            inplace=True
        )
#endregion

#region SESSÃO 5.5: Persistência do df_base em memória
st.session_state["df_os"] = df_base
df_base = st.session_state["df_os"]
#endregion

#region SESSÃO 5.6: Operações Master
st.sidebar.header("👑 Operações Master")
modo_master = st.sidebar.checkbox("Ativar Modo Master", value=False)

# Só habilita salvar no arquivo-base quando NÃO estiver em simulação
if modo_master and base_path is not None:
    st.sidebar.warning("⚠️ Modo Master habilitado. Evite salvar com o Excel aberto por outro usuário.")

    if st.sidebar.button("💾 SALVAR no arquivo base (com backup)", use_container_width=True):
        try:
            excel_bytes = gerar_excel_bytes(df_base)
            backup_criado = salvar_excel_com_backup_bytes(excel_bytes, base_path)
            st.sidebar.success("✅ Base salva com sucesso!")
            st.sidebar.info(f"Backup criado: {backup_criado}")
        except Exception as e:
            st.sidebar.error(f"❌ Falha ao salvar base: {e}")

elif modo_master and base_path is None:
    st.sidebar.info("Modo Master desabilitado durante simulação.")
#endregion
#endregion

#region SESSÃO 6: Filtros & KPIs (Sidebar)
# ==========================================

#region SESSÃO 6.1: ===== Filtros =====
st.sidebar.header("📊 Filtros Estratégicos")

# Preparação das colunas auxiliares (Turno e Status) ANTES dos filtros
if "Status_norm" not in df_base.columns:
    df_base["Status_norm"] = df_base["Status da Operação"].astype(str).str.strip().str.upper()
    df_base["dt_realizado"] = df_base["Data/Hora Realizado"].apply(parse_datahora_realizado)
    df_base["Turno"] = df_base["dt_realizado"].apply(classificar_turno)
    df_base["dia_realizado"] = pd.to_datetime(df_base["dt_realizado"], errors="coerce").dt.normalize()

colunas_esperadas = {"Classificacao", "Criticidade", "Nivel_Prioridade", "Status da Operação"}
faltando = [c for c in colunas_esperadas if c not in df_base.columns]
if faltando:
    st.error(f"❌ Colunas faltando: {', '.join(faltando)} ➡️ Recarregue a base.")
    st.stop()

# 1º filtro: Pátio
lista_patios = sorted(df_base["Patio"].dropna().astype(str).unique().tolist())
patios_selecionados = st.sidebar.multiselect("Selecione os Pátios:", lista_patios, default=lista_patios)

# 2º filtro: Classificação
ordem_class = ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
lista_classif = [c for c in ordem_class if c in set(df_base["Classificacao"].dropna().astype(str))]
classif_selecionadas = st.sidebar.multiselect("Classificação:", lista_classif, default=lista_classif)

# 3º filtro: Criticidade
ordem_crit = ["Muito Alta", "Alta", "Média", "Baixa"]
lista_crit = [c for c in ordem_crit if c in set(df_base["Criticidade"].dropna().astype(str))]
crit_selecionadas = st.sidebar.multiselect("Criticidade:", lista_crit, default=lista_crit)

st.sidebar.markdown("---")
st.sidebar.subheader("⏳ Filtros Operacionais")

# NOVO: Filtro de Status
opcoes_status = [
    "Todos", 
    "Todas Concluídas", 
    "Concluídas no Prazo", 
    "Concluídas com Atraso", 
    "Pendentes"
]
status_sel = st.sidebar.selectbox("Status das OS:", opcoes_status)

# NOVO: Filtro de Turno
lista_turnos = ["00h-07h", "07h-16h", "16h-00h"]
turnos_sel = st.sidebar.multiselect("Turno de Execução:", lista_turnos, default=lista_turnos)

# ---- MOTOR DE APLICAÇÃO DOS FILTROS ----
df_filtrado = df_base[
    (df_base["Patio"].isin(patios_selecionados)) &
    (df_base["Classificacao"].isin(classif_selecionadas)) &
    (df_base["Criticidade"].isin(crit_selecionadas))
].copy()

_status_prazo  = {"REALIZADO"}
_status_atraso = {"REALIZADO FORA DA DATA DE PROGRAMAÇÃO"}
_status_aberto = {"NÃO REALIZADO", "NAO REALIZADO", "PENDENTE", ""}

# Aplica Filtro de Status
if status_sel == "Todas Concluídas":
    df_filtrado = df_filtrado[df_filtrado["Status_norm"].isin(_status_prazo | _status_atraso)]
elif status_sel == "Concluídas no Prazo":
    df_filtrado = df_filtrado[df_filtrado["Status_norm"].isin(_status_prazo)]
elif status_sel == "Concluídas com Atraso":
    df_filtrado = df_filtrado[df_filtrado["Status_norm"].isin(_status_atraso)]
elif status_sel == "Pendentes":
    df_filtrado = df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto)]

# Aplica Filtro de Turno (se não estiverem todos selecionados)
if turnos_sel and len(turnos_sel) < len(lista_turnos):
    df_filtrado = df_filtrado[df_filtrado["Turno"].isin(turnos_sel)]
#endregion

#region SESSÃO 6.2: ===== KPIs coerentes =====
total_os = len(df_filtrado)

realizado_prazo = int((df_filtrado["Status da Operação"] == "Realizado").sum())
realizado_atraso = int((df_filtrado["Status da Operação"] == "Realizado Fora da Data de Programação").sum())
realizado_total = realizado_prazo + realizado_atraso
nao_realizado = int((df_filtrado["Status_norm"].isin(_status_aberto)).sum())

taxa_conclusao = (realizado_total / total_os * 100.0) if total_os > 0 else 0.0

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
col_kpi1.metric("📋 Planejado (OS)", f"{total_os}")
col_kpi2.metric("🔴 Backlog (Não Realizado)", f"{nao_realizado}", delta=f"{nao_realizado}", delta_color="inverse")
col_kpi3.metric("🟢 Realizado (Total)", f"{realizado_total}", delta=f"{realizado_prazo} no prazo / {realizado_atraso} atrasado")
col_kpi4.metric("📈 Taxa de Conclusão", f"{taxa_conclusao:.1f}%")

st.markdown("---")
#endregion

#endregion

#region SESSÃO 7: Abas (Visão Gerencial + Campo) + Pendentes/Abertas
# ==========================================

#region SESSÃO 7.1: Lógica das abas + Pendentes/Abertas
tab1, tab2 = st.tabs([
    "📊 Visão Gerencial (Indicadores)",
    "🗺️ Roteirização e Mapa de Campo"
])

# Criação do DataFrame exclusivo para o Mapa (Aba 2) - apenas OS Pendentes
_status_aberto_mapa = {"NÃO REALIZADO", "NAO REALIZADO", "PENDENTE", ""}

# Filtra as pendentes aproveitando o Status_norm já criado na Sessão 6
# (Removemos o .drop() antigo que apagava a coluna e quebrava os gráficos)
df_pendentes_f = df_filtrado[df_filtrado["Status_norm"].isin(_status_aberto_mapa)].copy()
#endregion

#region SESSÃO 7.2: Conteúdo da Aba 1 (Visão Gerencial)
# ==========================================

with tab1:
    #region SESSÃO 7.2.1: Preparação e KPIs Resumo
    st.subheader("📊 Visão Gerencial ")
    
    # Como transferimos tudo para a Sidebar, a base visual é exatamente a base filtrada
    df_visao_base = df_filtrado.copy()
    
    total_planejado      = len(df_visao_base)
    qtd_realizado_prazo  = int(df_visao_base["Status_norm"].isin(_status_prazo).sum())
    qtd_realizado_atraso = int(df_visao_base["Status_norm"].isin(_status_atraso).sum())
    qtd_nao_realizado    = int(df_visao_base["Status_norm"].isin(_status_aberto).sum())
    qtd_realizadas_total = qtd_realizado_prazo + qtd_realizado_atraso

    taxa_conclusao = (
        round((qtd_realizadas_total / total_planejado) * 100.0, 1)
        if total_planejado > 0 else 0.0
    )

    if taxa_conclusao <= 25:
        gauge_color = "#DC2626"
    elif taxa_conclusao <= 50:
        gauge_color = "#F59E0B"
    elif taxa_conclusao <= 80:
        gauge_color = "#16A34A"
    else:
        gauge_color = "#2563EB"
    #endregion

    #region SESSÃO 7.2.2: Camada 1 (Gauge, Rosca, Área)
    with st.expander("Resumo", expanded=True):
        col_g1, col_g2, col_g5 = st.columns(3)

        with col_g1:
            st.markdown("#### Realizado x Planejado")
            st.caption("Taxa de Conclusão")

            gauge_options = {
                "tooltip": {"formatter": "{a} <br/>{b}: {c}%"},
                "series": [
                    {
                        "name": "Conclusão", "type": "gauge", "min": 0, "max": 100, "radius": "90%",
                        "progress": {"show": True, "width": 14, "itemStyle": {"color": gauge_color}},
                        "axisLine": {
                            "lineStyle": {
                                "width": 14,
                                "color": [[0.25, "#DC2626"], [0.50, "#F59E0B"], [0.80, "#16A34A"], [1.00, "#2563EB"]],
                            }
                        },
                        "pointer": {"show": True, "length": "60%", "width": 6},
                        "itemStyle": {"color": gauge_color},
                        "anchor": {"show": True, "showAbove": True, "size": 10, "itemStyle": {"color": gauge_color}},
                        "title": {"show": True, "offsetCenter": [0, "70%"], "fontSize": 14},
                        "detail": {
                            "valueAnimation": True, "offsetCenter": [0, "40%"],
                            "formatter": f"{taxa_conclusao}%\n{qtd_realizadas_total} / {total_planejado}", "fontSize": 16,
                        },
                        "data": [{"value": taxa_conclusao, "name": "Realizado"}],
                    }
                ],
            }

            st_echarts(options=gauge_options, height="350px", theme="streamlit", key="aba1_gauge_v5")

        with col_g2:
            st.markdown("#### Distribuição por Status")
            st.caption("Visão da situação das OS ")

            rosca_options = {
                "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                "legend":  {"orient": "horizontal", "bottom": "0%"},
                "series": [{
                    "name": "Status", "type": "pie", "radius": ["35%", "60%"],
                    "data": [
                        {"value": qtd_realizado_prazo, "name": "Realizado no Prazo", "itemStyle": {"color": "#16A34A"}},
                        {"value": qtd_realizado_atraso, "name": "Realizado Atrasado", "itemStyle": {"color": "#F59E0B"}},
                        {"value": qtd_nao_realizado, "name": "Pendentes", "itemStyle": {"color": "#DC2626"}},
                    ],
                    "label": {
                        "show": True, "position": "inside", "formatter": "{c}\n({d}%)",
                        "color": "#FFFFFF", "fontWeight": "bold"
                    },
                }],
            }

            st_echarts(options=rosca_options, height="350px", theme="streamlit", key="aba1_rosca_v5")

        with col_g5:
            st.markdown("#### Plan x Real - Acumulado")
            st.caption("Evolução diária das Ordens de Serviço.")

            df_area = df_visao_base.copy()
            df_area["dia_programado"] = pd.to_datetime(df_area["Data inicial programada"], errors="coerce").dt.normalize()
            realizado_diario_a = (
                df_area[df_area["Status_norm"].isin(_status_prazo | _status_atraso)]
                .groupby("dia_realizado").size().rename("Realizado_Dia")
            )
            planejado_diario_a = df_area.groupby("dia_programado").size().rename("Planejado_Dia")

            _datas_a = pd.Index([])
            if len(realizado_diario_a.index) > 0:
                _datas_a = _datas_a.union(realizado_diario_a.index)
            if len(planejado_diario_a.index) > 0:
                _datas_a = _datas_a.union(planejado_diario_a.index)

            if len(_datas_a) == 0:
                st.info("Sem datas suficientes para o gráfico de área.")
            else:
                _idx_da   = pd.date_range(start=_datas_a.min(), end=_datas_a.max(), freq="D")
                _real_acum = realizado_diario_a.reindex(_idx_da, fill_value=0).cumsum()
                _plan_acum = planejado_diario_a.reindex(_idx_da, fill_value=0).cumsum()
                _xlabels_a = [d.strftime("%d/%m") for d in _idx_da]

                area_options = {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"top": "bottom"},
                    "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "10%", "containLabel": True},
                    "xAxis": {"type": "category", "data": _xlabels_a},
                    "yAxis": {"type": "value"},
                    "series": [
                        {"name": "Realizado Acumulado", "type": "line", "smooth": True, "data": _real_acum.tolist(),
                         "areaStyle": {"color": "rgba(37,99,235,0.28)"}, "lineStyle": {"color": "#2563EB", "width": 3}, "itemStyle": {"color": "#2563EB"}},
                        {"name": "Planejado Acumulado", "type": "line", "smooth": True, "data": _plan_acum.tolist(),
                         "lineStyle": {"color": "#F59E0B", "width": 3}, "itemStyle": {"color": "#F59E0B"}},
                    ],
                }

                st_echarts(options=area_options, height="350px", theme="streamlit", key="aba1_area_v5")
    #endregion

    #region SESSÃO 7.2.3: Camada 2 (HeatMap)
    with st.expander("Concentração por Criticidade e Classificação", expanded=True):
        st.markdown("#### % Realizado por Criticidade e Classificação")
        
        df_heat = df_visao_base.copy()
        df_heat["Realizada_flag"] = df_heat["Status_norm"].isin(_status_prazo | _status_atraso)
        agg = df_heat.groupby(["Classificacao", "Criticidade"], as_index=False).agg(
            Total_OS=("Ordem servico", "count"),
            Realizadas=("Realizada_flag", "sum")
        )
        agg["Pct_Realizado"] = np.where(agg["Total_OS"] > 0, (agg["Realizadas"] / agg["Total_OS"]) * 100.0, 0.0)

        ordem_class = ["Confiabilidade e Segurança", "Segurança", "Confiabilidade"]
        ordem_crit  = ["Muito Alta", "Alta", "Média", "Baixa"]

        if agg.empty:
            st.info("Sem dados suficientes para o HeatMap nos filtros atuais.")
        else:
            heat_data = []
            for _yi, _cls in enumerate(ordem_class):
                for _xi, _crt in enumerate(ordem_crit):
                    _row = agg[(agg["Classificacao"] == _cls) & (agg["Criticidade"] == _crt)]
                    _pct = float(_row["Pct_Realizado"].iloc[0]) if not _row.empty else 0.0
                    heat_data.append([_xi, _yi, round(_pct, 1)])

            heatmap_options = {
                "tooltip": {"position": "top", "formatter": JsCode("function(p){return p.value[2]+'%';}")},
                "grid": {"height": "65%", "top": "10%", "containLabel": True},
                "xAxis": {"type": "category", "data": ordem_crit,  "splitArea": {"show": True}},
                "yAxis": {"type": "category", "data": ordem_class, "splitArea": {"show": True}},
                "visualMap": {
                    "type": "piecewise", "orient": "horizontal", "left": "center", "bottom": "3%",
                    "pieces": [
                        {"min": 0,  "max": 25,  "label": "0-25%",  "color": "#DC2626"},
                        {"gt": 25,  "max": 50,  "label": "25-50%", "color": "#F59E0B"},
                        {"gt": 50,  "max": 80,  "label": "50-80%", "color": "#16A34A"},
                        {"gt": 80,  "max": 100, "label": ">80%",   "color": "#2563EB"},
                    ],
                },
                "series": [{
                    "name": "% Realizado", "type": "heatmap", "data": heat_data,
                    "label": {"show": True, "formatter": JsCode("function(p){return p.value[2]+'%';}")},
                }],
            }

            st_echarts(options=heatmap_options, height="380px", theme="streamlit", key="aba1_heatmap_v5")
    #endregion

    #region SESSÃO 7.2.4: Camada 3 (Barra e Linhas)
    with st.expander("Execução por Turno e Acumulado", expanded=True):
        col_g3, col_g6 = st.columns(2)

        with col_g3:
            st.markdown("#### Realizado por Turno")
            
            df_barra_real = df_visao_base[df_visao_base["Status_norm"].isin(_status_prazo | _status_atraso)].copy()
            x_turnos = ["00h-07h", "07h-16h", "16h-00h"]
            _cnt_t   = df_barra_real.groupby("Turno").size()
            y_vals   = [int(_cnt_t.get(t, 0)) for t in x_turnos]

            _cor_turno = {"00h-07h": "#2563EB", "07h-16h": "#7C3AED", "16h-00h": "#16A34A"}

            barra_options = {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "10%", "containLabel": True},
                "xAxis": {"type": "category", "data": x_turnos},
                "yAxis": {"type": "value"},
                "series": [{
                    "type": "bar", "barWidth": "55%",
                    "label": {"show": True, "position": "inside", "formatter": "{c}", "color": "#FFFFFF", "fontWeight": "bold"},
                    "data": [{"value": v, "name": t, "itemStyle": {"color": _cor_turno.get(t, "#94A3B8")}} for t, v in zip(x_turnos, y_vals)],
                }],
            }

            st_echarts(options=barra_options, height="350px", theme="streamlit", key="aba1_barra_v5")

        with col_g6:
            st.markdown("#### Realizado Acumulado por Turno")
            
            df_linhas_plot = df_visao_base.dropna(subset=["dia_realizado"]).copy()

            if df_linhas_plot.empty:
                st.info("Ainda não há registros de realização para o gráfico de linhas.")
            else:
                _ordem_t  = ["00h-07h", "07h-16h", "16h-00h"]
                _cores_t  = {"00h-07h": "#2563EB", "07h-16h": "#7C3AED", "16h-00h": "#16A34A"}
                _idx_dt   = pd.date_range(start=df_linhas_plot["dia_realizado"].min(), end=df_linhas_plot["dia_realizado"].max(), freq="D")
                _xlabels_t      = [d.strftime("%d/%m") for d in _idx_dt]

                _series_t = []
                for _t in _ordem_t:
                    _s = (df_linhas_plot[df_linhas_plot["Turno"] == _t].groupby("dia_realizado").size().reindex(_idx_dt, fill_value=0).cumsum())
                    _series_t.append({
                        "name": _t, "type": "line", "smooth": True, "data": _s.tolist(),
                        "lineStyle": {"color": _cores_t[_t], "width": 3}, "itemStyle": {"color": _cores_t[_t]},
                    })

                linhas_options = {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"top": "bottom"},
                    "grid": {"left": "5%", "right": "5%", "bottom": "15%", "top": "10%", "containLabel": True},
                    "xAxis": {"type": "category", "data": _xlabels_t},
                    "yAxis": {"type": "value"},
                    "series": _series_t,
                }

                st_echarts(options=linhas_options, height="350px", theme="streamlit", key="aba1_linhas_v5")
    #endregion

#region SESSÃO 7.2.5: Lista Detalhada
    st.subheader("📋 Lista Detalhada de OS")

    df_lista = df_visao_base.copy().rename(columns={"Ordem servico": "OS"})
    
    # ✅ AJUSTE: Formatar as colunas de data para exibição (dd/mm/yyyy hh:mm)
    if "Data inicial programada" in df_lista.columns:
        df_lista["Data inicial programada"] = pd.to_datetime(
            df_lista["Data inicial programada"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")
        
    if "Data/Hora Realizado" in df_lista.columns:
        # Se houver dados em texto vazio ou nulo, preenche com vazio em vez de NaT
        df_lista["Data/Hora Realizado"] = pd.to_datetime(
            df_lista["Data/Hora Realizado"], errors="coerce"
        ).dt.strftime("%d/%m/%Y %H:%M").fillna("")

    colunas_ordem = [
        "OS", "Patio", "Ativo", "Criticidade", "Classificacao",
        "Descrição Longa", "Data inicial programada",
        "Status da Operação", "Data/Hora Realizado",
    ]
    
    for c in colunas_ordem:
        if c not in df_lista.columns:
            df_lista[c] = ""

    if df_lista.empty:
        st.info("Nenhuma OS encontrada com os filtros atuais.")
    else:
        # 1. Filtramos apenas as colunas na ordem correta
        df_exibir = df_lista[colunas_ordem]
        
        # 2. Aplicamos o estilo para centralizar o conteúdo das células e dos cabeçalhos (th)
        df_styled = df_exibir.style.set_properties(**{'text-align': 'center'}) \
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            
        # 3. Exibimos a tabela com o estilo aplicado e sem a coluna de índice
        st.dataframe(df_styled, use_container_width=True, height=420, hide_index=True)

    #endregion

#region SESSÃO 7.3: Conteúdo da Aba 2        
with tab2:
    #region SESSÃO 7.3.1: Layout base da Aba 2
    col_mapa, col_acao = st.columns([1, 2])

    # Garantia: df_recomendado existe para a Sessão 9 (mapa)
    df_recomendado = pd.DataFrame()
    #endregion

    with col_acao:

        #region SESSÃO 7.3.2: Estados iniciais da origem e GPS
        st.subheader("🚀 Localização da Equipe de Campo")

        if "lat_partida" not in st.session_state:
            st.session_state["lat_partida"] = COORDENADAS_FIXAS["ICG"][0]
            st.session_state["lon_partida"] = COORDENADAS_FIXAS["ICG"][1]
            st.session_state["local_nome"] = "Campo Grande (ICG)"

        if "gps_ok" not in st.session_state:
            st.session_state["gps_ok"] = False
        if "gps_msg" not in st.session_state:
            st.session_state["gps_msg"] = ""
        if "accuracy_m" not in st.session_state:
            st.session_state["accuracy_m"] = None

        if "gps_pending" not in st.session_state:
            st.session_state["gps_pending"] = False
        if "gps_pending_start" not in st.session_state:
            st.session_state["gps_pending_start"] = 0.0
        if "gps_pending_tries" not in st.session_state:
            st.session_state["gps_pending_tries"] = 0

        GPS_POLL_MAX_SECONDS = 12.0
        GPS_POLL_SLEEP = 0.8
        GPS_POLL_MAX_TRIES = 15
        #endregion

        #region SESSÃO 7.4: Botões de GPS / Base fixa
        st.markdown("### 📍 GPS (Somente ao clicar)")
        st.caption("Clique em **Minha Localização** para solicitar sua localização ao navegador.")

        cbtn1, cbtn2 = st.columns(2)
        with cbtn1:
            clicar_gps = st.button("📍 Minha Localização", use_container_width=True)
        with cbtn2:
            usar_base = st.button("🏠 Usar Base Campo Grande", use_container_width=True)

        if usar_base:
            st.session_state["lat_partida"] = COORDENADAS_FIXAS["ICG"][0]
            st.session_state["lon_partida"] = COORDENADAS_FIXAS["ICG"][1]
            st.session_state["local_nome"] = "Campo Grande (ICG)"
            st.session_state["gps_ok"] = False
            st.session_state["gps_msg"] = "Base definida manualmente."
            st.session_state["accuracy_m"] = None

            st.session_state["gps_pending"] = False
            st.session_state["gps_pending_start"] = 0.0
            st.session_state["gps_pending_tries"] = 0

            st.toast("Base definida: Campo Grande (ICG)")
            st.rerun()

        if clicar_gps:
            st.session_state["gps_pending"] = True
            st.session_state["gps_pending_start"] = time.time()
            st.session_state["gps_pending_tries"] = 0
            st.session_state["gps_msg"] = "Solicitação enviada. Aguardando resposta do navegador…"
        #endregion

        #region SESSÃO 7.4.1: Polling para resposta do navegador (GPS)
        if st.session_state["gps_pending"]:
            elapsed = time.time() - st.session_state["gps_pending_start"]

            if st.session_state["gps_pending_tries"] < GPS_POLL_MAX_TRIES and elapsed < GPS_POLL_MAX_SECONDS:
                ok, lat_gps, lon_gps, msg_gps, acc = tentar_gps_uma_vez()
                st.session_state["gps_pending_tries"] += 1

                if ok:
                    st.session_state["gps_ok"] = True
                    st.session_state["lat_partida"] = lat_gps
                    st.session_state["lon_partida"] = lon_gps
                    st.session_state["local_nome"] = "Localização via GPS"
                    st.session_state["accuracy_m"] = acc
                    st.session_state["gps_msg"] = "GPS OK."
                    st.session_state["gps_pending"] = False
                else:
                    st.session_state["gps_msg"] = msg_gps or "Aguardando resposta do navegador…"

                    if isinstance(msg_gps, str) and "GPS falhou" in msg_gps:
                        st.session_state["gps_pending"] = False
                        st.session_state["gps_ok"] = False

                    if st.session_state["gps_pending"]:
                        st.info("📡 Aguardando… se aparecer o pop-up do navegador, permita e aguarde alguns segundos.")
                        time.sleep(GPS_POLL_SLEEP)
                        st.rerun()
            else:
                st.session_state["gps_pending"] = False
                if not st.session_state["gps_ok"]:
                    st.session_state["gps_msg"] = "Tempo esgotado aguardando o navegador. Clique em 'Minha Localização' novamente."
        #endregion

        #region SESSÃO 7.4.2: Feedback visual do GPS
        if st.session_state["gps_ok"]:
            if st.session_state["accuracy_m"] is not None:
                st.success(f"📍 GPS OK ✅ (precisão ~ {st.session_state['accuracy_m']:.0f} m)")
            else:
                st.success("📍 GPS OK ✅")
        else:
            if st.session_state["gps_msg"]:
                st.warning(f"⚠️ {st.session_state['gps_msg']}")
            else:
                st.info("Clique em **Minha Localização** para usar o GPS, ou use o fallback por endereço.")
        #endregion

        #region SESSÃO 7.5: Fallback por endereço
        with st.expander("⌨️ Digitar Endereço / Cidade (Fallback)", expanded=False):
            endereco_digitado = st.text_input(
                "Digite rua/bairro/cidade/ponto de referência:",
                placeholder="Ex: Guarulhos, SP ou Avenida Paulista, São Paulo"
            )

            if endereco_digitado:
                try:
                    loc = geocode_endereco(endereco_digitado)
                    if loc:
                        st.session_state["lat_partida"] = loc.latitude
                        st.session_state["lon_partida"] = loc.longitude
                        st.session_state["local_nome"] = endereco_digitado
                        st.session_state["gps_ok"] = False
                        st.session_state["accuracy_m"] = None
                        st.success(f"📍 Localizado: {loc.address}")
                    else:
                        st.error("❌ Endereço não encontrado.")
                except Exception:
                    st.warning("⚠️ Servidor de mapas ocupado.")
        #endregion

        #region SESSÃO 7.6: Definição de raio e origem
        raio_busca_km = st.slider(
            "📏 Definir Raio de Atuação Visual (km):",
            min_value=0,
            max_value=50,
            value=10,
            step=5
        )
        st.session_state["raio_busca_km"] = float(raio_busca_km)

        lat_origem = float(st.session_state["lat_partida"])
        lon_origem = float(st.session_state["lon_partida"])

        st.caption(
            f"📌 Origem: **{st.session_state['local_nome']}** | "
            f"Lat {lat_origem:.6f} | Lon {lon_origem:.6f}"
        )
        #endregion

        #region SESSÃO 7.7: Cálculo de rotas por raio
        if not df_pendentes_f.empty:
            df_calc = df_pendentes_f.copy()

            df_calc["lat_patio"] = df_calc["Patio"].map(
                lambda p: COORDENADAS_FIXAS.get(str(p), [np.nan, np.nan])[0]
            )
            df_calc["lon_patio"] = df_calc["Patio"].map(
                lambda p: COORDENADAS_FIXAS.get(str(p), [np.nan, np.nan])[1]
            )

            sem_coord = df_calc[df_calc["lat_patio"].isna() | df_calc["lon_patio"].isna()]
            if not sem_coord.empty:
                patios_faltantes = sorted(sem_coord["Patio"].dropna().astype(str).unique().tolist())
                st.warning(
                    f"⚠️ {len(sem_coord)} OS sem distância (pátio sem coordenada). "
                    f"Pátios: {', '.join(patios_faltantes) if patios_faltantes else '(não identificado)'}"
                )

            com_coord = df_calc.dropna(subset=["lat_patio", "lon_patio"]).copy()

            if not com_coord.empty:
                com_coord["Distancia_km"] = haversine_vectorized(
                    lat_origem,
                    lon_origem,
                    com_coord["lat_patio"],
                    com_coord["lon_patio"]
                )

                df_no_raio = com_coord[
                    com_coord["Distancia_km"] <= st.session_state["raio_busca_km"]
                ].copy()

                df_recomendado = df_no_raio.sort_values(
                    by=["Nivel_Prioridade", "Distancia_km"]
                )
            else:
                df_recomendado = pd.DataFrame()

            st.write(
                f"**🎯 Rotas recomendadas dentro do raio de {st.session_state['raio_busca_km']:.0f} km:** "
                f"{len(df_recomendado)} OS"
            )
        else:
            st.success("✅ Nenhuma OS pendente localizada nos filtros atuais.")
            df_recomendado = pd.DataFrame()
        #endregion

        #region SESSÃO 7.8: Lista de OS recomendadas
        if not df_recomendado.empty:
            df_exib = df_recomendado.copy()
            df_exib["Distancia_km"] = df_exib["Distancia_km"].apply(lambda x: f"{x:.2f} km")

            st.dataframe(
                df_exib[["Ordem servico", "Patio", "Classificacao", "Criticidade", "Distancia_km"]].head(10),
                use_container_width=True
            )
        elif not df_pendentes_f.empty:
            st.info("Nenhuma OS pendente encontrada dentro do raio selecionado.")
        #endregion

        #region SESSÃO 7.9: Dar baixa em OS
        if not df_recomendado.empty:
            st.markdown("---")
            st.subheader("✅ Dar Baixa em OS (sessão atual)")

            os_selecionada = st.selectbox(
                "Escolha a OS concluída:",
                df_recomendado["Ordem servico"].astype(str).tolist()
            )

            if st.button("Confirmar Execução de Campo", use_container_width=True):
                realizado_em_dt = agora_dt()
                realizado_em_str = formatar_dt_br(realizado_em_dt)

                mask = (
                    st.session_state["df_os"]["Ordem servico"].astype(str)
                    == str(os_selecionada)
                )

                serie_data = st.session_state["df_os"].loc[mask, "Data inicial programada"]
                data_prog = serie_data.iloc[0] if len(serie_data) > 0 else pd.NaT

                novo_status = determinar_status_execucao(data_prog, realizado_em_dt)

                # Persistência
                upsert_baixa(str(os_selecionada), novo_status, realizado_em_str)

                # Atualiza DF em memória
                st.session_state["df_os"].loc[mask, "Status da Operação"] = novo_status
                st.session_state["df_os"].loc[mask, "Data/Hora Realizado"] = realizado_em_str

                st.toast(f"OS {os_selecionada}: {novo_status} ✅")
                st.rerun()
        #endregion

        #region SESSÃO 7.10: Configuração final da aba (enquadrar pontos)
        st.session_state["enquadrar_pontos"] = st.checkbox(
            "📌 Enquadrar pontos automaticamente (opcional)",
            value=False
        )
        #endregion

#endregion

#region SESSÃO 8: Mapa (Folium) - SP Limitado + Auto-Zoom Inteligente#region SESSÃO 9apa (Folium) - SP Limitado + Auto-Zoom Inteligente
# ==========================================
# SESSÃO SESSÃO 8: Mapa (Folium) - SP Limitado + Auto-Zoom Inteligente#region SESSÃO 9apa (Folium) - SP Limitado + Auto-Zoom Inteligente
# ==========================================

with tab2:
    with col_mapa:

        #region SESSÃO 8.1: Cabeçalho e leitura dos estados base
        st.subheader("🗺️ Distribuição Geográfica (SP - foco na origem/OS/raio)")

        lat_origem = float(st.session_state.get("lat_partida", COORDENADAS_FIXAS["ICG"][0]))
        lon_origem = float(st.session_state.get("lon_partida", COORDENADAS_FIXAS["ICG"][1]))
        raio_km = float(st.session_state.get("raio_busca_km", 10.0))
        enquadrar_auto = bool(st.session_state.get("enquadrar_pontos", False))
        #endregion

        #region SESSÃO 8.2: Limites do Estado de São Paulo
        # Bounding box aproximado do Estado de São Paulo
        SP_MIN_LAT, SP_MAX_LAT = -25.50, -19.50
        SP_MIN_LON, SP_MAX_LON = -53.50, -44.00
        #endregion

        #region SESSÃO 8.3: Zoom inicial de fallback
        if raio_km <= 5:
            zoom_start = 14
        elif raio_km <= 10:
            zoom_start = 13
        elif raio_km <= 20:
            zoom_start = 12
        elif raio_km <= 30:
            zoom_start = 11
        else:
            zoom_start = 10
        #endregion

        #region SESSÃO 8.4: Criação do mapa base
        mapa = folium.Map(
            location=[lat_origem, lon_origem],
            zoom_start=zoom_start,
            control_scale=True,
            max_bounds=True,
            min_lat=SP_MIN_LAT,
            max_lat=SP_MAX_LAT,
            min_lon=SP_MIN_LON,
            max_lon=SP_MAX_LON,
        )
        #endregion

        #region SESSÃO 8.5: Origem da equipe + círculo do raio
        folium.Marker(
            [lat_origem, lon_origem],
            popup=f"Origem: {st.session_state.get('local_nome', 'Origem')}",
            icon=folium.Icon(color="red", icon="play")
        ).add_to(mapa)

        folium.Circle(
            location=[lat_origem, lon_origem],
            radius=raio_km * 1000.0,
            color="blue",
            weight=2,
            fill=True,
            fill_color="blue",
            fill_opacity=0.06
        ).add_to(mapa)
        #endregion

        #region SESSÃO 8.6: Inclusão das OS recomendadas no mapa
        lats = [lat_origem]
        lons = [lon_origem]

        if "df_recomendado" in locals() and isinstance(df_recomendado, pd.DataFrame) and not df_recomendado.empty:
            for _, row in df_recomendado.iterrows():
                patio = str(row["Patio"])

                if patio in COORDENADAS_FIXAS:
                    lat_p, lon_p = COORDENADAS_FIXAS[patio]

                    folium.Marker(
                        [lat_p, lon_p],
                        popup=f"OS: {row['Ordem servico']} | Pátio: {patio}",
                        icon=folium.Icon(color="blue", icon="info-sign")
                    ).add_to(mapa)

                    lats.append(float(lat_p))
                    lons.append(float(lon_p))
        #endregion

        #region SESSÃO 8.7: Envelope aproximado do raio em graus
        # 1 grau de latitude ~ 111 km
        # longitude depende do cos(latitude)
        if raio_km > 0:
            delta_lat = raio_km / 111.0
            cos_lat = max(np.cos(np.radians(lat_origem)), 0.2)  # evita divisão por quase zero
            delta_lon = raio_km / (111.0 * cos_lat)

            lats.extend([lat_origem + delta_lat, lat_origem - delta_lat])
            lons.extend([lon_origem + delta_lon, lon_origem - delta_lon])
        #endregion

        #region SESSÃO 8.8: Clipping dos bounds finais dentro de SP
        sw_lat = max(min(lats), SP_MIN_LAT)
        sw_lon = max(min(lons), SP_MIN_LON)
        ne_lat = min(max(lats), SP_MAX_LAT)
        ne_lon = min(max(lons), SP_MAX_LON)
        #endregion

        #region SESSÃO 8.9: Auto-enquadramento inteligente
        # Se o usuário marcar "enquadrar pontos", aplica fit_bounds
        # Caso contrário, mantém o centro na origem com zoom fallback
        if enquadrar_auto:
            mapa.fit_bounds([[sw_lat, sw_lon], [ne_lat, ne_lon]])
        #endregion

        #region SESSÃO 8.10: Renderização final do mapa
        st_folium(
            mapa,
            width=500,
            height=520,
            key="mapa_operacional"
        )
        #endregion

#endregion
# ==========================================
