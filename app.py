"""GuruFocus-style Quantitative Crystal Ball & Fundamental Value Investing Dashboard."""

from __future__ import annotations

import streamlit as st

from analysis.capital_allocation import analyze_capital_allocation, analyze_insider_activity
from analysis.crystal_ball import compute_triangulated_fair_value, run_monte_carlo_crystal_ball
from analysis.dcf import diagnose_capex_distortion, run_reverse_dcf
from analysis.decision_engine import run_decision_engine
from analysis.forensics import run_forensics_analysis
from analysis.legend_investors import evaluate_legendary_investors
from analysis.quality import run_quality_xray
from analysis.red_flags import run_red_flags_analysis
from analysis.valuation import (
    build_peer_comparison_df,
    build_target_peer_summary,
    compute_valuation_bands,
)
from analysis.valuation_models import compute_full_valuation_suite
from data.cache import cached_fetch_company, cached_fetch_peers, get_api_key_fingerprint
from data.provider import DataProviderError, load_fmp_api_key
from ui.sections import (
    render_deep_dive_expanders,
    render_disclaimer,
    render_gurufocus_summary_cockpit,
    render_legendary_investors_section,
    render_qualitative_section,
    render_sticky_summary_strip,
    render_warnings_and_banners,
)
from ui.sidebar import render_sidebar
from ui.styles import inject_custom_css

