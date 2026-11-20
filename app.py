import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Komplexní analýza akcie", layout="wide")
st.title("Analýza a valuace akcie z tvrdých dat")

# =============================================================================
# VYSVĚTLIVKY (TOOLTIPY) – po najetí na ikonu "?" u každého okna/sloupce
# =============================================================================
HELP = {
    "ticker": "Burzovní zkratka firmy z Yahoo Finance. Pro americké akcie např. AAPL, MSFT, NVDA; pro pražskou burzu přidej .PR (např. CEZ.PR).",
    "price": "Aktuální tržní cena jedné akcie na burze.",
    "eps_ttm": "Earnings Per Share (zisk na akcii) za posledních 12 měsíců (TTM). Udává, kolik čistého zisku firma vydělala na jednu akcii. Dole je aktuální P/E.",
    "eps_fwd": "Očekávaný zisk na akcii (Forward EPS) na příštích 12 měsíců podle konsenzu analytiků. Procento ukazuje očekávaný růst nebo pokles oproti dnešku.",
    "target_mean": "Průměrná 12měsíční cílová cena od analytiků z Wall Street. Procento ukazuje potenciál oproti aktuální ceně.",
    "dcf": "Discounted Cash Flow – odhad vnitřní hodnoty akcie z budoucích volných peněžních toků (FCF) diskontovaných sazbou CAPM, plus hotovost minus dluh.",
    "graham": "Grahamovo číslo = √(22,5 × EPS × účetní hodnota na akcii). Konzervativní strop férové ceny vhodný hlavně pro stabilní, zavedené firmy.",
    "fwd_pe_price": "Odhadovaná cena akcie za rok, pokud firma splní očekávané Forward EPS a trh ji bude dál oceňovat stejným P/E násobkem jako dnes.",
    "target_range": "Nejnižší (nejpesimističtější) a nejvyšší (nejoptimističtější) 12měsíční cílová cena od sledujících analytiků.",
    "rev_growth": "Meziroční růst tržeb (YoY). Spodní údaj (CAGR) je průměrný roční růst tržeb za poslední dostupné výroční zprávy.",
    "gross_margin": "Hrubá marže = (Tržby − přímé náklady výroby) / Tržby. Ukazuje cenovou sílu produktu a efektivitu samotné výroby či služby.",
    "op_margin": "Provozní marže = Provozní zisk / Tržby. Kolik procent z tržeb zůstane po zaplacení všech provozních nákladů (mzdy, vývoj, marketing).",
    "net_margin": "Čistá marže = Čistý zisk / Tržby. Kolik procent z každé utržené koruny/dolaru zůstane firmě jako čistý zisk po úrocích a daních.",
    "fcf_margin": "Free Cash Flow marže = FCF / Tržby. Kolik procent tržeb se skutečně přemění na volnou hotovost (na dividendy, odkupy akcií nebo splácení dluhu).",
    "debt": "Celkový krátkodobý i dlouhodobý dluh firmy z poslední rozvahy.",
    "cash": "Hotovost a krátkodobé likvidní investice, které má firma okamžitě k dispozici.",
    "net_debt_ebitda": "(Dluh − Hotovost) / EBITDA. Za kolik let provozního zisku by firma splatila čistý dluh. Záporné číslo znamená víc hotovosti než dluhu. Nad 3× roste riziko.",
    "debt_to_equity": "Poměr celkového dluhu k vlastnímu kapitálu akcionářů (v %). Vyšší číslo znamená větší zadlužení a finanční páku.",
    "current_ratio": "Běžná likvidita = Oběžná aktiva / Krátkodobé závazky. Nad 1,0 znamená, že firma bez problému pokryje závazky splatné do roka. Dole je ROE (návratnost vlastního kapitálu).",
    "val_section": "Srovnání, za jaký násobek zisků a cash flow se firma obchoduje dnes oproti vlastní historii a průměru svého sektoru. Záporné % = levnější, kladné % = dražší.",
    "col_ukazatel": "P/E = Cena / Zisk na akcii | P/FCF = Tržní kapitalizace / Volné cash flow | EV/EBITDA = Hodnota firmy včetně dluhu / Provozní zisk před odpisy.",
    "col_aktualne": "Současná hodnota ukazatele vypočtená z dnešní ceny akcie.",
    "col_hist_avg": "Průměrná hodnota ukazatele k datům posledních výročních zpráv firmy.",
    "col_vs_hist": "Procentuální rozdíl dnešního ocenění oproti historickému průměru té samé firmy.",
    "col_sektor": "Orientační benchmark celého sektoru (u P/E stažený živě ze sektorového ETF).",
    "col_vs_sektor": "Procentuální rozdíl dnešního ocenění firmy oproti průměru jejího sektoru.",
    "col_pe": "Price to Earnings – kolik dolarů/korun platíš za 1 dolar/korunu ročního čistého zisku firmy.",
    "col_pfcf": "Price to Free Cash Flow – kolik platíš za 1 jednotku volné hotovosti vygenerované firmou. Těžko se účetně zkresluje.",
    "col_ev_ebitda": "Enterprise Value / EBITDA – ocenění celé firmy (včetně dluhu, po odečtení hotovosti) vůči provoznímu zisku před odpisy. Dobré pro srovnání firem s různým dluhem.",
    "catalysts": "Automaticky vyhodnocené pozitivní faktory a rizika z tvrdých finančních metrik (růst EPS/tržeb, FCF marže, zadlužení, valuace vůči sektoru, short interest, beta).",
    "news": "Nejnovější články stažené z Yahoo Finance přímo pro danou firmu (vlevo) a pro celý její sektor přes příslušné sektorové ETF (vpravo).",
}

