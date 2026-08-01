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
from app.crud.report import get_parsed_data

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
        
        # Color Theme Config
        theme = (report.theme_color or "green").lower()
        theme_rgb_map = {
            "green": {"primary": RGBColor(0, 77, 37), "accent": RGBColor(217, 167, 0)},
            "navy": {"primary": RGBColor(15, 23, 42), "accent": RGBColor(56, 189, 248)},
            "dark": {"primary": RGBColor(17, 24, 39), "accent": RGBColor(129, 140, 248)},
            "gold": {"primary": RGBColor(120, 53, 15), "accent": RGBColor(245, 158, 11)},
        }
        theme_rgb = theme_rgb_map.get(theme, theme_rgb_map["green"])
        PRIMARY_COLOR = theme_rgb["primary"]
        ACCENT_COLOR = theme_rgb["accent"]
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
        
        # Tambahkan ornamen garis warna tema di bagian atas slide
        top_bar = slide.shapes.add_shape(
            1,  # MSO_SHAPE.RECTANGLE = 1
            Inches(0), Inches(0), Inches(10), Inches(0.35)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = PRIMARY_COLOR
        top_bar.line.color.rgb = PRIMARY_COLOR
        
        # Tambahkan Kotak Teks Judul Utama
        tx_box = slide.shapes.add_textbox(Inches(0.75), Inches(1.8), Inches(8.5), Inches(2.8))
        tf = tx_box.text_frame
        tf.word_wrap = True
        
        # Nama Perusahaan / Kop Header Title
        p_comp = tf.paragraphs[0]
        p_comp.text = report.header_title or "PT PETROKIMIA GRESIK"
        p_comp.font.size = Pt(22)
        p_comp.font.bold = True
        p_comp.font.color.rgb = PRIMARY_COLOR
        p_comp.alignment = PP_ALIGN.LEFT
        
        # Judul Laporan utama
        p_title = tf.add_paragraph()
        p_title.text = report.title
        p_title.font.size = Pt(38)
        p_title.font.bold = True
        p_title.font.color.rgb = PRIMARY_COLOR
        p_title.alignment = PP_ALIGN.LEFT
        
        # Subtitle / Kop Header Subtitle
        p_sub = tf.add_paragraph()
        formatted_date = format_report_date(report.period_end or datetime.datetime.now(), report.language)
        sub_text = report.header_subtitle or "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI"
        p_sub.text = f"{sub_text} | {report.data_type.upper()} | {formatted_date}"
        p_sub.font.size = Pt(13)
        p_sub.font.bold = True
        p_sub.font.color.rgb = ACCENT_COLOR
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

        # -------------------------------------------------------------
        # Helper Fase B: slide kartu KPI dari metrics_table (opsional, AI-generated)
        # -------------------------------------------------------------
        def add_metrics_slide(metrics: list):
            slide_layout = prs.slide_layouts[6]
            m_slide = prs.slides.add_slide(slide_layout)

            if has_logo:
                try:
                    m_slide.shapes.add_picture(logo_path, Inches(7.6), Inches(0.12), width=Inches(1.9))
                except Exception:
                    pass

            title_box = m_slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(7.0), Inches(0.7))
            p = title_box.text_frame.paragraphs[0]
            p.text = "Ringkasan Metrik Utama"
            p.font.size = Pt(26)
            p.font.bold = True
            p.font.color.rgb = GREEN
            add_title_rule(m_slide, y_top=Inches(1.05))

            # Batasi 8 kartu biar tidak overflow kalau AI kasih metrics_table terlalu panjang
            items = metrics[:8]
            cols = min(len(items), 4) or 1
            margin_x, usable_width, gap = 0.6, 8.8, 0.25
            card_w = (usable_width - gap * (cols - 1)) / cols
            card_h, row_gap, start_top = 1.7, 0.3, 1.5

            for idx, item in enumerate(items):
                row, col = idx // cols, idx % cols
                left, top = margin_x + col * (card_w + gap), start_top + row * (card_h + row_gap)

                card = m_slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(card_w), Inches(card_h)
                )
                card.fill.solid()
                card.fill.fore_color.rgb = RGBColor(0xF7, 0xFA, 0xFC)
                card.line.color.rgb = GREEN
                card.line.width = Pt(1)

                is_dict = isinstance(item, dict)
                value = str(item.get("value", "-")) if is_dict else str(item)
                pct = str(item.get("percentage") or "").strip() if is_dict else ""
                label = str(item.get("label", "")) if is_dict else ""

                ctf = card.text_frame
                ctf.word_wrap = True
                ctf.vertical_anchor = MSO_ANCHOR.MIDDLE

                p_value = ctf.paragraphs[0]
                p_value.text = value + (f"  ({pct})" if pct else "")
                p_value.font.size = Pt(22)
                p_value.font.bold = True
                p_value.font.color.rgb = GREEN
                p_value.alignment = PP_ALIGN.CENTER

                if label:
                    p_label = ctf.add_paragraph()
                    p_label.text = label
                    p_label.font.size = Pt(12)
                    p_label.font.color.rgb = DARK_TEXT
                    p_label.alignment = PP_ALIGN.CENTER
                    p_label.space_before = Pt(4)

        # Ambil data AI summary
        ai_summary = report.ai_summary or {}
        chart_data = report.chart_data or {}
        exec_summary = ai_summary.get("executive_summary", "Ringkasan eksekutif tidak tersedia.")
        trend_analysis = ai_summary.get("trend_analysis", "Analisis tren tidak tersedia.")
        severity_analysis = ai_summary.get("severity_analysis", "Analisis severity tidak tersedia.")
        risk_assessment = ai_summary.get("risk_assessment", "Penilaian risiko tidak tersedia.")
        recommendations = ai_summary.get("recommendations", [])
        conclusion = ai_summary.get("conclusion", "Kesimpulan tidak tersedia.")
        # Fase B — key opsional, kosong ([]) di laporan lama yang belum punya key ini
        key_findings = ai_summary.get("key_findings") or []
        metrics_table = ai_summary.get("metrics_table") or []
        chart_captions = ai_summary.get("chart_captions") or []

        # Section mana yang ditampilkan, sesuai pilihan "Include Sections" user di Report
        # Settings. included_sections None/kosong berarti semua ditampilkan (laporan lama
        # sebelum fitur ini ada, atau user tidak menyentuh pilihan defaultnya).
        included = report.included_sections or {}

        def is_included(key: str) -> bool:
            return included.get(key, True)

        # Slide 2: Ringkasan Eksekutif (+ Temuan Kunci kalau AI menyertakan key_findings)
        if is_included("executive_summary"):
            exec_content = [exec_summary]
            if key_findings:
                findings_html = "<ul>" + "".join(f"<li>{f}</li>" for f in key_findings) + "</ul>"
                exec_content.append(findings_html)
            add_content_slide("Ringkasan Eksekutif", exec_content)

        # Slide 2b: Kartu Metrik Utama (hanya dibuat kalau AI menyertakan metrics_table)
        if metrics_table:
            add_metrics_slide(metrics_table)

        # Slide 3+: Visualisasi Chart (Render SEMUA 3 chart yang ada)
        charts_list = []
        parsed_data = get_parsed_data(report)
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

        # Default narasi fallback jika AI belum generate chart_captions
        default_narasi = [
            "Distribusi data berdasarkan kategori utama dalam periode laporan ini.",
            "Tren dan pola data dari waktu ke waktu selama periode yang dianalisis.",
            "Perbandingan antar entitas atau kategori berdasarkan indikator utama.",
            "Analisis frekuensi dan proporsi per kelompok data yang teridentifikasi.",
            "Ringkasan visual temuan utama dari keseluruhan dataset yang diproses.",
        ]

        if PLOTLY_AVAILABLE and charts_list:
            for idx, c_dict in enumerate(charts_list):
                try:
                    # Render chart lebih kecil — hanya menempati ~60% lebar slide (kiri)
                    png_bytes = ChartGenerator.render_png(c_dict, width=700, height=440, scale=2)
                    img_io = io.BytesIO(png_bytes)

                    chart_slide_layout = prs.slide_layouts[6]
                    chart_slide = prs.slides.add_slide(chart_slide_layout)

                    if has_logo:
                        try:
                            chart_slide.shapes.add_picture(logo_path, Inches(8.3), Inches(0.1), width=Inches(1.5))
                        except Exception:
                            pass

                    # Judul slide
                    chart_title_text = ""
                    raw_title = c_dict.get("layout", {}).get("title", {})
                    if isinstance(raw_title, dict):
                        chart_title_text = raw_title.get("text", f"Visualisasi Data #{idx+1}")
                    elif isinstance(raw_title, str):
                        chart_title_text = raw_title
                    else:
                        chart_title_text = f"Visualisasi Data #{idx+1}"

                    title_box = chart_slide.shapes.add_textbox(Inches(0.3), Inches(0.12), Inches(7.8), Inches(0.65))
                    tf = title_box.text_frame
                    p = tf.paragraphs[0]
                    p.text = chart_title_text
                    p.font.size = Pt(20)
                    p.font.bold = True
                    p.font.color.rgb = PRIMARY_COLOR

                    # Garis pemisah header
                    rule = chart_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.3), Inches(0.82), Inches(9.4), Pt(2))
                    rule.fill.solid()
                    rule.fill.fore_color.rgb = ACCENT_COLOR
                    rule.line.fill.background()

                    # KIRI: Chart Image (60% lebar slide)
                    chart_slide.shapes.add_picture(img_io, Inches(0.2), Inches(1.0), Inches(5.8), Inches(5.5))

                    # KANAN: Panel narasi AI (40% lebar slide)
                    # Background box narasi
                    narasi_bg = chart_slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(6.15), Inches(1.0), Inches(3.6), Inches(5.5)
                    )
                    narasi_bg.fill.solid()
                    narasi_bg.fill.fore_color.rgb = RGBColor(0xFF, 0xFB, 0xEB)  # Amber-50
                    narasi_bg.line.color.rgb = RGBColor(0xD9, 0x77, 0x06)       # Amber-600
                    narasi_bg.line.width = Pt(1.5)

                    # Label "💡 Narasi Insight AI"
                    label_box = chart_slide.shapes.add_textbox(Inches(6.3), Inches(1.15), Inches(3.3), Inches(0.5))
                    lp = label_box.text_frame.paragraphs[0]
                    lp.text = "💡  Narasi Insight AI"
                    lp.font.size = Pt(12)
                    lp.font.bold = True
                    lp.font.color.rgb = RGBColor(0x92, 0x40, 0x0E)  # Amber-900

                    # Teks narasi
                    narasi_text = ""
                    if idx < len(chart_captions) and chart_captions[idx]:
                        narasi_text = str(chart_captions[idx])
                    else:
                        narasi_text = default_narasi[idx % len(default_narasi)]

                    narasi_box = chart_slide.shapes.add_textbox(Inches(6.3), Inches(1.75), Inches(3.3), Inches(4.45))
                    ntf = narasi_box.text_frame
                    ntf.word_wrap = True
                    np_ = ntf.paragraphs[0]
                    np_.text = narasi_text
                    np_.font.size = Pt(13)
                    np_.font.color.rgb = RGBColor(0x37, 0x41, 0x51)  # Gray-700
                    np_.line_spacing = 1.4

                except Exception as chart_err:
                    print(f"[PPT CHART WARNING] Gagal merender grafik slide #{idx+1}: {chart_err}")


        # Slide 4: Analisis Tren & Severity (satu slide gabungan — cuma dimasukkan bagiannya
        # yang beneran dipilih user; skip seluruh slide kalau dua-duanya di-exclude)
        trend_severity_content = []
        if is_included("trend_analysis"):
            trend_severity_content.append(trend_analysis)
        if is_included("severity_analysis"):
            trend_severity_content.append(severity_analysis)
        if trend_severity_content:
            add_content_slide("Analisis Tren & Severity", trend_severity_content)

        # Slide 4: Penilaian Risiko
        if is_included("risk_assessment"):
            add_content_slide("Penilaian Risiko Keamanan", [risk_assessment])

        # Slide 5: Rekomendasi Mitigasi (Bulleted List)
        if is_included("recommendations"):
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
        if is_included("conclusion"):
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