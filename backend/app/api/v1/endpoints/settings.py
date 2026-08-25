# backend/app/api/v1/endpoints/settings.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import json
import os
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
from app.models.system_setting import SystemSetting

router = APIRouter()

# Tentukan path file settings lokal
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "core", "settings.json")


class SettingsSchema(BaseModel):
    """
    Pengaturan level ORGANISASI (bukan per-user) — berlaku untuk 1 deployment/instance web ini.
    Field yang dulu ada di sini tapi cuma dekorasi tanpa fungsi nyata (security_2fa, storage_*,
    chart_*, export_*, ai_model/ai_temperature, dst.) sudah dibuang. Preferensi personal seperti
    bahasa, notifikasi, dan tampilan sekarang disimpan per-user di /settings/profile, bukan di sini.
    """
    organization_name: str = "PT Petrokimia Gresik"
    primary_color: str = "#008B45"
    secondary_color: str = "#2DAA7D"
    description: str = "AI-Powered Security Report Generator for SOC Team"


def load_settings_file() -> dict:
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        default_data = SettingsSchema().model_dump()
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_data, f, indent=2)
        return default_data
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)


def load_settings(db: Session | None = None) -> dict:
    """
    Membaca pengaturan organisasi dari database (tabel system_settings). Jika belum ada, buat default.
    RCA-B05: Menerima sesi DB opsional agar memanfaatkan connection pool yang sudah ada.
    """
    close_local = False
    if db is None:
        db = SessionLocal()
        close_local = True

    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == "global").first()
        default_data = SettingsSchema().model_dump()
        if not setting:
            setting = SystemSetting(key="global", value=default_data)
            db.add(setting)
            db.commit()
            return default_data

        merged_data = {**default_data, **(setting.value or {})}
        cleaned = {k: v for k, v in merged_data.items() if k in default_data}
        return cleaned
    except Exception as e:
        logger.warning(f"Gagal memuat dari DB: {e}. Fallback ke file.")
        return load_settings_file()
    finally:
        if close_local:
            db.close()


@router.get("/")
def get_settings(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mendapatkan pengaturan organisasi aktif saat ini. Wajib login.
    """
    try:
        return load_settings(db=db)
    except Exception as e:
        logger.error(f"Gagal memuat pengaturan: {e}")
        raise HTTPException(status_code=500, detail="Gagal memuat pengaturan. Silakan coba lagi atau hubungi admin.")


@router.put("/")
def update_settings(
    payload: Dict[str, Any],
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memperbarui pengaturan organisasi.
    RCA-A04: Membatasi izin ubah hanya untuk role 'Admin' atau 'Superadmin'.
    """
    user_role = (current_user.role or "").strip().lower()
    if user_role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=403,
            detail="Hanya administrator yang memiliki izin untuk mengubah pengaturan organisasi."
        )

    try:
        current_settings = load_settings(db=db)

        for key, value in payload.items():
            current_settings[key] = value

        validated_settings = SettingsSchema(**current_settings)
        data = validated_settings.model_dump()

        setting = db.query(SystemSetting).filter(SystemSetting.key == "global").first()
        if not setting:
            setting = SystemSetting(key="global", value=data)
            db.add(setting)
        else:
            setting.value = data
        db.commit()

        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

        # Catat ke audit log
        try:
            from app.crud.audit_log import log_action
            log_action(
                db, user_id=current_user.id, action="update_settings",
                resource_type="settings", resource_id=None,
                detail=f"Pengaturan organisasi diperbarui: org_name='{data.get('organization_name')}'",
            )
        except Exception:
            pass

        return {"status": "success", "message": "Pengaturan organisasi berhasil diperbarui.", "settings": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gagal memperbarui pengaturan: {e}")
        raise HTTPException(status_code=500, detail="Gagal memperbarui pengaturan. Periksa kembali data yang dikirim atau hubungi admin.")