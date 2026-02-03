import os
import socket
import math
import re
import html as html_lib
import urllib.request
from dotenv import load_dotenv
from brapi import Brapi
import yfinance as yf
import yfinance.cache as yf_cache
import pandas_ta as ta
import pandas as pd


load_dotenv()

DEFAULT_TIMEOUT = 15
_BRAPI_CLIENT = None
INVESTIDOR10_BASE_URL = "https://investidor10.com.br/fiis"


def _load_price_tolerance():
    try:
        return float(os.getenv("PRICE_MATCH_TOLERANCE", "0.02"))
    except Exception:
        return 0.02


PRICE_MATCH_TOLERANCE = _load_price_tolerance()


def _env_truthy(name, default=True):
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return default

def _parse_pt_number(value):
    if value is None:
        return float("nan")
    text = str(value).strip()
    if not text:
        return float("nan")
    text = text.replace("R$", "").strip()
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return float("nan")

def _parse_brl_value(text):
    if not text:
        return float("nan")
    match = re.search(r"([0-9\.\,]+)\s*(milh(?:ões)?|mi|m|bilh(?:ões)?|bi|b)?", text, re.IGNORECASE)
    if not match:
        return float("nan")
    number = _parse_pt_number(match.group(1))
    if math.isnan(number):
        return float("nan")
    suffix = (match.group(2) or "").lower()
    if suffix in {"bilh", "bilhões", "bi", "b"}:
        return number * 1_000_000_000
    if suffix in {"milh", "milhões", "mi", "m"}:
        return number * 1_000_000
    return number

