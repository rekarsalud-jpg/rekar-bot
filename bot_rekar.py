from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# 🧩 Variables de entorno de Render
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

@app.route("/", methods=["GET"])
def home():
    return "✅ Rekar Bot está activo y funcionando correctamente.", 200


# 🧩 Verificación inicial del webhook (Meta la usa al conectar)
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✔ Webhook verificado correctamente.")
        return challenge, 200
    else:
        print("❌ Error de verificación del webhook.")
        return "Error de verificación", 403


# 🧩 Recepción de mensajes entrantes desde WhatsApp
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("📩 Nuevo evento recibido:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    try:
        # --- Estructura estándar del webhook de Meta ---
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        # Si no hay mensajes, puede ser otro tipo de evento (estado, entrega, etc.)
        if not messages:
            print("⚠ No se encontró 'messages' en el JSON (posiblemente evento de estado).")
            return "EVENT_RECEIVED", 200

        message = messages[0]
        phone_number = message.get("from")
        text = message.get("text", {}).get("body", "").strip().lower()

        print(f"💬 Mensaje recibido de {phone_number}: {text}")

        # --- Respuestas automáticas ---
        if "hola" in text:
            send_whatsapp_message(phone_number, "👋 ¡Hola! Soy Rekar Bot. ¿Cómo puedo ayudarte hoy?")
        elif "turno" in text:
            send_whatsapp_message(phone_number, "📅 Perfecto, ¿para qué día querés solicitar tu turno?")
        elif "gracias" in text:
            send_whatsapp_message(phone_number, "🙏 ¡De nada! Estamos para ayudarte.")
        else:
            send_whatsapp_message(phone_number, "🤖 No entendí tu mensaje, pero pronto te responderemos.")

    except Exception as e:
        print(f"⚠ Error procesando mensaje: {e}")
        print("📦 Datos recibidos (para debug):", json.dumps(data, indent=2, ensure_ascii=False))

    return "EVENT_RECEIVED", 200


# 🧩 Función para enviar mensajes de respuesta a través de la API de WhatsApp
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

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"📤 Respuesta enviada — Código {response.status_code}")
        print(response.text)
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")


# 🧩 Inicio del servidor Flask (Render usa la variable de puerto automáticamente)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
