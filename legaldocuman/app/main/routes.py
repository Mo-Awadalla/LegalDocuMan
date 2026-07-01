import os

from flask import Blueprint, jsonify, render_template, send_from_directory, send_file
from sqlalchemy import text

from ..extensions import db

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


@main_bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@main_bp.route("/readyz")
def readyz():
    try:
        db.session.execute(text("select 1"))
    except Exception as exc:
        return jsonify({"status": "error", "database": str(exc)}), 503
    return jsonify({"status": "ok", "database": "ok"})
