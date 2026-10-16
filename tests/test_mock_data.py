"""The Douro Cellars story must be visible in the raw synthetic data."""

from mocks import douro_data as data

ZAVA, FABRIKAM, NORTHWIND, FOURTH_COFFEE = "C001", "C002", "C003", "C011"
AT_RISK = {ZAVA, FABRIKAM, NORTHWIND}


def test_there_are_ten_key_accounts_and_two_standard_ones():
    assert len(data.key_accounts()) == 10
    assert {c["customer_id"] for c in data.customers() if c["segment"] == "Standard"} == {"C011", "C012"}


def test_zava_lisboa_has_three_late_shipments_this_month():
    late = data.late_shipments(ZAVA)
    assert [s["shipment_id"] for s in late] == ["SHP-24117", "SHP-24131", "SHP-24138"]
    assert all(s["delay_days"] > 0 for s in late)


def test_late_shipments_of_standard_accounts_are_filtered_out_for_key_accounts():
    everyone = {s["customer_id"] for s in data.late_shipments()}
    key_only = {s["customer_id"] for s in data.late_shipments(key_accounts_only=True)}
    assert FOURTH_COFFEE in everyone
    assert key_only == {ZAVA}


def test_fabrikam_top_sku_is_short_with_no_complaints():
    stock = data.top_sku_stock(FABRIKAM)[0]
    assert (stock["top_sku"], stock["shortfall_cases"], stock["stock_status"]) == ("SKU-TW10", 700, "SHORTAGE")
    assert stock["next_replenishment_date"] == "2026-11-16"
    fabrikam_emails = [e for e in data.load("emails") if e["customer_id"] == FABRIKAM]
    assert not any(e["importance"] == "high" for e in fabrikam_emails)


def test_northwind_volume_is_declining_and_its_meeting_was_cancelled():
    trend = data.order_trend(NORTHWIND)[0]
    assert trend["trend_jul_to_sep_pct"] < -40
    meeting = next(m for m in data.load("meetings") if m["customer_id"] == NORTHWIND)
    assert meeting["status"] == "cancelled" and meeting["rescheduled"] is False


def test_healthy_key_accounts_show_no_risk_signal():
    healthy = {c["customer_id"] for c in data.key_accounts()} - AT_RISK
    assert len(healthy) == 7
    assert not {s["customer_id"] for s in data.late_shipments(key_accounts_only=True)} & healthy
    assert not [s for s in data.top_sku_stock() if s["customer_id"] in healthy and s["shortfall_cases"]]
    assert all(t["trend_jul_to_sep_pct"] > -10 for t in data.order_trend() if t["customer_id"] in healthy)


def test_zava_escalation_is_unanswered_and_the_qbr_is_tomorrow():
    escalation = next(e for e in data.load("emails") if e["id"] == "MSG-1001")
    assert escalation["importance"] == "high" and escalation["replied"] is False
    qbr = next(m for m in data.load("meetings") if m["id"] == "EVT-2001")
    assert qbr["start"].startswith("2026-10-20") and qbr["status"] == "scheduled"


def test_search_ontology_routes_each_topic():
    result = data.search_ontology("late shipments, stock shortages and declining order volume for key accounts")
    assert set(result["results"]) == {"late_shipments", "top_sku_stock", "order_trend"}
    assert "Zava Lisboa: 3" in result["answer"]
    assert "Fabrikam" in result["answer"] and "Northwind" in result["answer"]


def test_search_ontology_focuses_on_a_named_account():
    result = data.search_ontology("open orders for Zava")
    assert result["matched_customers"] == ["Zava Lisboa"]
    assert {o["customer_id"] for o in result["results"]["open_orders"]} == {ZAVA}


def test_work_iq_is_permission_aware():
    # Ana is not invited to Contoso's QBR (Beatriz owns that account), so Work IQ must not return it.
    results = data.retrieve("Contoso Bebidas")["results"]
    assert "EVT-2005" not in {r["id"] for r in results}


def test_work_iq_finds_the_unanswered_escalations():
    citations = [r["citation"] for r in data.retrieve("unanswered escalations or complaints")["results"]]
    assert any("URGENT: third late delivery" in c for c in citations)
    assert any("Northwind – Annual tasting" in c for c in citations)


def test_fetch_returns_the_full_email():
    item = data.fetch(["/me/messages/MSG-1001"])["items"][0]
    assert item["found"] and "supplier allocation for 2027" in item["item"]["body"]
