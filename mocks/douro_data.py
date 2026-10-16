"""Synthetic Douro Cellars data and the queries behind the mock Fabric IQ and Work IQ servers.

Everything here is deterministic: fixed JSON files in mocks/data and a fixed demo date.
The two MCP servers (fabric_iq_mcp.py, work_iq_mcp.py) are thin wrappers around these functions,
so the unit tests can check the story without starting a server.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
DEMO_TODAY = date.fromisoformat(os.environ.get("DEMO_TODAY", "2026-10-19"))
SIGNED_IN_USER = "ana.ribeiro@dourocellars.example"
LOOKBACK_DAYS = 30


@cache
def load(name: str) -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    """Lowercase and strip accents so 'São Paulo' matches 'sao paulo'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _has_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


# ============================================================================ customers


def customers() -> list[dict[str, Any]]:
    return load("customers")


def customer(customer_id: str) -> dict[str, Any]:
    return next(c for c in customers() if c["customer_id"] == customer_id)


def key_accounts() -> list[dict[str, Any]]:
    return [c for c in customers() if c["segment"] == "Key account"]


def _aliases(c: dict[str, Any]) -> set[str]:
    """'Zava Lisboa' -> {'zava lisboa', 'zava', 'c001'}; two-word brands keep both words ('wide world')."""
    name = _norm(c["name"])
    words = name.split()
    brand = " ".join(words[:2]) if words[0] in ("wide", "adventure", "fourth") else words[0]
    return {name, brand, c["customer_id"].lower()}


def find_customers(text: str) -> list[dict[str, Any]]:
    """Customers mentioned in free text, by id, full name or brand ('Zava')."""
    t = _norm(text)
    return [c for c in customers() if any(re.search(rf"\b{re.escape(a)}\b", t) for a in _aliases(c))]


# ============================================================================ Fabric IQ: ontology

ONTOLOGY = {
    "ontology": "DouroCellars",
    "description": "Business ontology for Douro Cellars, bound to OneLake tables (synthetic data).",
    "entity_types": [
        {
            "name": "Customer",
            "key": "customer_id",
            "properties": {
                "customer_id": "string", "name": "string", "country": "string", "city": "string",
                "segment": "string (Key account | Standard)", "account_owner": "string",
                "buyer_name": "string", "top_sku": "string", "annual_revenue_eur": "number",
            },
            "relationships": ["places → Order", "receives → Shipment"],
        },
        {
            "name": "Order",
            "key": "order_id",
            "properties": {
                "order_id": "string", "customer_id": "string", "order_date": "date", "sku": "string",
                "cases": "integer", "value_eur": "number", "requested_delivery_date": "date",
                "status": "string (open | in_transit | delivered)",
            },
            "relationships": ["placed_by → Customer", "fulfilled_by → Shipment", "contains → Inventory (sku)"],
        },
        {
            "name": "Shipment",
            "key": "shipment_id",
            "properties": {
                "shipment_id": "string", "order_id": "string", "customer_id": "string", "carrier": "string",
                "promised_date": "date", "delivered_date": "date | null", "eta": "date | null",
                "status": "string (delivered | in_transit | delayed)", "delay_days": "integer",
                "delay_reason": "string | null",
            },
            "relationships": ["fulfils → Order", "delivered_to → Customer"],
        },
        {
            "name": "Inventory",
            "key": "sku",
            "properties": {
                "sku": "string", "product_name": "string", "warehouse": "string", "on_hand_cases": "integer",
                "open_order_demand_cases": "integer", "projected_balance_cases": "integer",
                "next_replenishment_date": "date", "next_replenishment_cases": "integer",
            },
            "relationships": ["stocks → Order (sku)"],
        },
    ],
    "metrics": ["late_shipments_30d", "top_sku_shortfall_cases", "order_volume_trend_pct"],
}


def list_entity_types() -> dict[str, Any]:
    return ONTOLOGY


