import os

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
URL = "https://jsearch.p.rapidapi.com/search-v2"


def search(query, pages="4"):
    api_key = os.getenv("JSEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("Set JSEARCH_API_KEY in the environment or .env file.")

    params = {
        "query": query,
        "num_pages": pages,
        "date_posted": "month",
        "country": "in",
    }
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    response = requests.get(URL, headers=headers, params=params, timeout=30)
    print(f"'{query}' -> status {response.status_code}")
    if response.status_code != 200:
        print(response.text[:300])
        return []
    data = response.json().get("data", [])
    if isinstance(data, dict):  # v5 may nest the job list
        data = next((value for value in data.values() if isinstance(value, list)), [])
    return data


def to_rows(data):
    rows = []
    for job in data:
        state = (job.get("job_state") or "").lower()
        city = (job.get("job_city") or "").lower()
        in_kerala = "kerala" in state or "kerala" in city
        rows.append({
            "region": "Kerala" if in_kerala else "Outside Kerala",
            "job_id": job.get("job_id"),
            "title": job.get("job_title"),
            "company": job.get("employer_name"),
            "city": job.get("job_city"),
            "state": job.get("job_state"),
            "type": job.get("job_employment_type"),
            "posted": job.get("job_posted_at_datetime_utc"),
            "source": job.get("job_publisher"),
            "apply_link": job.get("job_apply_link"),
        })
    return rows


def fetch_jobs():
    """Fetch jobs from the JSearch API and return a DataFrame."""
    queries = [
        "mobile phone technician in Kerala, India",
        "laptop technician in Kerala, India",
        "mobile phone technician in India",
        "laptop technician in India",
    ]
    rows = []
    for query in queries:
        rows.extend(to_rows(search(query)))

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        raise SystemExit("No jobs found.")

    print(f"Fetched rows before job_id deduplication: {len(dataframe)}")
    print(f"Unique non-null job IDs: {dataframe['job_id'].nunique()}")
    print(f"Rows with missing job IDs: {dataframe['job_id'].isna().sum()}")
    print("Sample fetched jobs (job_id, title, company):")
    print(dataframe[["job_id", "title", "company"]].head(30).to_string(index=False))

    dataframe = dataframe.drop_duplicates("job_id")
    print(f"Rows after job_id deduplication: {len(dataframe)}")
    dataframe = dataframe.sort_values("region", ascending=False)
    return dataframe
