"""Application tracking routes."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.database import get_database
from app.schemas.common import ApplicationCreate, ApplicationUpdate
from app.middleware.auth import require_student, require_employee_or_admin
from app.utils.helpers import serialize_doc, utc_now

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.get("")
async def get_applications(user: dict = Depends(require_student)):
    db = get_database()
    apps = await db.applications.find({"user_id": user["id"]}).sort("created_at", -1).to_list(100)

    enriched = []
    for app in apps:
        serialized = serialize_doc(app)
        uni = await db.universities.find_one({"_id": ObjectId(app["university_id"])})
        if uni:
            serialized["university"] = serialize_doc(uni)
        enriched.append(serialized)

    # Group by status
    statuses = ["applied", "under_review", "offer_received", "rejected", "visa_stage"]
    grouped = {s: [a for a in enriched if a.get("status") == s] for s in statuses}

    return {"items": enriched, "grouped": grouped, "total": len(enriched)}


@router.post("", status_code=201)
async def create_application(data: ApplicationCreate, user: dict = Depends(require_student)):
    db = get_database()
    uni = await db.universities.find_one({"_id": ObjectId(data.university_id)})
    if not uni:
        raise HTTPException(status_code=404, detail="University not found")

    doc = {
        "user_id": user["id"],
        "university_id": data.university_id,
        "program_name": data.program_name,
        "status": data.status,
        "notes": data.notes or "",
        "timeline": [{
            "status": data.status,
            "date": utc_now().isoformat(),
            "note": "Application created",
        }],
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }
    result = await db.applications.insert_one(doc)
    doc["_id"] = result.inserted_id
    serialized = serialize_doc(doc)
    serialized["university"] = serialize_doc(uni)
    return serialized


@router.put("/{application_id}")
async def update_application(
    application_id: str,
    data: ApplicationUpdate,
    user: dict = Depends(require_student),
):
    db = get_database()
    app = await db.applications.find_one({
        "_id": ObjectId(application_id),
        "user_id": user["id"],
    })
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}

    # Append to timeline if status changed
    if data.status and data.status != app.get("status"):
        timeline = app.get("timeline", [])
        timeline.append({
            "status": data.status,
            "date": utc_now().isoformat(),
            "note": data.notes or f"Status changed to {data.status}",
        })
        update_data["timeline"] = timeline

    update_data["updated_at"] = utc_now().isoformat()
    await db.applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": update_data},
    )

    updated = await db.applications.find_one({"_id": ObjectId(application_id)})
    return serialize_doc(updated)


@router.delete("/{application_id}")
async def delete_application(application_id: str, user: dict = Depends(require_student)):
    db = get_database()
    result = await db.applications.delete_one({
        "_id": ObjectId(application_id),
        "user_id": user["id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"message": "Application deleted"}


@router.get("/student/{student_id}")
async def get_student_applications(
    student_id: str,
    user: dict = Depends(require_employee_or_admin),
):
    """Employee/Admin view of student applications."""
    db = get_database()
    apps = await db.applications.find({"user_id": student_id}).to_list(100)
    enriched = []
    for app in apps:
        serialized = serialize_doc(app)
        uni = await db.universities.find_one({"_id": ObjectId(app["university_id"])})
        if uni:
            serialized["university"] = serialize_doc(uni)
        enriched.append(serialized)
    return {"items": enriched, "total": len(enriched)}
