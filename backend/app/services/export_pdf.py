# backend/app/services/export_pdf.py
import base64
import datetime
import html
from typing import Any, Dict
import io
import os
from app.models.report import Report
from app.services.chart_generator import ChartGenerator
from app.crud.report import get_parsed_data

try:
    import plotly  # noqa: F401 — cuma dipakai untuk cek ketersediaan; render sungguhan lewat ChartGenerator.render_png
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False

try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False


def format_report_date(dt: datetime.datetime, language: str | None) -> str:
    """
    Format tanggal pembuatan laporan secara dinamis berdasarkan preferensi bahasa
    agar otomatis melokalkan nama bulan ke Bahasa Indonesia.
    """
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


class PDFExporter:
    @classmethod
    def generate_pdf_report(cls, report: Report) -> bytes:
        """
        Menghasilkan file PDF dari data laporan menggunakan WeasyPrint dengan format korporat PT Petrokimia Gresik.
        """
        if not WEASYPRINT_AVAILABLE and not XHTML2PDF_AVAILABLE:
            raise RuntimeError(
                "Pustaka sistem PDF (WeasyPrint dan xhtml2pdf) tidak ditemukan di sistem Anda. "
                "Silakan install xhtml2pdf atau jalankan aplikasi dengan WeasyPrint terinstal."
            )
            
        title = report.title
        data_type = report.data_type.upper()
        ai_summary = report.ai_summary or {}
        parsed_data = get_parsed_data(report)
        chart_data = report.chart_data or {}

        # Render SEMUA chart Plotly (3 Grafik) ke gambar PNG base64 untuk embed di PDF.
        # Jika report di database adalah laporan lama yang baru punya 1 grafik, regenerasikan 3 grafik secara dinamis.
        chart_imgs_html = []
        charts_list = []
        if isinstance(chart_data.get("charts"), list) and len(chart_data["charts"]) >= 2:
            charts_list = chart_data["charts"]
        elif parsed_data:
            fresh_config = ChartGenerator.generate_chart_config(report.data_type, parsed_data)
            if isinstance(fresh_config.get("charts"), list) and len(fresh_config["charts"]) > 0:
                charts_list = fresh_config["charts"]
            elif "data" in fresh_config:
                charts_list = [fresh_config]
        elif "data" in chart_data:
            charts_list = [chart_data]

        # Fase B — key opsional, kosong ([]) di laporan lama yang belum punya key ini
        key_findings = ai_summary.get("key_findings") or []
        metrics_table = ai_summary.get("metrics_table") or []
        chart_captions = ai_summary.get("chart_captions") or []

        # Default narasi fallback jika AI belum generate chart_captions
        default_captions = [
            "Distribusi data berdasarkan kategori utama dalam periode laporan ini.",
            "Tren dan pola data dari waktu ke waktu selama periode yang dianalisis.",
            "Perbandingan antar entitas atau kategori berdasarkan indikator utama.",
            "Analisis frekuensi dan proporsi per kelompok data yang diidentifikasi.",
            "Ringkasan visual temuan utama dari keseluruhan dataset yang diproses.",
        ]

        if PLOTLY_AVAILABLE and charts_list:
            for idx, c_dict in enumerate(charts_list):
                try:
                    # Render chart lebih kecil karena hanya menempati setengah lebar halaman
                    png_bytes = ChartGenerator.render_png(c_dict, width=520, height=310, scale=2)
                    c_b64 = base64.b64encode(png_bytes).decode("utf-8")

                    # Narasi per-chart: prioritas dari AI, fallback ke default
                    narasi_text = ""
                    if idx < len(chart_captions) and chart_captions[idx]:
                        narasi_text = html.escape(str(chart_captions[idx]))
                    else:
                        narasi_text = default_captions[idx % len(default_captions)]

                    chart_title = ""
                    raw_title = c_dict.get("layout", {}).get("title", {})
                    if isinstance(raw_title, dict):
                        chart_title = html.escape(str(raw_title.get("text", "")))
                    elif isinstance(raw_title, str):
                        chart_title = html.escape(raw_title)

                    # Layout 2-kolom: kiri = chart, kanan = narasi AI
                    # Menggunakan <table> (bukan flex/grid) karena xhtml2pdf tidak support flexbox
                    chart_imgs_html.append(
                        f'<table style="width:100%;border-collapse:collapse;margin-bottom:20px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">'
                        f'<tr>'
                        f'<td style="width:55%;vertical-align:middle;padding:8px;background-color:#f8fafc;border-right:1px solid #e2e8f0;">'
                        f'<img src="data:image/png;base64,{c_b64}" width="340" style="width:340px;display:block;margin:0 auto;" alt="Grafik #{idx+1}" />'
                        f'</td>'
                        f'<td style="width:45%;vertical-align:middle;padding:14px 12px;">'
                        f'<div style="background-color:#fffbeb;border-left:3px solid #d97706;padding:8px 10px;border-radius:4px;">'
                        f'<p style="font-size:7.5pt;font-weight:800;color:#92400e;margin:0 0 6px 0;">&#x1F4A1; Narasi Insight AI</p>'
                        + (f'<p style="font-size:8pt;font-weight:700;color:#1e293b;margin:0 0 5px 0;">{chart_title}</p>' if chart_title else '')
                        + f'<p style="font-size:8pt;color:#374151;margin:0;line-height:1.55;">{narasi_text}</p>'
                        f'</div>'
                        f'</td>'
                        f'</tr>'
                        f'</table>'
                    )
                except Exception as chart_err:
                    print(f"[PDF CHART WARNING] Gagal merender grafik #{idx+1}: {chart_err}")

        chart_img_html = "".join(chart_imgs_html) if chart_imgs_html else '<p style="color:#718096;font-style:italic;">Visualisasi grafik belum tersedia.</p>'

        # Ekstrak data narasi AI dari JSON siber
        exec_summary = ai_summary.get("executive_summary", "Ringkasan eksekutif tidak tersedia.")
        trend_analysis = ai_summary.get("trend_analysis", "Analisis tren tidak tersedia.")
        severity_analysis = ai_summary.get("severity_analysis", "Analisis severity tidak tersedia.")
        risk_assessment = ai_summary.get("risk_assessment", "Penilaian risiko tidak tersedia.")
        recommendations = ai_summary.get("recommendations", [])
        conclusion = ai_summary.get("conclusion", "Kesimpulan tidak tersedia.")

        # Bentuk daftar html rekomendasi siber
        rec_html = ""
        for rec in recommendations:
            rec_html += f"<li style='margin-bottom: 8px; font-weight: 500;'>{rec}</li>"
        if not rec_html:
            rec_html = "<li style='color:#718096; font-style:italic;'>Rekomendasi tidak tersedia saat ini.</li>"

        # Fase B — kartu KPI dari metrics_table (opsional, AI-generated). Dipakai <table> (bukan
        # flex/grid) karena xhtml2pdf (fallback engine kalau WeasyPrint tidak tersedia) tidak
        # mendukung flexbox/grid, sedangkan tabel HTML sudah terbukti aman di kedua engine.
        metrics_html = ""
        if metrics_table:
            cells_html = []
            for m in metrics_table[:8]:
                is_dict = isinstance(m, dict)
                m_value = html.escape(str(m.get("value", "-"))) if is_dict else html.escape(str(m))
                m_pct = html.escape(str(m.get("percentage") or "").strip()) if is_dict else ""
                m_label = html.escape(str(m.get("label", ""))) if is_dict else ""
                cells_html.append(
                    "<td style='width:25%; padding:14px 8px; text-align:center; "
                    "background-color:#f7fafc; border:1px solid #004D25; border-radius:8px;'>"
                    f"<div style='font-size:19pt;font-weight:800;color:#004D25;'>{m_value}"
                    f"{f' ({m_pct})' if m_pct else ''}</div>"
                    f"<div style='font-size:8.5pt;color:#4a5568;margin-top:4px;'>{m_label}</div>"
                    "</td>"
                )
            rows_html = "".join(
                f"<tr>{''.join(cells_html[i:i + 4])}</tr>" for i in range(0, len(cells_html), 4)
            )
            metrics_html = (
                "<table style='width:100%; border-collapse:separate; border-spacing:8px; margin-top:16px;'>"
                f"{rows_html}</table>"
            )

        # Fase B — bullet temuan kunci (opsional, AI-generated)
        key_findings_html = ""
        if key_findings:
            kf_items = "".join(f"<li style='margin-bottom: 6px;'>{html.escape(str(f))}</li>" for f in key_findings)
            key_findings_html = (
                "<h3 style='font-size:11pt;color:#004D25;margin-top:16px;margin-bottom:6px;'>Temuan Kunci</h3>"
                f"<ul>{kf_items}</ul>"
            )

        header_title_text = html.escape(report.header_title or "PT PETROKIMIA GRESIK")
        header_subtitle_text = html.escape(report.header_subtitle or "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI")
        
        # Color Theme Config
        theme = (report.theme_color or "green").lower()
        theme_map = {
            "green": {"primary": "#004D25", "accent": "#d9a700", "light": "#f0fdf4"},
            "navy": {"primary": "#0F172A", "accent": "#38BDF8", "light": "#f8fafc"},
            "dark": {"primary": "#111827", "accent": "#818CF8", "light": "#f3f4f6"},
            "gold": {"primary": "#78350F", "accent": "#F59E0B", "light": "#fffbeb"},
        }
        theme_colors = theme_map.get(theme, theme_map["green"])
        primary_color = theme_colors["primary"]
        accent_color = theme_colors["accent"]
        light_color = theme_colors["light"]

        # chart_img_html sudah berisi layout 2-kolom per chart (narasi inline)
        chart_img_html_with_caption = chart_img_html

        # Section mana yang ditampilkan, sesuai pilihan "Include Sections" user di Report
        included = report.included_sections or {}

        def is_included(key: str) -> bool:
            if isinstance(included, dict):
                return included.get(key, True)
            if isinstance(included, list):
                # If included is a list of section objects
                for sec in included:
                    if isinstance(sec, dict) and sec.get("key") == key:
                        return sec.get("enabled", True)
            return True

        # Render Dynamic Sections
        report_items = []
        if is_included("executive_summary"):
            report_items.append((
                "Ringkasan Eksekutif (Executive Summary)",
                f"<p>{exec_summary}</p>{metrics_html}{key_findings_html}"
            ))
        report_items.append(("Visualisasi Data & Infografis Analitik", chart_img_html_with_caption))
        
        # Check dynamic sections from included list or dict
        section_titles = {
            "trend_analysis": "Analisis Tren & Distribusi Data",
            "target_achievement": "Analisis Pencapaian Target & Realisasi",
            "revenue_expense_trend": "Analisis Tren Pendapatan vs Beban Operasional",
            "severity_analysis": "Analisis Tingkat Keparahan (Severity)",
            "top_performers": "Analisis Performa Teratas & Evaluasi",
            "budget_variance": "Analisis Varian Anggaran & Efisiensi",
            "risk_assessment": "Penilaian Risiko & Dampak Operasional",
            "financial_risk": "Penilaian Risiko Keuangan & Pengendalian Biaya",
            "gap_risk_analysis": "Identifikasi Kendala & Area Perbaikan",
            "recommendations": "Rekomendasi Tindakan Strategis & Pembinaan",
            "conclusion": "Kesimpulan & Catatan Manajemen"
        }

        # Override titles if custom sections exist
        if isinstance(included, list):
            for sec in included:
                if isinstance(sec, dict) and sec.get("enabled", True):
                    k = sec.get("key")
                    if k in ai_summary and k != "executive_summary":
                        t = sec.get("title", k.replace("_", " ").title())
                        c = html.escape(str(ai_summary.get(k, "")))
                        report_items.append((t, f"<p>{c}</p>"))
        else:
            if is_included("trend_analysis") and trend_analysis:
                report_items.append((section_titles.get("trend_analysis"), f"<p>{trend_analysis}</p>"))
            if is_included("severity_analysis") and severity_analysis:
                report_items.append((section_titles.get("severity_analysis"), f"<p>{severity_analysis}</p>"))
            if is_included("risk_assessment") and risk_assessment:
                report_items.append((section_titles.get("risk_assessment"), f"<p>{risk_assessment}</p>"))
            if is_included("recommendations") and rec_html:
                report_items.append((section_titles.get("recommendations"), f"<ul>{rec_html}</ul>"))
            if is_included("conclusion") and conclusion:
                report_items.append((section_titles.get("conclusion"), f"<p>{conclusion}</p>"))

        narrative_sections_html = "\n".join(
            f"<h2>{idx + 1}. {sec_title}</h2>\n{content}\n"
            for idx, (sec_title, content) in enumerate(report_items)
        )


        # Bentuk tabel data log terlampir (dipilih max 8 kolom utama agar tidak meluber/tumpang tindih di PDF)
        table_headers = ""
        table_rows = ""
        if parsed_data:
            all_headers = list(parsed_data[0].keys())
            # Prioritaskan kolom-kolom paling penting untuk sampel PDF
            preferred_keys = [
                "alert_id", "id", "timestamp", "date", "waktu", "source_ip", "src_ip",
                "destination_ip", "dst_ip", "destination_host", "host", "destination_port",
                "protocol", "attack_type", "event", "type", "signature_id", "severity",
                "level", "action_taken", "status", "description", "detail"
            ]

            if len(all_headers) > 8:
                selected_headers = [h for h in all_headers if h.lower() in preferred_keys]
                if len(selected_headers) < 5:
                    selected_headers = all_headers[:8]
                else:
                    selected_headers = selected_headers[:8]
            else:
                selected_headers = all_headers

            table_headers = "".join([
                f"<th style='padding: 6px 5px; font-weight: 700; text-transform: uppercase; font-size: 7.5pt; border: 1px solid #004D25; background-color: #004D25; color: white;'>{html.escape(str(h))}</th>"
                for h in selected_headers
            ])
            
            # Batasi 20 baris sampel
            for row in parsed_data[:20]:
                cell_strs = []
                for h in selected_headers:
                    val = row.get(h, "")
                    # Sel benar-benar kosong (bukan cuma falsy seperti 0/False) bikin xhtml2pdf
                    # menghitung lebar kolom otomatis jadi negatif dan crash (ValueError: flowable
                    # given negative availWidth) - lihat cell yang isinya "" di kolom pertama.
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        val_str = "-"
                    else:
                        val_str = str(val)
                    cell_strs.append(
                        f"<td style='padding: 5px 4px; border: 1px solid #cbd5e0; font-size: 7.5pt; word-wrap: break-word; overflow-wrap: break-word; vertical-align: top;'>{html.escape(val_str)}</td>"
                    )
                table_rows += f"<tr>{''.join(cell_strs)}</tr>"

        # Format tanggal pembuatan laporan secara dinamis (Indonesian Friendly)
        formatted_date = format_report_date(report.created_at, report.language)

        # Load logo image dari berkas aset frontend dan encode ke base64 jika tersedia (diperbesar agar menonjol)
        logo_img_html = ""
        try:
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "LOGO_PETRO_DANANTARA.png"))
            if not os.path.exists(logo_path):
                logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "LOGO_PETRO.png"))
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_b64 = base64.b64encode(f.read()).decode("utf-8")
                logo_img_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:75px;max-height:80px;width:auto;vertical-align:middle;object-fit:contain;" alt="Logo Petrokimia Danantara" />'
        except Exception as logo_err:
            print(f"[PDF LOGO WARNING] Gagal menyematkan logo: {logo_err}")

        # HTML Template dengan layout brand Petrokimia Gresik yang dipercantik (GSM Aligned)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
            <style>
                /* DEFINISI HALAMAN UTAMA (A4 PORTRAIT) */
                @page {{
                    size: A4;
                    margin: 25mm 20mm 20mm 20mm;
                    @top-left {{
                        content: "INTERNAL USE ONLY";
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 8pt;
                        color: #d9a700;
                        font-weight: 800;
                        letter-spacing: 1px;
                    }}
                    @bottom-right {{
                        content: "Halaman " counter(page);
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 8.5pt;
                        color: #718096;
                        font-weight: 500;
                    }}
                    @bottom-left {{
                        content: "PT Petrokimia Gresik - SOC Intelligence Platform";
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 8.5pt;
                        color: #718096;
                        font-weight: 500;
                    }}
                }}

                /* REVISI: DEFINISI HALAMAN LANDSCAPE KHUSUS UNTUK LAMPIRAN DATA LOG */
                @page landscape_page {{
                    size: A4 landscape;
                    margin: 20mm 15mm 15mm 15mm;
                    @top-left {{
                        content: "INTERNAL USE ONLY";
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 8pt;
                        color: #d9a700;
                        font-weight: 800;
                        letter-spacing: 1px;
                    }}
                    @bottom-right {{
                        content: "Halaman " counter(page);
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 8.5pt;
                        color: #718096;
                        font-weight: 500;
                    }}
                    @bottom-left {{
                        content: "PT Petrokimia Gresik - Lampiran Log Mentah";
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 8.5pt;
                        color: #718096;
                        font-weight: 500;
                    }}
                }}

                /* Gunakan kelas ini untuk mengaktifkan layout landscape otomatis */
                .appendix-section {{
                    page-break-before: always;
                    page: landscape_page; /* Mengarahkan halaman ini ke format landscape */
                }}

                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #2d3748;
                    line-height: 1.6;
                    font-size: 10.5pt;
                }}
                .header-container {{
                    border-bottom: 3px solid #004D25; /* HIJAU RESMI PETROKIMIA */
                    padding-bottom: 12px;
                    margin-bottom: 25px;
                }}
                .company-name {{
                    font-size: 18pt;
                    font-weight: 800;
                    color: #004D25; /* HIJAU RESMI PETROKIMIA */
                    margin: 0;
                    letter-spacing: -0.5px;
                }}
                .doc-subtitle {{
                    font-size: 9.5pt;
                    color: #d9a700; /* EMAS RESMI PETROKIMIA */
                    margin: 4px 0 0 0;
                    text-transform: uppercase;
                    font-weight: 800;
                    letter-spacing: 1px;
                }}
                h1 {{
                    font-size: 18pt;
                    color: #1a202c;
                    margin-top: 0;
                    margin-bottom: 20px;
                    font-weight: 800;
                    letter-spacing: -0.5px;
                    line-height: 1.2;
                }}
                h2 {{
                    font-size: 12pt;
                    color: #004D25; /* HIJAU RESMI PETROKIMIA */
                    border-bottom: 1px solid #edf2f7;
                    padding-bottom: 6px;
                    margin-top: 30px;
                    margin-bottom: 12px;
                    font-weight: 800;
                    page-break-after: avoid;
                }}
                p {{
                    margin-top: 0;
                    margin-bottom: 14px;
                    text-align: justify;
                    color: #4a5568;
                }}
                ul {{
                    margin-top: 0;
                    margin-bottom: 14px;
                    padding-left: 20px;
                    color: #4a5568;
                }}
                .meta-table {{
                    width: 100%;
                    margin-bottom: 25px;
                    font-size: 9.5pt;
                    border-collapse: collapse;
                }}
                .meta-table td {{
                    padding: 4px 0;
                    color: #4a5568;
                }}
                .meta-label {{
                    font-weight: 800;
                    width: 120px;
                    color: #718096;
                    text-transform: uppercase;
                    font-size: 8pt;
                    letter-spacing: 0.5px;
                }}
                table.data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                    margin-bottom: 25px;
                    font-size: 7.5pt; /* Diperkecil agar muat sempurna di landscape */
                    table-layout: fixed; /* Mencegah kolom meluber keluar halaman */
                }}
                table.data-table th {{
                    background-color: #004D25; /* HIJAU RESMI PETROKIMIA */
                    border: 1px solid #004D25;
                    text-align: left;
                    color: white;
                }}
                .alert-info {{
                    background-color: #f7fafc;
                    border-left: 4px solid #d9a700; /* EMAS RESMI PETROKIMIA */
                    padding: 14px;
                    margin-bottom: 25px;
                    font-size: 9pt;
                    color: #4a5568;
                    border-radius: 0 8px 8px 0;
                }}
            </style>
        </head>
        <body>
            <div class="header-container">
                <table style="width: 100%; border: none;">
                    <tr>
                        <td style="padding: 0; border: none; vertical-align: middle;">
                            <div class="company-name" style="color: {primary_color};">{header_title_text}</div>
                            <div class="doc-subtitle" style="color: {accent_color};">{header_subtitle_text}</div>
                        </td>
                        <td style="padding: 0; border: none; text-align: right; vertical-align: middle;">
                            {logo_img_html}
                        </td>
                    </tr>
                </table>
            </div>


            <h1>{title}</h1>
            
            <table class="meta-table">
                <tr>
                    <td class="meta-label">Jenis Data:</td>
                    <td style="font-weight: 700;">{data_type}</td>
                </tr>
                <tr>
                    <td class="meta-label">Tanggal Cetak:</td>
                    <td style="font-weight: 700;">{formatted_date}</td>
                </tr>
                <tr>
                    <td class="meta-label">Berkas Sumber:</td>
                    <td style="font-weight: 700; font-family: monospace;">{report.input_file_name or '-'}</td>
                </tr>
            </table>

            <div class="alert-info">
                <strong style="color: #1a202c;">Pemberitahuan Kerahasiaan siber:</strong> Dokumen ini berisi rekaman aktivitas operasional keamanan siber internal PT Petrokimia Gresik. 
                Dilarang keras menyebarluaskan isi laporan ini di luar otoritas SOC atau pihak berwenang tanpa izin tertulis dari manajemen TI.
            </div>

            {narrative_sections_html}

            {f'''
            <!-- REVISI: Pembungkusan dengan kelas appendix-section agar otomatis tercetak mendatar (Landscape) -->
            <div class="appendix-section">
                <h2>Lampiran: Sampel Data Log Mentah</h2>
                <p>Berikut adalah 20 baris pertama sampel data log yang berhasil diekstrak dan dianalisis secara otomatis oleh sistem:</p>
                <table class="data-table">
                    <thead>
                        <tr style="color: #ffffff;">{table_headers}</tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
            ''' if table_rows else ""}
        </body>
        </html>
        """
        
        # Konversi template HTML ke PDF biner
        if WEASYPRINT_AVAILABLE:
            try:
                return HTML(string=html_content).write_pdf()
            except Exception as weasy_err:
                print(f"[PDF WARNING] WeasyPrint gagal merender: {weasy_err}. Menggunakan fallback xhtml2pdf.")
                if not XHTML2PDF_AVAILABLE:
                    raise weasy_err
        
        # Fallback ke xhtml2pdf
        pdf_io = io.BytesIO()
        import re
        clean_html = re.sub(r'@(top|bottom)-(left|right|center)\s*\{[^}]*\}', '', html_content)
        clean_html = re.sub(r'@page\s+[a-zA-Z0-9_]+\s*\{[^}]*\}', '', clean_html)
        pisa_status = pisa.CreatePDF(clean_html, dest=pdf_io)
        if pisa_status.err:
            raise RuntimeError(f"Gagal mengonversi HTML ke PDF menggunakan xhtml2pdf: {pisa_status.err}")
        return pdf_io.getvalue()
        