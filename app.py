# app.py — Run with: uvicorn app:app --reload
import os, json
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import joblib, pandas as pd, numpy as np, io

# ── App setup ────────────────────────────────────────────────
app = FastAPI(title="Demand Forecasting API")

# CORS MUST be added immediately after app creation, before any routes
# In app.py, update the allow_origins line:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-app-name.vercel.app"   # replace after Vercel deploy
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Model loading ────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model       = joblib.load(os.path.join(BASE_DIR, "xgb_demand_model.pkl"))
feature_cols = joblib.load(os.path.join(BASE_DIR, "model_features.pkl"))

# ── Storage files ────────────────────────────────────────────
SALES_LOG     = os.path.join(BASE_DIR, "sales_log.json")
PRODUCTS_FILE = os.path.join(BASE_DIR, "products.json")
USERS_FILE    = os.path.join(BASE_DIR, "users.json")

DEFAULT_USERS = {"admin": "password123", "user1": "pass456"}

# ── File helpers ─────────────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_users():    return load_json(USERS_FILE, DEFAULT_USERS)
def load_sales():    return load_json(SALES_LOG, [])
def save_sales(d):   save_json(SALES_LOG, d)
def load_products(): return load_json(PRODUCTS_FILE, [])
def save_products(d): save_json(PRODUCTS_FILE, d)

# ── Auth ─────────────────────────────────────────────────────
security = HTTPBasic()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    users = load_users()
    if credentials.username not in users or users[credentials.username] != credentials.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

# ── Pydantic models ──────────────────────────────────────────
class SignupInput(BaseModel):
    username: str
    password: str

class ProductInput(BaseModel):
    name: str
    price: float
    supplier_cost: float
    unit: Optional[str] = "units"

class SaleEntry(BaseModel):
    product_name:  str
    quantity_sold: float
    stock_level:   float
    stock_added:   Optional[float] = 0.0
    date:          Optional[str]   = None

class OptimizeInput(BaseModel):
    avg_demand: float
    std_demand: float
    lead_time:  int = 5

# ════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════

@app.post("/login")
def login(credentials: HTTPBasicCredentials = Depends(security)):
    username = get_current_user(credentials)
    return {"status": "success", "username": username}

@app.post("/signup")
def signup(data: SignupInput):
    users = load_users()
    if data.username in users:
        raise HTTPException(status_code=400, detail="Username already exists.")
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    users[data.username] = data.password
    save_json(USERS_FILE, users)
    return {"status": "success", "message": f"Account created for {data.username}!"}

# ════════════════════════════════════════════════════════════
# PRODUCTS
# ════════════════════════════════════════════════════════════

@app.get("/products")
def get_products(username: str = Depends(get_current_user)):
    products = load_products()
    return [p for p in products if p.get("owner") == username]

@app.post("/products")
def add_product(product: ProductInput, username: str = Depends(get_current_user)):
    products = load_products()
    existing = [p for p in products if p["owner"] == username and p["name"] == product.name]
    if existing:
        raise HTTPException(status_code=400, detail=f"Product '{product.name}' already exists.")
    # Use model_dump() — works for both Pydantic v1 and v2
    try:
        record = product.model_dump()
    except AttributeError:
        record = product.dict()
    record["owner"]      = username
    record["created_at"] = datetime.today().strftime("%Y-%m-%d")
    products.append(record)
    save_products(products)
    return {"status": "added", "product": record}

@app.delete("/products/{product_name}")
def delete_product(product_name: str, username: str = Depends(get_current_user)):
    products = load_products()
    updated  = [p for p in products if not (p["owner"] == username and p["name"] == product_name)]
    if len(updated) == len(products):
        raise HTTPException(status_code=404, detail="Product not found.")
    save_products(updated)
    sales = load_sales()
    sales = [s for s in sales if not (s["owner"] == username and s["product_name"] == product_name)]
    save_sales(sales)
    return {"status": "deleted", "product": product_name}

# ════════════════════════════════════════════════════════════
# DAILY SALES ENTRY
# ════════════════════════════════════════════════════════════

@app.post("/log-sale")
def log_sale(entry: SaleEntry, username: str = Depends(get_current_user)):
    try:
        products = load_products()

        # ✅ SAFE access
        user_products = [p for p in products if p.get("owner") == username]

        product = next(
            (p for p in user_products if p.get("name") == entry.product_name),
            None
        )

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product '{entry.product_name}' not found. Add it in the Products tab first."
            )

        sales = load_sales()

        record = {
            "owner": username,
            "product_name": entry.product_name,
            "quantity_sold": entry.quantity_sold,
            "stock_level": entry.stock_level,
            "stock_added": entry.stock_added or 0.0,
            "price": product.get("price", 0),
            "supplier_cost": product.get("supplier_cost", 0),
            "date": entry.date or datetime.today().strftime("%Y-%m-%d")
        }

        sales.append(record)
        save_sales(sales)

        # ✅ SAFE access here too
        count = len([
            s for s in sales
            if s.get("owner") == username and s.get("product_name") == entry.product_name
        ])

        return {
            "status": "logged",
            "entries_for_product": count
        }

    except Exception as e:
        print("LOG-SALE ERROR:", e)
        return {"error": str(e)}

# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════

@app.get("/dashboard")
def dashboard(product_name: str, username: str = Depends(get_current_user)):
    sales         = load_sales()
    product_sales = [
        s for s in sales
        if s.get("owner") == username and s.get("product_name") == product_name
        ]

    if len(product_sales) < 2:
        return {
            "message":      f"Not enough data for '{product_name}'. Log at least 2 days of sales.",
            "total_entries": len(product_sales)
        }

    df           = pd.DataFrame(product_sales).sort_values("date").reset_index(drop=True)
    qty          = df["quantity_sold"].values
    latest       = df.iloc[-1]
    latest_stock  = float(latest["stock_level"])
    price         = float(latest["price"])
    supplier_cost = float(latest["supplier_cost"])

    avg_daily     = float(np.mean(qty[-7:]) if len(qty) >= 7 else np.mean(qty))
    days_of_supply = round(latest_stock / avg_daily, 1) if avg_daily > 0 else 99

    trend_pct = 0.0
    if len(qty) >= 6:
        recent   = np.mean(qty[-3:])
        previous = np.mean(qty[-6:-3])
        trend_pct = round(((recent - previous) / previous) * 100, 1) if previous > 0 else 0.0

    if days_of_supply < 3:
        alert       = f"Stock will run out in {days_of_supply} days. Reorder immediately!"
        alert_level = "danger"
    elif days_of_supply < 7:
        alert       = f"Stock will last ~{days_of_supply} days. Consider reordering soon."
        alert_level = "warning"
    else:
        alert       = f"Stock is sufficient for ~{days_of_supply} days."
        alert_level = "success"

    if trend_pct > 5:
        trend_msg = f"Demand is increasing by {trend_pct}% this week."
    elif trend_pct < -5:
        trend_msg = f"Demand is decreasing by {abs(trend_pct)}% this week."
    else:
        trend_msg = "Demand is stable this week."

    std          = float(np.std(qty)) if len(qty) > 1 else 10.0
    safety_stock = round(1.65 * std * np.sqrt(5))
    rop          = round(avg_daily * 5 + safety_stock)
    eoq          = round(np.sqrt((2 * avg_daily * 365 * 50) / 2))

    predicted_demand = None
    if len(qty) >= 8:
        features = {col: 0 for col in feature_cols}
        features["Lag_1"]          = float(qty[-1])
        features["Lag_7"]          = float(qty[-7])
        features["Rolling_Mean_7"] = float(np.mean(qty[-7:]))
        features["Price"]          = price
        features["Stock_Level"]    = latest_stock
        input_df = pd.DataFrame([features])[feature_cols].astype(float)
        predicted_demand = round(float(model.predict(input_df)[0]), 2)

    profit_margin    = round(price - supplier_cost, 2)
    total_profit_est = round(profit_margin * avg_daily * 30, 2)
    chart_data       = df.tail(7)[["date", "quantity_sold"]].to_dict(orient="records")

    return {
        "product":                  product_name,
        "total_entries":            len(product_sales),
        "days_of_supply":           days_of_supply,
        "avg_daily_demand":         round(avg_daily, 1),
        "predicted_demand":         predicted_demand,
        "alert":                    alert,
        "alert_level":              alert_level,
        "trend":                    trend_msg,
        "trend_pct":                trend_pct,
        "profit_margin":            profit_margin,
        "estimated_monthly_profit": total_profit_est,
        "inventory": {
            "safety_stock":   safety_stock,
            "reorder_point":  rop,
            "order_quantity": eoq
        },
        "chart_data": chart_data
    }

# ════════════════════════════════════════════════════════════
# CSV UPLOAD
# ════════════════════════════════════════════════════════════

REQUIRED_COLUMNS = ["product_name", "quantity_sold", "stock_level", "date"]

@app.post("/upload-data")
async def upload_data(file: UploadFile = File(...), username: str = Depends(get_current_user)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted.")
    contents = await file.read()
    df       = pd.read_csv(io.StringIO(contents.decode("utf-8")))

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return {
            "status":          "error",
            "message":         f"Missing columns: {missing}",
            "required_format": REQUIRED_COLUMNS
        }

    sales       = load_sales()
    new_records = df[REQUIRED_COLUMNS].dropna().to_dict(orient="records")
    for r in new_records:
        r["owner"]         = username
        r["price"]         = float(df["price"].iloc[0]) if "price" in df.columns else 0.0
        r["supplier_cost"] = 0.0
        r["stock_added"]   = 0.0
    sales.extend(new_records)
    save_sales(sales)

    return {
        "status":       "success",
        "rows_imported": len(new_records),
        "total_entries": len(sales)
    }

# ════════════════════════════════════════════════════════════
# EXPLAIN
# ════════════════════════════════════════════════════════════

@app.get("/explain")
def explain(username: str = Depends(get_current_user)):
    return {
        "explanation": [
            "Lag_1 has the highest impact — yesterday's sales strongly predict today's demand.",
            "Rolling_Mean_7 captures the weekly trend smoothly.",
            "Month captures seasonal variation across the year."
        ]
    }