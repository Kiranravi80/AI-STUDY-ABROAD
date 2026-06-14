"""Personalized roadmap generation engine."""

import json
import logging
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text

logger = logging.getLogger(__name__)


async def generate_personalized_roadmap(
    profile_data: dict,
    target_country: str,
    target_intake: str,
    target_course: str,
) -> dict:
    """Generate a step-by-step month-by-month study abroad roadmap."""
    system_instruction = (
        "You are an expert AI Study Abroad Advisor. Your task is to generate a comprehensive, highly personalized month-by-month study abroad roadmap "
        "for a student and return it in valid JSON format only."
    )

    prompt = f"""
    Create a personalized month-by-month study abroad timeline using the student's profile and preferences.

    Student Profile:
    - GPA: {profile_data.get('gpa', 'Not provided')}
    - Field of Study: {profile_data.get('field_of_study', 'Not provided')}
    - Existing Test Scores: {json.dumps(profile_data.get('test_scores', []))}
    - Experience: {json.dumps(profile_data.get('experience', []))}

    Target Plan:
    - Destination Country: {target_country}
    - Intake / Term: {target_intake}
    - Targeted Course: {target_course}

    Generate a monthly plan leading up to the intake. Include specific milestones for:
    - Language / standardized exams (IELTS, TOEFL, GRE)
    - APS Certificate (Mandatory for Germany)
    - SOP writing and LOR collection
    - Application submission deadlines
    - Visa applications (Blocked accounts, insurance, appointments)
    - Accommodation search and Flight bookings

    Output JSON structure must be exactly:
    {{
        "timeline": [
            {{
                "month": "<Month and Year, e.g. July 2026>",
                "focus": "<Core focus of this month>",
                "tasks": [
                    {{
                        "id": "<unique snake_case task id>",
                        "title": "<Task title>",
                        "description": "<Detailed instructions for this step>",
                        "required_by": "<Milestone deadline date>"
                    }}
                ]
            }}
        ],
        "overall_summary": "<Strategic summary of application journey>"
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to generate roadmap with AI: {e}")

        # Static fallback timeline
        return {
            "timeline": [
                {
                    "month": "Months 1-2 (Preparation Phase)",
                    "focus": "Standardized Testing and Academic Verification",
                    "tasks": [
                        {
                            "id": "ielts_toefl_prep",
                            "title": "Language Exam Preparation",
                            "description": "Start practicing IELTS/TOEFL modules. Focus on target band of 7.0+.",
                            "required_by": "End of Month 2"
                        },
                        {
                            "id": "aps_certificate",
                            "title": "APS Certificate Submission",
                            "description": "If applying to Germany, submit school and degree transcripts for APS evaluation immediately.",
                            "required_by": "End of Month 2"
                        }
                    ]
                },
                {
                    "month": "Months 3-4 (Application Phase)",
                    "focus": "Drafting Essays and Submitting Applications",
                    "tasks": [
                        {
                            "id": "sop_lor_drafting",
                            "title": "Statement of Purpose (SOP) & LORs",
                            "description": "Write a strong Statement of Purpose highlighting projects. Request 2 LORs from professors.",
                            "required_by": "End of Month 3"
                        },
                        {
                            "id": "application_submission",
                            "title": "Submit University Applications",
                            "description": "Verify program deadlines and submit online applications through uni-assist or portals.",
                            "required_by": "End of Month 4"
                        }
                    ]
                },
                {
                    "month": "Months 5-6 (Visa & Departure)",
                    "focus": "Financial Setup, Visa processing, and logistics",
                    "tasks": [
                        {
                            "id": "visa_application",
                            "title": "Student Visa Appointment",
                            "description": "Setup blocked account or sponsor proof. Purchase travel insurance and file visa case.",
                            "required_by": "Intake - 2 Months"
                        },
                        {
                            "id": "flights_accommodation",
                            "title": "Accommodation & Flight Bookings",
                            "description": "Look for dorms or shared apartments. Book flight ticket to match intake orientation.",
                            "required_by": "Intake - 1 Month"
                        }
                    ]
                }
            ],
            "overall_summary": "Standard application roadmap leading to study abroad destination. Complete test requirements early to avoid delays."
        }
