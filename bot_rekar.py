# ============================================================
# 🤖 REKYBOT 1.5 – Conexión con Gemini + Google Sheets + Telegram
# ============================================================

import os, time, requests, json
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ============================================================
# 🔐 VARIABLES DE ENTORNO
# ============================================================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ============================================================
# ⚙️ CONFIGURACIÓN GOOGLE SHEETS
# ============================================================
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Rekar_Contactos").sheet1
except Exception as e:
    print(f"⚠️ No se pudo conectar a Google Sheets: {e}")
    sheet = None

# ============================================================
# 💬 FUNCIONES BÁSICAS
# ============================================================

def send_whatsapp_text(phone, text):
    """Envia un mensaje a WhatsApp"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code != 200:
            print(f"⚠️ Error enviando mensaje a {phone}: {r.text}")
    except Exception as e:
        print(f"⚠️ Error de conexión con WhatsApp: {e}")

def send_telegram_message(text):
    """Envia un mensaje al grupo de Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        requests.post(url, data=data)
    except Exception as e:
        print(f"⚠️ Error enviando mensaje a Telegram: {e}")

def save_contact_to_sheet(name, phone):
    """Guarda los contactos en Google Sheets"""
    if sheet:
        try:
            sheet.append_row([time.strftime("%Y-%m-%d %H:%M:%S"), name, phone])
        except Exception as e:
            print(f"⚠️ Error guardando contacto: {e}")

# ============================================================
# 🔮 GEMINI API
# ============================================================

def ask_gemini(prompt):
    """Consulta al modelo Gemini y devuelve una respuesta de texto"""

    if not GEMINI_API_KEY:
        return "🤖 En breve agregaremos más funciones inteligentes. Escribí M para volver al menú o S para salir."

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}

        r = requests.post(url, headers=headers, json=data)

        if r.status_code == 200:
            response = r.json()
            if "candidates" in response and response["candidates"]:
                text = response["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                return "🤖 No pude entender la consulta. Intentá con otra pregunta."

        else:
            print(f"⚠️ Error Gemini ({r.status_code}): {r.text}")
            send_telegram_message(f"⚠️ Gemini respondió con código {r.status_code}. Error: {r.text[:250]}")
            return f"⚠️ Hubo un problema al procesar tu consulta (código {r.status_code}). Escribí M para volver al menú o S para salir."

    except Exception as e:
        print(f"⚠️ Error de conexión con Gemini: {e}")
        send_telegram_message(f"⚠️ Gemini no respondió. Error: {e}")
        return "⚠️ Hubo un problema procesando tu consulta. Escribí M para volver al menú o S para salir."

# ============================================================
# 🧠 ESTADOS Y MENÚ
# ============================================================

sessions = {}

def clear_session(phone):
    if phone in sessions:
        del sessions[phone]

def get_main_menu():
    return (
        "¡Genial! 🌟 Elegí una opción:\n\n"
        "1️⃣ Enviar tu CV (rekar.salud@gmail.com)\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante\n"
        "7️⃣ Seguir chateando con RekyBot (modo asistente IA)\n"
        "8️⃣ Salir ❌\n\n"
        "Si querés volver al *menú*, escribí M.\nPara *salir*, escribí S."
    )

def get_greeting():
    return (
        "👋 ¡Hola! Soy *RekyBot*, asistente virtual de *REKAR*.\n"
        "Atendemos de lunes a sábado de 9 a 19 hs.\n\n"
        "¿Cómo es tu nombre?"
    )

# ============================================================
# 🌐 WEBHOOK META
# ============================================================

@app.route('/webhook', methods=['GET'])
def verify_token():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Token inválido", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print(json.dumps(data, indent=2))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            phone = message["from"]
            text = message.get("text", {}).get("body", "").strip()

            if phone not in sessions:
                sessions[phone] = {"state": "start"}
                send_whatsapp_text(phone, get_greeting())
                return jsonify({"ok": True}), 200

            state = sessions[phone]["state"]

            # Primer mensaje: guarda nombre y muestra menú
            if state == "start":
                sessions[phone]["name"] = text
                save_contact_to_sheet(text, phone)
                send_whatsapp_text(phone, get_main_menu())
                sessions[phone]["state"] = "menu"
                return jsonify({"ok": True}), 200

            # MENÚ PRINCIPAL
            if text.lower() in ["m", "menú", "menu"]:
                send_whatsapp_text(phone, get_main_menu())
                sessions[phone]["state"] = "menu"
                return jsonify({"ok": True}), 200

            # SALIDA
            if text.lower() in ["s", "salir", "8"]:
                clear_session(phone)
                send_whatsapp_text(phone, "👋 ¡Gracias por comunicarte con REKAR! Que tengas un excelente día.")
                return jsonify({"ok": True}), 200

            # OPCIONES DEL MENÚ
            if state == "menu":
                if text == "1":
                    send_whatsapp_text(phone, "📩 Podés enviar tu CV a: rekar.salud@gmail.com")
                elif text == "2":
                    send_whatsapp_text(phone, "🧾 Requisitos: título habilitante, matrícula, monotributo activo, y disponibilidad para trabajo domiciliario.")
                elif text == "3":
                    send_whatsapp_text(phone, "🌐 Visitá nuestra web: https://rekarsalud.blogspot.com/")
                elif text == "4":
                    send_whatsapp_text(phone, "📋 Completá el formulario de base de datos: [agregar enlace de Google Form]")
                elif text == "5":
                    send_whatsapp_text(phone, "🏥 REKAR brinda servicios domiciliarios de kinesiología y enfermería en CABA y GBA.")
                elif text == "6":
                    send_whatsapp_text(phone, "👨‍⚕️ Un representante fue notificado. Te contactará a la brevedad.")
                    send_telegram_message(f"📞 Nuevo cliente solicita representante: {sessions[phone]['name']} ({phone})")
                elif text == "7":
                    send_whatsapp_text(phone, "💬 Ahora estás chateando con RekyBot Asistente. Podés hacerme preguntas sobre nuestros servicios.")
                    sessions[phone]["state"] = "assistant"
                else:
                    send_whatsapp_text(phone, "❌ Opción no válida. Escribí M para volver al menú o S para salir.")
                return jsonify({"ok": True}), 200

            # MODO ASISTENTE IA (GEMINI)
            if state == "assistant":
                answer = ask_gemini(text)
                send_whatsapp_text(phone, answer)
                return jsonify({"ok": True}), 200

    except Exception as e:
        print(f"⚠️ Error general webhook: {e}")
        send_telegram_message(f"⚠️ Error en webhook: {e}")

    return jsonify({"ok": True}), 200

# ============================================================
# 🚀 EJECUCIÓN DEL SERVIDOR
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
