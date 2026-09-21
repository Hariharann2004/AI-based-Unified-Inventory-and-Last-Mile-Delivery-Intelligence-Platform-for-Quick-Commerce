import pandas as pd

from unified_intelligence.ml.features import derive_stockout_target, prepare_inventory_features


def test_inventory_features_replace_date_with_calendar_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "Date": "2024-01-01",
                "SKU_ID": "SKU-1",
                "Warehouse_ID": "WH-1",
                "Supplier_ID": "SUP-1",
                "Region": "West",
                "Inventory_Level": 10,
                "Supplier_Lead_Time_Days": 2,
                "Reorder_Point": 5,
                "Order_Quantity": 1,
                "Unit_Cost": 4,
                "Unit_Price": 6,
                "Promotion_Flag": 0,
            }
        ]
    )

    result = prepare_inventory_features(frame)

    assert "Date" not in result
    assert result.loc[0, ["year", "month", "day_of_week"]].tolist() == [2024, 1, 0]


def test_stockout_target_uses_lead_time_safety_buffer() -> None:
    frame = pd.DataFrame(
        {
            "Inventory_Level": [100, 10],
            "Units_Sold": [10, 10],
            "Supplier_Lead_Time_Days": [2, 2],
        }
    )

    assert derive_stockout_target(frame).tolist() == [0, 1]
