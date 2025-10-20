import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# 🔐 Variables de entorno
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# 💬 Diccionarios
clientes = {}  # guarda {telefono: {"nombre": "Juan Pérez", "estado": "esperando_nombre"}}
nombres = {}   # guarda {nombre.lower(): telefono}

# 🏠 Ruta base
@app.route('/')
def home():
    return "✅ RekarBot activo y escuchando.", 200


# ✅ Verificación de Webhook Meta
@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token inválido", 403


# 📩 Recepción de mensajes de WhatsApp
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        message = entry["messages"][0]
        phone = message["from"]
        text = message["text"]["body"].strip()

        # Si el cliente es nuevo
        if phone not in clientes:
            clientes[phone] = {"nombre": None, "estado": "esperando_nombre"}
            send_whatsapp(phone,
                "👋 Hola, bienvenido a *Rekar Salud*!\n"
                "Somos un equipo de profesionales especializados en kinesiología y enfermería domiciliaria.\n"
                "🕐 Horario de atención: Lunes a Viernes de 9 a 18 hs.\n\n"
                "Por favor escribime tu *nombre y apellido* para poder ayudarte mejor. 🙏"
            )
            return "ok", 200

        # Si está esperando que deje su nombre
        if clientes[phone]["estado"] == "esperando_nombre":
            nombre = text.title()
            clientes[phone]["nombre"] = nombre
            clientes[phone]["estado"] = "registrado"
            nombres[nombre.lower()] = phone

            send_whatsapp(phone, f"Gracias, *{nombre}*! 🙌 En unos minutos un representante te responderá.")
            requests.post(SLACK_WEBHOOK_URL, json={"text": f"🆕 Nuevo cliente registrado: *{nombre}* ({phone})"})
            return "ok", 200

        # Si ya está registrado, reenviar el mensaje a Slack
        nombre = clientes[phone]["nombre"]
        texto = f"📩 *{nombre}* ({phone}) escribió:\n“{text}”"
        requests.post(SLACK_WEBHOOK_URL, json={"text": texto})

    except Exception as e:
        print("⚠️ Error al procesar mensaje:", e)

    return "ok", 200


# 📤 Enviar mensaje por WhatsApp
def send_whatsapp(to, message):
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


# 💬 Endpoint para recibir respuestas desde Slack
@app.route('/slack', methods=['POST'])
def slack_command():
    text = request.form.get("text")
    if not text:
        return jsonify({"response_type": "ephemeral", "text": "⚠️ Usá el formato `/responder nombre mensaje`"}), 200

    parts = text.split(" ", 1)
    if len(parts) < 2:
        return jsonify({"response_type": "ephemeral", "text": "⚠️ Formato incorrecto. Ejemplo: `/responder Juan Hola!`"}), 200

    nombre, mensaje = parts[0].lower(), parts[1]
    if nombre not in nombres:
        return jsonify({"response_type": "ephemeral", "text": f"⚠️ No se encontró el cliente *{nombre}*."}), 200

    phone = nombres[nombre]
    send_whatsapp(phone, mensaje)

    return jsonify({"response_type": "in_channel", "text": f"✅ Mensaje enviado a *{nombre}*: “{mensaje}”"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
