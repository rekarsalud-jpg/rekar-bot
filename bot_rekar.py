from flask import Flask, request
import requests
import os

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# 👉 Webhook de Slack (te paso luego cómo obtenerlo)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TU_WEBHOOK_DE_SLACK")

# 👉 Guardamos los números que ya recibieron la bienvenida
usuarios_saludados = set()

@app.route('/')
def home():
    return "🤖 RekarBot está activo y escuchando ✅"

# ✅ Verificación del webhook de Meta
@app.route('/webhook', methods=['GET'])
def verify():
    verify_token = VERIFY_TOKEN
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == verify_token:
            print("✅ Webhook verificado correctamente.")
            return challenge, 200
        else:
            return "❌ Token inválido", 403
    return "Faltan parámetros", 400

# ✅ Recepción de mensajes
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_number = message["from"]
        text = message["text"]["body"].lower().strip()

        # ✅ Si es un nuevo usuario, enviamos el mensaje de bienvenida
        if phone_number not in usuarios_saludados:
            usuarios_saludados.add(phone_number)
            bienvenida = (
                "👋 *Bienvenido/a a REKAR Salud*\n\n"
                "Somos un equipo profesional especializado en *kinesiología y enfermería domiciliaria*.\n\n"
                "🕘 Horarios de atención: *Lunes a Viernes de 9 a 18 hs*\n"
                "📧 Email: *rekar.salud@gmail.com*\n\n"
                "Por favor, aguardá unos minutos — un representante te atenderá."
            )
            send_message(phone_number, bienvenida)

            # Aviso en Slack 🚨
            avisar_slack(f"📢 *Nuevo cliente en WhatsApp:* {phone_number}\n🗨️ Mensaje: {text}")

        else:
            # Si ya fue saludado, solo notificamos a Slack
            avisar_slack(f"💬 *{phone_number}* escribió nuevamente: {text}")

    except Exception as e:
        print("⚠️ Error al procesar el mensaje:", e)

    return "OK", 200

# ✅ Envío de mensaje por WhatsApp
def send_message(to, message):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviado:", response.text)

# ✅ Envío de aviso a Slack
def avisar_slack(texto):
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": texto})
        print("📣 Notificación enviada a Slack.")
    except Exception as e:
        print("⚠️ Error al avisar en Slack:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
