"""Flask endpoints for the future React dashboard.

POST /api/inventory/predict with one inventory CSV row as JSON.
POST /api/delivery/predict with one delivery CSV row as JSON.
POST /api/decision/unified with {"inventory": {...}, "delivery": {...}}.
"""
from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS

from src.delivery.service import DeliveryService
from src.inventory.service import InventoryService
from src.decision_engine.service import create_unified_recommendation

app = Flask(__name__)
CORS(app)
_inventory: InventoryService | None = None
_delivery: DeliveryService | None = None


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


def body() -> dict:
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Request body must be one JSON object.")
    return value


@app.get("/health")
def health():
    return jsonify({"status": "ok", "algorithm": "LightGBM only"})


@app.post("/api/inventory/predict")
def inventory_predict():
    try:
        return jsonify(inventory_service().predict(body()))
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/delivery/predict")
def delivery_predict():
    try:
        return jsonify(delivery_service().predict(body()))
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/decision/unified")
def unified_decision():
    try:
        payload = body()
        inventory = inventory_service().predict(payload["inventory"])
        delivery_record = payload.get("delivery")
        delivery = delivery_service().predict(delivery_record) if delivery_record else None
        return jsonify({
            "inventory": inventory,
            "delivery": delivery,
            "decision": create_unified_recommendation(inventory, delivery),
        })
    except (ValueError, KeyError) as error:
        return jsonify({"error": str(error)}), 400
