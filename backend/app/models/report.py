from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean, Float, Date
from sqlalchemy.sql import func
from app.db.session import Base

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    data_type = Column(String, nullable=False)  # firewall, email_security, ids_ips, vapt, etc.
    status = Column(String, default="draft")  # draft, parsed, analyzed, completed, failed
    input_file_name = Column(String, nullable=True)
    
    parsed_data = Column(JSON, nullable=True)
    # Fix #2: Path ke file JSON parsed data yang disimpan di file system (storage/parsed/).
    # Jika terisi, maka parsed_data harus dibaca dari file ini, bukan dari kolom JSON di atas.
    # Kolom JSON di atas tetap ada sebagai fallback untuk laporan-laporan lama (backward compat).
    parsed_data_path = Column(String, nullable=True)
    ai_summary = Column(JSON, nullable=True)  # Executive Summary, Trend Analysis, dll.
    chart_data = Column(JSON, nullable=True)   # Plotly config data
    
    file_pdf_path = Column(String, nullable=True)
    file_ppt_path = Column(String, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Kolom Baru Menyesuaikan Mockup
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    template_type = Column(String, nullable=True, default="SOC Executive Summary (Monthly)")
    output_format = Column(String, nullable=True, default="PDF")
    language = Column(String, nullable=True, default="Indonesian")
    include_ai_insights = Column(Boolean, default=True)
    include_raw_data_summary = Column(Boolean, default=True)
    
    ai_confidence = Column(Float, nullable=True, default=94.0)
    sla_met = Column(Boolean, default=True)
    processing_time_sec = Column(Integer, nullable=True, default=15)
    created_by_name = Column(String, default="SOC Analyst")
    threat_count_critical = Column(Integer, nullable=True, default=0)
    threat_count_high = Column(Integer, nullable=True, default=0)
    threat_count_medium = Column(Integer, nullable=True, default=0)
    threat_count_low = Column(Integer, nullable=True, default=0)
    threat_count_info = Column(Integer, nullable=True, default=0)
    total_records_parsed = Column(Integer, nullable=True, default=0)
    # Total ukuran file asli yang diupload (bytes, gabungan semua file kalau multi-upload).
    # NULL untuk laporan lama sebelum kolom ini ada.
    total_file_size_bytes = Column(Integer, nullable=True)

    # Dict {section_key: bool} atau List[{key, title, description}] — section dinamis yang dipilih user
    included_sections = Column(JSON, nullable=True)

    # Kustomisasi Template Kop & Tema Visual (Revisi Progress 2)
    header_title = Column(String, nullable=True, default="PT PETROKIMIA GRESIK")
    header_subtitle = Column(String, nullable=True, default="Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI")
    theme_color = Column(String, nullable=True, default="green")  # green, navy, dark, gold
    domain_type = Column(String, nullable=True, default="general")  # soc_security, financial, kpi_hr, general


    # Jumlah token yang sudah dihasilkan Ollama sejauh ini selama status="processing" (di-update
    # live oleh background job lewat streaming /api/chat), dan jadi angka final (eval_count) begitu
    # selesai. Dipakai untuk menghitung estimasi sisa waktu yang genuinely bereaksi ke kecepatan
    # generate token asli — bukan animasi/tebakan — mirip ETA download yang dihitung dari bytes/s.
    tokens_generated = Column(Integer, nullable=True, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
