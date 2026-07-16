from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db.session import Base

class DataSource(Base):
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False) # e.g. Firewall Logs
    source_type = Column(String, nullable=False)  # e.g. Log Management, Email Gateway
    status = Column(String, default="Connected")  # Connected, Disconnected, Syncing, Failed
    records_count = Column(Integer, default=0)
    data_quality = Column(Integer, default=95)  # Persentase (e.g. 98%)
    
    last_sync = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
