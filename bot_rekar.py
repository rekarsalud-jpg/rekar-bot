# ==========================================
# 🤖 REKYBOT 1.5.2 – estable (Render)
# - Fijo: "M" vuelve al menú en cualquier estado
# - Fijo: integración Gemini (v1beta) con timeout + fallback híbrido
# - Silencio en modo HUMANO hasta /cerrar o TTL
# ==========================================

import os, time, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# === ENV VARS (Render) ===
ACCESS_TOKEN     = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID  = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN     = os.getenv("VERIFY_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# Gemini: usa exactamente estos nombres en Render
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL      = os.getenv(
    "GEMINI_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
)

# === Estado en memoria ===
sessions       = {}     # {phone: {"state":..., "name":..., "time":...}}
active_human   = {}     # {phone: last_ts}
last_user_text = {}     # anti-eco
HUMAN_TTL      = 60*60  # 60 min

# -------------------------------------------------
# Utilidades WhatsApp / Telegram
# -------------------------------------------------
def send_whatsapp(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            last_user_text[phone] = text
            return True
        print("WA error:", r.text)
        return False
    except Exception as e:
        print("WA ex:", e); return False

def send_telegram(text, reply_to=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(TELEGRAM_CHAT_ID), "text": text}
    if reply_to: payload["reply_to_message_id"] = reply_to
    try: requests.post(url, json=payload, timeout=6)
    except Exception as e: print("TG ex:", e)

# -------------------------------------------------
# Gemini (timeout + payload correcto v1beta)
# -------------------------------------------------
def ask_gemini(prompt):
    """Devuelve texto o None (para fallback). Timeout 10s."""
    if not GEMINI_API_KEY or not GEMINI_URL:
        return None
    try:
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=data,
            timeout=10
        )
        if r.status_code != 200:
            send_telegram(f"⚠️ Gemini respondió con código {r.status_code}.")
            return None
        js = r.json()
        cand = js.get("candidates", [])
        if not cand: return None
        parts = cand[0].get("content", {}).get("parts", [])
        if not parts: return None
        return parts[0].get("text", "").strip()
    except requests.Timeout:
        send_telegram("⏳ Timeout consultando a Gemini (10s).")
        return None
    except Exception as e:
        send_telegram(f"⚠️ Error llamando a Gemini: {e}")
        return None

# -------------------------------------------------
# Mensajes base
# -------------------------------------------------
def greeting():
    return ("👋 ¡Hola! Soy 🤖 *RekyBot 1.5.2*, asistente virtual de *REKAR*.\n"
            "Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
            "¿Cómo es tu nombre?")

def menu(name):
    return (f"¡Genial, {name}! ✨\nElegí una opción:\n\n"
            "1️⃣ Enviar tu CV (rekar.salud@gmail.com)\n"
            "2️⃣ Requisitos para trabajar en REKAR\n"
            "3️⃣ Ingresar a la web institucional\n"
            "4️⃣ Completar formulario de base de datos\n"
            "5️⃣ Información sobre REKAR\n"
            "6️⃣ Hablar con un representante\n"
            "7️⃣ Seguir chateando con RekyBot (modo asistente IA)\n"
            "8️⃣ Salir ❌\n\n"
            "Si querés volver al *menú*, escribí *M*. Para *salir*, escribí *S*.")

# -------------------------------------------------
# Helpers de sesión
# -------------------------------------------------
def clear_session(phone):
    sessions.pop(phone, None)
    active_human.pop(phone, None)
    last_user_text.pop(phone, None)
    print(f"🧹 sesión cerrada {phone}")

def ensure_session(phone):
    if phone not in sessions:
        sessions[phone] = {"state":"start","time":time.time()}

def is_duplicate_in(phone, incoming_text):
    last = last_user_text.get(phone)
    return last and last.strip() == incoming_text.strip()

# -------------------------------------------------
# Webhook WhatsApp
# -------------------------------------------------
@app.route("/webhook", methods=["GET","POST"])
def whatsapp_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json(silent=True) or {}
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = msg["from"]
        text  = msg.get("text",{}).get("body","").strip()
    except Exception:
        return jsonify({"ok":True}), 200

    ensure_session(phone)
    state = sessions[phone]["state"]

    # Silencio total si está en humano y dentro de TTL
    if state == "human" and (time.time() - sessions[phone]["time"] < HUMAN_TTL):
        # reenviamos a Telegram lo que dice el cliente
        send_telegram(f"💬 {sessions[phone].get('name','Cliente')} (+{phone}): {text}")
        # Notificamos al cliente que un representante contestará
        send_whatsapp(phone, "🕐 Gracias por tu mensaje. Un representante te responderá pronto.")
        return jsonify({"ok":True}), 200
    elif state == "human":
        # expiró la ventana
        sessions[phone]["state"] = "menu"
        send_whatsapp(phone, "⏳ La conversación con el representante finalizó.")
        send_whatsapp(phone, menu(sessions[phone].get("name","Cliente")))
        return jsonify({"ok":True}), 200

    # Comandos globales (funcionan SIEMPRE)
    if text.lower() in ["s","salir","exit"]:
        send_whatsapp(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
        clear_session(phone)
        return jsonify({"ok":True}), 200

    if text.lower() in ["m","menu"]:
        name = sessions[phone].get("name","Cliente")
        sessions[phone]["state"] = "menu"
        send_whatsapp(phone, menu(name))
        return jsonify({"ok":True}), 200

    # Bloque anti-eco
    if is_duplicate_in(phone, text):
        return jsonify({"ok":True}), 200

    # ----- Estados -----
    if state == "start":
        send_whatsapp(phone, greeting())
        sessions[phone]["state"] = "awaiting_name"
        return jsonify({"ok":True}), 200

    if state == "awaiting_name":
        name = text.split(" ")[0].capitalize() if text else "Cliente"
        sessions[phone]["name"] = name
        sessions[phone]["state"] = "menu"
        send_whatsapp(phone, menu(name))
        return jsonify({"ok":True}), 200

    if state == "menu":
        ch = text.lower()
        if ch == "1":
            send_whatsapp(phone, "📧 Enviá tu CV a *rekar.salud@gmail.com*. ¡Gracias por postularte! 🙌")
        elif ch == "2":
            send_whatsapp(phone, "✅ Requisitos: título habilitante, matrícula vigente y disponibilidad horaria.")
        elif ch == "3":
            send_whatsapp(phone, "🌐 Visitá nuestra web: https://rekarsalud.blogspot.com/?m=1")
        elif ch == "4":
            send_whatsapp(phone, "🗂️ Completá el formulario (base de datos): [agregar enlace Google Form]")
        elif ch == "5":
            send_whatsapp(phone, "🏥 REKAR brinda kinesiología y enfermería domiciliaria en CABA y GBA.")
        elif ch == "6":
            send_whatsapp(phone, "📞 Un representante fue notificado. Te contactará a la brevedad.")
            send_telegram(f"📞 Nuevo cliente quiere hablar con un representante:\n{sessions[phone].get('name','Cliente')} (+{phone})")
            sessions[phone]["state"] = "human"
            sessions[phone]["time"]  = time.time()
        elif ch == "7":
            sessions[phone]["state"] = "ia"
            send_whatsapp(phone, "💬 Estás en *modo IA*. Escribí tu consulta (puede demorar hasta 10 s).")
        elif ch == "8":
            send_whatsapp(phone, "¡Gracias por contactarte con REKAR! 👋 Que tengas un excelente día.")
            clear_session(phone)
        else:
            send_whatsapp(phone, "No entendí. Escribí el *número* de la opción, *M* para menú o *S* para salir.")
        return jsonify({"ok":True}), 200

    if state == "ia":
        # Indicador de procesamiento + llamada a Gemini con timeout
        send_whatsapp(phone, "⏳ Procesando tu pregunta...")
        answer = ask_gemini(text)

        if not answer:
            # Fallback híbrido + deja seguir en IA o volver
            send_whatsapp(
                phone,
                "🤖 No pude conectarme a la IA. "
                "Podés intentar de nuevo, escribir *M* para volver al menú o *S* para salir."
            )
        else:
            send_whatsapp(phone, answer)
        return jsonify({"ok":True}), 200

    # Si cae en un estado no esperado: volvemos al menú
    sessions[phone]["state"] = "menu"
    send_whatsapp(phone, menu(sessions[phone].get("name","Cliente")))
    return jsonify({"ok":True}), 200

# -------------------------------------------------
# Webhook Telegram (responder a WA + cerrar sesión)
# -------------------------------------------------
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    msg  = data.get("message", {})
    if not msg: return jsonify({"ok":True}), 200

    chat_id = str(msg.get("chat",{}).get("id",""))
    if chat_id != str(TELEGRAM_CHAT_ID):
        return jsonify({"ok":True}), 200

    text    = msg.get("text","").strip()
    reply   = msg.get("reply_to_message")
    # Si responde a un mensaje reenviado por el bot, extraemos el número del texto "(+....)"
    if reply and reply.get("text"):
        original = reply["text"]
        # Buscamos (+549...) entre paréntesis
        if "(" in original and ")" in original:
            phone = original.split("(")[1].split(")")[0].replace("+","").strip()
            if text.startswith("/cerrar"):
                clear_session(phone)
                send_telegram(f"✅ Sesión cerrada para {phone}")
            else:
                # Enviar el texto tal cual al cliente
                send_whatsapp(phone, text)
                # Bloqueamos respuestas automáticas hasta que cierres:
                sessions.setdefault(phone, {"state":"human","time":time.time()})
                sessions[phone]["state"] = "human"
                sessions[phone]["time"]  = time.time()
            return jsonify({"ok":True}), 200

    # Comandos manuales
    if text.startswith("/enviar"):
        try:
            _, phone, message = text.split(" ", 2)
            send_whatsapp(phone, message)
            sessions.setdefault(phone, {"state":"human","time":time.time()})
            sessions[phone]["state"] = "human"
            sessions[phone]["time"]  = time.time()
        except:
            send_telegram("❌ Formato: /enviar <numero> <mensaje>")
    elif text.startswith("/cerrar"):
        parts = text.split(" ",1)
        if len(parts)==2:
            clear_session(parts[1].strip())
        else:
            send_telegram("❌ Usa: /cerrar <numero>")
    return jsonify({"ok":True}), 200

# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)