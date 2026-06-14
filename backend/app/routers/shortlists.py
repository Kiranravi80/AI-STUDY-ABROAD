"""Shortlist management routes."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from pydantic import BaseModel

from app.database import get_database
from app.schemas.common import ShortlistCreate, ShortlistUpdate
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, serialize_docs, utc_now

router = APIRouter(prefix="/shortlists", tags=["Shortlists"])


class CompareAIRequest(BaseModel):
    shortlist_ids: list[str]



@router.get("")
async def get_shortlists(user: dict = Depends(require_student)):
    db = get_database()
    shortlists = await db.shortlists.find({"user_id": user["id"]}).to_list(length=200)

    # Enrich with university data
    enriched = []
    for item in shortlists:
        serialized = serialize_doc(item)
        uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
        if uni:
            serialized["university"] = serialize_doc(uni)
        enriched.append(serialized)

    # Group by category
    grouped = {"dream": [], "target": [], "safe": []}
    for item in enriched:
        cat = item.get("category", "target")
        grouped.get(cat, grouped["target"]).append(item)

    return {"items": enriched, "grouped": grouped, "total": len(enriched)}


@router.post("", status_code=201)
async def add_to_shortlist(data: ShortlistCreate, user: dict = Depends(require_student)):
    db = get_database()

    # Verify university exists
    uni = await db.universities.find_one({"_id": ObjectId(data.university_id)})
    if not uni:
        raise HTTPException(status_code=404, detail="University not found")

    existing = await db.shortlists.find_one({
        "user_id": user["id"],
        "university_id": data.university_id,
    })
    if existing:
        raise HTTPException(status_code=400, detail="University already in shortlist")

    doc = {
        "user_id": user["id"],
        "university_id": data.university_id,
        "category": data.category,
        "notes": data.notes or "",
        "created_at": utc_now().isoformat(),
    }
    result = await db.shortlists.insert_one(doc)
    doc["_id"] = result.inserted_id
    serialized = serialize_doc(doc)
    serialized["university"] = serialize_doc(uni)
    return serialized


@router.put("/{shortlist_id}")
async def update_shortlist(
    shortlist_id: str,
    data: ShortlistUpdate,
    user: dict = Depends(require_student),
):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.shortlists.update_one(
        {"_id": ObjectId(shortlist_id), "user_id": user["id"]},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Shortlist item not found")

    item = await db.shortlists.find_one({"_id": ObjectId(shortlist_id)})
    return serialize_doc(item)


@router.delete("/{shortlist_id}")
async def remove_from_shortlist(shortlist_id: str, user: dict = Depends(require_student)):
    db = get_database()
    result = await db.shortlists.delete_one({
        "_id": ObjectId(shortlist_id),
        "user_id": user["id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Shortlist item not found")
    return {"message": "Removed from shortlist"}


@router.get("/compare")
async def compare_shortlists(
    ids: str,
    user: dict = Depends(require_student),
):
    """Compare multiple shortlisted universities. Pass comma-separated IDs."""
    db = get_database()
    shortlist_ids = [s.strip() for s in ids.split(",") if s.strip()]

    items = []
    for sid in shortlist_ids:
        item = await db.shortlists.find_one({
            "_id": ObjectId(sid),
            "user_id": user["id"],
        })
        if item:
            serialized = serialize_doc(item)
            uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
            if uni:
                serialized["university"] = serialize_doc(uni)
            items.append(serialized)

    return {"items": items, "total": len(items)}


@router.post("/compare-ai")
async def generate_ai_comparison(
    data: CompareAIRequest,
    user: dict = Depends(require_student),
):
    """Generate side-by-side AI comparisons for selected shortlisted universities."""
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]}) or {}

    unis = []
    for sid in data.shortlist_ids:
        item = await db.shortlists.find_one({"_id": ObjectId(sid), "user_id": user["id"]})
        if item:
            uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
            if uni:
                unis.append(uni)

    if not unis:
        raise HTTPException(status_code=400, detail="No universities selected for comparison.")

    from app.ai.gemini_service import generate_ai
    system_instruction = (
        "You are an expert AI Study Abroad Advisor. Your task is to compare the selected universities "
        "side-by-side for the student's profile and provide a summary report."
    )

    prompt = f"""
    Compare the following universities for the student's profile.

    Student Profile:
    - GPA: {profile.get('gpa', 'Not provided')}
    - Field of Study: {profile.get('field_of_study', 'Not provided')}

    Universities to Compare:
    """
    for u in unis:
        prompt += (
            f"\n- {u.get('name')} in {u.get('country')} (QS Rank #{u.get('ranking')}), "
            f"Tuition: {u.get('tuition_min')}-{u.get('tuition_max')} {u.get('currency')}, "
            f"Requirements: {u.get('admission_requirements')}, Deadlines: {u.get('deadlines')}"
        )

    prompt += "\nProvide a detailed comparison summary of strengths, drawbacks, financial considerations, and your final recommendation."

    try:
        reply = await generate_ai(prompt, system_instruction, json_mode=False)
        return {"report": reply}
    except Exception as e:
        return {"report": f"Comparison analysis failed to connect to AI: {e}"}

