from __future__ import annotations

from datetime import date as DateType

from pydantic import Field

from unified_intelligence.api.schemas.common import ApiModel


class InventoryPredictionRequest(ApiModel):
    date: DateType = Field(alias="Date")
    sku_id: str = Field(alias="SKU_ID", min_length=1)
    warehouse_id: str = Field(alias="Warehouse_ID", min_length=1)
    supplier_id: str = Field(alias="Supplier_ID", min_length=1)
    region: str = Field(alias="Region", min_length=1)
    inventory_level: float = Field(alias="Inventory_Level", ge=0)
    supplier_lead_time_days: float = Field(alias="Supplier_Lead_Time_Days", ge=1)
    reorder_point: float = Field(alias="Reorder_Point", ge=0)
    order_quantity: float = Field(alias="Order_Quantity", ge=0)
    unit_cost: float = Field(alias="Unit_Cost", ge=0)
    unit_price: float = Field(alias="Unit_Price", ge=0)
    promotion_flag: int = Field(alias="Promotion_Flag", ge=0, le=1)


class InventoryPredictionResponse(ApiModel):
    sku_id: str | None
    warehouse_id: str | None
    predicted_daily_demand: float
    stockout_probability: float
    stockout_risk: str
    reorder_required: bool
    recommended_reorder_quantity: int
    inventory_health_score: float
    inventory_health_status: str
    recommendation: str
