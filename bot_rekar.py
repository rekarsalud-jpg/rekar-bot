import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Variables de entorno
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")

# Diccionarios para seguimiento
clientes = {}  # {numero: nombre}
usuarios_saludados = set()

# ====== WHATSAPP: RECEPCIÓN Y RESPUESTA ======
@app.route('/webhook', methods=['GET'])
def verify():
    """Verifica el token de Meta"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente.")
        return challenge, 200
    else:
        return "Token inválido", 403


@app.route('/webhook', methods=['POST'])
def receive_message():
    """Recibe mensajes desde WhatsApp"""
    data = request.get_json()
    print("📥 Mensaje recibido:", data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = message["from"]
        text = message["text"]["body"].strip()

        # Si no tenemos el nombre del cliente, lo pedimos
        if phone not in clientes:
            if phone not in usuarios_saludados:
                enviar_whatsapp(phone, 
                    "👋 ¡Hola! Bienvenido a *Rekar Salud*.\n\n"
                    "Somos un equipo especializado en kinesiología y enfermería domiciliaria.\n"
                    "Por favor, escribinos tu *nombre completo* para registrarte 📝."
                )
                usuarios_saludados.add(phone)
                return "OK", 200
            else:
                # El usuario responde con su nombre
                clientes[phone] = text
                enviar_whatsapp(phone, 
                    f"Gracias, {text}. Un representante se comunicará contigo en breve. 😊"
                )
                notificar_slack(phone, text)
                return "OK", 200

        else:
            # Cliente ya registrado, reenviamos mensaje a Slack
            notificar_slack(phone, text)
            return "OK", 200

    except Exception as e:
        print("⚠️ Error procesando mensaje:", e)
        return "error", 500


# ====== WHATSAPP: ENVÍO ======
def enviar_whatsapp(to, message):
    """Envía mensajes por WhatsApp"""
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
    print("📤 Enviado a WhatsApp:", response.text)


# ====== SLACK: AVISO ======
def notificar_slack(phone, message):
    """Envía notificación a Slack"""
    nombre = clientes.get(phone, "(sin registrar)")
    texto = f"📩 *Nuevo mensaje de cliente:*\n👤 {nombre}\n📱 {phone}\n💬 {message}"
    enviar_a_slack(texto)


def enviar_a_slack(text):
    """Envía texto simple a Slack usando bot token"""
    url = "https://slack.com/api/chat.postMessage"
    payload = {
        "channel": "#todo-rekar-mensajeria-wtz",  # Canal donde llegan los mensajes
        "text": text
    }
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    r = requests.post(url, json=payload, headers=headers)
    print("📨 Enviado a Slack:", r.text)


# ====== SLACK: RECEPCIÓN ======
@app.route('/slack/events', methods=['POST'])
def slack_events():
    """Recibe mensajes de Slack"""
    data = request.get_json()
    print("📥 Evento recibido desde Slack:", data)

    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    try:
        event = data.get("event", {})
        text = event.get("text", "")
        user = event.get("user", "")
        channel = event.get("channel", "")

        # Evitar loops (si el mensaje es del bot)
        if event.get("subtype") == "bot_message":
            return "OK", 200

        # Buscar si el mensaje parece una respuesta hacia un cliente
        if text.startswith("+54") and len(text.split()) > 1:
            # Formato esperado: +54XXXXXXXX mensaje
            partes = text.split(" ", 1)
            phone = partes[0].replace("+", "")
            msg = partes[1]
            enviar_whatsapp(phone, f"💬 {msg}")
            enviar_a_slack(f"✅ Mensaje reenviado a {phone}")
        else:
            enviar_a_slack(f"🤖 Mensaje interno recibido de Slack: {text}")

    except Exception as e:
        print("⚠️ Error procesando evento de Slack:", e)

    return "OK", 200


# ====== INICIO ======
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
