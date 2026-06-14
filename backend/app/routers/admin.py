"""Admin management routes."""

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.database import get_database
from app.schemas.common import EmployeeCreate, EmployeeUpdate, SubscriptionCreate
from app.middleware.auth import require_admin
from app.utils.security import hash_password
from app.utils.helpers import serialize_doc, utc_now

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def admin_dashboard(user: dict = Depends(require_admin)):
    db = get_database()
    total_students = await db.users.count_documents({"role": "student"})
    total_employees = await db.users.count_documents({"role": "employee"})
    total_universities = await db.universities.count_documents({})
    total_applications = await db.applications.count_documents({})
    total_searches = await db.universities.count_documents({})  # Placeholder metric
    premium_users = await db.subscriptions.count_documents({"plan": {"$in": ["premium", "enterprise"]}, "status": "active"})
    ai_usage = await db.analysis_reports.count_documents({})

    # Revenue from subscriptions
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    revenue_result = await db.subscriptions.aggregate(pipeline).to_list(1)
    revenue = revenue_result[0]["total"] if revenue_result else 0

    # Scrapers logs
    latest_logs = await db.scraper_logs.find({}).sort("created_at", -1).limit(5).to_list(5)
    
    # System Health
    system_health = {
        "database": "connected",
        "api_latency": "12ms",
        "scraper_service": "active"
    }

    return {
        "total_students": total_students,
        "total_employees": total_employees,
        "total_universities": total_universities,
        "total_applications": total_applications,
        "total_searches": total_searches,
        "premium_users": premium_users,
        "revenue": revenue,
        "ai_usage": ai_usage,
        "latest_logs": [serialize_doc(l) for l in latest_logs],
        "system_health": system_health
    }


@router.post("/scrapers/run")
async def trigger_scrapers(user: dict = Depends(require_admin)):
    from scrapers.scheduler import run_all_scrapers
    db = get_database()
    results = await run_all_scrapers(db)
    return results


@router.get("/scrapers/logs")
async def get_scraper_logs(user: dict = Depends(require_admin)):
    db = get_database()
    logs = await db.scraper_logs.find({}).sort("created_at", -1).limit(50).to_list(50)
    return {"items": [serialize_doc(l) for l in logs]}


@router.get("/scrapers/updates")
async def get_course_updates(user: dict = Depends(require_admin)):
    db = get_database()
    updates = await db.course_updates.find({}).sort("updated_at", -1).limit(50).to_list(50)
    return {"items": [serialize_doc(u) for u in updates]}


@router.get("/students")
async def list_students(user: dict = Depends(require_admin)):
    db = get_database()
    students = await db.users.find({"role": "student"}).sort("created_at", -1).to_list(500)
    enriched = []
    for s in students:
        serialized = serialize_doc(s)
        serialized.pop("password", None)
        profile = await db.profiles.find_one({"user_id": serialized["id"]})
        serialized["profile"] = serialize_doc(profile)
        serialized["applications_count"] = await db.applications.count_documents({"user_id": serialized["id"]})
        enriched.append(serialized)
    return {"items": enriched, "total": len(enriched)}


@router.put("/students/{student_id}/deactivate")
async def deactivate_student(student_id: str, user: dict = Depends(require_admin)):
    db = get_database()
    result = await db.users.update_one(
        {"_id": ObjectId(student_id), "role": "student"},
        {"$set": {"is_active": False, "updated_at": utc_now().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deactivated"}


@router.get("/employees")
async def list_employees(user: dict = Depends(require_admin)):
    db = get_database()
    employees = await db.users.find({"role": "employee"}).to_list(200)
    enriched = []
    for e in employees:
        serialized = serialize_doc(e)
        serialized.pop("password", None)
        emp_data = await db.employees.find_one({"user_id": serialized["id"]})
        serialized["employee_data"] = serialize_doc(emp_data)
        enriched.append(serialized)
    return {"items": enriched, "total": len(enriched)}


@router.post("/employees", status_code=201)
async def create_employee(data: EmployeeCreate, user: dict = Depends(require_admin)):
    """Admin creates employee accounts - employees cannot self-register."""
    db = get_database()

    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    user_doc = {
        "email": data.email.lower(),
        "password": hash_password(data.password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": "employee",
        "is_active": True,
        "created_at": utc_now().isoformat(),
    }
    result = await db.users.insert_one(user_doc)

    emp_doc = {
        "user_id": str(result.inserted_id),
        "department": data.department,
        "assigned_students": data.assigned_students,
        "created_at": utc_now().isoformat(),
    }
    await db.employees.insert_one(emp_doc)

    user_doc["_id"] = result.inserted_id
    serialized = serialize_doc(user_doc)
    serialized.pop("password", None)
    return serialized


@router.put("/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    data: EmployeeUpdate,
    user: dict = Depends(require_admin),
):
    db = get_database()
    emp_user = await db.users.find_one({"_id": ObjectId(employee_id), "role": "employee"})
    if not emp_user:
        raise HTTPException(status_code=404, detail="Employee not found")

    user_update = {}
    if data.first_name:
        user_update["first_name"] = data.first_name
    if data.last_name:
        user_update["last_name"] = data.last_name
    if data.is_active is not None:
        user_update["is_active"] = data.is_active

    if user_update:
        await db.users.update_one({"_id": ObjectId(employee_id)}, {"$set": user_update})

    emp_update = {}
    if data.department:
        emp_update["department"] = data.department
    if data.assigned_students is not None:
        emp_update["assigned_students"] = data.assigned_students

    if emp_update:
        await db.employees.update_one({"user_id": employee_id}, {"$set": emp_update})

    return {"message": "Employee updated"}


@router.post("/employees/{employee_id}/reset-password")
async def reset_employee_password(employee_id: str, user: dict = Depends(require_admin)):
    db = get_database()
    new_password = "TempPass123!"
    result = await db.users.update_one(
        {"_id": ObjectId(employee_id), "role": "employee"},
        {"$set": {"password": hash_password(new_password)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Password reset", "temporary_password": new_password}


@router.get("/analytics")
async def get_analytics(user: dict = Depends(require_admin)):
    db = get_database()

    # Monthly signups (last 6 months placeholder)
    students_by_month = []
    for i in range(6):
        students_by_month.append({"month": f"Month {i+1}", "count": await db.users.count_documents({"role": "student"}) // 6})

    return {
        "students_by_month": students_by_month,
        "application_statuses": {
            "applied": await db.applications.count_documents({"status": "applied"}),
            "under_review": await db.applications.count_documents({"status": "under_review"}),
            "offer_received": await db.applications.count_documents({"status": "offer_received"}),
            "rejected": await db.applications.count_documents({"status": "rejected"}),
            "visa_stage": await db.applications.count_documents({"status": "visa_stage"}),
        },
        "top_countries": [],
    }


@router.get("/subscriptions")
async def list_subscriptions(user: dict = Depends(require_admin)):
    db = get_database()
    subs = await db.subscriptions.find({}).sort("created_at", -1).to_list(200)
    return {"items": [serialize_doc(s) for s in subs], "total": len(subs)}


@router.post("/subscriptions", status_code=201)
async def create_subscription(data: SubscriptionCreate, user: dict = Depends(require_admin)):
    db = get_database()
    doc = {
        "user_id": data.user_id,
        "plan": data.plan,
        "amount": data.amount,
        "currency": data.currency,
        "status": "active",
        "created_at": utc_now().isoformat(),
    }
    result = await db.subscriptions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)
