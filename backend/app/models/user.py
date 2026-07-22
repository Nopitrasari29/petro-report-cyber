# backend/app/models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text  # Ditambahkan import Text
from sqlalchemy.sql import func
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_token_expiry = Column(DateTime(timezone=True), nullable=True)
    reset_password_token = Column(String, nullable=True)
    reset_password_token_expiry = Column(DateTime(timezone=True), nullable=True)
    
    full_name = Column(String, nullable=True)
    role = Column(String, default="Analyst")
    department = Column(String, default="IT Security SOC")
    avatar_url = Column(Text, nullable=True)  # Diubah menjadi Text agar aman menampung string Base64 ukuran besar
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Preferensi personal per-user (BUKAN pengaturan global) — tiap user ubah sendiri,
    # tidak mempengaruhi user lain sama sekali.
    language = Column(String, default="English")
    appearance = Column(String, default="light")
    notify_report_success = Column(Boolean, default=True)
    notify_report_failed = Column(Boolean, default=True)

    # False untuk akun yang daftar via Google (passwordnya di-generate acak, user tidak pernah
    # tahu isinya) sampai user secara sadar nge-set password sendiri lewat Settings. True untuk
    # akun yang daftar manual dari awal.
    password_set = Column(Boolean, default=True)