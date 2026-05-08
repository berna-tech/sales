import io
import re
import unicodedata
from typing import Optional, Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Berna Uçar Satış Performans Dashboard",
    page_icon="📊",
    layout="wide",
)

PRIMARY = "#123B63"
SUCCESS = "#1F8A5B"
RISK = "#9F1239"
OPP = "#D97706"

TARGET_PERSON = "Berna Uçar"


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def format_tl(value: float) -> str:
    if pd.isna(value):
        return "-"
    abs_v = abs(float(value))
    if abs_v >= 1_000_000_000:
        return f"{value/1_000_000_000:,.1f} mlr TL".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs_v >= 1_000_000:
        return f"{value/1_000_000:,.1f} mn TL".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:,.0f} TL".replace(",", ".")


def format_pct(value: float) -> str:
    if pd.isna(value) or np.isinf(value):
        return "-"
    return f"%{value*100:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def read_excel_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    uploaded_file.seek(0)
    if name.endswith(".xlsb"):
        xls = pd.ExcelFile(uploaded_file, engine="pyxlsb")
    else:
        xls = pd.ExcelFile(uploaded_file)

    # En dolu sayfayı otomatik seç
    best_df = None
    best_score = -1
    for sheet in xls.sheet_names:
        try:
            df_try = pd.read_excel(xls, sheet_name=sheet)
            score = df_try.shape[0] * max(df_try.shape[1], 1)
            if score > best_score:
                best_df = df_try
                best_score = score
        except Exception:
            continue
    if best_df is None:
        raise ValueError("Excel okunamadı. Lütfen dosya formatını kontrol edin.")
    return best_df


def find_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    norm_cols = {col: normalize_text(col) for col in df.columns}
    for col, ncol in norm_cols.items():
        if any(k in ncol for k in keywords):
            return col
    return None


def infer_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        "date": find_col(df, ["tarih", "donem", "ay", "date"]),
        "sales_rep": find_col(df, ["satis temsilcisi", "satisci", "temsilci", "personel", "bolge sorumlusu", "musteri temsilcisi"]),
        "region": find_col(df, ["bolge", "region"]),
        "dealer": find_col(df, ["bayi", "dealer", "musteri", "cari", "unvan"]),
        "customer": find_col(df, ["musteri", "customer", "cari", "unvan"]),
        "product": find_col(df, ["urun grubu", "urun", "malzeme grubu", "kategori", "product"]),
        "actual": find_col(df, ["fiili", "gerceklesen", "gerçekleşen", "net satis", "satis tutari", "ciro", "actual"]),
        "budget": find_col(df, ["butce", "bütçe", "hedef", "target", "plan"]),
        "m2": find_col(df, ["m2", "m²", "metrekare"]),
    }


