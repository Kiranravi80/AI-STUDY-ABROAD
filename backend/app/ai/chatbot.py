"""AI Study Abroad Chatbot assistant module."""

import logging
from app.ai.gemini_service import generate_ai

logger = logging.getLogger(__name__)


async def generate_chatbot_response(
    prompt: str,
    history: list[dict],
    student_profile: dict | None = None,
) -> str:
    """Generate a conversational response for the student chatbot assistant."""
    system_instruction = (
        "You are 'AiVentra Assistant', a highly knowledgeable, professional, and friendly study abroad advisor. "
        "You help students with: University selection, Admission eligibility, Course requirements, Roadmap timelines, "
        "Visa applications (financial proof, interviews), Cost estimations, and general Profile improvement advice. "
        "Keep responses structured, engaging, and clear. Use bullet points and bold formatting for key details."
    )

    if student_profile:
        system_instruction += (
            f"\n\nThe student you are helping has the following profile context:\n"
            f"- GPA: {student_profile.get('gpa', 'Not provided')}\n"
            f"- Academic Level: {student_profile.get('academic_level', 'Not provided')}\n"
            f"- Field of Study: {student_profile.get('field_of_study', 'Not provided')}\n"
            f"- Home University: {student_profile.get('university', 'Not provided')}\n"
            f"- Preferred Countries: {', '.join(student_profile.get('preferences', {}).get('preferred_countries', [])) or 'Not provided'}\n"
            "Use this profile information when advising them, making suggestions contextually relevant."
        )

    # Format conversation history
    context_prompt = ""
    # Only send last 10 messages to avoid large context overheads
    for msg in history[-10:]:
        role = "Student" if msg.get("role") == "user" else "Assistant"
        context_prompt += f"{role}: {msg.get('content')}\n"

    context_prompt += f"Student: {prompt}\nAssistant:"

    try:
        response_text = await generate_ai(context_prompt, system_instruction, json_mode=False)
        return response_text
    except Exception as e:
        logger.error(f"Chatbot query failed: {e}")
        return (
            "I apologize, I am experiencing temporary connectivity problems with the AI service. "
            "Please try again or let me know if you would like me to connect you with a student counselor."
        )
