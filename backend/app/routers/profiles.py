"""Profile management routes for students with resume extraction and photo uploads."""

import io
import json
import logging
import base64
import os
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from bson import ObjectId

from app.database import get_database
from app.schemas.profile import ProfileUpdate, ProfileResponse
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, utc_now
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Profiles"])


def extract_text_from_file(file_bytes: bytes, file_name: str) -> str:
    """Extract raw text from PDF, DOCX, DOC, or TXT file on-demand."""
    ext = file_name.split(".")[-1].lower() if file_name else ""
    
    if ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")
        
    elif ext == "pdf":
        try:
            import pypdf
        except ImportError:
            logger.info("pypdf missing. Performing self-healing installation...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "pip", "install", "pypdf"])
            import pypdf
            
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            logger.error(f"Error parsing PDF file: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF resume: {e}")
            
    elif ext in ["docx", "doc"]:
        try:
            import docx
        except ImportError:
            logger.info("python-docx missing. Performing self-healing installation...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "pip", "install", "python-docx"])
            import docx
            
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            logger.error(f"Error parsing DOCX file: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to parse DOCX resume: {e}")
            
    raise HTTPException(status_code=400, detail="Unsupported resume format. Only PDF, DOCX, DOC, or TXT allowed.")


async def calculate_completion(profile: dict, db) -> int:
    """Calculate profile completion percentage dynamically according to the upgrade rules."""
    academic_history = profile.get("academic_history", [])
    
    # 1. Personal Information (20%)
    has_personal = bool(
        profile.get("first_name") and
        profile.get("last_name") and
        profile.get("date_of_birth") and
        profile.get("gender") and
        profile.get("nationality") and
        profile.get("current_country") and
        profile.get("phone") and
        profile.get("email")
    )
    
    # 2. Academic History (30%)
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
    has_academic = has_10 and has_12 and has_bachelors
    
    # 3. Profile Photo (10%)
    has_photo = bool(profile.get("profile_photo"))
    
    # 4. Preferences (10%)
    prefs = profile.get("preferences", {})
    has_preferences = bool(
        prefs.get("preferred_countries") and 
        prefs.get("preferred_degrees") and 
        prefs.get("intake")
    )
    has_preferred_countries = bool(prefs.get("preferred_countries"))
    
    # 5. Experience (10%)
    has_experience = bool(profile.get("experience"))
    
    # 6. Projects (10%)
    has_projects = bool(profile.get("projects"))
    
    # 7. Skills (5%)
    skills = profile.get("skills", {})
    has_skills = any(skills.get(k) for k in [
        "technical_skills", "programming_languages", "frameworks", "tools",
        "databases", "cloud_platforms", "aiml_tools", "soft_skills"
    ] if skills.get(k))
    
    # 8. Social Links (5%)
    social = profile.get("social_media", {})
    has_socials = any(social.get(k) for k in [
        "linkedin_url", "github_url", "portfolio_website", "kaggle_profile",
        "google_scholar", "researchgate", "twitter_x", "other_website"
    ] if social.get(k))
    
    # Calculate raw sum
    score = 0
    if has_personal: score += 20
    if has_academic: score += 30
    if has_photo: score += 10
    if has_preferences: score += 10
    if has_experience: score += 10
    if has_projects: score += 10
    if has_skills: score += 5
    if has_socials: score += 5
    
    # Mandatory Rule: Profile Photo, Personal Info, Academic History, Preferred Countries
    is_mandatory_complete = has_photo and has_personal and has_academic and has_preferred_countries
    
    if is_mandatory_complete:
        return 100
        
    return min(score, 99)


@router.get("/profile", response_model=ProfileResponse)
@router.get("/profiles/me", response_model=ProfileResponse)
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
    if profile.get("profile_photo_url"):
        serialized["profile_photo"] = profile["profile_photo_url"]
    serialized["completion_percentage"] = await calculate_completion(profile, db)
    return ProfileResponse(**serialized)


@router.put("/profile", response_model=ProfileResponse)
@router.put("/profiles/me", response_model=ProfileResponse)
async def update_my_profile(data: ProfileUpdate, user: dict = Depends(require_student)):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}

    # Handle photo fields updates to prevent overwriting path with URL
    if "profile_photo" in update_data:
        if not update_data["profile_photo"]:
            update_data["profile_photo"] = ""
            update_data["profile_photo_url"] = ""
            update_data["uploaded_at"] = ""
        else:
            update_data.pop("profile_photo", None)
            
    update_data.pop("profile_photo_url", None)
    update_data.pop("uploaded_at", None)

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
    if profile.get("profile_photo_url"):
        serialized["profile_photo"] = profile["profile_photo_url"]
    return ProfileResponse(**serialized)


@router.post("/profile/photo")
async def upload_profile_photo(
    request: Request,
    photo: UploadFile = File(None),
    user: dict = Depends(require_student),
):
    """Upload a profile photo. Saves file to local disk and stores path, URL, and timestamp in MongoDB."""
    # Debug Logging: Request headers and FormData keys
    logger.info(f"Request headers: {dict(request.headers)}")
    try:
        form_data = await request.form()
        logger.info(f"FormData keys: {list(form_data.keys())}")
    except Exception as e:
        logger.error(f"Failed to read form data keys: {e}")
        form_data = {}

    # File missing validation
    if not photo or not photo.filename:
        err_msg = "Profile photo is required"
        logger.error(f"Validation error: {err_msg}")
        logger.error(f"FastAPI detail response: {{'detail': '{err_msg}'}}")
        raise HTTPException(status_code=400, detail=err_msg)

    logger.info(f"Uploaded filename: {photo.filename}")
    logger.info(f"Content type: {photo.content_type}")

    # Format validation
    ext = photo.filename.split(".")[-1].lower() if photo.filename else ""
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        err_msg = "Only JPG, PNG and WEBP are allowed"
        logger.error(f"Validation error: {err_msg}")
        logger.error(f"FastAPI detail response: {{'detail': '{err_msg}'}}")
        raise HTTPException(status_code=400, detail=err_msg)

    # Size validation
    content = await photo.read()
    if len(content) > 5 * 1024 * 1024:
        err_msg = "Maximum file size is 5MB"
        logger.error(f"Validation error: {err_msg}")
        logger.error(f"FastAPI detail response: {{'detail': '{err_msg}'}}")
        raise HTTPException(status_code=400, detail=err_msg)

    # Save photo to disk
    os.makedirs("uploads/profile_photos", exist_ok=True)
    filename = f"{user['id']}_{int(time.time())}.{ext}"
    file_path = os.path.join("uploads", "profile_photos", filename).replace("\\", "/")
    
    with open(file_path, "wb") as f:
        f.write(content)

    # Construct the photo URL
    base_url = str(request.base_url).rstrip("/")
    photo_url = f"{base_url}/{file_path}"

    uploaded_at = utc_now().isoformat()
    db = get_database()
    
    # Save path, url, and uploaded_at timestamp to MongoDB
    await db.profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "profile_photo": file_path,
            "profile_photo_url": photo_url,
            "uploaded_at": uploaded_at
        }}
    )
    
    profile = await db.profiles.find_one({"user_id": user["id"]})
    completion = await calculate_completion(profile, db)
    await db.profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"completion_percentage": completion}}
    )
    
    response_data = {"profile_photo": photo_url, "completion_percentage": completion}
    logger.info(f"FastAPI detail response: {response_data}")
    return response_data


