import os

from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()
api_token = os.getenv("APIFY_API_TOKEN")
client = ApifyClient(api_token) if api_token else None


def get_contact(company, city):
    if client is None:
        raise RuntimeError("Set APIFY_API_TOKEN in the environment or .env file.")

    run = client.actor("crustapi/google-maps-scraper").call(
        run_input={
            "query": [f"{company} {city}"],
            "location": "India",
            "maxResults": 5,
            "language": "en",
            "websiteFilter": "all",
        },
        logger=None,
    )
    first_word = company.lower().split()[0]
    for shop in client.dataset(run.default_dataset_id).iterate_items():
        title = shop.get("title") or ""
        if shop.get("phone") and first_word in title.lower():
            return title, shop.get("phone")
    return None, None


def fetch_mobile_laptop_shops():
    if client is None:
        raise RuntimeError("Set APIFY_API_TOKEN in the environment or .env file.")

    shops = []
    seen = set()
    categories = [
        "mobile service center",
        "mobile phone shop",
        "laptop service center",
        "laptop shop",
    ]
    searches = [
        ("Kerala", "Kerala, India", [f"{category} Kerala" for category in categories]),
        ("Outside Kerala", "India", categories),
    ]

    for requested_region, location_query, queries in searches:
        run = client.actor("crustapi/google-maps-scraper").call(
            run_input={
                "query": queries,
                "location": location_query,
                "maxResults": 5,
                "language": "en",
                "websiteFilter": "all",
            },
            logger=None,
        )

        for result in client.dataset(run.default_dataset_id).iterate_items():
            name = result.get("title") or result.get("name")
            contact = result.get("phone") or result.get("phoneUnformatted")
            location = (
                result.get("address")
                or result.get("formattedAddress")
                or ", ".join(
                    part
                    for part in (
                        result.get("city"),
                        result.get("state"),
                        result.get("country"),
                    )
                    if part
                )
            )
            state = str(result.get("state") or "")
            if not name or not location or not contact:
                continue
            country = str(result.get("country") or "").strip().lower()
            if country and country not in {"india", "in"}:
                continue

            region = "Kerala" if "kerala" in f"{state} {location}".lower() else "Outside Kerala"
            if region != requested_region:
                continue

            key = (str(name).strip().lower(), str(location).strip().lower(), str(contact).strip())
            if key in seen:
                continue
            seen.add(key)
            shops.append(
                {
                    "name": str(name).strip(),
                    "location": str(location).strip(),
                    "contact": str(contact).strip(),
                    "region": region,
                    "category": result.get("categoryName") or result.get("category"),
                }
            )
    return shops
