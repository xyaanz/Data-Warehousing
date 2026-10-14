# Data Warehouse & Dashboard Pendidikan Jawa Timur 2025

Proyek Data Mining (Datmin) yang mengintegrasikan tiga sumber data (IPM, rata-rata lama sekolah, serta jumlah sekolah/guru/murid) untuk 38 kabupaten/kota di Jawa Timur. Hasil akhirnya adalah dashboard Streamlit.

## Arsitektur

```
Excel -> pandas -> DuckDB (raw -> dw, star schema) -> DuckLake -> MotherDuck -> Streamlit
```

| Komponen | Peran |
|---|---|
| pandas, openpyxl | Membaca dan membersihkan file Excel |
| DuckDB | Skema `raw` dan `dw` (dimensi + fakta), view, dan query |
| DuckLake | Lapisan lakehouse (Parquet + katalog metadata) |
| MotherDuck | DuckDB di cloud, sumber data dashboard |
| Streamlit, Plotly | Tampilan dashboard |

## Struktur repositori

```
dashboard/                       Aplikasi Streamlit (app.py, requirements.txt, data cadangan)
raw_data/                        Tiga file Excel sumber
duckdb_raw/                      Tiga database DuckDB hasil konversi data mentah
DataWarehouse_DatminA.ipynb      Notebook ETL: raw -> DuckDB -> DuckLake -> MotherDuck
```

## Menjalankan dashboard

Butuh Python 3.10 atau lebih baru.

```bash
git clone https://github.com/xyaanz/Data-Warehousing.git
cd Data-Warehousing/dashboard

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Tanpa token MotherDuck, dashboard otomatis memakai `dashboard/data/indikator_jatim.csv`. Sidebar menampilkan **Sumber data: CSV lokal**.

Untuk memakai MotherDuck, salin `dashboard/.streamlit/secrets.toml.example` menjadi `dashboard/.streamlit/secrets.toml`, lalu isi `MOTHERDUCK_TOKEN` dengan token milik sendiri. Klien DuckDB harus versi 1.4.1 atau lebih baru.

## Deploy ke Streamlit Community Cloud

1. Buka https://share.streamlit.io lalu login dengan akun GitHub.
2. Pilih **Create app** dan pilih repositori ini (repositori harus public).
3. Isi **Main file path** dengan `dashboard/app.py`.
4. Di **Advanced settings, Secrets**, isi:
   ```toml
   MOTHERDUCK_TOKEN = "token_anda"
   ```
5. Klik **Deploy**.

## Menjalankan ulang pipeline data

1. Buka `DataWarehouse_DatminA.ipynb` di Google Colab.
2. Unggah tiga file dari `raw_data/` ke folder `/content`.
3. Simpan token MotherDuck di Colab Secrets dengan nama `MOTHERDUCK_TOKEN`.
4. Jalankan semua sel dari atas. Jika versi DuckDB yang tercetak di bawah 1.4.1, pilih Runtime, Restart session, lalu jalankan ulang.

## Sumber data

- IPM 2025 per kabupaten/kota: **[isi sumber resmi dan tanggal akses]**
- Rata-rata lama sekolah 2025: **[isi sumber resmi dan tanggal akses]**
- Jumlah sekolah, guru, dan murid (SD, SMP, SMA): **[isi sumber resmi dan tanggal akses]**

## Catatan

- Jangan pernah meng-commit token. File `secrets.toml` sudah masuk `.gitignore`.
- Korelasi IPM dan rata-rata lama sekolah tinggi sebagian karena rata-rata lama sekolah adalah komponen penyusun IPM, sehingga tidak boleh ditafsirkan sebagai hubungan sebab-akibat.
