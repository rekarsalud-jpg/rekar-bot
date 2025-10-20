from flask import Flask, request, jsonify
import requests, os, json
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
SLACK_CHANNEL = "#todo-rekar-mensajeria-wtz"

SLACK_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
}

clientes = {}

def enviar_whatsapp(numero, mensaje):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": numero.replace("+",""),
        "type": "text",
        "text": {"body": mensaje}
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)
        print("📤 WA ->", numero, r.status_code, r.text)
    except Exception as e:
        print("❌ Error enviando WA:", e)

def slack_post(msg):
    try:
        r = requests.post("https://slack.com/api/chat.postMessage",
                          headers=SLACK_HEADERS,
                          json={"channel": SLACK_CHANNEL, "text": msg},
                          timeout=15)
        print("📤 Slack ->", r.status_code, r.text)
    except Exception as e:
        print("❌ Error Slack:", e)

@app.route("/", methods=["GET"])
def home():
    return "REKAR BOT OK", 200

@app.route("/webhook", methods=["GET","POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Token inválido", 403

    data = request.get_json(silent=True) or {}
    print("📩 WA recibido:", json.dumps(data, ensure_ascii=False))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return "no messages", 200

        msg = entry["messages"][0]
        numero = msg["from"]
        texto = msg.get("text", {}).get("body", "")
        slack_post(f"📱 Nuevo mensaje de {numero}: {texto}")
    except Exception as e:
        print("❌ Error procesando WA:", e)

    return "ok", 200

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(silent=True) or {}
    print("📥 Slack evento:", json.dumps(data, ensure_ascii=False))

    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    event = data.get("event", {})
    text = (event.get("text") or "").strip()
    user = event.get("user")

    if not text or not user:
        return "ignore", 200

    if text.startswith("+549"):
        partes = text.split(" ", 1)
        if len(partes) == 2:
            numero, mensaje = partes
            print("➡️ Slack envía a WA:", numero, mensaje)
            enviar_whatsapp(numero, mensaje)
        else:
            slack_post("⚠️ Formato incorrecto: usa `+54911xxxx mensaje`")
    else:
        slack_post("💬 Para responder: `+54911xxxx mensaje`")

    return "ok", 200

@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return e
    print("🚨 Error global:", e)
    return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 BOT INICIADO")
    app.run(host="0.0.0.0", port=PORT)