@router.delete("/profile/photo")
async def delete_profile_photo(user: dict = Depends(require_student)):
    """Remove the student's profile photo."""
    db = get_database()
    await db.profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "profile_photo": "",
            "profile_photo_url": "",
            "uploaded_at": ""
        }}
    )
    
    profile = await db.profiles.find_one({"user_id": user["id"]})
    completion = await calculate_completion(profile, db)
    await db.profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"completion_percentage": completion}}
    )
    
    return {"message": "Profile photo removed", "completion_percentage": completion}


@router.post("/profile/resume/extract")
async def extract_resume_details(file: UploadFile = File(...), user: dict = Depends(require_student)):
    """Extract text from uploaded resume and send to Gemini to parse into profile fields."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
         raise HTTPException(status_code=400, detail="Resume too large. Max 5MB")
         
    # Extract text from the PDF/DOCX
    resume_text = extract_text_from_file(content, file.filename)
    
    if not resume_text or len(resume_text.strip()) < 50:
         raise HTTPException(status_code=400, detail="Failed to extract readable text from the resume file.")

    system_instruction = (
        "You are an expert AI Resume Parsing Service. Your task is to analyze the extracted resume text "
        "and return a highly structured JSON mapping matching the student's profile schema exactly. "
        "Do not include any other conversational text or markdown wrappers besides the JSON."
    )
    
    prompt = f"""
    Parse the following resume text and map it to the profile structure.
    
    Resume Text:
    {resume_text}
    
    Return a JSON object with this exact structure (if some parts are missing, leave empty lists or nulls):
    {{
        "personal_info": {{
            "first_name": "<string or null>",
            "last_name": "<string or null>",
            "date_of_birth": "<YYYY-MM-DD or null>",
            "gender": "<string or null>",
            "nationality": "<string or null>",
            "current_country": "<string or null>",
            "phone": "<string or null>",
            "email": "<string or null>",
            "address": "<string or null>"
        }},
        "academic_history": [
            {{
                "level": "10th",
                "school_name": "<string or null>",
                "board": "<string or null>",
                "year_of_passing": "<string or null>",
                "percentage": <float or null>
            }},
            {{
                "level": "12th",
                "college_name": "<string or null>",
                "board": "<string or null>",
                "year_of_passing": "<string or null>",
                "percentage": <float or null>
            }},
            {{
                "level": "bachelors",
                "degree": "<string, e.g. BTech or null>",
                "specialization": "<string or null>",
                "university": "<string or null>",
                "year_of_passing": "<string or null>",
                "cgpa": <float or null>,
                "percentage": <float or null>
            }},
            {{
                "level": "masters",
                "degree": "<string, e.g. MSc or null>",
                "specialization": "<string or null>",
                "university": "<string or null>",
                "year_of_passing": "<string or null>",
                "cgpa": <float or null>,
                "percentage": <float or null>
            }},
            {{
                "level": "phd",
                "degree": "PhD",
                "research_area": "<string or null>",
                "university": "<string or null>",
                "year_of_passing": "<string or null>"
            }}
        ],
        "experience": [
            {{
                "company": "<string>",
                "role": "<string>",
                "location": "<string or null>",
                "start_date": "<string, e.g. YYYY-MM or null>",
                "end_date": "<string or null>",
                "current_company": <bool>,
                "description": "<string or null>"
            }}
        ],
        "projects": [
            {{
                "title": "<string>",
                "description": "<string or null>",
                "technologies": [<list of strings>],
                "github_link": "<string or null>",
                "project_url": "<string or null>",
                "start_date": "<string or null>",
                "end_date": "<string or null>"
            }}
        ],
        "skills": {{
            "technical_skills": [<list of strings>],
            "programming_languages": [<list of strings>],
            "frameworks": [<list of strings>],
            "tools": [<list of strings>],
            "databases": [<list of strings>],
            "cloud_platforms": [<list of strings>],
            "aiml_tools": [<list of strings>],
            "soft_skills": [<list of strings>]
        }},
        "publications": [
            {{
                "title": "<string>",
                "journal_conference": "<string or null>",
                "date": "<string or null>",
                "doi": "<string or null>",
                "url": "<string or null>",
                "authors": [<list of strings>]
            }}
        ],
        "certifications": [
            {{
                "name": "<string>",
                "provider": "<string or null>",
                "issue_date": "<string or null>",
                "credential_url": "<string or null>",
                "credential_id": "<string or null>"
            }}
        ],
        "social_media": {{
            "linkedin_url": "<string or null>",
            "github_url": "<string or null>",
            "portfolio_website": "<string or null>",
            "kaggle_profile": "<string or null>",
            "google_scholar": "<string or null>",
            "researchgate": "<string or null>",
            "twitter_x": "<string or null>",
            "other_website": "<string or null>"
        }}
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        parsed_data = json.loads(cleaned)
        return parsed_data
    except Exception as e:
        logger.error(f"Failed to extract resume details: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini resume extraction failed: {e}")


@router.get("/profiles/student/{student_id}", response_model=ProfileResponse)
async def get_student_profile(student_id: str, user: dict = Depends(require_student)):
    """Employees/admins use a different route - this is for student self-view."""
    raise HTTPException(status_code=404, detail="Use employee/admin endpoints")