st.set_page_config(
    page_title="GuruFocus-Style Rentgen · Věštecká koule",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _parse_custom_peers(raw_text: str, exclude_ticker: str) -> list[str]:
    """Parse comma/semicolon-separated custom peer tickers."""
    cleaned = [
        tok.strip().upper()
        for tok in raw_text.replace(";", ",").split(",")
        if tok.strip()
    ]
    return [t for t in dict.fromkeys(cleaned) if t != exclude_ticker][:5]


def main() -> None:
    """Application entry point."""
    inject_custom_css()

    st.markdown("## 🔮 ValueFocus · Kvantitativní věštecká koule ve stylu GuruFocus")
    st.caption(
        "Čistě tvrdá data: 5-pilířové GF skóre, GF Value koridor, kompletní matematické modely férové ceny (DCF, Gordon, Exit Multiple, "
        "DDM, Graham, EPV, Buffett Owner Earnings s ΔWC, P/E, P/FCF, ROIC), 10 000 Monte Carlo scénářů a 6 kvalitativních kritérií."
    )

    if "active_ticker" not in st.session_state:
        st.session_state["active_ticker"] = ""

    with st.form("ticker_search_form", clear_on_submit=False):
        t_col, btn_col = st.columns([4.5, 1.3])
        with t_col:
            ticker_input = st.text_input(
                "Zadejte burzovní ticker",
                value=st.session_state["active_ticker"],
                placeholder="Např. MSFT, AAPL, GOOGL, COST, JNJ, KO, BRK-B, ASML",
                label_visibility="collapsed",
            )
        with btn_col:
            submitted = st.form_submit_button("Analyzovat akcii", type="primary", use_container_width=True)

    q_cols = st.columns([1.2, 1, 1, 1, 1, 1, 3.8])
    q_cols[0].caption("Rychlý test:")
    for idx, sample in enumerate(("MSFT", "GOOGL", "JNJ", "COST", "KO")):
        if q_cols[idx + 1].button(sample, key=f"sample_{sample}", use_container_width=True):
            st.session_state["active_ticker"] = sample
            st.rerun()

    if submitted and ticker_input.strip():
        st.session_state["active_ticker"] = ticker_input.strip().upper()

    active_ticker = st.session_state["active_ticker"].strip().upper()
    last_peers = st.session_state.get("last_auto_peers", [])
    default_g_map: dict[str, float] = st.session_state.get("default_stage1_g_map", {})
    default_g_pct = default_g_map.get(active_ticker)
    sidebar_cfg = render_sidebar(
        default_peers=last_peers,
        default_stage1_growth_pct=default_g_pct,
        ticker_key=active_ticker,
    )

    if not active_ticker:
        st.info(
            "Zadejte ticker výše a zobrazí se kompletní GuruFocus-style kokpit: 5-pilířové skóre (1–10), "
            "tachometr ocenění, GF Value pásmo, všech 13 oceňovacích vzorců, 10 000 simulací Monte Carlo "
            "a interaktivní checklist 6 nematematických kritérií."
        )
        render_disclaimer()
        return

    api_fp = get_api_key_fingerprint(load_fmp_api_key())
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0, text=f"Stahuji tvrdé výkazy pro {active_ticker}...")

    try:
        progress_bar.progress(18, text=f"Načítám výkaz zisku, rozvahu a cash flow pro {active_ticker}...")
        company = cached_fetch_company(active_ticker, api_key_fingerprint=api_fp)
        st.session_state["last_auto_peers"] = company.peers

        progress_bar.progress(42, text="Počítám ROIC, WACC, F/Z/M-Score, CapEx diagnostiku a účetní Red Flags...")
        capex_diag = diagnose_capex_distortion(company, sidebar_cfg.dcf_inputs)
        dcf_result = run_reverse_dcf(company, sidebar_cfg.dcf_inputs)
        red_flags = run_red_flags_analysis(company)
        quality = run_quality_xray(company, equity_risk_premium=sidebar_cfg.equity_risk_premium)
        forensics = run_forensics_analysis(company)

        progress_bar.progress(65, text=f"Spouštím 10 000 scénářů Monte Carlo ({sidebar_cfg.crystal_ball_horizon}Y) a všech 13 vzorců ocenění...")
        subtract_sbc = sidebar_cfg.dcf_inputs.fcf_base_type == "fcf_minus_sbc"
        monte_carlo = run_monte_carlo_crystal_ball(
            company=company,
            horizon_years=sidebar_cfg.crystal_ball_horizon,
            hurdle_rate=sidebar_cfg.dcf_inputs.discount_rate,
            subtract_sbc=subtract_sbc,
            n_simulations=10_000,
        )
        suite = compute_full_valuation_suite(
            company=company,
            dcf_params=sidebar_cfg.dcf_inputs,
            quality=quality,
            red_flags=red_flags,
            forensics=forensics,
            monte_carlo=monte_carlo,
            margin_of_safety=sidebar_cfg.margin_of_safety_target,
            aaa_yield_override_pct=sidebar_cfg.aaa_yield_override_pct,
            graham_weight_pct=sidebar_cfg.graham_weight_pct,
        )
        # Remember model's baseline Stage 1 growth for this ticker (used as slider default)
        g_map = dict(st.session_state.get("default_stage1_g_map", {}))
        g_map[active_ticker] = round(suite.default_stage1_growth * 100.0, 1)
        st.session_state["default_stage1_g_map"] = g_map
        triangulation = compute_triangulated_fair_value(
            company=company,
            dcf_params=sidebar_cfg.dcf_inputs,
            quality=quality,
            compounding=forensics.compounding,
            monte_carlo=monte_carlo,
            margin_of_safety_target=sidebar_cfg.margin_of_safety_target,
        )
        # Align decision engine's fair value & buy price directly with the full GuruFocus Valuation Suite
        if suite.gf_fair_value is not None:
            triangulation.fair_value_per_share = suite.gf_fair_value
            triangulation.max_buy_price = suite.gf_buy_price
            triangulation.upside_to_fair_value = suite.upside_pct
            triangulation.gap_to_buy_price = (
                ((suite.gf_buy_price / company.current_price) - 1.0)
                if (suite.gf_buy_price and company.current_price and company.current_price > 0)
                else None
            )

        alloc_report = analyze_capital_allocation(company)
        insider_report = analyze_insider_activity(company)
        val_bands = compute_valuation_bands(company)
        legends_report = evaluate_legendary_investors(
            company=company,
            quality=quality,
            red_flags=red_flags,
            forensics=forensics,
            suite=suite,
            insiders=insider_report,
        )

        verdict = run_decision_engine(
            company=company,
            dcf=dcf_result,
            red_flags=red_flags,
            quality=quality,
            forensics=forensics,
            monte_carlo=monte_carlo,
            triangulation=triangulation,
            insiders=insider_report,
        )

        custom_peers = _parse_custom_peers(sidebar_cfg.custom_peers_raw, exclude_ticker=company.ticker)
        peer_tickers = custom_peers if custom_peers else company.peers[:4]

        progress_bar.progress(86, text=f"Načítám srovnání s konkurencí ({', '.join(peer_tickers) or 'žádní'})...")
        peer_summaries = (
            cached_fetch_peers(tuple(peer_tickers), api_key_fingerprint=api_fp)
            if peer_tickers
            else []
        )
        target_summary = build_target_peer_summary(
            company=company,
            latest_roic=quality.latest_roic,
            rev_cagr_3y=dcf_result.cagrs.revenue_cagr_3y,
        )
        peer_df = build_peer_comparison_df(target_summary, peer_summaries)

        progress_bar.progress(100, text="Hotovo.")
        progress_placeholder.empty()
    except DataProviderError as exc:
        progress_placeholder.empty()
        st.error(f"Nepodařilo se načíst data pro ticker **{active_ticker}**: {exc}")
        render_disclaimer()
        return
    except Exception as exc:
        progress_placeholder.empty()
        st.error(f"Neočekávaná chyba při analýze tickeru **{active_ticker}**: {exc}")
        render_disclaimer()
        return

    # 1. Sticky GuruFocus Header + Banners (including smart CapEx safeguard)
    render_sticky_summary_strip(company, verdict, suite, monte_carlo)
    render_warnings_and_banners(company, capex_diag, sidebar_cfg.dcf_inputs)

    # 2. GuruFocus 5-Box Scorecards + Valuation Gauge + 1Y Target + GF Band + All Models + Monte Carlo + Forensics
    render_gurufocus_summary_cockpit(company, verdict, suite, monte_carlo, forensics)

    # 3. Legendary Investors Scorecard (Buffett, Graham, Lynch, Greenblatt, Munger/Smith + Top Holders)
    render_legendary_investors_section(company, legends_report)

    # 4. Interactive 6-Pillar Non-Mathematical Criteria Scorecard
    render_qualitative_section(company, verdict, quality, forensics, insider_report, suite)

    # 4. Collapsible Deep-Dive Expanders (LaTeX, Reverse DCF Heatmaps, Forensics, ROIC/WACC, Peers, Insiders)
    render_deep_dive_expanders(
        company=company,
        dcf=dcf_result,
        dcf_params=sidebar_cfg.dcf_inputs,
        suite=suite,
        forensics=forensics,
        red_flags=red_flags,
        quality=quality,
        val_bands=val_bands,
        peer_df=peer_df,
        peer_tickers=peer_tickers,
        alloc=alloc_report,
        insiders=insider_report,
    )
    render_disclaimer()


if __name__ == "__main__":
    main()
