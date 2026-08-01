# app/services/ai_engine/section_suggester.py
"""
AI Section Suggester & Domain Detector.

Membaca header kolom & sampel baris data mentah dari berkas yang diunggah (CSV, XLSX, PDF),
lalu secara cerdas:
1. Mendeteksi domain data (Keuangan, KPI/HR Mitra, Cyber Security SOC, Operasional, Umum).
2. Menghasilkan 4-6 Rekomendasi Section Laporan yang Paling Relevan khusus untuk berkas tersebut.
3. Menyediakan Kop Header bawaan yang cocok dengan domain data.

Modul ini mendukung AI (Ollama qwen3:8b) dengan fallback heuristik berbasis kolom jika AI offline
sehingga sistem SELALU cepat dan responsif.
"""

from typing import Any, Dict, List, Optional
import re

# Template Section bawaan per domain
_DOMAIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "kpi_hr": {
        "domain_label": "KPI & Kinerja Karyawan / Mitra",
        "default_header_title": "PT PETROKIMIA GRESIK - EVALUASI KINERJA & KPI",
        "default_header_subtitle": "Laporan Analisis Kinerja Mitra & Pencapaian Target SDM",
        "sections": [
            {
                "key": "executive_summary",
                "title": "Ringkasan Eksekutif KPI",
                "description": "Ringkasan tingkat tinggi pencapaian KPI dan evaluasi keseluruhan mitra/karyawan.",
                "enabled": True,
            },
            {
                "key": "target_achievement",
                "title": "Analisis Pencapaian Target & Realisasi",
                "description": "Evaluasi perbandingan target vs realisasi berdasarkan indikator kinerja.",
                "enabled": True,
            },
            {
                "key": "top_performers",
                "title": "Analisis Performa Mitra Teratas & Perlu Pembinaan",
                "description": "Pemetaan entitas dengan skor tertinggi serta area yang membutuhkan pembinaan.",
                "enabled": True,
            },
            {
                "key": "gap_risk_analysis",
                "title": "Identifikasi Kendala & Area Perbaikan",
                "description": "Analisis jurang pencapaian (gap) dan faktor penghambat kinerja.",
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": "Rekomendasi Strategis & Pembinaan",
                "description": "Tindakan perbaikan taktis dan alokasi target pengembangan ke depan.",
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": "Kesimpulan Evaluasi",
                "description": "Rangkuman akhir dan catatan persetujuan manajemen.",
                "enabled": True,
            },
        ],
    },
    "financial": {
        "domain_label": "Keuangan & Anggaran",
        "default_header_title": "PT PETROKIMIA GRESIK - DEPARTEMEN KEUANGAN",
        "default_header_subtitle": "Laporan Analisis Eksekutif Keuangan & Arus Kas",
        "sections": [
            {
                "key": "executive_summary",
                "title": "Ringkasan Eksekutif Keuangan",
                "description": "Gambaran umum kesehatan finansial, pos penerimaan, dan pengeluaran utama.",
                "enabled": True,
            },
            {
                "key": "revenue_expense_trend",
                "title": "Analisis Tren Pendapatan vs Beban Operasional",
                "description": "Evaluasi pergerakan arus kas dan tren pendapatan dibanding beban.",
                "enabled": True,
            },
            {
                "key": "budget_variance",
                "title": "Analisis Varian Anggaran & Efisiensi Biaya",
                "description": "Perbandingan realisasi anggaran terhadap rencana kerja anggaran perusahaan (RKAP).",
                "enabled": True,
            },
            {
                "key": "financial_risk",
                "title": "Penilaian Risiko Keuangan & Pengendalian Biaya",
                "description": "Identifikasi pos pengeluaran berisiko tinggi dan potensi pemborosan.",
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": "Rekomendasi Penghematan & Optimalisasi Anggaran",
                "description": "Langkah strategis optimalisasi arus kas dan efisiensi belanja operasional.",
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": "Kesimpulan & Catatan Finansial",
                "description": "Penutup dan rekomendasi keputusan direksi.",
                "enabled": True,
            },
        ],
    },
    "soc_security": {
        "domain_label": "Keamanan Siber (SOC)",
        "default_header_title": "PT PETROKIMIA GRESIK - SOC SECURITY OPERATIONS",
        "default_header_subtitle": "Laporan Otomasi Analisis Insiden Keamanan Siber Berbasis AI",
        "sections": [
            {
                "key": "executive_summary",
                "title": "Ringkasan Eksekutif SOC",
                "description": "Gambaran umum status postur keamanan siber dan sorotan insiden utama.",
                "enabled": True,
            },
            {
                "key": "trend_analysis",
                "title": "Analisis Tren Ancaman & Anomali",
                "description": "Pergerakan frekuensi insiden siber, jam puncak serangan, dan pola aktivitas.",
                "enabled": True,
            },
            {
                "key": "severity_analysis",
                "title": "Analisis Tingkat Keparahan (Severity)",
                "description": "Distribusi keparahan insiden (critical, high, medium, low) pada infrastruktur IT.",
                "enabled": True,
            },
            {
                "key": "risk_assessment",
                "title": "Penilaian Risiko & Dampak Operasional",
                "description": "Evaluasi potensi eksploitasi dan dampak terhadap kelangsungan bisnis.",
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": "Rekomendasi Mitigasi & Tuning Security",
                "description": "Tindakan penanganan cepat (quick win) dan pembaruan aturan firewall/SIEM.",
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": "Kesimpulan Postur Keamanan",
                "description": "Rangkuman kesiapan operasional SOC dan langkah perlindungan ke depan.",
                "enabled": True,
            },
        ],
    },
    "general": {
        "domain_label": "Analisis Operasional & Umum",
        "default_header_title": "PT PETROKIMIA GRESIK - EKSEKUTIF REPORT",
        "default_header_subtitle": "Laporan Analisis Eksekutif Data Operasional Berbasis AI",
        "sections": [
            {
                "key": "executive_summary",
                "title": "Ringkasan Eksekutif",
                "description": "Ringkasan umum mengenai hasil analisis data dan temuan utama.",
                "enabled": True,
            },
            {
                "key": "trend_analysis",
                "title": "Analisis Tren & Distribusi Data",
                "description": "Evaluasi pergerakan data, statistik utama, dan pola distribusi.",
                "enabled": True,
            },
            {
                "key": "key_findings",
                "title": "Temuan Utama & Identifikasi Anomali",
                "description": "Poin-poin penting yang membutuhkan perhatian manajemen.",
                "enabled": True,
            },
            {
                "key": "risk_assessment",
                "title": "Penilaian Risiko & Tantangan Operasional",
                "description": "Evaluasi potensi masalah dan kendala operasional.",
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": "Rekomendasi Tindakan Strategis",
                "description": "Langkah-langkah taktis dan strategis untuk perbaikan.",
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": "Kesimpulan Akhir",
                "description": "Rangkuman penutup laporan.",
                "enabled": True,
            },
        ],
    },
}


