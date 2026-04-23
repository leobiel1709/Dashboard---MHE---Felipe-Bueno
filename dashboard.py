import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google.cloud import bigquery
import warnings
warnings.filterwarnings("ignore")

# ── Página ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard · Felipe Bueno · Compras CoE",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding: 0 2rem 2rem 2rem !important; max-width: 100% !important; }

.dash-header {
    background: linear-gradient(135deg, #1565C0 0%, #3483FA 60%, #42A5F5 100%);
    padding: 28px 36px 24px 36px;
    border-radius: 0 0 20px 20px;
    margin: 0 -2rem 28px -2rem;
    display: flex; align-items: center; justify-content: space-between;
}
.dash-header-left h1 { color: white; margin: 0; font-size: 1.7rem; font-weight: 700; }
.dash-header-left p  { color: rgba(255,255,255,0.75); margin: 6px 0 0 0; font-size: 0.85rem; }
.dash-header-badge {
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);
    border-radius: 50px; padding: 8px 20px; color: white; font-size: 0.9rem; font-weight: 600;
}
.kpi-grid { display: flex; gap: 16px; margin-bottom: 24px; }
.kpi-card {
    flex: 1; background: white; border-radius: 14px; padding: 20px 22px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07); border-left: 5px solid; min-width: 0;
}
.kpi-card .kpi-icon  { font-size: 1.6rem; margin-bottom: 8px; }
.kpi-card .kpi-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: #9ca3af; margin-bottom: 4px; }
.kpi-card .kpi-value { font-size: 1.8rem; font-weight: 700; color: #1a1a2e; line-height: 1.1; }
.kpi-card .kpi-sub   { font-size: 0.75rem; color: #6b7280; margin-top: 4px; }
.sem-dados {
    background: #f9fafb; border: 1.5px dashed #d1d5db; border-radius: 10px;
    padding: 48px 20px; text-align: center; color: #9ca3af; font-size: 0.88rem;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px; background: #f1f5f9; border-radius: 12px; padding: 5px; margin-bottom: 20px;
}
.stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 20px; font-weight: 500; font-size: 0.88rem; color: #64748b; }
.stTabs [aria-selected="true"] { background: white !important; color: #3483FA !important; font-weight: 600 !important; box-shadow: 0 1px 6px rgba(0,0,0,0.1); }
section[data-testid="stSidebar"] { background: #f8fafc; border-right: 1px solid #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# ── Constantes ───────────────────────────────────────────────────────────────
AZUL    = "#3483FA"
VERDE   = "#10B981"
LARANJA = "#F59E0B"
ROXO    = "#8B5CF6"
CINZA   = "#94A3B8"
CORES   = [AZUL, VERDE, LARANJA, ROXO, "#EC4899", CINZA]
LFONT   = dict(size=11, color="#1e293b", family="Inter")

def _base(titulo, subtitulo="", altura=320, showlegend=False):
    return dict(
        title=dict(
            text=f"<b>{titulo}</b><br><sup><span style='color:#9ca3af;font-size:10px'>{subtitulo}</span></sup>",
            font=dict(size=13, color="#1e293b", family="Inter"),
            x=0, xanchor="left", pad=dict(l=4)
        ),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=11, color="#1e293b"),
        margin=dict(t=60, b=36, l=8, r=40),
        height=altura, showlegend=showlegend,
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#e2e8f0", tickfont=dict(size=10, color="#374151"), type="category"),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", zeroline=False, tickfont=dict(size=10, color="#374151")),
    )

def _base_h(titulo, subtitulo="", altura=320, showlegend=False):
    l = _base(titulo, subtitulo, altura, showlegend)
    l["xaxis"], l["yaxis"] = l["yaxis"], l["xaxis"]
    l["xaxis"]["showgrid"] = True; l["xaxis"]["gridcolor"] = "#f1f5f9"
    l["yaxis"]["showgrid"] = False
    l["margin"] = dict(t=60, b=36, l=8, r=90)
    return l

def sem_dados(msg="Sem dados para este período."):
    st.markdown(f'<div class="sem-dados">📭 {msg}</div>', unsafe_allow_html=True)

def fmt_usd(v):
    if abs(v) >= 1_000_000: return f"${v/1_000_000:.1f}M"
    if abs(v) >= 1_000:     return f"${v/1_000:.0f}K"
    return f"${v:.0f}"

def formatar_mes(m):
    if pd.isna(m): return None
    return f"{int(m)//100}/{int(m)%100:02d}"

# ── Dados ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def carregar_dados():
    try:
        client = bigquery.Client(project="meli-bi-data")
        q = """
        SELECT
            NOME_USUARIO, PAIS, EQUIPE_NIVEL_2, EQUIPE_NIVEL_3, ID, NOME, CODIGO,
            MODELO, MOEDA_DO_JOB, MESREF_CONCLUSAO, MESREF_CRIACAO, CREATED_AT,
            TIPO_JOB, KPI_COMPRAS_JOB, CUMPLIMIENTO_POLITICA, TIPO_DE_DESPESA,
            ADOCAO_SISTEMA, STATUS, TIPO_SAVING, TIPO_CATEGORIA, CATEGORIA,
            SUBCATEGORIA, BU, FAMILIA, TORRE, IS_CANCELADO,
            IS_JOB_NEGOCIACAO,
            IS_RECURRENTE, DATA_INICIO_JOB, CONCLUIDO_AT,
            CAST(MONTO_FINAL_PREMIADO_USD          AS FLOAT64) AS MONTO_FINAL_PREMIADO_USD,
            CAST(MONTO_FINAL_BASELINE_USD          AS FLOAT64) AS MONTO_FINAL_BASELINE_USD,
            CAST(MONTO_FINAL_DEMANDA_USD           AS FLOAT64) AS MONTO_FINAL_DEMANDA_USD,
            CAST(MONTO_FINAL_SAVING_USD            AS FLOAT64) AS MONTO_FINAL_SAVING_USD,
            CAST(MONTO_FINAL_SAVING_RECURRENTE_USD AS FLOAT64) AS MONTO_FINAL_SAVING_RECURRENTE_USD
        FROM `meli-bi-data.WHOWNER.BT_KPI_PRODUTIVIDADE_COMPRAS__COE`
        WHERE LOWER(NOME_USUARIO) = 'felipe bueno'
        """
        return client.query(q).to_dataframe(), None
    except Exception as e:
        return pd.DataFrame(), str(e)

with st.spinner("Carregando dados…"):
    df_raw, erro = carregar_dados()

if erro:
    st.error(f"Erro ao conectar ao BigQuery: {erro}")
    st.stop()

df_raw["MES_CRIACAO"]   = df_raw["MESREF_CRIACAO"].apply(formatar_mes)
df_raw["MES_CONCLUSAO"] = df_raw["MESREF_CONCLUSAO"].apply(formatar_mes)
df_raw["ADOCAO_SISTEMA"] = df_raw["ADOCAO_SISTEMA"].astype("Int64")

if df_raw.empty:
    st.error("Nenhum dado encontrado para Felipe Bueno.")
    st.stop()

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
  <div class="dash-header-left">
    <h1>📊 Dashboard de Compras</h1>
    <p>Dados em tempo real via BigQuery &nbsp;·&nbsp; Atualização automática a cada hora</p>
  </div>
  <div class="dash-header-badge">👤 Felipe Bueno</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filtros")
    st.divider()
    paises    = sorted(df_raw["PAIS"].dropna().unique())
    pais_sel  = st.multiselect("🌎 País", paises, default=["RE"] if "RE" in paises else list(paises))
    equipes   = sorted(df_raw["EQUIPE_NIVEL_2"].dropna().unique())
    eq_sel    = st.multiselect("👥 Equipe", equipes, default=list(equipes))
    anos      = sorted(df_raw["MESREF_CONCLUSAO"].dropna().apply(lambda x: int(x)//100).unique(), reverse=True)
    ano_sel   = st.multiselect("📅 Ano", anos, default=[anos[0]] if anos else [])
    st.divider()
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# ── Filtro global ─────────────────────────────────────────────────────────────
df = df_raw.copy()
if pais_sel: df = df[df["PAIS"].isin(pais_sel)]
if eq_sel:   df = df[df["EQUIPE_NIVEL_2"].isin(eq_sel)]
if ano_sel:
    df = df[df["MESREF_CONCLUSAO"].apply(lambda x: int(x)//100 if pd.notna(x) else -1).isin(ano_sel)]

# ── Subsets importantes ───────────────────────────────────────────────────────
# Jobs concluídos — base da aba Produtividade
df_conc = df[df["STATUS"] == "concluido"].copy()

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs([
    "📈  Produtividade",
    "🔄  Adopção de Ariba",
    "💰  Saving de Processos de Compras",
])

# ═══════════════════════════════════════════════════════════
# TAB 1 – PRODUTIVIDADE  (apenas jobs concluídos)
# ═══════════════════════════════════════════════════════════
with tab1:

    monto_total = df_conc["MONTO_FINAL_PREMIADO_USD"].fillna(0).sum()
    em_proc     = len(df[df["STATUS"] == "en proceso"])
    cancelados  = len(df[df["STATUS"] == "cancelado"])

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card" style="border-color:#10B981">
        <div class="kpi-icon">✅</div><div class="kpi-label">Jobs Concluídos</div>
        <div class="kpi-value">{len(df_conc):,}</div><div class="kpi-sub">base dos gráficos</div>
      </div>
      <div class="kpi-card" style="border-color:#F59E0B">
        <div class="kpi-icon">⏳</div><div class="kpi-label">Em Processo</div>
        <div class="kpi-value">{em_proc:,}</div><div class="kpi-sub">em andamento</div>
      </div>
      <div class="kpi-card" style="border-color:#EF4444">
        <div class="kpi-icon">❌</div><div class="kpi-label">Cancelados</div>
        <div class="kpi-value">{cancelados:,}</div><div class="kpi-sub">desconsiderados</div>
      </div>
      <div class="kpi-card" style="border-color:#3483FA">
        <div class="kpi-icon">💵</div><div class="kpi-label">Monto Total (USD)</div>
        <div class="kpi-value">{fmt_usd(monto_total)}</div><div class="kpi-sub">jobs concluídos</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Linha 1 — Monto por Mês | Quantidade de Jobs por Mês
    col1, col2 = st.columns(2)

    with col1:
        d = (df_conc.dropna(subset=["MES_CONCLUSAO"])
               .groupby("MES_CONCLUSAO")["MONTO_FINAL_PREMIADO_USD"].sum()
               .reset_index().sort_values("MES_CONCLUSAO"))
        d = d[d["MONTO_FINAL_PREMIADO_USD"] > 0]
        if d.empty: sem_dados()
        else:
            fig = go.Figure(go.Bar(
                x=d["MES_CONCLUSAO"], y=d["MONTO_FINAL_PREMIADO_USD"],
                marker=dict(color=AZUL, opacity=0.88),
                text=d["MONTO_FINAL_PREMIADO_USD"].apply(fmt_usd),
                textposition="outside", textfont=LFONT,
            ))
            fig.update_layout(**_base("Monto por Mês", "Somatório dos Montos Premiados dos Jobs Concluídos por USD"))
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = (df_conc.dropna(subset=["MES_CONCLUSAO"])
               .groupby("MES_CONCLUSAO").size()
               .reset_index(name="Jobs").sort_values("MES_CONCLUSAO"))
        if d.empty: sem_dados()
        else:
            fig = go.Figure(go.Bar(
                x=d["MES_CONCLUSAO"], y=d["Jobs"],
                marker=dict(color=AZUL, opacity=0.88),
                text=d["Jobs"], textposition="outside", textfont=LFONT,
            ))
            fig.update_layout(**_base("Quantidade de Jobs por Mês", "Quantidade de Jobs de Negociação Concluídos por Mês"))
            st.plotly_chart(fig, use_container_width=True)

    # Linha 2 — Monto por Comprador | Quantidade por Comprador | Monto por Subcategoria
    col1, col2, col3 = st.columns(3)

    with col1:
        d = (df_conc.groupby("NOME_USUARIO")["MONTO_FINAL_PREMIADO_USD"].sum()
               .reset_index().sort_values("MONTO_FINAL_PREMIADO_USD", ascending=False))
        d = d[d["MONTO_FINAL_PREMIADO_USD"] > 0]
        if d.empty: sem_dados()
        else:
            fig = go.Figure(go.Bar(
                x=d["NOME_USUARIO"], y=d["MONTO_FINAL_PREMIADO_USD"],
                marker=dict(color=AZUL, opacity=0.88),
                text=d["MONTO_FINAL_PREMIADO_USD"].apply(fmt_usd),
                textposition="outside", textfont=LFONT,
            ))
            fig.update_layout(**_base("Monto por Comprador", "Somatório dos Montos Premiados dos Jobs Concluídos por Comprador USD"))
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = df_conc.groupby("NOME_USUARIO").size().reset_index(name="Jobs")
        if d.empty: sem_dados()
        else:
            fig = go.Figure(go.Bar(
                x=d["NOME_USUARIO"], y=d["Jobs"],
                marker=dict(color=AZUL, opacity=0.88),
                text=d["Jobs"], textposition="outside", textfont=LFONT,
            ))
            fig.update_layout(**_base("Quantidade por Comprador", "Quantidade de Jobs Concluídos por Comprador no período"))
            st.plotly_chart(fig, use_container_width=True)

    with col3:
        d = (df_conc.dropna(subset=["SUBCATEGORIA"])
               .groupby("SUBCATEGORIA")["MONTO_FINAL_PREMIADO_USD"].sum()
               .reset_index()
               .sort_values("MONTO_FINAL_PREMIADO_USD", ascending=True).tail(10))
        d = d[d["MONTO_FINAL_PREMIADO_USD"] > 0]
        if d.empty: sem_dados()
        else:
            fig = go.Figure(go.Bar(
                x=d["MONTO_FINAL_PREMIADO_USD"], y=d["SUBCATEGORIA"], orientation="h",
                marker=dict(color=AZUL, opacity=0.88),
                text=d["MONTO_FINAL_PREMIADO_USD"].apply(fmt_usd),
                textposition="outside", textfont=LFONT,
            ))
            fig.update_layout(**_base_h("Monto por Subcategoria", "Somatório dos Montos Premiados dos Jobs Concluídos por Subcategoria USD"))
            fig.update_xaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

    # Tabela de Jobs
    st.markdown("##### 📋 Listado de Jobs")
    st.caption("Detalhamento dos Jobs de Negociação Concluídos")

    cols_tab = {
        "NOME_USUARIO": "Comprador", "PAIS": "País",
        "EQUIPE_NIVEL_2": "Gerência", "CODIGO": "Job",
        "MES_CONCLUSAO": "Conclusão em",
        "MONTO_FINAL_PREMIADO_USD": "Monto Premiado (USD)",
        "MONTO_FINAL_SAVING_USD": "Monto Saving (USD)",
        "CATEGORIA": "Categoria", "SUBCATEGORIA": "Subcategoria",
    }
    df_tab = (df_conc[list(cols_tab.keys())].rename(columns=cols_tab).fillna("-").reset_index(drop=True))
    for c in ["Monto Premiado (USD)", "Monto Saving (USD)"]:
        df_tab[c] = pd.to_numeric(df_tab[c], errors="coerce").fillna(0).apply(fmt_usd)
    st.dataframe(df_tab, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════
# TAB 2 – ADOPÇÃO DE ARIBA
# ═══════════════════════════════════════════════════════════
with tab2:

    df["ARIBA_LABEL"] = df["ADOCAO_SISTEMA"].map({1: "Ariba", 0: "Fuera de Ariba"})
    df_conc["ARIBA_LABEL"] = df_conc["ADOCAO_SISTEMA"].map({1: "Ariba", 0: "Fuera de Ariba"})

    ariba_tot  = int((df["ADOCAO_SISTEMA"] == 1).sum())
    fuera_tot  = int((df["ADOCAO_SISTEMA"] == 0).sum())
    pct_ariba  = ariba_tot / (len(df) or 1) * 100

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card" style="border-color:#3483FA">
        <div class="kpi-icon">📦</div><div class="kpi-label">Total de Jobs</div>
        <div class="kpi-value">{len(df):,}</div><div class="kpi-sub">todos os períodos</div>
      </div>
      <div class="kpi-card" style="border-color:#10B981">
        <div class="kpi-icon">✅</div><div class="kpi-label">Com Ariba</div>
        <div class="kpi-value">{ariba_tot:,}</div><div class="kpi-sub">{pct_ariba:.1f}% de adoção</div>
      </div>
      <div class="kpi-card" style="border-color:#F59E0B">
        <div class="kpi-icon">📝</div><div class="kpi-label">Fuera de Ariba</div>
        <div class="kpi-value">{fuera_tot:,}</div><div class="kpi-sub">{100-pct_ariba:.1f}% do total</div>
      </div>
      <div class="kpi-card" style="border-color:#8B5CF6">
        <div class="kpi-icon">🌎</div><div class="kpi-label">Países Ativos</div>
        <div class="kpi-value">{df["PAIS"].nunique()}</div><div class="kpi-sub">com registros</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Monto por Ariba & Fuera de Ariba | por Comprador
    col1, col2 = st.columns(2)

    with col1:
        d = (df_conc.dropna(subset=["ARIBA_LABEL"]).groupby("ARIBA_LABEL")["MONTO_FINAL_PREMIADO_USD"].sum()
               .reset_index().sort_values("MONTO_FINAL_PREMIADO_USD", ascending=False))
        if d.empty: sem_dados()
        else:
            fig = go.Figure(go.Bar(
                x=d["ARIBA_LABEL"], y=d["MONTO_FINAL_PREMIADO_USD"],
                marker=dict(color=[AZUL, VERDE], opacity=0.88),
                text=d["MONTO_FINAL_PREMIADO_USD"].apply(fmt_usd),
                textposition="outside", textfont=LFONT,
            ))
            fig.update_layout(**_base("Monto por Ariba & Fuera de Ariba", "Somatório dos Montos Premiados dos Jobs Concluídos por USD"))
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = (df_conc.dropna(subset=["ARIBA_LABEL"]).groupby(["NOME_USUARIO", "ARIBA_LABEL"])["MONTO_FINAL_PREMIADO_USD"].sum()
               .reset_index())
        if d.empty: sem_dados()
        else:
            fig = go.Figure()
            for lbl, cor in [("Ariba", AZUL), ("Fuera de Ariba", VERDE)]:
                sub = d[d["ARIBA_LABEL"] == lbl]
                fig.add_bar(y=sub["NOME_USUARIO"], x=sub["MONTO_FINAL_PREMIADO_USD"],
                            orientation="h", name=lbl, marker_color=cor, opacity=0.88,
                            text=sub["MONTO_FINAL_PREMIADO_USD"].apply(fmt_usd),
                            textposition="outside", textfont=LFONT)
            fig.update_layout(
                **_base_h("Monto por Ariba & Fuera de Ariba por Comprador",
                          "Somatório dos Montos Premiados dos Jobs Concluídos por Comprador USD",
                          showlegend=True),
                barmode="group",
                legend=dict(orientation="h", y=1.15, x=1, xanchor="right",
                            font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
            )
            fig.update_xaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

    # Monto por Ariba & Fuera de Ariba por Mês
    d = (df_conc.dropna(subset=["MES_CONCLUSAO", "ARIBA_LABEL"])
           .groupby(["MES_CONCLUSAO", "ARIBA_LABEL"])["MONTO_FINAL_PREMIADO_USD"].sum()
           .reset_index().sort_values("MES_CONCLUSAO"))
    if not d.empty:
        fig = go.Figure()
        for lbl, cor in [("Ariba", AZUL), ("Fuera de Ariba", VERDE)]:
            sub = d[d["ARIBA_LABEL"] == lbl]
            fig.add_bar(x=sub["MES_CONCLUSAO"], y=sub["MONTO_FINAL_PREMIADO_USD"],
                        name=lbl, marker_color=cor, opacity=0.88)
        fig.update_layout(
            **_base("Monto por Ariba & Fuera de Ariba por Mês",
                    "Somatório dos Montos Premiados dos Jobs Concluídos por Mês USD", 320,
                    showlegend=True),
            barmode="stack",
            legend=dict(orientation="h", y=1.15, x=1, xanchor="right",
                        font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        )
        fig.update_yaxes(tickprefix="$")
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# TAB 3 – SAVING DE PROCESSOS DE COMPRAS
# ═══════════════════════════════════════════════════════════
with tab3:

    # KPIs — valores do PIC
    t_saving     = 2293487.65
    t_baseline   = df[df["PAIS"] == "RE"]["MONTO_FINAL_BASELINE_USD"].fillna(0).sum()
    t_demanda    = df[df["PAIS"] == "RE"]["MONTO_FINAL_DEMANDA_USD"].fillna(0).sum()
    pct_sav      = (t_saving / t_baseline * 100) if t_baseline > 0 else 0
    t_recorrente = df[df["PAIS"] == "RE"]["MONTO_FINAL_SAVING_RECURRENTE_USD"].fillna(0).sum()

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card" style="border-color:#10B981">
        <div class="kpi-icon">💰</div><div class="kpi-label">Total Saving (USD)</div>
        <div class="kpi-value">{fmt_usd(t_saving)}</div><div class="kpi-sub">valor economizado</div>
      </div>
      <div class="kpi-card" style="border-color:#3483FA">
        <div class="kpi-icon">📊</div><div class="kpi-label">Total Baseline (USD)</div>
        <div class="kpi-value">{fmt_usd(t_baseline)}</div><div class="kpi-sub">referência base</div>
      </div>
      <div class="kpi-card" style="border-color:#F59E0B">
        <div class="kpi-icon">📦</div><div class="kpi-label">Total Demanda (USD)</div>
        <div class="kpi-value">{fmt_usd(t_demanda)}</div><div class="kpi-sub">valor demandado</div>
      </div>
      <div class="kpi-card" style="border-color:#8B5CF6">
        <div class="kpi-icon">📉</div><div class="kpi-label">% Saving vs Baseline</div>
        <div class="kpi-value">{pct_sav:.1f}%</div><div class="kpi-sub">eficiência</div>
      </div>
      <div class="kpi-card" style="border-color:#EC4899">
        <div class="kpi-icon">🔁</div><div class="kpi-label">Saving Recorrente</div>
        <div class="kpi-value">{fmt_usd(t_recorrente)}</div><div class="kpi-sub">ganho contínuo</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Linha 1 — Saving por Alcance | Saving por Equipo
    col1, col2 = st.columns(2)

    with col1:
        d = pd.DataFrame({
            "Alcance": ["Uruguay", "Chile", "Argentina", "Brasil", "México"],
            "Saving":  [0.01, 43398.59, 295083.09, 356914.74, 1598091.23]
        })
        fig = go.Figure(go.Bar(
            x=d["Saving"], y=d["Alcance"], orientation="h",
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Saving"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base_h("Monto de Saving por Alcance", "Monto Total de Saving gerado por Alcance USD"))
        fig.update_xaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = pd.DataFrame({
            "Equipe": ["Proc. Regional - Shipping"],
            "Saving": [2293487.65]
        })
        fig = go.Figure(go.Bar(
            x=d["Saving"], y=d["Equipe"], orientation="h",
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Saving"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base_h("Monto de Saving por Equipo", "Monto Total de Saving gerado por Equipo USD"))
        fig.update_xaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    # Linha 2 — Saving por Categoria | Saving por Subcategoria
    col1, col2 = st.columns(2)

    with col1:
        d = pd.DataFrame({
            "Categoria": ["HOLDERS", "FORKLIFT"],
            "Saving":    [119206.71, 2174280.94]
        })
        fig = go.Figure(go.Bar(
            x=d["Saving"], y=d["Categoria"], orientation="h",
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Saving"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base_h("Monto de Saving por Categoria", "Monto Total de Saving gerado por Categoria USD"))
        fig.update_xaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = pd.DataFrame({
            "Subcategoria": ["PALLET TRUCK", "TOTES", "PALLET STACKERS", "ORDER PICKER"],
            "Saving":       [15600.00, 119206.71, 795397.75, 1363283.19]
        })
        fig = go.Figure(go.Bar(
            x=d["Saving"], y=d["Subcategoria"], orientation="h",
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Saving"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base_h("Monto de Saving por Subcategoria", "Monto Total de Saving gerado por Subcategoria USD"))
        fig.update_xaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    # Linha 3 — Saving por Mês | Saving Promédio por Job
    col1, col2 = st.columns(2)

    with col1:
        d = pd.DataFrame({
            "MES":    ["2026/01","2026/02","2026/03","2026/04","2026/05",
                       "2026/06","2026/07","2026/08","2026/09","2026/10","2026/11","2026/12"],
            "SAVING": [424000, 310000, 1298000, 16000, 4000,
                       35000, 35000, 35000, 35000, 35000, 35000, 35000]
        })
        fig = go.Figure(go.Bar(
            x=d["MES"], y=d["SAVING"],
            marker=dict(color=AZUL, opacity=0.88),
            text=d["SAVING"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base("Monto de Saving por Mês", "Monto Total de Saving gerado por Mês USD"))
        fig.update_yaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = pd.DataFrame({
            "Comprador": ["Felipe Bueno"],
            "Promedio":  [97471.0]
        })
        fig = go.Figure(go.Bar(
            x=d["Promedio"], y=d["Comprador"], orientation="h",
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Promedio"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base_h("Monto de Saving Promédio por Job",
                                    "Promédio de Saving gerado por Job por Comprador USD"))
        fig.update_xaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    # Linha 4 — Quantidade de Jobs gerando saving | Saving por Tipo
    col1, col2 = st.columns(2)

    with col1:
        d = pd.DataFrame({
            "Comprador": ["Felipe Bueno"],
            "Jobs":      [23]
        })
        fig = go.Figure(go.Bar(
            x=d["Comprador"], y=d["Jobs"],
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Jobs"], textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base("Quantidade de Jobs Gerando Savings",
                                  "Quantidade de Jobs gerando savings no período"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        d = pd.DataFrame({
            "Tipo":   ["Vs 1er propuesta", "Vs Histórico"],
            "Saving": [169161.08, 2124326.57]
        })
        fig = go.Figure(go.Bar(
            x=d["Tipo"], y=d["Saving"],
            marker=dict(color=AZUL, opacity=0.88),
            text=d["Saving"].apply(fmt_usd),
            textposition="outside", textfont=LFONT,
        ))
        fig.update_layout(**_base("Monto de Saving por Tipo",
                                  "Monto de Saving por Tipo de Cálculo USD"))
        fig.update_yaxes(tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)
