# ==========================================
# 🤖 REKYBOT 1.5 – versión con Gemini y Google Sheets
# ==========================================

import os, time, requests, json
from flask import Flask, request, jsonify

# Librería para Google Sheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Gemini (opcional)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

# Google Sheets
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON")  # JSON del Service Account
SHEET_NAME = os.getenv("SHEET_NAME", "Contactos Rekar")

# === VARIABLES INTERNAS ===
active_sessions = {}
active_conversations = {}
last_messages = {}
HUMAN_TTL = 3600  # 60 minutos

# ==============================================
# FUNCIONES BASE
# ==============================================

def send_whatsapp_text(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200:
            last_messages[phone] = text
            print(f"✅ Enviado a WhatsApp {phone}")
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


# ==============================================
# GOOGLE SHEETS
# ==============================================

def save_contact_to_sheet(name, phone):
    """Guarda el contacto en Google Sheets"""
    try:
        if not GOOGLE_SHEETS_JSON:
            print("⚠️ No hay credenciales de Sheets configuradas.")
            return
        creds_json = json.loads(GOOGLE_SHEETS_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1

        existing = sheet.get_all_records()
        for row in existing:
            if row.get("Teléfono") == phone:
                print(f"ℹ️ {phone} ya está registrado.")
                return

        sheet.append_row([name, phone, time.strftime("%Y-%m-%d %H:%M:%S")])
        print(f"💾 Guardado en Google Sheets: {name} ({phone})")
    except Exception as e:
        print(f"❌ Error guardando en Sheets: {e}")


# ==============================================
# GEMINI – modo asistente
# ==============================================

def ask_gemini(prompt):
    """Consulta al modelo Gemini (si está configurado)"""
    if not GEMINI_API_KEY:
        return "🤖 Gracias por tu consulta. En breve agregaremos más funciones inteligentes. Escribí M para volver al menú o S para salir."

    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"⚠️ Error con Gemini: {e}")
        return "🤖 Hubo un problema procesando tu consulta. Escribí M para volver al menú o S para salir."


# ==============================================
# FUNCIONES DE CONTROL DE SESIÓN
# ==============================================

def clear_session(phone):
    active_sessions.pop(phone, None)
    active_conversations.pop(phone, None)
    last_messages.pop(phone, None)
    print(f"🧹 Sesión cerrada para {phone}")


def is_duplicate(phone, text):
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
        "👋 ¡Hola! Soy 🤖 *RekyBot 1.5*, asistente virtual de *REKAR*. 😊\n"
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

        if is_duplicate(phone, text):
            return jsonify({"ok": True}), 200

        info = active_sessions.get(phone, {"state": "start", "time": time.time()})

        if text.lower() in ["s", "salir"]:
            send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
            clear_session(phone)
            return jsonify({"ok": True}), 200

        if info["state"] == "start":
            send_whatsapp_text(phone, get_greeting())
            info["state"] = "awaiting_name"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        elif info["state"] == "awaiting_name":
            name = text.split(" ")[0].capitalize()
            info["name"] = name
            save_contact_to_sheet(name, phone)
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
                send_whatsapp_text(phone, "🌐 Visitá nuestra web: https://rekarsalud.blogspot.com/?m=1")
            elif choice == "4":
                send_whatsapp_text(phone, "🗂️ Completá el formulario: [agregar enlace Google Form]")
            elif choice == "5":
                send_whatsapp_text(phone, "🏥 REKAR brinda servicios domiciliarios de kinesiología y enfermería en CABA y GBA.")
            elif choice == "6":
                send_whatsapp_text(phone, "🧑‍💼 Un representante fue notificado. Te contactará a la brevedad.")
                send_telegram_message(f"📞 Nuevo cliente quiere hablar con un representante:\n{info.get('name','Cliente')} (+{phone})")
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

        elif info["state"] == "assistant_mode":
            reply = ask_gemini(text)
            send_whatsapp_text(phone, reply)
            return jsonify({"ok": True}), 200

    except Exception as e:
        print("⚠️ Error webhook:", e)
        return jsonify({"error": str(e)}), 200

    return jsonify({"ok": True}), 200


# ==============================================
# WEBHOOK TELEGRAM (modo reply)
# ==============================================

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": True}), 200

    msg = data["message"]
    text = msg.get("text", "").strip()
    reply = msg.get("reply_to_message")

    # Si se usa "Responder" en Telegram
    if reply and "+" in reply.get("text", ""):
        phone = reply["text"].split("+")[-1].split(")")[0].strip()
        send_whatsapp_text(phone, text)
        return jsonify({"ok": True}), 200

    if text.startswith("/enviar"):
        try:
            _, phone, message = text.split(" ", 2)
            send_whatsapp_text(phone, message)
        except:
            send_telegram_message("❌ Formato inválido. Usa: /enviar <número> <mensaje>")

    if text.startswith("/cerrar"):
        try:
            _, phone = text.split(" ", 1)
            clear_session(phone)
            send_telegram_message(f"✅ Sesión cerrada para {phone}")
        except:
            send_telegram_message("❌ Usa /cerrar <número> correctamente.")
    return jsonify({"ok": True}), 200


# ==============================================
# EJECUCIÓN SERVIDOR
# ==============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
