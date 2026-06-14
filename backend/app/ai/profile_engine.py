"""Profile analysis engine."""

import json
import logging
from app.ai.gemini_service import generate_ai

logger = logging.getLogger(__name__)


def clean_json_text(text: str) -> str:
    """Strip markdown code block wrappers from JSON string if present."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


async def analyze_profile(profile_data: dict) -> dict:
    """Analyze the student's profile and generate detailed AI feedback."""
    system_instruction = (
        "You are an expert AI Study Abroad Consultant. Your task is to analyze the student's profile "
        "and return a comprehensive evaluation in valid JSON format only. Do not return any other text."
    )

    prompt = f"""
    Evaluate the following student profile details and generate a JSON response.

    Student Profile:
    - Name: {profile_data.get('first_name', '')} {profile_data.get('last_name', '')}
    - Nationality: {profile_data.get('nationality', 'Not provided')}
    - Academic Level: {profile_data.get('academic_level', 'Not provided')}
    - Field of Study: {profile_data.get('field_of_study', 'Not provided')}
    - GPA: {profile_data.get('gpa', 'Not provided')}
    - Home University: {profile_data.get('university', 'Not provided')}
    - Graduation Year: {profile_data.get('graduation_year', 'Not provided')}
    - Test Scores: {json.dumps(profile_data.get('test_scores', []))}
    - Projects: {json.dumps(profile_data.get('projects', []))}
    - Experience: {json.dumps(profile_data.get('experience', []))}
    - Preferences: {json.dumps(profile_data.get('preferences', {}))}

    Output JSON structure must be exactly:
    {{
        "profile_score": <int between 0 and 100>,
        "strengths": [<list of strings>],
        "weaknesses": [<list of strings>],
        "missing_requirements": [<list of strings>],
        "recommendations": [<list of strings>],
        "improvement_plan": [<list of strings>],
        "detailed_explanation": "<narrative overview explaining the evaluation>"
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to analyze profile with AI: {e}")
        # Standard fallback logic
        gpa = profile_data.get("gpa", "")
        has_tests = len(profile_data.get("test_scores", [])) > 0
        score = 65
        if gpa:
            try:
                if float(gpa) >= 3.5:
                    score += 15
                elif float(gpa) >= 3.0:
                    score += 5
            except ValueError:
                pass
        if has_tests:
            score += 10

        return {
            "profile_score": min(score, 100),
            "strengths": ["Basic profile submitted"] if score > 65 else ["Profile updated"],
            "weaknesses": ["standardized tests not fully updated" if not has_tests else "Needs details"],
            "missing_requirements": ["Standardized tests (IELTS/TOEFL/GRE)"] if not has_tests else [],
            "recommendations": ["Ensure all academic achievements are loaded", "Complete standardized testing"],
            "improvement_plan": ["Attempt/retake IELTS/TOEFL to hit 7.0+", "Add key professional projects"],
            "detailed_explanation": "Profile score is calculated based on standard credentials. Enter test scores to unlock full AI evaluations."
        }
