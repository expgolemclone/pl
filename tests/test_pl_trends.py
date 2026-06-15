from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import pl.pl_trends as pl_trends
from pl.pl_trends import (
    _compute_cagr,
    _forecast_values,
    _generate_forecast_periods,
    build_pl_trend_payload,
    main,
    render_html,
)


def _source_id(conn: sqlite3.Connection) -> int:
    conn.execute(
        """
        INSERT INTO data_sources (source_code) VALUES ('edinet_xbrl')
        ON CONFLICT(source_code) DO NOTHING
        """
    )
    return int(
        conn.execute(
            "SELECT source_id FROM data_sources WHERE source_code = 'edinet_xbrl'"
        ).fetchone()["source_id"]
    )


def _insert_pl_fact(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    period: str,
    doc_id: str,
    scope: str,
    concept: str,
    value: float,
    role_uri: str = "http://example.test/role/rol_ConsolidatedStatementOfIncome",
    dimensions_json: str = "[]",
    context_id: str = "CurrentYearDuration",
) -> None:
    conn.execute(
        """
        INSERT INTO xbrl_profit_loss_facts
            (
                ticker,
                doc_id,
                period,
                source_id,
                consolidation_scope,
                context_id,
                dimensions_json,
                concept_namespace,
                concept_name,
                role_uri,
                unit,
                unit_ref,
                value,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "4776",
            doc_id,
            period,
            source_id,
            scope,
            context_id,
            dimensions_json,
            "http://example.test/taxonomy",
            concept,
            role_uri,
            "JPY",
            "JPY",
            value,
            "2026-06-01T00:00:00+00:00",
        ),
    )


def _insert_edge(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    doc_id: str,
    parent: str,
    child: str,
    child_label: str,
    order: float,
) -> None:
    conn.execute(
        """
        INSERT INTO xbrl_statement_presentation_edges
            (
                ticker,
                doc_id,
                statement,
                source_id,
                role_uri,
                parent_namespace,
                parent_name,
                parent_label,
                child_namespace,
                child_name,
                child_order,
                child_label,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "4776",
            doc_id,
            "pl",
            source_id,
            "http://example.test/role/rol_ConsolidatedStatementOfIncome",
            "http://example.test/taxonomy",
            parent,
            parent,
            "http://example.test/taxonomy",
            child,
            order,
            child_label,
            "2026-06-01T00:00:00+00:00",
        ),
    )


