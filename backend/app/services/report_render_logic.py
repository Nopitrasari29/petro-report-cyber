# backend/app/services/report_render_logic.py
"""
Logika & data murni yang dipakai BERSAMA oleh export_ppt.py, export_pdf.py, dan (nanti)
endpoint preview — TIDAK ADA import pptx atau HTML di sini, supaya aman dipakai ketiganya.

Sebelumnya fungsi-fungsi ini didefinisikan ULANG identik (byte-per-byte) di export_ppt.py
DAN export_pdf.py secara terpisah. Disatukan di sini murni supaya tidak ada 2 salinan yang
bisa diam-diam jadi beda saat salah satu diedit tanpa mengedit yang lain.

Konstanta warna (RGBColor vs hex string) & semua helper visual (badge/panel/tabel/chart)
SENGAJA TIDAK dipindah ke sini — itu genuinely berbeda implementasi per medium (PPTX vs
HTML), bukan duplikasi yang bisa disatukan.
"""
import datetime

from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import compute_statistics, _classify_severity_value
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text, coerce_finding_text

SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "informational": "Info",
}


def format_report_date(dt: datetime.datetime, language: str | None) -> str:
    """Format tanggal secara dinamis berdasarkan preferensi bahasa laporan."""
    if not dt:
        return "-"
    if language and language.strip().lower() == "indonesian":
        months_id = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
            5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
            9: "September", 10: "Oktober", 11: "November", 12: "Desember"
        }
        return f"{dt.day} {months_id[dt.month]} {dt.year}"
    return dt.strftime('%d %B %Y')


def format_period(report) -> str:
    if report.period_start and report.period_end:
        if report.period_start == report.period_end:
            return format_report_date(report.period_end, report.language)
        return f"{format_report_date(report.period_start, report.language)} sampai {format_report_date(report.period_end, report.language)}"
    if report.period_end:
        return format_report_date(report.period_end, report.language)
    if report.period_start:
        return format_report_date(report.period_start, report.language)
    return format_report_date(report.created_at or datetime.datetime.now(), report.language)


def classify_open_status(value) -> bool | None:
    """True = masih terbuka/belum tuntas, False = sudah tuntas, None = tak bisa diklasifikasi.
    Kosakata status SOC umum (Blocked/Mitigated/Isolated/Resolved/Logged/Quarantined = tuntas;
    Investigating/Open/Pending = masih berjalan)."""
    v = str(value).strip().lower()
    open_kw = ["investigating", "open", "pending", "in progress", "in-progress", "unresolved",
               "belum selesai", "belum ditangani", "menunggu", "baru", "new"]
    closed_kw = ["blocked", "mitigated", "isolated", "resolved", "logged", "quarantined",
                 "closed", "selesai", "done", "complete", "completed", "ditutup", "tertangani"]
    if any(kw in v for kw in open_kw):
        return True
    if any(kw in v for kw in closed_kw):
        return False
    return None


def pick_category(top_categories: dict, preferred: list, used: set):
    """Coba tiap label di `preferred` urut, kembalikan (label, items) pertama yang ADA
    isinya & belum dipakai slide/halaman lain — else None (bagian terkait di-skip aman)."""
    for label in preferred:
        items = top_categories.get(label)
        if items and label not in used:
            used.add(label)
            return label, items
    return None


def humanize_label(label: str) -> str:
    return label.replace("_", " ").replace("category ", "Kategori ").strip().title()


def build_key_findings(ai_summary: dict, report_stats: dict, open_count: int, sanitize_func=None) -> list:
    clean_fn = sanitize_func or sanitize_text
    findings = [
        clean_fn(coerce_finding_text(f))
        for f in (ai_summary.get("key_findings") or [])
        if coerce_finding_text(f)
    ]
    if not findings:
        sev = report_stats.get("severity_distribution") or {}
        total_sev = sum(sev.values())
        if total_sev:
            top, count = max(sev.items(), key=lambda kv: kv[1])
            pct = round(count / total_sev * 100, 1)
            findings.append(f"Proporsi {SEVERITY_LABEL.get(top, top.capitalize())} paling tinggi, {count} event ({pct}%).")
        tops = report_stats.get("top_categories") or {}
        for label, items in tops.items():
            if items:
                findings.append(
                    f"Kategori teratas pada {humanize_label(label)} adalah "
                    f"{items[0]['value']} dengan {items[0]['count']} kejadian."
                )
                break
        if not findings:
            findings.append("Temuan utama belum dapat dirumuskan otomatis dari data ini.")
    if open_count > 0:
        findings.insert(0, f"Terdapat {open_count} insiden berstatus terbuka/belum ditangani yang memerlukan tindak lanjut segera.")
    return findings[:6]


