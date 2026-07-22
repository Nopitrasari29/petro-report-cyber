# backend/app/api/v1/endpoints/settings.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import json
import os
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.api.v1.endpoints.auth import get_current_user
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


def load_settings() -> dict:
    """
    Membaca pengaturan organisasi dari database (tabel system_settings). Jika belum ada, buat default.
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

        merged_data = {**default_data, **(setting.value or {})}
        # Buang key lama peninggalan skema sebelumnya (mis. security_2fa) yang mungkin
        # masih tersimpan di DB lama, biar respons selalu bersih sesuai skema saat ini.
        cleaned = {k: v for k, v in merged_data.items() if k in default_data}
        return cleaned
    except Exception as e:
        print(f"[SETTINGS WARNING] Gagal memuat dari DB: {e}. Fallback ke file.")
        return load_settings_file()
    finally:
        db.close()


@router.get("/")
def get_settings(current_user = Depends(get_current_user)):
    """
    Mendapatkan pengaturan organisasi aktif saat ini. Wajib login.
    """
    try:
        return load_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat pengaturan: {str(e)}")


@router.put("/")
def update_settings(
    payload: Dict[str, Any],
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memperbarui pengaturan organisasi. Wajib login.
    Catatan: saat ini semua user yang login boleh mengubah ini (belum ada pembatasan role/admin
    khusus, karena sistem role belum diaktifkan di seluruh aplikasi). Kalau ke depannya cuma admin
    yang boleh ubah, tambahkan pengecekan current_user.role di sini.
    """
    try:
        current_settings = load_settings()

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

        return {"status": "success", "message": "Pengaturan organisasi berhasil diperbarui.", "settings": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui pengaturan: {str(e)}")