import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATA_BASE_URL")


class Database:
    def __init__(self, url=DATABASE_URL):
        self.url = url

    def _get_conn(self):
        if not self.url:
            raise RuntimeError("Set DATABASE_URL or DATA_BASE_URL in the project .env file.")
        return psycopg2.connect(self.url)

    def read_jobs(self):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM new_data")
        columns = [column[0] for column in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        conn.close()
        return rows

    def add_job(self, job):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO new_data
            (region, job_id, title, company, contact, city, state, type, posted, source, apply_link)
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM new_data
                WHERE title = %s AND company = %s
            )
            ON CONFLICT (job_id) DO NOTHING
        """, (
            job["region"], job["job_id"], job["title"], job["company"],
            job["contact"], job["city"], job["state"], job["type"],
            job["posted"], job["source"], job["apply_link"],
            job["title"], job["company"],
        ))
        conn.commit()
        conn.close()

db = Database()