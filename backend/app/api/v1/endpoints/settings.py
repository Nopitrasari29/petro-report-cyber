from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import json
import os

router = APIRouter()

# Tentukan path file settings lokal
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "core", "settings.json")

class SettingsSchema(BaseModel):
    organization_name: str = "PT Petrokimia Gresik"
    primary_color: str = "#008B45"
    secondary_color: str = "#2DAA7D"
    description: str = "AI-Powered Security Report Generator for SOC Team"
    
    default_template: str = "Executive SOC Report (Monthly)"
    default_output_format: str = "PDF"
    include_charts: bool = True
    include_exec_summary: bool = True
    confidential_watermark: bool = True
    
    ai_model_provider: str = "Ollama (Local)"
    ai_model: str = "qwen3:8b"
    ai_temperature: float = 0.3
    ai_max_tokens: int = 4000
    ai_prompt_style: str = "Executive Style"
    ai_narrative_length: str = "Medium"
    ai_language: str = "Indonesian"
    appearance: str = "light"
    
    storage_type: str = "Local Storage"
    storage_path: str = "/reports"
    storage_retention_days: int = 365
    storage_max_upload_mb: int = 250
    storage_auto_delete: bool = False
    
    chart_style: str = "Auto (Recommended)"
    chart_resolution: str = "High (1920px)"
    chart_refresh_interval: str = "Daily at 00:00"
    
    export_format: str = "PDF"
    export_enable_pptx: bool = True
    export_pptx_template: str = "Petrokimia - Executive Template"
    export_include_cover_page: bool = True
    export_table_of_contents: bool = True
    export_compress_files: bool = True
    
    security_2fa: bool = True
    security_timeout_minutes: int = 30
    security_ip_whitelist: bool = False
    security_audit_logging: bool = True
    security_encryption: bool = True

from app.db.session import SessionLocal, get_db
from app.models.system_setting import SystemSetting
from sqlalchemy.orm import Session

def load_settings_file() -> dict:
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        default_data = SettingsSchema().model_dump()
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_data, f, indent=2)
        return default_data
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def load_settings() -> dict:
    """
    Membaca pengaturan dari database (tabel system_settings). Jika belum ada, buat default.
    """
    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == "global").first()
        default_data = SettingsSchema().model_dump()
        if not setting:
            setting = SystemSetting(key="global", value=default_data)
            db.add(setting)
            db.commit()
            return default_data
            
        # Merge dengan default data agar field baru yang belum ada di DB tetap terisi default-nya
        merged_data = {**default_data, **(setting.value or {})}
        return merged_data
    except Exception as e:
        print(f"[SETTINGS WARNING] Gagal memuat dari DB: {e}. Fallback ke file.")
        return load_settings_file()
    finally:
        db.close()

@router.get("/")
def get_settings():
    """
    Mendapatkan pengaturan konfigurasi sistem aktif saat ini.
    """
    try:
        return load_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat pengaturan: {str(e)}")

@router.put("/")
def update_settings(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Memperbarui pengaturan konfigurasi sistem secara persisten ke database (hanya field yang dikirim).
    """
    try:
        # 1. Ambil settings saat ini dari DB/default
        current_settings = load_settings()
        
        # 2. Update field yang dikirim saja (partial update)
        for key, value in payload.items():
            current_settings[key] = value
            
        # 3. Validasi hasil merge dengan Pydantic Schema agar data type tetap aman
        validated_settings = SettingsSchema(**current_settings)
        data = validated_settings.model_dump()
        
        # 4. Simpan kembali ke DB
        setting = db.query(SystemSetting).filter(SystemSetting.key == "global").first()
        if not setting:
            setting = SystemSetting(key="global", value=data)
            db.add(setting)
        else:
            setting.value = data
        db.commit()
        
        # 5. Simpan ke file cadangan
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
            
        return {"status": "success", "message": "Pengaturan berhasil diperbarui secara persisten ke database.", "settings": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui pengaturan: {str(e)}")

# ── PROFILE CONFIGURATION ENDPOINTS ─────────────────────────────

from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import UserResponse

class ProfileUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    avatar_url: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

@router.get("/profile", response_model=UserResponse)
def get_profile(current_user = Depends(get_current_user)):
    """
    Mendapatkan data profil user yang sedang login dari database.
    """
    return current_user

@router.put("/profile", response_model=UserResponse)
def update_profile(
    profile_in: ProfileUpdateSchema,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memperbarui data profil user di database secara riil.
    """
    from app.crud.user import update_user, get_user_by_email
    from app.core.security import verify_password, get_password_hash
    
    # Validasi email jika diubah agar unik
    if profile_in.email and profile_in.email != current_user.email:
        existing = get_user_by_email(db, email=profile_in.email)
        if existing:
            raise HTTPException(status_code=400, detail="Alamat email sudah digunakan oleh pengguna lain.")
            
    update_data = profile_in.model_dump(exclude_unset=True)
    
    # Penanganan perubahan password
    if profile_in.new_password:
        if not profile_in.current_password:
            raise HTTPException(status_code=400, detail="Password saat ini wajib diisi untuk melakukan perubahan password.")
        if not verify_password(profile_in.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Password saat ini salah.")
        
        # Hash new password dan simpan di hashed_password
        update_data["hashed_password"] = get_password_hash(profile_in.new_password)
        
    # Buang key dummy untuk password agar tidak mengganggu kolom SQL model
    update_data.pop("current_password", None)
    update_data.pop("new_password", None)
            
    updated_user = update_user(db, current_user.id, update_data)
    return updated_user