def _strip_html(raw_html):
    if not raw_html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _as_float(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return float("nan")
    if isinstance(value, pd.Series):
        if value.empty: return float("nan")
        value = value.iloc[-1]
    try:
        return float(value)
    except:
        return float("nan")

def _format_currency(value):
    if math.isnan(value): return "N/A"
    if value >= 1_000_000: return f"R$ {value/1_000_000:.1f}M"
    if value >= 1_000: return f"R$ {value/1_000:.1f}K"
    return f"R$ {value:.2f}"

def _normalize_columns(df, symbol):
    if not isinstance(df.columns, pd.MultiIndex):
        return df
    if symbol in df.columns.get_level_values(-1):
        return df.xs(symbol, axis=1, level=-1)
    return df.droplevel(-1, axis=1)

def _prepare_yfinance_cache():
    cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    yf_cache.set_cache_location(cache_dir)
    socket.setdefaulttimeout(DEFAULT_TIMEOUT)

def _get_brapi_client():
    global _BRAPI_CLIENT
    if _BRAPI_CLIENT is not None:
        return _BRAPI_CLIENT
    token = os.getenv("BRAPI_TOKEN") or os.getenv("BRAPI_API_KEY")
    try:
        _BRAPI_CLIENT = Brapi(api_key=token) if token else Brapi()
    except Exception:
        _BRAPI_CLIENT = None
    return _BRAPI_CLIENT

def _brapi_get(data, *keys):
    if data is None:
        return None
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                return data[key]
        return None
    for key in keys:
        if hasattr(data, key):
            return getattr(data, key)
    return None

def _brapi_to_dict(item):
    if item is None:
        return None
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__dict__"):
        return item.__dict__
    return None

def _request_html(url, timeout=DEFAULT_TIMEOUT):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None

def _fetch_investidor10_html(ticker):
    if not _env_truthy("USE_INVESTIDOR10", default=True):
        return None
    url = f"{INVESTIDOR10_BASE_URL}/{ticker.lower()}/"
    return _request_html(url)

def _extract_investidor10_metrics(html):
    if not html:
        return {}
    metrics = {}
    text = _strip_html(html)

    pvp_match = re.search(r"\bP/VP\b[:\s]*([0-9][0-9\.\,]+)", text, re.IGNORECASE)
    if pvp_match:
        metrics["pvp"] = _parse_pt_number(pvp_match.group(1))

    dy_match = re.search(r"\bDY\s*\(12M\)\s*([0-9][0-9\.\,]+)", text, re.IGNORECASE)
    if not dy_match:
        dy_match = re.search(r"Dividend\s*Y(?:ield|eld).*?([0-9][0-9\.\,]+)\s*%", text, re.IGNORECASE)
    if dy_match:
        metrics["dividend_yield"] = _parse_pt_number(dy_match.group(1))

    liq_match = re.search(r"Liquidez\s*Di[áa]ria\s*R\$\s*([0-9\.\,]+\s*[a-zA-Z]*)", text, re.IGNORECASE)
    if liq_match:
        metrics["liquidez_brl"] = _parse_brl_value(liq_match.group(1))

    nav_match = re.search(r"VAL(?:\.|OR)?\s*PATRIMONIAL\s*P/\s*COTA\s*R\$\s*([0-9\.\,]+)", text, re.IGNORECASE)
    if not nav_match:
        nav_match = re.search(r"VALOR\s*PATRIMONIAL\s*P/\s*COTA\s*R\$\s*([0-9\.\,]+)", text, re.IGNORECASE)
    if nav_match:
        metrics["book_value"] = _parse_pt_number(nav_match.group(1))

    patr_match = re.search(r"VALOR\s*PATRIMONIAL\s*R\$\s*([0-9\.\,]+\s*[a-zA-Z]*)", text, re.IGNORECASE)
    if patr_match:
        metrics["equity"] = _parse_brl_value(patr_match.group(1))

    shares_match = re.search(r"COTAS\s*EMITIDAS\s*([0-9\.\,]+\s*[a-zA-Z]*)", text, re.IGNORECASE)
    if not shares_match:
        shares_match = re.search(r"N[ÚU]MERO\s*DE\s*COTAS\s*([0-9\.\,]+\s*[a-zA-Z]*)", text, re.IGNORECASE)
    if shares_match:
        metrics["shares_outstanding"] = _parse_brl_value(shares_match.group(1))

    price_match = re.search(r"Cotação\s*R\$\s*([0-9\.\,]+)", text, re.IGNORECASE)
    if price_match:
        metrics["price"] = _parse_pt_number(price_match.group(1))

    return metrics

def _fetch_brapi_quote(ticker, range_value=None, interval=None, modules=None):
    client = _get_brapi_client()
    if not client:
        return None
    params = {}
    if range_value:
        params["range"] = range_value
    if interval:
        params["interval"] = interval
    if modules:
        params["modules"] = modules
    try:
        data = client.quote.retrieve(tickers=ticker, **params)
    except Exception:
        return None
    if not data:
        return None
    results = _brapi_get(data, "results") or []
    if not results:
        return None
    return results[0]

def _brapi_history_to_df(quote):
    if not quote:
        return pd.DataFrame()
    items = _brapi_get(quote, "historicalDataPrice", "historical_data_price") or []
    if not items:
        return pd.DataFrame()
    rows = []
    for item in items:
        row = _brapi_to_dict(item)
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    date_col = "date" if "date" in df.columns else "datetime" if "datetime" in df.columns else None
    if date_col:
        df["Date"] = pd.to_datetime(df[date_col], unit="s", utc=True).dt.tz_convert(None)
        df = df.set_index("Date")
    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
        "adjustedClose": "Adj Close",
        "adjusted_close": "Adj Close",
    }
    df = df.rename(columns=rename_map)
    keep_cols = [col for col in ["Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    if keep_cols:
        df = df[keep_cols]
    return df.sort_index()

def _extract_brapi_price(quote, df=None):
    if not quote:
        return float("nan")
    price = _as_float(_brapi_get(quote, "regularMarketPrice", "regular_market_price"))
    if math.isnan(price):
        price = _as_float(_brapi_get(quote, "regularMarketPreviousClose", "regular_market_previous_close"))
    if math.isnan(price) and df is not None and not df.empty and "Close" in df.columns:
        price = _as_float(df["Close"].iloc[-1])
    return price

def _extract_brapi_metrics(quote):
    if not quote:
        return {}
    stats = _brapi_get(quote, "defaultKeyStatistics", "default_key_statistics") or {}
    fin = _brapi_get(quote, "financialData", "financial_data") or {}
    stats = _brapi_to_dict(stats) or {}
    fin = _brapi_to_dict(fin) or {}
    avg_volume = _brapi_get(
        quote,
        "averageDailyVolume3Month",
        "average_daily_volume3_month",
        "average_daily_volume_3_month"
    )
    if avg_volume is None:
        avg_volume = _brapi_get(
            quote,
            "averageDailyVolume10Day",
            "average_daily_volume10_day",
            "average_daily_volume_10_day"
        )
    if avg_volume is None:
        avg_volume = _brapi_get(quote, "regularMarketVolume", "regular_market_volume")
    return {
        "pvp": _as_float(stats.get("priceToBook") or stats.get("price_to_book")),
        "book_value": _as_float(stats.get("bookValue") or stats.get("book_value")),
        "shares_outstanding": _as_float(stats.get("sharesOutstanding") or stats.get("shares_outstanding")),
        "market_cap": _as_float(_brapi_get(quote, "marketCap", "market_cap")),
        "nav": _as_float(_brapi_get(quote, "netAssetValue", "net_asset_value", "navPrice", "nav_price")),
        "dividend_yield": _as_float(stats.get("dividendYield") or stats.get("dividend_yield")),
        "debt_to_equity": _as_float(fin.get("debtToEquity") or fin.get("debt_to_equity")),
        "avg_volume": _as_float(avg_volume),
    }

def _extract_brapi_equity(quote):
    history = _brapi_get(quote, "balanceSheetHistory", "balance_sheet_history") or []
    rows = []
    for item in history:
        row = _brapi_to_dict(item)
        if row:
            rows.append(row)
    if not rows:
        return float("nan")
    def _end_date(row):
        value = row.get("endDate") or row.get("end_date")
        if not value:
            return pd.Timestamp.min
        try:
            return pd.to_datetime(value)
        except Exception:
            return pd.Timestamp.min
    row = max(rows, key=_end_date)
    for key in (
        "totalStockholderEquity",
        "total_stockholder_equity",
        "shareholdersEquity",
        "shareholders_equity",
        "totalStockholdersEquity",
        "total_stockholders_equity",
    ):
        if key in row and row[key] is not None:
            return _as_float(row[key])
    return float("nan")

def _prices_match(a, b, tolerance=PRICE_MATCH_TOLERANCE):
    if math.isnan(a) or math.isnan(b):
        return False
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= tolerance

def _is_nan(value):
    if value is None:
        return True
    try:
        return math.isnan(value)
    except Exception:
        return False

def _select_price(primary, secondary, prefer_primary=True):
    if not math.isnan(primary) and not math.isnan(secondary):
        if _prices_match(primary, secondary):
            return primary
        return primary if prefer_primary else secondary
    if not math.isnan(primary):
        return primary
    if not math.isnan(secondary):
        return secondary
    return float("nan")

def _select_metric(primary, secondary):
    if _is_nan(primary) and _is_nan(secondary):
        return float("nan")
    if _is_nan(primary):
        return secondary
    return primary

def _clean_price(value):
    if value is None:
        return None
    try:
        if math.isnan(value):
            return None
    except Exception:
        pass
    return value

def _fetch_yahoo_price(symbol):
    try:
        ticker_obj = yf.Ticker(symbol)
        fast_info = getattr(ticker_obj, "fast_info", None)
        if fast_info:
            for key in ("lastPrice", "last_price", "regularMarketPrice", "regular_market_price"):
                if key in fast_info and fast_info[key] is not None:
                    return _as_float(fast_info[key])
        info = ticker_obj.info or {}
        return _as_float(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
        )
    except Exception:
        return float("nan")

def get_price_details(ticker):
    ticker = ticker.upper()
    symbol = f"{ticker}.SA"
    try:
        _prepare_yfinance_cache()
    except Exception:
        pass
    yahoo_price = _fetch_yahoo_price(symbol)
    brapi_quote = _fetch_brapi_quote(ticker)
    brapi_price = _extract_brapi_price(brapi_quote)
    price = _select_price(yahoo_price, brapi_price, prefer_primary=True)
    if math.isnan(price):
        return None
    match = None
    if not math.isnan(yahoo_price) and not math.isnan(brapi_price):
        match = _prices_match(yahoo_price, brapi_price)
    return {
        "price": price,
        "sources": {
            "yahoo": _clean_price(yahoo_price),
            "brapi": _clean_price(brapi_price),
        },
        "match": match,
    }

def get_price(ticker):
    details = get_price_details(ticker)
    if not details:
        return None
    return details["price"]

def get_analysis(ticker):
    ticker = ticker.upper()
    symbol = f"{ticker}.SA"
    ticker_obj = yf.Ticker(symbol)
    
    try:
        # Gerenciamento de Cache para evitar Rate Limiting
        _prepare_yfinance_cache()
        df = yf.download(symbol, period="1y", interval="1d", progress=False, timeout=DEFAULT_TIMEOUT, threads=False)
        info = ticker_obj.info or {}
    except Exception:
        df = pd.DataFrame()
        info = {}

    df = _normalize_columns(df, symbol)
    brapi_quote = None
    if df.empty or len(df) < 100:
        brapi_quote = _fetch_brapi_quote(ticker, range_value="1y", interval="1d")
        df = _brapi_history_to_df(brapi_quote)
    if df.empty or len(df) < 100:
        return None

    # --- INDICADORES TÉCNICOS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['SMA200'] = ta.sma(df['Close'], length=200)

    last = df.iloc[-1]
    yahoo_price = _as_float(last['Close'])
    if brapi_quote is None:
        brapi_quote = _fetch_brapi_quote(ticker)
    brapi_price = _extract_brapi_price(brapi_quote, df)
    price = _select_price(yahoo_price, brapi_price, prefer_primary=True)
    rsi = _as_float(last['RSI'])
    sma200 = _as_float(last['SMA200'])

    # --- LÓGICA DE SCORE EQUILIBRADA (ANALOGIAS DE PROGRAMADOR) ---
    score = 0
    sinais = []

    # 1. P/VP - Valor real vs. Valor de mercado
    # ANALOGIA: Refatoração - o código faz o mesmo, mas custa menos recursos.
    pvp_yahoo = _as_float(info.get('priceToBook'))
    book_value_yahoo = _as_float(info.get('bookValue'))
    nav_yahoo = _as_float(info.get('netAssetValue') or info.get('navPrice'))
    dy_yahoo = _as_float(info.get('dividendYield') or info.get('trailingAnnualDividendYield'))
    avg_vol_yahoo = _as_float(info.get('averageVolume') or info.get('volume'))
    debt_yahoo = _as_float(info.get('debtToEquity'))
    market_cap_yahoo = _as_float(info.get('marketCap'))

    brapi_fundamentals = None
    if (
        _is_nan(pvp_yahoo)
        or _is_nan(book_value_yahoo)
        or _is_nan(nav_yahoo)
        or _is_nan(dy_yahoo)
        or _is_nan(avg_vol_yahoo)
        or _is_nan(debt_yahoo)
        or _is_nan(market_cap_yahoo)
    ):
        brapi_fundamentals = _fetch_brapi_quote(
            ticker,
            modules="defaultKeyStatistics,financialData,balanceSheetHistory"
        )

    brapi_metrics = _extract_brapi_metrics(brapi_fundamentals or brapi_quote)
    investidor10_metrics = {}
    if ticker.endswith("11"):
        need_fii_source = (
            _is_nan(pvp_yahoo)
            or _is_nan(book_value_yahoo)
            or _is_nan(dy_yahoo)
            or _is_nan(avg_vol_yahoo)
            or _is_nan(debt_yahoo)
            or _is_nan(market_cap_yahoo)
            or math.isnan(price)
        )
        if need_fii_source:
            investidor10_metrics = _extract_investidor10_metrics(_fetch_investidor10_html(ticker))
            if math.isnan(price):
                price_from_fii = investidor10_metrics.get("price")
                if price_from_fii is not None and not math.isnan(price_from_fii):
                    price = price_from_fii

    pvp = _select_metric(pvp_yahoo, brapi_metrics.get("pvp"))
    pvp = _select_metric(pvp, investidor10_metrics.get("pvp"))
    if math.isnan(pvp):
        book_value = _select_metric(book_value_yahoo, brapi_metrics.get("book_value"))
        book_value = _select_metric(book_value, investidor10_metrics.get("book_value"))
        if math.isnan(book_value):
            nav_value = _select_metric(nav_yahoo, brapi_metrics.get("nav"))
            nav_value = _select_metric(nav_value, investidor10_metrics.get("book_value"))
            if not math.isnan(nav_value):
                book_value = nav_value
        if math.isnan(book_value):
            shares_outstanding = _select_metric(
                _as_float(info.get("sharesOutstanding")),
                brapi_metrics.get("shares_outstanding"),
            )
            shares_outstanding = _select_metric(shares_outstanding, investidor10_metrics.get("shares_outstanding"))
            equity_yahoo = _as_float(
                info.get("totalStockholderEquity")
                or info.get("totalStockholdersEquity")
                or info.get("shareholdersEquity")
            )
            equity_brapi = _extract_brapi_equity(brapi_fundamentals or brapi_quote)
            equity = _select_metric(equity_yahoo, equity_brapi)
            equity = _select_metric(equity, investidor10_metrics.get("equity"))
            if (
                not math.isnan(shares_outstanding)
                and not math.isnan(equity)
                and shares_outstanding > 0
            ):
                book_value = equity / shares_outstanding
        if math.isnan(book_value):
            equity_brapi = _extract_brapi_equity(brapi_fundamentals or brapi_quote)
            equity_yahoo = _as_float(
                info.get("totalStockholderEquity")
                or info.get("totalStockholdersEquity")
                or info.get("shareholdersEquity")
            )
            equity = _select_metric(equity_yahoo, equity_brapi)
            equity = _select_metric(equity, investidor10_metrics.get("equity"))
            market_cap = _select_metric(market_cap_yahoo, brapi_metrics.get("market_cap"))
            if not math.isnan(equity) and equity > 0 and not math.isnan(market_cap):
                pvp = market_cap / equity
        if not math.isnan(book_value) and book_value > 0 and not math.isnan(price):
            pvp = price / book_value
    if not math.isnan(pvp):
        if pvp < 0.95: 
            score += 3
            sinais.append("💎 Desconto (P/VP)")
        elif 0.95 <= pvp <= 1.05:
            score += 1 # Preço justo agora pontua positivamente
            sinais.append("✅ Preço Justo")
        elif pvp > 1.15: 
            score -= 2
            sinais.append("⚠️ Ágio (P/VP)")

    # 2. Dividend Yield - "Salário" que o ativo paga
    # ANALOGIA: Uptime de lucro passivo - sistema gerando valor sem intervenção.
    dy_raw = _select_metric(dy_yahoo, brapi_metrics.get("dividend_yield"))
    dy_raw = _select_metric(dy_raw, investidor10_metrics.get("dividend_yield"))
    dy_pct = float("nan")
    if not math.isnan(dy_raw):

        dy_pct = dy_raw if dy_raw > 1.0 else dy_raw * 100
        if dy_pct >= 8: 
            score += 2
            sinais.append("💰 Rendimento Alto")
        elif dy_pct < 5: 
            score -= 1
            sinais.append("📉 Rendimento Baixo")

    # 3. Liquidez Diária - Facilidade de sair do ativo
    # ANALOGIA: Velocidade de Deploy/Rollback.
    avg_vol = _select_metric(avg_vol_yahoo, brapi_metrics.get("avg_volume"))
    if math.isnan(avg_vol):
        liquidez_brl = investidor10_metrics.get("liquidez_brl")
        if liquidez_brl is not None and not math.isnan(liquidez_brl) and price and not math.isnan(price):
            avg_vol = liquidez_brl / price
    liquidez = avg_vol * price
    if not math.isnan(liquidez):
        if liquidez < 500_000: 
            score -= 4
            sinais.append("🚫 Baixa Liquidez")
        elif liquidez > 2_000_000: 
            score += 1
            sinais.append("✅ Boa Liquidez")

    # 4. Endividamento (Dívida) - Risco de infraestrutura
    debt = _select_metric(debt_yahoo, brapi_metrics.get("debt_to_equity"))
    debt_label = f"{debt:.1f}%" if not math.isnan(debt) else "N/A"
    if not ticker.endswith("11") and not math.isnan(debt):
        if debt > 150: 
            score -= 2
            sinais.append("🚩 Dívida Alta")
        elif debt < 50: 
            score += 1
            sinais.append("🛡️ Dívida Baixa")

    # 5. IFR (RSI) - Emoção do mercado
    # ANALOGIA: Load Average do Servidor - estresse do sistema.
    if not math.isnan(rsi):
        if rsi < 35: 
            score += 3
            sinais.append("🔥 Sobrevendido")
        elif 35 <= rsi <= 60:
            score += 1 # Zona neutra agora é vista como saudável
        elif rsi > 75: 
            score -= 3
            sinais.append("⚠️ Sobrecomprado")
    
    # Tendência de Longo Prazo
    trend = "Alta 📈" if price > sma200 else "Baixa 📉"

    if score >= 7:
        veredito = "FORTE COMPRA 🟢"
    elif score >= 4:
        veredito = "COMPRA MODERADA 🔵"
    elif score >= 1:
        veredito = "NEUTRO / AGUARDAR 🟡"
    else:
        veredito = "EVITAR / RISCO ALTO 🔴"

    # Formatação final
    pvp_display = f"{pvp:.2f}" if not math.isnan(pvp) else "N/A"
    rsi_display = f"{rsi:.1f}" if not math.isnan(rsi) else "N/A"
    dy_display = f"{dy_pct:.2f}%" if not math.isnan(dy_pct) else "N/A"

    msg = (
        f"🔎 *RELATÓRIO: {ticker}*\n"
        f"💵 *Preço:* R$ {price:.2f}\n"
        f"---------------------------\n"
        f"📏 *P/VP:* {pvp_display} (Alvo: <1.0)\n"
        f"📊 *IFR (RSI):* {rsi_display} (Alvo: <35)\n"
        f"💰 *Yield:* {dy_display} (Alvo: >8%)\n"
        f"🌊 *Liquidez:* {_format_currency(liquidez)}/dia\n"
        f"🏗️ *Dívida:* {debt_label}\n"
        f"📈 *Tendência:* {trend}\n"
        f"---------------------------\n"
        f"💡 *Sinais:* {' | '.join(sinais) if sinais else 'Neutro'}\n"
        f"⭐ *Score:* {score}/10\n"
        f"🎯 *Veredito:* {veredito}"
    )

    return {"msg": msg, "price": price, "score": score}