def to_numeric_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    cleaned = (
        s.astype(str)
        .str.replace("TL", "", regex=False)
        .str.replace("₺", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def prepare_data(raw: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    df = raw.copy()
    for key, col in mapping.items():
        if col and col in df.columns:
            new_col = key
            df[new_col] = df[col]
        else:
            df[key] = np.nan

    for col in ["actual", "budget", "m2"]:
        df[col] = to_numeric_series(df[col])

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if df["date"].isna().all():
            df["period"] = "Dönem Yok"
        else:
            df["period"] = df["date"].dt.to_period("M").astype(str)
    else:
        df["period"] = "Dönem Yok"

    for col in ["sales_rep", "region", "dealer", "customer", "product"]:
        df[col] = df[col].fillna("Belirtilmemiş").astype(str)

    df["rep_norm"] = df["sales_rep"].apply(normalize_text)
    df["is_berna"] = df["rep_norm"].str.contains("berna") & df["rep_norm"].str.contains("ucar")
    df["achievement"] = np.where(df["budget"] > 0, df["actual"] / df["budget"], np.nan)
    return df


def kpi_card(label: str, value: str, delta: str = ""):
    st.markdown(
        f"""
        <div style="background:white;border-radius:18px;padding:18px 20px;box-shadow:0 1px 8px rgba(15,23,42,.08);border:1px solid #E5E7EB;min-height:112px;">
            <div style="font-size:13px;color:#64748B;margin-bottom:8px;">{label}</div>
            <div style="font-size:26px;font-weight:750;color:#0F172A;line-height:1.1;">{value}</div>
            <div style="font-size:12px;color:#64748B;margin-top:8px;">{delta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def grouped_bar(df, group_col, value_col="actual", title=""):
    g = df.groupby(group_col, as_index=False)[value_col].sum().sort_values(value_col, ascending=False).head(10)
    fig = px.bar(g, x=value_col, y=group_col, orientation="h", title=title, text_auto=".2s")
    fig.update_layout(height=420, yaxis={"categoryorder":"total ascending"}, plot_bgcolor="white", paper_bgcolor="white")
    fig.update_traces(marker_color=PRIMARY)
    return fig


def budget_actual_fig(df, group_col="sales_rep", title="Bütçe vs Fiili Satış"):
    g = df.groupby(group_col, as_index=False).agg(actual=("actual", "sum"), budget=("budget", "sum"))
    g = g.sort_values("actual", ascending=False).head(12)
    long = g.melt(id_vars=group_col, value_vars=["budget", "actual"], var_name="Tip", value_name="Tutar")
    long["Tip"] = long["Tip"].replace({"budget":"Bütçe", "actual":"Fiili"})
    fig = px.bar(long, x=group_col, y="Tutar", color="Tip", barmode="group", title=title, text_auto=".2s")
    fig.update_layout(height=430, plot_bgcolor="white", paper_bgcolor="white", xaxis_tickangle=-30)
    return fig


def gauge(value_pct, title="Hedef Gerçekleşme"):
    value = 0 if pd.isna(value_pct) else min(max(value_pct * 100, 0), 150)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix":"%", "font":{"size":42}},
        title={"text": title},
        gauge={
            "axis": {"range": [0, 150]},
            "bar": {"color": PRIMARY},
            "steps": [
                {"range": [0, 80], "color": "#FEE2E2"},
                {"range": [80, 100], "color": "#FEF3C7"},
                {"range": [100, 150], "color": "#DCFCE7"},
            ],
            "threshold": {"line": {"color": RISK, "width": 4}, "thickness": 0.75, "value": 100},
        }
    ))
    fig.update_layout(height=310, margin=dict(l=20,r=20,t=50,b=10), paper_bgcolor="white")
    return fig


st.markdown("""
<style>
.block-container {padding-top: 1.3rem;}
h1, h2, h3 {color: #0F172A;}
[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Berna Uçar Satış Performans Dashboard")
st.caption("Excel yükle, dashboard otomatik güncellensin. Ana odak: Berna Uçar performansı + genel satış kıyaslaması.")

uploaded = st.sidebar.file_uploader("Excel dosyasını yükle", type=["xlsx", "xls", "xlsb"])
st.sidebar.markdown("---")
st.sidebar.info("Dosya yüklendikten sonra kolonları otomatik eşleştirir. Gerekirse aşağıdan manuel düzeltebilirsin.")

if not uploaded:
    st.info("Başlamak için sol menüden Excel dosyasını yükle.")
    st.stop()

try:
    raw_df = read_excel_file(uploaded)
except Exception as e:
    st.error(f"Dosya okunamadı: {e}")
    st.stop()

initial_mapping = infer_columns(raw_df)

with st.sidebar.expander("Kolon eşleştirme", expanded=False):
    columns = [None] + list(raw_df.columns)
    mapping = {}
    labels = {
        "date":"Tarih / Dönem", "sales_rep":"Satış Temsilcisi", "region":"Bölge", "dealer":"Bayi",
        "customer":"Müşteri", "product":"Ürün Grubu", "actual":"Fiili / Gerçekleşen Satış", "budget":"Bütçe / Hedef", "m2":"m²"
    }
    for key, label in labels.items():
        default = initial_mapping.get(key)
        idx = columns.index(default) if default in columns else 0
        mapping[key] = st.selectbox(label, columns, index=idx, key=f"map_{key}")

df = prepare_data(raw_df, mapping)

# Filters
st.sidebar.markdown("---")
st.sidebar.subheader("Filtreler")
periods = sorted([p for p in df["period"].dropna().unique()])
selected_periods = st.sidebar.multiselect("Dönem", periods, default=periods)
reps = sorted(df["sales_rep"].dropna().unique())
selected_reps = st.sidebar.multiselect("Satış Temsilcisi", reps, default=reps)
products = sorted(df["product"].dropna().unique())
selected_products = st.sidebar.multiselect("Ürün Grubu", products, default=products)

filtered = df[df["period"].isin(selected_periods) & df["sales_rep"].isin(selected_reps) & df["product"].isin(selected_products)]
berna = filtered[filtered["is_berna"]]

if filtered.empty:
    st.warning("Seçilen filtrelerle veri bulunamadı.")
    st.stop()

# KPI values
total_actual = filtered["actual"].sum(skipna=True)
total_budget = filtered["budget"].sum(skipna=True)
achievement = total_actual / total_budget if total_budget else np.nan
berna_actual = berna["actual"].sum(skipna=True)
berna_budget = berna["budget"].sum(skipna=True)
berna_ach = berna_actual / berna_budget if berna_budget else np.nan
berna_share = berna_actual / total_actual if total_actual else np.nan
strong_product = filtered.groupby("product")["actual"].sum().sort_values(ascending=False).index[0] if filtered["actual"].notna().any() else "-"
strong_dealer = filtered.groupby("dealer")["actual"].sum().sort_values(ascending=False).index[0] if filtered["actual"].notna().any() else "-"

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Yönetici Özeti", "Berna Uçar Paneli", "Ürün & Bayi Analizi", "Öne Çıkan Satışlar", "Veri Kontrol"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Toplam Fiili Satış", format_tl(total_actual))
    with c2: kpi_card("Toplam Bütçe", format_tl(total_budget))
    with c3: kpi_card("Gerçekleşme Oranı", format_pct(achievement), "100% üzeri hedef üstü kabul edilir")
    with c4: kpi_card("Berna Uçar Satış Payı", format_pct(berna_share))

    c5, c6, c7, c8 = st.columns(4)
    with c5: kpi_card("Berna Uçar Fiili Satış", format_tl(berna_actual))
    with c6: kpi_card("Berna Uçar Gerçekleşme", format_pct(berna_ach))
    with c7: kpi_card("En Güçlü Ürün Grubu", str(strong_product))
    with c8: kpi_card("En Güçlü Bayi/Müşteri", str(strong_dealer))

    st.plotly_chart(budget_actual_fig(filtered), use_container_width=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(grouped_bar(filtered, "product", title="Ürün Grubu Bazlı Satış"), use_container_width=True)
    with col_b:
        st.plotly_chart(grouped_bar(filtered, "dealer", title="Top 10 Bayi / Müşteri"), use_container_width=True)

with tab2:
    if berna.empty:
        st.warning("Bu dosyada Berna Uçar adına eşleşen kayıt bulunamadı. Kolon eşleştirmesini veya isim yazımını kontrol et.")
    else:
        c1, c2, c3 = st.columns([1,1,1])
        with c1: kpi_card("Berna Uçar Fiili Satış", format_tl(berna_actual))
        with c2: kpi_card("Berna Uçar Bütçe", format_tl(berna_budget))
        with c3: kpi_card("Toplam Satış İçindeki Pay", format_pct(berna_share))
        col_g, col_b = st.columns([1,2])
        with col_g:
            st.plotly_chart(gauge(berna_ach, "Berna Uçar Hedef Gerçekleşme"), use_container_width=True)
        with col_b:
            st.plotly_chart(budget_actual_fig(berna, "product", "Berna Uçar: Ürün Grubu Bütçe vs Fiili"), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(grouped_bar(berna, "dealer", title="Berna Uçar Top Bayi/Müşteri"), use_container_width=True)
        with col2:
            if berna["date"].notna().any():
                trend = berna.groupby("period", as_index=False)["actual"].sum()
                fig = px.line(trend, x="period", y="actual", markers=True, title="Berna Uçar Dönemsel Satış Trendi")
                fig.update_traces(line_color=PRIMARY)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Trend grafiği için tarih/dönem kolonu gerekli.")

        st.subheader("Otomatik Yönetici Yorumu")
        if not pd.isna(berna_ach):
            if berna_ach >= 1:
                insight = "Berna Uçar seçili dönemde hedef üstü performans göstermektedir. Güçlü ürün/bayi kırılımlarının korunması ve yüksek katkılı satışların sürekliliği takip edilmelidir."
            elif berna_ach >= 0.85:
                insight = "Berna Uçar hedefe yakın performans göstermektedir. Hedef altı kalan ürün veya bayi kırılımlarında kısa vadeli takip önerilir."
            else:
                insight = "Berna Uçar seçili dönemde hedefin altında kalmaktadır. En düşük katkılı ürün/bayi alanları öncelikli aksiyon listesine alınmalıdır."
            st.success(insight)

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(grouped_bar(filtered, "product", title="Ürün Grubu Performansı"), use_container_width=True)
    with col2:
        st.plotly_chart(grouped_bar(filtered, "dealer", title="Bayi / Müşteri Performansı"), use_container_width=True)

    if mapping.get("region"):
        st.plotly_chart(grouped_bar(filtered, "region", title="Bölge Bazlı Satış"), use_container_width=True)

    st.subheader("Satış Temsilcisi Sıralaması")
    rep_table = filtered.groupby("sales_rep", as_index=False).agg(
        Fiili_Satis=("actual", "sum"),
        Butce=("budget", "sum")
    )
    rep_table["Gerceklesme_%"] = np.where(rep_table["Butce"] > 0, rep_table["Fiili_Satis"] / rep_table["Butce"], np.nan)
    st.dataframe(rep_table.sort_values("Fiili_Satis", ascending=False), use_container_width=True)

with tab4:
    st.subheader("Genel Öne Çıkan Satışlar")
    show_cols = ["sales_rep", "dealer", "customer", "product", "actual", "budget", "achievement"]
    top_sales = filtered.sort_values("actual", ascending=False).head(20)[show_cols]
    st.dataframe(top_sales, use_container_width=True)

    st.subheader("Berna Uçar Öne Çıkan Satışları")
    if berna.empty:
        st.info("Berna Uçar kaydı bulunamadı.")
    else:
        st.dataframe(berna.sort_values("actual", ascending=False).head(20)[show_cols], use_container_width=True)

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Filtrelenmiş veriyi CSV indir", csv, file_name="dashboard_filtrelenmis_veri.csv", mime="text/csv")

with tab5:
    st.subheader("Veri Kontrol Özeti")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Satır Sayısı", f"{len(raw_df):,}".replace(",", "."))
    with col2: st.metric("Kolon Sayısı", len(raw_df.columns))
    with col3: st.metric("Berna Uçar Kayıt Sayısı", len(df[df["is_berna"]]))

    st.write("**Otomatik kolon eşleştirmesi:**")
    st.json(mapping)

    st.write("**İlk 50 satır:**")
    st.dataframe(raw_df.head(50), use_container_width=True)

    missing_required = [k for k in ["sales_rep", "actual", "budget"] if not mapping.get(k)]
    if missing_required:
        st.warning("Dashboard için kritik bazı kolonlar eşleşmedi: " + ", ".join(missing_required))
    else:
        st.success("Temel dashboard kolonları eşleşti.")
