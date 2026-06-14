"""Pydantic schemas for user profiles."""

from pydantic import BaseModel, Field
from typing import Any


class TestScore(BaseModel):
    test_name: str
    score: str
    date: str | None = None


class Project(BaseModel):
    title: str
    description: str | None = None
    technologies: list[str] = []
    year: str | None = None


class Experience(BaseModel):
    company: str
    role: str
    duration: str | None = None
    description: str | None = None


class Preferences(BaseModel):
    preferred_countries: list[str] = []
    preferred_degrees: list[str] = []
    budget_max: float | None = None
    intake: str | None = None


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    address: str | None = None
    academic_level: str | None = None
    field_of_study: str | None = None
    gpa: str | None = None
    university: str | None = None
    graduation_year: str | None = None
    test_scores: list[TestScore] | None = None
    projects: list[Project] | None = None
    experience: list[Experience] | None = None
    preferences: Preferences | None = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    date_of_birth: str = ""
    nationality: str = ""
    address: str = ""
    academic_level: str = ""
    field_of_study: str = ""
    gpa: str = ""
    university: str = ""
    graduation_year: str = ""
    test_scores: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    experience: list[dict[str, Any]] = []
    preferences: dict[str, Any] = {}
    completion_percentage: int = 0
