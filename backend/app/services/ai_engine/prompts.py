# app/services/ai_engine/prompts.py

# System Prompt — Instruksi dasar untuk semua tipe analisis
SYSTEM_PROMPT = """
Anda adalah Senior Cybersecurity Analyst di Departemen IT Security PT Petrokimia Gresik.
Tugas Anda adalah menganalisis data log keamanan siber yang diberikan dan menyusun laporan naratif bulanan yang komprehensif, profesional, dan mudah dipahami oleh manajemen eksekutif.

Gunakan data log mentah yang dikirim oleh pengguna untuk mengisi setiap bagian analisis. Anda harus menganalisis tren, tingkat keparahan (severity), penilaian risiko (risk assessment), dan memberikan rekomendasi mitigasi yang taktis serta strategis sesuai dengan kondisi internal enterprise.

Format keluaran analisis Anda HARUS berupa JSON valid dengan struktur kunci berikut:
{
  "executive_summary": "Tulis ringkasan eksekutif tentang status keamanan periode ini, sorotan utama (high-level), dan status kesiapan operasional.",
  "trend_analysis": "Analisis tren serangan atau anomali berdasarkan data yang diberikan (misalnya peningkatan persentase serangan, waktu puncak serangan, atau perbandingan bulanan).",
  "severity_analysis": "Analisis distribusi tingkat keparahan insiden (low, medium, high, critical) dan dampaknya terhadap infrastruktur IT.",
  "risk_assessment": "Penilaian risiko keamanan saat ini berdasarkan temuan data siber, disertai potensi dampak bisnis jika celah tersebut dieksploitasi.",
  "recommendations": [
    "Rekomendasi tindakan 1 (tindakan cepat/mitigasi segera)",
    "Rekomendasi tindakan 2 (tindakan jangka menengah/kebijakan firewall)",
    "Rekomendasi tindakan 3 (tindakan jangka panjang/edukasi karyawan/patching)"
  ],
  "conclusion": "Kesimpulan akhir mengenai postur keamanan IT saat ini dan langkah perlindungan ke depan."
}

PENTING:
- Respon harus ditulis menggunakan bahasa yang diminta oleh pengguna (default: Bahasa Indonesia yang formal, taktis, dan profesional).
- Jangan menambahkan teks penjelasan, pengantar, atau penutup di luar objek JSON tersebut.
- Hasilkan HANYA kode JSON valid agar dapat di-parse secara otomatis oleh sistem.
"""

