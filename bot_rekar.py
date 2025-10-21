import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#todo-rekar-mensajeria-wtz")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EMAIL_DESTINATION = os.getenv("EMAIL_DESTINATION")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# === VARIABLES DE CONTROL ===
last_contact = {}
active_conversations = {}

# === FUNCIONES BASE ===

def send_whatsapp_message(phone, message):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviado a WhatsApp:", response.status_code, response.text)
    return response.status_code == 200

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram no configurado.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    r = requests.post(url, json=data)
    print("📩 Enviado a Telegram:", r.status_code, r.text)

def need_new_greeting(phone):
    now = time.time()
    if phone not in last_contact:
        last_contact[phone] = now
        return True
    if now - last_contact[phone] > 1800:  # 30 minutos
        last_contact[phone] = now
        return True
    return False

# === WEBHOOK WHATSAPP ===
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
    print("📥 Mensaje recibido:", data)

    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" in changes:
            msg = changes["messages"][0]
            phone = msg["from"]
            text = msg["text"]["body"].strip().lower()

            # Si hay una conversación activa, no mostrar menú
            if phone in active_conversations and active_conversations[phone]:
                send_telegram_message(f"💬 {phone}: {text}")
                return jsonify({"status": "ok"}), 200

            # Saludo inicial
            if need_new_greeting(phone):
                saludo = ("👋 ¡Hola! Soy *RekyBot* de *REKAR*, red de enfermería y kinesiología.\n"
                          "Nuestro horario de atención es de *lunes a sábado de 9 a 19 hs*.\n\n"
                          "¿Podés decirme tu nombre, por favor?")
                send_whatsapp_message(phone, saludo)
                send_telegram_message(f"📞 Nuevo contacto: {phone}")
            elif "soy" in text or "me llamo" in text:
                nombre = text.replace("soy", "").replace("me llamo", "").strip().title()
                active_conversations[phone] = True
                send_whatsapp_message(phone, f"Gracias {nombre}. Un operador humano de REKAR se pondrá en contacto contigo pronto.\nPor favor, dejanos tu consulta.")
                send_telegram_message(f"👤 {nombre} ({phone}) se registró y espera atención.")
            else:
                send_whatsapp_message(phone, "Por favor, decime tu nombre para poder ayudarte 🙂")
                send_telegram_message(f"📨 {phone}: {text}")

    except Exception as e:
        print("❌ Error procesando mensaje:", e)

    return jsonify({"status": "ok"}), 200


# === WEBHOOK TELEGRAM ===
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    print("📩 Evento Telegram:", data)

    if "message" in data:
        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "")

        # Asegurar que venga del grupo correcto
        if chat_id != str(TELEGRAM_CHAT_ID):
            print("Mensaje ignorado: viene de otro chat.")
            return jsonify({"status": "ignored"}), 200

        # Detectar comando /enviar
        if text.startswith("/enviar"):
            try:
                parts = text.split(" ", 2)
                if len(parts) < 3:
                    send_telegram_message("❌ Formato inválido. Usá: /enviar <número> <mensaje>")
                    return jsonify({"status": "error"}), 200

                phone = parts[1].replace("+", "").strip()
                message = parts[2].strip()

                if send_whatsapp_message(phone, message):
                    active_conversations[phone] = True
                    send_telegram_message(f"✅ Mensaje enviado a {phone}: {message}")
                else:
                    send_telegram_message(f"⚠️ No se pudo enviar el mensaje a {phone}")
            except Exception as e:
                print("❌ Error procesando /enviar:", e)
                send_telegram_message(f"Error al enviar mensaje: {e}")

    return jsonify({"status": "ok"}), 200


# === EJECUCIÓN SERVIDOR ===
if __name__ == '__main__':
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
