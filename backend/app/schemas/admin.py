"""Admin dashboard schemas."""

from pydantic import BaseModel


class AdminSummary(BaseModel):
    patients: int
    nurses: int
    today_visits: int
    active_alerts: int
    completed_today: int = 0
