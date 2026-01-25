import os
import socket
import math
import yfinance as yf
import yfinance.cache as yf_cache
import pandas_ta as ta
import pandas as pd


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

def get_analysis(ticker):
    ticker = ticker.upper()
    symbol = f"{ticker}.SA"
    ticker_obj = yf.Ticker(symbol)
    
    try:
        # Gerenciamento de Cache para evitar Rate Limiting
        cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
        os.makedirs(cache_dir, exist_ok=True)
        yf_cache.set_cache_location(cache_dir)
        socket.setdefaulttimeout(15)
        
        df = yf.download(symbol, period="1y", interval="1d", progress=False, timeout=15, threads=False)
        info = ticker_obj.info or {}
    except Exception:
        return None

    df = _normalize_columns(df, symbol)
    if df.empty or len(df) < 100: 
        return None

    # --- INDICADORES TÉCNICOS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['SMA200'] = ta.sma(df['Close'], length=200)

    last = df.iloc[-1]
    price = _as_float(last['Close'])
    rsi = _as_float(last['RSI'])
    sma200 = _as_float(last['SMA200'])

    # --- LÓGICA DE SCORE EQUILIBRADA (ANALOGIAS DE PROGRAMADOR) ---
    score = 0
    sinais = []

    # 1. P/VP - Valor real vs. Valor de mercado
    # ANALOGIA: Refatoração - o código faz o mesmo, mas custa menos recursos.
    pvp = _as_float(info.get('priceToBook'))
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
    dy_raw = _as_float(info.get('dividendYield') or info.get('trailingAnnualDividendYield'))
    dy_pct = float("nan")
    if not math.isnan(dy_raw):
        # FIX: Corrigido o erro de escala (0.12 vs 12.0)
        dy_pct = dy_raw if dy_raw > 1.0 else dy_raw * 100
        if dy_pct >= 8: 
            score += 2
            sinais.append("💰 Rendimento Alto")
        elif dy_pct < 5: 
            score -= 1
            sinais.append("📉 Rendimento Baixo")

    # 3. Liquidez Diária - Facilidade de sair do ativo
    # ANALOGIA: Velocidade de Deploy/Rollback.
    avg_vol = _as_float(info.get('averageVolume') or info.get('volume'))
    liquidez = avg_vol * price
    if not math.isnan(liquidez):
        if liquidez < 500_000: 
            score -= 4
            sinais.append("🚫 Baixa Liquidez")
        elif liquidez > 2_000_000: 
            score += 1
            sinais.append("✅ Boa Liquidez")

    # 4. Endividamento (Dívida) - Risco de infraestrutura
    debt = _as_float(info.get('debtToEquity'))
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