def late_shipments(customer_id: str | None = None, key_accounts_only: bool = False) -> list[dict[str, Any]]:
    """Shipments delivered late, or still open past their promised date, in the last 30 days."""
    since = DEMO_TODAY - timedelta(days=LOOKBACK_DAYS)
    key_ids = {c["customer_id"] for c in key_accounts()}
    rows = []
    for s in load("shipments"):
        if s["delay_days"] <= 0 or date.fromisoformat(s["promised_date"]) < since:
            continue
        if customer_id and s["customer_id"] != customer_id:
            continue
        if key_accounts_only and s["customer_id"] not in key_ids:
            continue
        c = customer(s["customer_id"])
        rows.append({**s, "customer_name": c["name"], "segment": c["segment"]})
    return sorted(rows, key=lambda r: r["promised_date"])


def top_sku_stock(customer_id: str | None = None) -> list[dict[str, Any]]:
    """Can each key account's open orders for its top SKU be served from current stock?

    Stock is allocated to open orders in requested-delivery-date order (first due, first served).
    """
    inventory = {i["sku"]: i for i in load("inventory")}
    open_orders = sorted((o for o in load("orders") if o["status"] == "open"), key=lambda o: o["requested_delivery_date"])
    remaining = {sku: i["on_hand_cases"] for sku, i in inventory.items()}
    allocation: dict[str, tuple[int, int]] = {}  # order_id -> (allocated, short)
    for o in open_orders:
        allocated = max(0, min(o["cases"], remaining[o["sku"]]))
        remaining[o["sku"]] -= allocated
        allocation[o["order_id"]] = (allocated, o["cases"] - allocated)

    rows = []
    for c in key_accounts():
        if customer_id and c["customer_id"] != customer_id:
            continue
        sku = c["top_sku"]
        inv = inventory[sku]
        orders = [o for o in open_orders if o["customer_id"] == c["customer_id"] and o["sku"] == sku]
        short = sum(allocation[o["order_id"]][1] for o in orders)
        rows.append({
            "customer_id": c["customer_id"], "customer_name": c["name"], "top_sku": sku,
            "product_name": inv["product_name"], "on_hand_cases": inv["on_hand_cases"],
            "open_order_cases": sum(o["cases"] for o in orders),
            "next_due_date": orders[0]["requested_delivery_date"] if orders else None,
            "shortfall_cases": short, "stock_status": "SHORTAGE" if short else "OK",
            "next_replenishment_date": inv["next_replenishment_date"],
            "next_replenishment_cases": inv["next_replenishment_cases"],
            "open_orders": [o["order_id"] for o in orders],
        })
    return rows


def order_trend(customer_id: str | None = None) -> list[dict[str, Any]]:
    """Monthly order volume (cases) for key accounts: Jul–Sep plus October month-to-date."""
    month_progress = DEMO_TODAY.day / 31
    rows = []
    for c in key_accounts():
        if customer_id and c["customer_id"] != customer_id:
            continue
        by_month: dict[str, int] = {}
        for o in load("orders"):
            if o["customer_id"] == c["customer_id"]:
                by_month[o["order_date"][:7]] = by_month.get(o["order_date"][:7], 0) + o["cases"]
        jul, sep, oct_mtd = by_month.get("2026-07", 0), by_month.get("2026-09", 0), by_month.get("2026-10", 0)
        rows.append({
            "customer_id": c["customer_id"], "customer_name": c["name"],
            "cases_by_month": {k: by_month[k] for k in sorted(by_month)},
            "trend_jul_to_sep_pct": round((sep - jul) / jul * 100, 1) if jul else None,
            "october_pace_vs_september_pct": round((oct_mtd / month_progress - sep) / sep * 100, 1) if sep else None,
        })
    return rows


def open_orders(customer_id: str | None = None) -> list[dict[str, Any]]:
    return [o for o in load("orders") if o["status"] != "delivered" and (not customer_id or o["customer_id"] == customer_id)]


TOPICS = {
    "late_shipments": ["ship", "deliver", "late", "delay", "logistic", "eta", "transit", "carrier"],
    "top_sku_stock": ["stock", "inventor", "sku", "shortage", "short", "supply", "available", "replenish", "product"],
    "order_trend": ["trend", "volume", "declin", "drop", "growth", "monthly", "history", "revenue", "decrease"],
    "open_orders": ["open order", "pending order", "backlog"],
}


