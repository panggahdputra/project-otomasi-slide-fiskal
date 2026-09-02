"""
generate_report.py

Generate laporan PDF halaman "Fiskal" langsung dari CSV hasil data_preparation.py,
TANPA Quarto/LaTeX.

Alur:
    CSV (_01_data_input/00_input_quarto)
      -> pandas (data wrangling, identik dengan logika di Market_Update_Python_version.qmd)
      -> great_tables (render tabel jadi HTML)
      -> matplotlib (render chart jadi PNG base64)
      -> disusun jadi SATU halaman HTML (layout pakai <table> HTML biasa,
         vertical-align:top, supaya rata-atas pasti konsisten di semua engine
         HTML-to-PDF, termasuk wkhtmltopdf yang dukungan flexbox-nya terbatas)
      -> wkhtmltopdf render HTML -> PDF

Cara jalankan:
    python _02_script/generate_report.py

Output:
    _03_output_pdf/{YYYYMMDD} MU Part Fiskal.pdf
"""

import base64
import io
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless, tidak butuh display
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd
from great_tables import GT, loc, style


###############################################################################
### 1. SETTING DIREKTORI
###############################################################################

project_dir = Path(__file__).resolve().parent.parent
input_quarto_dir = project_dir / "_01_data_input" / "00_input_quarto"
output_pdf_dir = project_dir / "_03_output_pdf"
output_pdf_dir.mkdir(parents=True, exist_ok=True)


###############################################################################
### 2. FUNGSI HELPER
###############################################################################

def clean_names(df):
    """Rapikan nama kolom (identik dengan versi Quarto)."""
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.replace(r"([a-z0-9])([A-Z])", r"\1_\2", regex=True)
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[^0-9a-z_]", "", regex=True)
    )
    return df


def find_wkhtmltopdf():
    """Cari wkhtmltopdf otomatis: PATH sistem dulu, baru fallback default Windows."""
    found = shutil.which("wkhtmltopdf")
    if found:
        return found
    return r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"


