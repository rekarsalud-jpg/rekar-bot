from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

# ==============================
# VARIABLES DE ENTORNO
# ==============================
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")           # Meta WhatsApp token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")     # WhatsApp Business ID
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL") # Webhook canal Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")     # Token xoxb de Slack
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")           # Token verificación Meta
PORT = int(os.getenv("PORT", 10000))


# ==============================
# FUNCIONES
# ==============================
def enviar_whatsapp(numero, mensaje):
    """Envía mensaje de texto a WhatsApp vía Meta API"""
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
        print("➡️ Meta response:", r.status_code, r.text)
    except Exception as e:
        print("❌ Error enviando WhatsApp:", e)


def enviar_a_slack(mensaje):
    """Envía mensaje a Slack mediante Webhook"""
    try:
        payload = {"text": mensaje}
        r = requests.post(SLACK_WEBHOOK_URL, json=payload)
        print("📤 Enviado a Slack:", mensaje)
        print("➡️ Slack response:", r.status_code, r.text)
    except Exception as e:
        print("❌ Error enviando a Slack:", e)


# ==============================
# WEBHOOK META (WhatsApp)
# ==============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook_whatsapp():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            print("✅ Verificación Meta OK")
            return challenge
        print("❌ Token de verificación incorrecto")
        return "Error de verificación", 403

    if request.method == "POST":
        data = request.get_json()
        print("📩 Webhook recibido desde Meta:", json.dumps(data, indent=2, ensure_ascii=False))

        try:
            entry = data["entry"][0]["changes"][0]["value"]
            if "messages" in entry:
                msg = entry["messages"][0]
                numero = msg["from"]
                texto = msg.get("text", {}).get("body", "")
                nombre = entry.get("contacts", [{}])[0].get("profile", {}).get("name", "Desconocido")

                mensaje = f"📱 *Nuevo mensaje de cliente*\n*Teléfono:* +{numero}\n*Nombre:* {nombre}\n*Mensaje:* {texto}"
                enviar_a_slack(mensaje)

                if nombre == "Desconocido":
                    enviar_whatsapp(numero, "👋 Hola! Soy el asistente de REKAR. ¿Podrías decirme tu nombre para registrarte?")
        except Exception as e:
            print("⚠️ Error procesando mensaje de Meta:", e)

        return "EVENT_RECEIVED", 200


# ==============================
# EVENTOS DE SLACK
# ==============================
@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        data = request.get_json()
        print("📥 Evento recibido de Slack:", json.dumps(data, indent=2, ensure_ascii=False))

        # Validar challenge (verificación inicial)
        if "challenge" in data:
            print("✅ Challenge Slack verificado")
            return jsonify({"challenge": data["challenge"]})

        event = data.get("event", {})
        if not event:
            print("⚠️ Sin evento en payload Slack")
            return "OK", 200

        subtype = event.get("subtype")
        user = event.get("user")
        text = event.get("text", "").strip()

        # Ignorar mensajes del propio bot
        if subtype == "bot_message" or user is None:
            print("⚙️ Ignorado mensaje del bot")
            return "OK", 200

        # Si comienza con +549 se envía a WhatsApp
        if text.startswith("+549"):
            partes = text.split(" ", 1)
            if len(partes) == 2:
                numero, mensaje = partes
                enviar_whatsapp(numero, mensaje)
            else:
                enviar_a_slack("⚠️ Formato inválido. Usa: +549XXXXXXXX mensaje")

        else:
            # Mensaje sin número → pedir número
            enviar_a_slack("Por favor, escribí tu número de WhatsApp con el formato +549XXXXXXXX 🙌")

    except Exception as e:
        print("❌ Error general procesando evento Slack:", e)

    return "OK", 200


# ==============================
# HANDLER GENERAL DE ERRORES
# ==============================
@app.errorhandler(Exception)
def handle_exception(e):
    print("🚨 Error interno Flask:", e)
    return jsonify({"error": str(e)}), 500


# ==============================
# INICIO DEL SERVIDOR
# ==============================
if __name__ == "__main__":
    print("🚀 Iniciando servidor Flask en puerto", PORT)
    app.run(host="0.0.0.0", port=PORT)
