"""Profile management routes for students."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.database import get_database
from app.schemas.profile import ProfileUpdate, ProfileResponse
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, utc_now

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def calculate_completion(profile: dict) -> int:
    """Calculate profile completion percentage based on filled fields."""
    fields = [
        "first_name", "last_name", "phone", "nationality",
        "academic_level", "field_of_study", "gpa", "university",
    ]
    filled = sum(1 for f in fields if profile.get(f))
    bonus = 0
    if profile.get("test_scores"):
        bonus += 1
    if profile.get("projects"):
        bonus += 1
    if profile.get("experience"):
        bonus += 1
    if profile.get("preferences", {}).get("preferred_countries"):
        bonus += 1
    total = len(fields) + 4
    return min(int(((filled + bonus) / total) * 100), 100)


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
    serialized["completion_percentage"] = calculate_completion(profile)
    return ProfileResponse(**serialized)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(data: ProfileUpdate, user: dict = Depends(require_student)):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

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

    completion = calculate_completion(profile)
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
