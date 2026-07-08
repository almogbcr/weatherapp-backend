from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class DailyIpCount(Base):
    __tablename__ = "daily_ip_counts"

    day: Mapped[Date] = mapped_column(Date, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DailyDeviceCount(Base):
    __tablename__ = "daily_device_counts"

    day: Mapped[Date] = mapped_column(Date, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DailyPairCount(Base):
    __tablename__ = "daily_pair_counts"

    day: Mapped[Date] = mapped_column(Date, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
