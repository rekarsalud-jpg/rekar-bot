from flask import Flask, request
import requests
import os

app = Flask(__name__)

# 🔹 Variables de entorno
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# 🔹 Usuarios ya saludados
usuarios_saludados = set()

@app.route('/')
def home():
    return "✅ RekarBot activo y escuchando correctamente", 200


# =========================
# 🔸 VERIFICACIÓN META
# =========================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente.")
        return challenge, 200
    else:
        print("❌ Error de verificación del webhook.")
        return "Token inválido", 403


# =========================
# 🔸 RECEPCIÓN DE MENSAJES
# =========================
@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_number = message["from"]
        text = message["text"]["body"].strip()

        # Si es un nuevo usuario, enviar bienvenida y notificar Slack
        if phone_number not in usuarios_saludados:
            usuarios_saludados.add(phone_number)
            bienvenida = (
                "👋 ¡Bienvenido/a a *REKAR Salud*!\n\n"
                "Somos un equipo profesional especializado en *Kinesiología y Enfermería Domiciliaria*.\n"
                "📧 Podés escribirnos a *rekar.salud@gmail.com*\n"
                "🕐 Horarios de atención: *Lunes a Viernes de 9 a 18 hs.*\n\n"
                "Aguarde un momento, un representante se comunicará con usted. 🙏"
            )
            enviar_mensaje_whatsapp(phone_number, bienvenida)
            notificar_slack(phone_number, text)
        else:
            # Si ya fue saludado, solo notificamos a Slack
            notificar_slack(phone_number, text)

    except Exception as e:
        print(f"⚠️ Error al procesar mensaje: {e}")

    return "ok", 200


# =========================
# 🔸 ENVÍO DE MENSAJES A WHATSAPP
# =========================
def enviar_mensaje_whatsapp(to, message):
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
    print(f"📤 Enviado a {to}: {response.text}")


# =========================
# 🔸 AVISO A SLACK
# =========================
def notificar_slack(phone, mensaje):
    texto = f"📞 *Nuevo mensaje de cliente:*\nTeléfono: `{phone}`\nMensaje: {mensaje}"
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": texto})
        print("✅ Notificación enviada a Slack.")
    except Exception as e:
        print(f"⚠️ Error al notificar a Slack: {e}")


# =========================
# 🔸 RESPUESTA DESDE SLACK
# =========================
@app.route("/slack", methods=["POST"])
def responder_desde_slack():
    data = request.form
    texto = data.get("text", "")
    partes = texto.split(" ", 1)

    if len(partes) < 2:
        return "⚠️ Formato inválido. Usa: /responder <numero> <mensaje>", 200

    numero, mensaje = partes
    enviar_mensaje_whatsapp(numero, mensaje)
    return f"✅ Mensaje enviado a {numero}", 200


# =========================
# 🔸 MAIN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
