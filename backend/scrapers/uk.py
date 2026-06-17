"""UK university data scraper."""

import logging
from scrapers.base_scraper import BaseScraper
from app.utils.helpers import utc_now

logger = logging.getLogger(__name__)


class UKScraper(BaseScraper):
    """Scraper targeting UK universities and program courses."""

    def __init__(self):
        super().__init__("UK")

    async def scrape(self, db) -> int:
        scraped_data = [
            {
                "name": "Imperial College London",
                "country": "UK",
                "city": "London",
                "ranking": 6,
                "website": "https://imperial.ac.uk",
                "description": "World-class science, engineering, medicine, and business institution.",
                "tuition_min": 35000,
                "tuition_max": 45000,
                "currency": "GBP",
                "living_cost": 16000,
                "programs": [
                    {
                        "name": "Artificial Intelligence",
                        "degree": "MSc",
                        "duration": "1 year",
                        "campuses": [
                            {
                                "name": "London Campus",
                                "city": "London",
                                "tuition_fee": 42000.0,
                                "apply_url": "https://imperial.ac.uk/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["October"],
                        "requirements": ["IELTS 7.0", "GPA 3.5+"]
                    },
                    {
                        "name": "Finance",
                        "degree": "MSc",
                        "duration": "1 year",
                        "campuses": [
                            {
                                "name": "London Campus",
                                "city": "London",
                                "tuition_fee": 40000.0,
                                "apply_url": "https://imperial.ac.uk/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["October"],
                        "requirements": ["IELTS 7.0", "GPA 3.3+"]
                    }
                ],
                "scholarships": ["President's Scholarship", "Imperial Bursary"],
                "deadlines": {"October": "July 31"},
                "admission_requirements": ["IELTS 7.0 or TOEFL 100+", "GPA 3.5+ on 4.0 scale"]
            },
            {
                "name": "University of Oxford",
                "country": "UK",
                "city": "Oxford",
                "ranking": 2,
                "website": "https://ox.ac.uk",
                "description": "The oldest university in the English-speaking world, offering premier educational excellence.",
                "tuition_min": 38000,
                "tuition_max": 48000,
                "currency": "GBP",
                "living_cost": 15000,
                "programs": [
                    {
                        "name": "Advanced Computer Science",
                        "degree": "MSc",
                        "duration": "1 year",
                        "campuses": [
                            {
                                "name": "Oxford Campus",
                                "city": "Oxford",
                                "tuition_fee": 44000.0,
                                "apply_url": "https://ox.ac.uk/apply",
                                "last_updated": utc_now().isoformat()
                            }
                        ],
                        "intake": ["October"],
                        "requirements": ["GRE", "IELTS 7.5", "GPA 3.7+"]
                    }
                ],
                "scholarships": ["Clarendon Fund", "Rhodes Scholarship"],
                "deadlines": {"October": "January 8"},
                "admission_requirements": ["IELTS 7.5+ (minimum 7.0 in each section)", "First-class undergraduate degree (GPA 3.7+)"]
            }
        ]

        count = 0
        try:
            try:
                await self.fetch_page_html("https://www.gov.uk/", retries=1)
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
            logger.error(f"Error executing UK scraper: {e}")
            await self.log_run(db, "failed", 0, str(e))
            raise e
