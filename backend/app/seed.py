"""Seed database with German universities and admin user."""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from app.utils.security import hash_password
from app.utils.helpers import utc_now
from scrapers.germany import GermanyScraper


async def seed():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.database_name]

    # Seed admin user if not present
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

    # Run GermanyScraper to clean old static data and seed German universities
    scraper = GermanyScraper()
    count = await scraper.scrape(db)
    print(f"Seeded {count} German universities and updated collections (programs, deadlines, requirements).")

    client.close()
    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
