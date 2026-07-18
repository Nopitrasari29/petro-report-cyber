# backend/app/services/export_pdf.py
import base64
import datetime
from typing import Any, Dict
import io
import os
from app.models.report import Report

try:
    import plotly.io as pio
    import plotly.graph_objects as go
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
    
    # Jika bahasa laporan diset ke Indonesian, konversi nama bulan secara manual
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
        parsed_data = report.parsed_data or []
        chart_data = report.chart_data or {}

        # Render chart Plotly ke gambar PNG base64 untuk embed di PDF
        chart_img_html = ""
        if chart_data and PLOTLY_AVAILABLE and "data" in chart_data:
            try:
                fig = go.Figure(chart_data)
                png_bytes = pio.to_image(fig, format="png", width=700, height=380, scale=2)
                chart_b64 = base64.b64encode(png_bytes).decode("utf-8")
                chart_img_html = f'<img src="data:image/png;base64,{chart_b64}" style="width:100%;max-width:680px;margin:15px 0;border:1px solid #edf2f7;border-radius:12px;box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);" alt="Grafik Analisis" />'
            except Exception as chart_err:
                chart_img_html = f'<p style="color:#999;font-size:9pt;font-style:italic;">[Grafik tidak dapat dirender: {str(chart_err)[:100]}]</p>'

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

        # Bentuk tabel data log terlampir
        table_headers = ""
        table_rows = ""
        if parsed_data:
            headers = list(parsed_data[0].keys())
            table_headers = "".join([f"<th style='padding: 10px; font-weight: 700; text-transform: uppercase; font-size: 8pt;'>{h}</th>" for h in headers])
            
            # Batasi hanya 20 baris data agar PDF tetap rapi dan tidak terlalu panjang
            for row in parsed_data[:20]:
                row_str = "".join([f"<td style='padding: 8px; border-bottom: 1px solid #edf2f7;'>{row.get(h, '')}</td>" for h in headers])
                table_rows += f"<tr style='background-color: #ffffff;'>{row_str}</tr>"

        # Format tanggal pembuatan laporan secara dinamis (Indonesian Friendly)
        formatted_date = format_report_date(report.created_at, report.language)

        # Load logo image dari berkas aset frontend dan encode ke base64 jika tersedia
        logo_img_html = ""
        try:
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "LOGO_PETRO.png"))
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_b64 = base64.b64encode(f.read()).decode("utf-8")
                logo_img_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:48px;width:auto;vertical-align:middle;" alt="Logo Petrokimia" />'
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
                    font-size: 8.5pt;
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
                            <div class="company-name">PT PETROKIMIA GRESIK</div>
                            <div class="doc-subtitle">Sistem Otomasi Report Bulanan SOC Berbasis AI</div>
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

            <h2>1. Ringkasan Eksekutif (Executive Summary)</h2>
            <p>{exec_summary}</p>

            <h2>2. Visualisasi Data Analitik</h2>
            {chart_img_html if chart_img_html else '<p style="color:#718096;font-style:italic;">Visualisasi grafik belum tersedia. Jalankan "Generate Chart" terlebih dahulu.</p>'}

            <h2>3. Analisis Tren Ancaman (Trend Analysis)</h2>
            <p>{trend_analysis}</p>

            <h2>4. Analisis Tingkat Keparahan (Severity Analysis)</h2>
            <p>{severity_analysis}</p>

            <h2>5. Penilaian Risiko (Risk Assessment)</h2>
            <p>{risk_assessment}</p>

            <h2>6. Rekomendasi Tindakan Keamanan siber</h2>
            <ul>
                {rec_html}
            </ul>

            <h2>7. Kesimpulan (Conclusion)</h2>
            <p>{conclusion}</p>

            {"<div style='page-break-before: always;'></div>" if table_rows else ""}
            
            {f'''
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
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_io)
        if pisa_status.err:
            raise RuntimeError(f"Gagal mengonversi HTML ke PDF menggunakan xhtml2pdf: {pisa_status.err}")
        return pdf_io.getvalue()