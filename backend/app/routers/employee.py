"""Employee portal routes."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from pydantic import BaseModel

from app.database import get_database
from app.schemas.common import CounsellingNoteCreate, MeetingCreate, MeetingUpdate
from app.middleware.auth import require_employee
from app.utils.helpers import serialize_doc, utc_now

router = APIRouter(prefix="/employee", tags=["Employee"])


class AddRoadmapStepRequest(BaseModel):
    title: str
    description: str
    month: str
    required_by: str | None = None



async def get_assigned_student_ids(db, employee_user_id: str) -> list[str]:
    employee = await db.employees.find_one({"user_id": employee_user_id})
    return employee.get("assigned_students", []) if employee else []


async def ensure_student_is_assigned(db, student_id: str, employee_user_id: str) -> None:
    if student_id not in await get_assigned_student_ids(db, employee_user_id):
        raise HTTPException(status_code=403, detail="Student not assigned to you")


@router.get("/dashboard")
async def employee_dashboard(user: dict = Depends(require_employee)):
    db = get_database()
    employee = await db.employees.find_one({"user_id": user["id"]})
    assigned_ids = employee.get("assigned_students", []) if employee else []

    students = []
    for sid in assigned_ids:
        student = await db.users.find_one({"_id": ObjectId(sid), "role": "student"})
        if student:
            profile = await db.profiles.find_one({"user_id": sid})
            apps_count = await db.applications.count_documents({"user_id": sid})
            serialized = serialize_doc(student)
            serialized["profile"] = serialize_doc(profile) if profile else None
            serialized["applications_count"] = apps_count
            students.append(serialized)

    meetings_count = await db.meetings.count_documents({"employee_id": user["id"]})
    notes_count = await db.counselling_notes.count_documents({"employee_id": user["id"]})

    return {
        "assigned_students": len(students),
        "students": students,
        "meetings_count": meetings_count,
        "notes_count": notes_count,
        "department": employee.get("department", "") if employee else "",
    }


@router.get("/students")
async def get_assigned_students(user: dict = Depends(require_employee)):
    db = get_database()
    assigned_ids = await get_assigned_student_ids(db, user["id"])

    students = []
    for sid in assigned_ids:
        student = await db.users.find_one({"_id": ObjectId(sid)})
        if student:
            profile = await db.profiles.find_one({"user_id": sid})
            serialized = serialize_doc(student)
            serialized["profile"] = serialize_doc(profile)
            students.append(serialized)

    return {"items": students, "total": len(students)}


@router.get("/students/{student_id}")
async def get_student_detail(student_id: str, user: dict = Depends(require_employee)):
    db = get_database()
    await ensure_student_is_assigned(db, student_id, user["id"])

    student = await db.users.find_one({"_id": ObjectId(student_id)})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    profile = await db.profiles.find_one({"user_id": student_id})
    applications = await db.applications.find({"user_id": student_id}).to_list(50)
    documents = await db.documents.find({"user_id": student_id}).to_list(50)
    roadmap = await db.roadmaps.find_one({"user_id": student_id})
    notes = await db.counselling_notes.find({
        "student_id": student_id,
        "employee_id": user["id"],
    }).to_list(50)

    return {
        "student": serialize_doc(student),
        "profile": serialize_doc(profile),
        "applications": [serialize_doc(a) for a in applications],
        "documents": [{**serialize_doc(d), "file_data": None} for d in documents],
        "roadmap": serialize_doc(roadmap),
        "notes": [serialize_doc(n) for n in notes],
    }


@router.post("/notes", status_code=201)
async def create_note(data: CounsellingNoteCreate, user: dict = Depends(require_employee)):
    db = get_database()
    await ensure_student_is_assigned(db, data.student_id, user["id"])

    doc = {
        "employee_id": user["id"],
        "student_id": data.student_id,
        "title": data.title,
        "content": data.content,
        "is_private": data.is_private,
        "created_at": utc_now().isoformat(),
    }
    result = await db.counselling_notes.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/notes")
async def get_notes(user: dict = Depends(require_employee)):
    db = get_database()
    notes = await db.counselling_notes.find({"employee_id": user["id"]}).sort("created_at", -1).to_list(100)
    return {"items": [serialize_doc(n) for n in notes], "total": len(notes)}


@router.post("/meetings", status_code=201)
async def create_meeting(data: MeetingCreate, user: dict = Depends(require_employee)):
    db = get_database()
    await ensure_student_is_assigned(db, data.student_id, user["id"])

    doc = {
        "employee_id": user["id"],
        "student_id": data.student_id,
        "title": data.title,
        "scheduled_at": data.scheduled_at,
        "duration_minutes": data.duration_minutes,
        "meeting_link": data.meeting_link,
        "notes": data.notes,
        "status": "scheduled",
        "created_at": utc_now().isoformat(),
    }
    result = await db.meetings.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/meetings")
async def get_meetings(user: dict = Depends(require_employee)):
    db = get_database()
    meetings = await db.meetings.find({"employee_id": user["id"]}).sort("scheduled_at", 1).to_list(100)

    enriched = []
    for m in meetings:
        serialized = serialize_doc(m)
        student = await db.users.find_one({"_id": ObjectId(m["student_id"])})
        if student:
            serialized["student_name"] = f"{student.get('first_name', '')} {student.get('last_name', '')}"
        enriched.append(serialized)

    return {"items": enriched, "total": len(enriched)}


@router.put("/meetings/{meeting_id}")
async def update_meeting(
    meeting_id: str,
    data: MeetingUpdate,
    user: dict = Depends(require_employee),
):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    result = await db.meetings.update_one(
        {"_id": ObjectId(meeting_id), "employee_id": user["id"]},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
    return serialize_doc(meeting)


@router.post("/students/{student_id}/analysis")
async def generate_student_analysis_ai(
    student_id: str,
    user: dict = Depends(require_employee),
):
    """Counselors execute AI Profile Evaluation audits on behalf of students."""
    db = get_database()
    await ensure_student_is_assigned(db, student_id, user["id"])

    profile = await db.profiles.find_one({"user_id": student_id})
    if not profile:
        raise HTTPException(status_code=400, detail="Student profile not found")

    from app.ai.profile_engine import analyze_profile
    profile_eval = await analyze_profile(profile)

    report = {
        "user_id": student_id,
        **profile_eval,
        "is_premium": False,
        "created_at": utc_now().isoformat(),
        "generated_by": "employee",
    }
    result = await db.analysis_reports.insert_one(report)
    report["id"] = str(result.inserted_id)

    return serialize_doc(report)


@router.post("/students/{student_id}/roadmap/step")
async def add_student_roadmap_step(
    student_id: str,
    data: AddRoadmapStepRequest,
    user: dict = Depends(require_employee),
):
    """Counselors add personalized milestones to student roadmaps."""
    db = get_database()
    await ensure_student_is_assigned(db, student_id, user["id"])

    roadmap = await db.roadmaps.find_one({"user_id": student_id})
    if not roadmap:
        raise HTTPException(status_code=400, detail="Student has no roadmap seeded yet")

    steps = roadmap.get("steps", [])
    new_step = {
        "id": f"custom_{len(steps) + 1}",
        "title": data.title,
        "description": data.description,
        "status": "pending",
        "order": len(steps) + 1,
        "month": data.month,
        "required_by": data.required_by or "TBD",
        "created_at": utc_now().isoformat(),
    }
    steps.append(new_step)

    # Re-calculate overall roadmap progress
    from app.routers.roadmaps import calculate_progress
    progress = calculate_progress(steps)

    await db.roadmaps.update_one(
        {"user_id": student_id},
        {
            "$set": {
                "steps": steps,
                "progress": progress,
                "updated_at": utc_now().isoformat(),
            }
        },
    )

    return {"message": "Custom milestone added successfully", "step": new_step}

