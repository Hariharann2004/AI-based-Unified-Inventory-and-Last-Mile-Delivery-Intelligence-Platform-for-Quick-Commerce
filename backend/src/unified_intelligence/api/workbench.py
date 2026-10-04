"""Local workbench API. No inferred joins or externally executed actions."""

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from unified_intelligence.api.schemas.workbench import (
    ActionRequest,
    BatchRequest,
    EvaluationRequest,
    ReplayRequest,
    ScenarioRequest,
    StepRequest,
)
from unified_intelligence.application.batch_service import BatchService
from unified_intelligence.application.evaluation_service import EvaluationService
from unified_intelligence.application.ingestion_service import (
    FILENAMES,
    MAX_BYTES,
    IngestionService,
    validate_kind,
)
from unified_intelligence.application.replay_service import ReplayConflict, ReplayService
from unified_intelligence.application.scenario_service import SCENARIOS, ScenarioService
from unified_intelligence.core.config import PROJECT_ROOT, get_settings
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository
from unified_intelligence.infrastructure.persistence.sqlite_decision_repository import (
    SQLiteDecisionRepository,
)

workbench = Blueprint("workbench", __name__, url_prefix="/api/workbench")


@workbench.errorhandler(ValidationError)
def validation(error):
    return jsonify(
        {"error": "Request validation failed.", "details": error.errors(include_context=False)}
    ), 422


def payload(model):
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object.")
    return model.model_validate(value)


def batch_service():
    from unified_intelligence.api.app import delivery_service, inventory_service

    return BatchService(
        store(), inventory_service, delivery_service, get_settings().model_directory
    )


@workbench.post("/batches")
def batches():
    return jsonify(batch_service().process(payload(BatchRequest).record_ids))


def store():
    path = SQLiteDecisionRepository.from_url(
        get_settings().database_url, PROJECT_ROOT
    ).database_path
    return CaseRepository(path)


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
            warehouse=request.args.get("warehouse"),
            sku=request.args.get("sku"),
        )
    )


@workbench.get("/record/<record_id>")
def record(record_id):
    return jsonify(store().record(record_id))


@workbench.get("/cases")
def cases():
    return jsonify(
        store().cases(
            kind=request.args.get("kind"),
            status=request.args.get("status"),
            limit=request.args.get("limit", 50, type=int),
            offset=request.args.get("offset", 0, type=int),
        )
    )


@workbench.get("/cases/<case_id>")
def case(case_id):
    return jsonify(store().case(case_id))


@workbench.post("/cases/<case_id>/actions")
def case_action(case_id):
    value = payload(ActionRequest)
    return jsonify(store().transition(case_id, value.action, value.actor, value.reason))


@workbench.errorhandler(ReplayConflict)
def replay_conflict(error):
    return jsonify({"error": str(error)}), 409


@workbench.post("/replays")
def start_replay():
    value = payload(ReplayRequest)
    return jsonify(
        ReplayService(store(), batch_service()).start(value.kind, value.import_id, value.limit)
    ), 201


@workbench.get("/replays/<run_id>")
def get_replay(run_id):
    return jsonify(ReplayService(store(), batch_service()).get(run_id))


@workbench.post("/replays/<run_id>/steps")
def step_replay(run_id):
    value = payload(StepRequest)
    return jsonify(
        ReplayService(store(), batch_service()).step(run_id, value.expected_cursor, value.count)
    )


@workbench.get("/scenarios")
def scenarios():
    return jsonify(SCENARIOS)


@workbench.post("/scenarios")
def run_scenario():
    value = payload(ScenarioRequest)
    return jsonify(ScenarioService(store(), batch_service()).evaluate(**value.model_dump()))


@workbench.get("/evaluations")
def evaluations():
    return jsonify(EvaluationService(store()).reports())


@workbench.get("/evaluations/<evaluation_id>")
def evaluation(evaluation_id):
    return jsonify(EvaluationService(store()).get(evaluation_id))


@workbench.post("/evaluations")
def start_evaluation():
    value = payload(EvaluationRequest)
    return jsonify(EvaluationService(store()).start(value.kind, value.import_id)), 202
