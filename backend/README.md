# AI Security Analysis & Reporting Platform - Backend
### Sistem Otomasi Report Bulanan SOC Berbasis AI (Local LLM) — PT Petrokimia Gresik
Departemen Mitra Bisnis Layanan TI — Divisi Infrastruktur

Repositori ini berisi kode backend berbasis **FastAPI (Python)** untuk memproses data log keamanan, mengurainya secara otomatis, memicu analisis naratif siber menggunakan model AI lokal **Qwen3-8B (Ollama)**, memformat grafik Plotly, dan mengekspor hasilnya menjadi berkas PDF (WeasyPrint) & PowerPoint (python-pptx).

---

## 1. Prasyarat Sistem (Prerequisites)
Sebelum menjalankan backend, pastikan perangkat Anda sudah terpasang:
* **Python** (Versi 3.11 atau 3.12)
* **Git** (Versi terbaru)
* **Docker & Docker Desktop** (Untuk menjalankan database PostgreSQL secara otomatis)
* **Ollama** (Untuk menjalankan model AI lokal Qwen)

---

## 2. Setup Awal Lokal (Windows PowerShell)

Ikuti langkah demi langkah berikut untuk mengaktifkan environment lokal Anda:

### A. Aktivasi Virtual Environment & Install Dependencies
1. Masuk ke direktori backend:
   ```powershell
   cd d:\PKG-Intern\backend
   ```
2. Buat Virtual Environment:
   ```powershell
   python -m venv venv
   ```
3. Aktifkan Virtual Environment:
   ```powershell
   # Jika muncul error terkait ExecutionPolicy, jalankan ini sekali:
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   
   # Aktifkan venv:
   .\venv\Scripts\Activate.ps1
   ```
   *(Tanda `(venv)` akan muncul di depan prompt terminal Anda)*
4. Pasang library Python:
   ```powershell
   pip install -r requirements.txt
   ```

### B. Konfigurasi Environment Variables
Salin berkas template `.env.example` menjadi `.env` di folder root backend:
```powershell
cp .env.example .env
```
Secara default, `.env` sudah dikonfigurasikan menggunakan database **SQLite** lokal (`sqlite:///./sql_app.db`) untuk kemudahan pengujian tanpa Docker. Jika ingin menggunakan PostgreSQL, silakan aktifkan baris PostgreSQL di dalam berkas `.env` Anda.

### C. Generate Berkas Log Dummy untuk Pengujian
Jalankan skrip pembentuk log tiruan siber agar memiliki berkas pengujian:
```powershell
python tests/generate_dummy_files.py
```
Berkas berikut akan terbentuk di folder `tests/dummy_data/`:
* `firewall_data.csv` (log firewall terblokir)
* `email_data.json` (log spam/phishing)
* `vapt_data.xlsx` (log celah keamanan/vulnerability)

---

## 3. Migrasi Skema Database (Alembic)
Karena folder migrasi `alembic` sudah terbuat, Anda hanya perlu menerapkan migrasi ke database lokal Anda dengan mengetik:
```powershell
alembic upgrade head
```
Perintah ini akan membuat berkas database SQLite `sql_app.db` (atau tabel PostgreSQL jika docker menyala) dengan tabel `users`, `reports`, dan `datasources`.

---

## 4. Cara Menjalankan Server Backend

### Opsi A: Jalankan di Host Lokal (Sangat Direkomendasikan untuk Dev)
Jalankan development server FastAPI dengan Uvicorn:
```powershell
uvicorn app.main:app --reload --port 8000
```
Server akan aktif di alamat: **[http://localhost:8000](http://localhost:8000)**

### Opsi B: Jalankan Menggunakan Docker Compose (Production-ready)
Jika ingin menjalankan database PostgreSQL 16 dan Backend secara terisolasi di dalam container:
1. Buka aplikasi **Docker Desktop**.
2. Jalankan perintah:
   ```powershell
   docker compose up --build
   ```

---

## 5. Konfigurasi Model AI Lokal (Ollama)
Aplikasi ini memproses data siber lokal menggunakan Ollama.
1. Jalankan aplikasi Ollama di komputer Anda (biasanya otomatis aktif di system tray).
2. Unduh model Qwen siber:
   ```powershell
   ollama pull qwen3:8b
   ```
3. Pastikan daemon Ollama aktif di port 11434 dengan mengakses: **[http://localhost:11434](http://localhost:11434)**

---

## 6. Pengujian Fitur via Swagger UI

Buka browser Anda dan akses **[http://localhost:8000/docs](http://localhost:8000/docs)** untuk menguji API secara interaktif:

1. **Registrasi User**: Panggil `POST /api/v1/auth/register` dengan username dan password Anda.
2. **Dapatkan Token JWT**: Lakukan login di `POST /api/v1/auth/login`. Salin string `access_token` hasil respon.
3. **Autentikasi Swagger**: Klik tombol **Authorize** di pojok kanan atas Swagger UI, tempel token Anda, lalu klik Authorize.
4. **Upload Data Log**: Gunakan berkas di `tests/dummy_data/` untuk diunggah pada `POST /api/v1/upload/`. Masukkan param data_type (contoh: `firewall`). Salin `id` laporan yang dikembalikan.
5. **Validation Summary**: Panggil `GET /api/v1/validation/summary/{report_id}` untuk melihat data validasi kualitas log siber.
6. **Generate AI Report**: Panggil `POST /api/v1/analysis/generate/{report_id}`. API akan menyuruh Ollama merumuskan narasi siber dalam Bahasa Indonesia.
7. **Unduh PDF & PPTX**: Panggil `GET /api/v1/history/{report_id}/pdf` atau `GET /api/v1/history/{report_id}/pptx` untuk mengunduh laporan PDF Petro atau slide presentasi PowerPoint Anda!
