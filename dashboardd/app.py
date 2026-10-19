"""
Dashboard Indikator Pendidikan & IPM Provinsi Jawa Timur 2025
Sumber data : lihat README (sumber resmi diisi oleh pemilik proyek)
Arsitektur  : Excel -> DuckDB (schema raw & dw, star schema) -> DuckLake -> MotherDuck -> Streamlit

Jalankan lokal : streamlit run app.py
Koneksi MotherDuck dibaca dari st.secrets["MOTHERDUCK_TOKEN"].
Jika token tidak ada, dashboard memakai data/indikator_jatim.csv (mode lokal).
"""

import os

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from peta import ambang_tiga_kelas, bangun_peta_html, muat_geojson, titik_wilayah

# ------------------------------------------------------------------
# KONFIGURASI
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Pendidikan Jawa Timur",
    page_icon="📊",
    layout="wide",
)

MD_DATABASE = "jatim_dw"                      # nama database di MotherDuck
FACT_TABLE = "fact_indikator_pendidikan"      # tabel fakta (sudah denormalisasi)
CSV_FALLBACK = os.path.join(os.path.dirname(__file__), "data", "indikator_jatim.csv")

WARNA_JENIS = {"Kota": "#2563eb", "Kabupaten": "#f59e0b"}


# ------------------------------------------------------------------
# KONEKSI DATA
# ------------------------------------------------------------------
def _ambil_token():
    try:
        return st.secrets.get("MOTHERDUCK_TOKEN")
    except Exception:
        return os.environ.get("MOTHERDUCK_TOKEN")


@st.cache_resource(show_spinner="Menghubungkan ke data warehouse…")
def get_connection():
    """Kembalikan (koneksi, sumber, nama_tabel)."""
    token = _ambil_token()
    if token:
        try:
            con = duckdb.connect(f"md:{MD_DATABASE}?motherduck_token={token}")
            con.execute(f"SELECT 1 FROM {FACT_TABLE} LIMIT 1")
            return con, "MotherDuck", FACT_TABLE
        except Exception as e:  # token salah / jaringan / versi duckdb
            st.warning(f"Gagal terhubung ke MotherDuck, beralih ke CSV lokal. Detail: {e}")

    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW {FACT_TABLE} AS SELECT * FROM read_csv_auto('{CSV_FALLBACK}')")
    return con, "CSV lokal", FACT_TABLE


@st.cache_data(ttl=600, show_spinner="Memuat data…")
def load_data():
    con, sumber, tabel = get_connection()
    # Turunan indikator dihitung di sisi DuckDB/MotherDuck
    q = f"""
    SELECT
        kabupaten_kota,
        tahun,
        CASE WHEN kabupaten_kota LIKE 'Kota %' THEN 'Kota' ELSE 'Kabupaten' END AS jenis_wilayah,
        ipm,
        rata_lama_sekolah,
        sekolah_sd, sekolah_smp, sekolah_sma,
        sekolah_sd + sekolah_smp + sekolah_sma AS total_sekolah,
        guru_sd, guru_smp, guru_sma,
        guru_sd + guru_smp + guru_sma AS total_guru,
        murid_sd, murid_smp, murid_sma,
        murid_sd + murid_smp + murid_sma AS total_murid,
        ROUND(murid_sd  / NULLIF(guru_sd, 0), 2)  AS rasio_murid_guru_sd,
        ROUND(murid_smp / NULLIF(guru_smp, 0), 2) AS rasio_murid_guru_smp,
        ROUND(murid_sma / NULLIF(guru_sma, 0), 2) AS rasio_murid_guru_sma,
        ROUND((murid_sd + murid_smp + murid_sma)
              / NULLIF(guru_sd + guru_smp + guru_sma, 0), 2) AS rasio_murid_guru,
        ROUND((murid_sd + murid_smp + murid_sma)
              / NULLIF(sekolah_sd + sekolah_smp + sekolah_sma, 0), 1) AS murid_per_sekolah,
        ROUND(100.0 * murid_sma / NULLIF(murid_sd, 0), 1) AS persen_sma_thd_sd
    FROM {tabel}
    ORDER BY kabupaten_kota
    """
    return con.execute(q).df(), sumber


df_all, SUMBER = load_data()

# ------------------------------------------------------------------
# SIDEBAR / FILTER
# ------------------------------------------------------------------
st.sidebar.header("Filter")
jenis = st.sidebar.multiselect(
    "Jenis wilayah", ["Kabupaten", "Kota"], default=["Kabupaten", "Kota"]
)
pilihan_wilayah = st.sidebar.multiselect(
    "Kabupaten/Kota (kosongkan = semua)",
    sorted(df_all["kabupaten_kota"].unique()),
)
rentang_ipm = st.sidebar.slider(
    "Rentang IPM",
    float(np.floor(df_all["ipm"].min())),
    float(np.ceil(df_all["ipm"].max())),
    (float(np.floor(df_all["ipm"].min())), float(np.ceil(df_all["ipm"].max()))),
    step=0.5,
)

