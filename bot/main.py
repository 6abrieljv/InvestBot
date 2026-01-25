import os
from flask import Flask, request
import requests
import analysis  
app = Flask(__name__)

# Carregando variáveis do .env
EVO_URL = os.getenv("EVO_URL")
API_KEY = os.getenv("EVO_API_KEY")
INSTANCE = os.getenv("INSTANCE_NAME")
APORTE_MENSAL = float(os.getenv("VALOR_APORTE", 185.00))

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('event') == 'messages.upsert':
        msg_data = data['data']
        jid = msg_data['key']['remoteJid']
        text = msg_data['message'].get('conversation', '').strip().lower()

        if text.startswith('/analise'):
            ticker = text.split()[-1]
            res = analysis.get_analysis(ticker)
            send_msg(jid, res['msg'] if res else "⚠️ Ação não encontrada.")
            
        elif text.startswith('/aporte'):
            ticker = text.split()[-1]
            res = analysis.get_analysis(ticker)
            if res:
                qtd = int(APORTE_MENSAL // res['price'])
                sobra = APORTE_MENSAL % res['price']
                msg = (f"💸 *Simulador de Aporte*\n\n"
                       f"Com seu aporte de R$ {APORTE_MENSAL:.2f}:\n"
                       f"✅ Compra: *{qtd}* cotas de {ticker.upper()}\n"
                       f"💰 Sobra: R$ {sobra:.2f}")
                send_msg(jid, msg)

    return "OK", 200

def send_msg(jid, text):
    url = f"{EVO_URL}/message/sendText/{INSTANCE}"
    headers = {"apikey": API_KEY, "Content-Type": "application/json"}
    payload = {"number": jid, "text": text}
    requests.post(url, json=payload, headers=headers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))