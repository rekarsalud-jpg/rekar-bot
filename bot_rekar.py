from flask import Flask, request
import os
import requests

app = Flask(__name__)

# --- VARIABLES ---
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

@app.route('/')
def index():
    return "✅ RekarBot funcionando correctamente", 200

# --- WEBHOOK VERIFICACIÓN (GET) ---
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    print(f"🧩 Verificación recibida: mode={mode}, token={token}, challenge={challenge}")

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Error de verificación del Webhook")
        return "Error de verificación", 403

# --- WEBHOOK RECEPCIÓN DE MENSAJES (POST) ---
@app.route('/webhook', methods=['POST'])
def receive_message():
    data = request.get_json()
    print(f"📩 Mensaje recibido: {data}")

    if data and "messages" in data["entry"][0]["changes"][0]["value"]:
        phone_number_id = data["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
        from_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        message_text = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]

        print(f"📞 De: {from_number} — Mensaje: {message_text}")

        reply = "👋 Hola, soy RekarBot. Gracias por comunicarte con nosotros."
        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
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

        requests.post(url, headers=headers, json=body)

    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
