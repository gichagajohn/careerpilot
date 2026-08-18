"""Dashboard summary schemas."""
from __future__ import annotations

from pydantic import BaseModel


class UpcomingDeadline(BaseModel):
    kind: str  # job / scholarship / application
    title: str
    organization: str | None = None
    due_date: str
    link_id: int


class DashboardSummary(BaseModel):
    total_opportunities: int
    new_opportunities: int
    high_match_opportunities: int
    applications_total: int
    applications_interviews: int
    applications_offers: int
    scholarships_total: int
    upcoming_deadlines: list[UpcomingDeadline]
