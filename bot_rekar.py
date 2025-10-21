# ==========================================
# 🤖 REKYBOT 1.3.6 – versión estable (Render)
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

# === VARIABLES INTERNAS ===
active_sessions = {}
active_conversations = {}
last_messages = {}
HUMAN_TTL = 3600  # 60 minutos en segundos

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
            print(f"✅ Enviado a WhatsApp {phone}")
            last_messages[phone] = text
            return True
        else:
            print(f"❌ Error enviando mensaje: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ Error conexión WhatsApp: {e}")
        return False


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
# FUNCIONES DE CONTROL DE SESIÓN
# ==============================================

def clear_session(phone):
    """Elimina toda la sesión de un cliente"""
    active_sessions.pop(phone, None)
    active_conversations.pop(phone, None)
    last_messages.pop(phone, None)
    print(f"🧹 Sesión cerrada para {phone}")


def is_duplicate(phone, text):
    """Evita loops por reintento de WhatsApp"""
    last_text = last_messages.get(phone)
    if last_text and last_text.strip() == text.strip():
        print(f"⚠️ Duplicado detectado para {phone}, ignorado.")
        return True
    return False


# ==============================================
# FLUJOS PRINCIPALES
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
        "👋 ¡Hola! Soy 🤖 *RekyBot 1.3.6*, asistente virtual de *REKAR*. 😊\n"
        "¡Gracias por escribirnos! Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
        "¿Cómo es tu nombre?"
    )


# ==============================================
# WEBHOOK WHATSAPP
# ==============================================

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Validación del token
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = msg["from"]
        text = msg["text"]["body"].strip()

        # Evita eco / duplicados
        if is_duplicate(phone, text):
            return jsonify({"ok": True}), 200

        info = active_sessions.get(phone, {"state": "start", "time": time.time()})

        # Si cliente sale
        if text.lower() in ["s", "salir"]:
            send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
            clear_session(phone)
            return jsonify({"ok": True}), 200

        # === ESTADOS ===

        # Estado inicial
        if info["state"] == "start":
            send_whatsapp_text(phone, get_greeting())
            info["state"] = "awaiting_name"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        # Espera nombre
        elif info["state"] == "awaiting_name":
            name = text.split(" ")[0].capitalize()
            info["name"] = name
            send_whatsapp_text(phone, get_main_menu(name))
            info["state"] = "menu"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        # Menú principal
        elif info["state"] == "menu":
            choice = text.lower()

            if choice == "1":
                send_whatsapp_text(phone, "📧 Enviá tu CV a: rekar.salud@gmail.com\nGracias por postularte. 🙌")
            elif choice == "2":
                send_whatsapp_text(phone, "✅ Requisitos: Título habilitante, matrícula vigente y disponibilidad horaria.")
            elif choice == "3":
                send_whatsapp_text(phone, "🌐 Visitá nuestra web: www.rekar.com.ar")
            elif choice == "4":
                send_whatsapp_text(phone, "🗂️ Completá el formulario: https://forms.gle/rekar-form")
            elif choice == "5":
                send_whatsapp_text(phone, "🏥 REKAR brinda servicios domiciliarios de kinesiología y enfermería en CABA y GBA.")
            elif choice == "6":
                send_whatsapp_text(phone, "🧑‍💼 Un representante fue notificado. Te contactará a la brevedad.")
                send_telegram_message(f"📞 Nuevo cliente quiere hablar con un representante:\n{name} (+{phone})")
                info["state"] = "human_mode"
                info["time"] = time.time()
            elif choice == "7":
                send_whatsapp_text(phone, "💬 Ahora estás chateando con *RekyBot Asistente*. Podés hacerme preguntas sobre nuestros servicios.")
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

        # Modo humano
        elif info["state"] == "human_mode":
            elapsed = time.time() - info.get("time", 0)
            if elapsed < HUMAN_TTL:
                send_telegram_message(f"💬 {info.get('name', 'Cliente')} (+{phone}): {text}")
                send_whatsapp_text(phone, "🕐 Gracias por tu mensaje. Nuestro representante ya fue notificado y te responderá pronto.")
            else:
                send_whatsapp_text(phone, "⏳ Tu conversación anterior finalizó. Si querés hablar con alguien, elegí la opción 6 del menú.")
                info["state"] = "menu"
                send_whatsapp_text(phone, get_main_menu(info.get("name", "Cliente")))
            return jsonify({"ok": True}), 200

        # Modo asistente
        elif info["state"] == "assistant_mode":
            send_whatsapp_text(phone, "🤖 Gracias por tu consulta. En breve agregaremos más funciones inteligentes. Escribí M para volver al menú o S para salir.")
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

    if chat_id != str(TELEGRAM_CHAT_ID):
        return jsonify({"ok": True}), 200

    if text.startswith("/cerrar"):
        parts = text.split(" ", 1)
        if len(parts) == 2:
            phone = parts[1].strip()
            clear_session(phone)
            send_telegram_message(f"✅ Sesión cerrada para {phone}")
    elif text.startswith("/enviar"):
        try:
            _, phone, message = text.split(" ", 2)
            send_whatsapp_text(phone, message)
        except:
            send_telegram_message("❌ Formato inválido. Usa: /enviar <número> <mensaje>")
    return jsonify({"ok": True}), 200


# ==============================================
# EJECUCIÓN SERVIDOR
# ==============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