ticker_symbol = st.text_input(
    "Zadej ticker (např. AAPL, MSFT, GOOGL, NVDA, KO)",
    value="MSFT",
    help=HELP["ticker"],
).upper().strip()

# Mapování sektorů na US sektorové ETF (pro živé zprávy a živé sektorové P/E) + orientační sektorové mediány
SECTOR_MAP = {
    "Technology":             {"etf": "XLK",  "pe": 28.0, "pfcf": 30.0, "ev_ebitda": 20.0},
    "Communication Services": {"etf": "XLC",  "pe": 19.0, "pfcf": 20.0, "ev_ebitda": 12.0},
    "Consumer Cyclical":      {"etf": "XLY",  "pe": 22.0, "pfcf": 24.0, "ev_ebitda": 14.0},
    "Consumer Defensive":     {"etf": "XLP",  "pe": 21.0, "pfcf": 23.0, "ev_ebitda": 14.5},
    "Energy":                 {"etf": "XLE",  "pe": 12.0, "pfcf": 11.0, "ev_ebitda": 6.5},
    "Financial Services":     {"etf": "XLF",  "pe": 14.0, "pfcf": 15.0, "ev_ebitda": 11.0},
    "Healthcare":             {"etf": "XLV",  "pe": 22.0, "pfcf": 24.0, "ev_ebitda": 15.0},
    "Industrials":            {"etf": "XLI",  "pe": 21.0, "pfcf": 23.0, "ev_ebitda": 14.0},
    "Basic Materials":        {"etf": "XLB",  "pe": 17.0, "pfcf": 19.0, "ev_ebitda": 10.0},
    "Real Estate":            {"etf": "XLRE", "pe": 32.0, "pfcf": 22.0, "ev_ebitda": 18.0},
    "Utilities":              {"etf": "XLU",  "pe": 18.0, "pfcf": 20.0, "ev_ebitda": 12.0},
}

