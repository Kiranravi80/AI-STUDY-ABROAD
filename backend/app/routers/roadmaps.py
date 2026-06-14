"""Study abroad roadmap routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_database
from app.schemas.common import RoadmapStepUpdate
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, utc_now
from app.ai.roadmap_engine import generate_personalized_roadmap

router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])

DEFAULT_STEPS = [
    {"id": "research", "title": "Research Universities", "status": "pending", "order": 1, "month": "Month 1", "description": "Select colleges and compile requirements."},
    {"id": "ielts", "title": "IELTS Preparation", "status": "pending", "order": 2, "month": "Month 1-2", "description": "Register and study for exam."},
    {"id": "gre", "title": "GRE/GMAT", "status": "pending", "order": 3, "month": "Month 2", "description": "Attempt GRE if required."},
    {"id": "aps", "title": "APS Certificate", "status": "pending", "order": 4, "month": "Month 3", "description": "Get degree transcripts verified."},
    {"id": "sop", "title": "Statement of Purpose", "status": "pending", "order": 5, "month": "Month 3-4", "description": "Write and polish personal statement."},
    {"id": "lor", "title": "Letters of Recommendation", "status": "pending", "order": 6, "month": "Month 4", "description": "Gather letters from references."},
    {"id": "applications", "title": "Submit Applications", "status": "pending", "order": 7, "month": "Month 4-5", "description": "Submit application packages."},
    {"id": "visa", "title": "Visa Application", "status": "pending", "order": 8, "month": "Month 5-6", "description": "Schedule visa interview and verify finances."},
    {"id": "accommodation", "title": "Find Accommodation", "status": "pending", "order": 9, "month": "Month 6", "description": "Apply for student dormitories."},
    {"id": "flight", "title": "Book Flight", "status": "pending", "order": 10, "month": "Month 6", "description": "Secure airline tickets."},
]


class RoadmapGenerateRequest(BaseModel):
    target_country: str | None = None
    target_intake: str | None = None
    target_course: str | None = None


def calculate_progress(steps: list) -> int:
    completed = sum(1 for s in steps if s.get("status") == "completed")
    return int((completed / len(steps)) * 100) if steps else 0


@router.get("/me")
async def get_my_roadmap(user: dict = Depends(require_student)):
    """Retrieve user's current roadmap. Seeds default roadmap if none exists."""
    db = get_database()
    roadmap = await db.roadmaps.find_one({"user_id": user["id"]})

    if not roadmap:
        roadmap = {
            "user_id": user["id"],
            "steps": DEFAULT_STEPS.copy(),
            "progress": 0,
            "overall_summary": "Initial standard study abroad timeline.",
            "created_at": utc_now().isoformat(),
        }
        result = await db.roadmaps.insert_one(roadmap)
        roadmap["_id"] = result.inserted_id

    serialized = serialize_doc(roadmap)
    serialized["progress"] = calculate_progress(roadmap.get("steps", []))
    return serialized


@router.post("/generate")
async def generate_my_roadmap(
    data: RoadmapGenerateRequest,
    user: dict = Depends(require_student),
):
    """Generate and overwrite student's roadmap with custom AI month-by-month tasks."""
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]})

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Profile details not found. Complete your profile first."
        )

    # Resolve roadmap variables from request payload or profile preferences
    country = data.target_country or (
        profile.get("preferences", {}).get("preferred_countries", ["Germany"])[0]
        if profile.get("preferences", {}).get("preferred_countries") else "Germany"
    )
    intake = data.target_intake or profile.get("preferences", {}).get("intake", "Winter intake") or "Winter intake"
    course = data.target_course or profile.get("field_of_study", "Computer Science") or "Computer Science"

    ai_roadmap = await generate_personalized_roadmap(profile, country, intake, course)

    steps = []
    order = 1
    for m in ai_roadmap.get("timeline", []):
        month_name = m.get("month", "")
        focus = m.get("focus", "")
        for task in m.get("tasks", []):
            steps.append({
                "id": task.get("id") or f"task_{order}",
                "title": task.get("title", ""),
                "description": task.get("description", ""),
                "status": "pending",
                "order": order,
                "month": month_name,
                "focus": focus,
                "required_by": task.get("required_by", ""),
            })
            order += 1

    roadmap_doc = {
        "user_id": user["id"],
        "target_country": country,
        "target_intake": intake,
        "target_course": course,
        "steps": steps,
        "progress": 0,
        "overall_summary": ai_roadmap.get("overall_summary", ""),
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }

    # Delete existing roadmap and write the new one
    await db.roadmaps.delete_many({"user_id": user["id"]})
    result = await db.roadmaps.insert_one(roadmap_doc)
    roadmap_doc["_id"] = result.inserted_id

    return serialize_doc(roadmap_doc)


@router.put("/me/step")
async def update_roadmap_step(
    data: RoadmapStepUpdate,
    user: dict = Depends(require_student),
):
    """Update progress status of a specific step in the roadmap."""
    db = get_database()
    roadmap = await db.roadmaps.find_one({"user_id": user["id"]})

    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    steps = roadmap.get("steps", [])
    updated = False
    for step in steps:
        if step["id"] == data.step_id:
            step["status"] = data.status
            if data.notes:
                step["notes"] = data.notes
            step["updated_at"] = utc_now().isoformat()
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Step not found")

    progress = calculate_progress(steps)
    await db.roadmaps.update_one(
        {"user_id": user["id"]},
        {
            "$set": {
                "steps": steps,
                "progress": progress,
                "updated_at": utc_now().isoformat(),
            }
        },
    )

    return {"steps": steps, "progress": progress}


@router.get("/student/{student_id}")
async def get_student_roadmap(student_id: str, user: dict = Depends(require_student)):
    raise HTTPException(status_code=403, detail="Use employee endpoint")
