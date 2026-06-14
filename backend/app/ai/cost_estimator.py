"""AI Study Abroad Cost Estimator."""

import json
import logging
from app.ai.gemini_service import generate_ai
from app.ai.profile_engine import clean_json_text

logger = logging.getLogger(__name__)


async def estimate_study_costs(
    university_data: dict,
    program_name: str | None = None,
    duration_years: int = 2,
) -> dict:
    """Calculate and break down costs for studying abroad using AI."""
    system_instruction = (
        "You are an AI Study Abroad Financial Advisor. Your task is to calculate realistic costs for study abroad "
        "and return a comprehensive breakdown in valid JSON format only."
    )

    tuition_min = university_data.get("tuition_min", 20000) or 20000
    tuition_max = university_data.get("tuition_max", 30000) or 30000
    currency = university_data.get("currency", "USD")

    program_details = ""
    if program_name and university_data.get("programs"):
        for prog in university_data["programs"]:
            if prog.get("name", "").lower() == program_name.lower():
                program_details = f"Target Program: {prog.get('name')}, Tuition fee: {prog.get('tuition')} per year"
                break

    prompt = f"""
    Estimate study abroad expenses at this university.

    University Details:
    - Name: {university_data.get('name')}
    - Country: {university_data.get('country')}
    - City: {university_data.get('city', '')}
    - Living Cost average per year: {university_data.get('living_cost', 12000)}
    - Tuition Fees: Min {tuition_min} to Max {tuition_max} ({currency})
    {program_details}
    - Study Duration: {duration_years} years

    Provide numeric values for:
    1. Tuition (Total for {duration_years} years)
    2. Living Expenses (Total for {duration_years} years, including housing, food, and utilities)
    3. Visa Fees (Standard student visa cost for this country)
    4. Insurance (Health insurance for {duration_years} years)
    5. Flights (International flight tickets estimation)
    6. Application Fees (Standard application portal fees)
    7. Blocked Account (If Germany, calculate blocked account requirement of 11,904 EUR per year. Else, 0)
    8. Emergency Buffer (Emergency reserve funds)
    9. Total (Sum of all calculations)

    Output JSON structure must be exactly:
    {{
        "tuition": <numeric total tuition cost>,
        "living_expenses": <numeric total living cost>,
        "visa": <numeric visa fees>,
        "insurance": <numeric insurance costs>,
        "flights": <numeric flights estimate>,
        "application_fees": <numeric application fees>,
        "blocked_account": <numeric blocked account requirement or 0>,
        "emergency_buffer": <numeric emergency buffer>,
        "total": <numeric total sum>,
        "currency": "<currency code like USD, EUR, GBP, CAD>",
        "report_summary": "<Strategic narrative of blocked accounts, fee structure, and savings strategies>"
    }}
    """

    try:
        raw_response = await generate_ai(prompt, system_instruction, json_mode=True)
        cleaned = clean_json_text(raw_response)
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to calculate cost estimation with AI: {e}")

        # Static fallback estimates
        t_rate = tuition_min if tuition_min is not None else 20000
        t_cost = t_rate * duration_years
        l_rate = university_data.get("living_cost") or 12000
        l_cost = l_rate * duration_years
        v_cost = 500
        i_cost = 1500 * duration_years
        f_cost = 1200
        a_cost = 150
        bl_cost = 11904 * duration_years if university_data.get("country", "").lower() == "germany" else 0
        buf_cost = 2000

        tot = t_cost + l_cost + v_cost + i_cost + f_cost + a_cost + bl_cost + buf_cost

        return {
            "tuition": t_cost,
            "living_expenses": l_cost,
            "visa": v_cost,
            "insurance": i_cost,
            "flights": f_cost,
            "application_fees": a_cost,
            "blocked_account": bl_cost,
            "emergency_buffer": buf_cost,
            "total": tot,
            "currency": currency,
            "report_summary": "Financial estimation generated based on standard tuition rates and average living costs."
        }