def fig_to_base64(fig, dpi=400):
    """Simpan matplotlib figure ke PNG di memori, kembalikan sebagai base64 string.
    Sengaja TIDAK pakai bbox_inches="tight": crop otomatis itu memotong whitespace
    secara berbeda-beda tergantung konten tiap chart (mis. legend), sehingga rasio
    aspect gambar akhir jadi tidak konsisten antar chart meskipun figsize sama.
    Dengan menyimpan persis sesuai figsize, tinggi tampilan (setelah di-scale ke
    lebar kolom HTML) jadi bisa diprediksi dan disamakan antar chart.

    NOTE resolusi: chart di sini adalah gambar PNG raster (pixel tetap), beda
    dengan tabel yang HTML/teks murni (vector, tajam di zoom berapa pun). PNG
    pasti akan mulai terlihat pecah kalau di-zoom cukup jauh -- dpi dinaikkan
    ke 400 (dari 200) supaya "titik pecahnya" jauh lebih jauh saat di-zoom."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


###############################################################################
### 3. LOAD DATA
###############################################################################

def load_data():
    fiskal_raw = (
        pd.read_csv(
            sorted(
                input_quarto_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_fiskal.csv")
            )[-1]
        )
        .pipe(clean_names)
    )

    econ1_raw = pd.read_csv(sorted(input_quarto_dir.glob("*econ1.csv"))[-1])
    econ2_raw = pd.read_csv(sorted(input_quarto_dir.glob("*econ2.csv"))[-1])
    fiskal_in_raw = pd.read_csv(sorted(input_quarto_dir.glob("*fiskal_in.csv"))[-1])
    fiskal_out_raw = pd.read_csv(sorted(input_quarto_dir.glob("*fiskal_out.csv"))[-1])
    kurs = pd.read_csv(sorted(input_quarto_dir.glob("*kurs.csv"))[-1])

    return fiskal_raw, econ1_raw, econ2_raw, fiskal_in_raw, fiskal_out_raw, kurs


###############################################################################
### 4. DATA TRANSFORM
###############################################################################

def build_data_fiskal_inout(fiskal_in_raw, fiskal_out_raw, kurs):
    kurs_map = (
        kurs
        .assign(
            Currency=lambda d: d["Currency"].astype(str).str.strip().str.upper(),
            Rupiah=lambda d: pd.to_numeric(d["Rupiah"], errors="coerce"),
        )
        [["Currency", "Rupiah"]]
    )

    today = pd.Timestamp.today()

    data_fiskal_inout = (
        fiskal_in_raw
        .assign(
            Tanggal=lambda d: pd.to_datetime(d["Tanggal"], errors="coerce"),
            Proyeksi_IN_IDR=lambda d: pd.to_numeric(
                d["Proyeksi_IN_IDR"] if "Proyeksi_IN_IDR" in d.columns else d["Proyeksi_IDR"],
                errors="coerce"
            ),
            Realisasi_IN_IDR=lambda d: pd.to_numeric(
                d["Realisasi_IN_IDR"] if "Realisasi_IN_IDR" in d.columns else d["Realisasi_IDR"],
                errors="coerce"
            ),
        )
        [["Tanggal", "Proyeksi_IN_IDR", "Realisasi_IN_IDR"]]
        .merge(
            fiskal_out_raw
            .assign(
                Currency=lambda d: d["Currency"].astype(str).str.strip().str.upper(),
                Proyeksi_OUT=lambda d: pd.to_numeric(d["Proyeksi_OUT"], errors="coerce"),
            )
            .merge(kurs_map, on="Currency", how="left")
            .assign(
                Rupiah=lambda d: d["Rupiah"].where(d["Currency"] != "IDR", 1),
                Proyeksi_OUT_IDR=lambda d: d["Proyeksi_OUT"] * d["Rupiah"],
            )
            .drop(columns=["Currency", "Proyeksi_OUT", "Rupiah"])
            .assign(
                Tanggal=lambda d: pd.to_datetime(d["Tanggal"], errors="coerce"),
                Realisasi_OUT_IDR=lambda d: pd.to_numeric(d["Realisasi_OUT_IDR"], errors="coerce"),
                Proyeksi_OUT_IDR=lambda d: pd.to_numeric(d["Proyeksi_OUT_IDR"], errors="coerce"),
            )
            .dropna(subset=["Tanggal"])
            .groupby("Tanggal", as_index=False)[["Realisasi_OUT_IDR", "Proyeksi_OUT_IDR"]]
            .sum(),
            on="Tanggal",
            how="outer"
        )
        .assign(
            Proyeksi_IN_IDR=lambda d: d["Proyeksi_IN_IDR"].where(
                ~(d["Realisasi_IN_IDR"] >= d["Proyeksi_IN_IDR"]),
                d["Realisasi_IN_IDR"],
            ),
            Proyeksi_OUT_IDR=lambda d: d["Proyeksi_OUT_IDR"].where(
                ~(d["Realisasi_OUT_IDR"] >= d["Proyeksi_OUT_IDR"]),
                d["Realisasi_OUT_IDR"],
            ),
        )
        .assign(
            Proyeksi_OUT_IDR=lambda d: -d["Proyeksi_OUT_IDR"].abs(),
            Realisasi_OUT_IDR=lambda d: -d["Realisasi_OUT_IDR"].abs(),
        )
        [[
            "Tanggal",
            "Proyeksi_IN_IDR",
            "Realisasi_IN_IDR",
            "Proyeksi_OUT_IDR",
            "Realisasi_OUT_IDR",
        ]]
        .sort_values("Tanggal")
        .reset_index(drop=True)
        .loc[
            lambda d: (
                (d["Tanggal"].dt.year == today.year)
                & (d["Tanggal"].dt.month == today.month)
            ),
            [
                "Tanggal",
                "Proyeksi_IN_IDR",
                "Realisasi_IN_IDR",
                "Proyeksi_OUT_IDR",
                "Realisasi_OUT_IDR",
            ],
        ]
        .assign(
            Proyeksi_IN_IDR=lambda d: pd.to_numeric(d["Proyeksi_IN_IDR"], errors="coerce") / 1e6,
            Realisasi_IN_IDR=lambda d: pd.to_numeric(d["Realisasi_IN_IDR"], errors="coerce") / 1e6,
            Proyeksi_OUT_IDR=lambda d: pd.to_numeric(d["Proyeksi_OUT_IDR"], errors="coerce") / 1e6,
            Realisasi_OUT_IDR=lambda d: pd.to_numeric(d["Realisasi_OUT_IDR"], errors="coerce") / 1e6,
        )
        .dropna(
            subset=[
                "Proyeksi_IN_IDR",
                "Realisasi_IN_IDR",
                "Proyeksi_OUT_IDR",
                "Realisasi_OUT_IDR",
            ],
            how="all",
        )
        .sort_values("Tanggal")
        .reset_index(drop=True)
        .copy()
    )

    return data_fiskal_inout


def build_data_fiskal_neto(fiskal_in_raw, fiskal_out_raw, kurs):
    kurs_map = (
        kurs
        .assign(
            Currency=lambda d: d["Currency"].astype(str).str.strip().str.upper(),
            Rupiah=lambda d: pd.to_numeric(d["Rupiah"], errors="coerce"),
        )
        [["Currency", "Rupiah"]]
    )

    data_fiskal_neto = (
        pd.DataFrame({
            "Tanggal": pd.date_range(
                pd.to_datetime(fiskal_in_raw["Tanggal"], errors="coerce").min(),
                pd.to_datetime(fiskal_in_raw["Tanggal"], errors="coerce").max(),
                freq="D"
            )
        })
        .merge(
            fiskal_in_raw
            .assign(
                Tanggal=lambda d: pd.to_datetime(d["Tanggal"], errors="coerce"),
                Realisasi_IN_IDR=lambda d: pd.to_numeric(
                    d["Realisasi_IN_IDR"] if "Realisasi_IN_IDR" in d.columns else d["Realisasi_IDR"],
                    errors="coerce"
                ),
            )
            [["Tanggal", "Realisasi_IN_IDR"]]
            .merge(
                fiskal_out_raw
                .assign(
                    Currency=lambda d: d["Currency"].astype(str).str.strip().str.upper(),
                )
                .merge(kurs_map, on="Currency", how="left")
                .assign(
                    Rupiah=lambda d: d["Rupiah"].where(d["Currency"] != "IDR", 1),
                )
                .drop(columns=["Currency", "Rupiah"])
                .assign(
                    Tanggal=lambda d: pd.to_datetime(d["Tanggal"], errors="coerce"),
                    Realisasi_OUT_IDR=lambda d: pd.to_numeric(d["Realisasi_OUT_IDR"], errors="coerce"),
                )
                .groupby("Tanggal", as_index=False)[["Realisasi_OUT_IDR"]]
                .sum(),
                on="Tanggal",
                how="outer"
            )
            [["Tanggal", "Realisasi_IN_IDR", "Realisasi_OUT_IDR"]],
            on="Tanggal",
            how="left"
        )
        .assign(
            Realisasi_IN_IDR=lambda d: pd.to_numeric(d["Realisasi_IN_IDR"], errors="coerce") / 1e6,
            Realisasi_OUT_IDR=lambda d: pd.to_numeric(d["Realisasi_OUT_IDR"], errors="coerce") / 1e6,
        )
        .fillna({
            "Realisasi_IN_IDR": 0,
            "Realisasi_OUT_IDR": 0,
        })
        .assign(
            SBN_Neto=lambda d: d["Realisasi_IN_IDR"] - d["Realisasi_OUT_IDR"],
            SBN_Neto_Kumulatif=lambda d: d["SBN_Neto"].cumsum(),
        )
        [[
            "Tanggal",
            "Realisasi_IN_IDR",
            "Realisasi_OUT_IDR",
            "SBN_Neto",
            "SBN_Neto_Kumulatif",
        ]]
        .sort_values("Tanggal")
        .reset_index(drop=True)
        .copy()
    )

    return data_fiskal_neto


def build_tabel_fiskal(fiskal_raw):
    return (
        fiskal_raw
        .copy()
        .assign(
            uu_apbn_2026=lambda d: pd.to_numeric(d["uu_apbn_2026"], errors="coerce"),
            realisasi_sbn=lambda d: pd.to_numeric(d["realisasi_sbn"], errors="coerce"),
            pct_realisasi=lambda d: pd.to_numeric(d["pct_realisasi"], errors="coerce")
        )
    )


def build_tabel_econ1(econ1_raw):
    return (
        econ1_raw
        .assign(
            Tanggal=lambda d: pd.to_datetime(d["Tanggal"]).dt.strftime("%d %b")
        )
        .copy()
    )


def build_tabel_econ2(econ2_raw):
    return (
        econ2_raw
        .assign(
            Tanggal=lambda d: pd.to_datetime(d["Tanggal"]).dt.strftime("%d %b")
        )
        .copy()
    )


###############################################################################
### 4b. NARASI OTOMATIS (Realisasi & Proyeksi)
###############################################################################

BULAN_INDO = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def id_number(x, decimals=2):
    """Format angka gaya Indonesia: titik ribuan, koma desimal. Contoh: 1085.594 -> '1.085,59'"""
    if x is None or pd.isna(x):
        return "-"
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "#").replace(".", ",").replace("#", ".")


def id_percent(x, decimals=2):
    if x is None or pd.isna(x):
        return "-"
    return id_number(x * 100, decimals) + "%"


def extract_defisit_pct(fiskal_raw):
    """Baris pertama sheet tabel_fiskal (sebelum di-coerce ke numerik oleh
    build_tabel_fiskal) berisi teks 'Defisit: 2.68%' di kolom uu_apbn_2026 --
    ini satu-satunya sumber asumsi defisit, jadi diambil di sini sebelum
    baris itu jadi NaN semua."""
    for val in fiskal_raw["uu_apbn_2026"]:
        match = re.search(r"defisit\s*:?\s*([\d.,]+)\s*%", str(val), re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def build_narasi(fiskal_raw, fiskal, data_fiskal_inout, data_fiskal_neto):
    """Bangun narasi 'Realisasi' (kiri) dan 'Proyeksi' (kanan) persis format
    di Sampel Fiskal.pdf, dengan semua angka dihitung otomatis dari data
    (bukan hardcode)."""

    # lookup nilai realisasi & % per baris "uraian" pada tabel fiskal
    lookup = (
        fiskal
        .assign(uraian=lambda d: d["uraian"].astype(str).str.strip())
        .set_index("uraian")
    )

    def get(uraian, col):
        try:
            return lookup.loc[uraian, col]
        except KeyError:
            return None

    defisit_pct = extract_defisit_pct(fiskal_raw)

    total_realisasi = get("Kebutuhan Penerbitan 2026", "realisasi_sbn")
    total_pct = get("Kebutuhan Penerbitan 2026", "pct_realisasi")
    sun_realisasi = get("SUN", "realisasi_sbn")
    sun_pct = get("SUN", "pct_realisasi")
    sbsn_realisasi = get("SBSN", "realisasi_sbn")
    sbsn_pct = get("SBSN", "pct_realisasi")
    jt_realisasi = get("SBN Jatuh Tempo 2026", "realisasi_sbn")
    jt_pct = get("SBN Jatuh Tempo 2026", "pct_realisasi")
    neto_realisasi = get("SBN Neto", "realisasi_sbn")
    neto_pct = get("SBN Neto", "pct_realisasi")

    # ke Triliun Rupiah (data tabel fiskal dalam Juta Rupiah)
    JUTA_KE_T = 1e6

    # proyeksi bulan berjalan (data_fiskal_inout sudah difilter ke bulan ini,
    # dan kolom Proyeksi_* sudah blend realisasi (hari yg sudah lewat) +
    # proyeksi (hari yg akan datang), jadi sum-nya = estimasi total 1 bulan)
    today = pd.Timestamp.today().normalize()
    bulan_ini = BULAN_INDO[today.month]
    penerbitan_bulan = data_fiskal_inout["Proyeksi_IN_IDR"].sum()
    jatuh_tempo_bulan = data_fiskal_inout["Proyeksi_OUT_IDR"].abs().sum()

    # neto kumulatif di akhir bulan (proyeksi) = neto kumulatif akhir bulan
    # lalu (realisasi murni) + proyeksi neto bulan berjalan (realisasi+proyeksi)
    awal_bulan = today.replace(day=1)
    sebelum_bulan_ini = data_fiskal_neto.loc[data_fiskal_neto["Tanggal"] < awal_bulan]
    neto_awal_bulan = (
        sebelum_bulan_ini["SBN_Neto_Kumulatif"].iloc[-1]
        if not sebelum_bulan_ini.empty else 0.0
    )
    neto_proyeksi_akhir_bulan = neto_awal_bulan + penerbitan_bulan - jatuh_tempo_bulan

    narasi_kiri = f"""
    <div class="narasi-title underline">Realisasi dengan asumsi defisit: {id_number(defisit_pct, 2)}%</div>
    <ul>
      <li><b>Realisasi penerbitan SBN s.d. hari ini</b> adalah sebesar
        Rp{id_number(total_realisasi / JUTA_KE_T)} T ({id_percent(total_pct)}) dengan
        realisasi SUN sebesar Rp{id_number(sun_realisasi / JUTA_KE_T)} T ({id_percent(sun_pct)})
        dan SBSN Rp{id_number(sbsn_realisasi / JUTA_KE_T)} T ({id_percent(sbsn_pct)});</li>
      <li><b>Realisasi untuk SBN Jatuh Tempo</b> (termasuk <i>cash management</i> dan
        <i>buyback</i>) adalah sebesar Rp{id_number(jt_realisasi / JUTA_KE_T)} T
        ({id_percent(jt_pct)});</li>
      <li><b>Realisasi SBN Neto</b> adalah sebesar Rp{id_number(neto_realisasi / JUTA_KE_T)} T
        ({id_percent(neto_pct)}).</li>
    </ul>
    """

    narasi_kanan = f"""
    <div class="narasi-title underline">Proyeksi</div>
    <ul>
      <li>Pada bulan {bulan_ini} {today.year}, diperkirakan terdapat
        <b>Penerbitan sebesar Rp{id_number(penerbitan_bulan)} T</b>;</li>
      <li>Pada bulan {bulan_ini} {today.year}, diperkirakan terdapat
        <b>SBN jatuh tempo sebesar Rp{id_number(jatuh_tempo_bulan)} T</b>;</li>
      <li><b>SBN neto pada {bulan_ini} {today.year}</b>, diperkirakan menjadi
        <b>Rp{id_number(neto_proyeksi_akhir_bulan)} T</b>.</li>
    </ul>
    """

    return narasi_kiri, narasi_kanan


###############################################################################
### 5. CHART
###############################################################################

def plot_fiskal_inout(data):
    # figsize disesuaikan (bukan 5.2) supaya, setelah gambar di-scale ke lebar
    # kolom HTML-nya (col-chart1 57% vs col-chart2 39%), tinggi tampilan akhir
    # sama dengan chart fiskal neto (figsize 3 x 2.5 di kolom 39%).
    fig, ax = plt.subplots(figsize=(4, 2.67), dpi=200)

    string_bulan = date.today().strftime("%B %Y")
    x = list(range(len(data)))

    ax.bar(x, data["Proyeksi_IN_IDR"], width=0.50, color="#70AD47",
           edgecolor="#548235", linewidth=0.8, alpha=0.6,
           label="Proyeksi Penerbitan", zorder=1)
    ax.bar(x, data["Proyeksi_OUT_IDR"], width=0.50, color="#ED7D31",
           edgecolor="#D34817", linewidth=0.8, alpha=0.6,
           label="Proyeksi Pelunasan", zorder=1)
    ax.bar(x, data["Realisasi_IN_IDR"], width=0.50, color="#548235",
           edgecolor="#548235", linewidth=0.8,
           label="Realisasi Penerbitan", zorder=2)
    ax.bar(x, data["Realisasi_OUT_IDR"], width=0.50, color="#D34817",
           edgecolor="#D34817", linewidth=0.8,
           label="Realisasi Pelunasan", zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels(data["Tanggal"].dt.strftime("%d"), fontsize=6.5)

    ax.set_title(
        f"Realisasi dan Proyeksi Arus Kas APBN - {string_bulan}",
        fontsize=8.5, fontweight="bold", color="#548235", pad=10, loc="left",
    )

    ax.axhline(0, color="#D34817", linewidth=0.8, zorder=1)
    ax.tick_params(axis="y", labelsize=6, length=0)
    ax.tick_params(axis="x", labelsize=6, length=0)
    ax.margins(x=0.02)
    ax.set_xlabel("")
    ax.set_ylabel("")

    # garis vertikal per data value (per tick tanggal) di sumbu-x -- sama gaya
    # dengan garis vertikal akhir-bulan di chart fiskal neto (chart 1 datanya
    # cuma 1 bulan, jadi granularitasnya per titik data, bukan per akhir bulan)
    ax.grid(axis="x", color="#b0b0b0", linewidth=0.3, linestyle="--")
    ax.grid(axis="y", color="#b0b0b0", linewidth=0.3, linestyle="--")
    ax.set_axisbelow(True)

    ax.spines['bottom'].set_linewidth(1)
    ax.spines['bottom'].set_color("#D34817")
    ax.spines['top'].set_linewidth(0)
    ax.spines['left'].set_linewidth(0)
    ax.spines['right'].set_linewidth(0)

    ax.set_facecolor("#ffffff")

    ax.legend(loc='upper right', ncol=1, frameon=False, fontsize=5.5,
              handlelength=1.2, handletextpad=0.4, labelspacing=0.25)

    fig.text(0.01, 0.01, "sumber: Kemenkeu RI", fontsize=6,
             color="#404040", ha="left", va="bottom")

    plt.tight_layout(rect=[0, 0.02, 1, 1])

    return fig


def plot_fiskal_neto(data):
    fig, ax = plt.subplots(figsize=(3, 2.5), dpi=200)

    string_tahun = date.today().strftime("%Y")

    start_of_year = pd.Timestamp.today().normalize().replace(month=1, day=1)
    today = pd.Timestamp.today().normalize()
    data_plot = (
        data
        .copy()
        .assign(Tanggal=lambda d: pd.to_datetime(d["Tanggal"], errors="coerce"))
        .loc[lambda d: (d["Tanggal"] >= start_of_year) & (d["Tanggal"] <= today)]
        .sort_values("Tanggal")
        .reset_index(drop=True)
    )

    ax.plot(data_plot["Tanggal"], data_plot["SBN_Neto_Kumulatif"],
            linewidth=2, color="#D34817")

    # garis vertikal per akhir bulan data (data point terakhir tiap bulan)
    month_end_dates = (
        data_plot
        .assign(_ym=data_plot["Tanggal"].dt.to_period("M"))
        .groupby("_ym")["Tanggal"]
        .max()
    )
    for month_end in month_end_dates:
        ax.axvline(month_end, color="#b0b0b0", linewidth=0.3,
                   linestyle="--", zorder=0)

    x_offset = pd.Timedelta(days=0.3)
    last = data_plot.iloc[-1]
    ax.text(last["Tanggal"] + x_offset, last["SBN_Neto_Kumulatif"],
            f"{last['SBN_Neto_Kumulatif']:.0f}", fontsize=7,
            color="#D34817", ha="left", va="center")

    ax.set_title(f"SBN Neto Kumulatif {string_tahun}", fontsize=8, fontweight="bold",
                 color="#548235", pad=10, loc="left")

    y_min = data_plot["SBN_Neto_Kumulatif"].min()
    y_max = data_plot["SBN_Neto_Kumulatif"].max()
    y_padding = max((y_max - y_min) * 0.1, 10)
    ax.set_ylim(y_min - y_padding, y_max + y_padding)
    ax.set_xlim(start_of_year, today)
    ax.set_xticks([start_of_year, today])
    ax.set_xticklabels([start_of_year.strftime("%d-%b"), today.strftime("%d-%b")])
    ax.yaxis.set_major_locator(MultipleLocator(100))
    ax.tick_params(axis="x", labelsize=6, rotation=0, length=0)
    ax.tick_params(axis="y", labelsize=6, length=0)
    ax.set_xlabel("")
    ax.set_ylabel("")

    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color="#b0b0b0", linewidth=0.3, linestyle="--")
    ax.set_axisbelow(True)

    ax.spines['bottom'].set_linewidth(1)
    ax.spines['bottom'].set_color("#D34817")
    ax.spines['top'].set_linewidth(0)
    ax.spines['left'].set_linewidth(0)
    ax.spines['right'].set_linewidth(0)

    ax.set_facecolor("#ffffff")

    fig.text(0.01, 0.01, "sumber: Kemenkeu RI", fontsize=6,
             color="#404040", ha="left", va="bottom")

    plt.tight_layout(rect=[0, 0.02, 1, 1])

    return fig


###############################################################################
### 6. TABEL (great_tables -> HTML langsung, TANPA screenshot)
###############################################################################

def strip_gt_wrapper_padding(html):
    """great_tables' as_raw_html() bungkus tabel dalam <div id="..." style="...
    padding-top:10px;padding-bottom:10px;...">. Padding bawaan ini yang bikin
    jarak vertikal antar tabel (mis. tabel econ1 vs econ2) tetap ada meskipun
    margin CSS di .econ-stack sudah di-nol-kan. Nolkan di sini supaya jarak
    antar tabel murni dikontrol oleh CSS .econ-stack (atau margin lain)."""
    html = re.sub(r"padding-top:\s*10px;padding-bottom:\s*10px;",
                   "padding-top:0px;padding-bottom:0px;", html, count=1)
    return html


def make_gt_fiskal(fiskal):
    gt = (
        GT(fiskal)
        .tab_header(title="Realisasi Penerbitan SBSN")
        .tab_source_note(source_note="- target berdasarkan Kepdirjen PPR Nomor 89 Tahun 2025 terkait SPU Tahun 2026")
        .tab_source_note(source_note="- dalam juta Rupiah")
        .tab_source_note(source_note="- sumber: Kementerian Keuangan RI")
        .tab_style(
            style=style.text(size="7px", whitespace="pre-line"),
            locations=loc.source_notes()
        )
        .tab_style(
            style=style.text(color="#548235", weight="bold", size="13px"),
            locations=loc.title()
        )
        .cols_label(
            uraian="",
            uu_apbn_2026="UU APBN 2026",
            realisasi_sbn="Realisasi SBN",
            pct_realisasi="% Realisasi"
        )
        .tab_style(
            style=[style.text(color="#404040", weight="bold", size="7px")],
            locations=loc.column_labels()
        )
        .tab_style(
            style=[style.text(color="#404040", weight="bold", size="7px")],
            locations=loc.body(rows=lambda x: pd.Series(x.index == 0, index=x.index))
        )
        .tab_style(
            style=[style.fill(color="#548235"), style.text(color="white")],
            locations=loc.body(rows=lambda x: x["uraian"].isin(["Kebutuhan Penerbitan 2026"]))
        )
        .tab_style(
            style=[style.fill(color="#B4E5A2")],
            locations=loc.body(rows=lambda x: x["uraian"].isin(["SBN Jatuh Tempo 2026", "SBN Neto"]))
        )
        .tab_style(
            style=[style.fill(color="#D34817"), style.text(color="white")],
            locations=loc.body(rows=lambda x: x["uraian"].isin(["SUN", "SBSN"]))
        )
        .tab_style(
            style=[style.fill(color="#FABF8F")],
            locations=loc.body(rows=lambda x: x["uraian"].isin(
                ["SUN Rupiah", "SUN Valas", "SBSN Rupiah", "SBSN Valas"]))
        )
        .fmt_number(
            columns=fiskal.columns[1:3].tolist(),
            rows=lambda x: pd.Series(x.index != 0, index=x.index),
            decimals=0
        )
        .fmt_percent(
            columns=fiskal.columns[3:4].tolist(),
            rows=lambda x: pd.Series(x.index != 0, index=x.index),
            decimals=2
        )
        .cols_align(align="right", columns=fiskal.columns[1:4].tolist())
        .tab_options(
            table_font_size="7px",
            table_width="100%",
            data_row_padding="0.63px",
            source_notes_padding="0.63px",
        )
        .cols_width(dict(zip(fiskal.columns, ["40%", "20%", "20%", "20%"])))
    )
    return gt.as_raw_html()


def make_gt_econ1(data_tabel_econ1):
    gt = (
        GT(data_tabel_econ1)
        .tab_header(title="Realisasi Indikator Ekonomi APBN")
        .tab_source_note(source_note="sumber: Bloomberg")
        .tab_style(
            style=style.text(size="7px", whitespace="pre-line"),
            locations=loc.source_notes()
        )
        .tab_style(
            style=style.text(color="#548235", weight="bold", size="13px"),
            locations=loc.title()
        )
        .tab_style(
            style=[style.fill(color="#D34817"),
                   style.text(color="white", v_align="middle", stretch="condensed", size="7px")],
            locations=loc.column_labels()
        )
        .tab_style(
            style=style.borders(sides="right", color="#B0B0B0", weight="0.8px"),
            locations=[loc.body(columns="2025"), loc.column_labels(columns="2025")]
        )
        .cols_align(
            align="right",
            columns=["2021", "2022", "2023", "2024", "2025",
                     "Asumsi APBN", "Realisasi 2026", "Tanggal"]
        )
        .fmt_number(
            columns=["2021", "2022", "2023", "2024", "2025", "2026"],
            rows=lambda x: ~x["Indikator"].astype(str).str.strip().str.lower().str.contains("nilai tukar", na=False),
            decimals=2
        )
        .fmt_number(
            columns=["2021", "2022", "2023", "2024", "2025", "Asumsi APBN", "Realisasi 2026"],
            rows=lambda x: x["Indikator"].astype(str).str.strip().str.lower().str.contains("nilai tukar", na=False),
            decimals=0
        )
        .tab_options(
            table_font_size="7px",
            table_width="100%",
            data_row_padding="3.7px",
            source_notes_padding="2px",
        )
        .cols_width({
            "Indikator": "20.5%", "2021": "9.5%", "2022": "9.5%", "2023": "9.5%",
            "2024": "9.5%", "2025": "9.5%", "Asumsi APBN": "11%",
            "Realisasi 2026": "11%", "Tanggal": "11%",
        })
    )
    return gt.as_raw_html()


def make_gt_econ2(data_tabel_econ2):
    gt = (
        GT(data_tabel_econ2)
        .tab_header(title="Realisasi Indikator Ekonomi Lainnya")
        .tab_source_note(source_note="sumber: BI, BPS")
        .tab_style(
            style=style.text(size="7px", whitespace="pre-line"),
            locations=loc.source_notes()
        )
        .tab_style(
            style=style.text(color="#548235", weight="bold", size="13px"),
            locations=loc.title()
        )
        .tab_style(
            style=[style.fill(color="#D34817"),
                   style.text(color="white", v_align="middle", stretch="condensed", size="7px")],
            locations=loc.column_labels()
        )
        .tab_style(
            style=style.borders(sides="right", color="#B0B0B0", weight="0.8px"),
            locations=[loc.body(columns="2025"), loc.column_labels(columns="2025")]
        )
        .cols_align(
            align="right",
            columns=["2021", "2022", "2023", "2024", "2025", "2026", "Tanggal"]
        )
        .fmt_number(columns=["2021", "2022", "2023", "2024", "2025", "2026"])
        .tab_options(
            table_font_size="7px",
            table_width="100%",
            data_row_padding="3.7px",
            source_notes_padding="2px",
        )
        .cols_width({
            "Indikator": "30.5%", "2021": "9.5%", "2022": "9.5%", "2023": "9.5%",
            "2024": "9.5%", "2025": "9.5%", "2026": "11%", "Tanggal": "11%",
        })
    )
    return gt.as_raw_html()


###############################################################################
### 7. SUSUN HTML
###############################################################################

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  /* NOTE: margin halaman sengaja tidak pakai CSS at-rule "at-page margin"
     karena wkhtmltopdf (WebKit lama) tidak konsisten mendukung itu.
     Margin diatur lewat padding pada body (box-model biasa, didukung semua
     engine) plus flag margin di perintah wkhtmltopdf (lihat render_pdf). */
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html {{
    height: 297mm;
  }}
  body {{
    position: relative;
    height: 297mm;
    font-family: Arial, Helvetica, sans-serif;
    margin: 0;
    padding: 4mm 6mm;
    color: #222;
  }}
  table.header-bar {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10mm;
  }}
  table.header-bar td {{
    color: #548235;
    font-weight: bold;
    font-size: 20px;
    padding: 0;
    vertical-align: bottom;
  }}
  table.header-bar td.header-left {{ text-align: left; }}
  table.header-bar td.header-right {{ text-align: right; }}
  .footer-bar {{
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #D34817;
    padding: 3mm 5mm;
  }}
  table.footer-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  table.footer-table td {{
    color: #ffffff;
    vertical-align: top;
    padding: 0;
  }}
  td.footer-left {{
    width: 42%;
    font-weight: bold;
    font-size: 9px;
    line-height: 1.6;
    letter-spacing: 0.5px;
    white-space: nowrap;
  }}
  td.footer-right {{
    width: 58%;
    font-size: 7.5px;
    line-height: 1.5;
    letter-spacing: 1px;
  }}
  table.layout {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin-bottom: 7mm;
  }}
  table.layout td {{
    vertical-align: top;
    padding: 0;
  }}
  /* NOTE: gap antar kolom SENGAJA pakai <td> kosong terpisah (bukan
     padding-right/padding-left) karena wkhtmltopdf (WebKit lama) tidak
     konsisten menghormati padding pada <td> saat table-layout:fixed
     dipakai bersama lebar persen -- paddingnya kadang diabaikan sehingga
     dua kolom terlihat nempel. <td> kosong dengan lebar tetap jauh lebih
     bisa diandalkan di semua engine. */
  td.col-fiskal {{ width: 53%; }}
  td.col-econ {{ width: 43%; }}
  td.col-chart1 {{ width: 53%; }}
  td.col-chart2 {{ width: 43%; }}
  td.gap {{ width: 2%; }}
  .econ-stack > div + div {{
    margin-top: 5mm;
  }}
  .chart-box {{
    border: 1px solid #b0b0b0;
    padding: 2mm;
  }}
  .chart-box img {{
    width: 100%;
    display: block;
  }}
  table.narasi-layout {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  table.narasi-layout td {{
    vertical-align: top;
    padding: 0;
    font-size: 8.5px;
    line-height: 1.5;
    letter-spacing: 0.5px;
  }}
  td.narasi-kiri {{ width: 48%; }}
  td.narasi-kanan {{ width: 48%; }}
  td.narasi-gap {{ width: 4%; }}
  .narasi-title {{
    font-weight: bold;
    margin-bottom: 1mm;
  }}
  .narasi-title.underline {{
    text-decoration: underline;
  }}
  table.narasi-layout ul {{
    margin: 0;
    padding-left: 3.5mm;
  }}
  table.narasi-layout li {{
    margin-bottom: 1mm;
  }}
</style>
</head>
<body>

  <table class="header-bar">
    <tr>
      <td class="header-left">Realisasi Penerbitan SBN</td>
      <td class="header-right">Fiskal</td>
    </tr>
  </table>

  <table class="layout">
    <tr>
      <td class="col-fiskal">{gt_fiskal_html}</td>
      <td class="gap"></td>
      <td class="col-econ">
        <div class="econ-stack">
          <div>{gt_econ1_html}</div>
          <div>{gt_econ2_html}</div>
        </div>
      </td>
    </tr>
  </table>

  <table class="layout">
    <tr>
      <td class="col-chart1">
        <div class="chart-box"><img src="data:image/png;base64,{chart_inout_b64}"></div>
      </td>
      <td class="gap"></td>
      <td class="col-chart2">
        <div class="chart-box"><img src="data:image/png;base64,{chart_neto_b64}"></div>
      </td>
    </tr>
  </table>

  <table class="narasi-layout">
    <tr>
      <td class="narasi-kiri">{narasi_kiri_html}</td>
      <td class="narasi-gap"></td>
      <td class="narasi-kanan">{narasi_kanan_html}</td>
    </tr>
  </table>

  <div class="footer-bar">
    <table class="footer-table">
      <tr>
        <td class="footer-left">
          Powered by:<br>
          DJPPR, Kemenkeu<br>
          Ged. Frans Seda, Jl. Wahidin Raya No. 1, Jakarta
        </td>
        <td class="footer-right">
          Disclaimer: Dokumen ini disusun untuk keperluan informasi bagi internal DJPPR dan pihak
          yang diperkenankan memperoleh informasi ini, dan tidak untuk dipublikasikan atau
          disebarluaskan kepada pihak lain. Apabila informasi ini kurang akurat/lengkap maka akan
          diperbaiki sebagaimana mestinya. Hak cipta pada DJPPR, Kementerian Keuangan.
        </td>
      </tr>
    </table>
  </div>

</body>
</html>
"""


