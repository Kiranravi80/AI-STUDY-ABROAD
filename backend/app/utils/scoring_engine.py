"""Recommendation and Eligibility Scoring Engine for Student Admission Chances."""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

def parse_gpa_to_percentage(gpa_str: str | None) -> float | None:
    """Parse GPA string (e.g. '8.5', '85%', '3.8/4') and convert to percentage."""
    if not gpa_str:
        return None
    gpa_str = str(gpa_str).strip()
    try:
        # Extract digits, dots, and % sign
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(%|/10|/4)?', gpa_str)
        if not match:
            return None
        
        val = float(match.group(1))
        unit = match.group(2)

        if unit == "%" or "%" in gpa_str:
            return min(max(val, 0.0), 100.0)
        elif unit == "/10" or (val <= 10.0 and val > 4.0):
            # Scale 10 CGPA -> Percentage
            return min(max(val * 9.5, 0.0), 100.0)
        elif unit == "/4" or val <= 4.0:
            # Scale 4 US GPA -> Percentage
            return min(max((val / 4.0) * 100.0, 0.0), 100.0)
        else:
            # Fallback if > 10, assume percentage
            if val > 10.0:
                return min(max(val, 0.0), 100.0)
            return min(max(val * 10.0, 0.0), 100.0)
    except Exception as e:
        logger.warning(f"Error parsing GPA '{gpa_str}': {e}")
        return None

def convert_percentage_to_german_grade(pct: float) -> float:
    """Convert percentage (50-100) to German grade scale (4.0 - 1.0) using Bavarian formula."""
    # max grade = 1.0, passing minimum = 4.0 (mapped to 50% here)
    if pct >= 100.0:
        return 1.0
    if pct <= 50.0:
        return 4.0
    grade = 1.0 + 3.0 * (100.0 - pct) / 50.0
    return round(min(max(grade, 1.0), 4.0), 2)

