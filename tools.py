import csv
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent/ "data"
INVENTORY_FILE = DATA_DIR / "inventory.csv"
INBOUND_FILE = DATA_DIR / "inbound.csv"
PO_FILE = DATA_DIR / "purchase_orders.csv"

MAX_PO_TOTAL_JMD = 500_000

PO_FIELDS = ["po_id", "date", "sku", "name", "quantity", "supplier", "unit_cost_jmd", "total_jmd", "reason"]

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding= "utf-8") as f:
        return list(csv.DictReader(f))

def _load_inventory() -> list[dict]:
    rows = _read_csv(INVENTORY_FILE)
    for r in rows:
        for key in ("quantity", "reorder_point", "reorder_qty", "unit_cost_jmd", "lead_time_days"):
            r[key] = int(r[key])
    return rows

def _inbound_by_sku() -> dict[str, int]:
    totals: dict[str, int] = {}
    for s in _read_csv(INBOUND_FILE):
        totals[s["sku"]] = totals.get(s["sku"], 0) + int(s["quantity"])
    return totals


def _ordered_by_sku() -> dict[str, int]:
    totals: dict[str, int] = {}
    for po in _read_csv(PO_FILE):
        totals[po["sku"]] = totals.get(po["sku"], 0) + int(po["quantity"])
    return totals

# ---------- inventory tools ----------

def search_items(query: str) -> list[dict]:
    """Search for items in the inventory by SKU, name or category.
    Args:
        query: The search query string.
    Returns:
        List of items with SKU, name, category, location, quantity and reorder point.
    """
    q = query.lower().strip()
    return [
        {k: item[k] for k in ("sku", "name", "category", "location", "quantity", "reorder_point")}
        for item in _load_inventory()
        if q in item["sku"].lower() or q in item["name"].lower()
        or q in item["category"].lower()     
    ]

def list_low_stock() -> list[dict]:
    """List items that are at or below their reorder point.

    Returns:
        List of items with SKU, name, quantity, reorder point, incoming quantity and whether the incoming quantity covers the reorder point.
    """   
    inbound = _inbound_by_sku()
    ordered = _ordered_by_sku()
    low = []
    for item in _load_inventory():
        if item["quantity"] <= item["reorder_point"]:
            incoming = inbound.get(item["sku"], 0) + ordered.get(item["sku"], 0)
            low.append({
                "sku": item["sku"],
                "name": item["name"],
                "quantity": item["quantity"],
                "reorder_point": item["reorder_point"],
                "incoming": incoming,
                "covered_by_incoming": item["quantity"] + incoming > item["reorder_point"],
        })
    return low


def get_inbound_shipments(sku: str = "") -> list[dict]:
    """List shipments arriving at the warehouse.

    Args:
        sku: Optional SKU to filter by. Leave empty for all shipments.

    Returns:
        Shipments with SKU, quantity, vessel and expected arrival date (eta).
    """
    shipments = _read_csv(INBOUND_FILE)
    if sku:
        shipments = [s for s in shipments if s["sku"].upper() == sku.upper()]
    return shipments

# ---------- purchasing tools ----------

def get_item_details(sku: str) -> dict:
    """Get full details for one item, including supplier, unit cost and lead time.

    Args:
        sku: The item's SKU, e.g. "WH-002".

    Returns:
        The item's details, or an error if the SKU does not exist.
    """
    for item in _load_inventory():
        if item["sku"].upper() == sku.upper():
            return item
    return {"error": f"No item with SKU {sku}"}


def create_purchase_order(sku: str, quantity: int, reason: str) -> dict:
    """Create a purchase order to restock an item from its supplier.

    A single order cannot exceed J$500,000; larger orders are refused and must
    be approved by a human manager.

    Args:
        sku: The item's SKU, e.g. "WH-002".
        quantity: How many units to order. Must be greater than zero.
        reason: One short sentence explaining why this order is needed.

    Returns:
        The purchase order that was created, or an error.
    """
    item = get_item_details(sku)
    if "error" in item:
        return item
    if quantity <= 0:
        return {"error": "Quantity must be greater than zero."}
    total = quantity * item["unit_cost_jmd"]
    if total > MAX_PO_TOTAL_JMD:
        return {"error": f"Order total J${total:,} is over the J${MAX_PO_TOTAL_JMD:,} "
                         "limit and needs a human manager's approval. Not created."}

    existing = _read_csv(PO_FILE)
    po = {
        "po_id": f"PO-{1001 + len(existing)}",
        "date": date.today().isoformat(),
        "sku": item["sku"],
        "name": item["name"],
        "quantity": quantity,
        "supplier": item["supplier"],
        "unit_cost_jmd": item["unit_cost_jmd"],
        "total_jmd": total,
        "reason": reason,
    }
    is_new_file = not PO_FILE.exists()
    with open(PO_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PO_FIELDS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(po)
    return po


def list_purchase_orders() -> list[dict]:
    """List all purchase orders created so far.

    Returns:
        Every purchase order with its SKU, quantity, supplier and total cost.
    """
    return _read_csv(PO_FILE)

def get_stock_value() -> dict:
    """Calculate the total value of all stock in the warehouse.

    Returns:
        The total stock value in JMD, plus the value broken down by category.
    """
    items = _load_inventory()
    by_category: dict[str, int] = {}
    for item in items:
        item["total_value_jmd"] = item["quantity"] * item["unit_cost_jmd"]
        by_category[item["category"]] = by_category.get(item["category"], 0) + item["total_value_jmd"]
    total_value = sum(item["total_value_jmd"] for item in items)
    return {"total_stock_value_jmd": total_value, "by_category_jmd": by_category}