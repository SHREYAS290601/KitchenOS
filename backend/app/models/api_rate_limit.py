from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class ApiRateLimit(Base):
    __tablename__ = "api_rate_limit"

    bucket_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
