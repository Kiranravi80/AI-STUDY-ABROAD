"""Shortlist management routes for programs."""

import json
import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from pydantic import BaseModel

from app.database import get_database
from app.schemas.common import ShortlistCreate, ShortlistUpdate
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, serialize_docs, utc_now
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text
from app.utils.scoring_engine import calculate_eligibility_and_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shortlists", tags=["Shortlists"])


class CompareAIRequest(BaseModel):
    shortlist_ids: list[str]


def format_tuition_fee(program: dict, university: dict) -> str:
    campuses = program.get("campuses", [])
    currency = program.get("currency") or university.get("currency") or "EUR"
    if not campuses:
        t_min = university.get("tuition_min")
        t_max = university.get("tuition_max")
        if t_min is not None and t_max is not None:
            if t_min == t_max:
                return "Free" if t_min == 0 else f"{currency} {t_min:,.0f} / semester"
            return f"{currency} {t_min:,.0f} - {t_max:,.0f} / semester"
        return "N/A"
    
    fees = [c.get("tuition_fee") for c in campuses if c.get("tuition_fee") is not None]
    if not fees:
        return "N/A"
    
    min_fee = min(fees)
    max_fee = max(fees)
    if min_fee == max_fee:
        return "Free" if min_fee == 0 else f"{currency} {min_fee:,.0f} / semester"
    return f"{currency} {min_fee:,.0f} - {max_fee:,.0f} / semester"


def format_deadline(program: dict) -> str:
    deadlines = program.get("deadlines", {})
    if deadlines:
        items = [f"{k}: {v}" for k, v in deadlines.items()]
        return ", ".join(items)
    return program.get("deadline") or "N/A"


def format_location(program: dict, university: dict) -> str:
    campuses = program.get("campuses", [])
    if campuses:
        cities = list(set(c.get("city") for c in campuses if c.get("city")))
        if cities:
            return ", ".join(cities) + f", {university.get('country')}"
    
    city = university.get("city")
    country = university.get("country")
    if city and country:
        return f"{city}, {country}"
    return country or "N/A"


@router.get("")
async def get_shortlists(user: dict = Depends(require_student)):
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]}) or {}
    shortlists = await db.shortlists.find({"user_id": user["id"]}).to_list(length=200)

    enriched = []
    for item in shortlists:
        uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
        if not uni:
            continue
            
        program = None
        for p in uni.get("programs", []):
            if p.get("name", "").lower() == item["program_name"].lower():
                program = p
                break
                
        if not program:
            program = {
                "name": item["program_name"],
                "degree": "Master's",
                "language": "English",
                "campuses": []
            }
            
        # Run real scoring engine
        res = calculate_eligibility_and_score(profile, program, uni)

        serialized = {
            "id": str(item["_id"]),
            "university_id": item["university_id"],
            "program_name": item["program_name"],
            "university_name": uni["name"],
            "degree": program.get("degree") or "Master's",
            "language": program.get("language") or "English",
            "location": format_location(program, uni),
            "tuition_fee": format_tuition_fee(program, uni),
            "deadline": format_deadline(program),
            "intake": program.get("intake") or [],
            "apply_url": program.get("campuses", [{}])[0].get("apply_url") if program.get("campuses") else program.get("apply_url") or uni.get("website") or "",
            "match_score": res["match_score"],
            "notes": item.get("notes") or "",
            "created_at": item.get("created_at")
        }
        enriched.append(serialized)

    return {"items": enriched, "total": len(enriched)}


@router.post("", status_code=201)
async def add_to_shortlist(data: ShortlistCreate, user: dict = Depends(require_student)):
    db = get_database()

    uni = await db.universities.find_one({"_id": ObjectId(data.university_id)})
    if not uni:
        raise HTTPException(status_code=404, detail="University not found")

    program = None
    for p in uni.get("programs", []):
        if p.get("name", "").lower() == data.program_name.lower():
            program = p
            break
            
    if not program:
        raise HTTPException(status_code=404, detail=f"Program '{data.program_name}' not found at this university")

    existing = await db.shortlists.find_one({
        "user_id": user["id"],
        "university_id": data.university_id,
        "program_name": data.program_name
    })
    if existing:
        raise HTTPException(status_code=400, detail="Program already in shortlist")

    doc = {
        "user_id": user["id"],
        "university_id": data.university_id,
        "program_name": data.program_name,
        "notes": data.notes or "",
        "created_at": utc_now().isoformat(),
    }
    result = await db.shortlists.insert_one(doc)
    doc["_id"] = result.inserted_id
    
    profile = await db.profiles.find_one({"user_id": user["id"]}) or {}
    res = calculate_eligibility_and_score(profile, program, uni)
    
    serialized = {
        "id": str(doc["_id"]),
        "university_id": doc["university_id"],
        "program_name": doc["program_name"],
        "university_name": uni["name"],
        "degree": program.get("degree") or "Master's",
        "language": program.get("language") or "English",
        "location": format_location(program, uni),
        "tuition_fee": format_tuition_fee(program, uni),
        "deadline": format_deadline(program),
        "intake": program.get("intake") or [],
        "apply_url": program.get("campuses", [{}])[0].get("apply_url") if program.get("campuses") else program.get("apply_url") or uni.get("website") or "",
        "match_score": res["match_score"],
        "notes": doc["notes"],
        "created_at": doc["created_at"]
    }
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


