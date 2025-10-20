import os
import time
import re
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ====== Entorno ======
ACCESS_TOKEN       = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID    = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN       = os.getenv("VERIFY_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# memoria simple en RAM
last_contact = {}         # phone -> last timestamp we greeted
pending_name = set()      # phones esperando que nos digan el nombre

# ====== Utilidades ======
def send_whatsapp_message(phone, message):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    r = requests.post(url, headers=headers, json=data)
    print("📤 WA:", r.status_code, r.text)
    return r.status_code == 200

def send_telegram_message(text):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    print("📨 TG:", r.status_code, r.text)
    return r.status_code == 200

def need_new_greeting(phone, window_sec=1800):
    now = time.time()
    if phone not in last_contact or (now - last_contact[phone] > window_sec):
        last_contact[phone] = now
        return True
    return False

# Heurística simple para detectar nombres “probables”
NAME_BAD_WORDS = {
    "hola","buenas","buenos","dias","tardes","noches","gracias","consulta",
    "turno","precio","presupuesto","necesito","quiero","urgente","soy","me","llamo",
    "que","qué","q","como","cómo","estás","estas","ok","listo"
}

NAME_REGEX = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s'.-]{0,38}$")

def extract_name(text):
    """
    1) Si dice 'soy ...' o 'me llamo ...' => extraemos lo que sigue.
    2) Si está pendiente de nombre y el texto parece nombre, lo aceptamos.
    3) Si no, devolvemos None.
    """
    t = text.strip()
    tl = t.lower()

    # Caso “soy … / me llamo …”
    for key in ("me llamo", "soy"):
        if key in tl:
            name = t[tl.find(key) + len(key):].strip(" :,-.")
            return normalize_name(name) if is_probable_name(name) else None

    # Caso “solo el nombre”
    return normalize_name(t) if is_probable_name(t) else None

def is_probable_name(s):
    # Longitud razonable
    if not (2 <= len(s) <= 40):
        return False
    # Solo letras, espacios y signos de nombre comunes
    if not NAME_REGEX.match(s):
        return False
    # No contener palabras evidentes de no-nombre
    words = {w.strip(".,;:!?¡¿") for w in s.lower().split()}
    if words & NAME_BAD_WORDS:
        return False
    # Máximo 4 palabras (nombre/s y apellido/s)
    if len([w for w in words if w]) > 4:
        return False
    return True

def normalize_name(s):
    # Quita espacios múltiples y capitaliza cada palabra
    parts = [p for p in re.split(r"\s+", s.strip()) if p]
    return " ".join(p.capitalize() for p in parts)

# ====== Endpoints ======
@app.route('/webhook', methods=['GET'])
def verify_token():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📥 WA in:", data)
    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" in changes:
            msg   = changes["messages"][0]
            phone = msg["from"]
            text  = msg.get("text", {}).get("body", "").strip()

            # ¿Debemos saludar otra vez?
            if need_new_greeting(phone):
                saludo = (
                    "👋 ¡Hola! Soy *RekyBot 🤖* de *REKAR*, red de enfermería y kinesiología.\n"
                    "🕓 Horario de atención: *Lunes a Viernes de 8 a 18 hs*.\n\n"
                    "¿Podés decirme tu *nombre*, por favor?"
                )
                send_whatsapp_message(phone, saludo)
                send_telegram_message(f"📞 Nuevo contacto: {phone}\nMensaje: {text}")
                pending_name.add(phone)
                return jsonify({"status": "ok"}), 200

            # Si esperamos nombre, intentamos extraerlo
            if phone in pending_name:
                name = extract_name(text)
                if name:
                    send_whatsapp_message(
                        phone,
                        f"¡Gracias, *{name}*! Un operador humano de *REKAR* se pondrá en contacto a la brevedad.\n"
                        "Por favor, contanos tu consulta."
                    )
                    send_telegram_message(f"👤 Registrado: {name} ({phone})")
                    pending_name.discard(phone)
                else:
                    # No parece nombre, pedimos de nuevo pero sin cortar el flujo
                    send_whatsapp_message(phone, "¿Podés decirme tu *nombre*? (por ejemplo: *Juan Pérez*)")
                    send_telegram_message(f"ℹ️ {phone} envió: {text} (no parece nombre)")
                return jsonify({"status": "ok"}), 200

            # No esperábamos nombre: reenviamos a Telegram
            send_telegram_message(f"💬 {phone}: {text}")

    except Exception as e:
        print("❌ Error WA:", e)

    return jsonify({"status": "ok"}), 200

# Webhook (opcional) para enviar desde Telegram a WhatsApp con: +54911xxxx mensaje
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    print("📥 TG in:", data)
    try:
        message = data.get("message", {})
        text = message.get("text", "")
        if text and text.startswith("+"):
            # formato: +54911xxxxxxxx <mensaje>
            parts = text.split(" ", 1)
            if len(parts) == 2:
                phone, msg = parts
                ok = send_whatsapp_message(phone.replace("+", ""), msg)
                send_telegram_message(("✅" if ok else "⚠️") + f" Envío a {phone}: {'OK' if ok else 'error'}")
    except Exception as e:
        print("❌ Error TG:", e)

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    import sys
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
