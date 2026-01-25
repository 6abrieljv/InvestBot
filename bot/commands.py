import os
import analysis


APORTE_MENSAL = float(os.getenv("VALOR_APORTE", 185.00))

def _extract_ticker(parts, command_hint):
    if len(parts) < 2:
        return None, f"⚠️ Informe o ticker. Ex: {command_hint} PETR4"
    ticker = parts[-1].upper()
    if ticker.startswith("/"):
        return None, f"⚠️ Informe o ticker. Ex: {command_hint} PETR4"
    return ticker, None

def build_response(text):
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None

    lowered = cleaned.lower()
    parts = cleaned.split()

    # COMANDO UNIFICADO: ANÁLISE + APORTE + TÍTULO
    if lowered.startswith("/analise"):
        ticker, error = _extract_ticker(parts, "/analise")
        if error:
            return error
        
        res = analysis.get_analysis(ticker)
        if not res:
            return "⚠️ Ação ou Fundo não encontrado. Verifique o ticker."

        # Cálculo do Aporte Automático
        qtd = int(APORTE_MENSAL // res["price"])
        sobra = APORTE_MENSAL % res["price"]
        
       
        header = "🚀 *ESTRATÉGIA INVESTBOT 2026 - RELATÓRIO COMPLETO* 🚀\n"
        
        aporte_msg = (f"\n💸 *SIMULADOR DE APORTE*\n"
                      f"Com seu aporte mensal de R$ {APORTE_MENSAL:.2f}:\n"
                      f"✅ Compra sugerida: *{qtd}* cotas de {ticker}\n"
                      f"💰 Sobra para o próximo mês: R$ {sobra:.2f}")
        
        footer = "\n\n💡 *Dica:* Mantenha sua diversificação para segurança máxima!"
        
        return f"{header}\n{res['msg']}\n{aporte_msg}{footer}"

    
    if lowered.startswith("/aporte"):
        ticker, error = _extract_ticker(parts, "/aporte")
        if error:
            return error
        res = analysis.get_analysis(ticker)
        if not res:
            return "⚠️ Ação não encontrada."
        
        qtd = int(APORTE_MENSAL // res["price"])
        sobra = APORTE_MENSAL % res["price"]
        
        return (f"💸 *SIMULADOR DE APORTE*\n\n"
                f"Com seu aporte de R$ {APORTE_MENSAL:.2f}:\n"
                f"✅ Compra: *{qtd}* cotas de {ticker.upper()}\n"
                f"💰 Sobra: R$ {sobra:.2f}")

    if lowered.startswith("/preco"):
        ticker, error = _extract_ticker(parts, "/preco")
        if error:
            return error
        price = analysis.get_price(ticker)
        if price is None:
            return "⚠️ Ação não encontrada."
        return f"💵 Preço atual de {ticker}: R$ {price:.2f}"

    return None