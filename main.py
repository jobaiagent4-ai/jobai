import hashlib
import json
import os
import tempfile
import threading
from io import BytesIO
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request, send_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from JOB_SCRAP.jsearch import fetch_jobs
from JOB_SCRAP.apify import fetch_mobile_laptop_shops, get_contact as lookup_contact
from DATA_BASE.DB import db
import pandas as pd

app = Flask(__name__)
EXCEL_EXPORT_STATE_PATH = os.path.join(app.instance_path, "excel_export_state.json")
excel_export_lock = threading.Lock()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/jobs")
def jobs():
    try:
        jobs_list = db.read_jobs()
        return jsonify(jobs_list)
    except Exception as e:
        return f"Error fetching jobs: {e}", 500


@app.route("/shops", methods=["GET"])
def shops():
    try:
        return jsonify(db.read_shops())
    except Exception:
        app.logger.exception("Failed to read shop data.")
        return jsonify(error="Unable to load shops."), 500


@app.route("/shops/export/excel")
def export_shops_excel():
    try:
        shops_list = db.read_shops()
        columns = ["name", "location", "contact", "region", "category"]
        shops_df = pd.DataFrame(shops_list, columns=columns)
        for column in shops_df.columns:
            shops_df[column] = shops_df[column].map(prepare_excel_value)

        output = BytesIO()
        shops_df.to_excel(output, index=False, sheet_name="Shops")
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="shop_data.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        app.logger.exception("Failed to export shops to Excel.")
        return jsonify(error="Unable to export shops to Excel."), 500


@app.route("/shops/fetch", methods=["POST"])
def fetch_shops():
    if not os.getenv("APIFY_API_TOKEN"):
        return jsonify(error="Shop search is not configured."), 503

    try:
        fetched_shops = fetch_mobile_laptop_shops()
        db.add_shops(fetched_shops)
        return jsonify(db.read_shops())
    except Exception:
        app.logger.exception("Failed to fetch India-wide shops from Apify.")
        return jsonify(error="Unable to fetch shops."), 500


def read_export_jobs():
    return db.read_jobs()


def job_export_signature(job):
    job_id = job.get("job_id")
    if job_id is not None and str(job_id).strip():
        return "id:" + str(job_id)

    job_data = json.dumps(job, sort_keys=True, default=str, ensure_ascii=False)
    return "row:" + hashlib.sha256(job_data.encode("utf-8")).hexdigest()


def read_excel_export_state():
    try:
        with open(EXCEL_EXPORT_STATE_PATH, encoding="utf-8") as state_file:
            state = json.load(state_file)
    except FileNotFoundError:
        return set()

    exported_jobs = state.get("exported_jobs")
    if not isinstance(exported_jobs, list) or not all(
        isinstance(signature, str) for signature in exported_jobs
    ):
        raise ValueError("Excel export history is invalid.")
    return set(exported_jobs)