def search_ontology(question: str) -> dict[str, Any]:
    """Keyword-routed stand-in for Fabric IQ's natural-language ontology search."""
    q = _norm(question)
    mentioned = find_customers(question)
    key_only = not mentioned  # a named customer is always answered, whatever its segment
    results: dict[str, Any] = {"customers": mentioned} if mentioned else {}
    answers: list[str] = []
    ids = [c["customer_id"] for c in mentioned] or [None]

    for topic, words in TOPICS.items():
        if not _has_any(q, words):
            continue
        rows: list[dict[str, Any]] = []
        for cid in ids:
            if topic == "late_shipments":
                rows += late_shipments(cid, key_accounts_only=key_only)
            elif topic == "top_sku_stock":
                rows += top_sku_stock(cid)
            elif topic == "order_trend":
                rows += order_trend(cid)
            else:
                rows += open_orders(cid)
        results[topic] = rows
        answers.append(_summarize(topic, rows))

    if not answers:  # no topic recognised: describe the customers and what can be asked
        if not mentioned:
            results["customers"] = key_accounts()
        answers.append("You can ask about late shipments, stock for top SKUs, open orders or order volume trends.")
    if mentioned:
        answers.insert(0, " ".join(f"{c['name']} is a {c['segment']} customer." for c in mentioned))

    return {
        "ontology": ONTOLOGY["ontology"], "question": question, "as_of": DEMO_TODAY.isoformat(),
        "matched_customers": [c["name"] for c in mentioned], "results": results, "answer": " ".join(answers),
    }


def _summarize(topic: str, rows: list[dict[str, Any]]) -> str:
    if topic == "late_shipments":
        by_customer: dict[str, int] = {}
        for r in rows:
            by_customer[r["customer_name"]] = by_customer.get(r["customer_name"], 0) + 1
        parts = [f"{name}: {n}" for name, n in by_customer.items()]
        return f"Late shipments in the last {LOOKBACK_DAYS} days — " + (", ".join(parts) if parts else "none") + "."
    if topic == "top_sku_stock":
        short = [f"{r['customer_name']} ({r['product_name']}, short {r['shortfall_cases']} cases)" for r in rows if r["shortfall_cases"]]
        return "Top-SKU stock shortages: " + (", ".join(short) if short else "none") + "."
    if topic == "order_trend":
        falling = [f"{r['customer_name']} ({r['trend_jul_to_sep_pct']}% Jul→Sep)" for r in rows
                   if (r["trend_jul_to_sep_pct"] or 0) <= -20]
        return "Declining order volume: " + (", ".join(falling) if falling else "none") + "."
    return f"{len(rows)} open order(s)."


# ============================================================================ Work IQ: emails, meetings, chats, people, files


def _visible(item_people: list[str]) -> bool:
    """Work IQ is permission-aware: the signed-in user only sees items they are part of."""
    return SIGNED_IN_USER in item_people


def _email_item(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "email", "id": e["id"], "url": f"/me/messages/{e['id']}", "customer_id": e["customer_id"],
        "subject": e["subject"], "from": f"{e['from_name']} <{e['from']}>", "received": e["received"],
        "importance": e["importance"], "replied": e["replied"], "snippet": e["body"][:280],
        "citation": f"Email \"{e['subject']}\" from {e['from_name']}, {e['received'][:10]}",
    }


def _meeting_item(m: dict[str, Any]) -> dict[str, Any]:
    item = {
        "type": "meeting", "id": m["id"], "url": f"/me/events/{m['id']}", "customer_id": m["customer_id"],
        "title": m["title"], "start": m["start"], "status": m["status"], "organizer": m["organizer"],
        "attendees": m["attendees"], "citation": f"Meeting \"{m['title']}\", {m['start'][:10]} ({m['status']})",
    }
    for extra in ("agenda", "cancelled_by", "cancelled_on", "cancellation_note", "rescheduled"):
        if extra in m:
            item[extra] = m[extra]
    return item


def _chat_item(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "teams_message", "id": c["id"], "url": f"/me/chats/messages/{c['id']}", "customer_id": c["customer_id"],
        "chat": c["chat"], "from": c["from_name"], "sent": c["sent"], "text": c["text"],
        "citation": f"Teams message from {c['from_name']} in \"{c['chat']}\", {c['sent'][:10]}",
    }


def _person_item(p: dict[str, Any]) -> dict[str, Any]:
    owned = [customer(cid)["name"] for cid in p.get("accounts", [])]
    return {
        "type": "person", "id": p["email"], "url": f"/users/{p['email']}", "name": p["name"], "email": p["email"],
        "job_title": p["job_title"], "department": p["department"], "accounts_owned": owned,
        "citation": f"Directory: {p['name']}, {p['job_title']}",
    }