_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS data_sources (
    source_id   INTEGER PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS stock_entities (
    ticker     TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    sector     TEXT NOT NULL DEFAULT '',
    market     TEXT NOT NULL DEFAULT '',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS xbrl_profit_loss_facts (
    ticker               TEXT    NOT NULL,
    doc_id               TEXT    NOT NULL,
    period               TEXT    NOT NULL,
    source_id            INTEGER NOT NULL,
    consolidation_scope  TEXT    NOT NULL,
    context_id           TEXT    NOT NULL,
    dimensions_json      TEXT    NOT NULL DEFAULT '[]',
    concept_namespace    TEXT    NOT NULL,
    concept_name         TEXT    NOT NULL,
    role_uri             TEXT    NOT NULL DEFAULT '',
    unit                 TEXT    NOT NULL,
    unit_ref             TEXT    NOT NULL,
    value                REAL,
    updated_at           TEXT    NOT NULL,
    PRIMARY KEY (
        ticker, doc_id, period, source_id, consolidation_scope,
        context_id, concept_namespace, concept_name, role_uri
    )
);

CREATE TABLE IF NOT EXISTS xbrl_statement_presentation_edges (
    ticker           TEXT    NOT NULL,
    doc_id           TEXT    NOT NULL,
    statement        TEXT    NOT NULL,
    source_id        INTEGER NOT NULL,
    role_uri         TEXT    NOT NULL DEFAULT '',
    parent_namespace TEXT    NOT NULL,
    parent_name      TEXT    NOT NULL,
    parent_label     TEXT    NOT NULL DEFAULT '',
    child_namespace  TEXT    NOT NULL,
    child_name       TEXT    NOT NULL,
    child_order      REAL    NOT NULL DEFAULT 0,
    child_label      TEXT    NOT NULL DEFAULT '',
    updated_at       TEXT    NOT NULL,
    PRIMARY KEY (
        ticker, doc_id, statement, source_id, role_uri,
        parent_namespace, parent_name, child_namespace, child_name
    )
);

CREATE VIEW stocks AS
SELECT
    ticker,
    name,
    sector,
    market,
    updated_at
FROM stock_entities;
"""


def _build_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_SQL)
    conn.execute(
        "INSERT INTO stock_entities (ticker, name, sector, market) VALUES (?, ?, ?, ?)",
        ("4776", "Cybozu", "Info", "Prime"),
    )
    source_id = _source_id(conn)
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2023-12",
        doc_id="S100OLD",
        scope="non_consolidated",
        concept="NetSales",
        value=999.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2023-12",
        doc_id="S100OLD",
        scope="consolidated",
        concept="NetSales",
        value=100.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2023-12",
        doc_id="S100OLD",
        scope="consolidated",
        concept="OldExpense",
        value=12.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2023-12",
        doc_id="S100ZZZ",
        scope="consolidated",
        concept="NetSales",
        value=101.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2023-12",
        doc_id="S100ZZZ",
        scope="consolidated",
        concept="OldExpense",
        value=13.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2024-12",
        doc_id="S100NEW",
        scope="consolidated",
        concept="NetSales",
        value=200.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2024-12",
        doc_id="S100NEW",
        scope="consolidated",
        concept="NetSales",
        value=200.0,
        role_uri="http://example.test/role/rol_StatementOfIncome",
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2024-12",
        doc_id="S100NEW",
        scope="consolidated",
        concept="SegmentProfit",
        value=30.0,
    )
    _insert_pl_fact(
        conn,
        source_id=source_id,
        period="2024-12",
        doc_id="S100NEW",
        scope="consolidated",
        concept="SegmentProfit",
        value=999.0,
        dimensions_json='[{"dimension":"axis","member":"segment"}]',
        context_id="CurrentYearDuration_Segment",
    )
    _insert_edge(
        conn,
        source_id=source_id,
        doc_id="S100NEW",
        parent="StatementOfIncomeLineItems",
        child="NetSales",
        child_label="売上高",
        order=1.0,
    )
    _insert_edge(
        conn,
        source_id=source_id,
        doc_id="S100NEW",
        parent="StatementOfIncomeLineItems",
        child="SegmentProfit",
        child_label="セグメント利益",
        order=2.0,
    )
    conn.commit()
    conn.close()


def test_build_payload_selects_consolidated_reports_and_dedupes_values(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    _build_db(db_path)
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        payload = build_pl_trend_payload(conn, ticker="4776", n_periods=2)
    finally:
        conn.close()

    assert payload["periods"] == ["2023-12", "2024-12"]
    assert [row["consolidation_scope"] for row in payload["selected_reports"]] == [
        "consolidated",
        "consolidated",
    ]
    assert payload["selected_reports"][0]["doc_id"] == "S100ZZZ"
    items = {item["concept_name"]: item for item in payload["items"]}
    assert items["NetSales"]["label"] == "売上高"
    assert items["NetSales"]["values"] == [101.0, 200.0]
    assert items["SegmentProfit"]["values"] == [None, 30.0]
    assert items["OldExpense"]["values"] == [13.0, None]

    assert payload["forecast_periods"] == ["2025-12", "2026-12"]
    assert items["NetSales"]["cagr"] is not None
    assert items["NetSales"]["forecast_values"] is not None
    assert len(items["NetSales"]["forecast_values"]) == 2


def test_display_label_covers_public_report_xbrl_concepts() -> None:
    expected = {
        "AmortizationOfBondIssuanceCostNOE": "社債発行費償却",
        "CommissionForUnderwritingSecondaryDistributionAndSolicitationForSellingAndOthersForProfessionalInvestorsORSEC": "引受・売出・私募等手数料",
        "CommissionReceivedORSEC": "受取手数料",
        "CommissionToConsigneesORSEC": "委託手数料",
        "DepreciationSGA": "減価償却費",
        "DirectorsRetirementBenefitsEL": "役員退職慰労金",
        "EquityInEarningsOfAffiliatesNOI": "持分法による投資利益",
        "FeeForOfferingSecondaryDistributionAndSolicitationForSellingAndOthersForProfessionalInvestorsORSEC": "売出・私募等に係る費用",
        "FinancialExpensesSEC": "金融費用",
        "FinancialRevenueORSEC": "金融収益",
        "GainOnBargainPurchaseIFRS": "割安購入益",
        "GainOnNegativeGoodwillEI": "負ののれん発生益",
        "GainOnReversalOfSubscriptionRightsToSharesEI": "新株予約権消滅益",
        "GainOnTransferOfBenefitObligationRelatingToEmployeesPensionFundEI": "厚生年金基金代行部分移転益",
        "IncomeBeforeMinorityInterests": "少数株主利益控除前利益",
        "IncomeTaxExpenseIFRS": "法人所得税費用",
        "InsuranceIncomeEI": "保険収入",
        "LossOnBusinessOfSubsidiariesAndAffiliatesEL": "関係会社事業損失",
        "LossOnDisasterEL": "災害損失",
        "LossOnRedemptionOfInvestmentSecuritiesEL": "投資有価証券償還損",
        "LossOnSalesOfInvestmentSecuritiesEL": "投資有価証券売却損",
        "LossOnSalesOfStocksOfSubsidiariesAndAffiliatesEL": "関係会社株式売却損",
        "MinorityInterestsInIncome": "少数株主利益",
        "NetIncome": "当期純利益",
        "NetOperatingRevenueSEC": "営業収益純額",
        "NetTradingIncomeORSEC": "トレーディング純収益",
        "OfficeCostSGA": "事務費",
        "OperatingRevenueSEC": "営業収益",
        "OtherEL": "その他特別損失",
        "OtherFeesReceivedORSEC": "その他受取手数料",
        "ProfitLossAttributableToNonControllingInterestsIFRS": "非支配持分に帰属する当期利益",
        "ProfitLossAttributableToOwnersOfParentIFRS": "親会社の所有者に帰属する当期利益",
        "ProfitLossBeforeTaxIFRS": "税引前利益",
        "ProfitLossIFRS": "当期利益",
        "ProvisionOfAllowanceForDoubtfulAccountsEL": "貸倒引当金繰入額",
        "ProvisionOfReserveForCommoditiesTransactionLiabilitiesEL": "商品取引引当金繰入額",
        "ProvisionOfReserveForFinancialProductsTransactionLiabilitiesELSEC": "金融商品取引引当金繰入額",
        "PurchaseDiscountsNOI": "仕入割引",
        "RealEstateExpensesSGASEC": "不動産費用",
        "ReversalOfReserveForCommoditiesTransactionLiabilitiesEI": "商品取引引当金戻入益",
        "ReversalOfReserveForFinancialProductsTransactionLiabilitiesEISEC": "金融商品取引引当金戻入益",
        "SalesDiscountsNOE": "売上割引",
        "ShareOfProfitLossOfInvestmentsAccountedForUsingEquityMethodIFRS": "持分法による投資損益",
        "SurrenderValueOfInsuranceEI": "保険解約返戻金",
        "TaxesAndDuesSGA": "租税公課",
        "TechnicalAdvisoryFeeNOI": "受取技術援助料",
        "TradingRelatedExpensesSGASEC": "トレーディング関連費用",
    }

    for concept_name, label in expected.items():
        assert pl_trends._display_label(concept_name, {}) == label


def test_display_label_prefers_japanese_presentation_label() -> None:
    labels = {"CompensationExpensesEL": "支払補償費"}

    assert pl_trends._display_label("CompensationExpensesEL", labels) == "支払補償費"


def test_render_html_embeds_data() -> None:
    payload = {
        "ticker": "4776",
        "name": "Cybozu",
        "source": "edinet_xbrl",
        "requested_scope": "auto",
        "periods": ["2024-12"],
        "forecast_periods": ["2025-12", "2026-12"],
        "selected_reports": [
            {
                "period": "2024-12",
                "doc_id": "S100NEW",
                "consolidation_scope": "consolidated",
                "fact_count": 1,
                "valued_count": 1,
                "role_fact_count": 1,
            }
        ],
        "items": [
            {
                "concept_name": "NetSales",
                "label": "売上高",
                "values": [200.0],
                "latest_value": 200.0,
                "non_null_count": 1,
                "min_value": 200.0,
                "max_value": 200.0,
                "total_abs_value": 200.0,
                "cagr": None,
                "forecast_values": [None, None],
            }
        ],
    }

    rendered = render_html(payload)

    assert "window.PL_TREND_DATA" in rendered
    assert "4776" in rendered
    assert "売上高" in rendered
    assert "detailChart" in rendered
    assert "forecastToggle" in rendered
    assert "forecastToggleChart" not in rendered
    assert "forecastToggleTable" not in rendered
    assert "forecast-help" not in rendered
    assert "CAGR forecast" in rendered
    assert "CAGR = (Vlast / Vfirst)^(1 / gaps) - 1" in rendered
    assert "formatCagr" in rendered
    assert "col-cagr cagr-cell" in rendered
    assert "showForecast ? `<th class=\"col-cagr cagr-cell\"" in rendered
    assert "showForecast ? `<td class=\"col-cagr cagr-cell\">" in rendered
    assert "CAGR \" + formatCagr(entry.item.cagr)" in rendered
    assert "CAGR予測を表示" not in rendered
    assert "CAGR予測を非表示" not in rendered
    assert "toggleForecast" in rendered


def test_render_html_supports_manual_multi_series_overlay() -> None:
    payload = {
        "ticker": "4776",
        "name": "Cybozu",
        "source": "edinet_xbrl",
        "requested_scope": "auto",
        "periods": ["2023-12", "2024-12"],
        "forecast_periods": ["2025-12", "2026-12"],
        "selected_reports": [
            {
                "period": "2023-12",
                "doc_id": "S100OLD",
                "consolidation_scope": "consolidated",
                "fact_count": 2,
                "valued_count": 2,
                "role_fact_count": 2,
            },
            {
                "period": "2024-12",
                "doc_id": "S100NEW",
                "consolidation_scope": "consolidated",
                "fact_count": 2,
                "valued_count": 2,
                "role_fact_count": 2,
            },
        ],
        "items": [
            {
                "concept_name": "NetSales",
                "label": "売上高",
                "values": [100.0, 200.0],
                "latest_value": 200.0,
                "non_null_count": 2,
                "min_value": 100.0,
                "max_value": 200.0,
                "total_abs_value": 300.0,
                "cagr": None,
                "forecast_values": [None, None],
            },
            {
                "concept_name": "OperatingIncome",
                "label": "営業利益",
                "values": [10.0, 30.0],
                "latest_value": 30.0,
                "non_null_count": 2,
                "min_value": 10.0,
                "max_value": 30.0,
                "total_abs_value": 40.0,
                "cagr": None,
                "forecast_values": [None, None],
            },
        ],
    }

    rendered = render_html(payload)

    assert "selectedConcepts" in rendered
    assert "toggleItemSelection" in rendered
    assert "aria-pressed" in rendered
    assert "selected-row" in rendered
    assert "scaledActual" in rendered
    assert "tooltip-row" in rendered
    assert "function selectedColor(conceptName)" in rendered
    assert 'const color = isSelected ? selectedColor(item.concept_name) : "";' in rendered
    assert "const sparkColor = isSelected ? color : inactiveSparkColor;" in rendered
    assert "sparkline(item.values, sparkColor)" in rendered
    assert "const color = selectedColor(item.concept_name);" in rendered
    assert "selectedColor(entry.item.concept_name)" in rendered
    assert "seriesColor(seriesIndex)" not in rendered
    assert "seriesColor(entry.index)" not in rendered
    assert "box-shadow: inset 4px 0 0 var(--series-color);" in rendered


def test_render_html_places_hover_details_below_chart() -> None:
    payload = {
        "ticker": "4776",
        "name": "Cybozu",
        "source": "edinet_xbrl",
        "requested_scope": "auto",
        "periods": ["2023-12", "2024-12"],
        "forecast_periods": ["2025-12", "2026-12"],
        "selected_reports": [
            {
                "period": "2023-12",
                "doc_id": "S100OLD",
                "consolidation_scope": "consolidated",
                "fact_count": 1,
                "valued_count": 1,
                "role_fact_count": 1,
            },
            {
                "period": "2024-12",
                "doc_id": "S100NEW",
                "consolidation_scope": "consolidated",
                "fact_count": 1,
                "valued_count": 1,
                "role_fact_count": 1,
            },
        ],
        "items": [
            {
                "concept_name": "NetSales",
                "label": "売上高",
                "values": [100.0, 200.0],
                "latest_value": 200.0,
                "non_null_count": 2,
                "min_value": 100.0,
                "max_value": 200.0,
                "total_abs_value": 300.0,
                "cagr": None,
                "forecast_values": [230.0, 260.0],
            }
        ],
    }

    rendered = render_html(payload)
    guide_index = rendered.index('<div id="guideLine" class="guide-line"></div>')
    tooltip_index = rendered.index('<div id="tooltip" class="tooltip" aria-live="polite"></div>')
    period_strip_index = rendered.index('<div id="periodStrip" class="period-strip"></div>')

    assert guide_index < tooltip_index < period_strip_index
    assert 'tip.classList.add("is-visible")' in rendered
    assert ".tooltip.is-visible" in rendered
    assert "tip.style.left" not in rendered
    assert "tip.style.top" not in rendered
    assert "tip.style.display" not in rendered


def test_render_html_contains_responsive_layout_guards() -> None:
    payload = {
        "ticker": "4776",
        "name": "Cybozu",
        "source": "edinet_xbrl",
        "requested_scope": "auto",
        "periods": ["2023-12", "2024-12"],
        "forecast_periods": ["2025-12", "2026-12"],
        "selected_reports": [
            {
                "period": "2023-12",
                "doc_id": "S100OLD",
                "consolidation_scope": "consolidated",
                "fact_count": 1,
                "valued_count": 1,
                "role_fact_count": 1,
            },
            {
                "period": "2024-12",
                "doc_id": "S100NEW",
                "consolidation_scope": "consolidated",
                "fact_count": 1,
                "valued_count": 1,
                "role_fact_count": 1,
            },
        ],
        "items": [
            {
                "concept_name": "NetSales",
                "label": "売上高",
                "values": [100.0, 200.0],
                "latest_value": 200.0,
                "non_null_count": 2,
                "min_value": 100.0,
                "max_value": 200.0,
                "total_abs_value": 300.0,
                "cagr": None,
                "forecast_values": [None, None],
            }
        ],
    }

    rendered = render_html(payload)

    assert "@media (max-width: 1200px)" in rendered
    assert "contain: inline-size layout paint;" in rendered
    assert "overflow-x: clip;" in rendered
    assert "ResizeObserver" in rendered


def test_main_writes_html(tmp_path: Path, capsys: object) -> None:
    db_path = tmp_path / "stocks.db"
    output_path = tmp_path / "pl.html"
    _build_db(db_path)

    rc = main(["4776", "--db", str(db_path), "--periods", "2", "--output", str(output_path), "--no-open-with-playwright"])
    captured = capsys.readouterr()

    assert rc == 0
    assert output_path.is_file()
    assert "2 periods, 3 PL items" in captured.out
    assert "売上高" in output_path.read_text(encoding="utf-8")


def test_main_can_open_html_with_playwright(
    tmp_path: Path,
    capsys: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "stocks.db"
    output_path = tmp_path / "pl.html"
    screenshot_path = tmp_path / "pl.png"
    browser_path = tmp_path / "chrome"
    browser_path.write_text("#!/bin/sh\n", encoding="utf-8")
    _build_db(db_path)
    calls: list[dict[str, object]] = []

    def fake_open_html_with_playwright(
        html_path: Path,
        *,
        screenshot_path: Path | None,
        headed: bool,
        hold_ms: int,
        browser_executable: Path | None,
        timeout_ms: int,
        viewport_width: int = 1440,
        viewport_height: int = 1000,
    ) -> pl_trends.PlaywrightOpenResult:
        calls.append(
            {
                "html_path": html_path,
                "screenshot_path": screenshot_path,
                "headed": headed,
                "hold_ms": hold_ms,
                "browser_executable": browser_executable,
                "timeout_ms": timeout_ms,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
            }
        )
        return {
            "title": "4776 Cybozu PL",
            "item_count": 3,
            "canvas_width": 900,
            "canvas_height": 500,
            "drawn_pixels": 1234,
            "screenshot_path": str(screenshot_path) if screenshot_path is not None else None,
        }

    monkeypatch.setattr(
        pl_trends,
        "open_html_with_playwright",
        fake_open_html_with_playwright,
    )

    rc = main(
        [
            "4776",
            "--db",
            str(db_path),
            "--periods",
            "2",
            "--output",
            str(output_path),
            "--open-with-playwright",
            "--playwright-screenshot",
            str(screenshot_path),
            "--playwright-headed",
            "--playwright-hold-ms",
            "250",
            "--playwright-browser-executable",
            str(browser_path),
            "--playwright-timeout-ms",
            "12345",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert output_path.is_file()
    assert calls == [
        {
            "html_path": output_path,
            "screenshot_path": screenshot_path,
            "headed": True,
            "hold_ms": 250,
            "browser_executable": browser_path,
            "timeout_ms": 12345,
            "viewport_width": 1440,
            "viewport_height": 1000,
        }
    ]
    assert "Playwright opened" in captured.out
    assert "1234 drawn canvas pixels" in captured.out
    assert f"Playwright screenshot: {screenshot_path}" in captured.out


def test_main_returns_2_for_invalid_playwright_timeout(
    tmp_path: Path,
    capsys: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "stocks.db"
    output_path = tmp_path / "pl.html"
    _build_db(db_path)
    monkeypatch.setattr(
        pl_trends,
        "open_html_with_playwright",
        lambda *args, **kwargs: pytest.fail("should not open Playwright"),
    )

    rc = main(
        [
            "4776",
            "--db",
            str(db_path),
            "--periods",
            "2",
            "--output",
            str(output_path),
            "--open-with-playwright",
            "--playwright-timeout-ms",
            "0",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "--playwright-timeout-ms must be >= 1" in captured.err


def test_main_returns_2_for_invalid_playwright_hold(
    tmp_path: Path,
    capsys: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "stocks.db"
    output_path = tmp_path / "pl.html"
    _build_db(db_path)
    monkeypatch.setattr(
        pl_trends,
        "open_html_with_playwright",
        lambda *args, **kwargs: pytest.fail("should not open Playwright"),
    )

    rc = main(
        [
            "4776",
            "--db",
            str(db_path),
            "--periods",
            "2",
            "--output",
            str(output_path),
            "--open-with-playwright",
            "--playwright-hold-ms",
            "-1",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "--playwright-hold-ms must be >= 0" in captured.err


def test_main_returns_1_for_missing_ticker(tmp_path: Path, capsys: object) -> None:
    db_path = tmp_path / "stocks.db"
    _build_db(db_path)

    rc = main(["9999", "--db", str(db_path), "--no-open-with-playwright"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "No PL XBRL facts found for ticker 9999" in captured.err


def test_main_returns_2_for_missing_db(tmp_path: Path, capsys: object) -> None:
    db_path = tmp_path / "missing.db"

    rc = main(["4776", "--db", str(db_path), "--no-open-with-playwright"])
    captured = capsys.readouterr()

    assert rc == 2
    assert f"DB not found: {db_path}" in captured.err


def test_generate_forecast_periods() -> None:
    assert _generate_forecast_periods(["2023-12", "2024-12"]) == ["2025-12", "2026-12"]
    assert _generate_forecast_periods(["2024-03"], n_forecast=3) == [
        "2025-03",
        "2026-03",
        "2027-03",
    ]
    assert _generate_forecast_periods([]) == []


def test_compute_cagr_basic() -> None:
    # 100 → 200 in 1 gap → CAGR = 100%
    cagr = _compute_cagr([100.0, 200.0])
    assert cagr is not None
    assert abs(cagr - 1.0) < 1e-9


def test_compute_cagr_multi_period() -> None:
    # 100 → 400 in 3 gaps → CAGR = (4)^(1/3) - 1
    cagr = _compute_cagr([100.0, None, None, 400.0])
    assert cagr is not None
    assert abs(cagr - (4.0 ** (1 / 3) - 1)) < 1e-9


def test_compute_cagr_returns_none_for_single_value() -> None:
    assert _compute_cagr([100.0]) is None


def test_compute_cagr_returns_none_when_first_is_zero() -> None:
    assert _compute_cagr([0.0, 200.0]) is None


def test_compute_cagr_returns_none_for_all_none() -> None:
    assert _compute_cagr([None, None]) is None


def test_forecast_values_basic() -> None:
    values = [100.0, 200.0]
    cagr = _compute_cagr(values)
    assert cagr is not None
    fc = _forecast_values(values, cagr)
    assert len(fc) == 2
    assert abs(fc[0] - 200.0 * (1 + cagr)) < 1e-6
    assert abs(fc[1] - 200.0 * (1 + cagr) ** 2) < 1e-6


def test_forecast_values_returns_none_when_cagr_is_none() -> None:
    assert _forecast_values([100.0], None) == [None, None]


def test_forecast_values_returns_none_when_all_values_are_none() -> None:
    assert _forecast_values([None, None], 0.1) == [None, None]
