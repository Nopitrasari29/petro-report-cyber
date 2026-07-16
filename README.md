# Platform Pelaporan Keamanan Siber Berbasis AI (SOC Platform)
### PT Petrokimia Gresik · Departemen Mitra Bisnis Layanan TI

Aplikasi ini merupakan platform otomasi pembuatan laporan keamanan bulanan *Security Operations Center* (SOC) berbasis kecerdasan buatan (AI) menggunakan model bahasa lokal (**Ollama Qwen**). Platform ini terdiri dari dua bagian utama:
1. **Backend (FastAPI)**: Memproses data log (firewall, email, vulnerability), menjalankan narasi analisis AI, memetakan grafik Plotly, serta mengekspor hasil ke format PDF & PowerPoint.
2. **Frontend (Next.js)**: Menyediakan antarmuka premium dinamis dengan dukungan multibahasa (Inggris & Indonesia), dashboard analisis riwayat, penyunting narasi, dan wizard generasi laporan.

---

## 🏛️ Arsitektur & Layanan Default

| Komponen | Teknologi | Port Default | URL Akses |
| :--- | :--- | :--- | :--- |
| **Frontend** | Next.js (React / TS) | `3000` | http://localhost:3000 |
| **Backend** | FastAPI (Python) | `8000` | http://localhost:8000 |
| **Dokumentasi API** | OpenAPI (Swagger) | `8000` | http://localhost:8000/docs |
| **AI LLM Engine** | Ollama | `11434` | http://localhost:11434 |
| **Database** | SQLite / PostgreSQL | - | Lokal (`sql_app.db`) / Docker compose |

---

## 🚀 Alur Lengkap Menjalankan Sistem

Ikuti 3 tahapan utama di bawah ini secara berurutan untuk menjalankan sistem secara lokal di mesin Anda.

### TAHAP 1: Konfigurasi AI Engine Lokal (Ollama)
Sistem ini membutuhkan model AI lokal agar data log keamanan perusahaan tetap aman berada di infrastruktur internal.
1. Pastikan aplikasi **Ollama** telah terpasang dan sedang berjalan (cek ikon Ollama di *system tray* atau taskbar).
2. Jalankan perintah berikut di PowerShell/Command Prompt Anda untuk mengunduh model AI Qwen:
   ```bash
   ollama pull qwen3:8b
   ```
3. Uji apakah Ollama telah berjalan dengan baik dengan membuka tautan **[http://localhost:11434](http://localhost:11434)** di browser Anda.

---

### TAHAP 2: Menjalankan Backend (FastAPI)
Buka terminal baru (PowerShell direkomendasikan) di root proyek `d:\PKG-Intern`:

1. **Masuk ke folder backend**:
   ```powershell
   cd d:\PKG-Intern\backend
   ```

2. **Buat & Aktifkan Virtual Environment**:
   ```powershell
   # Buat environment python
   python -m venv venv

   # Jika muncul kendala execution policy di Windows, jalankan ini terlebih dahulu:
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

   # Aktifkan virtual environment
   .\venv\Scripts\Activate.ps1
   ```
   *(Akan muncul tanda `(venv)` di baris input terminal Anda).*

3. **Instal Library / Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Konfigurasi Environment (`.env`)**:
   Salin berkas template konfigurasi awal:
   ```powershell
   cp .env.example .env
   ```
   *Secara bawaan, `.env` sudah menggunakan SQLite lokal (`sql_app.db`) sehingga Anda bisa langsung menggunakannya tanpa konfigurasi tambahan.*

5. **Generate Berkas Log Sampel (Dummy) untuk Pengujian**:
   ```powershell
   python tests/generate_dummy_files.py
   ```
   *Perintah ini akan membuat berkas dummy log di `tests/dummy_data/` yang siap diunggah.*

6. **Terapkan Migrasi Skema Database**:
   ```powershell
   alembic upgrade head
   ```

7. **Jalankan Server Backend**:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```
   *Tunggu hingga terminal menampilkan log `INFO: Uvicorn running on http://localhost:8000`.*

---

### TAHAP 3: Menjalankan Frontend (Next.js)
Buka terminal baru (PowerShell) lainnya dan biarkan terminal backend tetap berjalan:

1. **Masuk ke folder frontend**:
   ```powershell
   cd d:\PKG-Intern\frontend
   ```

2. **Instal Package Dependencies**:
   ```powershell
   npm install
   ```

3. **Jalankan Server Development Frontend**:
   ```powershell
   npm run dev
   ```
   *Frontend akan aktif dalam mode development. Buka **[http://localhost:3000](http://localhost:3000)** di browser Anda untuk masuk ke sistem.*

---

## 🛠️ Perintah Opsional Lainnya

### Menguji Versi Produksi (Production Build) Frontend
Untuk menguji hasil kompilasi optimal produksi di sisi Frontend:
```powershell
# Jalankan kompilasi TypeScript & Next.js
npm run build

# Jalankan server hasil build produksi
npm run start
```

### Menggunakan Database PostgreSQL via Docker (Opsional)
Jika Anda ingin menggunakan PostgreSQL 16 di lingkungan Docker:
1. Pastikan **Docker Desktop** Anda aktif.
2. Di dalam folder `backend`, jalankan perintah:
   ```powershell
   docker compose up --build
   ```
3. Ubah konfigurasi database di berkas `.env` backend Anda untuk mengarah ke PostgreSQL (sesuaikan parameter koneksi PostgreSQL).
