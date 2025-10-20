import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================
# 🔧 VARIABLES DE ENTORNO
# ==============================
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")

# ==============================
# 💾 ESTRUCTURAS DE DATOS
# ==============================
clientes = {}  # Guarda {numero: nombre}
usuarios_saludados = set()  # Guarda números a los que ya se saludó

# ==============================
# 🟢 VERIFICACIÓN WEBHOOK META
# ==============================
@app.route('/webhook', methods=['GET'])
def verify():
    """Verifica el token de Meta (para conexión con WhatsApp Cloud API)"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente con Meta.")
        return challenge, 200
    else:
        return "Token inválido", 403


# ==============================
# 📩 RECEPCIÓN DE MENSAJES WHATSAPP
# ==============================
@app.route('/webhook', methods=['POST'])
def receive_message():
    """Recibe mensajes de WhatsApp (Meta Webhook)"""
    data = request.get_json()
    print("📥 Webhook recibido desde Meta:", data)

    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})

        # Si no hay mensajes, lo ignoramos (puede ser "status" u otro evento)
        messages = value.get("messages", [])
        if not messages:
            print("⚠️ Evento sin campo 'messages' (status o delivery report). Ignorado.")
            return "no_message", 200

        message = messages[0]
        phone = message.get("from")
        text = message.get("text", {}).get("body", "").strip()

        if not phone or not text:
            print("⚠️ Evento sin número o texto. Ignorado.")
            return "invalid", 200

        # ==============================
        # NUEVO CLIENTE → Pedir nombre
        # ==============================
        if phone not in clientes:
            if phone not in usuarios_saludados:
                enviar_whatsapp(
                    phone,
                    "👋 ¡Hola! Bienvenido a *Rekar Salud*.\n\n"
                    "Somos un equipo especializado en *kinesiología* y *enfermería domiciliaria*.\n"
                    "Por favor, escribinos tu *nombre completo* para registrarte 📝."
                )
                usuarios_saludados.add(phone)
                return "ok", 200
            else:
                # Guarda el nombre y avisa a Slack
                clientes[phone] = text
                enviar_whatsapp(phone, f"Gracias, {text}. Un representante se comunicará contigo en breve. 😊")
                notificar_slack(phone, f"📋 Nuevo cliente registrado: {text}")
                return "ok", 200

        # ==============================
        # CLIENTE EXISTENTE → reenviar mensaje a Slack
        # ==============================
        else:
            notificar_slack(phone, text)
            return "ok", 200

    except Exception as e:
        print("⚠️ Error procesando mensaje:", e)
        return "error", 500


# ==============================
# 💬 ENVÍO DE MENSAJES WHATSAPP
# ==============================
def enviar_whatsapp(to, message):
    """Envía texto por WhatsApp Cloud API"""
    try:
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
    except Exception as e:
        print("⚠️ Error enviando mensaje a WhatsApp:", e)


# ==============================
# 🔔 ENVÍO DE NOTIFICACIONES A SLACK
# ==============================
def notificar_slack(phone, message):
    """Envía mensaje al canal Slack"""
    nombre = clientes.get(phone, "(sin registrar)")
    texto = (
        f"📩 *Nuevo mensaje de cliente*\n"
        f"👤 *Nombre:* {nombre}\n"
        f"📱 *Tel:* {phone}\n"
        f"💬 *Mensaje:* {message}"
    )
    enviar_a_slack(texto)


def enviar_a_slack(text):
    """Envía texto simple al canal de Slack"""
    try:
        url = "https://slack.com/api/chat.postMessage"
        payload = {
            "channel": "#todo-rekar-mensajeria-wtz",  # Asegurate que coincida con tu canal real
            "text": text
        }
        headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
        r = requests.post(url, json=payload, headers=headers)
        print("📨 Enviado a Slack:", r.text)
    except Exception as e:
        print("⚠️ Error enviando a Slack:", e)


# ==============================
# 🔄 RECEPCIÓN DE MENSAJES DESDE SLACK
# ==============================
@app.route('/slack/events', methods=['POST'])
def slack_events():
    """Recibe mensajes desde Slack y los reenvía al cliente WhatsApp"""
    data = request.get_json()
    print("📥 Evento recibido desde Slack:", data)

    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    try:
        event = data.get("event", {})
        text = event.get("text", "")
        user = event.get("user", "")
        subtype = event.get("subtype")

        # Ignorar mensajes automáticos del bot
        if subtype == "bot_message":
            return "ignored", 200

        # Formato esperado: +54XXXXXXXX Mensaje
        if text.startswith("+54") and " " in text:
            partes = text.split(" ", 1)
            phone = partes[0].replace("+", "")
            msg = partes[1]
            enviar_whatsapp(phone, f"💬 {msg}")
            enviar_a_slack(f"✅ Mensaje reenviado a {phone}")
        else:
            print("⚠️ Mensaje interno o sin número detectado:", text)

    except Exception as e:
        print("⚠️ Error procesando evento Slack:", e)

    return "ok", 200


# ==============================
# 🚀 EJECUCIÓN LOCAL / RENDER
# ==============================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
