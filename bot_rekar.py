import os
import requests
from flask import Flask, request

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

@app.route("/")
def home():
    return "REKAR Bot conectado a WhatsApp ✅"

# Verificación del webhook (Meta la usa al conectar)
@app.route("/webhook", methods=["GET"])
def verify():
    VERIFY_TOKEN = "rekar_verificacion"
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Error de verificación", 403

# Recepción de mensajes de WhatsApp
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("Mensaje recibido:", data)

    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        phone = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

        # Responder con un mensaje automático
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
        requests.post(url, headers=headers, json=body)
    except Exception as e:
        print("Error procesando el mensaje:", e)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
