from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Variables de entorno
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

@app.route('/webhook', methods=['GET'])
def verify():
    """Verifica conexión del webhook con Meta."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Error de verificación', 403


@app.route('/webhook', methods=['POST'])
def webhook():
    """Recibe mensajes desde WhatsApp."""
    data = request.get_json()

    if not data or 'entry' not in data:
        return 'no data', 400

    for entry in data['entry']:
        for change in entry.get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages', [])
            if messages:
                for message in messages:
                    sender = message['from']
                    text = message['text']['body']

                    # Solo responder si es el primer mensaje
                    if not message.get("context"):
                        enviar_mensaje_whatsapp(sender)
                        notificar_slack(sender, text)

    return 'ok', 200


def enviar_mensaje_whatsapp(to):
    """Envía mensaje de bienvenida al cliente."""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": (
                "👋 ¡Hola! Gracias por comunicarte con *Rekar Asistencia Profesional*.\n\n"
                "🕒 Horarios de atención: Lunes a Viernes de 8 a 18 hs.\n"
                "📧 Contacto: rekar.salud@gmail.com\n\n"
                "🧑‍⚕️ En unos minutos un representante se comunicará con vos."
            )
        }
    }
    requests.post(url, headers=headers, json=data)


def notificar_slack(phone, mensaje):
    """Envía aviso a Slack cuando un cliente escribe."""
    texto = f"📩 *Nuevo cliente escribió desde WhatsApp*\n📱 *Teléfono:* {phone}\n💬 *Mensaje:* {mensaje}"
    requests.post(SLACK_WEBHOOK_URL, json={"text": texto})


if __name__ == '__main__':
    app.run(host='0.0.0.0',
    port=int(os.environ.get("port",10000)))
