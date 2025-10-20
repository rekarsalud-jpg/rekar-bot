import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#todo-rekar-mensajeria-wtz")

EMAIL_DESTINATION = os.getenv("EMAIL_DESTINATION")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

last_contact = {}

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

def send_slack_message(text):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    data = {"channel": SLACK_CHANNEL, "text": text}
    r = requests.post(url, headers=headers, json=data)
    print("📩 Enviado a Slack:", r.status_code, r.text)
    return r.status_code == 200

def send_email(subject, body):
    if not EMAIL_DESTINATION: return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_DESTINATION
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("📧 Email enviado correctamente")
    except Exception as e:
        print("❌ Error al enviar email:", e)

def need_new_greeting(phone):
    now = time.time()
    if phone not in last_contact:
        last_contact[phone] = now
        return True
    if now - last_contact[phone] > 1800:  # 30 min
        last_contact[phone] = now
        return True
    return False

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

            if need_new_greeting(phone):
                saludo = ("¡Hola! Soy *RekyBot 🤖* de *REKAR*, red de enfermería y kinesiología.\n"
                          "Nuestro horario de atención es de *lunes a viernes de 8 a 18 hs*.\n\n"
                          "¿Podés decirme tu nombre, por favor?\n"
                          "dejanos tu pregunta👇")
                send_whatsapp_message(phone, saludo)
                send_slack_message(f"📞 Nuevo contacto: {phone}")
                send_email("Nuevo contacto REKAR", f"Teléfono: {phone}\nMensaje: {text}")
            elif "soy" in text or "me llamo" in text:
                nombre = text.replace("soy", "").replace("me llamo", "").replace("","").strip()
                send_whatsapp_message(phone, f"Gracias {nombre}. Un operador humano de REKAR se pondrá en contacto contigo pronto.\nPor favor, dejanos tu consulta.")
                send_slack_message(f"👤 {nombre} ({phone}) se registró y espera atención.")
                send_email("Cliente identificado", f"Nombre: {nombre}\nTeléfono: {phone}")
            else:
                send_slack_message(f"📨 {phone}: {text}")

    except Exception as e:
        print("❌ Error procesando mensaje:", e)

    return jsonify({"status": "ok"}), 200

@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.get_json()
    print("📥 Slack evento:", data)

    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    try:
        event = data.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id"):
            text = event.get("text", "")
            if text.startswith("+549"):
                parts = text.split(" ", 1)
                if len(parts) == 2:
                    phone, msg = parts
                    send_whatsapp_message(phone.replace("+", ""), msg)
                    send_slack_message(f"✅ Mensaje enviado a {phone}")
    except Exception as e:
        print("❌ Error evento Slack:", e)

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