@st.cache_data(ttl=1800)
def get_all_data(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    cf = stock.cashflow
    inc = stock.income_stmt
    bs = stock.balance_sheet
    hist_prices = stock.history(period="5y")["Close"]
    news_company = stock.news or []

    try:
        rf = yf.Ticker("^TNX").history(period="5d")["Close"].iloc[-1] / 100.0
    except Exception:
        rf = 0.042

    sector = info.get("sector")
    sector_info = {}
    news_sector = []
    if sector in SECTOR_MAP:
        etf_ticker = yf.Ticker(SECTOR_MAP[sector]["etf"])
        try:
            sector_info = etf_ticker.info or {}
            news_sector = etf_ticker.news or []
        except Exception:
            pass

    return info, cf, inc, bs, hist_prices, news_company, sector_info, news_sector, rf

def calc_cagr(series):
    s = series.dropna()
    if len(s) < 2:
        return None
    newest, oldest = s.iloc[0], s.iloc[-1]
    n = len(s) - 1
    if oldest <= 0 or newest <= 0:
        return None
    return (newest / oldest) ** (1 / n) - 1

def parse_news_item(item):
    if "content" in item and isinstance(item["content"], dict):
        c = item["content"]
        title = c.get("title", "Bez titulku")
        provider = (c.get("provider") or {}).get("displayName", "Neznámý zdroj")
        link = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or "#"
        pub_date = c.get("pubDate", "")[:10]
        summary = c.get("summary", "")
    else:
        title = item.get("title", "Bez titulku")
        provider = item.get("publisher", "Neznámý zdroj")
        link = item.get("link", "#")
        ts = item.get("providerPublishTime")
        pub_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
        summary = ""
    return title, provider, link, pub_date, summary

def compute_historical_multiples(inc, cf, bs, hist_prices):
    rows = []
    if hist_prices.empty or inc.empty:
        return pd.DataFrame()

    prices_naive = hist_prices.copy()
    prices_naive.index = prices_naive.index.tz_localize(None)

    for col_date in inc.columns:
        dt = pd.Timestamp(col_date).tz_localize(None)
        valid_prices = prices_naive[prices_naive.index <= dt]
        if valid_prices.empty:
            continue
        p = float(valid_prices.iloc[-1])

        shares = None
        for key in ["Diluted Average Shares", "Basic Average Shares"]:
            if key in inc.index and pd.notna(inc.loc[key, col_date]):
                shares = float(inc.loc[key, col_date])
                break
        if not shares or shares <= 0:
            continue

        mcap = p * shares
        ni = float(inc.loc["Net Income", col_date]) if "Net Income" in inc.index and pd.notna(inc.loc["Net Income", col_date]) else None
        ebitda = float(inc.loc["EBITDA", col_date]) if "EBITDA" in inc.index and pd.notna(inc.loc["EBITDA", col_date]) else None
        fcf = float(cf.loc["Free Cash Flow", col_date]) if (not cf.empty and "Free Cash Flow" in cf.index and col_date in cf.columns and pd.notna(cf.loc["Free Cash Flow", col_date])) else None

        debt, cash = 0.0, 0.0
        if not bs.empty and col_date in bs.columns:
            if "Total Debt" in bs.index and pd.notna(bs.loc["Total Debt", col_date]):
                debt = float(bs.loc["Total Debt", col_date])
            for ckey in ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]:
                if ckey in bs.index and pd.notna(bs.loc[ckey, col_date]):
                    cash = float(bs.loc[ckey, col_date])
                    break

        ev = mcap + debt - cash
        pe = (mcap / ni) if (ni and ni > 0) else np.nan
        pfcf = (mcap / fcf) if (fcf and fcf > 0) else np.nan
        ev_ebitda = (ev / ebitda) if (ebitda and ebitda > 0) else np.nan

        rows.append({
            "Rok": dt.strftime("%Y"),
            "Cena k uzávěrce": round(p, 2),
            "P/E": round(pe, 1) if pd.notna(pe) else np.nan,
            "P/FCF": round(pfcf, 1) if pd.notna(pfcf) else np.nan,
            "EV/EBITDA": round(ev_ebitda, 1) if pd.notna(ev_ebitda) else np.nan,
        })

    return pd.DataFrame(rows).sort_values("Rok")

if not ticker_symbol:
    st.stop()

