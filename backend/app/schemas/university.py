"""Pydantic schemas for universities and programs."""

from pydantic import BaseModel, Field
from typing import Any


class CampusSchema(BaseModel):
    name: str
    city: str
    tuition_fee: float
    apply_url: str | None = None
    last_updated: str | None = None


class EctsRequirementSchema(BaseModel):
    subject: str
    ects: int


class AcademicRequirementsSchema(BaseModel):
    eligible_degrees: list[str] = []
    ects_requirements: list[EctsRequirementSchema] = []
    required_subjects: list[str] = []


class LanguageRequirementsSchema(BaseModel):
    ielts: float | None = None
    toefl: int | None = None
    pte: int | None = None
    german: str | None = None
    minimum_score_text: str | None = None


class IndianStudentRequirementsSchema(BaseModel):
    aps_required: bool | None = None
    uni_assist: bool | None = None
    vpd_required: bool | None = None


class ProgramRequirementsSchema(BaseModel):
    academic: AcademicRequirementsSchema | None = None
    language: LanguageRequirementsSchema | None = None
    documents_required: list[str] = []
    indian_students: IndianStudentRequirementsSchema | None = None
    requirement_source_url: str | None = None
    deadline_source_url: str | None = None
    program_source_url: str | None = None
    last_updated: str | None = None


class ProgramSchema(BaseModel):
    name: str
    degree: str
    duration: str | None = None
    campuses: list[CampusSchema] = []
    semester_contribution: float | None = None
    currency: str = "EUR"
    intake: list[str] = []
    requirements: list[str] = []
    requirements_details: ProgramRequirementsSchema | None = None
    description: str | None = None
    language: str | None = None
    deadlines: dict[str, str] = {}
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