def is_section_included(key: str, included_sections) -> bool:
    """`included_sections` = report.included_sections (dict preset lama ATAU list section
    dinamis PART A2) — default True kalau key tidak ditemukan (tampilkan, bukan sembunyikan)."""
    if isinstance(included_sections, dict):
        return included_sections.get(key, True)
    if isinstance(included_sections, list):
        for sec in included_sections:
            if isinstance(sec, dict) and (sec.get("key") == key or sec.get("id") == key):
                return sec.get("enabled", True)
    return True


def build_report_blocks(report) -> list[dict]:
    parsed_data = get_parsed_data(report)
    report_stats = compute_statistics(parsed_data, report.data_type) if parsed_data else {"total_records": 0}
    ai_summary = report.ai_summary or {}

    total_records = report_stats.get("total_records", 0)
    severity = report_stats.get("severity_distribution") or {}
    total_sev = sum(severity.values())
    top_categories = report_stats.get("top_categories") or {}
    status_items = top_categories.get("status") or []

    used_labels: set = set()
    generic_category_keys = sorted(k for k in top_categories if k.startswith("category_"))
    category_pick = pick_category(top_categories, ["action", *generic_category_keys, "location", "destination_port"], used_labels)
    asset_pick = pick_category(top_categories, ["asset", "destination_port", "location", *generic_category_keys], used_labels)

    source_cols = report_stats.get("_source_columns") or {}
    severity_col = source_cols.get("severity")
    status_col = source_cols.get("status")
    open_count = 0
    if status_col and parsed_data:
        for row in parsed_data:
            if classify_open_status(row.get(status_col)) is True:
                open_count += 1

    recommendations = normalize_recommendations(ai_summary.get("recommendations"))
    key_findings = build_key_findings(ai_summary, report_stats, open_count, sanitize_text)
    period_text = format_period(report)
    included = report.included_sections or {}
    is_included = lambda key: is_section_included(key, included)

    # Detect domain & language
    domain = (report.domain_type or "general").lower().strip().replace("-", "_")
    is_en = bool(report.language and report.language.strip().lower() == "english")

    blocks: list[dict] = []

    # ---------------- Cover ----------------
    cat_count = len(top_categories)
    crit_count = severity.get("critical", 0)
    blocks.append({
        "kind": "cover",
        "dark": True,
        "title": report.title,
        "subtitle": sanitize_text(report.header_subtitle) or ("Security Operations Center" if domain == "soc_security" else "Executive Data Analytics"),
        "period_text": period_text,
        "total_records": total_records,
        "category_count": cat_count,
        "critical_count": crit_count,
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    })

    # ---------------- Latar Belakang & Tujuan (Domain & Language Aware) ----------------
    if domain == "financial":
        data_name = "financial transactions" if is_en else "data transaksi & operasional keuangan"
        obj1_title = "Map Financial Position" if is_en else "Memetakan Postur Keuangan"
        obj1_desc = "Identify expense categories, revenue trends, and budget efficiency." if is_en else "Mengidentifikasi kategori beban, pendapatan, dan efisiensi anggaran."
        obj2_title = "Evaluate Budget Efficiency" if is_en else "Evaluasi Efisiensi Anggaran"
        obj2_desc = "Evaluate expenditure ratio against target plans." if is_en else "Mengevaluasi rasio pengeluaran terhadap target kerja perusahaan."
        obj3_title = "Formulate Recommendations" if is_en else "Menyusun Rekomendasi Finansial"
        obj3_desc = "Formulate cost optimization and savings actions." if is_en else "Merumuskan langkah optimalisasi biaya dan penghematan."
    elif domain == "kpi_hr":
        data_name = "KPI & performance evaluation data" if is_en else "data penilaian KPI & kinerja SDM/mitra"
        obj1_title = "Map Target Achievement" if is_en else "Memetakan Pencapaian Target"
        obj1_desc = "Identify KPI achievement scores per unit/division." if is_en else "Mengidentifikasi pencapaian skor KPI per divisi/unit kerja."
        obj2_title = "Evaluate Performance Gaps" if is_en else "Evaluasi Gap & Performa"
        obj2_desc = "Assess development areas and top performers." if is_en else "Menilai area pembinaan dan mitra dengan performa teratas."
        obj3_title = "Formulate Action Plans" if is_en else "Rekomendasi Pengembangan"
        obj3_desc = "Formulate performance improvement steps." if is_en else "Merumuskan langkah perbaikan kinerja dan alokasi target."
    elif domain == "soc_security":
        data_name = "cybersecurity log events" if is_en else "sistem keamanan siber"
        obj1_title = "Map Event Patterns" if is_en else "Memetakan Pola Kejadian"
        obj1_desc = "Identify categories, time trends, and target assets." if is_en else "Mengidentifikasi kategori, tren waktu, dan aset sasaran."
        obj2_title = "Assess Response Status" if is_en else "Menilai Efektivitas Respons"
        obj2_desc = "Evaluate incident mitigation status." if is_en else "Mengevaluasi status penanganan tiap insiden."
        obj3_title = "Formulate Mitigations" if is_en else "Menyusun Rekomendasi"
        obj3_desc = "Formulate priority mitigation steps based on data." if is_en else "Merumuskan langkah mitigasi prioritas berbasis temuan data."
    else:
        data_name = "operational data records" if is_en else "data operasional"
        obj1_title = "Map Data Distribution" if is_en else "Memetakan Distribusi Data"
        obj1_desc = "Identify trends, frequency patterns, and main categories." if is_en else "Mengidentifikasi tren, pola frekuensi, dan kategori dominan."
        obj2_title = "Evaluate Operational Metrics" if is_en else "Evaluasi Kinerja Operasional"
        obj2_desc = "Evaluate key indicators and status." if is_en else "Menilai indikator utama dan status penanganan."
        obj3_title = "Formulate Strategic Actions" if is_en else "Menyusun Rekomendasi Taktis"
        obj3_desc = "Formulate improvement steps based on findings." if is_en else "Merumuskan langkah perbaikan berbasis temuan data."

    if is_en:
        purpose_text = sanitize_text(
            f"Throughout the period {period_text}, a total of {total_records} {data_name} "
            f"were analyzed in this report to map key patterns, evaluate operational efficiency, "
            f"and formulate data-driven strategic recommendations."
        )
    else:
        purpose_text = sanitize_text(
            f"Sepanjang periode {period_text}, tercatat {total_records} {data_name} "
            f"yang dianalisis pada laporan ini untuk memetakan pola kejadian, "
            f"menilai efektivitas operasional, dan menjadi dasar rekomendasi perbaikan."
        )

    blocks.append({
        "kind": "intro",
        "dark": False,
        "purpose_text": purpose_text,
        "objectives": [
            {"num": "1", "title": obj1_title, "detail": obj1_desc},
            {"num": "2", "title": obj2_title, "detail": obj2_desc},
            {"num": "3", "title": obj3_title, "detail": obj3_desc},
        ],
        "scope": {
            "period_text": period_text,
            "total_records": total_records,
            "input_file_name": report.input_file_name or "-",
            "data_type_label": (report.data_type or "-").replace("_", " ").title(),
        },
    })

    # ---------------- Ringkasan Eksekutif (Domain & Language Aware) ----------------
    if is_included("executive_summary"):
        lbl_total = "Total Records" if is_en else "Total Data"
        stat_items = [(str(total_records), lbl_total)]
        
        if total_sev:
            if severity.get("critical"):
                lbl_crit = "Critical" if is_en else "Kategori Kritis"
                stat_items.append((str(severity["critical"]), lbl_crit))
            if severity.get("high"):
                lbl_high = "High Priority" if is_en else "Prioritas Tinggi"
                stat_items.append((str(severity["high"]), lbl_high))
        if status_col:
            closed = sum(1 for row in parsed_data if classify_open_status(row.get(status_col)) is False)
            if closed:
                lbl_closed = "Completed" if is_en else "Sudah Ditangani"
                stat_items.append((str(closed), lbl_closed))
            lbl_open = "Pending" if is_en else "Masih Terbuka"
            stat_items.append((str(open_count), lbl_open))
        if category_pick:
            lbl_cat = "Categories" if is_en else "Kategori Sumber"
            stat_items.append((str(len(top_categories)), lbl_cat))
        stat_items = stat_items[:6]

        if domain == "financial":
            heading = f"Financial Snapshot, {period_text}" if is_en else f"Ringkasan Kinerja Keuangan, {period_text}"
        elif domain == "kpi_hr":
            heading = f"KPI Performance Snapshot, {period_text}" if is_en else f"Ringkasan Pencapaian KPI, {period_text}"
        elif domain == "soc_security":
            heading = f"Security Log Snapshot, {period_text}" if is_en else f"Snapshot Log Keamanan, {period_text}"
        else:
            heading = f"Operational Snapshot, {period_text}" if is_en else f"Ringkasan Data Operasional, {period_text}"

        caption = sanitize_text(ai_summary.get("executive_summary") or (key_findings[0] if key_findings else ""))
        blocks.append({
            "kind": "executive_summary",
            "dark": True,
            "heading": heading,
            "stat_items": stat_items,
            "caption": caption,
        })

    # ---------------- Distribusi Kategori Event ----------------
    if category_pick:
        label, items = category_pick
        top_items = items[:6]
        cat_total = sum(i["count"] for i in items) or 1
        intro = sanitize_text(
            f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} event "
            f"({round(top_items[0]['count']/cat_total*100,1)}% dari total)."
        )
        legend = [
            {"color_index": i % 5, "name": it["value"], "pct": round(it["count"] / cat_total * 100, 1)}
            for i, it in enumerate(top_items)
        ]
        blocks.append({
            "kind": "category_distribution",
            "dark": False,
            "label": humanize_label(label),
            "raw_label": label,
            "categories": [i["value"] for i in top_items],
            "values": [i["count"] for i in top_items],
            "legend": legend,
            "intro": intro,
            "footnote": sanitize_text(f"{top_items[0]['value']} menjadi kontributor volume terbesar pada kategori ini."),
        })

    # ---------------- Distribusi Severity ----------------
    if total_sev > 0 and is_included("severity_analysis"):
        crit_pct = round(severity.get("critical", 0) / total_sev * 100, 1)
        high_pct = round(severity.get("high", 0) / total_sev * 100, 1)
        intro = sanitize_text(f"{high_pct}% event berkategori High dan {crit_pct}% Critical. Kombinasi keduanya memerlukan perhatian dan eskalasi serius.")
        detail_text = None
        if category_pick:
            names = ", ".join(i["value"] for i in category_pick[1][:6])
            detail_text = sanitize_text(f"Insiden Critical tersebar pada kategori {names}.")
        blocks.append({
            "kind": "severity_distribution",
            "dark": False,
            "categories": [SEVERITY_LABEL[k] for k in SEVERITY_ORDER],
            "values": [severity.get(k, 0) for k in SEVERITY_ORDER],
            "severity_keys": list(SEVERITY_ORDER),
            "intro": intro,
            "crit_pct": crit_pct,
            "panel_text": "dari seluruh event berstatus Critical Severity",
            "detail_text": detail_text,
        })

    # ---------------- Status Penanganan Insiden ----------------
    if status_items:
        status_total = sum(i["count"] for i in status_items) or 1
        top_status = status_items[0]
        intro = sanitize_text(
            f"{round(top_status['count']/status_total*100,1)}% event berstatus {top_status['value']}. "
            f"Sebagian kecil masih memerlukan tindak lanjut aktif tim SOC."
        )
        top_status_items = status_items[:8]
        blocks.append({
            "kind": "status_distribution",
            "dark": False,
            "categories": [i["value"] for i in top_status_items],
            "values": [i["count"] for i in top_status_items],
            "intro": intro,
        })

    # ---------------- Tabel Insiden Critical/Prioritas Tinggi ----------------
    if severity_col and parsed_data:
        critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
        if len(critical_rows) < 5:
            critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
        critical_rows = critical_rows[:12]

        if critical_rows:
            headers = ["No"]
            if category_pick:
                headers.append(humanize_label(category_pick[0]))
            headers.append("Severity")
            if status_col:
                headers.append("Status")

            cat_col_name = source_cols.get(category_pick[0]) if category_pick else None
            rows_out = []
            highlight_idx = []
            for idx, row in enumerate(critical_rows):
                row_vals = [str(idx + 1)]
                if category_pick:
                    row_vals.append(str(row.get(cat_col_name, "-")) if cat_col_name else "-")
                row_vals.append(_classify_severity_value(str(row.get(severity_col, ""))).capitalize())
                if status_col:
                    status_val = row.get(status_col, "-")
                    row_vals.append(str(status_val))
                    if classify_open_status(status_val) is True:
                        highlight_idx.append(idx)
                rows_out.append(row_vals)

            table_title = f"{len(critical_rows)} Priority Items" if is_en else f"{len(critical_rows)} Insiden Prioritas Tinggi"
            blocks.append({
                "kind": "critical_table",
                "dark": False,
                "title": table_title,
                "headers": headers,
                "rows": rows_out,
                "highlight_idx": highlight_idx,
                "open_count": open_count,
                "kicker_is_critical": bool(open_count),
                "caption": sanitize_text(f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.") if open_count else None,
            })

    # ---------------- Aset Paling Sering Menjadi Sasaran ----------------
    if asset_pick:
        label, items = asset_pick
        asset_total = sum(i["count"] for i in items) or 1
        top_assets = items[:3]
        card_items = []
        for idx, item in enumerate(top_assets):
            pct = round(item["count"] / asset_total * 100, 1)
            card_items.append({
                "num": str(idx + 1),
                "name": item["value"],
                "stat": f"{item['count']} event",
                "detail": sanitize_text(f"Tercatat {item['count']} kejadian ({pct}% dari total) yang menyasar kategori ini."),
            })
        blocks.append({
            "kind": "asset_cards",
            "dark": True,
            "label": humanize_label(label),
            "title": f"{humanize_label(label)} yang Paling Sering Menjadi Sasaran",
            "items": card_items,
        })

    # ---------------- Temuan Utama ----------------
    if key_findings:
        findings_items = []
        for idx, finding in enumerate(key_findings):
            title_part, _, detail_part = finding.partition(". ")
            if not detail_part:
                title_part, detail_part = finding, ""
            findings_items.append({
                "num": str(idx + 1),
                "title": title_part.strip() or finding,
                "detail": detail_part.strip(),
                "is_critical": bool(open_count and idx == 0),
            })
        blocks.append({"kind": "key_findings", "dark": False, "items": findings_items})

    # ---------------- Rekomendasi Mitigasi ----------------
    if is_included("recommendations") and recommendations:
        items = recommendations[:6]
        rec_items = []
        for idx, item in enumerate(items):
            title_txt = item.get("title") or (item.get("detail") or "")[:60]
            rec_items.append({
                "num": str(idx + 1),
                "title": title_txt,
                "detail": item.get("detail") if (item.get("title") and item.get("detail")) else None,
            })
        blocks.append({"kind": "recommendations", "dark": False, "items": rec_items})

    # ---------------- Kesimpulan ----------------
    if is_included("conclusion") and ai_summary.get("conclusion"):
        pills = []
        if total_sev and status_col:
            resolved_pct = round((total_sev - open_count) / total_sev * 100, 1)
            pills.append(f"{resolved_pct}% event tertangani")
        if category_pick:
            pills.append(f"{category_pick[1][0]['value']} jadi prioritas perhatian")
        if open_count:
            pills.append(f"{open_count} insiden masih berjalan")

        priority_items = []
        for idx, rec in enumerate(recommendations[:4]):
            letter = chr(ord("a") + idx)
            priority_items.append({"letter": letter, "text": rec.get("title") or (rec.get("detail") or "")[:70]})

        blocks.append({
            "kind": "conclusion",
            "dark": True,
            "text": sanitize_text(ai_summary.get("conclusion")),
            "pills": pills,
            "priority_items": priority_items,
        })

    # ---------------- Penutup ----------------
    blocks.append({"kind": "closing", "dark": True, "title": report.title})

    return blocks
