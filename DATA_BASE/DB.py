import os
from difflib import SequenceMatcher

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATA_BASE_URL")


def _normalize_shop_name(value):
    normalized_value = (value or "").casefold()
    return "".join(
        character for character in normalized_value if character.isalnum()
    )


def _normalize_contact(value):
    digits = "".join(character for character in (value or "") if character.isdigit())
    if len(digits) > 10:
        digits = digits.lstrip("0")
        if digits.startswith("91") and len(digits) > 10:
            digits = digits[2:]
    return digits


def _contacts_match(first_contacts, second_contacts):
    for first_contact in first_contacts:
        for second_contact in second_contacts:
            if first_contact and second_contact:
                shorter = min(len(first_contact), len(second_contact))
                if shorter >= 10 and (
                    first_contact.endswith(second_contact)
                    or second_contact.endswith(first_contact)
                ):
                    return True
    return False


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
        cur.execute("ALTER TABLE new_data ADD COLUMN IF NOT EXISTS contact2 TEXT")
        cur.execute("SELECT * FROM new_data")
        columns = [column[0] for column in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        conn.commit()
        conn.close()
        return rows

    def add_job(self, job):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("ALTER TABLE new_data ADD COLUMN IF NOT EXISTS contact2 TEXT")
        cur.execute("""
            INSERT INTO new_data
            (region, job_id, title, company, contact, contact2, city, state, type, posted, source, apply_link)
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM new_data
                WHERE title = %s AND company = %s
            )
            ON CONFLICT (job_id) DO NOTHING
        """, (
            job["region"], job["job_id"], job["title"], job["company"],
            job.get("contact"), job.get("contact2"), job["city"], job["state"], job["type"],
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
        cur.execute(
            "ALTER TABLE shopdata ADD COLUMN IF NOT EXISTS contact2 TEXT"
        )
        cur.execute("""
            UPDATE shopdata
            SET region = CASE
                WHEN location ILIKE '%Kerala%' THEN 'Kerala'
                ELSE 'Outside Kerala'
            END
            WHERE region IS NULL
        """)

    def _ensure_oldata_table(self, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS oldata (
                id SERIAL PRIMARY KEY,
                shop_name TEXT NOT NULL,
                contact TEXT NOT NULL
            )
        """)
        cur.execute(
            "ALTER TABLE oldata ADD COLUMN IF NOT EXISTS contact2 TEXT"
        )

    def read_shops(self):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            self._ensure_shopdata_table(cur)
            self._ensure_oldata_table(cur)
            cur.execute(
                "SELECT name, location, contact, contact2, region, category "
                "FROM shopdata ORDER BY name"
            )
            columns = [column[0] for column in cur.description]
            shops = [dict(zip(columns, row)) for row in cur.fetchall()]
            cur.execute("SELECT shop_name, contact, contact2 FROM oldata")
            old_shops = cur.fetchall()

            old_names = {
                normalized
                for name, _contact, _contact2 in old_shops
                if (normalized := _normalize_shop_name(name))
            }
            old_contacts = {
                normalized
                for _name, contact, contact2 in old_shops
                for normalized in (
                    _normalize_contact(contact),
                    _normalize_contact(contact2),
                )
                if normalized
            }

            rows = []
            for shop in shops:
                shop_name = _normalize_shop_name(shop["name"])
                shop_contacts = {
                    normalized
                    for normalized in (
                        _normalize_contact(shop["contact"]),
                        _normalize_contact(shop.get("contact2")),
                    )
                    if normalized
                }
                name_matches = bool(shop_name) and any(
                    SequenceMatcher(
                        None, shop_name, old_name, autojunk=False
                    ).ratio() > 0.8
                    for old_name in old_names
                )
                contact_matches = _contacts_match(shop_contacts, old_contacts)
                if not name_matches and not contact_matches:
                    rows.append(shop)

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
                    INSERT INTO shopdata (name, location, contact, contact2, region, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name, location, contact) DO NOTHING
                    """,
                    (
                        shop["name"],
                        shop["location"],
                        shop["contact"],
                        shop.get("contact2"),
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

    def add_oldata(self, records):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            self._ensure_oldata_table(cur)
            batch_size = 500
            for start in range(0, len(records), batch_size):
                batch = records[start:start + batch_size]
                execute_values(
                    cur,
                    "INSERT INTO oldata (shop_name, contact, contact2) VALUES %s",
                    [
                        (record["shop_name"], record["contact"], record.get("contact2"))
                        for record in batch
                    ],
                    page_size=batch_size,
                )
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

db = Database()