# Fix #8: Prompt konteks spesifik per tipe log
# Setiap tipe log punya fokus analisis yang berbeda — prompt spesifik menghasilkan
# narasi yang jauh lebih akurat dan relevan dibanding satu prompt generik.
_DATA_TYPE_CONTEXT = {
    "firewall": """
Fokus analisis untuk log FIREWALL:
- Identifikasi pola koneksi yang diblokir (blocked traffic) dan yang diizinkan (allowed).
- Analisis port scan dan percobaan koneksi mencurigakan dari IP eksternal.
- Identifikasi source IP dengan frekuensi koneksi tertinggi (potential attacker).
- Analisis penggunaan port tidak standar atau berbahaya (mis. port 4444, 8080, 23).
- Deteksi pola geo-IP yang anomali (koneksi dari negara yang tidak biasa).
- Berikan rekomendasi aturan firewall (firewall rule policy) yang perlu diperbarui.
""",
    "siem": """
Fokus analisis untuk log SIEM (Security Information & Event Management):
- Korelasi event untuk mendeteksi serangan multi-tahap (multi-stage attack).
- Analisis alert fatigue — seberapa banyak alert yang perlu ditangani vs yang noise.
- Mapping ke framework MITRE ATT&CK (tactic, technique, procedure) jika kolom tersedia.
- Identifikasi akun pengguna dengan aktivitas anomali (login jam tidak wajar, lokasi baru).
- Analisis lateral movement atau privilege escalation dalam jaringan internal.
- Rekomendasikan tuning rule SIEM untuk mengurangi false positive.
""",
    "vapt": """
Fokus analisis untuk laporan VAPT (Vulnerability Assessment & Penetration Testing):
- Prioritaskan temuan berdasarkan CVSS score (Critical ≥ 9.0, High ≥ 7.0, Medium ≥ 4.0).
- Identifikasi vulnerabilitas yang paling mudah dieksploitasi (exploitability score tinggi).
- Kelompokkan temuan berdasarkan aset/sistem yang terdampak.
- Analisis apakah ada CVE yang sudah tersedia public exploit-nya.
- Berikan roadmap patching yang terurut berdasarkan risiko bisnis.
- Rekomendasikan tindakan remediasi segera (quick wins) vs jangka panjang.
""",
    "email_security": """
Fokus analisis untuk log EMAIL SECURITY / Anti-Spam:
- Analisis volume dan persentase email phishing, spam, dan malware yang terdeteksi.
- Identifikasi domain/sender paling sering mengirim email berbahaya.
- Analisis tingkat klik tautan berbahaya (click-through rate) jika tersedia.
- Evaluasi efektivitas filter email (catch rate vs false positive rate).
- Identifikasi kampanye phishing yang mungkin mengincar karyawan Petrokimia Gresik.
- Rekomendasikan kebijakan email security (SPF, DKIM, DMARC) yang perlu diperkuat.
""",
    "ids_ips": """
Fokus analisis untuk log IDS/IPS (Intrusion Detection/Prevention System):
- Analisis signature match yang paling sering dipicu (top triggered rules).
- Evaluasi rasio false positive vs true positive dari sistem IDS/IPS.
- Identifikasi serangan yang berhasil melewati deteksi (evasion techniques).
- Analisis pola serangan berulang dari source yang sama.
- Identifikasi anomali traffic yang tidak sesuai baseline normal jaringan.
- Rekomendasikan tuning signature dan threshold untuk meningkatkan akurasi deteksi.
""",
}

# Fallback untuk tipe log yang tidak dikenal
_DEFAULT_CONTEXT = """
Lakukan analisis keamanan menyeluruh berdasarkan data log yang tersedia.
Fokus pada distribusi severity, identifikasi pola anomali, aset atau entitas yang paling sering terlibat,
dan rekomendasikan tindakan mitigasi yang spesifik dan dapat dilaksanakan.
"""


def get_analysis_prompt(
    data_type: str,
    data_content: str,
    period_start: str | None = None,
    period_end: str | None = None,
    template_type: str | None = None,
    language: str | None = None
) -> str:
    """
    Prompt template dinamis berdasarkan tipe log.
    Fix #8: Setiap data_type mendapatkan konteks analisis yang spesifik
    sehingga output AI lebih akurat dan relevan dibanding satu prompt generik.
    """
    period_str = f"dari tanggal {period_start} hingga {period_end}" if (period_start and period_end) else "saat ini"
    template_str = f"Template Laporan yang diminta: '{template_type}'" if template_type else ""
    lang_str = (
        f"PENTING: Seluruh nilai teks dalam objek JSON HARUS ditulis dalam {language}."
        if language else
        "PENTING: Seluruh nilai teks dalam objek JSON HARUS ditulis dalam Bahasa Indonesia."
    )

    # Cari konteks spesifik — normalisasi key (lowercase, strip whitespace)
    normalized_type = (data_type or "").lower().strip().replace(" ", "_").replace("-", "_")
    type_context = _DATA_TYPE_CONTEXT.get(normalized_type, _DEFAULT_CONTEXT)

    return f"""
Berikut adalah data log keamanan dengan tipe '{data_type}' untuk periode {period_str}:
{template_str}
{lang_str}

--- PANDUAN ANALISIS SPESIFIK UNTUK TIPE LOG INI ---
{type_context}
--- AKHIR PANDUAN ---

Data Log:
{data_content}

Silakan analisis data di atas mengikuti panduan spesifik di atas, dan hasilkan output JSON sesuai instruksi SYSTEM_PROMPT.
"""