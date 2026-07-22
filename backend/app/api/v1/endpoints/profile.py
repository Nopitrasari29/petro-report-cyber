from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import UserResponse

router = APIRouter()

class ProfileUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    avatar_url: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    # Preferensi personal per-user (dulunya salah kesimpan di pengaturan global)
    language: Optional[str] = None
    appearance: Optional[str] = None
    notify_report_success: Optional[bool] = None
    notify_report_failed: Optional[bool] = None


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
    Memperbarui data profil user (Nama, Email, dan Foto Profil Base64) di database secara riil.
    """
    from app.crud.user import update_user, get_user_by_email
    from app.core.security import verify_password, get_password_hash
    
    # Validasi email jika diubah agar unik
    if profile_in.email and profile_in.email != current_user.email:
        existing = get_user_by_email(db, email=profile_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Alamat email sudah digunakan oleh pengguna lain."
            )
            
    update_data = profile_in.model_dump(exclude_unset=True)
    
    # Penanganan perubahan password jika dikirimkan oleh Frontend.
    # Kalau akun ini belum pernah nge-set password sendiri (password_set == False, artinya
    # daftar via Google dan passwordnya cuma string acak dari sistem yang user sendiri tidak
    # tahu), maka current_password TIDAK wajib diisi — ini bukan "ganti password", tapi
    # "nge-set password untuk pertama kali".
    if profile_in.new_password:
        if current_user.password_set:
            if not profile_in.current_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Password saat ini wajib diisi untuk melakukan perubahan password."
                )
            if not verify_password(profile_in.current_password, current_user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Password saat ini salah."
                )
        
        # Hash new password dan simpan di hashed_password
        update_data["hashed_password"] = get_password_hash(profile_in.new_password)
        update_data["password_set"] = True
        
    # Buang key dummy password agar tidak mengganggu kolom SQL model User
    update_data.pop("current_password", None)
    update_data.pop("new_password", None)
            
    updated_user = update_user(db, current_user.id, update_data)
    return updated_user