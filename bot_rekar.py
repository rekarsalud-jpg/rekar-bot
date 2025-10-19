from flask import Flask, request, jsonify
import requests, os, json

app = Flask(__name__)

VERIFY_TOKEN   = os.getenv("VERIFY_TOKEN", "rekar_verificacion")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID= os.getenv("PHONE_NUMBER_ID")

GRAPH_URL = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

def send_message(to, text):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    r = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print(f"📤 Meta API -> {r.status_code} {r.text}")
    return r.status_code, r.text

@app.route("/", methods=["GET"])
def home():
    return "✅ RekarBot vivo", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    ok = (mode == "subscribe" and token == VERIFY_TOKEN)
    print(f"🔎 VERIFY: mode={mode} token_ok={ok}")
    return (challenge, 200) if ok else ("Error", 403)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    print("📩 RAW PAYLOAD:", json.dumps(data, ensure_ascii=False))

    try:
        # WhatsApp empaqueta así: entry -> changes -> value
        entries = data.get("entry", [])
        for e in entries:
            for c in e.get("changes", []):
                value = c.get("value", {})

                # 1) Si hay 'messages', es un mensaje entrante del usuario
                msgs = value.get("messages", [])
                if msgs:
                    for m in msgs:
                        from_number = m.get("from")
                        msg_type = m.get("type")
                        print(f"✅ INCOMING: from={from_number} type={msg_type}")

                        # Respondemos SIEMPRE “Hola 👋”, sin importar el tipo
                        if from_number:
                            send_message(from_number, "👋 Hola, soy Rekar Bot. ¡Te leo!")
                        else:
                            print("⚠ No llegó 'from' en el mensaje")

                # 2) Si no hay 'messages' pero hay 'statuses', es un acuse/estado
                elif value.get("statuses"):
                    print("ℹ Llego 'statuses' (entregas/lecturas), no se responde.")

                else:
                    print("ℹ value sin 'messages' ni 'statuses'. Nada para responder.")

    except Exception as ex:
        print(f"💥 EXCEPCIÓN en handler: {ex}")

    return jsonify(ok=True), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
