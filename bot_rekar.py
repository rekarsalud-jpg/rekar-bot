import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Variables de entorno (Render las toma automáticamente)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

@app.route("/", methods=["GET"])
def home():
    return "REKAR Bot conectado a WhatsApp ✅"

# ==========================================================
# 🔹 Verificación del Webhook (usada por Meta al conectar)
# ==========================================================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    VERIFY_TOKEN = "rekar_verificacion"
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente con Meta.")
        return challenge, 200
    else:
        print("❌ Error de verificación del Webhook.")
        return "Error de verificación", 403


# ==========================================================
# 🔹 Recepción y respuesta automática de mensajes
# ==========================================================
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    try:
        # Extrae texto y número del mensaje entrante
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        phone = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

        # Respuesta automática
        url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        body = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": f"Hola 👋, soy el bot REKAR. Recibí tu mensaje: {msg}"}
        }

        response = requests.post(url, headers=headers, json=body)
        print("📤 Respuesta enviada:", response.text)

    except Exception as e:
        print("⚠️ Error procesando el mensaje:", e)

    return "OK", 200


# ==========================================================
# 🔹 Ejecución local (Render usará Gunicorn para producción)
# ==========================================================
if __name__ == "__main__":
    app.run()
