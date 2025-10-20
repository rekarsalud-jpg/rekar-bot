from flask import Flask, request, jsonify
import requests, os, json, time

app = Flask(__name__)

# ======= VARIABLES DE ENTORNO =======
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "rekar_verificacion")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = "#todo-rekar-mensajeria-wtz"
PORT = int(os.getenv("PORT", 10000))

SLACK_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
}

# ======= MEMORIA DE CLIENTES =======
CLIENTES_FILE = "clientes.json"

def cargar_clientes():
    try:
        with open(CLIENTES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def guardar_clientes(data):
    with open(CLIENTES_FILE, "w") as f:
        json.dump(data, f)

clientes = cargar_clientes()

# ======= FUNCIONES =======

def enviar_whatsapp(numero, mensaje):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": numero.replace("+",""),
        "type": "text",
        "text": {"body": mensaje}
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"📤 WA -> {numero} ({r.status_code}): {r.text}")

def slack_post(msg):
    r = requests.post("https://slack.com/api/chat.postMessage",
                      headers=SLACK_HEADERS,
                      json={"channel": SLACK_CHANNEL, "text": msg})
    print(f"📤 Slack -> {r.status_code}: {r.text}")

# ======= RUTAS =======

@app.route("/", methods=["GET"])
def home():
    return "✅ REKAR Bot conectado correctamente.", 200

# --- Verificación de webhook de Meta ---
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✔ Webhook verificado correctamente.")
        return challenge, 200
    else:
        print("❌ Error de verificación del webhook.")
        return "Error de verificación", 403

# --- Recepción de mensajes desde WhatsApp ---
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("📩 WA recibido:", json.dumps(data, ensure_ascii=False))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return "no messages", 200

        msg = entry["messages"][0]
        numero = msg["from"]
        texto = msg.get("text", {}).get("body", "").strip()
        timestamp = time.time()

        # Si el cliente es nuevo
        if numero not in clientes:
            clientes[numero] = {"nombre": None, "ultimo_mensaje": timestamp}
            guardar_clientes(clientes)
            enviar_whatsapp(numero, "👋 ¡Hola! Soy el asistente de REKAR. ¿Podrías decirme tu nombre para registrarte?")
            slack_post(f"🆕 Nuevo cliente: {numero} escribió: {texto}")
        else:
            cliente = clientes[numero]
            cliente["ultimo_mensaje"] = timestamp
            guardar_clientes(clientes)

            if cliente["nombre"] is None:
                cliente["nombre"] = texto
                guardar_clientes(clientes)
                enviar_whatsapp(numero, f"¡Gracias {texto}! 😊 ¿En qué puedo ayudarte hoy?")
                slack_post(f"✅ {texto} ({numero}) se registró correctamente.")
            else:
                enviar_whatsapp(numero, f"👋 Hola de nuevo, {cliente['nombre']}. ¿Querés continuar con tu consulta?")
                slack_post(f"📨 {cliente['nombre']} ({numero}) dice: {texto}")

    except Exception as e:
        print("⚠️ Error procesando el mensaje:", e)

    return "EVENT_RECEIVED", 200

# --- Mensajes desde Slack hacia WhatsApp ---
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json()
    print("📥 Slack evento:", json.dumps(data, ensure_ascii=False))

    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    event = data.get("event", {})
    text = (event.get("text") or "").strip()
    user = event.get("user")

    if not text or not user:
        return "ignore", 200

    # formato: +54911XXXX mensaje
    if text.startswith("+549"):
        try:
            partes = text.split(" ", 1)
            if len(partes) == 2:
                numero, mensaje = partes
                enviar_whatsapp(numero, mensaje)
                slack_post(f"✅ Mensaje enviado a {numero}: {mensaje}")
            else:
                slack_post("⚠️ Formato incorrecto. Usa: `+54911XXXX mensaje`")
        except Exception as e:
            slack_post(f"❌ Error enviando mensaje: {e}")
    else:
        slack_post("💬 Para responder a un cliente, usa: `+54911XXXX mensaje`")

    return "ok", 200


if __name__ == "__main__":
    print("🚀 BOT INICIADO Y ESCUCHANDO...")
    app.run(host="0.0.0.0", port=PORT)
