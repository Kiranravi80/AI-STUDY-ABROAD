"""Student dashboard stats route."""

from fastapi import APIRouter, Depends
from bson import ObjectId

from app.database import get_database
from app.middleware.auth import require_student
from app.utils.helpers import serialize_doc
from app.ai.admission_engine import predict_admission_probability

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/student")
async def student_dashboard(user: dict = Depends(require_student)):
    db = get_database()
    user_id = user["id"]

    shortlist_count = await db.shortlists.count_documents({"user_id": user_id})
    applications_count = await db.applications.count_documents({"user_id": user_id})
    analysis_count = await db.analysis_reports.count_documents({"user_id": user_id})
    universities_count = await db.universities.count_documents({})

    profile = await db.profiles.find_one({"user_id": user_id})
    roadmap = await db.roadmaps.find_one({"user_id": user_id})

    # Recommended universities based on preferences
    query = {}
    if profile and profile.get("preferences", {}).get("preferred_countries"):
        query["country"] = {"$in": profile["preferences"]["preferred_countries"]}

    recommended = await db.universities.find(query).sort("ranking", 1).limit(4).to_list(4)

    # Latest AI analysis
    latest_analysis = await db.analysis_reports.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )

    # Enriched active applications with predicted admission probability
    apps = await db.applications.find({"user_id": user_id}).limit(5).to_list(5)
    enriched_apps = []
    for app in apps:
        serialized_app = serialize_doc(app)
        uni = await db.universities.find_one({"_id": ObjectId(app["university_id"])})
        if uni:
            serialized_app["university"] = serialize_doc(uni)
            # Fetch from report if available, else run estimation
            report = await db.analysis_reports.find_one({
                "user_id": user_id,
                "university_id": app["university_id"]
            }, sort=[("created_at", -1)])
            if report:
                serialized_app["admission_chance"] = report.get("admission_chance", 70)
            else:
                eval_res = await predict_admission_probability(profile or {}, uni, app.get("program_name"))
                serialized_app["admission_chance"] = eval_res.get("admission_probability", 70)
        enriched_apps.append(serialized_app)

    # Shortlisted upcoming deadlines
    shortlists = await db.shortlists.find({"user_id": user_id}).to_list(50)
    upcoming_deadlines = []
    for item in shortlists:
        uni = await db.universities.find_one({"_id": ObjectId(item["university_id"])})
        if uni and uni.get("deadlines"):
            for intake, date in uni["deadlines"].items():
                upcoming_deadlines.append({
                    "university_name": uni["name"],
                    "country": uni["country"],
                    "intake": intake,
                    "deadline": date,
                    "category": item.get("category", "target")
                })

    # Check subscription
    subscription = await db.subscriptions.find_one({
        "user_id": user_id,
        "status": "active",
        "plan": {"$in": ["premium", "enterprise"]},
    })

    return {
        "stats": {
            "universities_found": universities_count,
            "shortlisted": shortlist_count,
            "applications": applications_count,
            "ai_analyses": analysis_count,
        },
        "recommended_universities": [serialize_doc(u) for u in recommended],
        "roadmap_progress": roadmap.get("progress", 0) if roadmap else 0,
        "profile_completion": profile.get("completion_percentage", 0) if profile else 0,
        "latest_analysis": serialize_doc(latest_analysis) if latest_analysis else None,
        "is_premium": subscription is not None,
        "applications": enriched_apps,
        "upcoming_deadlines": sorted(upcoming_deadlines, key=lambda x: x["deadline"])[:5]
    }
