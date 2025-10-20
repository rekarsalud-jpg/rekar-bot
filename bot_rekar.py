from flask import Flask, request, jsonify
import requests, os, json
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

# ====== ENV ======
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")  # opcional (para avisos simples)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")      # necesario para leer/enviar desde Slack
PORT = int(os.getenv("PORT", 10000))
SLACK_CHANNEL = "#todo-rekar-mensajeria-wtz"

SLACK_HEADERS = {
    "Content-Type": "application/json",
    **({"Authorization": f"Bearer {SLACK_BOT_TOKEN}"} if SLACK_BOT_TOKEN else {})
}

# memoria simple en runtime
clientes = {}  # { numero: nombre|None }

# ====== helpers ======
def enviar_whatsapp(numero, mensaje):
    try:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": numero.replace("+","").strip(),
            "type": "text",
            "text": {"body": mensaje}
        }
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        print("📤 WA ->", numero, r.status_code, r.text)
    except Exception as e:
        print("❌ Error enviando WhatsApp:", e)

def slack_post(texto):
    if not SLACK_BOT_TOKEN:
        # fallback a webhook si existe
        if SLACK_WEBHOOK_URL:
            try:
                requests.post(SLACK_WEBHOOK_URL, json={"text": texto}, timeout=15)
            except Exception as e:
                print("❌ Error webhook Slack:", e)
        else:
            print("ℹ️ Slack no configurado:", texto)
        return
    try:
        payload = {"channel": SLACK_CHANNEL, "text": texto}
        r = requests.post("https://slack.com/api/chat.postMessage",
                          headers=SLACK_HEADERS, json=payload, timeout=15)
        print("📤 Slack ->", r.status_code, r.text)
    except Exception as e:
        print("❌ Error chat.postMessage:", e)

# ====== salud ======
@app.route("/", methods=["GET", "HEAD"])
def home():
    # Para que Render tenga una respuesta 200 inmediata
    return "REKAR-BOT OK", 200

# ====== WhatsApp webhook ======
@app.route("/webhook", methods=["GET", "POST"])
def webhook_whatsapp():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            print("✅ Verificación Meta OK")
            return challenge, 200
        return "Token inválido", 403

    data = request.get_json(silent=True) or {}
    print("📩 WA recibido:", json.dumps(data, ensure_ascii=False))
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return "NO_MESSAGE", 200

        msg = entry["messages"][0]
        numero = msg["from"]
        texto = msg.get("text", {}).get("body", "").strip()
        nombre_meta = entry.get("contacts", [{}])[0].get("profile", {}).get("name")

        if numero not in clientes:
            clientes[numero] = nombre_meta if nombre_meta else None

        # si aún no tenemos nombre, pedirlo
        if clientes[numero] is None:
            if texto and texto.lower() not in ("hola","buenas","buenos dias","buenas tardes","buenas noches"):
                clientes[numero] = texto
                enviar_whatsapp(numero, f"✅ Gracias {texto}! Te registré. En breve te atiende un representante.")
                slack_post(f"✅ Cliente registrado: *{texto}* (+{numero})")
            else:
                enviar_whatsapp(numero, "👋 Hola! Soy el asistente de REKAR. ¿Podrías decirme tu *nombre* para registrarte?")
                slack_post(f"🟡 Cliente nuevo detectado (+{numero}), solicitando nombre.")
        else:
            slack_post(f"📱 *Mensaje de {clientes[numero]} (+{numero})*: {texto}")

    except Exception as e:
        print("⚠️ Error procesando WA:", e)

    return "EVENT_RECEIVED", 200

# ====== Slack events ======
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(silent=True) or {}
    print("📥 Slack evento:", json.dumps(data, ensure_ascii=False))
    # verificación
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    event = data.get("event") or {}
    subtype = event.get("subtype")
    user = event.get("user")
    text = (event.get("text") or "").strip()

    # ignorar mensajes del bot/app
    if subtype == "bot_message" or not user:
        return "IGNORE", 200

    # formato: +549XXXXXXXX mensaje
    if text.startswith("+549"):
        partes = text.split(" ", 1)
        if len(partes) == 2:
            numero, mensaje = partes
            enviar_whatsapp(numero, mensaje)
            slack_post(f"✅ Enviado a +{numero}: {mensaje}")
        else:
            slack_post("⚠️ Formato inválido. Usá: `+549XXXXXXXX mensaje`")
    else:
        slack_post("💬 Para responder al cliente, escribí: `+549XXXXXXXX mensaje`")

    return "OK", 200

# ====== errores ======
@app.errorhandler(Exception)
def handle_any(e):
    # no convertir 404/405 en 500
    if isinstance(e, HTTPException):
        return e
    print("🚨 Error interno:", e)
    return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 REKAR-BOT iniciado")
    app.run(host="0.0.0.0", port=PORT)
