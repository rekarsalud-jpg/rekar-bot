import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

last_contact = {}

# === FUNCIONES AUXILIARES ===

def send_whatsapp_message(phone, message):
    """Enviar mensaje a WhatsApp via Graph API."""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        print(f"📤 Enviado a WhatsApp: {r.status_code} → {r.text}")
        return r.status_code == 200
    except Exception as e:
        print("❌ Error enviando a WhatsApp:", e)
        return False

def send_telegram_message(message):
    """Enviar mensaje a tu chat de Telegram (notificación interna)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=data)
        print(f"📨 Enviado a Telegram: {r.status_code}")
    except Exception as e:
        print("❌ Error enviando a Telegram:", e)

def need_new_greeting(phone):
    """Verifica si pasaron más de 30 min desde el último contacto."""
    now = time.time()
    if phone not in last_contact or now - last_contact[phone] > 1800:
        last_contact[phone] = now
        return True
    return False


# === WEBHOOK META / WHATSAPP ===
@app.route('/webhook', methods=['GET'])
def verify_token():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📥 WhatsApp recibido:", data)

    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" in changes:
            msg = changes["messages"][0]
            phone = msg["from"]
            text = msg.get("text", {}).get("body", "").strip()

            if need_new_greeting(phone):
                saludo = (
                    "¡Hola! Soy *RekyBot 🤖* de *REKAR*, red de enfermería y kinesiología.\n"
                    "Nuestro horario de atención es de *lunes a viernes de 8 a 18 hs*.\n\n"
                    "¿Podés decirme tu nombre, por favor?"
                )
                send_whatsapp_message(phone, saludo)
                send_telegram_message(f"📞 Nuevo contacto: {phone} → {text}")

            elif any(word in text.lower() for word in ["soy", "me llamo"]) or len(text.split()) <= 3:
                nombre = text.replace("soy", "").replace("me llamo", "").strip().title()
                send_whatsapp_message(phone, f"Gracias {nombre}. Un operador humano de REKAR se pondrá en contacto contigo pronto.\nPor favor, dejanos tu consulta.")
                send_telegram_message(f"👤 Registrado: {nombre} ({phone})")

            else:
                send_telegram_message(f"💬 {phone}: {text}")

    except Exception as e:
        print("❌ Error procesando mensaje:", e)

    return jsonify({"status": "ok"}), 200


# === WEBHOOK TELEGRAM ===
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    print("📥 Telegram evento:", data)

    try:
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")

            if text.startswith("/start"):
                send_telegram_message("🤖 Bot Rekar conectado correctamente.")
                return jsonify({"ok": True})

            elif text.startswith("/enviar"):
                parts = text.split(" ", 2)
                if len(parts) == 3:
                    _, phone, msg = parts
                    send_whatsapp_message(phone, msg)
                    send_telegram_message(f"✅ Mensaje enviado a WhatsApp {phone}: {msg}")
                else:
                    send_telegram_message("❌ Formato incorrecto. Usá /enviar <telefono> <mensaje>")

            else:
                send_telegram_message(f"Mensaje recibido: {text}")

    except Exception as e:
        print("❌ Error en Telegram webhook:", e)

    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
