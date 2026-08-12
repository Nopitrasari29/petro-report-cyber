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
import logging
import re

from app.services.ai_engine.data_profiler import (
    compute_statistics,
    compute_schema_summary,
    format_statistics_as_text,
    format_schema_as_text,
)
from app.services.ai_engine.ollama_client import ollama_client

logger = logging.getLogger(__name__)

# Template Section bawaan per domain — title/description/default_header_* SEKARANG bilingual
# (id, en). BUG YANG DIPERBAIKI (dilaporkan user): dulu semuanya string tunggal hardcode Bahasa
# Indonesia, dipakai APA ADANYA terlepas dari bahasa yang diminta user di Report Settings —
# laporan berbahasa Inggris tetap dapat Kop Subtitle & judul section Indonesia. `_pick_lang()`
# di bawah memilih index [1] (en) kalau language=="english", selalu [0] (id) kalau tidak/kosong.
_DOMAIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "procurement": {
        "domain_label": ("Pengadaan Barang & Jasa", "Goods & Services Procurement"),
        "default_header_title": ("PT PETROKIMIA GRESIK - PENGADAAN BARANG & JASA", "PT PETROKIMIA GRESIK - GOODS & SERVICES PROCUREMENT"),
        "default_header_subtitle": ("Laporan Analisis Eksekutif Pengadaan & Manajemen Vendor", "Procurement & Vendor Management Executive Analysis Report"),
        "sections": [
            {
                "key": "executive_summary",
                "title": ("Ringkasan Eksekutif Pengadaan", "Procurement Executive Summary"),
                "description": ("Ringkasan tingkat tinggi volume, nilai, dan status pengadaan periode ini.", "High-level summary of procurement volume, value, and status for this period."),
                "enabled": True,
            },
            {
                "key": "procurement_method_trend",
                "title": ("Analisis Metode & Tren Pengadaan", "Procurement Method & Trend Analysis"),
                "description": ("Evaluasi distribusi metode pengadaan (e-katalog, tender, penunjukan langsung, dst).", "Evaluation of procurement method distribution (e-catalog, tender, direct appointment, etc)."),
                "enabled": True,
            },
            {
                "key": "vendor_analysis",
                "title": ("Analisis Vendor & Pemasok Utama", "Key Vendor & Supplier Analysis"),
                "description": ("Pemetaan vendor/pemasok dengan volume atau nilai transaksi tertinggi.", "Mapping of vendors/suppliers with the highest transaction volume or value."),
                "enabled": True,
            },
            {
                "key": "gap_risk_analysis",
                "title": ("Identifikasi Kendala & Risiko Pengadaan", "Procurement Constraint & Risk Identification"),
                "description": ("Analisis dokumen bermasalah/dibatalkan dan risiko keterlambatan proses.", "Analysis of problematic/cancelled documents and process delay risks."),
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": ("Rekomendasi Perbaikan Proses Pengadaan", "Procurement Process Improvement Recommendations"),
                "description": ("Tindakan perbaikan taktis untuk efisiensi dan transparansi pengadaan ke depan.", "Tactical improvement actions for future procurement efficiency and transparency."),
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": ("Kesimpulan Pengadaan", "Procurement Conclusion"),
                "description": ("Rangkuman akhir dan catatan persetujuan manajemen.", "Final summary and management approval notes."),
                "enabled": True,
            },
        ],
    },
    "kpi_hr": {
        "domain_label": ("KPI & Kinerja Karyawan / Mitra", "KPI & Employee/Partner Performance"),
        "default_header_title": ("PT PETROKIMIA GRESIK - EVALUASI KINERJA & KPI", "PT PETROKIMIA GRESIK - KPI & PERFORMANCE EVALUATION"),
        "default_header_subtitle": ("Laporan Analisis Kinerja Mitra & Pencapaian Target SDM", "Partner Performance & HR Target Achievement Analysis Report"),
        "sections": [
            {
                "key": "executive_summary",
                "title": ("Ringkasan Eksekutif KPI", "KPI Executive Summary"),
                "description": ("Ringkasan tingkat tinggi pencapaian KPI dan evaluasi keseluruhan mitra/karyawan.", "High-level summary of KPI achievement and overall partner/employee evaluation."),
                "enabled": True,
            },
            {
                "key": "target_achievement",
                "title": ("Analisis Pencapaian Target & Realisasi", "Target Achievement & Realization Analysis"),
                "description": ("Evaluasi perbandingan target vs realisasi berdasarkan indikator kinerja.", "Evaluation comparing target vs realization based on performance indicators."),
                "enabled": True,
            },
            {
                "key": "top_performers",
                "title": ("Analisis Performa Mitra Teratas & Perlu Pembinaan", "Top Performer & Coaching-Needed Partner Analysis"),
                "description": ("Pemetaan entitas dengan skor tertinggi serta area yang membutuhkan pembinaan.", "Mapping of entities with the highest scores and areas requiring coaching."),
                "enabled": True,
            },
            {
                "key": "gap_risk_analysis",
                "title": ("Identifikasi Kendala & Area Perbaikan", "Constraint & Improvement Area Identification"),
                "description": ("Analisis jurang pencapaian (gap) dan faktor penghambat kinerja.", "Analysis of achievement gaps and performance-hindering factors."),
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": ("Rekomendasi Strategis & Pembinaan", "Strategic & Coaching Recommendations"),
                "description": ("Tindakan perbaikan taktis dan alokasi target pengembangan ke depan.", "Tactical improvement actions and future development target allocation."),
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": ("Kesimpulan Evaluasi", "Evaluation Conclusion"),
                "description": ("Rangkuman akhir dan catatan persetujuan manajemen.", "Final summary and management approval notes."),
                "enabled": True,
            },
        ],
    },
    "financial": {
        "domain_label": ("Keuangan & Anggaran", "Finance & Budget"),
        "default_header_title": ("PT PETROKIMIA GRESIK - DEPARTEMEN KEUANGAN", "PT PETROKIMIA GRESIK - FINANCE DEPARTMENT"),
        "default_header_subtitle": ("Laporan Analisis Eksekutif Keuangan & Arus Kas", "Financial & Cash Flow Executive Analysis Report"),
        "sections": [
            {
                "key": "executive_summary",
                "title": ("Ringkasan Eksekutif Keuangan", "Financial Executive Summary"),
                "description": ("Gambaran umum kesehatan finansial, pos penerimaan, dan pengeluaran utama.", "Overview of financial health, key revenue, and expense items."),
                "enabled": True,
            },
            {
                "key": "revenue_expense_trend",
                "title": ("Analisis Tren Pendapatan vs Beban Operasional", "Revenue vs Operating Expense Trend Analysis"),
                "description": ("Evaluasi pergerakan arus kas dan tren pendapatan dibanding beban.", "Evaluation of cash flow movement and revenue trends compared to expenses."),
                "enabled": True,
            },
            {
                "key": "budget_variance",
                "title": ("Analisis Varian Anggaran & Efisiensi Biaya", "Budget Variance & Cost Efficiency Analysis"),
                "description": ("Perbandingan realisasi anggaran terhadap rencana kerja anggaran perusahaan (RKAP).", "Comparison of budget realization against the company's annual work budget plan (RKAP)."),
                "enabled": True,
            },
            {
                "key": "financial_risk",
                "title": ("Penilaian Risiko Keuangan & Pengendalian Biaya", "Financial Risk & Cost Control Assessment"),
                "description": ("Identifikasi pos pengeluaran berisiko tinggi dan potensi pemborosan.", "Identification of high-risk expense items and potential wastage."),
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": ("Rekomendasi Penghematan & Optimalisasi Anggaran", "Savings & Budget Optimization Recommendations"),
                "description": ("Langkah strategis optimalisasi arus kas dan efisiensi belanja operasional.", "Strategic steps for cash flow optimization and operating expenditure efficiency."),
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": ("Kesimpulan & Catatan Finansial", "Financial Conclusion & Notes"),
                "description": ("Penutup dan rekomendasi keputusan direksi.", "Closing remarks and board decision recommendations."),
                "enabled": True,
            },
        ],
    },
    "soc_security": {
        "domain_label": ("Keamanan Siber (SOC)", "Cyber Security (SOC)"),
        "default_header_title": ("PT PETROKIMIA GRESIK - SOC SECURITY OPERATIONS", "PT PETROKIMIA GRESIK - SOC SECURITY OPERATIONS"),
        "default_header_subtitle": ("Laporan Otomasi Analisis Insiden Keamanan Siber Berbasis AI", "AI-Powered Cyber Security Incident Analysis Automation Report"),
        "sections": [
            {
                "key": "executive_summary",
                "title": ("Ringkasan Eksekutif SOC", "SOC Executive Summary"),
                "description": ("Gambaran umum status postur keamanan siber dan sorotan insiden utama.", "Overview of cyber security posture status and key incident highlights."),
                "enabled": True,
            },
            {
                "key": "trend_analysis",
                "title": ("Analisis Tren Ancaman & Anomali", "Threat & Anomaly Trend Analysis"),
                "description": ("Pergerakan frekuensi insiden siber, jam puncak serangan, dan pola aktivitas.", "Movement of cyber incident frequency, peak attack hours, and activity patterns."),
                "enabled": True,
            },
            {
                "key": "severity_analysis",
                "title": ("Analisis Tingkat Keparahan (Severity)", "Severity Level Analysis"),
                "description": ("Distribusi keparahan insiden (critical, high, medium, low) pada infrastruktur IT.", "Distribution of incident severity (critical, high, medium, low) across IT infrastructure."),
                "enabled": True,
            },
            {
                "key": "risk_assessment",
                "title": ("Penilaian Risiko & Dampak Operasional", "Risk & Operational Impact Assessment"),
                "description": ("Evaluasi potensi eksploitasi dan dampak terhadap kelangsungan bisnis.", "Evaluation of exploitation potential and impact on business continuity."),
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": ("Rekomendasi Mitigasi & Tuning Security", "Mitigation & Security Tuning Recommendations"),
                "description": ("Tindakan penanganan cepat (quick win) dan pembaruan aturan firewall/SIEM.", "Quick-win response actions and firewall/SIEM rule updates."),
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": ("Kesimpulan Postur Keamanan", "Security Posture Conclusion"),
                "description": ("Rangkuman kesiapan operasional SOC dan langkah perlindungan ke depan.", "Summary of SOC operational readiness and future protection steps."),
                "enabled": True,
            },
        ],
    },
    "general": {
        "domain_label": ("Analisis Operasional & Umum", "General & Operational Analysis"),
        "default_header_title": ("PT PETROKIMIA GRESIK - EKSEKUTIF REPORT", "PT PETROKIMIA GRESIK - EXECUTIVE REPORT"),
        "default_header_subtitle": ("Laporan Analisis Eksekutif Data Operasional Berbasis AI", "AI-Powered Operational Data Executive Analysis Report"),
        "sections": [
            {
                "key": "executive_summary",
                "title": ("Ringkasan Eksekutif", "Executive Summary"),
                "description": ("Ringkasan umum mengenai hasil analisis data dan temuan utama.", "General summary of the data analysis results and key findings."),
                "enabled": True,
            },
            {
                "key": "trend_analysis",
                "title": ("Analisis Tren & Distribusi Data", "Trend & Data Distribution Analysis"),
                "description": ("Evaluasi pergerakan data, statistik utama, dan pola distribusi.", "Evaluation of data movement, key statistics, and distribution patterns."),
                "enabled": True,
            },
            {
                "key": "key_findings",
                "title": ("Temuan Utama & Identifikasi Anomali", "Key Findings & Anomaly Identification"),
                "description": ("Poin-poin penting yang membutuhkan perhatian manajemen.", "Key points that require management attention."),
                "enabled": True,
            },
            {
                "key": "risk_assessment",
                "title": ("Penilaian Risiko & Tantangan Operasional", "Risk & Operational Challenge Assessment"),
                "description": ("Evaluasi potensi masalah dan kendala operasional.", "Evaluation of potential issues and operational constraints."),
                "enabled": True,
            },
            {
                "key": "recommendations",
                "title": ("Rekomendasi Tindakan Strategis", "Strategic Action Recommendations"),
                "description": ("Langkah-langkah taktis dan strategis untuk perbaikan.", "Tactical and strategic steps for improvement."),
                "enabled": True,
            },
            {
                "key": "conclusion",
                "title": ("Kesimpulan Akhir", "Final Conclusion"),
                "description": ("Rangkuman penutup laporan.", "Closing summary of the report."),
                "enabled": True,
            },
        ],
    },
}


