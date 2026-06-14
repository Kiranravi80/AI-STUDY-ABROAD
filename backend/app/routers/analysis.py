"""AI analysis report routes."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.database import get_database
from app.schemas.common import AnalysisRequest, CostEstimateRequest
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc, serialize_docs, utc_now
from app.ai.profile_engine import analyze_profile
from app.ai.admission_engine import predict_admission_probability
from app.ai.recommendation_engine import match_university
from app.ai.cost_estimator import estimate_study_costs

router = APIRouter(prefix="/analysis", tags=["AI Analysis"])


@router.post("/generate")
async def generate_analysis_report(
    data: AnalysisRequest,
    user: dict = Depends(require_student),
):
    """Generate detailed AI profile analysis and admission predictions."""
    db = get_database()
    profile = await db.profiles.find_one({"user_id": user["id"]})

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Student profile not found. Please complete your profile first."
        )

    university = None
    if data.university_id:
        university = await db.universities.find_one({"_id": ObjectId(data.university_id)})
        if not university:
            raise HTTPException(status_code=404, detail="University not found")

    # 1. Run profile audit
    profile_eval = await analyze_profile(profile)

    # 2. Run university matching evaluations
    admission_eval = {}
    match_eval = {}

    if university:
        admission_eval = await predict_admission_probability(
            profile, university, data.program_name
        )
        match_eval = await match_university(profile, university)

    # Fetch recommended universities (fallback helper)
    query = {}
    if profile.get("preferences", {}).get("preferred_countries"):
        query["country"] = {"$in": profile["preferences"]["preferred_countries"]}
    recommended_cursor = db.universities.find(query).sort("ranking", 1).limit(5)
    recommended = await recommended_cursor.to_list(5)

    # Compile report dictionary
    report = {
        "user_id": user["id"],
        "university_id": data.university_id,
        "program_name": data.program_name,
        # Profile fields
        "profile_score": profile_eval.get("profile_score", 65),
        "strengths": profile_eval.get("strengths", []),
        "weaknesses": profile_eval.get("weaknesses", []),
        "missing_requirements": profile_eval.get("missing_requirements", []),
        "recommendations": profile_eval.get("recommendations", []),
        "improvement_plan": profile_eval.get("improvement_plan", []),
        "profile_explanation": profile_eval.get("detailed_explanation", ""),
        # Admission fields
        "admission_chance": admission_eval.get("admission_probability", profile_eval.get("profile_score", 65)),
        "reasons_why_student_matches": admission_eval.get("reasons_why_student_matches", []),
        "reasons_why_student_may_be_rejected": admission_eval.get("reasons_why_student_may_be_rejected", []),
        "suggestions": admission_eval.get("improvement_suggestions", profile_eval.get("recommendations", [])),
        "admission_missing_requirements": admission_eval.get("missing_requirements", []),
        "confidence_score": admission_eval.get("confidence_score", 70),
        # Match fields
        "match_percentage": match_eval.get("match_percentage", 0) if university else 0,
        "category": match_eval.get("category", "") if university else "",
        "match_reasons": match_eval.get("key_reasons", []) if university else [],
        "recommended_universities": [serialize_doc(u) for u in recommended],
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
