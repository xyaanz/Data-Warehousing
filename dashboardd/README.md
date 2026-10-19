# Dashboard Indikator Pendidikan & IPM Jawa Timur 2025

Dashboard Streamlit yang mengintegrasikan tiga sumber data (IPM, rata-rata lama sekolah, serta jumlah sekolah/guru/murid) untuk 38 kabupaten/kota di Jawa Timur.

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

Proses ETL ada di notebook `DataWarehouse_Datmin.ipynb` (dijalankan di Google Colab).

## Isi repositori

```
app.py                         Aplikasi Streamlit
peta.py                        Modul peta Leaflet (gelembung bernomor + batas wilayah)
requirements.txt               Daftar library
data/indikator_jatim.csv       Data cadangan (dipakai bila MotherDuck tidak tersedia)
data/jatim_kabkota.geojson     Batas 38 kabupaten/kota Jawa Timur untuk peta
.streamlit/secrets.toml.example  Contoh format token (bukan token asli)
.gitignore                     Mencegah secrets.toml ikut ter-upload
```

## Peta sebaran

Tab pertama dashboard menampilkan peta Leaflet:

- Satu gelembung = satu kabupaten/kota. Gelembung yang berdekatan menyatu saat peta di-zoom out (jumlahnya dijumlahkan) dan terpecah lagi saat di-zoom in.
- Indikator yang bisa dipilih: jumlah sekolah, guru, atau murid, untuk semua jenjang atau per jenjang (SD, SMP, SMA). Wilayah juga bisa diwarnai menurut IPM.
- Klik gelembung untuk melihat rincian wilayah. Filter di sidebar ikut berlaku pada peta.
- Batasan: data yang dipetakan adalah agregat per kabupaten/kota, bukan titik lokasi sekolah. Peta titik sekolah membutuhkan data koordinat per sekolah.
- Peta memuat pustaka Leaflet dari unpkg dan peta dasar dari OpenStreetMap, sehingga membutuhkan koneksi internet.

## Menjalankan di komputer sendiri

Butuh Python 3.10 atau lebih baru.

```bash
git clone https://github.com/<username>/<nama-repo>.git
cd <nama-repo>

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Browser akan terbuka di `http://localhost:8501`.

Tanpa token, dashboard otomatis memakai `data/indikator_jatim.csv`. Sidebar menampilkan **Sumber data: CSV lokal**.

### (Opsional) Terhubung ke MotherDuck

1. Salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`.
2. Isi `MOTHERDUCK_TOKEN` dengan token milik sendiri (MotherDuck, Settings, Access Tokens).
3. Jalankan ulang `streamlit run app.py`. Sidebar akan menampilkan **Sumber data: MotherDuck**.

Klien DuckDB harus versi 1.4.1 atau lebih baru agar kompatibel dengan MotherDuck.

## Deploy ke Streamlit Community Cloud

1. Buka https://share.streamlit.io lalu login dengan akun GitHub.
2. Pilih **Create app**, lalu pilih repositori ini.
3. Isi **Main file path** dengan `app.py` (atau `dashboard/app.py` bila file berada di dalam folder `dashboard/`).
4. Buka **Advanced settings, Secrets**, lalu isi:
   ```toml
   MOTHERDUCK_TOKEN = "token_anda"
   ```
5. Klik **Deploy**. Pengunjung cukup membuka tautan aplikasi, tidak perlu token.

## Sumber data

- IPM 2025 per kabupaten/kota: **[isi sumber resmi dan tahun akses]**
- Rata-rata lama sekolah 2025: **[isi sumber resmi dan tahun akses]**
- Jumlah sekolah, guru, dan murid (SD, SMP, SMA): **[isi sumber resmi dan tahun akses]**
- Batas wilayah kabupaten/kota (untuk peta): Badan Pusat Statistik (BPS), World Food Programme, dan OCHA ROAP, disebarkan melalui geoBoundaries (gbOpen, IDN ADM2, tahun batas 2020, lisensi CC BY 3.0 IGO). Geometri disederhanakan untuk tampilan web.

## Catatan

- Jangan pernah meng-commit token. File `secrets.toml` sudah masuk `.gitignore`.
- Korelasi IPM dan rata-rata lama sekolah tinggi sebagian karena RLS adalah komponen penyusun IPM, sehingga tidak boleh ditafsirkan sebagai hubungan sebab-akibat.
