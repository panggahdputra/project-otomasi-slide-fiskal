###############################################################################
### IMPORT LIBRARIES
###############################################################################

import pandas as pd
from pathlib import Path
from datetime import date, datetime
import re
import warnings

###############################################################################
### SETTING DIRECTORIES
###############################################################################

# folder project = folder induk dari folder "_02_script" (tempat script ini berada)
project_dir = Path(__file__).resolve().parent.parent

# folder data_input
data_input_dir = project_dir / "_01_data_input"

# folder input outstanding (dipakai untuk extract kurs)
raw_outstanding_dir = data_input_dir / "01_raw_outstanding"

# folder input fiskal
raw_fiskal_dir = data_input_dir / "02_fiskal"

# folder input econ1 dan econ2
raw_econ_dir = data_input_dir / "03_econ"

# folder output
input_quarto_dir = data_input_dir / "00_input_quarto"


###############################################################################
### 01: EXTRACT NILAI KURS DARI FILE OUTSTANDING
###############################################################################

def extract_nilai_kurs(input_dir, output_dir, pattern="*.xls", output_suffix="kurs"):
    """Extract asumsi nilai kurs (IDR per mata uang) dari file outstanding terbaru."""

    print("\n" + "="*80)
    print("01: EXTRACT NILAI KURS DARI FILE OUTSTANDING")
    print("="*80)

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    latest_file = max(input_dir.glob(pattern), key=lambda x: x.stat().st_mtime)
    print("File yang digunakan:", latest_file.name)

    raw = pd.read_excel(latest_file, header=None)

    row_2 = raw.iloc[1].astype(str)
    date_value = None
    for cell in row_2:
        match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})',
            str(cell),
            re.IGNORECASE,
        )
        if match:
            try:
                date_value = datetime.strptime(match.group(), "%B %d, %Y")
                break
            except:
                pass
            
    if date_value is None:
        print("Warning: Tanggal tidak ditemukan di row 2, menggunakan tanggal hari ini")
        file_date = date.today().strftime("%Y%m%d")
    else:
        file_date = date_value.strftime("%Y%m%d")
        print("Tanggal update:", file_date)

    fx_pattern = re.compile(
        r"Assumed\s+exchange\s+rate\s+for\s+conversion\s*\(IDR\s*/\s*([A-Z]{3})\)\s*is\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
        flags=re.IGNORECASE,
    )

    fx_map = {}
    for cell_value in raw.astype(str).stack():
        text = str(cell_value).strip()
        if not text or text.lower() == "nan":
            continue

        match = fx_pattern.search(text)
        if match:
            ccy = match.group(1).upper()
            rate_str = match.group(2).replace(",", "")
            fx_map[ccy] = pd.to_numeric(rate_str, errors="coerce")

    target_currency = ["USD", "JPY", "EUR", "AUD", "CNH", "CNY"]
    kurs_df = pd.DataFrame({
        "Currency": target_currency,
        "Rupiah": [fx_map.get(ccy, pd.NA) for ccy in target_currency],
    })

    output_file = f"{file_date}_{output_suffix}.csv"
    kurs_df.to_csv(output_dir / output_file, index=False)
    print("Save as:", output_file)

    missing_currency = [ccy for ccy in target_currency if ccy not in fx_map]
    if missing_currency:
        print(f"Warning: Kurs tidak ditemukan untuk {', '.join(missing_currency)}")

    return kurs_df


###############################################################################
### 02: PULL FISKAL SHEET
###############################################################################