def _file_item(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "file", "id": f["id"], "url": f["web_url"], "customer_id": f["customer_id"], "name": f["name"],
        "modified": f["modified"], "modified_by": f["modified_by"],
        "citation": f"File \"{f['name']}\", modified {f['modified'][:10]}",
    }


CAPABILITIES = ["Email", "Meetings", "TeamsMessages", "People", "OneDriveAndSharePoint"]


def retrieve(query: str, capabilities: list[str] | None = None) -> dict[str, Any]:
    """Keyword-routed stand-in for Work IQ's `retrieve` grounding tool."""
    q = _norm(query)
    caps = set(capabilities or CAPABILITIES)
    mentioned = {c["customer_id"] for c in find_customers(query)}
    escalation = _has_any(q, ["escalat", "complain", "urgent", "unanswered", "unreplied", "angry", "issue", "risk"])

    def relevant(customer_id: str | None) -> bool:
        return not mentioned or customer_id in mentioned

    items: list[dict[str, Any]] = []
    if "Email" in caps:
        for e in load("emails"):
            if _visible([e["from"], *e["to"], *e["cc"]]) and relevant(e["customer_id"]):
                external = not e["from"].endswith("@dourocellars.example")
                if escalation and not mentioned and (e["replied"] or not external):
                    continue
                items.append(_email_item(e))
    if "Meetings" in caps:
        for m in load("meetings"):
            if _visible(m["attendees"]) and relevant(m["customer_id"]):
                if escalation and not mentioned and m["status"] != "cancelled":
                    continue
                items.append(_meeting_item(m))
    if "TeamsMessages" in caps:
        items += [_chat_item(c) for c in load("chats") if relevant(c["customer_id"])]
    if "OneDriveAndSharePoint" in caps and (mentioned or _has_any(q, ["file", "deck", "document", "plan"])):
        items += [_file_item(f) for f in load("files") if relevant(f["customer_id"])]
    if "People" in caps and (mentioned or _has_any(q, ["owner", "who", "contact", "buyer"])):
        for p in load("people"):
            owns = set(p.get("accounts", [])) & mentioned
            is_buyer = p.get("customer_id") in mentioned
            if owns or is_buyer or (not mentioned and p.get("accounts")):
                items.append(_person_item(p))

    def sort_key(item: dict[str, Any]) -> str:
        return item.get("received") or item.get("start") or item.get("sent") or item.get("modified") or ""

    items.sort(key=sort_key, reverse=True)
    return {"query": query, "signed_in_user": SIGNED_IN_USER, "as_of": DEMO_TODAY.isoformat(),
            "result_count": len(items), "results": items[:25]}


def ask(question: str) -> dict[str, Any]:
    """Copilot-style answer with citations, built from `retrieve` results."""
    found = retrieve(question)["results"]
    lines = []
    for item in found[:8]:
        if item["type"] == "email":
            state = "not replied" if not item["replied"] else "replied"
            lines.append(f"- {item['citation']} [{item['importance']}, {state}]: {item['snippet'][:160]}")
        elif item["type"] == "meeting":
            lines.append(f"- {item['citation']}")
        elif item["type"] == "teams_message":
            lines.append(f"- {item['citation']}: {item['text'][:160]}")
        else:
            lines.append(f"- {item['citation']}")
    answer = "Here is what I found in your Microsoft 365 data:\n" + "\n".join(lines) if lines else "I found nothing relevant."
    return {"question": question, "answer": answer, "citations": [i["citation"] for i in found[:8]]}


def fetch(entity_urls: list[str]) -> dict[str, Any]:
    """Return full items for Graph-style paths such as /me/messages/MSG-1001 or /me/events/EVT-2001."""
    out = []
    for url in entity_urls:
        item_id = url.rstrip("/").split("/")[-1]
        match = (
            next((e for e in load("emails") if e["id"] == item_id), None)
            or next((m for m in load("meetings") if m["id"] == item_id), None)
            or next((c for c in load("chats") if c["id"] == item_id), None)
            or next((p for p in load("people") if p["email"] == item_id), None)
        )
        out.append({"url": url, "found": match is not None, "item": match})
    return {"items": out}