try:
    info, cf, inc, bs, hist_prices, news_company, sector_info, news_sector, rf = get_all_data(ticker_symbol)

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    currency = info.get("currency", "USD")
    name = info.get("shortName", ticker_symbol)
    sector = info.get("sector", "Neznámý sektor")
    industry = info.get("industry", "Neznámé odvětví")
    shares = info.get("sharesOutstanding")
    mcap = info.get("marketCap")

    if not price or not shares:
        st.error("Nepodařilo se načíst základní tržní data pro tento ticker.")
        st.stop()

    st.subheader(f"{name} ({ticker_symbol}) — {sector} | {industry}")

    # Společné proměnné
    eps_ttm = info.get("trailingEps")
    eps_fwd = info.get("forwardEps")
    pe_ttm = info.get("trailingPE")
    pe_fwd = info.get("forwardPE")
    ev_ebitda_curr = info.get("enterpriseToEbitda")
    bvps = info.get("bookValue")
    beta = info.get("beta") or 1.0
    cash = info.get("totalCash") or 0
    debt = info.get("totalDebt") or 0
    ebitda = info.get("ebitda")
    fcf_ttm = info.get("freeCashflow")
    revenue_ttm = info.get("totalRevenue")
    p_fcf_curr = (mcap / fcf_ttm) if (mcap and fcf_ttm and fcf_ttm > 0) else None

    rev_cagr = calc_cagr(inc.loc["Total Revenue"]) if "Total Revenue" in inc.index else None
    ni_cagr = calc_cagr(inc.loc["Net Income"]) if "Net Income" in inc.index else None
    fcf_cagr = calc_cagr(cf.loc["Free Cash Flow"]) if "Free Cash Flow" in cf.index else None
    eps_implied_growth = ((eps_fwd / eps_ttm) - 1) if (eps_ttm and eps_fwd and eps_ttm > 0) else None

    df_hist_mult = compute_historical_multiples(inc, cf, bs, hist_prices)
    hist_pe_avg = df_hist_mult["P/E"].mean() if not df_hist_mult.empty else None
    hist_pfcf_avg = df_hist_mult["P/FCF"].mean() if not df_hist_mult.empty else None
    hist_ev_ebitda_avg = df_hist_mult["EV/EBITDA"].mean() if not df_hist_mult.empty else None

    sec_bench = SECTOR_MAP.get(sector, {"etf": None, "pe": 20.0, "pfcf": 22.0, "ev_ebitda": 13.0})
    sec_pe = sector_info.get("trailingPE") or sec_bench["pe"]
    sec_pfcf = sec_bench["pfcf"]
    sec_ev_ebitda = sec_bench["ev_ebitda"]

    # --- ZÁLOŽKY ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Vnitřní hodnota & EPS",
        "Fundamenty & Zdraví",
        "Valuace (Historie vs. Sektor)",
        "Katalyzátory & Rizika",
        "Aktuální zprávy"
    ])

    # =========================================================================
    # TAB 1: VNITŘNÍ HODNOTA & EPS
    # =========================================================================
    with tab1:
        st.subheader("Aktuální stav a odhady analytiků")
        target_mean = info.get("targetMeanPrice")
        target_low = info.get("targetLowPrice")
        target_high = info.get("targetHighPrice")
        num_analysts = info.get("numberOfAnalystOpinions")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Aktuální cena", f"{price:.2f} {currency}", help=HELP["price"])
        c2.metric(
            "EPS teď (TTM)",
            f"{eps_ttm:.2f} {currency}" if eps_ttm else "N/A",
            f"P/E: {pe_ttm:.1f}" if pe_ttm else None,
            help=HELP["eps_ttm"],
        )
        c3.metric(
            "Předpokládané EPS (Forward)",
            f"{eps_fwd:.2f} {currency}" if eps_fwd else "N/A",
            f"{eps_implied_growth*100:+.1f} %" if eps_implied_growth is not None else None,
            help=HELP["eps_fwd"],
        )
        if target_mean:
            c4.metric(
                f"Cíl analytiků (n={num_analysts or '?'})",
                f"{target_mean:.2f} {currency}",
                f"{((target_mean - price)/price)*100:+.1f} %",
                help=HELP["target_mean"],
            )
        else:
            c4.metric("Cíl analytiků", "N/A", help=HELP["target_mean"])

        st.divider()
        st.subheader("Automatický výpočet vnitřní a budoucí ceny")

        erp = 0.055
        discount_rate = max(rf + beta * erp, 0.06)
        terminal_growth = 0.025
        growth_sources = [g for g in [fcf_cagr, rev_cagr, eps_implied_growth] if g is not None]
        dcf_growth = float(np.clip(np.mean(growth_sources) if growth_sources else 0.05, 0.0, 0.20))

        dcf_value = None
        if fcf_ttm and fcf_ttm > 0 and discount_rate > terminal_growth:
            pv_fcfs = sum((fcf_ttm * ((1 + dcf_growth) ** t)) / ((1 + discount_rate) ** t) for t in range(1, 6))
            fcf_y5 = fcf_ttm * ((1 + dcf_growth) ** 5)
            tv = (fcf_y5 * (1 + terminal_growth)) / (discount_rate - terminal_growth)
            dcf_value = (pv_fcfs + tv / ((1 + discount_rate) ** 5) + cash - debt) / shares

        graham_value = np.sqrt(22.5 * eps_ttm * bvps) if (eps_ttm and bvps and eps_ttm > 0 and bvps > 0) else None
        fwd_pe_price = (eps_fwd * pe_ttm) if (eps_fwd and pe_ttm and eps_fwd > 0) else None

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Vnitřní hodnota (Auto DCF)",
            f"{dcf_value:.2f} {currency}" if dcf_value else "N/A",
            f"{((dcf_value - price)/price)*100:+.1f} %" if dcf_value else None,
            help=HELP["dcf"],
        )
        m2.metric(
            "Grahamovo číslo",
            f"{graham_value:.2f} {currency}" if graham_value else "N/A",
            f"{((graham_value - price)/price)*100:+.1f} %" if graham_value else None,
            help=HELP["graham"],
        )
        m3.metric(
            "Cena dle Fwd EPS × P/E",
            f"{fwd_pe_price:.2f} {currency}" if fwd_pe_price else "N/A",
            f"{((fwd_pe_price - price)/price)*100:+.1f} %" if fwd_pe_price else None,
            help=HELP["fwd_pe_price"],
        )
        m4.metric(
            "Rozptyl cílů analytiků",
            f"{target_low:.0f} – {target_high:.0f} {currency}" if (target_low and target_high) else "N/A",
            help=HELP["target_range"],
        )

        st.caption(f"CAPM diskontní sazba: {discount_rate*100:.2f} % (Rf={rf*100:.2f} %, Beta={beta:.2f}) | Použitý růst FCF: {dcf_growth*100:.1f} %")

    # =========================================================================
    # TAB 2: FUNDAMENTÁLNÍ A FINANČNÍ ZDRAVÍ
    # =========================================================================
    with tab2:
        st.subheader("Růst, marže a volné peněžní toky (FCF)")
        rev_growth_yoy = info.get("revenueGrowth")
        gross_margin = info.get("grossMargins")
        op_margin = info.get("operatingMargins")
        net_margin = info.get("profitMargins")
        fcf_margin = (fcf_ttm / revenue_ttm) if (fcf_ttm and revenue_ttm and revenue_ttm > 0) else None

        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric(
            "Růst tržeb (YoY)",
            f"{rev_growth_yoy*100:.1f} %" if rev_growth_yoy is not None else "N/A",
            f"CAGR: {rev_cagr*100:.1f} %" if rev_cagr else None,
            help=HELP["rev_growth"],
        )
        f2.metric("Hrubá marže", f"{gross_margin*100:.1f} %" if gross_margin is not None else "N/A", help=HELP["gross_margin"])
        f3.metric("Provozní marže", f"{op_margin*100:.1f} %" if op_margin is not None else "N/A", help=HELP["op_margin"])
        f4.metric("Čistá marže", f"{net_margin*100:.1f} %" if net_margin is not None else "N/A", help=HELP["net_margin"])
        f5.metric("FCF marže", f"{fcf_margin*100:.1f} %" if fcf_margin is not None else "N/A", help=HELP["fcf_margin"])

        st.divider()
        st.subheader("Úroveň zadlužení a likvidita")
        net_debt = debt - cash
        net_debt_ebitda = (net_debt / ebitda) if (ebitda and ebitda > 0) else None
        debt_to_equity = info.get("debtToEquity")
        current_ratio = info.get("currentRatio")
        roe = info.get("returnOnEquity")

        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric("Celkový dluh", f"{debt/1e9:.2f} mld.", help=HELP["debt"])
        d2.metric("Hotovost", f"{cash/1e9:.2f} mld.", help=HELP["cash"])
        d3.metric("Čistý dluh / EBITDA", f"{net_debt_ebitda:.2f}×" if net_debt_ebitda is not None else "N/A", help=HELP["net_debt_ebitda"])
        d4.metric("Debt / Equity", f"{debt_to_equity:.1f} %" if debt_to_equity is not None else "N/A", help=HELP["debt_to_equity"])
        d5.metric(
            "Běžná likvidita (Current)",
            f"{current_ratio:.2f}" if current_ratio is not None else "N/A",
            f"ROE: {roe*100:.1f} %" if roe else None,
            help=HELP["current_ratio"],
        )

        st.divider()
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("#### Vývoj tržeb, zisku a FCF (mld.)")
            hist_fin = {}
            if "Total Revenue" in inc.index:
                hist_fin["Tržby"] = inc.loc["Total Revenue"] / 1e9
            if "Net Income" in inc.index:
                hist_fin["Čistý zisk"] = inc.loc["Net Income"] / 1e9
            if "Free Cash Flow" in cf.index:
                hist_fin["FCF"] = cf.loc["Free Cash Flow"] / 1e9
            if hist_fin:
                df_fin = pd.DataFrame(hist_fin).sort_index()
                df_fin.index = df_fin.index.strftime("%Y")
                st.bar_chart(df_fin)
        with col_g2:
            st.markdown("#### Vývoj marží v čase (%)")
            if "Total Revenue" in inc.index:
                rev_s = inc.loc["Total Revenue"]
                margins_hist = {}
                if "Gross Profit" in inc.index:
                    margins_hist["Hrubá %"] = (inc.loc["Gross Profit"] / rev_s) * 100
                if "Operating Income" in inc.index:
                    margins_hist["Provozní %"] = (inc.loc["Operating Income"] / rev_s) * 100
                if "Net Income" in inc.index:
                    margins_hist["Čistá %"] = (inc.loc["Net Income"] / rev_s) * 100
                if margins_hist:
                    df_m = pd.DataFrame(margins_hist).sort_index()
                    df_m.index = df_m.index.strftime("%Y")
                    st.line_chart(df_m)

    # =========================================================================
    # TAB 3: VALUACE (HISTORIE VS. SEKTOR)
    # =========================================================================
    with tab3:
        st.subheader(f"Srovnání násobků: Aktuálně vs. Historie firmy vs. Sektor ({sector})", help=HELP["val_section"])

        # Rychlý přehled s tooltipy pro jednotlivé poměrové ukazatele
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("P/E (TTM)", f"{pe_ttm:.1f}×" if pe_ttm else "N/A", help=HELP["col_pe"])
        v2.metric("P/E (Forward)", f"{pe_fwd:.1f}×" if pe_fwd else "N/A", help="Poměr aktuální ceny k očekávanému zisku (Forward EPS) na příštích 12 měsíců.")
        v3.metric("P/FCF", f"{p_fcf_curr:.1f}×" if p_fcf_curr else "N/A", help=HELP["col_pfcf"])
        v4.metric("EV/EBITDA", f"{ev_ebitda_curr:.1f}×" if ev_ebitda_curr else "N/A", help=HELP["col_ev_ebitda"])

        def fmt_mult(val):
            return f"{val:.1f}×" if (val is not None and pd.notna(val)) else "N/A"

        def diff_str(curr, bench):
            if curr is None or bench is None or pd.isna(curr) or pd.isna(bench) or bench == 0:
                return "N/A"
            pct = ((curr - bench) / bench) * 100
            return f"{pct:+.1f} % ({'dražší' if pct > 0 else 'levnější'})"

        sec_col = f"Sektor ({sec_bench['etf'] or 'medián'})"
        val_table = pd.DataFrame([
            {
                "Ukazatel": "P/E (TTM)",
                "Aktuálně": fmt_mult(pe_ttm),
                "Historický průměr firmy": fmt_mult(hist_pe_avg),
                "vs. Historie": diff_str(pe_ttm, hist_pe_avg),
                sec_col: fmt_mult(sec_pe),
                "vs. Sektor": diff_str(pe_ttm, sec_pe),
            },
            {
                "Ukazatel": "P/E (Forward)",
                "Aktuálně": fmt_mult(pe_fwd),
                "Historický průměr firmy": "—",
                "vs. Historie": "—",
                sec_col: fmt_mult(sec_pe),
                "vs. Sektor": diff_str(pe_fwd, sec_pe),
            },
            {
                "Ukazatel": "P/FCF",
                "Aktuálně": fmt_mult(p_fcf_curr),
                "Historický průměr firmy": fmt_mult(hist_pfcf_avg),
                "vs. Historie": diff_str(p_fcf_curr, hist_pfcf_avg),
                sec_col: fmt_mult(sec_pfcf),
                "vs. Sektor": diff_str(p_fcf_curr, sec_pfcf),
            },
            {
                "Ukazatel": "EV/EBITDA",
                "Aktuálně": fmt_mult(ev_ebitda_curr),
                "Historický průměr firmy": fmt_mult(hist_ev_ebitda_avg),
                "vs. Historie": diff_str(ev_ebitda_curr, hist_ev_ebitda_avg),
                sec_col: fmt_mult(sec_ev_ebitda),
                "vs. Sektor": diff_str(ev_ebitda_curr, sec_ev_ebitda),
            },
        ])

        st.dataframe(
            val_table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Ukazatel": st.column_config.TextColumn("Ukazatel", help=HELP["col_ukazatel"]),
                "Aktuálně": st.column_config.TextColumn("Aktuálně", help=HELP["col_aktualne"]),
                "Historický průměr firmy": st.column_config.TextColumn("Historický průměr firmy", help=HELP["col_hist_avg"]),
                "vs. Historie": st.column_config.TextColumn("vs. Historie", help=HELP["col_vs_hist"]),
                sec_col: st.column_config.TextColumn(sec_col, help=HELP["col_sektor"]),
                "vs. Sektor": st.column_config.TextColumn("vs. Sektor", help=HELP["col_vs_sektor"]),
            },
        )

        st.divider()
        st.subheader("Historický vývoj valuačních násobků k datu výročních zpráv")
        if not df_hist_mult.empty:
            c_v1, c_v2 = st.columns([1, 1.5])
            with c_v1:
                st.dataframe(
                    df_hist_mult,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "P/E": st.column_config.NumberColumn("P/E", help=HELP["col_pe"]),
                        "P/FCF": st.column_config.NumberColumn("P/FCF", help=HELP["col_pfcf"]),
                        "EV/EBITDA": st.column_config.NumberColumn("EV/EBITDA", help=HELP["col_ev_ebitda"]),
                    },
                )
            with c_v2:
                chart_df = df_hist_mult.set_index("Rok")[["P/E", "P/FCF", "EV/EBITDA"]]
                st.line_chart(chart_df)
        else:
            st.info("Pro tento ticker není dostatek historických výkazů k výpočtu násobků.")

    # =========================================================================
    # TAB 4: RŮSTOVÉ KATALYZÁTORY A HLAVNÍ RIZIKA
    # =========================================================================
    with tab4:
        st.subheader("Automatická diagnostika z tvrdých dat", help=HELP["catalysts"])
        catalysts = []
        risks = []

        if eps_implied_growth is not None:
            if eps_implied_growth > 0.12:
                catalysts.append(f"**Silná akcelerace zisku:** Analytici čekají růst EPS o **{eps_implied_growth*100:.1f} %** (z {eps_ttm:.2f} na {eps_fwd:.2f} {currency}).")
            elif eps_implied_growth < 0:
                risks.append(f"**Očekávaný pokles zisku:** Forward EPS ({eps_fwd:.2f}) je pod aktuálním TTM EPS ({eps_ttm:.2f}), což značí kontrakci ({eps_implied_growth*100:.1f} %).")

        if rev_growth_yoy is not None:
            if rev_growth_yoy > 0.10:
                catalysts.append(f"**Dvouciferný růst tržeb:** Meziroční expanze tržeb dosahuje **{rev_growth_yoy*100:.1f} %**.")
            elif rev_growth_yoy < 0:
                risks.append(f"**Klesající tržby:** Meziroční pokles tržeb o **{rev_growth_yoy*100:.1f} %** naznačuje slábnoucí poptávku nebo ztrátu tržního podílu.")

        if fcf_margin is not None:
            if fcf_margin > 0.15:
                catalysts.append(f"**Vysoká konverze na hotovost:** FCF marže **{fcf_margin*100:.1f} %** dává firmě prostor pro zpětné odkupy, dividendy nebo akvizice.")
            elif fcf_margin < 0.05:
                risks.append(f"**Nízká FCF marže ({fcf_margin*100:.1f} %):** Byznys generuje málo volné hotovosti vůči tržbám (vysoké CapEx nebo slabá ziskovost).")

        if fcf_ttm is not None and fcf_ttm < 0:
            risks.append("**Záporné Free Cash Flow:** Firma pálí hotovost a může být závislá na novém dluhu nebo ředění akcií.")

        if net_debt_ebitda is not None:
            if net_debt_ebitda < 0:
                catalysts.append(f"**Pevnostní rozvaha (Net Cash):** Hotovost ({cash/1e9:.1f} mld.) převyšuje celkový dluh ({debt/1e9:.1f} mld.) – minimální úrokové riziko.")
            elif net_debt_ebitda > 3.0:
                risks.append(f"**Vysoká zadluženost:** Čistý dluh / EBITDA je **{net_debt_ebitda:.2f}×** (nad hranicí 3× roste citlivost na úrokové sazby).")

        if pe_ttm and sec_pe:
            if pe_ttm < sec_pe * 0.85:
                catalysts.append(f"**Valuační diskont vůči sektoru:** P/E ({pe_ttm:.1f}×) je výrazně pod průměrem sektoru ({sec_pe:.1f}×) – prostor pro přecenění násobku.")
            elif pe_ttm > sec_pe * 1.35:
                risks.append(f"**Vysoká valuační prémie:** P/E ({pe_ttm:.1f}×) je vysoko nad sektorem ({sec_pe:.1f}×). Jakékoli zpomalení růstu může vést k prudké korekci.")

        if target_mean and ((target_mean - price) / price) > 0.15:
            catalysts.append(f"**Konsenzus Wall Street:** Průměrná cílová cena ({target_mean:.2f} {currency}) implikuje potenciál **{((target_mean-price)/price)*100:+.1f} %**.")

        short_pct = info.get("shortPercentOfFloat")
        if short_pct and short_pct > 0.08:
            risks.append(f"**Zvýšený zájem shortařů:** Short interest činí **{short_pct*100:.1f} %** volně obchodovaných akcií.")

        if beta > 1.4:
            risks.append(f"**Vysoká volatilita (Beta {beta:.2f}):** Akcie reaguje na výkyvy trhu výrazně prudčeji než index S&P 500.")

        col_cat, col_risk = st.columns(2)
        with col_cat:
            st.success("### Růstové katalyzátory (Co může posunout cenu výš)")
            if catalysts:
                for item in catalysts:
                    st.markdown(f"- {item}")
            else:
                st.write("Žádný výrazný kvantitativní katalyzátor z aktuálních dat nevyčnívá.")

        with col_risk:
            st.error("### Hlavní rizika (Co ohrožuje byznys a cenu)")
            if risks:
                for item in risks:
                    st.markdown(f"- {item}")
            else:
                st.write("V základních finančních metrikách nejsou detekována kritická rizika.")

        st.divider()
        with st.expander("Profil byznysu firmy (popis z Yahoo Finance)"):
            st.write(info.get("longBusinessSummary", "Popis není k dispozici."))

    # =========================================================================
    # TAB 5: AKTUÁLNÍ ZPRÁVY (FIRMA + SEKTOR)
    # =========================================================================
    with tab5:
        st.subheader("Aktuální zprávy z trhu", help=HELP["news"])
        col_n1, col_n2 = st.columns(2)

        with col_n1:
            st.markdown(f"#### Zprávy pro {name} ({ticker_symbol})")
            if news_company:
                for item in news_company[:10]:
                    title, provider, link, pub_date, summary = parse_news_item(item)
                    st.markdown(f"**[{title}]({link})**")
                    st.caption(f"{provider} | {pub_date}")
                    if summary:
                        st.write(summary[:180] + ("..." if len(summary) > 180 else ""))
                    st.divider()
            else:
                st.info("Pro tento ticker nebyly nalezeny žádné aktuální zprávy.")

        with col_n2:
            etf_name = sec_bench.get("etf")
            st.markdown(f"#### Zprávy ze sektoru: {sector}" + (f" (přes ETF {etf_name})" if etf_name else ""))
            if news_sector:
                for item in news_sector[:10]:
                    title, provider, link, pub_date, summary = parse_news_item(item)
                    st.markdown(f"**[{title}]({link})**")
                    st.caption(f"{provider} | {pub_date}")
                    if summary:
                        st.write(summary[:180] + ("..." if len(summary) > 180 else ""))
                    st.divider()
            else:
                st.info("Sektorové zprávy nejsou pro tento sektor k dispozici.")

except Exception as e:
    st.error(f"Chyba při zpracování dat: {e}")
