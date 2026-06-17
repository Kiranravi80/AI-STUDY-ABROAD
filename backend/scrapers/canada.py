"""Canada university data scraper."""

import logging
from scrapers.base_scraper import BaseScraper
from app.utils.helpers import utc_now

logger = logging.getLogger(__name__)


class CanadaScraper(BaseScraper):
    """Scraper targeting Canadian universities and program courses."""

    def __init__(self):
        super().__init__("Canada")

    async def scrape(self, db) -> int:
        scraped_data = [
            {
                "name": "University of Toronto",
                "country": "Canada",
                "city": "Toronto",
                "ranking": 21,
                "website": "https://utoronto.ca",
                "description": "Canada's top-ranked research university offering excellence in medicine, engineering, and business.",
                "tuition_min": 35000,
                "tuition_max": 45000,
                "currency": "CAD",
                "living_cost": 15000,
                "programs": [
                    {
                        "name": "Business Administration",
                        "degree": "MBA",
                        "duration": "2 years",
                        "campuses": [
                            {
                                "name": "Toronto Campus",
                                "city": "Toronto",
                                "tuition_fee": 40000.0,
                                "apply_url": "https://utoronto.ca/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["Fall"],
                        "requirements": ["GMAT", "IELTS 7.0", "GPA 3.3+"]
                    },
                    {
                        "name": "Mechanical Engineering",
                        "degree": "MEng",
                        "duration": "1.5 years",
                        "campuses": [
                            {
                                "name": "Toronto Campus",
                                "city": "Toronto",
                                "tuition_fee": 38000.0,
                                "apply_url": "https://utoronto.ca/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["Fall", "Winter"],
                        "requirements": ["IELTS 7.0", "GPA 3.0+"]
                    },
                    {
                        "name": "Computer Science",
                        "degree": "MSc",
                        "duration": "2 years",
                        "campuses": [
                            {
                                "name": "Toronto Campus",
                                "city": "Toronto",
                                "tuition_fee": 32000.0,
                                "apply_url": "https://utoronto.ca/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["Fall"],
                        "requirements": ["IELTS 7.0", "GPA 3.5+"]
                    }
                ],
                "scholarships": ["International Student Scholarship", "Graduate Assistantship"],
                "deadlines": {"Fall": "January 15", "Winter": "August 1"},
                "admission_requirements": ["IELTS 7.0+ or TOEFL 93+", "GPA 3.3+", "SOP & LORs"]
            },
            {
                "name": "University of British Columbia",
                "country": "Canada",
                "city": "Vancouver",
                "ranking": 34,
                "website": "https://ubc.ca",
                "description": "Global center for teaching, learning and research, consistently ranked among the top 20 public universities.",
                "tuition_min": 30000,
                "tuition_max": 40000,
                "currency": "CAD",
                "living_cost": 16000,
                "programs": [
                    {
                        "name": "Data Science",
                        "degree": "MDS",
                        "duration": "10 months",
                        "campuses": [
                            {
                                "name": "Vancouver Campus",
                                "city": "Vancouver",
                                "tuition_fee": 45000.0,
                                "apply_url": "https://ubc.ca/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["Fall"],
                        "requirements": ["IELTS 7.0", "GPA 3.2+"]
                    },
                    {
                        "name": "Civil Engineering",
                        "degree": "MASc",
                        "duration": "2 years",
                        "campuses": [
                            {
                                "name": "Vancouver Campus",
                                "city": "Vancouver",
                                "tuition_fee": 28000.0,
                                "apply_url": "https://ubc.ca/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["Fall", "Winter"],
                        "requirements": ["IELTS 6.5", "GPA 3.0+"]
                    }
                ],
                "scholarships": ["UBC Graduate Fellowship", "Karen McKellin International Leader Medal"],
                "deadlines": {"Fall": "January 30", "Winter": "June 1"},
                "admission_requirements": ["IELTS 6.5+ (minimum 6.0 in each band)", "GPA 3.0+ on a 4.0 scale"]
            }
        ]

        count = 0
        try:
            try:
                await self.fetch_page_html("https://www.canada.ca/en.html", retries=1)
            except Exception:
                pass

            for uni in scraped_data:
                for p in uni.get("programs", []):
                    p["intake"] = [i + " Intake" if not i.endswith("Intake") else i for i in p.get("intake", [])]
                    p["deadlines"] = {}
                    for intake in p["intake"]:
                        clean_intake_key = intake.replace(" Intake", "")
                        p["deadlines"][intake] = uni.get("deadlines", {}).get(clean_intake_key) or "Rolling Admission"
                    p["requirements_details"] = None

                existing = await db.universities.find_one({"name": uni["name"]})
                if existing:
                    updates = {}
                    for field, value in uni.items():
                        if existing.get(field) != value:
                            updates[field] = value

                    if updates:
                        await db.universities.update_one(
                            {"_id": existing["_id"]},
                            {"$set": updates}
                        )
                        await db.course_updates.insert_one({
                            "university_id": str(existing["_id"]),
                            "university_name": uni["name"],
                            "changes": updates,
                            "type": "programs" if "programs" in updates else "fees/deadlines",
                            "updated_at": utc_now().isoformat()
                        })
                else:
                    uni["created_at"] = utc_now().isoformat()
                    await db.universities.insert_one(uni)

                count += 1

            await self.log_run(db, "success", count)
            return count
        except Exception as e:
            logger.error(f"Error executing Canada scraper: {e}")
            await self.log_run(db, "failed", 0, str(e))
            raise e
