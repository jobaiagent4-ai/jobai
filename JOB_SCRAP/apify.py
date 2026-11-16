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
