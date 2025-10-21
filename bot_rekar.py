# ==========================================
# 🤖 REKYBOT 1.4.1 – versión estable (Render)
# ==========================================

import os, time, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # opcional: activa IA si existe

# === VARIABLES INTERNAS ===
active_sessions = {}
last_messages = {}
HUMAN_TTL = 3600  # 60 minutos

# ==============================================
# FUNCIONES BASE
# ==============================================

def send_whatsapp_text(phone, text):
    """Envía mensaje a WhatsApp"""
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
            print(f"✅ Enviado a WhatsApp {phone}")
            last_messages[phone] = text
            return True
        else:
            print(f"❌ Error enviando mensaje: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ Error conexión WhatsApp: {e}")
        return False


def send_telegram_message(text, reply_to=None):
    """Envía mensaje al grupo de Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        requests.post(url, json=data)
        print(f"📤 Enviado a Telegram: {text}")
    except Exception as e:
        print(f"⚠️ Error Telegram: {e}")


def ask_gemini(prompt):
    """Consulta a Gemini 1.5 Flash (Google AI)"""
    if not GEMINI_API_KEY:
        return "🤖 Gracias por tu consulta. En breve agregaremos más funciones inteligentes."

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GEMINI_API_KEY}"
        }
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, headers=headers, json=data)

        if r.status_code == 200:
            response = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return response
        else:
            print("⚠️ Error Gemini:", r.text)
            return "⚠️ Hubo un problema consultando a la IA. Intentá más tarde."
    except Exception as e:
        print("⚠️ Error Gemini:", e)
        return "⚠️ Hubo un problema consultando a la IA. Intentá más tarde."

def save_contact(phone, name):
    """Guarda contacto (estructura base para Google Sheets)"""
    print(f"💾 Guardar contacto: {name} - {phone} ({time.ctime()})")
    # aquí luego agregaremos la conexión a Google Sheets


def clear_session(phone):
    active_sessions.pop(phone, None)
    last_messages.pop(phone, None)
    print(f"🧹 Sesión cerrada para {phone}")


def is_duplicate(phone, text):
    last_text = last_messages.get(phone)
    if last_text and last_text.strip() == text.strip():
        print(f"⚠️ Duplicado detectado para {phone}, ignorado.")
        return True
    return False


# ==============================================
# TEXTOS BASE
# ==============================================

def get_main_menu(name):
    return (
        f"¡Genial, {name}! 🌟\n"
        "Elegí una opción:\n\n"
        "1️⃣ Enviar tu CV (rekar.salud@gmail.com)\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante de REKAR\n"
        "7️⃣ Seguir chateando con RekyBot (modo asistente)\n"
        "8️⃣ Salir ❌\n\n"
        "Si querés volver al *menú*, escribí M.\nPara *salir*, S."
    )


def get_greeting():
    return (
        "👋 ¡Hola! Soy 🤖 *RekyBot 1.4.1*, asistente virtual de *REKAR*. 😊\n"
        "Gracias por escribirnos. Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
        "¿Cómo es tu nombre?"
    )


# ==============================================
# WEBHOOK WHATSAPP
# ==============================================

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = msg["from"]
        text = msg["text"]["body"].strip()

        if is_duplicate(phone, text):
            return jsonify({"ok": True}), 200

        info = active_sessions.get(phone, {"state": "start", "time": time.time()})

        if text.lower() in ["s", "salir"]:
            send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
            clear_session(phone)
            return jsonify({"ok": True}), 200

        # === ESTADOS ===
        if info["state"] == "start":
            send_whatsapp_text(phone, get_greeting())
            info["state"] = "awaiting_name"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        elif info["state"] == "awaiting_name":
            name = text.split(" ")[0].capitalize()
            info["name"] = name
            save_contact(phone, name)
            send_whatsapp_text(phone, get_main_menu(name))
            info["state"] = "menu"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        elif info["state"] == "menu":
            choice = text.lower()

            if choice == "1":
                send_whatsapp_text(phone, "📧 Enviá tu CV a: rekar.salud@gmail.com\nGracias por postularte. 🙌")
            elif choice == "2":
                send_whatsapp_text(phone, "✅ Requisitos: Título habilitante, matrícula vigente y disponibilidad horaria.")
            elif choice == "3":
                send_whatsapp_text(phone, "🌐 Visitá nuestra web: [link pendiente]")
            elif choice == "4":
                send_whatsapp_text(phone, "🗂️ Completá el formulario: [link pendiente]")
            elif choice == "5":
                send_whatsapp_text(phone, "🏥 REKAR brinda servicios domiciliarios de kinesiología y enfermería en CABA y GBA.")
            elif choice == "6":
                send_whatsapp_text(phone, "🧑‍💼 Un representante fue notificado. Te contactará a la brevedad.")
                send_telegram_message(f"📞 Nuevo cliente quiere hablar con un representante:\n{info['name']} (+{phone})")
                info["state"] = "human_mode"
                info["time"] = time.time()
            elif choice == "7":
                send_whatsapp_text(phone, "💬 Estás chateando con RekyBot Asistente. Podés hacerme preguntas sobre nuestros servicios.")
                info["state"] = "assistant_mode"
                info["time"] = time.time()
            elif choice == "8":
                send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Que tengas un excelente día.")
                clear_session(phone)
                return jsonify({"ok": True}), 200
            elif choice in ["m", "menu"]:
                send_whatsapp_text(phone, get_main_menu(info.get("name", "Cliente")))
            else:
                send_whatsapp_text(phone, "No entendí tu respuesta. Escribí el número de la opción o M para menú.")
            return jsonify({"ok": True}), 200

        elif info["state"] == "human_mode":
            elapsed = time.time() - info.get("time", 0)
            if elapsed < HUMAN_TTL:
                send_telegram_message(f"💬 {info.get('name', 'Cliente')} (+{phone}): {text}")
                send_whatsapp_text(phone, "🕐 Gracias por tu mensaje. Un representante ya fue notificado.")
            else:
                send_whatsapp_text(phone, "⏳ Tu conversación anterior finalizó. Escribí 6 para hablar con un representante.")
                info["state"] = "menu"
                send_whatsapp_text(phone, get_main_menu(info.get("name", "Cliente")))
            return jsonify({"ok": True}), 200

        elif info["state"] == "assistant_mode":
            reply = ask_gemini(f"El usuario escribió: {text}. Respondé como asistente amable de REKAR.")
            send_whatsapp_text(phone, reply)
            return jsonify({"ok": True}), 200

    except Exception as e:
        print("⚠️ Error webhook:", e)
        return jsonify({"error": str(e)}), 200

    return jsonify({"ok": True}), 200


# ==============================================
# WEBHOOK TELEGRAM
# ==============================================

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": True}), 200

    msg = data["message"]
    chat_id = str(msg["chat"]["id"])
    text = msg.get("text", "").strip()

    # Solo mensajes del grupo autorizado
    if chat_id != str(TELEGRAM_CHAT_ID):
        return jsonify({"ok": True}), 200

    # Si es respuesta a un mensaje del bot → identificar el número
    if "reply_to_message" in msg:
        original = msg["reply_to_message"]["text"]
        if "(+" in original and ")" in original:
            phone = original.split("(+")[1].split(")")[0]
            send_whatsapp_text(phone, text)
            send_telegram_message(f"✅ Enviado a {phone}", reply_to=msg["message_id"])
            return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200


# ==============================================
# EJECUCIÓN SERVIDOR
# ==============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

