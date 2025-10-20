import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================
# 🔐 TOKENS Y VARIABLES
# ==========================
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
BUSINESS_ID = os.getenv("BUSINESS_ID")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ==========================
# 🧠 VARIABLES DE ESTADO
# ==========================
user_states = {}

# ==========================
# 📩 FUNCIONES DE ENVÍO
# ==========================
def send_whatsapp_message(phone, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    requests.post(url, json=payload)

# ==========================
# 💬 MENÚ PRINCIPAL
# ==========================
def main_menu():
    return (
        "Seleccioná una opción:\n\n"
        "1️⃣ Enviar tu CV a rekar.salud@gmail.com\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a nuestra web\n"
        "4️⃣ Formulario para base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante humano"
    )

# ==========================
# 🤖 LÓGICA DEL BOT
# ==========================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "entry" in data:
        try:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            phone = message["from"]
            text = message["text"]["body"].strip().lower()

            # --- Registro nuevo contacto ---
            if phone not in user_states:
                user_states[phone] = "asking_name"
                send_whatsapp_message(phone, "👋 Hola! Soy *RekyBot*, asistente virtual de *REKAR Salud*.\n\nAtendemos de *lunes a sábado de 9 a 19 hs*.\n¿Cómo te llamás?")
                send_telegram_message(f"📞 Nuevo contacto: {phone}")
                return "ok", 200

            # --- Pide nombre ---
            if user_states[phone] == "asking_name":
                user_states[phone] = "menu"
                send_telegram_message(f"👤 Registrado: {text.title()} ({phone})")
                send_whatsapp_message(phone, f"Gracias {text.title()} 🙌\n\n{main_menu()}")
                return "ok", 200

            # --- En menú ---
            if user_states[phone] == "menu":
                if text in ["1", "1️⃣"]:
                    send_whatsapp_message(phone, "📧 Podés enviar tu CV a *rekar.salud@gmail.com*")
                elif text in ["2", "2️⃣"]:
                    send_whatsapp_message(phone, "📋 Requisitos:\n- Kinesiólogo/a o Lic. en Enfermería con matrícula provincial y nacional.\n- Monotributista activo.\n- Seguro de mala praxis vigente.")
                elif text in ["3", "3️⃣"]:
                    send_whatsapp_message(phone, "🌐 Podés ingresar a nuestra web aquí: LINK_AQUI_WEB")
                elif text in ["4", "4️⃣"]:
                    send_whatsapp_message(phone, "📝 Ingresá a nuestro formulario aquí: LINK_AQUI_FORMULARIO")
                elif text in ["5", "5️⃣"]:
                    send_whatsapp_message(phone,
                        "🏥 Somos *REKAR*, una red de enfermería y kinesiología domiciliaria.\n"
                        "Conectamos pacientes con profesionales calificados.\n"
                        "Trabajamos en Zona Sur y Oeste.\n"
                        "Capacitamos a los profesionales y ofrecemos sueldos competitivos para garantizar calidad en la atención."
                    )
                elif text in ["6", "6️⃣"]:
                    send_whatsapp_message(phone, "☎️ Gracias por comunicarte. Un representante humano te contactará pronto.")
                    send_telegram_message(f"📞 {phone} solicita hablar con un representante.")
                else:
                    send_whatsapp_message(phone, "⚠️ No entendí tu respuesta.\n\n" + main_menu())
                    return "ok", 200

                send_whatsapp_message(phone, "¿Querés volver al menú principal o salir?\nEscribí *menú* o *salir*.")
                user_states[phone] = "after_action"
                return "ok", 200

            # --- Después de acción ---
            if user_states[phone] == "after_action":
                if "menú" in text or "menu" in text:
                    send_whatsapp_message(phone, main_menu())
                    user_states[phone] = "menu"
                elif "salir" in text:
                    send_whatsapp_message(phone, "👋 ¡Gracias por comunicarte con *REKAR Salud*! Hasta pronto.")
                    del user_states[phone]
                else:
                    send_whatsapp_message(phone, "⚠️ No entendí. Escribí *menú* o *salir*.")
                return "ok", 200

        except Exception as e:
            print("Error:", e)
    return "ok", 200

# ==========================
# 🔄 RESPUESTA DESDE TELEGRAM
# ==========================
@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.get_json()
    if "message" in data:
        msg = data["message"]
        text = msg.get("text", "")
        if text.startswith("/responder"):
            try:
                parts = text.split(" ", 2)
                phone = parts[1]
                reply = parts[2]
                send_whatsapp_message(phone, reply)
                send_telegram_message(f"✅ Respuesta enviada a {phone}")
            except Exception:
                send_telegram_message("⚠️ Formato incorrecto. Usa:\n/responder NUMERO mensaje")
    return "ok", 200

# ==========================
# 🧾 VERIFICACIÓN WEBHOOK
# ==========================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verificación fallida", 403

# ==========================
# 🚀 INICIO
# ==========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
