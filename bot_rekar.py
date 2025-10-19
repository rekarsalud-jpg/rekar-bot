from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

@app.route("/", methods=["GET"])
def home():
    return "✅ Rekar Bot está activo y funcionando.", 200


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
    print("📩 Datos recibidos del webhook:")
    print(data)

    try:
        if "entry" in data and data["entry"]:
            entry = data["entry"][0]
            if "changes" in entry and entry["changes"]:
                changes = entry["changes"][0]
                value = changes.get("value", {})
                messages = value.get("messages", [])
                
                if messages:
                    message = messages[0]
                    phone_number = message.get("from")
                    text = message.get("text", {}).get("body", "").strip().lower()

                    print(f"💬 Mensaje recibido: {text} de {phone_number}")

                    if "hola" in text:
                        send_whatsapp_message(phone_number, "👋 ¡Hola! Soy Rekar Bot. ¿Cómo puedo ayudarte hoy?")
                    elif "turno" in text:
                        send_whatsapp_message(phone_number, "📅 Perfecto, ¿para qué día querés solicitar tu turno?")
                    else:
                        send_whatsapp_message(phone_number, "🤖 No entendí tu mensaje, pero pronto te responderemos.")
                else:
                    print("⚠ No hay mensajes nuevos en la solicitud.")
        else:
            print("⚠ Estructura inesperada en el JSON recibido.")

    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}")

    return jsonify({"status": "EVENT_RECEIVED"}), 200


def send_whatsapp_message(to, message):
    """Enviar un mensaje de texto por WhatsApp"""
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
    print(f"📤 Respuesta de Meta API: {response.status_code} - {response.text}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
