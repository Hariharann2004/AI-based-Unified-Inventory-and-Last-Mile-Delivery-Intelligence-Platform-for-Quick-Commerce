"""Flask endpoints for the future React dashboard.

POST /api/inventory/predict with one inventory CSV row as JSON.
POST /api/delivery/predict with one delivery CSV row as JSON.
POST /api/decision/unified with {"inventory": {...}, "delivery": {...}}.
"""

from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import BaseModel, ValidationError

from unified_intelligence.api.schemas.decisions import UnifiedDecisionRequest
from unified_intelligence.api.schemas.delivery import DeliveryPredictionRequest
from unified_intelligence.api.schemas.inventory import InventoryPredictionRequest
from unified_intelligence.application.decision_service import DecisionService
from unified_intelligence.application.delivery_service import DeliveryService
from unified_intelligence.application.inventory_service import InventoryService
from unified_intelligence.core.config import PROJECT_ROOT, get_settings
from unified_intelligence.infrastructure.messaging import LoggingDecisionEventPublisher
from unified_intelligence.infrastructure.persistence import SQLiteDecisionRepository

settings = get_settings()
app = Flask(__name__)
CORS(app, origins=settings.cors_origins)
_inventory: InventoryService | None = None
_delivery: DeliveryService | None = None
_repository: SQLiteDecisionRepository | None = None


def inventory_service() -> InventoryService:
    global _inventory
    if _inventory is None:
        _inventory = InventoryService()
    return _inventory


def delivery_service() -> DeliveryService:
    global _delivery
    if _delivery is None:
        _delivery = DeliveryService()
    return _delivery


def decision_repository() -> SQLiteDecisionRepository:
    global _repository
    if _repository is None:
        _repository = SQLiteDecisionRepository.from_url(settings.database_url, PROJECT_ROOT)
    return _repository


def body(model: type[BaseModel]) -> dict:
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Request body must be one JSON object.")
    return model.model_validate(value).model_dump(by_alias=True, mode="json")


@app.errorhandler(ValidationError)
def validation_error(error: ValidationError):
    return jsonify({"error": "Request validation failed.", "details": error.errors()}), 422


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "algorithm": "LightGBM only",
            "environment": settings.environment,
        }
    )


@app.post("/api/inventory/predict")
def inventory_predict():
    try:
        record = body(InventoryPredictionRequest)
        return jsonify(inventory_service().predict(record))
    except ValidationError:
        raise
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/delivery/predict")
def delivery_predict():
    try:
        record = body(DeliveryPredictionRequest)
        return jsonify(delivery_service().predict(record))
    except ValidationError:
        raise
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/decision/unified")
def unified_decision():
    try:
        payload = body(UnifiedDecisionRequest)
        service = DecisionService(
            inventory_service(),
            delivery_service(),
            repository=decision_repository(),
            event_publisher=LoggingDecisionEventPublisher(app.logger),
        )
        return jsonify(service.evaluate(payload["inventory"], payload.get("delivery")))
    except ValidationError:
        raise
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400


@app.get("/api/decisions")
def decision_history():
    limit = request.args.get("limit", default=20, type=int)
    records = decision_repository().list_recent(limit)
    return jsonify(
        [
            {
                "decision_id": record.decision_id,
                "created_at": record.created_at,
                "inventory_input": record.inventory_input,
                "delivery_input": record.delivery_input,
                "outcome": record.outcome,
            }
            for record in records
        ]
    )
