"""AI university matching and recommendation engine."""

import json
import logging
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text

logger = logging.getLogger(__name__)


async def match_university(profile_data: dict, university_data: dict) -> dict:
    """Evaluate and categorize a university match (Dream, Target, Safe) for a student."""
    system_instruction = (
        "You are an AI Study Abroad Admission Matcher. Your task is to assess how well a student profile matches "
        "a university's standards and return a JSON match score and category classification."
    )

    prompt = f"""
    Compare the student's profile to the target university to determine eligibility.

    Student Profile:
    - GPA: {profile_data.get('gpa', 'Not provided')}
    - Field of Study: {profile_data.get('field_of_study', 'Not provided')}
    - Standardized Tests: {json.dumps(profile_data.get('test_scores', []))}
    - Experience: {json.dumps(profile_data.get('experience', []))}
    - Projects: {json.dumps(profile_data.get('projects', []))}
    - Preferred Budget: {profile_data.get('preferences', {}).get('budget_max', 'Not provided')}

    Target University:
    - Name: {university_data.get('name')}
    - Country: {university_data.get('country')}
    - Ranking: {university_data.get('ranking', 'Not ranked')}
    - Tuition Fees: Min {university_data.get('tuition_min')} to Max {university_data.get('tuition_max')} ({university_data.get('currency', 'USD')})
    - Admission Requirements: {json.dumps(university_data.get('admission_requirements', []))}
    - Programs: {json.dumps(university_data.get('programs', []))}

    Based on this, classify the university into one of:
    - "dream": University is top-tier or student requirements are on the lower limit. Admission is highly competitive.
    - "target": Student meets or exceeds average requirements. Admission is likely.
    - "safe": Student significantly exceeds all requirements. Admission is highly probable.

    Output JSON structure must be exactly:
    {{
        "match_percentage": <int between 0 and 100>,
        "category": "<dream | target | safe>",
        "key_reasons": [<list of strings>]
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to match university with AI: {e}")

        # Basic logical fallback based on university ranking
        ranking = university_data.get("ranking", 500)
        category = "target"
        pct = 75

        if ranking:
            if ranking <= 50:
                category = "dream"
                pct = 60
            elif ranking >= 300:
                category = "safe"
                pct = 90

        return {
            "match_percentage": pct,
            "category": category,
            "key_reasons": [
                f"Categorized as {category} based on academic standards and university global rank #{ranking}."
            ]
        }