###############################################################################
### 8. RENDER HTML -> PDF (wkhtmltopdf)
###############################################################################

def render_pdf(html_path: Path, pdf_path: Path):
    wkhtmltopdf_path = find_wkhtmltopdf()
    cmd = [
        wkhtmltopdf_path,
        "--page-size", "A4",
        "--margin-top", "0mm",
        "--margin-bottom", "0mm",
        "--margin-left", "0mm",
        "--margin-right", "0mm",
        "--enable-local-file-access",
        "--disable-smart-shrinking",
        str(html_path),
        str(pdf_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"wkhtmltopdf gagal (exit {result.returncode}). "
            f"Pastikan wkhtmltopdf terinstall (cek: {wkhtmltopdf_path})."
        )


###############################################################################
### MAIN
###############################################################################

def main():
    print("=" * 80)
    print("GENERATE REPORT")
    print("=" * 80)

    print("1. Load data...")
    fiskal_raw, econ1_raw, econ2_raw, fiskal_in_raw, fiskal_out_raw, kurs = load_data()

    print("2. Olah data...")
    data_fiskal_inout = build_data_fiskal_inout(fiskal_in_raw, fiskal_out_raw, kurs)
    data_fiskal_neto = build_data_fiskal_neto(fiskal_in_raw, fiskal_out_raw, kurs)
    fiskal = build_tabel_fiskal(fiskal_raw)
    data_tabel_econ1 = build_tabel_econ1(econ1_raw)
    data_tabel_econ2 = build_tabel_econ2(econ2_raw)

    print("3. Render tabel (great_tables -> HTML)...")
    gt_fiskal_html = strip_gt_wrapper_padding(make_gt_fiskal(fiskal))
    gt_econ1_html = strip_gt_wrapper_padding(make_gt_econ1(data_tabel_econ1))
    gt_econ2_html = strip_gt_wrapper_padding(make_gt_econ2(data_tabel_econ2))

    print("4. Render chart (matplotlib -> PNG base64)...")
    chart_inout_b64 = fig_to_base64(plot_fiskal_inout(data_fiskal_inout))
    chart_neto_b64 = fig_to_base64(plot_fiskal_neto(data_fiskal_neto))

    print("4b. Susun narasi otomatis...")
    narasi_kiri_html, narasi_kanan_html = build_narasi(
        fiskal_raw, fiskal, data_fiskal_inout, data_fiskal_neto
    )

    print("5. Susun HTML...")
    html = PAGE_TEMPLATE.format(
        gt_fiskal_html=gt_fiskal_html,
        gt_econ1_html=gt_econ1_html,
        gt_econ2_html=gt_econ2_html,
        chart_inout_b64=chart_inout_b64,
        chart_neto_b64=chart_neto_b64,
        narasi_kiri_html=narasi_kiri_html,
        narasi_kanan_html=narasi_kanan_html,
    )

    html_path = output_pdf_dir / "_report_tmp.html"
    html_path.write_text(html, encoding="utf-8")

    print("6. Render PDF (wkhtmltopdf)...")
    today_str = date.today().strftime("%Y%m%d")
    pdf_path = output_pdf_dir / f"{today_str} MU Part Fiskal.pdf"
    render_pdf(html_path, pdf_path)

    # html_path cuma file perantara utk wkhtmltopdf -- setelah PDF berhasil
    # dibuat, tidak diperlukan lagi, jadi dihapus supaya tidak numpuk di folder
    html_path.unlink(missing_ok=True)

    print("=" * 80)
    print("SELESAI! PDF tersimpan di:", pdf_path)
    print("=" * 80)


if __name__ == "__main__":
    main()

### selesai ###
