"""API endpoints for the AI Chatbot assistant."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import get_database
from app.middleware.auth import require_student
from app.utils.helpers import serialize_docs, utc_now
from app.ai.chatbot import generate_chatbot_response

router = APIRouter(prefix="/chatbot", tags=["AI Chatbot"])


class MessageRequest(BaseModel):
    message: str


@router.get("/history")
async def get_chat_history(user: dict = Depends(require_student)):
    """Fetch user's chatbot message history."""
    db = get_database()
    history = await db.chat_history.find(
        {"user_id": user["id"]}
    ).sort("created_at", 1).to_list(100)

    return {"items": serialize_docs(history), "total": len(history)}


@router.post("/message")
async def send_chat_message(
    data: MessageRequest,
    user: dict = Depends(require_student),
):
    """Post a new chat message and retrieve AI response."""
    db = get_database()

    # Get student profile for contextual response tailoring
    profile = await db.profiles.find_one({"user_id": user["id"]}) or {}

    # Get chat history for conversational context
    history_cursor = db.chat_history.find(
        {"user_id": user["id"]}
    ).sort("created_at", 1).limit(15)
    raw_history = await history_cursor.to_list(15)

    history = [
        {"role": msg.get("role"), "content": msg.get("content")}
        for msg in raw_history
    ]
    
    # Generate reply
    print("USER")
    print(user)

    print("PROFILE")
    print(profile)
    reply = await generate_chatbot_response(data.message, history, profile)

    # Save both messages to the database
    now = utc_now().isoformat()
    user_message = {
        "user_id": user["id"],
        "role": "user",
        "content": data.message,
        "created_at": now,
    }
    assistant_message = {
        "user_id": user["id"],
        "role": "assistant",
        "content": reply,
        "created_at": now,
    }

    await db.chat_history.insert_many([user_message, assistant_message])

    return {
        "reply": reply,
        "history": [user_message, assistant_message],
    }
