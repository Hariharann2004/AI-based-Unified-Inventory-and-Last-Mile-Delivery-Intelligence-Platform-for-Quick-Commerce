"""Local workbench API. No inferred joins or externally executed actions."""

from flask import Blueprint, jsonify, request

from unified_intelligence.application.ingestion_service import (
    FILENAMES,
    MAX_BYTES,
    IngestionService,
    validate_kind,
)
from unified_intelligence.core.config import PROJECT_ROOT, get_settings
from unified_intelligence.infrastructure.persistence.sqlite_decision_repository import (
    SQLiteDecisionRepository,
)
from unified_intelligence.infrastructure.persistence.workbench_store import WorkbenchStore

workbench = Blueprint("workbench", __name__, url_prefix="/api/workbench")


def store():
    path = SQLiteDecisionRepository.from_url(
        get_settings().database_url, PROJECT_ROOT
    ).database_path
    return WorkbenchStore(path)


@workbench.errorhandler(ValueError)
def invalid(error):
    return jsonify({"error": str(error)}), 400


@workbench.errorhandler(KeyError)
def missing(error):
    return jsonify({"error": str(error.args[0])}), 404


@workbench.errorhandler(FileNotFoundError)
def unavailable(_error):
    return jsonify(
        {"error": "Local dataset/model unavailable. Follow artifact setup in README."}
    ), 503


@workbench.get("/imports")
def imports():
    return jsonify(store().imports())


@workbench.post("/imports/<kind>")
def import_dataset(kind):
    validate_kind(kind)
    uploaded = request.files.get("file")
    if uploaded:
        content, source = uploaded.stream.read(MAX_BYTES + 1), "uploaded_csv"
    else:
        path = PROJECT_ROOT / "data" / "raw" / FILENAMES[kind]
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("CSV exceeds the 15 MiB import limit.")
        content, source = path.read_bytes(), FILENAMES[kind]
    return jsonify(IngestionService(store()).ingest(content, kind, source)), 201


@workbench.get("/records/<kind>")
def records(kind):
    validate_kind(kind)
    return jsonify(
        store().records(
            kind,
            import_id=request.args.get("import_id"),
            limit=request.args.get("limit", 50, type=int),
            offset=request.args.get("offset", 0, type=int),
        )
    )


@workbench.get("/record/<record_id>")
def record(record_id):
    return jsonify(store().record(record_id))
