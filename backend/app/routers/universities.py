"""University search and management routes."""

import math
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from app.database import get_database
from app.schemas.university import UniversityCreate, UniversityUpdate, UniversityResponse
from app.schemas.common import PaginatedResponse
from app.middleware.auth import get_current_user, require_admin
from app.utils.helpers import serialize_doc, serialize_docs, paginate_params, utc_now

router = APIRouter(prefix="/universities", tags=["Universities"])


@router.get("", response_model=PaginatedResponse)
async def search_universities(
    q: str | None = None,
    country: str | None = None,
    degree: str | None = None,
    course: str | None = None,
    tuition_min: float | None = None,
    tuition_max: float | None = None,
    ranking_max: int | None = None,
    intake: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    sort_by: str = "ranking",
    sort_order: str = "asc",
    user: dict = Depends(get_current_user),
):
    """Search universities with filters, sorting, and pagination."""
    db = get_database()
    query: dict = {}

    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"country": {"$regex": q, "$options": "i"}},
            {"city": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if country:
        query["country"] = {"$regex": country, "$options": "i"}
    if degree:
        query["programs.degree"] = {"$regex": degree, "$options": "i"}
    if course:
        query["programs.name"] = {"$regex": course, "$options": "i"}
    if tuition_min is not None:
        query["tuition_min"] = {"$gte": tuition_min}
    if tuition_max is not None:
        query["tuition_max"] = {"$lte": tuition_max}
    if ranking_max is not None:
        query["ranking"] = {"$lte": ranking_max}
    if intake:
        query["programs.intake"] = intake

    skip, limit = paginate_params(page, limit)
    sort_direction = 1 if sort_order == "asc" else -1
    sort_field = sort_by if sort_by in ["ranking", "name", "tuition_min", "tuition_max"] else "ranking"

    total = await db.universities.count_documents(query)
    cursor = db.universities.find(query).sort(sort_field, sort_direction).skip(skip).limit(limit)
    universities = await cursor.to_list(length=limit)

    return PaginatedResponse(
        items=serialize_docs(universities),
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total > 0 else 0,
    )


@router.get("/{university_id}", response_model=UniversityResponse)
async def get_university(university_id: str, user: dict = Depends(get_current_user)):
    db = get_database()
    university = await db.universities.find_one({"_id": ObjectId(university_id)})
    if not university:
        raise HTTPException(status_code=404, detail="University not found")
    return UniversityResponse(**serialize_doc(university))


@router.post("", response_model=UniversityResponse, status_code=201)
async def create_university(data: UniversityCreate, user: dict = Depends(require_admin)):
    db = get_database()
    doc = data.model_dump()
    doc["created_at"] = utc_now().isoformat()
    doc["updated_at"] = utc_now().isoformat()
    result = await db.universities.insert_one(doc)
    university = await db.universities.find_one({"_id": result.inserted_id})
    return UniversityResponse(**serialize_doc(university))


@router.put("/{university_id}", response_model=UniversityResponse)
async def update_university(
    university_id: str,
    data: UniversityUpdate,
    user: dict = Depends(require_admin),
):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = utc_now().isoformat()
    result = await db.universities.update_one(
        {"_id": ObjectId(university_id)},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="University not found")

    university = await db.universities.find_one({"_id": ObjectId(university_id)})
    return UniversityResponse(**serialize_doc(university))


@router.delete("/{university_id}")
async def delete_university(university_id: str, user: dict = Depends(require_admin)):
    db = get_database()
    result = await db.universities.delete_one({"_id": ObjectId(university_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="University not found")
    return {"message": "University deleted"}
