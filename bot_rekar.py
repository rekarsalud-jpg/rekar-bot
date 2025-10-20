from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ==============================
# VARIABLES DE ENTORNO
# ==============================
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # Token de Meta WhatsApp Cloud API
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # ID de número de WhatsApp
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")  # Webhook de Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")  # Token del bot Slack
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")  # Token de verificación Meta

# ==============================
# FUNCIONES DE UTILIDAD
# ==============================

def enviar_whatsapp(numero, mensaje):
    """Envía un mensaje de WhatsApp usando la API de Meta."""
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
        print(f"📤 Enviando a WhatsApp {numero}: {mensaje}")
        print("➡️ Respuesta Meta:", r.status_code, r.text)
    except Exception as e:
        print("⚠️ Error al enviar mensaje de WhatsApp:", e)


def enviar_a_slack(texto):
    """Envía mensaje a Slack vía Webhook."""
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": texto})
        print("📤 Enviado a Slack:", texto)
    except Exception as e:
        print("⚠️ Error al enviar a Slack:", e)


# ==============================
# ENDPOINT WEBHOOK META (WHATSAPP)
# ==============================

@app.route("/webhook", methods=["GET", "POST"])
def webhook_whatsapp():
    """Recibe mensajes de WhatsApp y los reenvía a Slack."""
    if request.method == "GET":
        # Verificación inicial de Meta
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token de verificación incorrecto", 403

    elif request.method == "POST":
        data = request.get_json()
        print("📩 Mensaje recibido de WhatsApp:", data)

        try:
            entry = data["entry"][0]["changes"][0]["value"]

            # Si hay mensajes
            if "messages" in entry:
                mensaje = entry["messages"][0]
                numero = mensaje["from"]
                texto = mensaje.get("text", {}).get("body", "")

                # Buscar nombre si viene en contacto
                nombre = entry.get("contacts", [{}])[0].get("profile", {}).get("name", "Desconocido")

                texto_slack = f"📱 *Nuevo mensaje de cliente*\n*Teléfono:* +{numero}\n*Nombre:* {nombre}\n*Mensaje:* {texto}"
                enviar_a_slack(texto_slack)

                # Responder automáticamente pidiendo nombre si no se conoce
                if nombre == "Desconocido":
                    enviar_whatsapp(numero, "👋 Hola! Soy el asistente de REKAR. ¿Podrías decirme tu nombre para registrarte?")
        except Exception as e:
            print("⚠️ Error procesando mensaje de WhatsApp:", e)

        return "EVENT_RECEIVED", 200


# ==============================
# ENDPOINT EVENTOS SLACK
# ==============================

@app.route('/slack/events', methods=['POST'])
def slack_events():
    """Recibe eventos de Slack (mensajes en canal) y los reenvía a WhatsApp."""
    data = request.get_json()
    print("📥 Evento recibido desde Slack:", data)

    # ✅ Validar challenge de verificación
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    try:
        event = data.get("event", {})
        subtype = event.get("subtype", "")
        user = event.get("user")
        text = event.get("text", "").strip()

        # Evitar responder a mensajes del propio bot
        if subtype == "bot_message" or user is None:
            return "OK", 200

        # Si empieza con +549 se interpreta como número + mensaje
        if text.startswith("+549"):
            partes = text.split(" ", 1)
            if len(partes) == 2:
                numero, mensaje = partes
                enviar_whatsapp(numero, mensaje)
                print(f"✅ Enviado a WhatsApp {numero}: {mensaje}")
            else:
                enviar_a_slack("⚠️ Formato incorrecto. Usá: +549XXXXXXXX mensaje")

        # Si no empieza con número, el bot pide nombre
        else:
            slack_response = {
                "text": "Por favor, escribí tu número de WhatsApp (con +549...) y tu nombre para registrarte 🙌"
            }
            requests.post(SLACK_WEBHOOK_URL, json=slack_response)
            print("ℹ️ Solicitud de nombre enviada a Slack")

    except Exception as e:
        print("⚠️ Error procesando evento Slack:", e)

    return "OK", 200


# ==============================
# INICIO DEL SERVICIO
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
