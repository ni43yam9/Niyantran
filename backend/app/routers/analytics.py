from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.analytics import (
    AnalyticsOverview,
    DailyAnalytics,
    WeeklyAnalytics,
    MonthlyAnalytics,
    TimeAnalytics,
    GoalAnalytics,
    InsightsResponse,
)
from backend.app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/overview", response_model=AnalyticsOverview)
def get_analytics_overview(
    tz_offset: int = Query(0, description="Client timezone offset in minutes from UTC"),
    db: Session = Depends(get_db),
):
    """
    Returns high-level productivity score, completion rates across daily/weekly/monthly horizons,
    postponements, and active goals.
    """
    return analytics_service.get_analytics_overview(db, tz_offset_mins=tz_offset)

@router.get("/daily", response_model=DailyAnalytics)
def get_daily_analytics(
    target_date: Optional[date] = Query(None, alias="date", description="Target calendar date YYYY-MM-DD"),
    tz_offset: int = Query(0, description="Client timezone offset in minutes"),
    db: Session = Depends(get_db),
):
    """
    Returns daily execution analytics: tasks planned, completed, postponed, and focus duration.
    """
    return analytics_service.get_daily_analytics(db, target_date=target_date, tz_offset_mins=tz_offset)

@router.get("/weekly", response_model=WeeklyAnalytics)
def get_weekly_analytics(
    start_date: Optional[date] = Query(None, description="Monday starting date of week YYYY-MM-DD"),
    tz_offset: int = Query(0, description="Client timezone offset in minutes"),
    db: Session = Depends(get_db),
):
    """
    Returns 7-day day-by-day deliverable analytics, weekly productivity trend, and peak execution day.
    """
    return analytics_service.get_weekly_analytics(db, start_date=start_date, tz_offset_mins=tz_offset)

@router.get("/monthly", response_model=MonthlyAnalytics)
def get_monthly_analytics(
    year: Optional[int] = Query(None, description="Target year e.g. 2026"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Target month 1-12"),
    db: Session = Depends(get_db),
):
    """
    Returns monthly deliverable volume, month-to-month velocity delta, goal progress, and habit consistency.
    """
    return analytics_service.get_monthly_analytics(db, year=year, month=month)

@router.get("/time", response_model=TimeAnalytics)
def get_time_analytics(
    tz_offset: int = Query(0, description="Client timezone offset in minutes"),
    db: Session = Depends(get_db),
):
    """
    Returns time-of-day analytics: peak & least productive windows, average completion duration,
    and planned vs actual focus estimation variance.
    """
    return analytics_service.get_time_analytics(db, tz_offset_mins=tz_offset)

@router.get("/goals", response_model=GoalAnalytics)
def get_goal_analytics(
    db: Session = Depends(get_db),
):
    """
    Returns comprehensive goal analytics: short vs long-term distribution, linked task completion ratios,
    and milestone progress.
    """
    return analytics_service.get_goal_analytics(db)

@router.get("/insights", response_model=InsightsResponse)
def get_productivity_insights(
    tz_offset: int = Query(0, description="Client timezone offset in minutes"),
    db: Session = Depends(get_db),
):
    """
    Returns automated, data-backed productivity observations based on user behavioural patterns.
    """
    return analytics_service.get_productivity_insights(db, tz_offset_mins=tz_offset)