def save_excel_export_state(exported_jobs):
    os.makedirs(app.instance_path, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix="excel-export-",
        suffix=".tmp",
        dir=app.instance_path,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as state_file:
            json.dump(
                {
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    "exported_jobs": sorted(exported_jobs),
                },
                state_file,
            )
        os.replace(temporary_path, EXCEL_EXPORT_STATE_PATH)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def prepare_excel_value(value):
    if isinstance(value, datetime) and value.utcoffset() is not None:
        value = value.isoformat()
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@app.route("/jobs/export/excel")
def export_jobs_excel():
    scope = request.args.get("scope", "all")
    if scope not in {"all", "latest"}:
        return jsonify(error="scope must be 'all' or 'latest'."), 400

    try:
        with excel_export_lock:
            jobs_list = read_export_jobs()
            signatures = [job_export_signature(job) for job in jobs_list]
            previously_exported = read_excel_export_state()
            if scope == "latest":
                export_jobs = [
                    job
                    for job, signature in zip(jobs_list, signatures)
                    if signature not in previously_exported
                ]
            else:
                export_jobs = jobs_list

            columns = list(jobs_list[0]) if jobs_list else [
                "region", "job_id", "title", "company", "contact", "city",
                "state", "type", "posted", "source", "apply_link",
            ]
            jobs_df = pd.DataFrame(export_jobs, columns=columns)
            for column in jobs_df.columns:
                jobs_df[column] = jobs_df[column].map(prepare_excel_value)

            output = BytesIO()
            jobs_df.to_excel(output, index=False, sheet_name="Jobs")
            output.seek(0)
            save_excel_export_state(previously_exported.union(signatures))

        return send_file(
            output,
            as_attachment=True,
            download_name="job_data.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        app.logger.exception("Failed to export jobs to Excel.")
        return jsonify(error="Unable to export jobs to Excel."), 500


@app.route("/jobs/export/pdf")
def export_jobs_pdf():
    try:
        jobs_list = read_export_jobs()
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=letter,
            rightMargin=0.55 * inch,
            leftMargin=0.55 * inch,
            topMargin=0.55 * inch,
            bottomMargin=0.55 * inch,
            title="Job Board Data",
        )
        base_styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ExportTitle",
            parent=base_styles["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#39254e"),
        )
        value_style = ParagraphStyle(
            "ExportValue",
            parent=base_styles["BodyText"],
            fontSize=8,
            leading=10,
            wordWrap="CJK",
        )
        label_style = ParagraphStyle(
            "ExportLabel",
            parent=value_style,
            textColor=colors.HexColor("#39254e"),
            fontName="Helvetica-Bold",
        )
        story = [
            Paragraph("Job Board Data", title_style),
            Paragraph(f"{len(jobs_list)} jobs", base_styles["Normal"]),
            Spacer(1, 14),
        ]

        if not jobs_list:
            story.append(Paragraph("No jobs available.", base_styles["Normal"]))
        else:
            for job in jobs_list:
                title = escape(str(job.get("title") or "Untitled role"))
                rows = [[Paragraph("<b>Title</b>", label_style), Paragraph(title, value_style)]]
                rows.extend(
                    [
                        Paragraph(escape(str(key)), label_style),
                        Paragraph(escape("" if value is None else str(value)).replace("\n", "<br/>"), value_style),
                    ]
                    for key, value in job.items()
                    if key != "title"
                )
                table = Table(rows, colWidths=[1.05 * inch, 5.85 * inch], splitByRow=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2eaf7")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7e7dc")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e7e7dc")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.extend([table, Spacer(1, 12)])

        document.build(story)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="job_data.pdf",
            mimetype="application/pdf",
        )
    except Exception:
        app.logger.exception("Failed to export jobs to PDF.")
        return jsonify(error="Unable to export jobs to PDF."), 500


def get_contact(job):
    original_count = len(job)
    job = job.drop_duplicates(
        subset=["title", "company", "city", "state"],
        keep="first",
    ).copy()
    app.logger.info(
        "Skipped %d duplicate jobs before contact lookup.",
        original_count - len(job),
    )

    subset = job[["job_id", "company", "city", "state"]]
    for jobs in subset.to_dict(orient="records"):
        id = jobs.get("job_id")
        company = jobs.get("company")
        city = jobs.get("city")
        state = jobs.get("state")
        print(f"Looking up contact for job_id: {id}, company: {company}, city: {city}, state: {state}")
        if not company or not city:
            continue
        location = ", ".join(part for part in (city, state) if isinstance(part, str) and part)
        title, phone = lookup_contact(company, location)
        if title and phone:
            if company.lower() in title.lower() or company.lower().split()[0] in title.lower():
                job.loc[job["job_id"] == id, "contact"] = phone
    return pd.DataFrame(job)




def fetch_and_store_jobs():
    try:
        jobs_df = fetch_jobs()
    except SystemExit as exc:
        if exc.code != "No jobs found.":
            raise
        app.logger.info("No jobs found during scheduled fetch.")
        return

    if jobs_df.empty:
        app.logger.info("No jobs found during scheduled fetch.")
        return

    if os.getenv("APIFY_API_TOKEN"):
        updated_df = get_contact(jobs_df)
    else:
        app.logger.warning(
            "APIFY_API_TOKEN is not configured; saving jobs without contact details."
        )
        updated_df = jobs_df.copy()

    for job in updated_df.to_dict(orient="records"):
        job.setdefault("contact", None)
        db.add_job(job)

    app.logger.info("Processed %d fetched jobs.", len(updated_df))


def configure_daily_job(scheduler):
    scheduler.add_job(
        fetch_and_store_jobs,
        trigger="cron",
        hour=0,
        minute=0,
        id="fetch-jobs-daily",
        max_instances=1,
        coalesce=True,
    )


scheduler = BackgroundScheduler()
configure_daily_job(scheduler)
scheduler.start()
app.logger.info("Daily job fetch scheduler started for 00:00 (%s).", scheduler.timezone)

if __name__ == "__main__":
    try:
        app.run(debug=True, use_reloader=False)
    finally:
        scheduler.shutdown()
