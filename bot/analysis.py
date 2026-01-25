import yfinance as yf
import pandas_ta as ta
import pandas as pd

def get_analysis(ticker):
    symbol = f"{ticker.upper()}.SA"
    # Pegamos 1 ano para ter dados de suporte e resistência consistentes
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    
    if df.empty or len(df) < 200: 
        return None

    # --- INDICADORES ---
    # 1. RSI (Força do preço)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # 2. Médias Móveis (Tendência)
    df['EMA9'] = ta.ema(df['Close'], length=9)   # Média rápida
    df['SMA20'] = ta.sma(df['Close'], length=20) # Média média
    df['SMA200'] = ta.sma(df['Close'], length=200) # Média longa (tendência principal)

    # 3. Volatilidade (Bandas de Bollinger)
    bollinger = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bollinger], axis=1)

    # --- DADOS ATUAIS ---
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['Close']
    rsi = last['RSI']
    
    # --- LÓGICA DE DECISÃO (SCORE) ---
    score = 0
    sinais = []

    # Critério 1: RSI (Oversold)
    if rsi < 35: 
        score += 4
        sinais.append("🔥 Preço muito descontado (RSI baixo)")
    elif rsi > 70:
        score -= 2
        sinais.append("⚠️ Preço esticado/caro (RSI alto)")

    # Critério 2: Tendência de Longo Prazo
    if price > last['SMA200']:
        score += 3
        trend_long = "Alta 📈"
    else:
        trend_long = "Baixa 📉"

    # Critério 3: Cruzamento de Médias (Setup de compra clássico)
    if last['EMA9'] > last['SMA20'] and prev['EMA9'] <= prev['SMA20']:
        score += 3
        sinais.append("🚀 Cruzamento de alta (9 cruza 20)")

    # Critério 4: Suporte e Resistência (Mínimas de 52 semanas)
    min_52 = df['Low'].min()
    if price <= min_52 * 1.05: # Dentro de 5% da mínima do ano
        score += 2
        sinais.append("🛡️ Perto do suporte histórico")

    # --- FORMATAÇÃO DA RESPOSTA ---
    veredito = "FORTE COMPRA 🟢" if score >= 7 else "AGUARDAR 🟡" if score >= 4 else "RISCO ALTO 🔴"
    
    msg = (
        f"🔎 *RELATÓRIO: {ticker.upper()}*\n"
        f"💵 *Preço:* R$ {price:.2f}\n"
        f"📊 *IFR (RSI):* {rsi:.1f}\n"
        f"🏗️ *Tendência (200 dias):* {trend_long}\n"
        f"---------------------------\n"
        f"💡 *Análise:* {' | '.join(sinais) if sinais else 'Sem sinais claros'}\n"
        f"⭐ *Score de Entrada:* {score}/10\n"
        f"🎯 *Veredito:* {veredito}"
    )

    return {"msg": msg, "price": price, "score": score}