@router.get("/suggestions")
async def get_suggested_programs(user: dict = Depends(require_student)):
    """Retrieve Scored and Filtered Program Recommendations."""
    db = get_database()
    
    # 1. Check if shortlist is empty
    shortlists_count = await db.shortlists.count_documents({"user_id": user["id"]})
    if shortlists_count == 0:
        return {
            "message": "Shortlist at least one program to receive personalized recommendations.",
            "items": [],
            "total": 0
        }

    # 2. Check if profile exists and is completed (100%)
    profile = await db.profiles.find_one({"user_id": user["id"]})
    if not profile:
        return {
            "message": "Complete your profile and shortlist programs to receive recommendations.",
            "items": [],
            "total": 0
        }
        
    from app.routers.profiles import calculate_completion
    completion = await calculate_completion(profile, db)
    if completion < 100:
        return {
            "message": "Complete your profile and shortlist programs to receive recommendations.",
            "items": [],
            "total": 0
        }

    # Gather shortlisted programs
    shortlists = await db.shortlists.find({"user_id": user["id"]}).to_list(length=100)
    shortlisted_keys = set((s["university_id"], s["program_name"].lower()) for s in shortlists)
    shortlisted_program_names = [s["program_name"] for s in shortlists]

    # Clean keywords from shortlisted programs to suggest similar ones
    shortlist_keywords = []
    for sname in shortlisted_program_names:
        shortlist_keywords.extend([kw.lower() for kw in re.findall(r'\w+', sname) if len(kw) > 3])
    shortlist_keywords = list(set(shortlist_keywords))

    prefs = profile.get("preferences", {})
    preferred_countries = prefs.get("preferred_countries", [])
    budget_max = prefs.get("budget_max")

    # Build Mongo query for universities
    uni_query = {}
    if preferred_countries:
        uni_query["country"] = {"$in": preferred_countries}

    unis = await db.universities.find(uni_query).to_list(length=150)
    
    # Analyze degree progression
    student_level = profile.get("academic_level", "").lower()
    
    candidates = []
    for uni in unis:
        uni_id_str = str(uni["_id"])
        for prog in uni.get("programs", []):
            prog_name_lower = prog["name"].lower()
            
            # Exclude programs already in shortlist
            if (uni_id_str, prog_name_lower) in shortlisted_keys:
                continue

            # Enforce Degree Progression Logic (Issue 2)
            prog_degree = prog.get("degree", "").lower()
            is_bach = "bachelor" in prog_degree
            is_master = "master" in prog_degree or "mba" in prog_degree or "msc" in prog_degree or "mtech" in prog_degree
            is_phd = "phd" in prog_degree or "doctor" in prog_degree

            if student_level == "bachelors":
                if not is_master:
                    continue  # Only show Master's
            elif student_level == "masters":
                if not (is_master or is_phd):
                    continue  # Show Master's and PhD
            elif student_level == "12th":
                if not is_bach:
                    continue  # Only show Bachelor's
            else:
                pass  # If no academic info, let progression filters pass (handled by top logic)

            # Filter budget
            if budget_max is not None:
                campuses = prog.get("campuses", [])
                fees = [c.get("tuition_fee") for c in campuses if c.get("tuition_fee") is not None]
                tuition_fee_val = min(fees) if fees else (uni.get("tuition_min") or 0.0)
                if tuition_fee_val > budget_max:
                    continue

            # Run Scoring Engine
            scoring_res = calculate_eligibility_and_score(profile, prog, uni)
            
            # Boost score slightly if similar to shortlisted courses
            similarity_boost = 0
            if shortlist_keywords and any(kw in prog_name_lower for kw in shortlist_keywords):
                similarity_boost = 5

            match_score = min(scoring_res["match_score"] + similarity_boost, 99)
            category = scoring_res["category"]

            # Filter low matches (only recommend Safe or Target admission chances)
            if match_score < 70:
                continue

            reasons_str = ", ".join(scoring_res["reasons"])
            why_recommended = f"{match_score}% Match. Reasons: {reasons_str}."

            candidates.append({
                "university_id": uni_id_str,
                "university_name": uni["name"],
                "program_name": prog["name"],
                "degree": prog.get("degree") or "Master's",
                "language": prog.get("language") or "English",
                "location": format_location(prog, uni),
                "tuition_fee": format_tuition_fee(prog, uni),
                "deadline": format_deadline(prog),
                "intake": prog.get("intake") or [],
                "apply_url": prog.get("campuses", [{}])[0].get("apply_url") if prog.get("campuses") else prog.get("apply_url") or uni.get("website") or "",
                "match_score": match_score,
                "category": category,
                "why_recommended": why_recommended
            })

    # Sort suggestions by match score descending
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    top_candidates = candidates[:10]

    return {"items": top_candidates, "total": len(top_candidates)}


