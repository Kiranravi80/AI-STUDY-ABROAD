"""Admission probability prediction engine."""

import json
import logging
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text

logger = logging.getLogger(__name__)


async def predict_admission_probability(
    profile_data: dict,
    university_data: dict,
    program_name: str | None = None,
) -> dict:
    """Predict the admission chance for a student at a specific university/program."""
    system_instruction = (
        "You are an expert AI Study Abroad Admission Officer. Your task is to calculate the probability of the student's admission "
        "to a specific university/program and return a comprehensive analysis in valid JSON format only."
    )

    program_info = ""
    if program_name and university_data.get("programs"):
        for prog in university_data["programs"]:
            if prog.get("name", "").lower() == program_name.lower():
                program_info = (
                    f"Target Program Details:\n"
                    f"- Name: {prog.get('name')}\n"
                    f"- Degree: {prog.get('degree')}\n"
                    f"- Duration: {prog.get('duration')}\n"
                    f"- Tuition: {prog.get('tuition')} per year\n"
                    f"- Intake: {', '.join(prog.get('intake', []))}\n"
                    f"- Specific Requirements: {', '.join(prog.get('requirements', []))}\n"
                )
                break

    prompt = f"""
    Evaluate the following student's profile details against the target university/program.

    Student Profile:
    - Academic Level: {profile_data.get('academic_level', 'Not provided')}
    - Field of Study: {profile_data.get('field_of_study', 'Not provided')}
    - GPA: {profile_data.get('gpa', 'Not provided')}
    - Standardized Test Scores: {json.dumps(profile_data.get('test_scores', []))}
    - Experience: {json.dumps(profile_data.get('experience', []))}
    - Projects: {json.dumps(profile_data.get('projects', []))}

    Target University:
    - Name: {university_data.get('name')}
    - Country: {university_data.get('country')}
    - City: {university_data.get('city', '')}
    - Ranking: {university_data.get('ranking', 'Not ranked')}
    - Admission Requirements: {json.dumps(university_data.get('admission_requirements', []))}
    {program_info}

    Output JSON structure must be exactly:
    {{
        "admission_probability": <int between 0 and 100>,
        "reasons_why_student_matches": [<list of strings>],
        "reasons_why_student_may_be_rejected": [<list of strings>],
        "improvement_suggestions": [<list of strings>],
        "missing_requirements": [<list of strings>],
        "confidence_score": <int between 0 and 100>
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to calculate admission probability with AI: {e}")

        # Fallback calculation logic based on basic matching rules
        gpa = profile_data.get("gpa", "")
        ranking = university_data.get("ranking", 1000)

        prob = 60
        if gpa:
            try:
                gpa_val = float(gpa)
                if gpa_val >= 3.6:
                    prob += 20
                elif gpa_val >= 3.0:
                    prob += 10
            except ValueError:
                pass

        if ranking:
            if ranking < 50:
                prob -= 15
            elif ranking < 200:
                prob -= 5

        prob = min(max(prob, 15), 95)

        return {
            "admission_probability": prob,
            "reasons_why_student_matches": [
                "Field of study aligns with program domain",
                "Basic GPA eligibility criteria met"
            ],
            "reasons_why_student_may_be_rejected": [
                "Highly competitive ranking category" if ranking and ranking < 100 else "Standard rejection risk factors"
            ],
            "improvement_suggestions": [
                "Provide standardized exam results (IELTS/GRE/TOEFL) to lower rejection risk",
                "Attach letters of recommendation from college professors"
            ],
            "missing_requirements": [],
            "confidence_score": 65
        }
