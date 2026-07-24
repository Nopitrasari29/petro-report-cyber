# backend/app/services/export_ppt.py
import base64
import datetime
import io
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from app.models.report import Report
from app.services.html_to_pptx import parse_html_to_blocks, render_blocks_to_textframe, render_tables_to_slide
from app.services.chart_generator import ChartGenerator

try:
    import plotly  # noqa: F401 — cuma dipakai untuk cek ketersediaan; render sungguhan lewat ChartGenerator.render_png
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def format_report_date(dt: datetime.datetime, language: str | None) -> str:
    """
    Format tanggal pembuatan laporan secara dinamis berdasarkan preferensi bahasa
    agar otomatis melokalkan nama bulan ke Bahasa Indonesia di slide judul.
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


class PPTXExporter:
    @classmethod
    def generate_ppt_report(cls, report: Report) -> bytes:
        """
        Menghasilkan file PowerPoint (.pptx) dari data laporan menggunakan python-pptx.
        """
        prs = Presentation()
        
        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "LOGO_PETRO_DANANTARA.png"))
        if not os.path.exists(logo_path):
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "LOGO_PETRO.png"))
        has_logo = os.path.exists(logo_path)
        
        # Palet Warna Korporat Resmi PT Petrokimia Gresik (GSM Aligned)
        GREEN = RGBColor(0, 77, 37)       # Hijau Petro Resmi (#004D25)
        GOLD = RGBColor(217, 167, 0)      # Emas Petro Resmi (#d9a700)
        DARK_TEXT = RGBColor(51, 51, 51)  # Hitam Elegan
        
        # -------------------------------------------------------------
        # Slide 1: Slide Judul (Menggunakan layout kosong)
        # -------------------------------------------------------------
        blank_slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(blank_slide_layout)
        
        # Tambahkan logo Petrokimia di cover slide (diperbesar agar menonjol)
        if has_logo:
            try:
                slide.shapes.add_picture(logo_path, Inches(6.8), Inches(0.55), width=Inches(2.7))
            except Exception:
                pass
        
        # Tambahkan ornamen garis hijau di bagian atas slide
        top_bar = slide.shapes.add_shape(
            1,  # MSO_SHAPE.RECTANGLE = 1
            Inches(0), Inches(0), Inches(10), Inches(0.35)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = GREEN
        top_bar.line.color.rgb = GREEN
        
        # Tambahkan Kotak Teks Judul Utama
        tx_box = slide.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(8.5), Inches(2.8))
        tf = tx_box.text_frame
        tf.word_wrap = True
        
        # Nama Perusahaan
        p_comp = tf.paragraphs[0]
        p_comp.text = "PT PETROKIMIA GRESIK"
        p_comp.font.size = Pt(22)
        p_comp.font.bold = True
        p_comp.font.color.rgb = GREEN
        p_comp.alignment = PP_ALIGN.LEFT
        
        # Judul Laporan utama
        p_title = tf.add_paragraph()
        p_title.text = report.title
        p_title.font.size = Pt(38)
        p_title.font.bold = True
        p_title.font.color.rgb = GREEN
        p_title.alignment = PP_ALIGN.LEFT
        p_title.space_before = Pt(14)
        
        # Subjudul (Penanggalan yang sudah melokalkan bahasa Indonesia)
        p_sub = tf.add_paragraph()
        formatted_date = format_report_date(report.created_at, report.language)
        p_sub.text = f"Sistem Otomasi Report SOC | Laporan {report.data_type.upper()} | {formatted_date}"
        p_sub.font.size = Pt(14)
        p_sub.font.bold = True
        p_sub.font.color.rgb = GOLD
        p_sub.alignment = PP_ALIGN.LEFT
        p_sub.space_before = Pt(20)
        p_sub.line_spacing = 1.2

        # -------------------------------------------------------------
        # Helper: garis aksen tipis + label kecil di bawah judul slide
        # -------------------------------------------------------------
        def add_title_rule(c_slide, y_top=Inches(1.35)):
            rule = c_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.75), y_top, Inches(1.2), Pt(3))
            rule.fill.solid()
            rule.fill.fore_color.rgb = GOLD
            rule.line.fill.background()

        # -------------------------------------------------------------
        # Helper: bar aksen vertikal tipis di sisi kiri blok konten
        # -------------------------------------------------------------
        def add_left_accent(c_slide, top, height):
            bar = c_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.4), top, Pt(3.5), height)
            bar.fill.solid()
            bar.fill.fore_color.rgb = GREEN
            bar.line.fill.background()

        # -------------------------------------------------------------
        # Helper Fungsi untuk Membuat Slide Konten Generik
        # -------------------------------------------------------------
        def add_content_slide(title_text: str, content_htmls: list):
            slide_layout = prs.slide_layouts[5]
            c_slide = prs.slides.add_slide(slide_layout)

            if has_logo:
                try:
                    c_slide.shapes.add_picture(logo_path, Inches(7.6), Inches(0.12), width=Inches(1.9))
                except Exception:
                    pass

            title_shape = c_slide.shapes.title
            title_shape.text = title_text
            title_shape.text_frame.paragraphs[0].font.size = Pt(30)
            title_shape.text_frame.paragraphs[0].font.bold = True
            title_shape.text_frame.paragraphs[0].font.color.rgb = GREEN
            add_title_rule(c_slide)

            body_left, body_top, body_width, body_height = Inches(0.9), Inches(1.7), Inches(8.35), Inches(4.4)
            add_left_accent(c_slide, body_top, body_height)
            body_box = c_slide.shapes.add_textbox(body_left, body_top, body_width, body_height)
            btf = body_box.text_frame
            btf.word_wrap = True
            btf.vertical_anchor = MSO_ANCHOR.MIDDLE

            all_blocks = []
            for html_or_text in content_htmls:
                all_blocks.extend(parse_html_to_blocks(html_or_text))

            pending_tables = render_blocks_to_textframe(btf, all_blocks, base_size=Pt(15), base_color=DARK_TEXT)

            if pending_tables:
                render_tables_to_slide(c_slide, pending_tables, body_left, Inches(5.6), body_width)


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

        # Slide 3+: Visualisasi Chart (Render SEMUA chart yang ada)
        charts_list = []
        if isinstance(chart_data.get("charts"), list) and len(chart_data["charts"]) > 0:
            charts_list = chart_data["charts"]
        elif "data" in chart_data:
            charts_list = [chart_data]

        if PLOTLY_AVAILABLE and charts_list:
            for idx, c_dict in enumerate(charts_list):
                try:
                    png_bytes = ChartGenerator.render_png(c_dict, width=1000, height=560, scale=2)
                    img_io = io.BytesIO(png_bytes)

                    chart_slide_layout = prs.slide_layouts[6]
                    chart_slide = prs.slides.add_slide(chart_slide_layout)

                    if has_logo:
                        try:
                            chart_slide.shapes.add_picture(logo_path, Inches(7.6), Inches(0.12), width=Inches(1.9))
                        except Exception:
                            pass

                    chart_title_text = c_dict.get("layout", {}).get("title", {}).get("text", f"Visualisasi Data Analitik #{idx+1}")

                    title_box = chart_slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(7.0), Inches(0.8))
                    tf = title_box.text_frame
                    p = tf.paragraphs[0]
                    p.text = chart_title_text
                    p.font.size = Pt(22)
                    p.font.bold = True
                    p.font.color.rgb = GREEN

                    p_sub = tf.add_paragraph()
                    p_sub.text = f"Visualisasi Grafik Analitis Keamanan #{idx+1} | PT Petrokimia Gresik"
                    p_sub.font.size = Pt(11)
                    p_sub.font.bold = False
                    p_sub.font.color.rgb = DARK_TEXT
                    p_sub.space_before = Pt(4)

                    chart_slide.shapes.add_picture(img_io, Inches(0.5), Inches(1.2), Inches(9.0), Inches(5.2))
                except Exception as chart_err:
                    print(f"[PPT CHART WARNING] Gagal merender grafik slide #{idx+1}: {chart_err}")

        # Slide 4: Analisis Tren & Severity
        add_content_slide("Analisis Tren & Severity", [trend_analysis, severity_analysis])

        # Slide 4: Penilaian Risiko
        add_content_slide("Penilaian Risiko Keamanan", [risk_assessment])

        # Slide 5: Rekomendasi Mitigasi (Bulleted List)
        rec_slide_layout = prs.slide_layouts[5]
        rec_slide = prs.slides.add_slide(rec_slide_layout)
        
        # Tambahkan logo kecil di pojok kanan atas slide rekomendasi
        if has_logo:
            try:
                rec_slide.shapes.add_picture(logo_path, Inches(7.6), Inches(0.12), width=Inches(1.9))
            except Exception:
                pass
        
        title_shape = rec_slide.shapes.title
        title_shape.text = "Rekomendasi Keamanan Siber"
        title_shape.text_frame.paragraphs[0].font.size = Pt(28)
        title_shape.text_frame.paragraphs[0].font.bold = True
        title_shape.text_frame.paragraphs[0].font.color.rgb = GREEN
        add_title_rule(rec_slide)

        rec_body_top, rec_body_height = Inches(1.7), Inches(4.4)
        add_left_accent(rec_slide, rec_body_top, rec_body_height)
        body_box = rec_slide.shapes.add_textbox(Inches(0.9), rec_body_top, Inches(8.35), rec_body_height)
        btf = body_box.text_frame
        btf.word_wrap = True
        btf.vertical_anchor = MSO_ANCHOR.MIDDLE

        rec_blocks = []
        for rec in recommendations:
            item_blocks = parse_html_to_blocks(rec)
            if not item_blocks:
                continue
            # Paksa tiap rekomendasi tampil sebagai satu bullet, apapun struktur HTML aslinya
            # (rekomendasi disimpan sebagai array per-item, bukan satu blok list panjang).
            item_blocks[0]["list"] = "bullet"
            rec_blocks.extend(item_blocks)

        pending_tables = render_blocks_to_textframe(btf, rec_blocks, base_size=Pt(15), base_color=DARK_TEXT)
        if pending_tables:
            render_tables_to_slide(rec_slide, pending_tables, Inches(0.9), Inches(5.6), Inches(8.35))

        if not recommendations:
            p = btf.paragraphs[0]
            p.text = "Tidak ada rekomendasi yang tersedia."
            p.font.size = Pt(14)

        # Slide 6: Kesimpulan
        add_content_slide("Kesimpulan Akhir", [conclusion])

        # -------------------------------------------------------------
        # Footer halaman: nomor halaman + nama perusahaan, ditambahkan di akhir
        # (setelah semua slide selesai dibuat) supaya total halaman sudah pasti diketahui.
        # Slide 0 (cover) sengaja dilewati karena sudah punya desainnya sendiri.
        # -------------------------------------------------------------
        total_slides = len(prs.slides)
        for idx, content_slide in enumerate(prs.slides):
            if idx == 0:
                continue
            footer_line = content_slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(6.95), Inches(9), Pt(0.75)
            )
            footer_line.fill.solid()
            footer_line.fill.fore_color.rgb = GOLD
            footer_line.line.fill.background()

            footer_box = content_slide.shapes.add_textbox(Inches(0.5), Inches(7.02), Inches(9), Inches(0.35))
            ftf = footer_box.text_frame
            fp = ftf.paragraphs[0]
            fp.text = f"PT Petrokimia Gresik  |  Internal & Confidential  |  Halaman {idx + 1} dari {total_slides}"
            fp.font.size = Pt(9)
            fp.font.color.rgb = RGBColor(140, 140, 140)

        # Simpan ke byte stream memori agar bisa dikirim via API
        ppt_io = io.BytesIO()
        prs.save(ppt_io)
        ppt_io.seek(0)
        return ppt_io.read()