@router.get("/{shortlist_id}/similar")
async def get_similar_programs(shortlist_id: str, user: dict = Depends(require_student)):
    """Retrieve 10 similar programs in Germany database with matching scores."""
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]}) or {}
    
    shortlist_item = await db.shortlists.find_one({
        "_id": ObjectId(shortlist_id),
        "user_id": user["id"]
    })
    if not shortlist_item:
        raise HTTPException(status_code=404, detail="Shortlisted program not found")
        
    target_program_name = shortlist_item["program_name"]
    target_uni = await db.universities.find_one({"_id": ObjectId(shortlist_item["university_id"])})
    if not target_uni:
        raise HTTPException(status_code=404, detail="Associated university not found")

    germany_unis = await db.universities.find({"country": "Germany"}).to_list(length=150)
    
    keywords = [kw.lower() for kw in re.findall(r'\w+', target_program_name) if len(kw) > 3]
    if not keywords:
        keywords = ["science", "engineering", "technology"]

    candidates = []
    for uni in germany_unis:
        uni_id_str = str(uni["_id"])
        for prog in uni.get("programs", []):
            if uni_id_str == shortlist_item["university_id"] and prog["name"] == target_program_name:
                continue
                
            prog_name_lower = prog["name"].lower()
            if any(kw in prog_name_lower for kw in keywords):
                # Calculate real scoring
                scoring_res = calculate_eligibility_and_score(profile, prog, uni)
                
                reasons_str = ", ".join(scoring_res["reasons"])
                why_rec = f"Curriculum matches your interests in {', '.join(keywords[:2])}. {reasons_str}."

                campuses = prog.get("campuses", [])
                candidates.append({
                    "program_name": prog["name"],
                    "university_name": uni["name"],
                    "location": format_location(prog, uni),
                    "degree": prog.get("degree") or "Master's",
                    "language": prog.get("language") or "English",
                    "tuition": format_tuition_fee(prog, uni),
                    "deadline": format_deadline(prog),
                    "intake": ", ".join(prog.get("intake", ["Winter Intake"])),
                    "apply_url": campuses[0].get("apply_url") if campuses else prog.get("apply_url") or uni.get("website") or "",
                    "match_score": scoring_res["match_score"],
                    "why_recommended": why_rec
                })
                
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    return {"items": candidates[:10], "total": len(candidates[:10])}


@router.get("/compare")
async def compare_shortlists(
    ids: str,
    user: dict = Depends(require_student),
):
    db = get_database()
    shortlist_ids = [s.strip() for s in ids.split(",") if s.strip()]

    items = []
    for sid in shortlist_ids:
        item = await db.shortlists.find_one({
            "_id": ObjectId(sid),
            "user_id": user["id"],
        })
        if item:
            uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
            if uni:
                program = None
                for p in uni.get("programs", []):
                    if p.get("name", "").lower() == item["program_name"].lower():
                        program = p
                        break
                if program:
                    items.append({
                        "id": str(item["_id"]),
                        "university_id": item["university_id"],
                        "program_name": item["program_name"],
                        "university_name": uni["name"],
                        "degree": program.get("degree"),
                        "language": program.get("language"),
                        "location": format_location(program, uni),
                        "tuition_fee": format_tuition_fee(program, uni),
                        "deadline": format_deadline(program),
                        "intake": program.get("intake") or []
                    })
    return {"items": items, "total": len(items)}


@router.post("/compare-ai")
async def generate_ai_comparison(
    data: CompareAIRequest,
    user: dict = Depends(require_student),
):
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]}) or {}

    unis = []
    for sid in data.shortlist_ids:
        item = await db.shortlists.find_one({"_id": ObjectId(sid), "user_id": user["id"]})
        if item:
            uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
            if uni:
                unis.append((uni, item["program_name"]))

    if not unis:
        raise HTTPException(status_code=400, detail="No programs selected for comparison.")

    prompt = f"""
    Compare the following programs for the student's profile.

    Student Profile:
    - GPA: {profile.get('gpa', 'Not provided')}
    - Field of Study: {profile.get('field_of_study', 'Not provided')}

    Programs to Compare:
    """
    for u, prog_name in unis:
        prompt += (
            f"\n- {prog_name} at {u.get('name')} in {u.get('country')} (QS Rank #{u.get('ranking')}), "
            f"Tuition: {u.get('tuition_min')}-{u.get('tuition_max')} {u.get('currency')}"
        )

    prompt += "\nProvide a detailed comparison summary of strengths, drawbacks, financial considerations, and your final recommendation."

    try:
        reply = await generate_ai(prompt, "You are an expert AI Study Abroad Advisor.", json_mode=False)
        return {"report": reply}
    except Exception as e:
        return {"report": f"Comparison analysis failed to connect to AI: {e}"}
