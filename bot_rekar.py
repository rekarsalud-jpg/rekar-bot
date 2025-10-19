from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "rekar_verificacion")

@app.route("/", methods=["GET"])
def home():
    return "✅ Rekar Bot activo y listo para responder.", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✔ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Error de verificación del webhook")
        return "Error de verificación", 403


@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("📩 Datos recibidos:")
    print(data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_number = message["from"]
        text = message.get("text", {}).get("body", "").lower()

        # Cualquier mensaje que llegue -> responde "Hola!"
        send_whatsapp_message(phone_number, "👋 Hola, soy Rekar Bot. Estoy activo y te escucho.")

    except Exception as e:
        print(f"⚠ Error procesando mensaje: {e}")

    return jsonify({"ok": True}), 200


def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, json=payload)
    print(f"📤 Enviado: {response.status_code} - {response.text}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
