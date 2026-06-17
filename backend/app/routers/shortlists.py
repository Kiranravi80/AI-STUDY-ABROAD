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


def calculate_match_score(profile: dict, program: dict) -> int:
    score = 75  # base score
    gpa_str = profile.get("gpa")
    req_details = program.get("requirements_details") or {}
    
    # Check GPA
    if gpa_str:
        try:
            if "%" in gpa_str:
                gpa_val = float(gpa_str.replace("%", ""))
                if gpa_val > 80: score += 10
                elif gpa_val > 70: score += 5
            else:
                gpa_val = float(gpa_str)
                if gpa_val >= 3.5: score += 12
                elif gpa_val >= 3.0: score += 6
        except ValueError:
            pass
            
    # Check IELTS/language requirements
    test_scores = profile.get("test_scores", [])
    ielts_score = None
    for t in test_scores:
        if t.get("test_name", "").lower() == "ielts":
            try:
                ielts_score = float(t.get("score", "0"))
            except ValueError:
                pass
                
    req_lang = req_details.get("language") or {}
    req_ielts = req_lang.get("ielts")
    if req_ielts and ielts_score:
        if ielts_score >= req_ielts:
            score += 8
        else:
            score -= 10
            
    return min(max(score, 45), 98)


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
            # Fallback mock program if scraper deleted it
            program = {
                "name": item["program_name"],
                "degree": "Master's",
                "language": "English",
                "campuses": []
            }
            
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
            "match_score": calculate_match_score(profile, program),
            "notes": item.get("notes") or "",
            "created_at": item.get("created_at")
        }
        enriched.append(serialized)

    return {"items": enriched, "total": len(enriched)}


@router.post("", status_code=201)
async def add_to_shortlist(data: ShortlistCreate, user: dict = Depends(require_student)):
    db = get_database()

    # Verify university exists
    uni = await db.universities.find_one({"_id": ObjectId(data.university_id)})
    if not uni:
        raise HTTPException(status_code=404, detail="University not found")

    # Verify program exists inside the university
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
        "match_score": calculate_match_score(profile, program),
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
    """Retrieve AI Suggested Programs based on student profile and preferences."""
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]})
    if not profile:
        return {"items": [], "total": 0}

    prefs = profile.get("preferences", {})
    preferred_countries = prefs.get("preferred_countries", [])
    preferred_degrees = prefs.get("preferred_degrees", [])
    budget_max = prefs.get("budget_max")
    specialization = profile.get("field_of_study", "")

    # Build Mongo query
    query = {}
    if preferred_countries:
        query["country"] = {"$in": preferred_countries}

    # Fetch universities matching preferences
    unis = await db.universities.find(query).to_list(length=100)
    
    candidates = []
    for uni in unis:
        for prog in uni.get("programs", []):
            # 1. Check degree match
            if preferred_degrees:
                if prog.get("degree") not in preferred_degrees:
                    continue
            
            # 2. Check budget match
            campuses = prog.get("campuses", [])
            if budget_max is not None:
                fees = [c.get("tuition_fee") for c in campuses if c.get("tuition_fee") is not None]
                if fees and min(fees) > budget_max:
                    continue
            
            # Compute match score
            match_score = calculate_match_score(profile, prog)
            
            # Filter low matches if specialization matches
            if specialization:
                spec_keywords = re.findall(r'\w+', specialization.lower())
                prog_name_lower = prog.get("name", "").lower()
                keyword_match = any(kw in prog_name_lower for kw in spec_keywords if len(kw) > 3)
                if keyword_match:
                    match_score = min(match_score + 10, 99)
            
            candidates.append({
                "university_id": str(uni["_id"]),
                "university_name": uni["name"],
                "program_name": prog["name"],
                "degree": prog.get("degree") or "Master's",
                "language": prog.get("language") or "English",
                "location": format_location(prog, uni),
                "tuition_fee": format_tuition_fee(prog, uni),
                "deadline": format_deadline(prog),
                "intake": prog.get("intake") or [],
                "apply_url": campuses[0].get("apply_url") if campuses else prog.get("apply_url") or uni.get("website") or "",
                "match_score": match_score
            })

    # Sort candidates by match score descending
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    top_candidates = candidates[:10]  # return top 10 suggestions

    return {"items": top_candidates, "total": len(top_candidates)}


@router.get("/{shortlist_id}/similar")
async def get_similar_programs(shortlist_id: str, user: dict = Depends(require_student)):
    """Retrieve 10 similar programs in Germany database with Gemini recommendations."""
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

    # Find candidate programs in Germany
    germany_unis = await db.universities.find({"country": "Germany"}).to_list(length=150)
    
    # Simple keyword extraction
    keywords = [kw.lower() for kw in re.findall(r'\w+', target_program_name) if len(kw) > 3]
    if not keywords:
        keywords = ["science", "engineering", "technology"]

    candidates = []
    for uni in germany_unis:
        for prog in uni.get("programs", []):
            # Exclude current program/university combo
            if str(uni["_id"]) == shortlist_item["university_id"] and prog["name"] == target_program_name:
                continue
                
            prog_name_lower = prog["name"].lower()
            if any(kw in prog_name_lower for kw in keywords):
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
                    "apply_url": campuses[0].get("apply_url") if campuses else prog.get("apply_url") or uni.get("website") or ""
                })
                
    # Sort or prune to top 15 candidates for LLM processing
    candidates = candidates[:15]
    
    if not candidates:
        # Fallback empty list if none found
        return {"items": [], "total": 0}

    # Use Gemini to rank/recommend 10 programs
    system_instruction = (
        "You are an expert AI Admission Recommendation Engine. Your job is to select 10 similar programs in Germany "
        "and provide personalized reasoning (why recommended) for each of them based on the student's profile."
    )
    
    prompt = f"""
    The student shortlisted the program: "{target_program_name}" at "{target_uni.get('name')}".
    
    Student Profile:
    - GPA: {profile.get('gpa', 'Not provided')}
    - Field of study: {profile.get('field_of_study', 'Not provided')}
    - Test Scores: {json.dumps(profile.get('test_scores', []))}
    
    Here is a list of similar program options in Germany:
    {json.dumps(candidates)}
    
    Please choose exactly 10 programs from the candidates that are most relevant. For each selected program:
    1. Calculate a personalized "match_score" (integer between 60 and 98) representing suitability for this student.
    2. Write a short 1-2 sentence "why_recommended" explaining why this program is a good fit.
    
    Return the response as a JSON array of 10 items.
    Example schema:
    [
        {{
            "program_name": "...",
            "university_name": "...",
            "location": "...",
            "degree": "...",
            "language": "...",
            "tuition": "...",
            "deadline": "...",
            "intake": "...",
            "apply_url": "...",
            "match_score": 85,
            "why_recommended": "This program offers strong machine learning tracks that align with your AI coursework."
        }}
    ]
    """

    try:
        raw_reply = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_reply)
        similar_items = json.loads(cleaned)
        # Ensure we return exactly what was generated (up to 10)
        return {"items": similar_items[:10], "total": len(similar_items)}
    except Exception as e:
        logger.error(f"Failed to generate AI similar programs recommendation: {e}")
        # Programmatic fallback
        fallback_items = []
        for c in candidates[:10]:
            fallback_items.append({
                **c,
                "match_score": 80,
                "why_recommended": "Based on similar course curriculum and international student support."
            })
        return {"items": fallback_items, "total": len(fallback_items)}


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
