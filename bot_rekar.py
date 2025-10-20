from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

# ==============================
# VARIABLES DE ENTORNO
# ==============================
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

HEADERS_SLACK = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
}

# Base temporal de clientes conocidos
clientes_registrados = {}

# ==============================
# FUNCIONES
# ==============================
def enviar_whatsapp(numero, mensaje):
    """Envía mensaje a WhatsApp."""
    try:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "messaging_product": "whatsapp",
            "to": numero.replace("+", "").strip(),
            "type": "text",
            "text": {"body": mensaje}
        }
        r = requests.post(url, headers=headers, json=data)
        print(f"📤 Enviado a WhatsApp {numero}: {mensaje}")
        print("➡️ Meta:", r.status_code, r.text)
    except Exception as e:
        print("❌ Error enviando WhatsApp:", e)


def enviar_a_slack(mensaje, canal="#todo-rekar-mensajeria-wtz"):
    """Envía texto al canal Slack con token del bot."""
    try:
        data = {"channel": canal, "text": mensaje}
        r = requests.post("https://slack.com/api/chat.postMessage", headers=HEADERS_SLACK, json=data)
        print("📤 Enviado a Slack:", mensaje)
        print("➡️ Slack:", r.status_code, r.text)
    except Exception as e:
        print("❌ Error enviando a Slack:", e)


# ==============================
# WHATSAPP WEBHOOK (ENTRADA)
# ==============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook_whatsapp():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            print("✅ Verificación Meta OK")
            return challenge
        return "Token inválido", 403

    if request.method == "POST":
        data = request.get_json()
        print("📩 WhatsApp recibido:", json.dumps(data, indent=2, ensure_ascii=False))
        try:
            entry = data["entry"][0]["changes"][0]["value"]
            if "messages" in entry:
                msg = entry["messages"][0]
                numero = msg["from"]
                texto = msg.get("text", {}).get("body", "").strip()
                nombre = entry.get("contacts", [{}])[0].get("profile", {}).get("name", "Desconocido")

                # Si es un nuevo cliente
                if numero not in clientes_registrados:
                    clientes_registrados[numero] = {"nombre": nombre, "registrado": False}
                    enviar_whatsapp(numero, "👋 Hola! Soy el asistente de REKAR. ¿Podrías decirme tu nombre completo para registrarte?")
                    enviar_a_slack(f"🆕 Nuevo contacto detectado: +{numero} (esperando nombre)")
                else:
                    # Si el cliente responde con su nombre
                    if not clientes_registrados[numero]["registrado"]:
                        clientes_registrados[numero]["nombre"] = texto
                        clientes_registrados[numero]["registrado"] = True
                        enviar_a_slack(f"📱 *Nuevo cliente registrado:* {texto} (+{numero})")
                        enviar_whatsapp(numero, f"Gracias {texto}! 😊 Un profesional de REKAR se comunicará con vos pronto.")
                    else:
                        # Cliente ya registrado → enviar mensaje normal a Slack
                        nombre = clientes_registrados[numero]['nombre']
                        mensaje = f"📱 *Nuevo mensaje de cliente*\n*Teléfono:* +{numero}\n*Nombre:* {nombre}\n*Mensaje:* {texto}"
                        enviar_a_slack(mensaje)
        except Exception as e:
            print("⚠️ Error procesando WhatsApp:", e)

        return "EVENT_RECEIVED", 200


# ==============================
# SLACK EVENTS (RESPUESTA)
# ==============================
@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        data = request.get_json(force=True)
        print("📥 Evento Slack:", json.dumps(data, indent=2, ensure_ascii=False))

        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        event = data.get("event", {})
        if not event:
            return "NO_EVENT", 200

        user = event.get("user")
        subtype = event.get("subtype", "")
        text = event.get("text", "").strip()

        if subtype == "bot_message" or not text or not user:
            return "IGNORE", 200

        if text.startswith("+549"):
            partes = text.split(" ", 1)
            if len(partes) == 2:
                numero, mensaje = partes
                enviar_whatsapp(numero, mensaje)
                enviar_a_slack(f"✅ Enviado a WhatsApp {numero}")
            else:
                enviar_a_slack("⚠️ Formato incorrecto. Usá: +549XXXXXXXX mensaje")
        else:
            enviar_a_slack("Para responder a un cliente escribí: +549XXXXXXXX mensaje 🙌")

    except Exception as e:
        print("❌ Error general Slack:", e)
        return jsonify({"error": str(e)}), 500

    return "OK", 200


# ==============================
# ERRORES GLOBALES
# ==============================
@app.errorhandler(Exception)
def handle_exception(e):
    print("🚨 Error Flask:", e)
    return jsonify({"error": str(e)}), 500


# ==============================
# EJECUCIÓN
# ==============================
if __name__ == "__main__":
    print("🚀 Iniciando REKAR-BOT con registro de nombre.")
    app.run(host="0.0.0.0", port=PORT)
