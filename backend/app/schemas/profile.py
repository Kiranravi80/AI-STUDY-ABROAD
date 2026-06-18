"""Pydantic schemas for user profiles with extended academic portfolio support."""

from pydantic import BaseModel
from typing import Any


class TestScore(BaseModel):
    test_name: str
    score: str
    date: str | None = None


class Project(BaseModel):
    title: str
    description: str | None = None
    technologies: list[str] = []
    github_link: str | None = None
    project_url: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class Experience(BaseModel):
    company: str
    role: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current_company: bool | None = False
    description: str | None = None


class SkillsSchema(BaseModel):
    technical_skills: list[str] = []
    programming_languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []
    databases: list[str] = []
    cloud_platforms: list[str] = []
    aiml_tools: list[str] = []
    soft_skills: list[str] = []


class Publication(BaseModel):
    title: str
    journal_conference: str | None = None
    date: str | None = None
    doi: str | None = None
    url: str | None = None
    authors: list[str] = []


class Certification(BaseModel):
    name: str
    provider: str | None = None
    issue_date: str | None = None
    credential_url: str | None = None
    credential_id: str | None = None


class SocialMediaSchema(BaseModel):
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_website: str | None = None
    kaggle_profile: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    twitter_x: str | None = None
    other_website: str | None = None


class Preferences(BaseModel):
    preferred_countries: list[str] = []
    preferred_degrees: list[str] = []
    intake: str | None = None
    preferred_language: str | None = None
    preferred_budget: float | None = None
    preferred_program_areas: list[str] = []


class AcademicRecord(BaseModel):
    level: str  # "10th", "12th", "bachelors", "masters", "phd", etc.
    school_name: str | None = None
    college_name: str | None = None
    university: str | None = None
    board: str | None = None
    degree: str | None = None
    specialization: str | None = None
    year_of_passing: str | None = None
    percentage: float | None = None
    cgpa: float | None = None
    research_area: str | None = None  # PhD specific


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    address: str | None = None
    gender: str | None = None
    current_country: str | None = None
    email: str | None = None
    profile_photo: str | None = None  # Base64 data url or string
    academic_level: str | None = None
    field_of_study: str | None = None
    gpa: str | None = None
    university: str | None = None
    graduation_year: str | None = None
    test_scores: list[TestScore] | None = None
    projects: list[Project] | None = None
    experience: list[Experience] | None = None
    skills: SkillsSchema | None = None
    publications: list[Publication] | None = None
    certifications: list[Certification] | None = None
    social_media: SocialMediaSchema | None = None
    preferences: Preferences | None = None
    academic_history: list[AcademicRecord] | None = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    date_of_birth: str = ""
    nationality: str = ""
    address: str = ""
    gender: str = ""
    current_country: str = ""
    email: str = ""
    profile_photo: str = ""
    academic_level: str = ""
    field_of_study: str = ""
    gpa: str = ""
    university: str = ""
    graduation_year: str = ""
    test_scores: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    experience: list[dict[str, Any]] = []
    skills: dict[str, Any] = {}
    publications: list[dict[str, Any]] = []
    certifications: list[dict[str, Any]] = []
    social_media: dict[str, Any] = {}
    preferences: dict[str, Any] = {}
    academic_history: list[AcademicRecord] = []
    completion_percentage: int = 0
