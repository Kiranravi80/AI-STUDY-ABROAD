"""Profile management routes for students."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.database import get_database
from app.schemas.profile import ProfileUpdate, ProfileResponse
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, utc_now

router = APIRouter(prefix="/profiles", tags=["Profiles"])


async def calculate_completion(profile: dict, db) -> int:
    """Calculate profile completion percentage based on five milestones (20% each)."""
    academic_history = profile.get("academic_history", [])
    
    has_10 = any(
        e.get("level") == "10th" and 
        e.get("school_name") and 
        e.get("board") and 
        e.get("year_of_passing") and 
        e.get("percentage") is not None
        for e in academic_history
    )
    
    has_12 = any(
        e.get("level") == "12th" and 
        e.get("college_name") and 
        e.get("board") and 
        e.get("year_of_passing") and 
        e.get("percentage") is not None
        for e in academic_history
    )
    
    has_bachelors = any(
        e.get("level") == "bachelors" and 
        e.get("degree") and 
        e.get("university") and 
        e.get("year_of_passing") and 
        (e.get("cgpa") is not None or e.get("percentage") is not None)
        for e in academic_history
    )
    
    prefs = profile.get("preferences", {})
    has_preferences = bool(
        profile.get("nationality") and
        prefs.get("preferred_countries") and 
        prefs.get("preferred_degrees") and 
        prefs.get("intake")
    )
    
    docs_count = await db.documents.count_documents({"user_id": profile["user_id"]})
    has_documents = docs_count > 0
    
    score = 0
    if has_10: score += 20
    if has_12: score += 20
    if has_bachelors: score += 20
    if has_preferences: score += 20
    if has_documents: score += 20
    
    return score


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: dict = Depends(require_student)):
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]})

    if not profile:
        profile = {
            "user_id": user["id"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "completion_percentage": 10,
        }
        result = await db.profiles.insert_one(profile)
        profile["_id"] = result.inserted_id

    serialized = serialize_doc(profile)
    serialized["completion_percentage"] = await calculate_completion(profile, db)
    return ProfileResponse(**serialized)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(data: ProfileUpdate, user: dict = Depends(require_student)):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Map academic history records to legacy flat fields for AI compatibility
    if "academic_history" in update_data and update_data["academic_history"]:
        history = update_data["academic_history"]
        rank_map = {
            "phd": 9,
            "mba": 8,
            "mtech": 7,
            "msc": 6,
            "masters": 5,
            "pg_diploma": 4,
            "bachelors": 3,
            "12th": 2,
            "10th": 1
        }
        
        highest_record = None
        highest_rank = -1
        for record in history:
            lvl = record.get("level", "").lower()
            rank = rank_map.get(lvl, 0)
            if rank > highest_rank:
                highest_rank = rank
                highest_record = record
                
        if highest_record:
            update_data["academic_level"] = highest_record.get("level", "")
            update_data["field_of_study"] = highest_record.get("specialization") or highest_record.get("degree") or ""
            update_data["university"] = highest_record.get("university") or highest_record.get("college_name") or highest_record.get("school_name") or ""
            update_data["graduation_year"] = highest_record.get("year_of_passing") or ""
            
            if highest_record.get("cgpa") is not None:
                update_data["gpa"] = str(highest_record["cgpa"])
            elif highest_record.get("percentage") is not None:
                update_data["gpa"] = f"{highest_record['percentage']}%"
            else:
                update_data["gpa"] = ""

    update_data["updated_at"] = utc_now().isoformat()

    profile = await db.profiles.find_one({"user_id": user["id"]})
    if not profile:
        update_data["user_id"] = user["id"]
        update_data["created_at"] = utc_now().isoformat()
        result = await db.profiles.insert_one(update_data)
        profile = await db.profiles.find_one({"_id": result.inserted_id})
    else:
        await db.profiles.update_one({"user_id": user["id"]}, {"$set": update_data})
        profile = await db.profiles.find_one({"user_id": user["id"]})

    # Sync name to user document
    if data.first_name or data.last_name:
        user_update = {}
        if data.first_name:
            user_update["first_name"] = data.first_name
        if data.last_name:
            user_update["last_name"] = data.last_name
        await db.users.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": user_update},
        )

    completion = await calculate_completion(profile, db)
    await db.profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"completion_percentage": completion}},
    )
    profile["completion_percentage"] = completion

    serialized = serialize_doc(profile)
    return ProfileResponse(**serialized)


@router.get("/student/{student_id}", response_model=ProfileResponse)
async def get_student_profile(student_id: str, user: dict = Depends(require_student)):
    """Employees/admins use a different route - this is for student self-view."""
    raise HTTPException(status_code=404, detail="Use employee/admin endpoints")
