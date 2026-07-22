from sqlalchemy.orm import Session
import secrets
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash


def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    
    # Auto-generate unique username dari email
    base_username = user.email.split("@")[0]
    username = base_username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1
        
    db_user = User(
        username=username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name or username.title(),
        role="Analyst",
        department="IT Security SOC"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: dict) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    for key, value in user_update.items():
        if value is not None:
            setattr(db_user, key, value)
            
    db.commit()
    db.refresh(db_user)
    return db_user

def create_user_oauth(db: Session, email: str, username: str, full_name: str | None = None, avatar_url: str | None = None) -> User:
    """
    Mendaftarkan user baru yang login melalui Google OAuth secara otomatis.
    """
    # 1. Cek & selesaikan tabrakan (collision) username
    base_username = username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1
        
    # 2. Bikin password acak yang kuat (tidak dipakai login manual)
    random_password = secrets.token_urlsafe(32)
    hashed_password = get_password_hash(random_password)
    
    db_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name or username.title(),
        avatar_url=avatar_url,
        is_verified=True,  # Pengguna Google sudah diverifikasi oleh Google
        role="Analyst",
        department="IT Security SOC",
        password_set=False  # Belum pernah nge-set password sendiri, cuma password acak dari sistem
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user