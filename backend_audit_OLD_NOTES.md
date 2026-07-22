# 🔍 Audit Backend: Section yang Masih Dummy / Belum Profesional

> Dokumen ini merangkum seluruh bagian backend & frontend yang masih menggunakan data statis (hardcoded), mock fallback, atau belum terintegrasi dengan data riil dari database / layanan eksternal.

---

## 🔴 KRITIS — Belum Berfungsi Sama Sekali

### 1. Export PDF — Hanya Bisa di Docker (WeasyPrint)
**File:** [`export_pdf.py`](file:///d:/PKG-Intern/backend/app/services/export_pdf.py#L6-L23)

WeasyPrint membutuhkan library sistem Linux (`gobject-2.0-0`) yang **tidak tersedia di Windows**. Artinya endpoint `/history/{id}/pdf` akan selalu `500 Internal Server Error` jika dijalankan di lokal Windows.

```python
if not WEASYPRINT_AVAILABLE:
    raise RuntimeError("Pustaka sistem WeasyPrint ... tidak ditemukan di sistem Windows Anda.")
```
**Impact:** Tombol "Export PDF" di halaman History/Detail tidak bisa digunakan di environment Windows lokal.

**Solusi:** Gunakan `reportlab` atau `xhtml2pdf` sebagai alternatif yang kompatibel Windows, atau integrasikan Docker.

---

### 2. Email Verification & Reset Password — Hanya Print ke Terminal
**File:** [`email.py`](file:///d:/PKG-Intern/backend/app/services/email.py#L35-L43)

Jika `SMTP_HOST` dan `SMTP_USERNAME` di `.env` kosong (kondisi default lokal), sistem **tidak mengirim email sungguhan**. Link verifikasi dan reset password hanya dicetak ke terminal log.

```python
if not mail_config:
    print(" [EMAIL MOCK] VERIFIKASI EMAIL PENDAFTARAN")
    print(f" Tautan Aktif: {link}")
    return  # ← tidak ada email yang dikirim
```
**Impact:** User yang mendaftar tidak akan menerima email verifikasi → tidak bisa login (karena `is_verified` harus `True`).

**Solusi:** Isi konfigurasi SMTP di `.env` (Gmail / Mailgun / SMTP server perusahaan), atau tambahkan mekanisme auto-verify untuk development mode.

---

## 🟠 PENTING — Data Sebagian Dummy / Hardcoded

### 3. Dashboard Stats — Persentase Perubahan Statis
**File:** [`dashboard.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/dashboard.py#L120)

Counter utama dashboard (Critical Incidents) memiliki `percentage_change` yang **di-hardcode** selamanya:

```python
"percentage_change": -12.0,  # Metrik statis relasional perbandingan
```
Tidak ada perhitungan perbandingan dengan bulan sebelumnya. Angka `-12.0%` selalu tampil di kartu dashboard meskipun data nyatanya berbeda.

---

### 4. Dashboard — Fallback Data Dummy Ketika DB Kosong
**File:** [`dashboard.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/dashboard.py#L74-L82)

Jika database belum memiliki laporan (baru install), chart Threat Trend menggunakan data hardcoded:

```python
labels = ["28 Jun", "5 Jul", "12 Jul", "19 Jul", "26 Jul"]
datasets = [
    {"label": "Critical", "data": [15, 25, 20, 18, 28]},
    ...
]
```
Dan severity distribution juga fallback ke angka statis:
```python
"total_events": total_events if total_events > 0 else 312,
"breakdown": ... else [{"severity": "Critical", "count": 122, ...}]
```

---

### 5. Dashboard — AI Generation Queue Dummy
**File:** [`dashboard.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/dashboard.py#L105-L114)

Jika tidak ada laporan yang sedang diproses, antrian digantikan dengan satu item placeholder statis:

```python
if not queue_list:
    queue_list = [{
        "report_name": "SOC Executive Summary - July 2026",
        "progress_percentage": 100,
        "status": "Completed",
        "timestamp": "8 Jul 2026, 10:30"
    }]
```
**Impact:** Antrean selalu terlihat "ada isinya" padahal kosong.

---

### 6. Analytics Stats — Semua Persentase Perubahan Hardcoded
**File:** [`analytics.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/analytics.py#L98-L119)

Seluruh `percentage_change` di halaman Analytics menggunakan angka statis yang tidak berdasarkan data nyata:

| Metrik | Nilai Hardcoded |
|---|---|
| Total Reports | `+18.2%` |
| SLA Met | `+5.6%` |
| AI Confidence Avg | `+4.6%` |
| Critical Incidents | `-12.0%` |
| High Risk Alerts | `-8.1%` |
| Severity changes | `12, 8, 3, 4, 6` |

**Impact:** Semua angka % perubahan di kartu-kartu Analytics tidak akurat.

---

### 7. Analytics — Fallback Source Quality Dummy
**File:** [`analytics.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/analytics.py#L40-L47)

Jika tabel DataSource kosong, sistem menggunakan data source tiruan:

```python
source_breakdown = [
    {"source": "SIEM Export", "score": 98},
    {"source": "Vulnerability XLSX", "score": 91},
    ...
]
```

---

### 8. Datasources — Sepenuhnya Diisi Data Mock saat DB Kosong
**File:** [`datasources.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/datasources.py#L12-L29)

Sumber data (`/datasources/`) menggunakan fungsi `init_mock_datasources()` yang **otomatis mengisi 7 baris data palsu** ke database saat tabel masih kosong:

```python
sources = [
    DataSource(name="Firewall Logs", ..., records_count=560320, data_quality=98),
    DataSource(name="Email Security", ..., records_count=320145, data_quality=96),
    ...
]
```
**Impact:** Data sumber yang tampil di dashboard bukan dari sistem nyata, melainkan dummy yang diisi otomatis.

---

### 9. Datasources Upload — Simulasi Saja, Tidak Parse File Sungguhan
**File:** [`datasources.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/datasources.py#L123-L127)

Endpoint upload datasource tidak benar-benar memproses/membaca file yang diunggah. Ia hanya menambahkan `12500` ke counter `records_count` secara manual:

```python
# Simulasi pembacaan baris log
ds.records_count += 12500
```

---

### 10. Analytics — AI Insight Summary Hardcoded
**File:** [`analytics.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/analytics.py#L133-L139)

Narasi ringkasan AI di halaman Analytics adalah teks statis yang tidak dihasilkan dari analisis data nyata:

```python
"ai_insight_summary": {
    "summary": "Analisis terintegrasi menunjukkan tren eskalasi insiden pada log...",
    "top_recommendations": [
        "Perkuat filter spam di email security",
        "Tingkatkan monitoring pada jalur VPN eksternal",
        "Jalankan validasi anomali terjadwal"
    ]
}
```

---

### 11. Report Model — Nilai Default Nama & Confidence Statis
**File:** [`report.py`](file:///d:/PKG-Intern/backend/app/models/report.py#L32-L35)

Kolom-kolom ini memiliki default yang bisa menyesatkan:

```python
ai_confidence = Column(Float, nullable=True, default=94.0)   # ← angka tetap, bukan dari AI
sla_met = Column(Boolean, default=True)                       # ← selalu dianggap SLA terpenuhi
created_by_name = Column(String, default="Rafika A.Z.K")      # ← nama hardcoded
```
`ai_confidence` tidak pernah diperbarui oleh mesin AI yang sebenarnya.

---

## 🟡 MINOR — Masih Perlu Diperhatikan

### 12. Chart Generator — Fallback Bar Chart Generic
**File:** [`chart_generator.py`](file:///d:/PKG-Intern/backend/app/services/chart_generator.py#L79)

Jika data log tidak memiliki kolom yang dikenali, chart generator menggunakan fallback bar chart generik dari 2 kolom pertama yang tersedia — bukan visualisasi keamanan yang bermakna.

---

### 13. Ollama AI Engine — Berjalan Lokal, Bisa Tidak Tersedia
**File:** [`ollama_client.py`](file:///d:/PKG-Intern/backend/app/services/ai_engine/ollama_client.py)

Analisis AI bergantung pada **Ollama yang berjalan di mesin lokal** dengan model `qwen3:8b` (berat ~5GB). Jika Ollama tidak running atau model belum diunduh, endpoint analisis akan error dan fallback ke pesan error:

```python
return {
    "executive_summary": "Gagal merumuskan ringkasan otomatis...",
    ...
}
```
**Impact:** Fitur inti AI Generate tidak bisa berjalan tanpa setup Ollama terlebih dahulu.

---

### 14. Settings — Disimpan ke File JSON Lokal, Bukan Database
**File:** [`settings.py`](file:///d:/PKG-Intern/backend/app/api/v1/endpoints/settings.py#L10)

Pengaturan sistem (AI model, template, storage, dll.) disimpan ke file `settings.json` di filesystem lokal, **bukan ke database**. Ini berarti:
- Settings akan hilang jika container di-restart ulang dengan volume baru
- Tidak ada multi-user settings (semua user berbagi satu config global)

---

## ✅ Sudah Berfungsi Secara Profesional

| Section | Status |
|---|---|
| Autentikasi (Login/Register/JWT) | ✅ Riil & aman |
| Google OAuth Login | ✅ Terintegrasi |
| Email Verification Logic | ✅ Berfungsi (jika SMTP dikonfigurasi) |
| Reset Password Flow | ✅ Berfungsi (jika SMTP dikonfigurasi) |
| Upload & Parsing File (CSV/XLSX/PDF) | ✅ Riil via ParserFactory |
| Threat Count dari Log Asli | ✅ Dihitung dari parsed_data |
| History CRUD (List/Detail/Delete) | ✅ Riil dari database |
| AI Analysis Engine (Ollama) | ✅ Terhubung (butuh Ollama running) |
| Export PPTX | ✅ Berfungsi (python-pptx) |
| Validation (Duplicate/Missing/Invalid) | ✅ Analisis riil dari parsed_data |
| Profile Update & Password Change | ✅ Riil ke database |

---

## 📋 Prioritas Perbaikan yang Disarankan

| # | Item | Prioritas | Estimasi Effort |
|---|---|---|---|
| 1 | SMTP Email Config (kirim email sungguhan) | 🔴 Tinggi | Rendah (konfigurasi .env saja) |
| 2 | PDF Export (pakai reportlab/xhtml2pdf) | 🔴 Tinggi | Sedang |
| 3 | Hapus data mock DataSources, ganti input manual | 🟠 Sedang | Rendah |
| 4 | Hitung percentage_change dari data historis nyata | 🟠 Sedang | Sedang |
| 5 | Update ai_confidence dari hasil Ollama sungguhan | 🟠 Sedang | Rendah |
| 6 | Pindahkan Settings ke tabel database | 🟡 Rendah | Sedang |
| 7 | AI Insight Analytics dari data riil | 🟡 Rendah | Tinggi |
