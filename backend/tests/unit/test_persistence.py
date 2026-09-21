import pytest

from unified_intelligence.infrastructure.persistence import SQLiteDecisionRepository


def test_sqlite_repository_round_trips_decisions(tmp_path) -> None:
    repository = SQLiteDecisionRepository(tmp_path / "decisions.db")
    inventory = {"SKU_ID": "SKU-1"}
    delivery = {"delivery_id": "DEL-1"}
    outcome = {"decision": {"operational_priority": "High"}}

    stored = repository.save(inventory, delivery, outcome)
    records = repository.list_recent()

    assert records == [stored]
    assert records[0].inventory_input == inventory
    assert records[0].delivery_input == delivery
    assert records[0].outcome == outcome


def test_sqlite_repository_resolves_relative_database_url(tmp_path) -> None:
    repository = SQLiteDecisionRepository.from_url("sqlite:///data/platform.db", tmp_path)

    assert repository.database_path == (tmp_path / "data" / "platform.db").resolve()


def test_sqlite_repository_rejects_other_database_schemes(tmp_path) -> None:
    with pytest.raises(ValueError, match="Only sqlite"):
        SQLiteDecisionRepository.from_url("postgresql://localhost/platform", tmp_path)
