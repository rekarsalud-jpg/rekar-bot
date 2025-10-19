from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


@app.route("/", methods=["GET"])
def home():
    return "✅ Bot Rekar está activo.", 200


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
        return "Error", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    print("📩 Mensaje recibido desde Meta (POST)")
    try:
        data = request.get_json()
        print(data)  # 👀 Para ver qué llega exactamente en los logs

        # Buscar si hay un mensaje nuevo
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_number = message["from"]

        # Enviar un simple "Hola 👋"
        send_message(phone_number, "👋 Hola, soy Rekar Bot. Todo funcionando bien!")

    except Exception as e:
        print(f"⚠ Error procesando mensaje: {e}")

    return jsonify({"status": "ok"}), 200


def send_message(to, text):
    """Envía un mensaje simple por WhatsApp"""
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, headers=headers, json=payload)
    print(f"📤 Respuesta Meta API: {response.status_code} - {response.text}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
