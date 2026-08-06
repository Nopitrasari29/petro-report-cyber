# app/services/ai_engine/section_suggester.py
"""
AI Section Suggester & Domain Detector.

Membaca header kolom & sampel baris data mentah dari berkas yang diunggah (CSV, XLSX, PDF),
lalu:
1. Mendeteksi domain data (Keuangan, KPI/HR Mitra, Cyber Security SOC, Operasional, Umum) —
   heuristik berbasis nama kolom & nama berkas, dipakai juga sebagai hint domain untuk AI.
2. Mencoba memanggil AI (Ollama qwen3:8b) untuk mengusulkan 5-8 section laporan paling relevan
   BESERTA URUTANNYA — bebas mengusulkan judul section di luar daftar umum bila data menuntutnya
   (lihat `OllamaClient.suggest_sections`).
3. Kalau AI offline/gagal/timeout, fallback ke preset section heuristik per-domain di bawah
   (4 preset domain, masing-masing 6 section tetap) supaya sistem SELALU cepat dan responsif.
4. Menyediakan Kop Header bawaan yang cocok dengan domain data terdeteksi.
"""

from typing import Any, Dict, List, Optional
import re

from app.services.ai_engine.data_profiler import (
    compute_statistics,
    compute_schema_summary,
    format_statistics_as_text,
    format_schema_as_text,
)
from app.services.ai_engine.ollama_client import ollama_client

# Template Section bawaan per domain
_DOMAIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "procurement": {
        "domain_label": "Pengadaan Barang & Jasa",
        "default_header_title": "PT PETROKIMIA GRESIK - PENGADAAN BARANG & JASA",
        "default_header_subtitle": "Laporan Analisis Eksekutif Pengadaan & Manajemen Vendor",
        "sections": [
            {
                "key": "executive_summary",
                "title": "Ringkasan Eksekutif Pengadaan",
                "description": "Ringkasan tingkat tinggi volume, nilai, dan status pengadaan periode ini.",
                "enabled": True,
            },
            {
                "key": "procurement_method_trend",
                "title": "Analisis Metode & Tren Pengadaan",
                "description": "Evaluasi distribusi metode pengadaan (e-katalog, tender, penunjukan langsung, dst).",
                "enabled": True,
            },
            {
                "key": "vendor_analysis",
                "title": "Analisis Vendor & Pemasok Utama",
                "description": "Pemetaan vendor/pemasok dengan volume atau nilai transaksi tertinggi.",
                "enabled": True,
            },
            {
                "key": "gap_risk_analysis",
                "title": "Identifikasi Kendala & Risiko Pengadaan",
                "description": "Analisis dokumen bermasalah/dibatalkan dan risiko keterlambatan proses.",
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": "Rekomendasi Perbaikan Proses Pengadaan",
                "description": "Tindakan perbaikan taktis untuk efisiensi dan transparansi pengadaan ke depan.",
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": "Kesimpulan Pengadaan",
                "description": "Rangkuman akhir dan catatan persetujuan manajemen.",
                "enabled": True,
            },
        ],
    },
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


# Kata kunci per domain, dipakai detect_domain_from_columns via SISTEM SKOR (jumlah kata
# kunci yang cocok), BUKAN first-match-wins seperti sebelumnya. BUG YANG DIPERBAIKI: dengan
# first-match-wins, data pengadaan/vendor yang kebetulan punya kolom "Unit_Kerja"/"Departemen"
# (lazim ada di data apa pun sbg penanggung jawab) langsung salah terklasifikasi "kpi_hr"
# karena "unit_kerja" ada di daftar kpi_keywords DAN dicek PALING AWAL — walau sinyal
# pengadaan (vendor/tender/pengadaan) jauh lebih banyak & lebih spesifik. Sistem skor
# memilih domain dengan kecocokan TERBANYAK, jadi sinyal yang lebih kuat/spesifik menang,
# bukan sekadar domain mana yang kebetulan dicek duluan.
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "procurement": ["vendor", "tender", "pengadaan", "purchase", "po_number", "supplier",
                    "penunjukan_langsung", "e-katalog", "e_katalog", "kontrak", "rfq", "rfp",
                    "procurement", "pembelian", "pemasok", "barang_jasa", "nilai_kontrak"],
    "kpi_hr": ["kpi", "mitra", "kinerja", "target", "realisasi", "pencapaian", "skor",
               "pegawai", "karyawan", "bobot", "unit_kerja", "divisi"],
    "financial": ["keuangan", "biaya", "pendapatan", "pengeluaran", "anggaran", "kas",
                  "rupiah", "revenue", "expense", "budget", "price", "nominal",
                  "total_harga", "rkap"],
    "soc_security": ["firewall", "severity", "threat", "ip_address", "source_ip",
                      "destination_ip", "cve", "vulnerability", "attack", "malware",
                      "virus", "port", "signature", "soc"],
}


