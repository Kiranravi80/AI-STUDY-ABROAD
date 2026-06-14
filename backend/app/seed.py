"""Seed database with sample universities and admin user."""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from app.utils.security import hash_password
from app.utils.helpers import utc_now

SAMPLE_UNIVERSITIES = [
    {
        "name": "Massachusetts Institute of Technology",
        "country": "USA",
        "city": "Cambridge",
        "ranking": 1,
        "website": "https://mit.edu",
        "description": "World-leading institution for science, engineering, and technology.",
        "tuition_min": 55000,
        "tuition_max": 60000,
        "currency": "USD",
        "living_cost": 18000,
        "programs": [
            {"name": "Computer Science", "degree": "MS", "duration": "2 years", "tuition": 58000, "intake": ["Fall", "Spring"]},
            {"name": "Data Science", "degree": "MS", "duration": "2 years", "tuition": 56000, "intake": ["Fall"]},
        ],
        "scholarships": ["Merit Scholarship", "Research Assistantship"],
        "deadlines": {"Fall": "December 15", "Spring": "October 1"},
        "admission_requirements": ["GRE", "TOEFL 100+", "GPA 3.5+"],
    },
    {
        "name": "University of Toronto",
        "country": "Canada",
        "city": "Toronto",
        "ranking": 21,
        "website": "https://utoronto.ca",
        "description": "Canada's top university with diverse programs and research opportunities.",
        "tuition_min": 35000,
        "tuition_max": 45000,
        "currency": "CAD",
        "living_cost": 15000,
        "programs": [
            {"name": "Business Administration", "degree": "MBA", "duration": "2 years", "tuition": 40000, "intake": ["Fall"]},
            {"name": "Mechanical Engineering", "degree": "MEng", "duration": "1.5 years", "tuition": 38000, "intake": ["Fall", "Winter"]},
        ],
        "scholarships": ["International Student Scholarship"],
        "deadlines": {"Fall": "January 15"},
        "admission_requirements": ["IELTS 7.0", "GPA 3.3+"],
    },
    {
        "name": "Technical University of Munich",
        "country": "Germany",
        "city": "Munich",
        "ranking": 37,
        "website": "https://tum.de",
        "description": "Leading European technical university with low tuition fees.",
        "tuition_min": 0,
        "tuition_max": 3000,
        "currency": "EUR",
        "living_cost": 12000,
        "programs": [
            {"name": "Informatics", "degree": "MSc", "duration": "2 years", "tuition": 1500, "intake": ["Winter", "Summer"]},
            {"name": "Automotive Engineering", "degree": "MSc", "duration": "2 years", "tuition": 1500, "intake": ["Winter"]},
        ],
        "scholarships": ["DAAD Scholarship", "TUM Scholarship"],
        "deadlines": {"Winter": "May 31", "Summer": "November 30"},
        "admission_requirements": ["APS Certificate", "IELTS 6.5", "GPA 3.0+"],
    },
    {
        "name": "University of Melbourne",
        "country": "Australia",
        "city": "Melbourne",
        "ranking": 14,
        "website": "https://unimelb.edu.au",
        "description": "Australia's leading university with strong industry connections.",
        "tuition_min": 40000,
        "tuition_max": 50000,
        "currency": "AUD",
        "living_cost": 20000,
        "programs": [
            {"name": "Information Technology", "degree": "Master", "duration": "2 years", "tuition": 45000, "intake": ["February", "July"]},
        ],
        "scholarships": ["Melbourne International Scholarship"],
        "deadlines": {"February": "October 31", "July": "April 30"},
        "admission_requirements": ["IELTS 6.5", "GPA 3.0+"],
    },
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
            {"name": "Artificial Intelligence", "degree": "MSc", "duration": "1 year", "tuition": 42000, "intake": ["October"]},
            {"name": "Finance", "degree": "MSc", "duration": "1 year", "tuition": 40000, "intake": ["October"]},
        ],
        "scholarships": ["President's Scholarship"],
        "deadlines": {"October": "July 31"},
        "admission_requirements": ["IELTS 7.0", "GPA 3.5+"],
    },
    {
        "name": "National University of Singapore",
        "country": "Singapore",
        "city": "Singapore",
        "ranking": 8,
        "website": "https://nus.edu.sg",
        "description": "Asia's top university with global recognition.",
        "tuition_min": 30000,
        "tuition_max": 40000,
        "currency": "SGD",
        "living_cost": 14000,
        "programs": [
            {"name": "Computer Engineering", "degree": "MSc", "duration": "1.5 years", "tuition": 35000, "intake": ["August", "January"]},
        ],
        "scholarships": ["NUS Graduate Scholarship"],
        "deadlines": {"August": "March 15"},
        "admission_requirements": ["GRE", "IELTS 6.5", "GPA 3.2+"],
    },
]


async def seed():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.database_name]

    # Seed admin user (created manually in database as per requirements)
    admin_exists = await db.users.find_one({"email": "admin@aiventra.com"})
    if not admin_exists:
        await db.users.insert_one({
            "email": "admin@aiventra.com",
            "password": hash_password("Admin@123"),
            "first_name": "System",
            "last_name": "Admin",
            "role": "admin",
            "is_active": True,
            "created_at": utc_now().isoformat(),
        })
        print("Admin user created: admin@aiventra.com / Admin@123")

    # Seed universities
    count = await db.universities.count_documents({})
    if count == 0:
        for uni in SAMPLE_UNIVERSITIES:
            uni["created_at"] = utc_now().isoformat()
            await db.universities.insert_one(uni)
        print(f"Seeded {len(SAMPLE_UNIVERSITIES)} universities")

    client.close()
    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
