from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

# Variables de entorno (asegúrate de configurarlas en Render)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

@app.route('/', methods=['GET'])
def index():
    return "RekarBot funcionando correctamente", 200

# Verificación del webhook (GET)
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    print(f"🔍 Verificación recibida: mode={mode}, token={token}, challenge={challenge}")

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✔️ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Verificación fallida")
        return "Forbidden", 403

# Recibir los eventos del webhook (POST)
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json()
    print(f"📩 Evento recibido: {data}")

    # Verificar que sean mensajes
    if data and 'entry' in data:
        for entry in data['entry']:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                if messages:
                    for message in messages:
                        from_number = message.get('from')
                        msg_body = message.get('text', {}).get('body')
                        print(f"📨 De: {from_number} — Mensaje: {msg_body}")

                        # Responder al usuario
                        url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
                        headers = {
                            "Authorization": f"Bearer {ACCESS_TOKEN}",
                            "Content-Type": "application/json"
                        }
                        body = {
                            "messaging_product": "whatsapp",
                            "to": from_number,
                            "type": "text",
                            "text": {"body": "Hola, soy RekarBot. Gracias por comunicarte con nosotros."}
                        }
                        resp = requests.post(url, headers=headers, json=body)
                        print(f"➡️ Respuesta enviada. Código: {resp.status_code}, Contenido: {resp.text}")

    # Siempre responder 200 para que Meta considere entregado el webhook
    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