def detect_domain_from_columns(columns: List[str], sample_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Mendeteksi domain data berdasarkan nama kolom — domain dengan JUMLAH kata kunci yang
    cocok TERBANYAK yang menang (bukan domain pertama yang punya minimal 1 kecocokan).
    """
    col_str = " ".join(str(c).lower() for c in columns)
    scores = {domain: sum(1 for kw in kws if kw in col_str) for domain, kws in _DOMAIN_KEYWORDS.items()}
    best_domain = max(scores, key=scores.get)
    if scores[best_domain] == 0:
        return "general"
    return best_domain


def suggest_sections_for_file(
    columns: List[str],
    sample_data: Optional[List[Dict[str, Any]]] = None,
    file_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Menghasilkan usulan section laporan dinamis berbasis analisis data file. Mencoba jalur AI
    dulu (butuh `sample_data` berisi data yang cukup representatif — idealnya SELURUH baris yang
    sudah di-parse, bukan cuma beberapa baris, supaya statistik yang dikirim ke AI akurat);
    kalau AI offline/gagal/timeout/hasil tidak valid, fallback ke preset heuristik per-domain
    supaya upload file tetap cepat & tidak pernah error.
    """
    # 1. Detect Domain (dipakai sbg hint utk AI + fallback key preset & label domain)
    domain = detect_domain_from_columns(columns, sample_data)

    # 2. Check if file_name hints at domain — procurement dicek PALING AWAL (sebelum kpi_hr)
    # karena nama file pengadaan nyata (mis. "Data Dummy PKG - Pengadaan Barang Jasa.pdf")
    # ditemukan salah terklasifikasi kpi_hr sebelum ini.
    if file_name:
        fn_lower = file_name.lower()
        if "pengadaan" in fn_lower or "procurement" in fn_lower or "vendor" in fn_lower or "tender" in fn_lower:
            domain = "procurement"
        elif "kpi" in fn_lower or "mitra" in fn_lower or "kinerja" in fn_lower or "hr" in fn_lower:
            domain = "kpi_hr"
        elif "keuangan" in fn_lower or "budget" in fn_lower or "kas" in fn_lower or "finan" in fn_lower:
            domain = "financial"
        elif "firewall" in fn_lower or "soc" in fn_lower or "threat" in fn_lower or "vapt" in fn_lower or "siem" in fn_lower:
            domain = "soc_security"

    preset = _DOMAIN_PRESETS.get(domain, _DOMAIN_PRESETS["general"])

    # 3. Coba usulan AI dulu — grounded pada skema & statistik terhitung (bukan data mentah)
    ai_sections = None
    if sample_data:
        try:
            schema_text = format_schema_as_text(compute_schema_summary(sample_data))
            stats_text = format_statistics_as_text(compute_statistics(sample_data, domain))
            ai_sections = ollama_client.suggest_sections(
                schema_text=schema_text,
                stats_text=stats_text,
                file_name=file_name,
                domain_hint=preset["domain_label"],
            )
        except Exception as e:
            print(f"[SECTION SUGGESTER] Jalur AI gagal, fallback ke preset heuristik: {e}")
            ai_sections = None

    if ai_sections:
        return {
            "domain_type": domain,
            "domain_label": preset["domain_label"],
            "header_title": preset["default_header_title"],
            "header_subtitle": preset["default_header_subtitle"],
            "suggested_sections": ai_sections,
            "source": "ai",
        }

    # 4. Fallback: preset heuristik per-domain — field order/recommended/enabled diseragamkan
    # supaya BENTUKNYA SAMA dengan hasil AI di atas (frontend tidak perlu tahu jalur mana yang dipakai).
    custom_sections = []
    for idx, s in enumerate(preset["sections"]):
        item = dict(s)
        item.setdefault("order", idx)
        item.setdefault("recommended", True)
        item.setdefault("enabled", True)
        custom_sections.append(item)

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
        "source": "heuristic",
    }
