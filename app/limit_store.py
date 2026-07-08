from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DailyDeviceCount, DailyIpCount, DailyPairCount


@dataclass(frozen=True)
class RateInfo:
    day: str
    limit: int
    ip_count: int
    device_count: int
    pair_count: int
    blocked: bool

    def max_count(self) -> int:
        return max(self.ip_count, self.device_count, self.pair_count)

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "limit": self.limit,
            "ip_count": self.ip_count,
            "device_count": self.device_count,
            "pair_count": self.pair_count,
            "blocked": self.blocked,
        }


def _get_for_update(session: Session, stmt):
    return session.execute(stmt.with_for_update()).scalar_one_or_none()


def check_and_increment(session: Session, ip: str, device_id: str, limit: int) -> RateInfo:
    day = date.today()

    ip_row = _get_for_update(
        session, select(DailyIpCount).where(DailyIpCount.day == day, DailyIpCount.ip == ip)
    )
    device_row = _get_for_update(
        session,
        select(DailyDeviceCount).where(
            DailyDeviceCount.day == day, DailyDeviceCount.device_id == device_id
        ),
    )
    pair_row = _get_for_update(
        session,
        select(DailyPairCount).where(
            DailyPairCount.day == day,
            DailyPairCount.ip == ip,
            DailyPairCount.device_id == device_id,
        ),
    )

    ip_count = ip_row.count if ip_row else 0
    device_count = device_row.count if device_row else 0
    pair_count = pair_row.count if pair_row else 0

    if max(ip_count, device_count, pair_count) >= limit:
        return RateInfo(
            day=day.isoformat(),
            limit=limit,
            ip_count=ip_count,
            device_count=device_count,
            pair_count=pair_count,
            blocked=True,
        )

    if ip_row:
        ip_row.count += 1
    else:
        session.add(DailyIpCount(day=day, ip=ip, count=1))

    if device_row:
        device_row.count += 1
    else:
        session.add(DailyDeviceCount(day=day, device_id=device_id, count=1))

    if pair_row:
        pair_row.count += 1
    else:
        session.add(DailyPairCount(day=day, ip=ip, device_id=device_id, count=1))

    return RateInfo(
        day=day.isoformat(),
        limit=limit,
        ip_count=ip_count + 1,
        device_count=device_count + 1,
        pair_count=pair_count + 1,
        blocked=False,
    )
