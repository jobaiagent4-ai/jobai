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

    def _ensure_shopdata_table(self, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shopdata (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                contact TEXT NOT NULL,
                region TEXT NOT NULL DEFAULT 'Outside Kerala',
                category TEXT,
                UNIQUE (name, location, contact)
            )
        """)
        cur.execute(
            "ALTER TABLE shopdata ADD COLUMN IF NOT EXISTS region TEXT"
        )
        cur.execute("""
            UPDATE shopdata
            SET region = CASE
                WHEN location ILIKE '%Kerala%' THEN 'Kerala'
                ELSE 'Outside Kerala'
            END
            WHERE region IS NULL
        """)

    def read_shops(self):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            self._ensure_shopdata_table(cur)
            cur.execute(
                "SELECT name, location, contact, region, category "
                "FROM shopdata ORDER BY name"
            )
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            conn.commit()
            return rows
        finally:
            conn.close()

    def add_shops(self, shops):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            self._ensure_shopdata_table(cur)
            for shop in shops:
                cur.execute(
                    """
                    INSERT INTO shopdata (name, location, contact, region, category)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name, location, contact) DO NOTHING
                    """,
                    (
                        shop["name"],
                        shop["location"],
                        shop["contact"],
                        shop["region"],
                        shop.get("category"),
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

db = Database()