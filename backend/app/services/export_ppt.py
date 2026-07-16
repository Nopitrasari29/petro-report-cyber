from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from app.models.report import Report
import io

try:
    import plotly.io as pio
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

class PPTXExporter:
    @classmethod
    def generate_ppt_report(cls, report: Report) -> bytes:
        """
        Menghasilkan file PowerPoint (.pptx) dari data laporan menggunakan python-pptx.
        """
        prs = Presentation()
        
        # Palet Warna Korporat Petrokimia Gresik
        GREEN = RGBColor(0, 158, 84)      # Hijau Petro
        BLUE = RGBColor(0, 90, 156)       # Biru Petro
        DARK_TEXT = RGBColor(51, 51, 51)  # Hitam Elegan
        
        # -------------------------------------------------------------
        # Slide 1: Slide Judul (Menggunakan layout kosong)
        # -------------------------------------------------------------
        blank_slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(blank_slide_layout)
        
        # Tambahkan ornamen garis hijau di bagian atas slide
        top_bar = slide.shapes.add_shape(
            1,  # MSO_SHAPE.RECTANGLE = 1
            Inches(0), Inches(0), Inches(10), Inches(0.4)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = GREEN
        top_bar.line.color.rgb = GREEN
        
        # Tambahkan Kotak Teks Judul Utama
        tx_box = slide.shapes.add_textbox(Inches(0.75), Inches(2.2), Inches(8.5), Inches(2.5))
        tf = tx_box.text_frame
        tf.word_wrap = True
        
        # Perusahaan
        p_comp = tf.paragraphs[0]
        p_comp.text = "PT PETROKIMIA GRESIK"
        p_comp.font.size = Pt(20)
        p_comp.font.bold = True
        p_comp.font.color.rgb = GREEN
        p_comp.alignment = PP_ALIGN.LEFT
        
        # Judul Laporan
        p_title = tf.add_paragraph()
        p_title.text = report.title
        p_title.font.size = Pt(32)
        p_title.font.bold = True
        p_title.font.color.rgb = BLUE
        p_title.alignment = PP_ALIGN.LEFT
        p_title.space_before = Pt(12)
        
        # Subjudul
        p_sub = tf.add_paragraph()
        formatted_date = report.created_at.strftime('%d %B %Y') if report.created_at else "-"
        p_sub.text = f"Sistem Otomasi Report SOC | Laporan {report.data_type.upper()} | {formatted_date}"
        p_sub.font.size = Pt(13)
        p_sub.font.color.rgb = DARK_TEXT
        p_sub.alignment = PP_ALIGN.LEFT
        p_sub.space_before = Pt(18)

        # -------------------------------------------------------------
        # Helper Fungsi untuk Membuat Slide Konten Generik
        # -------------------------------------------------------------
        def add_content_slide(title_text: str, content_paragraphs: list):
            # Layout 5 adalah slide bertajuk tanpa konten bawaan
            slide_layout = prs.slide_layouts[5]
            c_slide = prs.slides.add_slide(slide_layout)
            
            # Konfigurasi Judul Slide
            title_shape = c_slide.shapes.title
            title_shape.text = title_text
            title_shape.text_frame.paragraphs[0].font.size = Pt(28)
            title_shape.text_frame.paragraphs[0].font.bold = True
            title_shape.text_frame.paragraphs[0].font.color.rgb = GREEN
            
            # Tambahkan boks teks konten di bawah judul
            body_box = c_slide.shapes.add_textbox(Inches(0.75), Inches(1.5), Inches(8.5), Inches(4.8))
            btf = body_box.text_frame
            btf.word_wrap = True
            
            for i, p_text in enumerate(content_paragraphs):
                p = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
                p.text = p_text
                p.font.size = Pt(14)
                p.font.color.rgb = DARK_TEXT
                p.space_after = Pt(12)
                p.line_spacing = 1.3
                
        # Ambil data AI summary
        ai_summary = report.ai_summary or {}
        chart_data = report.chart_data or {}
        exec_summary = ai_summary.get("executive_summary", "Ringkasan eksekutif tidak tersedia.")
        trend_analysis = ai_summary.get("trend_analysis", "Analisis tren tidak tersedia.")
        severity_analysis = ai_summary.get("severity_analysis", "Analisis severity tidak tersedia.")
        risk_assessment = ai_summary.get("risk_assessment", "Penilaian risiko tidak tersedia.")
        recommendations = ai_summary.get("recommendations", [])
        conclusion = ai_summary.get("conclusion", "Kesimpulan tidak tersedia.")

        # Slide 2: Ringkasan Eksekutif
        add_content_slide("Ringkasan Eksekutif", [exec_summary])

        # Slide 3: Visualisasi Chart (jika chart tersedia)
        if chart_data and PLOTLY_AVAILABLE and "data" in chart_data:
            try:
                fig = go.Figure(chart_data)
                png_bytes = pio.to_image(fig, format="png", width=900, height=500, scale=2)
                img_io = io.BytesIO(png_bytes)

                chart_slide_layout = prs.slide_layouts[6]  # blank layout
                chart_slide = prs.slides.add_slide(chart_slide_layout)

                # Judul slide chart
                title_box = chart_slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.7))
                tf = title_box.text_frame
                p = tf.paragraphs[0]
                p.text = "Visualisasi Data Analitik"
                p.font.size = Pt(24)
                p.font.bold = True
                p.font.color.rgb = GREEN

                # Tambahkan gambar chart
                chart_slide.shapes.add_picture(img_io, Inches(0.5), Inches(1.0), Inches(9), Inches(5.0))
            except Exception:
                # Jika chart gagal dirender, tambahkan slide teks penjelasan
                add_content_slide("Visualisasi Data", ["Chart tidak dapat dirender. Pastikan kaleido terinstall."])

        # Slide 4: Analisis Tren & Severity
        add_content_slide("Analisis Tren & Severity", [trend_analysis, severity_analysis])

        # Slide 4: Penilaian Risiko
        add_content_slide("Penilaian Risiko Keamanan", [risk_assessment])

        # Slide 5: Rekomendasi Mitigasi (Bulleted List)
        rec_slide_layout = prs.slide_layouts[5]
        rec_slide = prs.slides.add_slide(rec_slide_layout)
        
        title_shape = rec_slide.shapes.title
        title_shape.text = "Rekomendasi Keamanan siber"
        title_shape.text_frame.paragraphs[0].font.size = Pt(28)
        title_shape.text_frame.paragraphs[0].font.bold = True
        title_shape.text_frame.paragraphs[0].font.color.rgb = GREEN
        
        body_box = rec_slide.shapes.add_textbox(Inches(0.75), Inches(1.5), Inches(8.5), Inches(4.8))
        btf = body_box.text_frame
        btf.word_wrap = True
        
        for i, rec in enumerate(recommendations):
            p = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
            p.text = f"• {rec}"
            p.font.size = Pt(13.5)
            p.font.color.rgb = DARK_TEXT
            p.space_after = Pt(10)
            p.line_spacing = 1.2
            
        if not recommendations:
            p = btf.paragraphs[0]
            p.text = "Tidak ada rekomendasi yang tersedia."
            p.font.size = Pt(14)

        # Slide 6: Kesimpulan
        add_content_slide("Kesimpulan Akhir", [conclusion])

        # Simpan ke byte stream memori agar bisa dikirim via API
        ppt_io = io.BytesIO()
        prs.save(ppt_io)
        ppt_io.seek(0)
        return ppt_io.read()
