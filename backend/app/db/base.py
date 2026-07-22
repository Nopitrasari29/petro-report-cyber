from app.db.session import Base

# Impor model agar terdeteksi oleh Alembic untuk autogenerate
from app.models.user import User
from app.models.report import Report
from app.models.system_setting import SystemSetting