# === REKAR BOT v2 (Python / Flask) ===
# Bot oficial de WhatsApp REKAR Salud
# Compatible con Meta Graph API v21 + Render Hosting

from flask import Flask, request
import os
import requests

app = Flask(__name__)

# === VARIABLES ===
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

@app.route('/')
def index():
    return "✅ RekarBot funcionando correctamente", 200


# === VERIFICACIÓN DEL WEBHOOK (GET) ===
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    print(f"🔍 Verificación recibida: mode={mode}, token={token}, challenge={challenge}")

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("🟢 Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Error de verificación")
        return "Error de verificación", 403


# === RECEPCIÓN DE MENSAJES (POST) ===
@app.route('/webhook', methods=['POST'])
def receive_message():
    try:
        data = request.get_json()

        if data.get("object") == "whatsapp_business_account":
            entry = data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]

            if "messages" in value:
                message = value["messages"][0]
                from_number = message["from"]
                text = message.get("text", {}).get("body", "")

                print(f"📩 Mensaje recibido de {from_number}: {text}")

                reply = f"""👋 Hola, soy el asistente automático de *REKAR Salud*.
Recibí tu mensaje: "{text}".
En breve uno de nuestros operadores se comunicará con vos.
🕘 Horario de atención: Lunes a Sábado de 9 a 19 hs."""

                send_message(from_number, reply)

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print(f"❌ Error al procesar mensaje: {e}")
        return "Error interno", 500


# === FUNCIÓN PARA ENVIAR MENSAJES ===
def send_message(to, message):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        print(f"✅ Mensaje enviado correctamente a {to}")
    else:
        print(f"❌ Error al enviar mensaje: {response.text}")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
