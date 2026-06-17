"""Pydantic schemas for universities and programs."""

from pydantic import BaseModel, Field
from typing import Any


class ProgramSchema(BaseModel):
    name: str
    degree: str
    duration: str | None = None
    tuition: float | None = None
    semester_contribution: float | None = None
    currency: str = "EUR"
    intake: list[str] = []
    requirements: list[str] = []
    description: str | None = None
    language: str | None = None
    apply_url: str | None = None
    deadline: str | None = None


class UniversityCreate(BaseModel):
    name: str
    country: str
    city: str | None = None
    ranking: int | None = None
    website: str | None = None
    description: str | None = None
    tuition_min: float | None = None
    tuition_max: float | None = None
    currency: str = "EUR"
    programs: list[ProgramSchema] = []
    scholarships: list[str] = []
    deadlines: dict[str, str] = {}
    admission_requirements: list[str] = []
    living_cost: float | None = None
    logo_url: str | None = None
    short_name: str | None = None
    state: str | None = None
    german_ranking: int | None = None
    type: str | None = None
    intl_students_pct: float | None = None
    founded_year: int | None = None


class UniversityUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    city: str | None = None
    ranking: int | None = None
    website: str | None = None
    description: str | None = None
    tuition_min: float | None = None
    tuition_max: float | None = None
    currency: str | None = None
    programs: list[ProgramSchema] | None = None
    scholarships: list[str] | None = None
    deadlines: dict[str, str] | None = None
    admission_requirements: list[str] | None = None
    living_cost: float | None = None
    logo_url: str | None = None
    short_name: str | None = None
    state: str | None = None
    german_ranking: int | None = None
    type: str | None = None
    intl_students_pct: float | None = None
    founded_year: int | None = None


class UniversitySearchParams(BaseModel):
    q: str | None = None
    country: str | None = None
    degree: str | None = None
    course: str | None = None
    tuition_min: float | None = None
    tuition_max: float | None = None
    ranking_max: int | None = None
    intake: str | None = None
    page: int = 1
    limit: int = 12
    sort_by: str = "ranking"
    sort_order: str = "asc"


class UniversityResponse(BaseModel):
    id: str
    name: str
    country: str
    city: str = ""
    ranking: int | None = None
    website: str = ""
    description: str = ""
    tuition_min: float | None = None
    tuition_max: float | None = None
    currency: str = "EUR"
    programs: list[dict[str, Any]] = []
    scholarships: list[str] = []
    deadlines: dict[str, str] = {}
    admission_requirements: list[str] = []
    living_cost: float | None = None
    logo_url: str | None = None
    short_name: str | None = None
    state: str | None = None
    german_ranking: int | None = None
    type: str | None = None
    intl_students_pct: float | None = None
    founded_year: int | None = None
