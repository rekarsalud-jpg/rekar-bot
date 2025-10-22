# ==========================================
# 🤖 REKYBOT 1.5.1 – versión estable (Render + Gemini + Sheets)
# ==========================================

import os, time, requests, json
from flask import Flask, request, jsonify

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_URL = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta")

# === VARIABLES INTERNAS ===
active_sessions = {}
last_messages = {}
HUMAN_TTL = 3600  # 60 minutos

# ==============================================
# FUNCIONES BASE
# ==============================================

def send_whatsapp_text(phone, text):
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
            last_messages[phone] = text
            print(f"✅ Enviado a WhatsApp {phone}")
        else:
            print(f"❌ Error enviando mensaje: {r.text}")
    except Exception as e:
        print(f"⚠️ Error conexión WhatsApp: {e}")

def send_telegram_message(text):
    """Envía mensaje al canal de Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, json=data)
        print(f"📤 Enviado a Telegram: {text}")
    except Exception as e:
        print(f"⚠️ Error Telegram: {e}")

# ==============================================
# GEMINI IA
# ==============================================

def ask_gemini(prompt):
    """Consulta a Gemini con fallback"""
    if not GEMINI_API_KEY:
        return "🤖 En breve agregaremos más funciones inteligentes. Escribí M para volver al menú o S para salir."

    try:
        url = f"{GEMINI_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return content
        else:
            print(f"⚠️ Error Gemini: {r.text}")
            return "⚠️ Hubo un problema procesando tu consulta. Escribí M para volver al menú o S para salir."
    except Exception as e:
        print(f"⚠️ Error Gemini conexión: {e}")
        return "⚠️ Hubo un problema procesando tu consulta. Escribí M para volver al menú o S para salir."

# ==============================================
# UTILIDADES DE SESIÓN
# ==============================================

def clear_session(phone):
    active_sessions.pop(phone, None)
    last_messages.pop(phone, None)
    print(f"🧹 Sesión cerrada para {phone}")

def return_to_menu(phone):
    info = active_sessions.get(phone, {})
    name = info.get("name", "Cliente")
    send_whatsapp_text(phone, get_main_menu(name))
    info["state"] = "menu"
    active_sessions[phone] = info

# ==============================================
# MENÚS Y TEXTOS
# ==============================================

def get_main_menu(name):
    return (
        f"¡Genial, {name}! 🌟\n"
        "Elegí una opción:\n\n"
        "1️⃣ Enviar tu CV\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante\n"
        "7️⃣ Seguir chateando con RekyBot (modo asistente IA)\n"
        "8️⃣ Salir ❌\n\n"
        "Si querés volver al *menú*, escribí M.\nPara *salir*, S."
    )

def get_greeting():
    return (
        "👋 ¡Hola! Soy 🤖 *RekyBot 1.5.1*, asistente virtual de *REKAR*. 😊\n"
        "¡Gracias por escribirnos! Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
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

        info = active_sessions.get(phone, {"state": "start", "time": time.time()})

        # Salida manual
        if text.lower() in ["s", "salir"]:
            send_whatsapp_text(phone, "👋 ¡Gracias por contactarte con REKAR! Cuando necesites, escribinos de nuevo.")
            clear_session(phone)
            return jsonify({"ok": True}), 200

        # Volver al menú
        if text.lower() in ["m", "menu"]:
            return_to_menu(phone)
            return jsonify({"ok": True}), 200

        # === ESTADOS ===
        if info["state"] == "start":
            send_whatsapp_text(phone, get_greeting())
            info["state"] = "awaiting_name"

        elif info["state"] == "awaiting_name":
            name = text.split(" ")[0].capitalize()
            info["name"] = name
            send_whatsapp_text(phone, get_main_menu(name))
            info["state"] = "menu"

        elif info["state"] == "menu":
            if text == "1":
                send_whatsapp_text(phone, "📧 Podés enviar tu CV a rekar.salud@gmail.com incluyendo tus datos y disponibilidad.")
            elif text == "2":
                send_whatsapp_text(phone, "🩺 Requisitos: matrícula, monotributo, disponibilidad y compromiso profesional.")
            elif text == "3":
                send_whatsapp_text(phone, "🌐 Visitá nuestra web: https://rekarsalud.blogspot.com/?m=1")
            elif text == "4":
                send_whatsapp_text(phone, "🗂️ Completá el formulario: [agregar enlace de Google Form]")
            elif text == "5":
                send_whatsapp_text(phone, "🏥 REKAR brinda servicios domiciliarios de kinesiología y enfermería en CABA y GBA.")
            elif text == "6":
                send_whatsapp_text(phone, "🧑‍💼 Un representante fue notificado. Te contactará a la brevedad.")
                send_telegram_message(f"📞 Nuevo cliente quiere hablar con un representante:\n{info.get('name')} (+{phone})")
                info["state"] = "human_active"
                info["time"] = time.time()
            elif text == "7":
                send_whatsapp_text(phone, "💬 Ahora estás chateando con RekyBot Asistente. Podés hacerme preguntas sobre nuestros servicios.")
                info["state"] = "assistant_mode"
            elif text == "8":
                send_whatsapp_text(phone, "👋 ¡Gracias por contactarte con REKAR! Que tengas un excelente día.")
                clear_session(phone)
            else:
                send_whatsapp_text(phone, "No entendí tu respuesta. Escribí el número de la opción o M para menú.")

        elif info["state"] == "human_active":
            # Solo reenvía a Telegram, sin responder
            send_telegram_message(f"💬 {info.get('name', 'Cliente')} (+{phone}): {text}")

        elif info["state"] == "assistant_mode":
            reply = ask_gemini(text)
            send_whatsapp_text(phone, reply)

        active_sessions[phone] = info
        return jsonify({"ok": True}), 200

    except Exception as e:
        print("⚠️ Error webhook:", e)
        return jsonify({"error": str(e)}), 200

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

    if chat_id != str(TELEGRAM_CHAT_ID):
        return jsonify({"ok": True}), 200

    # Responder directamente desde Telegram (reply)
    if "reply_to_message" in msg and msg["reply_to_message"]:
        phone = msg["reply_to_message"]["text"].split("(")[-1].split(")")[0]
        send_whatsapp_text(phone, text)
        return jsonify({"ok": True}), 200

    if text.startswith("/cerrar"):
        try:
            _, phone = text.split(" ", 1)
            clear_session(phone)
            send_telegram_message(f"✅ Sesión cerrada para {phone}")
            send_whatsapp_text(phone, "🔚 La conversación fue cerrada. Gracias por comunicarte con REKAR.")
        except:
            send_telegram_message("❌ Usa: /cerrar <número>")
    return jsonify({"ok": True}), 200

# ==============================================
# EJECUCIÓN SERVIDOR
# ==============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
