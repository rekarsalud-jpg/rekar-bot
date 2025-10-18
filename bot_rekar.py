# === REKARBOT v5 (Flask directo, sin Gunicorn) ===
from flask import Flask, request
import os
import requests

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

# === RUTA PRINCIPAL ===
@app.route('/')
def index():
    return "💬 RekarBot funcionando correctamente (Flask directo)", 200

# === VERIFICACIÓN DEL WEBHOOK ===
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Error en la verificación del webhook")
        return "Error de verificación", 403

# === RECEPCIÓN DE MENSAJES ===
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json()
    print("===== MENSAJE RECIBIDO =====")
    print(data)

    try:
        # Analiza la estructura JSON que manda Meta
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            msg = messages[0]
            from_number = msg["from"]
            text = msg["text"]["body"]
            print(f"📩 De: {from_number} — Mensaje: {text}")

            # Respuesta del bot
            reply = f"👋 Hola! Soy RekarBot. Recibí tu mensaje: '{text}'. ¿Cómo puedo ayudarte?"

            url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
            body = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": "text",
                "text": {"body": reply}
            }

            response = requests.post(url, headers=headers, json=body)
            print("📤 Respuesta enviada:", response.status_code, response.text)
        else:
            print("⚠️ No se encontró campo 'messages' en la data recibida")

    except Exception as e:
        print("⚠️ Error procesando el mensaje:", e)

    return "EVENT_RECEIVED", 200

# === MAIN ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Iniciando RekarBot en puerto {port}")
    app.run(host='0.0.0.0', port=port)
