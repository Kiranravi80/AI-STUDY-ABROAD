"""Document center routes."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from bson import ObjectId
import base64

from app.database import get_database
from app.middleware.auth import require_student, require_employee_or_admin
from app.utils.helpers import serialize_doc, utc_now

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_TYPES = {"pdf", "docx", "doc", "png", "jpg", "jpeg", "gif", "webp"}


async def ensure_employee_can_access_student(db, student_id: str, user: dict) -> None:
    """Allow admins globally, but keep employees scoped to assigned students."""
    if user.get("role") == "admin":
        return

    employee = await db.employees.find_one({"user_id": user["id"]})
    assigned_ids = employee.get("assigned_students", []) if employee else []
    if student_id not in assigned_ids:
        raise HTTPException(status_code=403, detail="Student not assigned to you")


@router.get("")
async def get_documents(user: dict = Depends(require_student)):
    db = get_database()
    docs = await db.documents.find({"user_id": user["id"]}).sort("created_at", -1).to_list(100)
    return {"items": [serialize_doc(d) for d in docs], "total": len(docs)}


@router.post("/upload", status_code=201)
async def upload_document(
    name: str = Form(...),
    category: str = Form("general"),
    file: UploadFile = File(...),
    user: dict = Depends(require_student),
):
    """Upload a document. Stores as base64 in MongoDB (use cloud storage in production)."""
    db = get_database()

    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_TYPES)}",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 10MB")

    doc = {
        "user_id": user["id"],
        "name": name,
        "file_name": file.filename,
        "file_type": ext,
        "category": category,
        "file_data": base64.b64encode(content).decode("utf-8"),
        "size_bytes": len(content),
        "verified": False,
        "created_at": utc_now().isoformat(),
    }
    result = await db.documents.insert_one(doc)
    doc["_id"] = result.inserted_id
    serialized = serialize_doc(doc)
    serialized.pop("file_data", None)  # Don't return file data in list
    return serialized


@router.get("/student/{student_id}")
async def get_student_documents(student_id: str, user: dict = Depends(require_employee_or_admin)):
    db = get_database()
    await ensure_employee_can_access_student(db, student_id, user)

    docs = await db.documents.find({"user_id": student_id}).sort("created_at", -1).to_list(100)
    items = [serialize_doc(d) for d in docs]
    for item in items:
        item.pop("file_data", None)
    return {"items": items, "total": len(items)}


@router.get("/{document_id}")
async def get_document(document_id: str, user: dict = Depends(require_student)):
    db = get_database()
    doc = await db.documents.find_one({
        "_id": ObjectId(document_id),
        "user_id": user["id"],
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return serialize_doc(doc)


@router.delete("/{document_id}")
async def delete_document(document_id: str, user: dict = Depends(require_student)):
    db = get_database()
    result = await db.documents.delete_one({
        "_id": ObjectId(document_id),
        "user_id": user["id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}


@router.put("/{document_id}/verify")
async def verify_document(document_id: str, user: dict = Depends(require_employee_or_admin)):
    """Employee verifies a student document."""
    db = get_database()
    doc = await db.documents.find_one({"_id": ObjectId(document_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await ensure_employee_can_access_student(db, doc["user_id"], user)

    result = await db.documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"verified": True, "verified_by": user["id"], "verified_at": utc_now().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document verified"}
