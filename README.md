# Slide Fiskal — Market Update Part Fiskal

Project otomasi untuk menghasilkan laporan PDF 1 halaman "Market Update — Part Fiskal", berisi tabel realisasi penerbitan SBN, tabel indikator ekonomi, chart arus kas APBN, chart SBN neto kumulatif, dan narasi realisasi & proyeksi. Laporan dibuat langsung dari data Excel mentah menggunakan Python (pandas, great_tables, matplotlib) dan wkhtmltopdf.

## Struktur Folder

```
Slide Fiskal/
├── generate.bat                     # entry point: jalankan 2 script Python secara berurutan
├── _01_data_input/
│   ├── 01_raw_outstanding/          # file .xls Outstanding (DMFAS) -- sumber kurs IDR
│   ├── 02_fiskal/                   # fiskal.xlsx -- sumber tabel & chart realisasi SBN
│   ├── 03_econ/                     # data_econ.xlsx -- sumber indikator ekonomi
│   └── 00_input_quarto/             # OUTPUT data_preparation.py (6 CSV, JANGAN diedit manual)
├── _02_script/
│   ├── data_preparation.py          # olah data mentah -> CSV di 00_input_quarto
│   └── generate_report.py           # CSV -> HTML (tabel + chart) -> PDF via wkhtmltopdf
├── _03_output_pdf/
│   └── {YYYYMMDD} MU Part Fiskal.pdf  # hasil akhir
└── _04_dokumentasi/
    ├── 0. requirements.txt          # daftar dependency Python
    ├── 1. installation.txt          # panduan instalasi Python, wkhtmltopdf, packages lain
    ├── 2. data_preparation.txt      # format & cara update tiap file Excel input
    └── 3. execution.txt             # cara jalan & troubleshooting generate.bat
```

## Alur Kerja

1. **Update data input** — perbarui file Excel di `01_raw_outstanding`, `02_fiskal`, `03_econ` (lihat detail format di `_04_dokumentasi/2. data_preparation.txt`).
2. **Jalankan `generate.bat`** (double-click) — otomatis menjalankan:
   - `data_preparation.py`: membaca Excel mentah, mengekstrak kurs, merapikan data fiskal & ekonomi, menyimpan 6 file CSV ke `00_input_quarto` (berprefix tanggal `YYYYMMDD`).
   - `generate_report.py`: membaca CSV terbaru, membangun tabel (great_tables) dan chart (matplotlib), menyusun jadi satu halaman HTML, lalu merender ke PDF via wkhtmltopdf.
3. **Cek hasil** di `_03_output_pdf\{YYYYMMDD} MU Part Fiskal.pdf`.

## Instalasi

Prasyarat: Python 3.9+ dan wkhtmltopdf (panduan lengkap di `_04_dokumentasi/1. installation.txt`).

```
pip install -r "_04_dokumentasi\0. requirements.txt"
```

Dependency utama: `pandas`, `openpyxl`, `xlrd`, `numpy`, `matplotlib`, `great_tables`.

## Dokumentasi Lengkap

Lihat folder `_04_dokumentasi/` untuk panduan instalasi, format data, cara eksekusi, dan troubleshooting lengkap (error umum & solusinya).

---

Disusun oleh **Panggah Dwi Putra** — Tim Analisis Keuangan dan Pasar SBSN
