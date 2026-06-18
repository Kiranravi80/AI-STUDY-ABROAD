"""AI analysis report routes for admission chance and requirements checking."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from pydantic import BaseModel

from app.database import get_database
from app.schemas.common import AnalysisRequest, CostEstimateRequest
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, serialize_docs, utc_now
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["AI Analysis"])


@router.post("/generate")
async def generate_analysis_report(
    data: AnalysisRequest,
    user: dict = Depends(require_student),
):
    """Generate detailed AI profile analysis, requirements gap, and roadmaps."""
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]})

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Student profile not found. Please complete your profile first."
        )

    university_id = data.university_id
    program_name = data.program_name

    # Fallback to latest shortlisted program if not provided
    if not university_id or not program_name:
        latest_shortlist = await db.shortlists.find_one(
            {"user_id": user["id"]},
            sort=[("created_at", -1)]
        )
        if latest_shortlist:
            university_id = latest_shortlist["university_id"]
            program_name = latest_shortlist["program_name"]

    if not university_id or not program_name:
        raise HTTPException(
            status_code=400,
            detail="Please shortlist a program first to run the AI Admission Analysis."
        )

    university = await db.universities.find_one({"_id": ObjectId(university_id)})
    if not university:
        raise HTTPException(status_code=404, detail="University not found")

    # Find the target program
    program = None
    for p in university.get("programs", []):
        if p.get("name", "").lower() == program_name.lower():
            program = p
            break

    if not program:
        raise HTTPException(
            status_code=404,
            detail=f"Program '{program_name}' not found at this university"
        )

    # Get uploaded documents
    uploaded_docs = await db.documents.find({"user_id": user["id"]}).to_list(length=100)
    uploaded_doc_names = [d.get("name", "") for d in uploaded_docs]

    # Call Gemini to perform structured gap analysis
    system_instruction = (
        "You are an expert AI Study Abroad Admission Consultant. Your task is to perform a highly accurate, "
        "evidence-based comparison between a student's profile (including uploaded documents) and a specific program's requirements. "
        "You must return the analysis in valid JSON format only, matching the specified structure."
    )

    prompt = f"""
    Perform a detailed admission analysis for this student against the target program.

    Student Profile:
    - Academic Level: {profile.get('academic_level', 'Not provided')}
    - Field of Study: {profile.get('field_of_study', 'Not provided')}
    - GPA: {profile.get('gpa', 'Not provided')}
    - Academic History (including ECTS/credits): {json.dumps(profile.get('academic_history', []))}
    - Standardized Test Scores: {json.dumps(profile.get('test_scores', []))}
    - Experience: {json.dumps(profile.get('experience', []))}
    - Projects: {json.dumps(profile.get('projects', []))}
    - Skills: {json.dumps(profile.get('skills', {}))}
    - Publications: {json.dumps(profile.get('publications', []))}
    - Certifications: {json.dumps(profile.get('certifications', []))}
    - Social Media: {json.dumps(profile.get('social_media', {}))}
    - Preferences: {json.dumps(profile.get('preferences', {}))}

    Student's Uploaded Documents:
    {json.dumps(uploaded_doc_names)}

    Target Program:
    - Program Name: {program_name}
    - University Name: {university.get('name')}
    - Degree Type: {program.get('degree', "Master's")}
    - Intakes: {json.dumps(program.get('intake', []))}
    - Deadlines: {json.dumps(program.get('deadlines', {}))}
    - Requirements Details (including ECTS & Language rules): {json.dumps(program.get('requirements_details', {}))}
    - University General Requirements: {json.dumps(university.get('admission_requirements', []))}

    Country Requirements for Germany:
    - APS: Certificate required for students from India, China, Vietnam.
    - Uni Assist / VPD: Required if specified by the program requirements.

    Analyze the requirements gap and document check. Provide:
    1. Overall Chance: one of "Very High", "High", "Moderate", "Low"
    2. Percentage: integer between 10 and 99
    3. Strengths: list of 3-5 profile matches (e.g. CGPA exceeds requirement, Strong CS background, etc.)
    4. Weaknesses: list of 1-4 areas of improvement / missing items (e.g. Missing Mathematics ECTS, No APS, etc.)
    5. Requirement Gap Analysis: array of items:
       {{
           "requirement": "<required credit or GPA, e.g., 30 ECTS Mathematics>",
           "profile": "<student credentials, e.g., 24 ECTS>",
           "gap": "<missing amount or text, e.g., Missing 6 ECTS>"
       }}
    6. Document Check: array of items for each required document (e.g. CV, Transcript, Passport, IELTS, APS Certificate, LOR, SOP):
       {{
           "document_name": "<document name, e.g., APS Certificate>",
           "status": "<'Uploaded' if a similar document name exists in the student's uploaded documents list, else 'Missing'>"
       }}
    7. AI Reasoning: a paragraph explanation
    8. AI Roadmap: a step-by-step checklist of 4-6 actions (e.g. "Step 1: Take IELTS")

    Output JSON structure must be exactly:
    {{
        "overall_chance": "Very High" | "High" | "Moderate" | "Low",
        "admission_chance": <percentage>,
        "strengths": [<list of strings>],
        "weaknesses": [<list of strings>],
        "requirement_gap_analysis": [
            {{
                "requirement": "...",
                "profile": "...",
                "gap": "..."
            }}
        ],
        "document_check": [
            {{
                "document_name": "...",
                "status": "Uploaded" | "Missing"
            }}
        ],
        "ai_reasoning": "...",
        "ai_roadmap": ["Step 1: ...", "Step 2: ..."]
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        eval_data = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to generate AI analysis: {e}")
        # Programmatic calculation fallback using real database rules
        from app.utils.scoring_engine import calculate_eligibility_and_score
        scoring = calculate_eligibility_and_score(profile, program, university)
        
        # Map documents status using actual uploaded document names
        doc_checks = []
        for doc in scoring["document_check"]:
            doc_name = doc["document_name"]
            status = "Missing"
            for udoc in uploaded_doc_names:
                udoc_clean = udoc.lower().replace(" ", "").replace("_", "").replace("-", "")
                doc_clean = doc_name.lower().replace(" ", "").replace("_", "").replace("-", "")
                if doc_clean in udoc_clean or udoc_clean in doc_clean:
                    status = "Uploaded"
                    break
            doc_checks.append({
                "document_name": doc_name,
                "status": status
            })

        eval_data = {
            "overall_chance": scoring["category"],
            "admission_chance": scoring["match_score"],
            "strengths": scoring["strengths"],
            "weaknesses": scoring["weaknesses"],
            "requirement_gap_analysis": scoring["requirement_gap"],
            "document_check": doc_checks,
            "ai_reasoning": f"Your programmatic admission eligibility score is calculated at {scoring['match_score']}%. " + " ".join(scoring["reasons"]),
            "ai_roadmap": [
                "Step 1: Gather and upload certified documents for outstanding items.",
                "Step 2: Submit APS certificate verification request for Germany (mandatory for India/China/Vietnam).",
                "Step 3: Draft program-specific Statement of Purpose (SOP).",
                "Step 4: Request Academic Reference / Recommendation Letters from university professors."
            ]
        }

    # Compile report dictionary
    report = {
        "user_id": user["id"],
        "university_id": university_id,
        "program_name": program_name,
        "university_name": university["name"],
        "overall_chance": eval_data.get("overall_chance", "Moderate"),
        "admission_chance": eval_data.get("admission_chance", 70),
        "strengths": eval_data.get("strengths", []),
        "weaknesses": eval_data.get("weaknesses", []),
        "requirement_gap_analysis": eval_data.get("requirement_gap_analysis", []),
        "document_check": eval_data.get("document_check", []),
        "ai_reasoning": eval_data.get("ai_reasoning", ""),
        "ai_roadmap": eval_data.get("ai_roadmap", []),
        "is_premium": False,
        "created_at": utc_now().isoformat(),
    }

    result = await db.analysis_reports.insert_one(report)
    report["id"] = str(result.inserted_id)

    return serialize_doc(report)


@router.get("/reports")
async def get_analysis_reports(user: dict = Depends(require_student)):
    """Retrieve student's evaluation reports."""
    db = get_database()
    reports = await db.analysis_reports.find(
        {"user_id": user["id"]}
    ).sort("created_at", -1).to_list(20)

    return {"items": [serialize_doc(r) for r in reports], "total": len(reports)}


@router.get("/reports/latest")
async def get_latest_report(user: dict = Depends(require_student)):
    """Retrieve student's latest evaluation report."""
    db = get_database()
    report = await db.analysis_reports.find_one(
        {"user_id": user["id"]},
        sort=[("created_at", -1)],
    )

    if not report:
        return {"message": "No analysis reports yet", "report": None}

    return {"report": serialize_doc(report)}


@router.post("/cost-estimate")
async def estimate_costs(
    data: CostEstimateRequest,
    user: dict = Depends(require_student),
):
    """Estimate and record total costs using AI cost engine."""
    db = get_database()
    university = await db.universities.find_one({"_id": ObjectId(data.university_id)})

    if not university:
        raise HTTPException(status_code=404, detail="University not found")

    from app.ai.cost_estimator import estimate_study_costs
    costs = await estimate_study_costs(
        university, data.program_name, data.duration_years
    )

    report = {
        "user_id": user["id"],
        "university_id": data.university_id,
        "program_name": data.program_name,
        "duration_years": data.duration_years,
        "university_name": university.get("name"),
        "country": university.get("country"),
        **costs,
        "created_at": utc_now().isoformat(),
    }

    result = await db.cost_reports.insert_one(report)
    report["id"] = str(result.inserted_id)

    return serialize_doc(report)


@router.get("/costs")
async def get_cost_reports(user: dict = Depends(require_student)):
    """Fetch previous cost estimates."""
    db = get_database()
    reports = await db.cost_reports.find(
        {"user_id": user["id"]}
    ).sort("created_at", -1).to_list(50)

    return {"items": [serialize_doc(r) for r in reports], "total": len(reports)}
