"""Pydantic schemas for shortlists, applications, documents, and more."""

from pydantic import BaseModel, Field
from typing import Any, Literal


ShortlistCategory = Literal["dream", "target", "safe"]
ApplicationStatus = Literal[
    "applied", "under_review", "offer_received", "rejected", "visa_stage"
]
SubscriptionPlan = Literal["free", "premium", "enterprise"]
RoadmapStatus = Literal["pending", "in_progress", "completed"]


class ShortlistCreate(BaseModel):
    university_id: str
    program_name: str
    notes: str | None = None


class ShortlistUpdate(BaseModel):
    notes: str | None = None


class ApplicationCreate(BaseModel):
    university_id: str
    program_name: str
    status: ApplicationStatus = "applied"
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    timeline: list[dict[str, str]] | None = None


class DocumentCreate(BaseModel):
    name: str
    file_type: str
    file_url: str
    category: str = "general"


class RoadmapStepUpdate(BaseModel):
    step_id: str
    status: RoadmapStatus
    notes: str | None = None


class AnalysisRequest(BaseModel):
    university_id: str | None = None
    program_name: str | None = None


class CounsellingNoteCreate(BaseModel):
    student_id: str
    title: str
    content: str
    is_private: bool = False


class MeetingCreate(BaseModel):
    student_id: str
    title: str
    scheduled_at: str
    duration_minutes: int = 30
    meeting_link: str | None = None
    notes: str | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None
    scheduled_at: str | None = None
    duration_minutes: int | None = None
    meeting_link: str | None = None
    notes: str | None = None
    status: str | None = None


class EmployeeCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    department: str = "Counselling"
    assigned_students: list[str] = []


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    department: str | None = None
    is_active: bool | None = None
    assigned_students: list[str] | None = None


class SubscriptionCreate(BaseModel):
    user_id: str
    plan: SubscriptionPlan = "premium"
    amount: float = 0
    currency: str = "USD"


class CostEstimateRequest(BaseModel):
    university_id: str
    program_name: str | None = None
    duration_years: int = 2
    include_living: bool = True
    include_insurance: bool = True
    include_visa: bool = True
    include_flight: bool = True


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    limit: int
    pages: int