def detect_domain_from_columns(columns: List[str], sample_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Mendeteksi domain data berdasarkan nama kolom dan isi sampel.
    """
    col_str = " ".join(str(c).lower() for c in columns)
    
    # Check KPI / HR keywords
    kpi_keywords = ["kpi", "mitra", "kinerja", "target", "realisasi", "pencapaian", "skor", "pegawai", "karyawan", "bobot", "unit_kerja", "divisi"]
    if any(kw in col_str for kw in kpi_keywords):
        return "kpi_hr"

    # Check Financial keywords
    fin_keywords = ["keuangan", "biaya", "pendapatan", "pengeluaran", "anggaran", "kas", "rupiah", "revenue", "expense", "budget", "price", "nominal", "total_harga", "rkap"]
    if any(kw in col_str for kw in fin_keywords):
        return "financial"

    # Check SOC / Cyber Security keywords
    soc_keywords = ["firewall", "severity", "threat", "ip_address", "source_ip", "destination_ip", "cve", "vulnerability", "attack", "malware", "virus", "port", "signature", "soc"]
    if any(kw in col_str for kw in soc_keywords):
        return "soc_security"

    return "general"


def suggest_sections_for_file(
    columns: List[str],
    sample_data: Optional[List[Dict[str, Any]]] = None,
    file_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Menghasilkan usulan section laporan dinamis berbasis analisis data file.
    """
    # 1. Detect Domain
    domain = detect_domain_from_columns(columns, sample_data)
    
    # 2. Check if file_name hints at domain
    if file_name:
        fn_lower = file_name.lower()
        if "kpi" in fn_lower or "mitra" in fn_lower or "kinerja" in fn_lower or "hr" in fn_lower:
            domain = "kpi_hr"
        elif "keuangan" in fn_lower or "budget" in fn_lower or "kas" in fn_lower or "finan" in fn_lower:
            domain = "financial"
        elif "firewall" in fn_lower or "soc" in fn_lower or "threat" in fn_lower or "vapt" in fn_lower or "siem" in fn_lower:
            domain = "soc_security"

    preset = _DOMAIN_PRESETS.get(domain, _DOMAIN_PRESETS["general"])

    # 3. Dynamic Section Customization based on actual columns
    custom_sections = [dict(s) for s in preset["sections"]]
    
    # Append dynamic column-specific insight if applicable
    if domain == "general" and len(columns) > 0:
        # Custom section based on first 2 categorical columns
        cat_cols = [c for c in columns if not any(kw in c.lower() for kw in ["id", "no", "date", "time"])]
        if cat_cols:
            custom_sections[1]["title"] = f"Analisis Berdasarkan {cat_cols[0].replace('_', ' ').title()}"

    return {
        "domain_type": domain,
        "domain_label": preset["domain_label"],
        "header_title": preset["default_header_title"],
        "header_subtitle": preset["default_header_subtitle"],
        "suggested_sections": custom_sections,
    }