df = df_all[df_all["jenis_wilayah"].isin(jenis)]
if pilihan_wilayah:
    df = df[df["kabupaten_kota"].isin(pilihan_wilayah)]
df = df[df["ipm"].between(*rentang_ipm)]

st.sidebar.markdown("---")
st.sidebar.caption(f"Sumber data: **{SUMBER}**")
st.sidebar.caption(f"Wilayah ditampilkan: **{len(df)}** dari {len(df_all)}")

# ------------------------------------------------------------------
# HEADER
# ------------------------------------------------------------------
st.title("Dashboard Indikator Pendidikan & IPM Jawa Timur 2025")
st.caption(
    "Integrasi tiga sumber data (IPM, Rata-rata Lama Sekolah, serta jumlah sekolah/guru/murid) "
    "yang dimodelkan sebagai star schema di DuckDB, disimpan di DuckLake, dan disajikan dari MotherDuck."
)

if df.empty:
    st.info("Tidak ada wilayah yang cocok dengan filter. Ubah filter di sidebar.")
    st.stop()


def fmt(n, d=0):
    s = f"{n:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------
# KPI
# ------------------------------------------------------------------
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total Sekolah", fmt(df["total_sekolah"].sum()))
k2.metric("Total Guru", fmt(df["total_guru"].sum()))
k3.metric("Total Murid", fmt(df["total_murid"].sum()))
k4.metric("Rata-rata IPM", fmt(df["ipm"].mean(), 2))
k5.metric("Rata-rata RLS (tahun)", fmt(df["rata_lama_sekolah"].mean(), 2))
k6.metric("Rasio Murid : Guru", fmt(df["total_murid"].sum() / df["total_guru"].sum(), 1))

# ------------------------------------------------------------------
# TAB
# ------------------------------------------------------------------
tab_peta, tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Peta Sebaran", "Peringkat IPM", "IPM vs Lama Sekolah", "Rasio Pendidikan", "Jenjang Pendidikan", "Data & Arsitektur"]
)


