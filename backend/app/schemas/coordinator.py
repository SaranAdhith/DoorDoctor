"""Coordinator dashboard schemas."""

from pydantic import BaseModel


class CoordinatorSummary(BaseModel):
    patients: int
    caregivers: int
    today_visits: int
    active_alerts: int
    completed_today: int = 0
