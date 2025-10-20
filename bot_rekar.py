import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================
# 🔧 VARIABLES DE ENTORNO
# ==============================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# Diccionario para guardar nombres ↔ teléfonos
nombres = {}
usuarios_saludados = set()


# ======================================
# 🏠 RUTA PRINCIPAL (para verificar)
# ======================================
@app.route('/')
def home():
    return "✅ RekarBot está activo y escuchando", 200


# ======================================
# 🧩 VERIFICACIÓN WEBHOOK DE META (WhatsApp)
# ======================================
@app.route('/webhook', methods=['GET'])
def verificar_token():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook de Meta verificado correctamente.")
        return challenge, 200
    else:
        print("❌ Error en la verificación del webhook.")
        return "Token inválido", 403


# ======================================
# 📩 RECEPCIÓN DE MENSAJES DESDE WHATSAPP
# ======================================
@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    data = request.get_json()
    print("📥 Mensaje recibido:", data)

    try:
        message = data['entry'][0]['changes'][0]['value']['messages'][0]
        phone_number = message['from']
        text = message['text']['body'].strip()

        # Si es nuevo usuario
        if phone_number not in usuarios_saludados:
            usuarios_saludados.add(phone_number)
            nombres[text.lower()] = phone_number  # Guardar nombre -> número

            mensaje_bienvenida = (
                f"¡Bienvenido/a a REKAR Salud, {text}! 👋\n\n"
                "Somos un equipo profesional especializado en Kinesiología y Enfermería Domiciliaria.\n"
                "📅 Horarios de atención: Lunes a Viernes de 9 a 18 hs.\n\n"
                "Por favor, aguardá unos minutos, un representante se comunicará con vos."
            )
            enviar_whatsapp(phone_number, mensaje_bienvenida)
            notificar_slack(f"Nuevo cliente registrado: {text} ({phone_number})")

        else:
            # Cliente ya registrado → reenviar a Slack
            notificar_slack(f"Nuevo mensaje de cliente:\n📞 {phone_number}\n💬 {text}")

    except Exception as e:
        print("⚠️ Error procesando mensaje de WhatsApp:", e)

    return "ok", 200


# ======================================
# 📤 ENVÍO DE MENSAJE A WHATSAPP
# ======================================
def enviar_whatsapp(phone, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviando a WhatsApp:", response.text)


# ======================================
# 📢 NOTIFICAR MENSAJE EN SLACK
# ======================================
def notificar_slack(texto):
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": texto})
        print("✅ Notificación enviada a Slack.")
    except Exception as e:
        print("⚠️ Error enviando mensaje a Slack:", e)


# ======================================
# 💬 RECEPCIÓN DE MENSAJES DESDE SLACK
# ======================================
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json()
    print("📥 Evento recibido desde Slack:", data)

    # Slack envía challenge para verificar
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]}), 200

    try:
        event = data.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id"):
            text = event.get("text", "").strip()
            user = event.get("user", "")
            print(f"💬 Mensaje desde Slack ({user}): {text}")

            # Ejemplo: "rodrigo Hola, cómo estás?"
            partes = text.split(" ", 1)
            if len(partes) == 2:
                nombre = partes[0].lower()
                mensaje = partes[1]

                if nombre in nombres:
                    phone = nombres[nombre]
                    enviar_whatsapp(phone, mensaje)
                    print(f"✅ Enviado a {nombre} ({phone}) desde Slack")
                else:
                    print(f"⚠️ No se encontró el cliente '{nombre}'")
                    notificar_slack(f"⚠️ No se encontró el cliente '{nombre}' en la lista.")

    except Exception as e:
        print("⚠️ Error procesando evento Slack:", e)

    return "ok", 200


# ======================================
# 🚀 INICIO DEL SERVIDOR FLASK
# ======================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
