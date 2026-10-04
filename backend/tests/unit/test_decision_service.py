from unified_intelligence.application.decision_service import DecisionService


class PredictionStub:
    def __init__(self, result):
        self.result = result

    def predict(self, _record):
        return self.result


class RepositorySpy:
    def __init__(self):
        self.saved = None

    def save(self, inventory, delivery, outcome):
        self.saved = (inventory, delivery, outcome)
        return type("Record", (), {"decision_id": "decision-1"})()


class PublisherSpy:
    def __init__(self):
        self.published = None

    def publish(self, decision_id, outcome):
        self.published = (decision_id, outcome)


def test_decision_service_persists_and_publishes_result() -> None:
    repository = RepositorySpy()
    publisher = PublisherSpy()
    service = DecisionService(
        PredictionStub({"stockout_probability": 0.1, "reorder_required": False}),
        PredictionStub({"delay_probability": 0.1}),
        repository=repository,
        event_publisher=publisher,
    )

    result = service.evaluate({"SKU_ID": "SKU-1"}, {"delivery_id": "DEL-1"})

    assert result["decision_id"] == "decision-1"
    assert repository.saved[0] == {"SKU_ID": "SKU-1"}
    assert publisher.published == ("decision-1", result)
