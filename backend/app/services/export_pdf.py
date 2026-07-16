import base64
from typing import Any, Dict
import io
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
                chart_img_html = f'<img src="data:image/png;base64,{chart_b64}" style="width:100%;max-width:680px;margin:10px 0;border:1px solid #eee;border-radius:4px;" alt="Grafik Analisis" />'
            except Exception as chart_err:
                chart_img_html = f'<p style="color:#999;font-size:9pt;">[Grafik tidak dapat dirender: {str(chart_err)[:100]}]</p>'

        # Ekstrak data narasi AI dari JSON siber
        exec_summary = ai_summary.get("executive_summary", "Ringkasan eksekutif tidak tersedia.")
        trend_analysis = ai_summary.get("trend_analysis", "Analisis tren tidak tersedia.")
        severity_analysis = ai_summary.get("severity_analysis", "Analisis severity tidak tersedia.")
        risk_assessment = ai_summary.get("risk_assessment", "Penilaian risiko tidak tersedia.")
        recommendations = ai_summary.get("recommendations", [])
        conclusion = ai_summary.get("conclusion", "Kesimpulan tidak tersedia.")

        # Bentuk daftar html rekomendasi
        rec_html = ""
        for rec in recommendations:
            rec_html += f"<li>{rec}</li>"
        if not rec_html:
            rec_html = "<li>Rekomendasi tidak tersedia saat ini.</li>"

        # Bentuk tabel data log terlampir
        table_headers = ""
        table_rows = ""
        if parsed_data:
            headers = list(parsed_data[0].keys())
            table_headers = "".join([f"<th>{h}</th>" for h in headers])
            
            # Batasi hanya 20 baris data agar PDF tetap rapi dan tidak terlalu panjang
            for row in parsed_data[:20]:
                row_str = "".join([f"<td>{row.get(h, '')}</td>" for h in headers])
                table_rows += f"<tr>{row_str}</tr>"

        # Format tanggal pembuatan laporan
        formatted_date = report.created_at.strftime('%d %B %Y') if report.created_at else "-"

        # HTML Template dengan layout brand Petrokimia Gresik
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
                        content: "CONFIDENTIAL";
                        font-family: Arial, sans-serif;
                        font-size: 8pt;
                        color: #d9534f;
                        font-weight: bold;
                    }}
                    @bottom-right {{
                        content: "Halaman " counter(page);
                        font-family: Arial, sans-serif;
                        font-size: 9pt;
                        color: #666;
                    }}
                    @bottom-left {{
                        content: "PT Petrokimia Gresik - SOC Report Automation";
                        font-family: Arial, sans-serif;
                        font-size: 9pt;
                        color: #666;
                    }}
                }}
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #333;
                    line-height: 1.6;
                    font-size: 11pt;
                }}
                .header-container {{
                    border-bottom: 3px solid #009E54;
                    padding-bottom: 10px;
                    margin-bottom: 25px;
                }}
                .company-name {{
                    font-size: 20pt;
                    font-weight: bold;
                    color: #009E54;
                    margin: 0;
                    letter-spacing: 0.5px;
                }}
                .doc-subtitle {{
                    font-size: 10pt;
                    color: #005A9C;
                    margin: 5px 0 0 0;
                    text-transform: uppercase;
                    font-weight: bold;
                    letter-spacing: 1px;
                }}
                h1 {{
                    font-size: 18pt;
                    color: #333;
                    margin-top: 0;
                    margin-bottom: 15px;
                }}
                h2 {{
                    font-size: 13pt;
                    color: #009E54;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 4px;
                    margin-top: 25px;
                    margin-bottom: 10px;
                    page-break-after: avoid;
                }}
                p {{
                    margin-top: 0;
                    margin-bottom: 12px;
                    text-align: justify;
                }}
                ul {{
                    margin-top: 0;
                    margin-bottom: 12px;
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 6px;
                }}
                .meta-table {{
                    width: 100%;
                    margin-bottom: 20px;
                    font-size: 10pt;
                    border-collapse: collapse;
                }}
                .meta-table td {{
                    padding: 5px 0;
                }}
                .meta-label {{
                    font-weight: bold;
                    width: 130px;
                    color: #555;
                }}
                table.data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                    margin-bottom: 20px;
                    font-size: 9pt;
                }}
                table.data-table th {{
                    background-color: #009E54;
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                    font-weight: bold;
                    color: white;
                }}
                table.data-table td {{
                    border: 1px solid #ddd;
                    padding: 6px 8px;
                }}
                .alert-info {{
                    background-color: #f7f9fa;
                    border-left: 4px solid #005A9C;
                    padding: 12px;
                    margin-bottom: 20px;
                    font-size: 9.5pt;
                    color: #555;
                }}
            </style>
        </head>
        <body>
            <div class="header-container">
                <table style="width: 100%; border: none;">
                    <tr>
                        <td style="padding: 0; border: none;">
                            <div class="company-name">PT PETROKIMIA GRESIK</div>
                            <div class="doc-subtitle">Sistem Otomasi Report Bulanan SOC Berbasis AI</div>
                        </td>
                    </tr>
                </table>
            </div>

            <h1>{title}</h1>
            
            <table class="meta-table">
                <tr>
                    <td class="meta-label">Jenis Data:</td>
                    <td>{data_type}</td>
                </tr>
                <tr>
                    <td class="meta-label">Tanggal Cetak:</td>
                    <td>{formatted_date}</td>
                </tr>
                <tr>
                    <td class="meta-label">Berkas Sumber:</td>
                    <td>{report.input_file_name or '-'}</td>
                </tr>
            </table>

            <div class="alert-info">
                <strong>Catatan Kerahasiaan:</strong> Dokumen ini berisi informasi operasional keamanan siber internal PT Petrokimia Gresik. 
                Dilarang mendistribusikan isi dokumen ini di luar pihak yang berwenang tanpa izin tertulis.
            </div>

            <h2>1. Ringkasan Eksekutif (Executive Summary)</h2>
            <p>{exec_summary}</p>

            <h2>2. Visualisasi Data Analitik</h2>
            {chart_img_html if chart_img_html else '<p style="color:#999;font-style:italic;">Visualisasi grafik belum tersedia. Jalankan "Generate Chart" terlebih dahulu.</p>'}

            <h2>3. Analisis Tren Ancaman (Trend Analysis)</h2>
            <p>{trend_analysis}</p>

            <h2>4. Analisis Tingkat Keparahan (Severity Analysis)</h2>
            <p>{severity_analysis}</p>

            <h2>5. Penilaian Risiko (Risk Assessment)</h2>
            <p>{risk_assessment}</p>

            <h2>6. Rekomendasi Tindakan Keamanan</h2>
            <ul>
                {rec_html}
            </ul>

            <h2>7. Kesimpulan (Conclusion)</h2>
            <p>{conclusion}</p>

            {"<div style='page-break-before: always;'></div>" if table_rows else ""}
            
            {f'''
            <h2>Lampiran: Sampel Data Log Mentah</h2>
            <p>Berikut adalah 20 baris pertama sampel data log yang berhasil diekstrak dan dianalisis oleh sistem:</p>
            <table class="data-table">
                <thead>
                    <tr>{table_headers}</tr>
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
