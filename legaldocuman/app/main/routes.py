import os

from flask import Blueprint, current_app, render_template, send_from_directory

from ..extensions import db
from ..models import Document

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def upload():
    return render_template("upload.html")


@main_bp.route("/jobs")
def jobs():
    docs = db.session.execute(
        db.select(Document).order_by(Document.created_at.desc())
    ).scalars().all()
    return render_template("jobs.html", documents=docs)


@main_bp.route("/jobs/<int:doc_id>")
def job_detail(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return render_template("job_detail.html", error="Document not found"), 404
    return render_template("job_detail.html", document=doc)