def tampilkan_html(html, tinggi):
    """Sematkan HTML mandiri. st.iframe adalah pengganti components.html (deprecated)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=tinggi)
    else:  # Streamlit versi lama
        import streamlit.components.v1 as components
        components.html(html, height=tinggi)


# --- Tab 0: peta sebaran ---
with tab_peta:
    pc1, pc2, pc3 = st.columns([2, 3, 3])
    with pc1:
        indikator = st.radio("Indikator", ["Sekolah", "Guru", "Murid"], horizontal=True, key="peta_indikator")
    with pc2:
        jenjang_peta = st.radio("Jenjang", ["Semua", "SD", "SMP", "SMA"], horizontal=True, key="peta_jenjang")
    with pc3:
        warnai_ipm = st.checkbox("Warnai wilayah menurut IPM", value=False, key="peta_warna_ipm")

    awalan = {"Sekolah": "sekolah", "Guru": "guru", "Murid": "murid"}[indikator]
    kolom_peta = f"total_{awalan}" if jenjang_peta == "Semua" else f"{awalan}_{jenjang_peta.lower()}"
    judul_peta = f"Jumlah {awalan}" + ("" if jenjang_peta == "Semua" else f" {jenjang_peta}")

    geo = muat_geojson()
    titik = titik_wilayah(geo)
    wilayah_peta = []
    for r in df.itertuples():
        if r.kabupaten_kota not in titik:
            continue
        lat, lon = titik[r.kabupaten_kota]
        wilayah_peta.append({
            "nama": r.kabupaten_kota,
            "lat": lat,
            "lon": lon,
            "nilai": int(getattr(r, kolom_peta)),
            "rincian": [
                ["IPM", fmt(r.ipm, 2)],
                ["Rata-rata lama sekolah", f"{fmt(r.rata_lama_sekolah, 2)} tahun"],
                ["Sekolah (SD/SMP/SMA)",
                 f"{fmt(r.total_sekolah)} ({fmt(r.sekolah_sd)}/{fmt(r.sekolah_smp)}/{fmt(r.sekolah_sma)})"],
                ["Guru", fmt(r.total_guru)],
                ["Murid", fmt(r.total_murid)],
                ["Murid per guru", fmt(r.rasio_murid_guru, 1)],
            ],
        })

    tampilkan_html(
        bangun_peta_html(
            wilayah_peta,
            geo,
            judul=judul_peta,
            ambang=ambang_tiga_kelas(df_all[kolom_peta]),   # ambang dari seluruh wilayah agar warna stabil saat difilter
            ipm={r.kabupaten_kota: r.ipm for r in df_all.itertuples()},
            warna_ipm=warnai_ipm,
        ),
        tinggi=620,
    )
    st.caption(
        "Satu gelembung = satu kabupaten/kota (data agregat, bukan titik lokasi sekolah). "
        "Gelembung yang berdekatan menyatu saat peta di-zoom out dan jumlahnya dijumlahkan. "
        "Batas wilayah: BPS, WFP, OCHA ROAP via geoBoundaries (CC BY 3.0 IGO). "
        "Peta dasar: OpenStreetMap contributors."
    )

# --- Tab 1: peringkat IPM ---
with tab1:
    c1, c2 = st.columns([3, 2])
    with c1:
        d = df.sort_values("ipm")
        fig = px.bar(
            d, x="ipm", y="kabupaten_kota", color="jenis_wilayah", orientation="h",
            color_discrete_map=WARNA_JENIS,
            labels={"ipm": "IPM", "kabupaten_kota": "", "jenis_wilayah": "Jenis"},
            height=max(400, 22 * len(d)),
        )
        fig.add_vline(x=df_all["ipm"].mean(), line_dash="dash", line_color="gray",
                      annotation_text=f"Rata-rata Jatim {df_all['ipm'].mean():.2f}")
        fig.update_layout(margin=dict(l=0, r=10, t=30, b=0), legend_title_text="")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("5 IPM tertinggi")
        st.dataframe(
            df.nlargest(5, "ipm")[["kabupaten_kota", "ipm", "rata_lama_sekolah"]],
            hide_index=True, width="stretch",
        )
        st.subheader("5 IPM terendah")
        st.dataframe(
            df.nsmallest(5, "ipm")[["kabupaten_kota", "ipm", "rata_lama_sekolah"]],
            hide_index=True, width="stretch",
        )
        rata_kota = df_all.loc[df_all.jenis_wilayah == "Kota", "ipm"].mean()
        rata_kab = df_all.loc[df_all.jenis_wilayah == "Kabupaten", "ipm"].mean()
        st.info(
            f"Rata-rata IPM kota **{rata_kota:.2f}** vs kabupaten **{rata_kab:.2f}** "
            f"(selisih {rata_kota - rata_kab:.2f} poin)."
        )

# --- Tab 2: hubungan IPM dan RLS ---
with tab2:
    if len(df) >= 3:
        r = df["ipm"].corr(df["rata_lama_sekolah"])
        b1, b0 = np.polyfit(df["rata_lama_sekolah"], df["ipm"], 1)
        r2 = r ** 2
    else:
        r = b1 = b0 = r2 = np.nan

    c1, c2 = st.columns([3, 1])
    with c1:
        fig = px.scatter(
            df, x="rata_lama_sekolah", y="ipm", color="jenis_wilayah",
            size="total_murid", hover_name="kabupaten_kota",
            color_discrete_map=WARNA_JENIS, size_max=40,
            labels={"rata_lama_sekolah": "Rata-rata Lama Sekolah (tahun)", "ipm": "IPM",
                    "jenis_wilayah": "Jenis", "total_murid": "Total murid"},
            height=520,
        )
        if not np.isnan(b1):
            xs = np.linspace(df["rata_lama_sekolah"].min(), df["rata_lama_sekolah"].max(), 50)
            fig.add_scatter(x=xs, y=b0 + b1 * xs, mode="lines", name="Garis regresi",
                            line=dict(color="gray", dash="dash"))
        fig.update_layout(legend_title_text="")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.metric("Korelasi Pearson (r)", "–" if np.isnan(r) else f"{r:.4f}")
        st.metric("Koefisien determinasi (R²)", "–" if np.isnan(r2) else f"{r2:.4f}")
        if not np.isnan(b1):
            st.markdown(f"**Persamaan:**  \nIPM = {b0:.2f} + {b1:.2f} × RLS")
            st.caption(
                f"Setiap tambahan 1 tahun rata-rata lama sekolah berasosiasi dengan "
                f"kenaikan IPM sekitar {b1:.2f} poin. Perlu dicatat RLS adalah salah satu "
                f"komponen penyusun IPM (dimensi pendidikan), sehingga korelasi tinggi "
                f"sebagian bersifat definisional, bukan kausal."
            )
        st.caption("Ukuran titik = total murid.")

# --- Tab 3: rasio pendidikan ---
with tab3:
    jenjang = st.radio("Jenjang", ["Semua", "SD", "SMP", "SMA"], horizontal=True)
    kolom = {"Semua": "rasio_murid_guru", "SD": "rasio_murid_guru_sd",
             "SMP": "rasio_murid_guru_smp", "SMA": "rasio_murid_guru_sma"}[jenjang]
    c1, c2 = st.columns(2)
    with c1:
        d = df.sort_values(kolom, ascending=False)
        fig = px.bar(
            d, x="kabupaten_kota", y=kolom, color="jenis_wilayah",
            color_discrete_map=WARNA_JENIS,
            labels={kolom: "Murid per guru", "kabupaten_kota": "", "jenis_wilayah": "Jenis"},
            title=f"Rasio murid per guru ({jenjang})", height=460,
        )
        fig.update_layout(xaxis_tickangle=-60, legend_title_text="")
        st.plotly_chart(fig, width="stretch")
    with c2:
        fig = px.scatter(
            df, x="murid_per_sekolah", y="ipm", color="jenis_wilayah",
            hover_name="kabupaten_kota", color_discrete_map=WARNA_JENIS,
            labels={"murid_per_sekolah": "Rata-rata murid per sekolah", "ipm": "IPM",
                    "jenis_wilayah": "Jenis"},
            title="Kepadatan sekolah vs IPM", height=460,
        )
        fig.update_layout(legend_title_text="")
        st.plotly_chart(fig, width="stretch")
    st.caption(
        "Rasio murid per guru dihitung di DuckDB: Σ murid / Σ guru. "
        "Nilai lebih tinggi berarti satu guru menangani lebih banyak murid."
    )

# --- Tab 4: jenjang ---
with tab4:
    total = pd.DataFrame({
        "Jenjang": ["SD", "SMP", "SMA"] * 3,
        "Kategori": ["Sekolah"] * 3 + ["Guru"] * 3 + ["Murid"] * 3,
        "Jumlah": [
            df.sekolah_sd.sum(), df.sekolah_smp.sum(), df.sekolah_sma.sum(),
            df.guru_sd.sum(), df.guru_smp.sum(), df.guru_sma.sum(),
            df.murid_sd.sum(), df.murid_smp.sum(), df.murid_sma.sum(),
        ],
    })
    cols = st.columns(3)
    for col, kat in zip(cols, ["Sekolah", "Guru", "Murid"]):
        with col:
            fig = px.pie(total[total.Kategori == kat], names="Jenjang", values="Jumlah",
                         hole=0.5, title=f"Komposisi {kat.lower()}",
                         color_discrete_sequence=["#2563eb", "#10b981", "#f59e0b"])
            st.plotly_chart(fig, width="stretch")

    d = df.sort_values("persen_sma_thd_sd", ascending=False)
    fig = px.bar(
        d, x="kabupaten_kota", y="persen_sma_thd_sd", color="jenis_wilayah",
        color_discrete_map=WARNA_JENIS,
        labels={"persen_sma_thd_sd": "Murid SMA / murid SD (%)", "kabupaten_kota": "",
                "jenis_wilayah": "Jenis"},
        title="Proporsi murid SMA terhadap murid SD (indikasi keberlanjutan jenjang)",
        height=440,
    )
    fig.update_layout(xaxis_tickangle=-60, legend_title_text="")
    st.plotly_chart(fig, width="stretch")

# --- Tab 5: data & arsitektur ---
with tab5:
    st.subheader("Tabel data terintegrasi")
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button(
        "Unduh CSV (sesuai filter)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="indikator_pendidikan_jatim_2025.csv",
        mime="text/csv",
    )
    st.subheader("Alur data")
    st.markdown(
        """
| Tahap | Proses | Hasil |
|---|---|---|
| 1. Extract | Membaca 3 file Excel (IPM, RLS, sekolah/guru/murid) | DataFrame pandas |
| 2. Transform | Standarisasi nama wilayah, konversi numerik, buang header & agregat provinsi | 5 tabel bersih (38 wilayah) |
| 3. Load – raw | `raw.ipm`, `raw.jumlah_sekolah`, `raw.jumlah_guru`, `raw.jumlah_murid`, `raw.rata_lama_sekolah` | DuckDB |
| 4. Load – DW | Star schema: `dim_wilayah`, `dim_tahun`, `fact_indikator_pendidikan` | DuckDB schema `dw` |
| 5. Lakehouse | Salin dimensi & fakta ke DuckLake (Parquet + katalog metadata) | `lake_jatim` |
| 6. Cloud | Publikasi ke MotherDuck | database `jatim_dw` |
| 7. Visualisasi | Streamlit membaca MotherDuck melalui DuckDB | Dashboard ini |
"""
    )
    st.caption(f"Sumber data aktif: {SUMBER}")
