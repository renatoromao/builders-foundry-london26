"""One-off generator for the Douro Cellars synthetic dataset (output is committed as JSON)."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

D = date.fromisoformat


def iso(d: date) -> str:
    return d.isoformat()


# --------------------------------------------------------------------------- products / inventory
products = {
    "SKU-VP17": ("Vintage Port 2017", 300),
    "SKU-TW10": ("10 Year Old Tawny Port", 140),
    "SKU-TW20": ("20 Year Old Tawny Port", 260),
    "SKU-DRT21": ("Douro Reserva Tinto 2021", 90),
    "SKU-RUBY": ("Fine Ruby Port", 60),
    "SKU-WHITE": ("Extra Dry White Port", 55),
    "SKU-DBR23": ("Douro Branco Reserva 2023", 70),
}

# --------------------------------------------------------------------------- customers
customers = [
    # id, name, country, city, segment, owner, buyer, buyer_email, top_sku, revenue, lead_days
    ("C001", "Zava Lisboa", "Portugal", "Lisbon", "Key account", "Ana Ribeiro",
     "Sofia Almeida", "sofia.almeida@zava-lisboa.example", "SKU-VP17", 1_850_000, 5),
    ("C002", "Fabrikam Wines London", "United Kingdom", "London", "Key account", "Ana Ribeiro",
     "James Whitfield", "james.whitfield@fabrikamwines.example", "SKU-TW10", 2_300_000, 10),
    ("C003", "Northwind Traders Hamburg", "Germany", "Hamburg", "Key account", "Ana Ribeiro",
     "Lukas Becker", "lukas.becker@northwind-hamburg.example", "SKU-DRT21", 1_400_000, 8),
    ("C004", "Contoso Bebidas São Paulo", "Brazil", "São Paulo", "Key account", "Beatriz Lopes",
     "Camila Rocha", "camila.rocha@contosobebidas.example", "SKU-RUBY", 1_650_000, 30),
    ("C005", "Wide World Importers New York", "United States", "New York", "Key account", "Tiago Martins",
     "Emily Carter", "emily.carter@wideworldimporters.example", "SKU-TW20", 2_900_000, 25),
    ("C006", "Adventure Works Cellars Tokyo", "Japan", "Tokyo", "Key account", "Beatriz Lopes",
     "Haruto Sato", "haruto.sato@adventureworks-tokyo.example", "SKU-WHITE", 1_100_000, 35),
    ("C007", "Alpine Wine House Zurich", "Switzerland", "Zurich", "Key account", "Ana Ribeiro",
     "Lena Meier", "lena.meier@alpinewinehouse.example", "SKU-TW20", 980_000, 7),
    ("C008", "Woodgrove Vins Paris", "France", "Paris", "Key account", "Tiago Martins",
     "Claire Dubois", "claire.dubois@woodgrove-vins.example", "SKU-DBR23", 1_250_000, 6),
    ("C009", "Lamna Drinks Oslo", "Norway", "Oslo", "Key account", "Beatriz Lopes",
     "Ingrid Hansen", "ingrid.hansen@lamnadrinks.example", "SKU-RUBY", 760_000, 9),
    ("C010", "Relecloud Imports Sydney", "Australia", "Sydney", "Key account", "Beatriz Lopes",
     "Oliver Smith", "oliver.smith@relecloud-imports.example", "SKU-TW20", 890_000, 40),
    ("C011", "Fourth Coffee & Wine Madrid", "Spain", "Madrid", "Standard", "Tiago Martins",
     "Javier Morales", "compras@fourthcoffee-madrid.example", "SKU-DRT21", 210_000, 5),
    ("C012", "Tailspin Bottle Shop Toronto", "Canada", "Toronto", "Standard", "Beatriz Lopes",
     "Noah Tremblay", "noah@tailspinbottles.example", "SKU-RUBY", 150_000, 28),
]
customer_rows = [
    {
        "customer_id": c[0], "name": c[1], "country": c[2], "city": c[3], "segment": c[4],
        "account_owner": c[5], "buyer_name": c[6], "buyer_email": c[7], "top_sku": c[8],
        "annual_revenue_eur": c[9], "standard_lead_time_days": c[10],
    }
    for c in customers
]

# --------------------------------------------------------------------------- orders
# Monthly volume in cases (Jul, Aug, Sep, Oct-to-date) split over two orders per month.
monthly_cases = {
    "C001": [820, 860, 900, 940],      # Zava: volume healthy, service is the problem
    "C002": [600, 650, 700, 1250],     # Fabrikam: growing, big Christmas order on TW10
    "C003": [1200, 950, 640, 180],     # Northwind: steep decline
    "C004": [700, 720, 690, 420],      # healthy accounts: October is ~61% through the month
    "C005": [1100, 1150, 1120, 680],
    "C006": [400, 420, 410, 250],
    "C007": [300, 310, 320, 195],
    "C008": [520, 500, 530, 325],
    "C009": [260, 270, 255, 155],
    "C010": [340, 350, 360, 220],
    "C011": [90, 85, 95, 58],
    "C012": [60, 65, 62, 38],
}
secondary_sku = {
    "C001": "SKU-DRT21", "C002": "SKU-RUBY", "C003": "SKU-WHITE", "C004": "SKU-DBR23",
    "C005": "SKU-DBR23", "C006": "SKU-RUBY", "C007": "SKU-VP17", "C008": "SKU-RUBY",
    "C009": "SKU-WHITE", "C010": "SKU-DRT21", "C011": "SKU-RUBY", "C012": "SKU-WHITE",
}
months = [(2026, 7), (2026, 8), (2026, 9), (2026, 10)]
TODAY = D("2026-10-19")

orders = []
shipments = []
order_no = 50100
ship_no = 24000
cust_by_id = {c["customer_id"]: c for c in customer_rows}

# Story overrides for Zava Lisboa (3 late shipments) and others keyed by (customer, month, slot)
story_shipments = {
    # Zava Lisboa: three late shipments this month
    ("C001", 10, 0): dict(promised="2026-10-05", delivered="2026-10-10", eta=None, status="delivered",
                          reason="Warehouse picking backlog at Vila Nova de Gaia", carrier="TransDouro Logística"),
    ("C001", 9, 1): dict(promised="2026-10-12", delivered=None, eta="2026-10-21", status="in_transit",
                         reason="Carrier capacity shortage (TransDouro Logística)", carrier="TransDouro Logística"),
    ("C001", 10, 1): dict(promised="2026-10-16", delivered=None, eta="2026-10-23", status="delayed",
                          reason="Excise e-AD document rejected; resubmitted 2026-10-17", carrier="TransDouro Logística"),
    # Wide World Importers: one minor late delivery last month, resolved
    ("C005", 8, 1): dict(promised="2026-09-14", delivered="2026-09-15", eta=None, status="delivered",
                         reason="Customs inspection at Port Newark", carrier="Atlantic Reefer Lines"),
    # Fourth Coffee Madrid (standard account): one late delivery
    ("C011", 10, 0): dict(promised="2026-10-09", delivered="2026-10-13", eta=None, status="delivered",
                          reason="Carrier capacity shortage (Ibérica Express)", carrier="Ibérica Express"),
}

carriers = {
    "Portugal": "TransDouro Logística", "Spain": "Ibérica Express", "France": "Ibérica Express",
    "Germany": "Rhein Cargo", "Switzerland": "Rhein Cargo", "Norway": "Nordic Freight",
    "United Kingdom": "Channel Freight", "United States": "Atlantic Reefer Lines",
    "Canada": "Atlantic Reefer Lines", "Brazil": "Atlantic Reefer Lines",
    "Japan": "Pacific Wine Shipping", "Australia": "Pacific Wine Shipping",
}

for cid, vols in monthly_cases.items():
    c = cust_by_id[cid]
    lead = c["standard_lead_time_days"]
    for (year, month), cases in zip(months, vols):
        split = [cases // 2, cases - cases // 2]
        for slot, qty in enumerate(split):
            order_day = 2 if slot == 0 else 16
            if month == 10 and slot == 1 and cid != "C001":
                order_day = 14
            order_date = date(year, month, order_day)
            sku = c["top_sku"] if slot == 0 else secondary_sku[cid]
            # Fabrikam's Christmas order: 1,100 cases of TW10 due 30 Oct
            if cid == "C002" and month == 10:
                sku = "SKU-TW10" if slot == 1 else "SKU-RUBY"
                qty = 1100 if slot == 1 else 150
            # Zava's Christmas Vintage Port order is the delayed one
            if cid == "C001" and month == 10 and slot == 1:
                sku = "SKU-VP17"
                order_date = D("2026-10-06")
            if cid == "C001" and month == 9 and slot == 1:
                order_date = D("2026-09-29")
            if cid == "C001" and month == 10 and slot == 0:
                order_date = D("2026-10-01")
            requested = order_date + timedelta(days=lead)
            if cid == "C002" and month == 10 and slot == 1:
                requested = D("2026-10-30")
            order_no += 1
            oid = f"ORD-{order_no}"
            key = (cid, month, slot)
            story = story_shipments.get(key)
            if story:
                requested = D(story["promised"])
            delivered_flag = requested < TODAY or story is not None
            status = "delivered" if requested < TODAY else "open"
            if story:
                status = "delivered" if story["status"] == "delivered" else "in_transit"
            if not delivered_flag:
                status = "open"
            unit = products[sku][1]
            orders.append({
                "order_id": oid, "customer_id": cid, "order_date": iso(order_date), "sku": sku,
                "cases": qty, "value_eur": qty * unit, "requested_delivery_date": iso(requested), "status": status,
            })
            if not delivered_flag:
                continue
            ship_no += 1
            sid = f"SHP-{ship_no}"
            if story:
                promised = D(story["promised"])
                delivered = D(story["delivered"]) if story["delivered"] else None
                eta = D(story["eta"]) if story["eta"] else None
                end = delivered or eta
                shipments.append({
                    "shipment_id": sid, "order_id": oid, "customer_id": cid, "carrier": story["carrier"],
                    "ship_date": iso(promised - timedelta(days=max(2, lead - 1))), "promised_date": iso(promised),
                    "delivered_date": iso(delivered) if delivered else None, "eta": iso(eta) if eta else None,
                    "status": story["status"], "delay_days": (end - promised).days, "delay_reason": story["reason"],
                })
            else:
                shipments.append({
                    "shipment_id": sid, "order_id": oid, "customer_id": cid, "carrier": carriers[c["country"]],
                    "ship_date": iso(requested - timedelta(days=max(2, lead - 1))), "promised_date": iso(requested),
                    "delivered_date": iso(requested - timedelta(days=1 if slot else 0)), "eta": None,
                    "status": "delivered", "delay_days": 0, "delay_reason": None,
                })

# Wide World Importers: a small 10 Year Tawny order due before Fabrikam's (takes 120 of the 520 cases)
order_no += 1
orders.append({
    "order_id": f"ORD-{order_no}", "customer_id": "C005", "order_date": "2026-10-09", "sku": "SKU-TW10",
    "cases": 120, "value_eur": 120 * products["SKU-TW10"][1], "requested_delivery_date": "2026-10-26", "status": "open",
})

# Rename the Zava story shipment IDs to the ones used in emails/chats
rename = {}
zava_late = [s for s in shipments if s["customer_id"] == "C001" and s["delay_days"] > 0]
zava_late.sort(key=lambda s: s["promised_date"])
for s, new_id in zip(zava_late, ["SHP-24117", "SHP-24131", "SHP-24138"]):
    rename[s["shipment_id"]] = new_id
for s in shipments:
    s["shipment_id"] = rename.get(s["shipment_id"], s["shipment_id"])

# --------------------------------------------------------------------------- inventory
open_by_sku: dict[str, int] = {}
for o in orders:
    if o["status"] == "open":
        open_by_sku[o["sku"]] = open_by_sku.get(o["sku"], 0) + o["cases"]

inventory_spec = {
    # sku: on_hand, reorder_point, weekly_demand, next_replenishment_date, next_replenishment_cases
    "SKU-VP17": (2400, 600, 160, "2027-01-15", 1200),
    "SKU-TW10": (520, 900, 260, "2026-11-16", 1500),
    "SKU-TW20": (1600, 400, 90, "2026-12-01", 600),
    "SKU-DRT21": (4800, 1200, 420, "2026-11-02", 3000),
    "SKU-RUBY": (5200, 1500, 520, "2026-10-28", 4000),
    "SKU-WHITE": (2100, 500, 140, "2026-11-09", 1000),
    "SKU-DBR23": (1900, 500, 150, "2026-11-23", 1200),
}
inventory = []
for sku, (on_hand, rop, weekly, nxt, nxt_q) in inventory_spec.items():
    allocated = open_by_sku.get(sku, 0)
    inventory.append({
        "sku": sku, "product_name": products[sku][0], "warehouse": "Vila Nova de Gaia",
        "on_hand_cases": on_hand, "open_order_demand_cases": allocated,
        "projected_balance_cases": on_hand - allocated, "reorder_point_cases": rop,
        "weekly_demand_cases": weekly, "next_replenishment_date": nxt,
        "next_replenishment_cases": nxt_q, "unit_price_eur_per_case": products[sku][1],
    })

# --------------------------------------------------------------------------- Work IQ: people
ME = "ana.ribeiro@dourocellars.example"
people = [
    {"name": "Ana Ribeiro", "email": ME, "job_title": "Key Account Manager", "department": "Sales – Key Accounts",
     "is_signed_in_user": True, "accounts": ["C001", "C002", "C003", "C007"]},
    {"name": "Tiago Martins", "email": "tiago.martins@dourocellars.example", "job_title": "Key Account Manager",
     "department": "Sales – Key Accounts", "accounts": ["C005", "C008", "C011"]},
    {"name": "Beatriz Lopes", "email": "beatriz.lopes@dourocellars.example", "job_title": "Key Account Manager",
     "department": "Sales – Key Accounts", "accounts": ["C004", "C006", "C009", "C010", "C012"]},
    {"name": "Rui Costa", "email": "rui.costa@dourocellars.example", "job_title": "Logistics Lead",
     "department": "Operations", "accounts": []},
    {"name": "Pedro Nunes", "email": "pedro.nunes@dourocellars.example", "job_title": "Supply Planning Manager",
     "department": "Operations", "accounts": []},
]
for c in customer_rows:
    people.append({"name": c["buyer_name"], "email": c["buyer_email"], "job_title": "Buyer",
                   "department": c["name"], "is_external": True, "customer_id": c["customer_id"]})
for p in people:
    if p["name"] == "Sofia Almeida":
        p["job_title"] = "Head of Purchasing"
    if p["name"] == "Lukas Becker":
        p["job_title"] = "Purchasing Director"
    if p["name"] == "James Whitfield":
        p["job_title"] = "Category Buyer – Fortified Wines"

# --------------------------------------------------------------------------- Work IQ: emails
emails = [
    {
        "id": "MSG-1001", "conversation_id": "CONV-ZAVA-DELAYS", "customer_id": "C001",
        "received": "2026-10-16T17:42:00+01:00", "from": "sofia.almeida@zava-lisboa.example",
        "from_name": "Sofia Almeida", "to": [ME], "cc": ["rui.costa@dourocellars.example"],
        "subject": "URGENT: third late delivery this month – Christmas range at risk",
        "importance": "high", "is_read": True, "replied": False,
        "body": (
            "Ana,\n\nThis is the third delivery from Douro Cellars that arrives late this month "
            "(SHP-24117, SHP-24131 and now SHP-24138 with our Vintage Port 2017 for the Christmas range). "
            "Our Christmas range launches in 87 stores on 1 November and the Vintage Port shelf space is still empty.\n\n"
            "Before our QBR on Tuesday I need a written recovery plan with confirmed delivery dates. "
            "If we cannot rely on your dates, we will have to review our supplier allocation for 2027.\n\n"
            "Regards,\nSofia Almeida\nHead of Purchasing, Zava Lisboa"
        ),
    },
    {
        "id": "MSG-0996", "conversation_id": "CONV-ZAVA-DELAYS", "customer_id": "C001",
        "received": "2026-10-10T09:15:00+01:00", "from": "sofia.almeida@zava-lisboa.example",
        "from_name": "Sofia Almeida", "to": [ME], "cc": [],
        "subject": "Delivery SHP-24117 arrived 5 days late",
        "importance": "normal", "is_read": True, "replied": True,
        "body": "Hi Ana, the delivery for SHP-24117 only arrived today, 5 days after the promised date. "
                "Please make sure the next ones arrive on time. Sofia",
    },
    {
        "id": "MSG-0997", "conversation_id": "CONV-ZAVA-DELAYS", "customer_id": "C001",
        "received": "2026-10-10T11:02:00+01:00", "from": ME, "from_name": "Ana Ribeiro",
        "to": ["sofia.almeida@zava-lisboa.example"], "cc": [],
        "subject": "RE: Delivery SHP-24117 arrived 5 days late",
        "importance": "normal", "is_read": True, "replied": False,
        "body": "Hi Sofia, I'm sorry about the delay – we had a picking backlog at our Gaia warehouse. "
                "It's resolved and your next deliveries are on track. Ana",
    },
    {
        "id": "MSG-1002", "conversation_id": "CONV-FAB-XMAS", "customer_id": "C002",
        "received": "2026-10-14T10:20:00+01:00", "from": "james.whitfield@fabrikamwines.example",
        "from_name": "James Whitfield", "to": [ME], "cc": [],
        "subject": "Christmas campaign – confirming 1,100 cases of 10 Year Tawny for 30 Oct",
        "importance": "normal", "is_read": True, "replied": True,
        "body": "Hi Ana, confirming our Christmas order: 1,100 cases of 10 Year Old Tawny for delivery on 30 October. "
                "Our in-store tasting campaign starts on 9 November across 140 shops – the team is excited! James",
    },
    {
        "id": "MSG-1003", "conversation_id": "CONV-FAB-XMAS", "customer_id": "C002",
        "received": "2026-10-14T12:05:00+01:00", "from": ME, "from_name": "Ana Ribeiro",
        "to": ["james.whitfield@fabrikamwines.example"], "cc": [],
        "subject": "RE: Christmas campaign – confirming 1,100 cases of 10 Year Tawny for 30 Oct",
        "importance": "normal", "is_read": True, "replied": False,
        "body": "Thanks James, order received. Looking forward to the campaign! Ana",
    },
    {
        "id": "MSG-1004", "conversation_id": "CONV-NW-TASTING", "customer_id": "C003",
        "received": "2026-10-13T08:30:00+01:00", "from": "lukas.becker@northwind-hamburg.example",
        "from_name": "Lukas Becker", "to": [ME], "cc": [],
        "subject": "Canceled: Northwind – Annual tasting & 2027 planning",
        "importance": "normal", "is_read": True, "replied": False,
        "body": "Hi Ana, I have to cancel our tasting and 2027 planning on 15 October because of an internal "
                "restructuring of our purchasing team. I will come back to you. Lukas",
    },
    {
        "id": "MSG-0950", "conversation_id": "CONV-NW-Q3", "customer_id": "C003",
        "received": "2026-08-28T15:10:00+01:00", "from": "lukas.becker@northwind-hamburg.example",
        "from_name": "Lukas Becker", "to": [ME], "cc": [],
        "subject": "September order",
        "importance": "normal", "is_read": True, "replied": True,
        "body": "Hi Ana, please find our September order attached. We are reducing volumes a bit while we review "
                "our range for 2027. Best, Lukas",
    },
    {
        "id": "MSG-1005", "conversation_id": "CONV-PLAN-TW10", "customer_id": None,
        "received": "2026-10-15T16:45:00+01:00", "from": "pedro.nunes@dourocellars.example",
        "from_name": "Pedro Nunes", "to": [ME, "tiago.martins@dourocellars.example"], "cc": [],
        "subject": "Heads-up: 10 Year Tawny bottling run moved to 16 Nov",
        "importance": "normal", "is_read": False, "replied": False,
        "body": "Hi both, the next 10 Year Old Tawny bottling run moved to 16 November (glass supplier delay). "
                "Free stock is tight until then – please check big open orders. Pedro",
    },
    {
        "id": "MSG-1006", "conversation_id": "CONV-FC-LATE", "customer_id": "C011",
        "received": "2026-10-15T09:00:00+01:00", "from": "compras@fourthcoffee-madrid.example",
        "from_name": "Javier Morales", "to": ["tiago.martins@dourocellars.example"], "cc": [ME],
        "subject": "Pedido entregado con retraso / late delivery",
        "importance": "normal", "is_read": True, "replied": False,
        "body": "Hola, our last order arrived 4 days late. Please confirm the next delivery date. Javier",
    },
    {
        "id": "MSG-0980", "conversation_id": "CONV-WWI-FIX", "customer_id": "C005",
        "received": "2026-09-16T14:00:00+01:00", "from": "emily.carter@wideworldimporters.example",
        "from_name": "Emily Carter", "to": ["tiago.martins@dourocellars.example"], "cc": [ME],
        "subject": "Thanks for the quick fix",
        "importance": "normal", "is_read": True, "replied": True,
        "body": "Hi Tiago, the delivery came one day late because of customs, but your team handled it well. "
                "All good on our side. Emily",
    },
    {
        "id": "MSG-1007", "conversation_id": "CONV-ALP-NOV", "customer_id": "C007",
        "received": "2026-10-12T10:00:00+01:00", "from": "lena.meier@alpinewinehouse.example",
        "from_name": "Lena Meier", "to": [ME], "cc": [],
        "subject": "November order and QBR date",
        "importance": "normal", "is_read": True, "replied": True,
        "body": "Hi Ana, November order as usual – and 4 November works for our QBR. Lena",
    },
    {
        "id": "MSG-1008", "conversation_id": "CONV-CTS-QBR", "customer_id": "C004",
        "received": "2026-10-09T13:30:00+01:00", "from": "camila.rocha@contosobebidas.example",
        "from_name": "Camila Rocha", "to": ["beatriz.lopes@dourocellars.example"], "cc": [ME],
        "subject": "Q4 forecast",
        "importance": "normal", "is_read": True, "replied": True,
        "body": "Hi Beatriz, our Q4 forecast is in line with last year. See you at the QBR on 29 Oct. Camila",
    },
]

# --------------------------------------------------------------------------- Work IQ: meetings
meetings = [
    {"id": "EVT-2001", "customer_id": "C001", "title": "Zava Lisboa – Q4 Quarterly Business Review",
     "start": "2026-10-20T10:00:00+01:00", "end": "2026-10-20T11:00:00+01:00", "organizer": ME,
     "attendees": [ME, "sofia.almeida@zava-lisboa.example", "rui.costa@dourocellars.example"],
     "location": "Zava Lisboa HQ, Lisbon / Microsoft Teams", "status": "scheduled",
     "agenda": "Q3 performance, Christmas range readiness, 2027 supplier allocation"},
    {"id": "EVT-2002", "customer_id": "C003", "title": "Northwind – Annual tasting & 2027 planning",
     "start": "2026-10-15T14:00:00+02:00", "end": "2026-10-15T16:00:00+02:00", "organizer": ME,
     "attendees": [ME, "lukas.becker@northwind-hamburg.example"], "location": "Northwind Traders, Hamburg",
     "status": "cancelled", "cancelled_by": "lukas.becker@northwind-hamburg.example",
     "cancelled_on": "2026-10-13", "cancellation_note": "Internal restructuring of the purchasing team",
     "rescheduled": False},
    {"id": "EVT-2003", "customer_id": "C002", "title": "Fabrikam – Christmas campaign sync",
     "start": "2026-10-27T15:00:00+00:00", "end": "2026-10-27T15:30:00+00:00", "organizer": ME,
     "attendees": [ME, "james.whitfield@fabrikamwines.example"], "location": "Microsoft Teams",
     "status": "scheduled", "agenda": "Delivery of the 1,100-case 10 Year Tawny order, tasting campaign"},
    {"id": "EVT-2004", "customer_id": "C005", "title": "Wide World Importers – monthly check-in",
     "start": "2026-10-22T15:00:00+01:00", "end": "2026-10-22T15:30:00+01:00",
     "organizer": "tiago.martins@dourocellars.example",
     "attendees": ["tiago.martins@dourocellars.example", "emily.carter@wideworldimporters.example", ME],
     "location": "Microsoft Teams", "status": "scheduled", "agenda": "Holiday season volumes"},
    {"id": "EVT-2005", "customer_id": "C004", "title": "Contoso Bebidas – Q4 QBR",
     "start": "2026-10-29T14:00:00+01:00", "end": "2026-10-29T15:00:00+01:00",
     "organizer": "beatriz.lopes@dourocellars.example",
     "attendees": ["beatriz.lopes@dourocellars.example", "camila.rocha@contosobebidas.example"],
     "location": "Microsoft Teams", "status": "scheduled", "agenda": "Q4 forecast, 2027 range"},
    {"id": "EVT-2006", "customer_id": "C007", "title": "Alpine Wine House – Q4 QBR",
     "start": "2026-11-04T10:00:00+01:00", "end": "2026-11-04T11:00:00+01:00", "organizer": ME,
     "attendees": [ME, "lena.meier@alpinewinehouse.example"], "location": "Zurich", "status": "scheduled",
     "agenda": "Q3 review, Christmas sell-out"},
]

# --------------------------------------------------------------------------- Work IQ: Teams chats
chats = [
    {"id": "CHAT-3001", "customer_id": "C001", "chat": "Ana Ribeiro / Rui Costa",
     "sent": "2026-10-17T16:05:00+01:00", "from": "rui.costa@dourocellars.example", "from_name": "Rui Costa",
     "text": "Zava update: SHP-24131 ETA 21 Oct. SHP-24138 (Vintage Port) e-AD resubmitted, earliest 23 Oct. "
             "Option: express road freight for €1,350 gets SHP-24138 to Lisbon on 21 Oct if you approve today."},
    {"id": "CHAT-3002", "customer_id": "C002", "chat": "Key Accounts – Ops (channel)",
     "sent": "2026-10-15T17:10:00+01:00", "from": "pedro.nunes@dourocellars.example", "from_name": "Pedro Nunes",
     "text": "10 Year Tawny: only ~400 cases free until the 16 Nov bottling run. Fabrikam's 1,100 cases for "
             "30 Oct can't be fully covered – we could ship 400 now and the rest on 18 Nov, or offer 20 Year Tawny."},
    {"id": "CHAT-3003", "customer_id": "C003", "chat": "Ana Ribeiro / Tiago Martins",
     "sent": "2026-10-14T11:20:00+01:00", "from": "tiago.martins@dourocellars.example", "from_name": "Tiago Martins",
     "text": "FYI Northwind is restructuring purchasing – I heard their new category manager is talking to other "
             "Port houses for 2027."},
]

# --------------------------------------------------------------------------- Work IQ: files
files = [
    {"id": "FILE-4001", "customer_id": "C001", "name": "Zava Lisboa – QBR Q4 2026 (draft).pptx",
     "modified": "2026-10-16T18:30:00+01:00", "modified_by": ME,
     "web_url": "https://dourocellars.sharepoint.example/sites/KeyAccounts/Zava/QBR-Q4-2026.pptx"},
    {"id": "FILE-4002", "customer_id": None, "name": "Christmas allocation plan 2026.xlsx",
     "modified": "2026-10-15T17:00:00+01:00", "modified_by": "pedro.nunes@dourocellars.example",
     "web_url": "https://dourocellars.sharepoint.example/sites/Ops/Christmas-allocation-2026.xlsx"},
]


def dump(name: str, rows: object) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


dump("customers", customer_rows)
dump("orders", orders)
dump("shipments", shipments)
dump("inventory", inventory)
dump("people", people)
dump("emails", emails)
dump("meetings", meetings)
dump("chats", chats)
dump("files", files)
print("orders", len(orders), "shipments", len(shipments))
print([s for s in shipments if s["delay_days"]])
print([i for i in inventory if i["sku"] == "SKU-TW10"])