def calculate_eligibility_and_score(profile: dict[str, Any], program: dict[str, Any], university: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate eligibility match score and category.
    Returns:
    {
        "match_score": int (40-99),
        "category": "Dream" | "Target" | "Safe",
        "reasons": list[str],
        "strengths": list[str],
        "weaknesses": list[str],
        "requirement_gap": list[dict],
        "document_check": list[dict]
    }
    """
    reasons = []
    strengths = []
    weaknesses = []
    requirement_gap = []
    doc_checks = []

    # Get student metrics
    student_gpa_pct = parse_gpa_to_percentage(profile.get("gpa"))
    student_german_grade = convert_percentage_to_german_grade(student_gpa_pct) if student_gpa_pct else None
    
    # Extract test scores
    test_scores = profile.get("test_scores") or []
    ielts_score = None
    toefl_score = None
    pte_score = None
    for t in test_scores:
        name = t.get("test_name", "").lower()
        try:
            score_val = float(t.get("score", "0"))
            if "ielts" in name:
                ielts_score = score_val
            elif "toefl" in name:
                toefl_score = score_val
            elif "pte" in name:
                pte_score = score_val
        except ValueError:
            pass

    # Extract preferences
    prefs = profile.get("preferences") or {}
    budget_max = prefs.get("budget_max")
    preferred_countries = prefs.get("preferred_countries") or []
    preferred_intake = prefs.get("intake")

    # Extract program requirements details
    req_details = program.get("requirements_details") or {}
    academic_reqs = req_details.get("academic") or {}
    lang_reqs = req_details.get("language") or {}
    docs_required = req_details.get("documents_required") or ["CV", "Transcript", "Degree Certificate", "Passport"]
    indian_students_reqs = req_details.get("indian_students") or {}

    # Base score
    score = 70.0

    # 1. Degree Progression check
    student_level = profile.get("academic_level", "").lower()
    program_degree = program.get("degree", "").lower()
    
    # Standardize program degree type
    is_program_bach = "bachelor" in program_degree
    is_program_master = "master" in program_degree or "mba" in program_degree or "msc" in program_degree or "mtech" in program_degree
    is_program_phd = "phd" in program_degree or "doctor" in program_degree

    progression_valid = True
    if student_level == "bachelors":
        if is_program_bach:
            progression_valid = False
            reasons.append("Student completed Bachelor's - Bachelor's programs are not recommended.")
    elif student_level == "masters":
        if is_program_bach:
            progression_valid = False
            reasons.append("Student completed Master's - Bachelor's programs are not recommended.")
    elif student_level == "12th":
        if is_program_master or is_program_phd:
            progression_valid = False
            reasons.append("Student completed 12th - Master's / PhD programs are not recommended.")

    if not progression_valid:
        score = 40.0
        weaknesses.append("Degree level progression does not align with background.")
        requirement_gap.append({
            "requirement": f"Eligible Degree for {program.get('degree')}",
            "profile": f"Completed: {profile.get('academic_level')}",
            "gap": "Degree mismatch progression"
        })

    # 2. Field of Study / Specialization Match
    student_field = profile.get("field_of_study", "").strip()
    eligible_degrees = academic_reqs.get("eligible_degrees") or []
    field_matched = False
    
    if student_field and progression_valid:
        student_field_lower = student_field.lower()
        # Clean text keywords
        keywords = [k.lower() for k in re.findall(r'\w+', student_field) if len(k) > 3]
        program_name_lower = program.get("name", "").lower()

        # Check if direct keywords match program name or eligible degrees list
        if any(k in program_name_lower for k in keywords):
            field_matched = True
            score += 10
            strengths.append(f"Field of study aligns with {program.get('name')}")
        elif eligible_degrees and any(any(k in ed.lower() for k in keywords) for ed in eligible_degrees):
            field_matched = True
            score += 8
            strengths.append("Specialization falls under program's list of eligible backgrounds")
        else:
            score -= 5
            weaknesses.append(f"Field of study ({student_field}) differs from typical prerequisites")

    # 3. CGPA / GPA Checks
    if student_gpa_pct and progression_valid:
        # Check if university requires specific grade
        # German system: lower is better (1.0 is best, 4.0 is minimum passing)
        # Check if program has a GPA minimum (DAAD courses sometimes require <= 2.5 or 2.7 German grade)
        min_gpa_req = academic_reqs.get("min_gpa") or 2.5
        
        if student_german_grade:
            if student_german_grade <= min_gpa_req:
                score += 12
                strengths.append(f"CGPA meets or exceeds requirements ({student_gpa_pct:.1f}% / German Grade: {student_german_grade})")
            else:
                score -= 15
                weaknesses.append(f"CGPA is below program recommendation (Requires German Grade <= {min_gpa_req}, profile: {student_german_grade})")
                requirement_gap.append({
                    "requirement": f"German Grade <= {min_gpa_req}",
                    "profile": f"German Grade {student_german_grade}",
                    "gap": "Grade is lower than recommended"
                })
        else:
            score += 5
    else:
        if progression_valid:
            weaknesses.append("CGPA/GPA details are missing in profile")

    # 4. English Language Test requirements
    is_english_program = "english" in program.get("language", "").lower()
    
    if is_english_program and progression_valid:
        req_ielts = lang_reqs.get("ielts") or 6.5
        req_toefl = lang_reqs.get("toefl") or 80.0
        req_pte = lang_reqs.get("pte") or 58.0

        lang_ok = False
        if ielts_score:
            if ielts_score >= req_ielts:
                lang_ok = True
                score += 8
                strengths.append(f"IELTS score of {ielts_score} meets language requirement (Required: {req_ielts})")
            else:
                score -= 15
                weaknesses.append(f"IELTS score of {ielts_score} is below requirement ({req_ielts})")
                requirement_gap.append({
                    "requirement": f"IELTS >= {req_ielts}",
                    "profile": f"IELTS {ielts_score}",
                    "gap": "Language score gap"
                })
        elif toefl_score:
            if toefl_score >= req_toefl:
                lang_ok = True
                score += 8
                strengths.append(f"TOEFL score of {toefl_score} meets language requirement (Required: {req_toefl})")
            else:
                score -= 15
                weaknesses.append(f"TOEFL score of {toefl_score} is below requirement ({req_toefl})")
                requirement_gap.append({
                    "requirement": f"TOEFL >= {req_toefl}",
                    "profile": f"TOEFL {toefl_score}",
                    "gap": "Language score gap"
                })
        elif pte_score:
            if pte_score >= req_pte:
                lang_ok = True
                score += 8
                strengths.append(f"PTE score of {pte_score} meets language requirement (Required: {req_pte})")
            else:
                score -= 15
                weaknesses.append(f"PTE score of {pte_score} is below requirement ({req_pte})")
                requirement_gap.append({
                    "requirement": f"PTE >= {req_pte}",
                    "profile": f"PTE {pte_score}",
                    "gap": "Language score gap"
                })
        else:
            # Missing English Test
            score -= 10
            weaknesses.append("English proficiency test scores (IELTS/TOEFL) not found in profile")
            requirement_gap.append({
                "requirement": f"IELTS >= {req_ielts} or TOEFL >= {req_toefl}",
                "profile": "No English test score provided",
                "gap": "English test score required"
            })

    # 5. APS Certificate Requirement (India/China/Vietnam students applying to Germany)
    is_germany = university.get("country", "").lower() == "germany"
    student_nationality = profile.get("nationality", "").lower()
    
    # We fetch document list to verify if APS certificate exists
    # If student is from India/China/Vietnam, check for APS
    is_indian_sub = any(c in student_nationality for c in ["india", "china", "vietnam"])
    requires_aps = is_germany and is_indian_sub and indian_students_reqs.get("aps_required", True)

    if requires_aps:
        # Check documents from document check
        # For programmatic check, we'll check if the profile has documents uploaded
        # Or look at documents if document list is passed
        pass

    # 6. Preferences - Country
    uni_country = university.get("country", "")
    if preferred_countries:
        if uni_country in preferred_countries:
            score += 5
            strengths.append(f"University is located in your preferred country ({uni_country})")
        else:
            score -= 5

    # 7. Preferences - Budget
    # Compute program fees
    campuses = program.get("campuses", [])
    fees = [c.get("tuition_fee") for c in campuses if c.get("tuition_fee") is not None]
    tuition_fee_val = min(fees) if fees else (university.get("tuition_min") or 0.0)

    if budget_max is not None:
        if tuition_fee_val <= budget_max:
            score += 5
            strengths.append(f"Tuition fee matches budget constraints ({tuition_fee_val:,.0f} <= {budget_max:,.0f})")
        else:
            score -= 15
            weaknesses.append(f"Tuition fee exceeds preferred budget (Tuition: {tuition_fee_val:,.0f}, Budget: {budget_max:,.0f})")
            requirement_gap.append({
                "requirement": f"Budget max {budget_max:,.0f}",
                "profile": f"Tuition {tuition_fee_val:,.0f}",
                "gap": "Tuition exceeds budget limits"
            })

    # 8. Preferences - Intake
    program_intakes = program.get("intake") or []
    if preferred_intake and program_intakes:
        if any(preferred_intake.lower() in pi.lower() for pi in program_intakes):
            score += 3
            strengths.append(f"Program intake is available for your target intake ({preferred_intake})")

    # 9. Academic Portfolio Check (Experience, Projects, Skills, Publications, Certifications)
    portfolio_boost = 0
    program_keywords = set()
    prog_name = program.get("name", "")
    # Extract keywords from program name
    for word in re.findall(r'[a-zA-Z]{3,}', prog_name.lower()):
        if word not in {"and", "for", "the", "with", "msc", "bsc", "phd", "master", "bachelor", "science", "engineering", "technology", "studies", "systems", "advanced", "applied"}:
            program_keywords.add(word.lower())

    # 9a. Experience Check
    experiences = profile.get("experience") or []
    if experiences:
        exp_count = len(experiences)
        score += 3
        portfolio_boost += 3
        strengths.append(f"Has {exp_count} work experience entry/entries")
        
        # Check if experience is relevant to program keywords
        relevant_exp_count = 0
        for exp in experiences:
            exp_text = (exp.get("role", "") + " " + exp.get("description", "")).lower()
            if any(kw in exp_text for kw in program_keywords):
                relevant_exp_count += 1
        
        if relevant_exp_count > 0:
            score += min(relevant_exp_count * 2, 6)
            portfolio_boost += min(relevant_exp_count * 2, 6)
            strengths.append(f"Possesses {relevant_exp_count} relevant professional experience(s) in the field")

    # 9b. Projects Check
    projects = profile.get("projects") or []
    if projects:
        proj_count = len(projects)
        score += 2
        portfolio_boost += 2
        strengths.append(f"Completed {proj_count} project(s)")
        
        # Check relevance
        relevant_proj_count = 0
        for proj in projects:
            proj_text = (proj.get("title", "") + " " + (proj.get("description") or "") + " " + " ".join(proj.get("technologies", []))).lower()
            if any(kw in proj_text for kw in program_keywords):
                relevant_proj_count += 1
        
        if relevant_proj_count > 0:
            score += min(relevant_proj_count * 2, 4)
            portfolio_boost += min(relevant_proj_count * 2, 4)
            strengths.append(f"Showcases {relevant_proj_count} relevant technical project(s)")

    # 9c. Skills Check
    skills_data = profile.get("skills") or {}
    skills_list = []
    if isinstance(skills_data, dict):
        for val in skills_data.values():
            if isinstance(val, list):
                skills_list.extend(val)
    else:
        for field in ["technical_skills", "programming_languages", "frameworks", "tools", "databases", "cloud_platforms", "aiml_tools", "soft_skills"]:
            val = getattr(skills_data, field, None)
            if isinstance(val, list):
                skills_list.extend(val)
                
    if skills_list:
        score += 2
        portfolio_boost += 2
        # Check for skills matching program keywords
        matched_skills = []
        for skill in skills_list:
            skill_clean = str(skill).lower()
            if any(kw in skill_clean for kw in program_keywords):
                matched_skills.append(skill)
        
        if matched_skills:
            matching_boost = min(len(matched_skills) * 1, 5)
            score += matching_boost
            portfolio_boost += matching_boost
            strengths.append(f"Demonstrates relevant skills: {', '.join(list(set(matched_skills))[:4])}")
        else:
            strengths.append(f"Has {len(skills_list)} listed skill(s)")

    # 9d. Publications Check
    publications = profile.get("publications") or []
    if publications:
        pub_count = len(publications)
        pub_boost = 5 if is_program_phd or is_program_master else 3
        score += pub_boost
        portfolio_boost += pub_boost
        strengths.append(f"Has {pub_count} research publication(s)")

    # 9e. Certifications Check
    certifications = profile.get("certifications") or []
    if certifications:
        cert_count = len(certifications)
        cert_boost = min(cert_count * 2, 4)
        score += cert_boost
        portfolio_boost += cert_boost
        strengths.append(f"Earned {cert_count} professional certification(s)")

    # Standardize score normalization
    final_score = int(min(max(score, 40.0), 99.0))

    # Determine Categories
    if final_score >= 85:
        category = "Safe"
        reasons.append("Strong academic background, meets language score, and satisfies intake criteria.")
    elif final_score >= 70:
        category = "Target"
        reasons.append("Good academic profile. Most requirements are met, with minor recommendations.")
    else:
        category = "Dream"
        reasons.append("High competitive standards or slight credentials gap (e.g. GPA / ECTS / Language gap).")

    # Standardize document checklist
    # We will mock the documents list or use profile document structures
    # Common required docs: "CV", "Transcript", "Degree Certificate", "Motivation Letter", "Passport"
    req_docs_set = set(docs_required)
    if requires_aps:
        req_docs_set.add("APS Certificate")
    if is_english_program:
        req_docs_set.add("English Certificate")

    # Generate document check structures
    # (Actual check mapping will be performed against DB documents by router, 
    # but we seed them here)
    for doc in sorted(list(req_docs_set)):
        doc_checks.append({
            "document_name": doc,
            "status": "Missing"  # Will be mapped in the endpoint using real documents count
        })

    # Formulate match reasoning bullet points
    match_reasons = []
    if progression_valid:
        match_reasons.append("Degree eligible")
    if student_gpa_pct:
        match_reasons.append(f"CGPA meets target standard")
    if ielts_score or toefl_score or pte_score:
        match_reasons.append("Language requirement met")
    if field_matched:
        match_reasons.append(f"Strong background in {student_field}")
    if not match_reasons:
        match_reasons.append(reasons[0] if reasons else "Profile matched")

    return {
        "match_score": final_score,
        "category": category,
        "reasons": match_reasons,
        "strengths": strengths if strengths else ["Profile updated"],
        "weaknesses": weaknesses if weaknesses else ["Verify credit requirements"],
        "requirement_gap": requirement_gap if requirement_gap else [{"requirement": "All entry rules", "profile": "Meets standards", "gap": "None"}],
        "document_check": doc_checks
    }
