import os

from flask import Blueprint, current_app, render_template, send_from_directory, send_file

from ..extensions import db
from ..models import Document

main_bp = Blueprint("main", __name__)

FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "frontend", "dist",
)


def _serve_spa():
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return send_file(index_path)
    return render_template("upload.html")


@main_bp.route("/assets/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(FRONTEND_DIST, "assets"), filename)


@main_bp.route("/")
def index():
    return _serve_spa()


@main_bp.route("/upload")
@main_bp.route("/documents")
@main_bp.route("/documents/<int:doc_id>")
def spa_routes(**kwargs):
    return _serve_spa()


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
