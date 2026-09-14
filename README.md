# AI based Unified Inventory and Last Mile Delivery Intelligence Platform for Quick Commerce 
Software Design and Development Project (Final Year Project - 1)



# Unified Inventory and Delivery Intelligence

This project implements the capstone's two core modules using **LightGBM only** as its machine-learning algorithm:

- Smart Inventory Engine: demand forecasting and stockout-risk prediction.
- Delivery Intelligence Platform: ETA and delivery-delay prediction.
- Live AI Decision Engine: rule-based recommendations that combine both outputs.

The health, performance, cost and recommendation outputs are transparent business rules; they are not additional ML algorithms.

## Project layout

```
data/raw/                 Original project datasets
data/processed/           Generated training-ready data (optional)
models/                   Generated .joblib LightGBM artifacts
src/inventory/            Inventory feature, training and inference code
src/delivery/             Delivery feature, training and inference code
src/decision_engine/      Unified recommendation rules
src/api/                  Flask API for a React dashboard
```

## Run in VS Code

Before creating the environment, verify that a full Python installation is available:

```powershell
python --version
```

If this command fails or displays a Windows Store access error, install Python 3.10 or newer from python.org and select **Add Python to PATH** during installation. Then reopen VS Code.

Open this folder in VS Code and create one fresh virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.train_models
python -m flask --app src.api.app run --debug
```

To run the included React dashboard in a second VS Code terminal:

```powershell
cd frontend
npm install
npm run dev
```

The training command reads both files in `data/raw` and creates four LightGBM artifacts in `models/`:

- `inventory_demand.joblib`
- `inventory_stockout.joblib`
- `delivery_eta.joblib`
- `delivery_delay.joblib`

Open `http://127.0.0.1:5000/health` after starting Flask. API examples are in `src/api/app.py`.

For example, submit an inventory row with the VS Code REST Client, Postman, or a
React `fetch` request:

```json
{
  "Date": "2024-01-01",
  "SKU_ID": "SKU_1",
  "Warehouse_ID": "WH_1",
  "Supplier_ID": "SUP_8",
  "Region": "West",
  "Inventory_Level": 592,
  "Supplier_Lead_Time_Days": 14,
  "Reorder_Point": 379,
  "Order_Quantity": 0,
  "Unit_Cost": 13.95,
  "Unit_Price": 20.48,
  "Promotion_Flag": 0
}
```

## Important data decisions

- Inventory demand is trained against `Units_Sold`; the pre-existing `Demand_Forecast` column is excluded so the model predicts rather than copies a supplied forecast.
- Demand evaluation uses the latest 20% of inventory dates as the holdout set, which is more appropriate than randomly mixing past and future records.
- `Stockout_Flag` is constant at `0` in the provided file, so it cannot train a classifier. The implementation transparently derives a historical stockout-risk target when inventory is below observed lead-time demand plus a 15% safety buffer; `Units_Sold` is not an input feature for that classifier.
- Delivery ETA is trained against `delivery_time_minutes`. Derived outcome columns such as `ETA_Minutes`, `Delay_Risk`, `Delivery_Intelligence_Score`, `delivery_status`, and `delivery_time_minutes` are excluded from ETA inputs to avoid target leakage.
- The delivery delay classifier is trained against `delayed`; it excludes post-delivery outcome fields for the same reason.