def export_fiskal(input_dir, output_dir, pattern="*.xlsx", sheet_name="tabel_fiskal"):
    """Menarik dan menyimpan data fiskal sheet tabel_fiskal"""

    print("\n" + "="*80)
    print("02: PULL FISKAL SHEET")
    print("="*80)

    # set path input dan output
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # pilih file xlsx di folder
    files = list(input_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Tidak ada file dengan pola {pattern} di {input_dir}")

    xlsx_file = files[0]

    print("File yang digunakan:", xlsx_file.name)

    # baca file excel dengan sheet tabel_fiskal
    df = pd.read_excel(xlsx_file, sheet_name=sheet_name)

    # ambil tanggal terbaru dari kolom "Tanggal"
    if "Tanggal" in df.columns:
        dates       = pd.to_datetime(df["Tanggal"], errors="coerce")
        valid_dates = dates[dates.notna()]
        latest_date = valid_dates.max().date() if not valid_dates.empty else date.today()
    else:
        latest_date = date.today()

    print("Tanggal update:", latest_date)

    # nama file otomatis pakai tanggal terakhir dari dataframe
    output_file = f"{latest_date.strftime('%Y%m%d')}_fiskal.csv"

    # simpan dalam bentuk csv di folder output_dir
    df.to_csv(output_dir / output_file, index=False)

    print("Save as:", output_file)

    return df


###############################################################################
### 03: PULL ECON1 SHEET
###############################################################################

def export_econ1(input_dir, output_dir, pattern="*.xlsx", sheet_name="tabel_econ1"):
    """Menarik dan menyimpan data econ1 sheet tabel_econ1"""

    print("\n" + "="*80)
    print("03: PULL ECON1 SHEET")
    print("="*80)

    # set path input dan output
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # pilih file xlsx di folder
    files = list(input_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Tidak ada file dengan pola {pattern} di {input_dir}")

    xlsx_file = files[0]

    print("File yang digunakan:", xlsx_file.name)

    # baca file excel dengan sheet tabel_econ
    df = pd.read_excel(xlsx_file, sheet_name=sheet_name)

    # ambil tanggal terbaru dari kolom "Data Terakhir"
    latest_date = date.today()

    print("Tanggal update:", latest_date)

    # nama file otomatis pakai tanggal terakhir dari dataframe
    output_file = f"{latest_date.strftime('%Y%m%d')}_econ1.csv"

    # simpan dalam bentuk csv di folder output_dir
    df.to_csv(output_dir / output_file, index=False)

    print("Save as:", output_file)

    return df


###############################################################################
### 04: PULL ECON2 SHEET
###############################################################################

def export_econ2(input_dir, output_dir, pattern="*.xlsx", sheet_name="tabel_econ2"):
    """Menarik dan menyimpan data econ2 sheet tabel_econ2"""

    print("\n" + "="*80)
    print("04: PULL ECON2 SHEET")
    print("="*80)

    # set path input dan output
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # pilih file xlsx di folder
    files = list(input_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Tidak ada file dengan pola {pattern} di {input_dir}")

    xlsx_file = files[0]

    print("File yang digunakan:", xlsx_file.name)

    # baca file excel dengan sheet tabel_econ
    df = pd.read_excel(xlsx_file, sheet_name=sheet_name)

    # ambil tanggal terbaru dari kolom "Data Terakhir"
    latest_date = date.today()

    print("Tanggal update:", latest_date)

    # nama file otomatis pakai tanggal terakhir dari dataframe
    output_file = f"{latest_date.strftime('%Y%m%d')}_econ2.csv"

    # simpan dalam bentuk csv di folder output_dir
    df.to_csv(output_dir / output_file, index=False)

    print("Save as:", output_file)

    return df


###############################################################################
### 05: PULL REALISASI DAN PROYEKSI FISKAL
###############################################################################

def export_fiskal_inout(input_dir, output_dir, pattern="*.xlsx", sheet_name=None):
    """Menarik dan menyimpan data realisasi/proyeksi fiskal ke format output Quarto."""

    print("\n" + "="*80)
    print("05: PULL REALISASI DAN PROYEKSI FISKAL")
    print("="*80)

    # set path input dan output
    input_dir   = Path(input_dir)
    output_dir  = Path(output_dir)

    # pilih file xlsx di folder
    files       = list(input_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Tidak ada file dengan pola {pattern} di {input_dir}")

    xlsx_file   = files[0]

    print("File yang digunakan:", xlsx_file.name)

    # konfigurasi sheet default
    if sheet_name is None:
        sheet_name = {
            "issuance"  : "issuance_2026",
            "rencana"   : "rencana_2026",
            "base"      : "maturity_all_2026",
            "spn_spns"  : "maturity_spn_spns_2026",
            "srbi"      : "maturity_SRBI_2026",
            "buyback"   : "buyback_2026",
        }

    # kolom yang diperlukan per sheet
    required_columns = {
        "issuance"  : ["Tanggal Transaksi", "Seri", "Volume Penerbitan (juta Rupiah)"],
        "rencana"   : ["Tanggal", "Rencana Penerbitan (juta Rupiah)"],
        "base"      : ["Seri", "Jatuh Tempo", "Currency", "Outstanding", "Jatuh Tempo Total (juta Rupiah)"],
        "spn_spns"  : ["Seri", "Jatuh Tempo", "Currency", "Volume Penerbitan (juta Rupiah)", "Jatuh Tempo Total (juta Rupiah)"],
        "srbi"      : ["Seri", "Jatuh Tempo", "Currency", "Jatuh Tempo Total (juta Rupiah)"],
        "buyback"   : ["Seri", "Jatuh Tempo", "Currency", "Volume Buyback (juta Rupiah)"],
    }

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Data Validation extension is not supported and will be removed",
            category=UserWarning,
            module=r"openpyxl\.worksheet\._reader",
        )

        issuance_sheet  = pd.read_excel(xlsx_file, sheet_name=sheet_name["issuance"])
        issuance_df     = issuance_sheet[required_columns["issuance"]].copy()

        rencana_sheet  = pd.read_excel(xlsx_file, sheet_name=sheet_name["rencana"])
        rencana_df     = rencana_sheet[required_columns["rencana"]].copy()

        base_sheet  = pd.read_excel(xlsx_file, sheet_name=sheet_name["base"])
        base_df     = base_sheet[required_columns["base"]].copy()

        spn_spns_sheet  = pd.read_excel(xlsx_file, sheet_name=sheet_name["spn_spns"])
        spn_spns_df     = spn_spns_sheet[required_columns["spn_spns"]].copy()

        srbi_sheet  = pd.read_excel(xlsx_file, sheet_name=sheet_name["srbi"])
        srbi_df     = srbi_sheet[required_columns["srbi"]].copy()

        buyback_sheet  = pd.read_excel(xlsx_file, sheet_name=sheet_name["buyback"])
        buyback_df     = buyback_sheet[required_columns["buyback"]].copy()

    # olah data keluaran 1 (fiskal_in.csv)
    realisasi_df = issuance_df[["Tanggal Transaksi", "Volume Penerbitan (juta Rupiah)"]].copy()
    realisasi_df["Tanggal Transaksi"] = pd.to_datetime(
        realisasi_df["Tanggal Transaksi"], errors="coerce"
    )
    realisasi_df["Volume Penerbitan (juta Rupiah)"] = pd.to_numeric(
        realisasi_df["Volume Penerbitan (juta Rupiah)"], errors="coerce"
    )
    realisasi_daily = (
        realisasi_df.dropna(subset=["Tanggal Transaksi"])
        .groupby("Tanggal Transaksi", as_index=False)["Volume Penerbitan (juta Rupiah)"]
        .sum()
        .rename(columns={"Tanggal Transaksi": "Tanggal", "Volume Penerbitan (juta Rupiah)": "Realisasi_IN_IDR"})
    )

    # prefix nama file pakai tanggal hari ini (konsisten dgn export_econ1/export_econ2)
    latest_date = date.today()
    print("Tanggal update:", latest_date)

    proyeksi_df = rencana_df[["Tanggal", "Rencana Penerbitan (juta Rupiah)"]].copy()
    proyeksi_df["Tanggal"] = pd.to_datetime(
        proyeksi_df["Tanggal"], errors="coerce"
    )
    proyeksi_df["Rencana Penerbitan (juta Rupiah)"] = pd.to_numeric(
        proyeksi_df["Rencana Penerbitan (juta Rupiah)"], errors="coerce"
    )
    proyeksi_daily = (
        proyeksi_df.dropna(subset=["Tanggal"])
        .groupby("Tanggal", as_index=False)["Rencana Penerbitan (juta Rupiah)"]
        .sum()
        .rename(columns={"Rencana Penerbitan (juta Rupiah)": "Proyeksi_IN_IDR"})
    )

    fiskal_in_df = pd.merge(proyeksi_daily, realisasi_daily, on="Tanggal", how="outer")
    fiskal_in_df = fiskal_in_df.sort_values("Tanggal").reset_index(drop=True)
    fiskal_in_df["Tanggal"] = fiskal_in_df["Tanggal"].dt.strftime("%Y-%m-%d")
    fiskal_in_df = fiskal_in_df[["Tanggal", "Proyeksi_IN_IDR", "Realisasi_IN_IDR"]]
    fiskal_in_df = fiskal_in_df.fillna(0)

    fiskal_in_file = output_dir / f"{latest_date.strftime('%Y%m%d')}_fiskal_in.csv"
    fiskal_in_df.to_csv(fiskal_in_file, index=False)
    print("Save as:", fiskal_in_file.name)

    # olah data keluaran 2 (fiskal_out.csv)
    out_base = pd.DataFrame({
        "Tanggal": base_df["Jatuh Tempo"],
        "Currency": base_df["Currency"],
        "Proyeksi_OUT": pd.to_numeric(base_df["Outstanding"], errors="coerce") / 1_000_000,
        "Realisasi_OUT_IDR": pd.to_numeric(base_df["Jatuh Tempo Total (juta Rupiah)"], errors="coerce").fillna(0),
    })

    out_spn_spns = pd.DataFrame({
        "Tanggal": spn_spns_df["Jatuh Tempo"],
        "Currency": spn_spns_df["Currency"],
        "Proyeksi_OUT": pd.to_numeric(spn_spns_df["Volume Penerbitan (juta Rupiah)"], errors="coerce"),
        "Realisasi_OUT_IDR": pd.to_numeric(spn_spns_df["Jatuh Tempo Total (juta Rupiah)"], errors="coerce").fillna(0),
    })

    out_srbi = pd.DataFrame({
        "Tanggal": srbi_df["Jatuh Tempo"],
        "Currency": srbi_df["Currency"],
        "Proyeksi_OUT": pd.to_numeric(srbi_df["Jatuh Tempo Total (juta Rupiah)"], errors="coerce").fillna(0),
        "Realisasi_OUT_IDR": pd.to_numeric(srbi_df["Jatuh Tempo Total (juta Rupiah)"], errors="coerce").fillna(0),
    })

    out_buyback = pd.DataFrame({
        "Tanggal": buyback_df["Jatuh Tempo"],
        "Currency": buyback_df["Currency"],
        "Proyeksi_OUT": pd.to_numeric(buyback_df["Volume Buyback (juta Rupiah)"], errors="coerce").fillna(0),
        "Realisasi_OUT_IDR": pd.to_numeric(buyback_df["Volume Buyback (juta Rupiah)"], errors="coerce").fillna(0),
    })

    fiskal_out_df = pd.concat(
        [out_base, out_spn_spns, out_srbi, out_buyback],
        ignore_index=True
    )
    # pastikan "Tanggal" bertipe datetime murni (bukan campuran Timestamp/angka),
    # lalu buang baris tanpa tanggal jatuh tempo yang valid
    fiskal_out_df["Tanggal"] = pd.to_datetime(fiskal_out_df["Tanggal"], errors="coerce")
    fiskal_out_df = fiskal_out_df.dropna(subset=["Tanggal"])
    # fillna hanya utk kolom angka -- jangan sampai menimpa kolom Tanggal
    fiskal_out_df[["Proyeksi_OUT", "Realisasi_OUT_IDR"]] = (
        fiskal_out_df[["Proyeksi_OUT", "Realisasi_OUT_IDR"]].fillna(0)
    )
    fiskal_out_df = fiskal_out_df.sort_values("Tanggal").reset_index(drop=True)

    fiskal_out_file = output_dir / f"{latest_date.strftime('%Y%m%d')}_fiskal_out.csv"
    fiskal_out_df.to_csv(fiskal_out_file, index=False)

    print("Save as:", fiskal_out_file.name)

    return {
        "fiskal_in": fiskal_in_df,
        "fiskal_out": fiskal_out_df,
    }


###############################################################################
### MAIN: RUN ALL PROCESSING
###############################################################################

def run_all():
    """Jalankan semua proses data processing"""
    print("\n" + "="*80)
    print("MULAI PROSES DATA PREPARATION")
    print("="*80)

    try:
        # 01: Extract Nilai Kurs
        extract_nilai_kurs(
            input_dir=raw_outstanding_dir,
            output_dir=input_quarto_dir
        )

        # 02: Pull Fiskal
        export_fiskal(
            input_dir=raw_fiskal_dir,
            output_dir=input_quarto_dir
        )

        # 03: Pull Econ1
        export_econ1(
            input_dir=raw_econ_dir,
            output_dir=input_quarto_dir
        )

        # 04: Pull Econ2
        export_econ2(
            input_dir=raw_econ_dir,
            output_dir=input_quarto_dir
        )

        # 05: Pull Fiskal In/Out
        export_fiskal_inout(
            input_dir=raw_fiskal_dir,
            output_dir=input_quarto_dir
        )

        print("\n" + "="*80)
        print("SEMUA PROSES DATA PREPARATIN SELESAI!")
        print("="*80)

    except Exception as e:
        print(f"\n!!! ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    run_all()

### selesai ###
