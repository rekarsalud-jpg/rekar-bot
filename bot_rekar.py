from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

@app.route("/", methods=["GET"])
def home():
    return "✅ Rekar Bot activo.", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✔ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Error en verificación")
        return "Error", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📨 DATA RECIBIDA DESDE META:")
    print(json.dumps(data, indent=2))  # 🔍 Esto mostrará toda la estructura exacta

    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            print("⚠ No se encontraron mensajes en la solicitud.")
            return jsonify({"status": "no_message"}), 200

        message = messages[0]
        phone_number = message.get("from")
        text = message.get("text", {}).get("body", "").strip().lower()

        print(f"📲 Mensaje recibido: {text} de {phone_number}")

        if "hola" in text:
            send_message(phone_number, "👋 ¡Hola! Soy Rekar Bot, ¿cómo puedo ayudarte?")
        elif "turno" in text:
            send_message(phone_number, "📅 Perfecto, ¿para qué día querés solicitar tu turno?")
        else:
            send_message(phone_number, "🤖 No entendí tu mensaje, pero pronto te ayudaremos.")

    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}")

    return jsonify({"status": "ok"}), 200


def send_message(to, message):
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
    print(f"📤 RESPUESTA META API: {response.status_code} - {response.text}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