def _pick_lang(value, is_en: bool):
    """Pilih varian (id, en) sesuai bahasa — dipakai utk semua field bilingual di
    _DOMAIN_PRESETS. Tuple selalu (teks_indonesia, teks_inggris)."""
    if isinstance(value, tuple):
        return value[1] if is_en else value[0]
    return value


def _localize_preset(preset: Dict[str, Any], is_en: bool) -> Dict[str, Any]:
    """Ratakan 1 preset domain (masih berisi tuple (id,en)) jadi string tunggal sesuai bahasa
    yang diminta — dipanggil sekali di awal suggest_sections_for_file supaya sisa fungsi di
    bawah tetap kerja dengan string biasa seperti sebelumnya (tidak perlu tahu soal tuple)."""
    return {
        "domain_label": _pick_lang(preset["domain_label"], is_en),
        "default_header_title": _pick_lang(preset["default_header_title"], is_en),
        "default_header_subtitle": _pick_lang(preset["default_header_subtitle"], is_en),
        "sections": [
            {
                "key": s["key"],
                "title": _pick_lang(s["title"], is_en),
                "description": _pick_lang(s["description"], is_en),
                "enabled": s["enabled"],
            }
            for s in preset["sections"]
        ],
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


# Skor minimum sebelum berani mengklaim SATU dari 4 domain spesifik (bukan cuma "> 0").
# BUG NYATA YANG DIPERBAIKI (dilaporkan user): sebelumnya HANYA jatuh ke "general" kalau skor
# SEMUA domain persis 0 — 1 kecocokan kata kunci yang kebetulan (mis. data bandwidth/jaringan
# punya kolom "Port", yang nyasar cocok ke daftar kata kunci soc_security) sudah cukup buat
# mengklaim domain itu dengan yakin penuh, padahal datanya sama sekali BUKAN salah satu dari 4
# domain yang dikenal sistem — hasilnya header/subtitle laporan salah total ("Laporan
# Pengadaan" utk data bandwidth). >= 2 kata kunci BERBEDA yang cocok jauh lebih jarang
# kebetulan (data domain asli biasanya punya banyak sinyal sekaligus, mis. data pengadaan
# nyata punya "vendor" DAN "kontrak" DAN "tender", bukan cuma satu).
_MIN_CONFIDENT_DOMAIN_SCORE = 2


def detect_domain_from_columns(columns: List[str], sample_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Mendeteksi domain data berdasarkan nama kolom — domain dengan JUMLAH kata kunci yang
    cocok TERBANYAK yang menang (bukan domain pertama yang punya minimal 1 kecocokan).

    Kembalikan "general" (preset netral, tidak mengklaim domain spesifik apa pun) kalau
    domain terbaik skornya masih di bawah _MIN_CONFIDENT_DOMAIN_SCORE, ATAU kalau skor
    tertingginya SERI antara >1 domain (sinyalnya ambigu, bukan sinyal kuat ke satu domain
    tertentu — dulu `max()` diam-diam memenangkan domain yang didefinisikan PALING AWAL di
    _DOMAIN_KEYWORDS kalau seri, bukan keputusan yang genuinely lebih yakin)."""
    col_str = " ".join(str(c).lower() for c in columns)
    scores = {domain: sum(1 for kw in kws if kw in col_str) for domain, kws in _DOMAIN_KEYWORDS.items()}
    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]
    if best_score < _MIN_CONFIDENT_DOMAIN_SCORE:
        return "general"
    if sum(1 for s in scores.values() if s == best_score) > 1:
        return "general"
    return best_domain


def suggest_sections_for_file(
    columns: List[str],
    sample_data: Optional[List[Dict[str, Any]]] = None,
    file_name: Optional[str] = None,
    language: Optional[str] = None,
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

    # Ratakan preset (id,en) jadi string sesuai bahasa yang diminta SEKALI di sini — BUG YANG
    # DIPERBAIKI (dilaporkan user): dulu domain_label/header_title/header_subtitle/section
    # title-description SELALU Bahasa Indonesia terlepas dari `language`, karena fungsi ini
    # (dipanggil dari Step 1 Upload, SEBELUM user memilih bahasa di Step 2 Settings — makanya
    # parameter `language` di sini opsional & defaultnya None/Indonesia) tidak pernah menerima
    # sinyal bahasa sama sekali. Sekarang endpoint /upload/suggest-sections meneruskan bahasa
    # default user (dari preferensi profil) supaya hasilnya sudah sesuai sejak awal.
    is_en = (language or "").strip().lower() == "english"
    preset = _localize_preset(_DOMAIN_PRESETS.get(domain, _DOMAIN_PRESETS["general"]), is_en)

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
                language=language,
            )
        except Exception as e:
            logger.warning(f"Jalur AI gagal, fallback ke preset heuristik: {e}")
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
            col_label = cat_cols[0].replace('_', ' ').title()
            custom_sections[1]["title"] = f"Analysis by {col_label}" if is_en else f"Analisis Berdasarkan {col_label}"

    return {
        "domain_type": domain,
        "domain_label": preset["domain_label"],
        "header_title": preset["default_header_title"],
        "header_subtitle": preset["default_header_subtitle"],
        "suggested_sections": custom_sections,
        "source": "heuristic",
    }
