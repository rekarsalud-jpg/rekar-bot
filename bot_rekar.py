import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================
# VARIABLES DE ENTORNO
# ==============================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL = "#todo-rekar-mensajeria-wtz"

# ==============================
# FUNCIONES AUXILIARES
# ==============================

def enviar_whatsapp(to, message):
    """Envía un mensaje por WhatsApp usando la API de Meta"""
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
    print(f"📤 Enviado a WhatsApp: {response.text}")

def enviar_a_slack(text):
    """Envía un mensaje al canal de Slack"""
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"channel": SLACK_CHANNEL, "text": text}
    response = requests.post(url, headers=headers, json=data)
    print(f"📨 Enviado a Slack: {response.text}")

# ==============================
# RUTAS
# ==============================

@app.route('/')
def home():
    return "✅ RekarBot está activo y escuchando."

# --- VERIFICACIÓN DEL WEBHOOK ---
@app.route('/webhook', methods=['GET'])
def verificar():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403


# --- RECEPCIÓN DE MENSAJES DE WHATSAPP ---
@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            phone = message["from"]
            text = message["text"]["body"].strip()

            # Si el mensaje contiene nombre, lo registramos
            if text.lower().startswith("soy") or text.lower().startswith("me llamo"):
                nombre = text.split(" ", 1)[1] if " " in text else "Sin nombre"
                enviar_a_slack(f"👤 *Nuevo cliente registrado:* {nombre} ({phone})")
                enviar_whatsapp(phone, "Gracias, " + nombre + ". Un representante se comunicará con vos en breve.")
            else:
                # Mensaje inicial del cliente
                enviar_whatsapp(phone, "👋 ¡Hola! Bienvenido a *Rekar Salud*.\n"
                                       "Por favor, decinos tu nombre para registrarte (por ejemplo: *Soy Juan Pérez*).")
                enviar_a_slack(f"📲 *Nuevo mensaje de cliente:*\nTeléfono: {phone}\nMensaje: {text}")
    except Exception as e:
        print("⚠️ Error procesando mensaje:", e)
        return "Error", 500

    return "OK", 200


# --- EVENTOS DESDE SLACK ---
@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.get_json()
    print("📥 Evento desde Slack:", data)

    # Verificación del challenge
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    try:
        event = data.get("event", {})
        user = event.get("user")
        text = event.get("text", "")
        if text.startswith("+549"):  # Si empieza con número de teléfono, se reenvía a WhatsApp
            numero, mensaje = text.split(" ", 1)
            enviar_whatsapp(numero, mensaje)
            print(f"✅ Enviado al WhatsApp {numero}: {mensaje}")
    except Exception as e:
        print("⚠️ Error procesando evento Slack:", e)

    return "OK", 200


# --- INICIO ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
