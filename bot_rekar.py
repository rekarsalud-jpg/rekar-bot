import os
import csv
import time
from datetime import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Credenciales desde Render
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # ID del grupo donde están vos y Facu

# Archivo CSV para guardar los contactos
CSV_FILE = "contactos_rekar.csv"

# Control de últimas interacciones
last_contact = {}
contact_names = {}

# -------------------- Funciones principales --------------------

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
    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviado a WhatsApp:", response.status_code, response.text)
    return response.status_code == 200


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    response = requests.post(url, json=payload)
    print("📨 Enviado a Telegram:", response.status_code, response.text)


def save_contact(name, phone, message):
    """Guarda contacto en CSV"""
    fieldnames = ["FechaHora", "Nombre", "Telefono", "Mensaje"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "FechaHora": now,
            "Nombre": name,
            "Telefono": phone,
            "Mensaje": message
        })


def need_new_greeting(phone):
    """Evita que salude repetidamente"""
    now = time.time()
    if phone not in last_contact or now - last_contact[phone] > 1800:  # 30 min
        last_contact[phone] = now
        return True
    return False


# -------------------- Webhooks --------------------

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
    print("📥 Mensaje recibido:", data)

    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" in changes:
            msg = changes["messages"][0]
            phone = msg["from"]
            text = msg.get("text", {}).get("body", "").strip().lower()

            # Nuevo contacto o reactivación
            if need_new_greeting(phone):
                saludo = (
                    "👋 ¡Hola! Soy *RekyBot 🤖* de *REKAR*, Red de Enfermería y Kinesiología.\n\n"
                    "📅 *Horarios de atención:*\nLunes a Viernes de 8 a 18 hs.\n\n"
                    "¿Podrías decirme tu nombre, por favor?"
                )
                send_whatsapp_message(phone, saludo)
                send_telegram_message(f"📞 Nuevo contacto: {phone}")
                save_contact("Desconocido", phone, text)

            elif "soy" in text or "me llamo" in text or len(text.split()) <= 3:
                nombre = text.replace("soy", "").replace("me llamo", "").strip().title()
                contact_names[phone] = nombre
                save_contact(nombre, phone, text)

                menu = (
                    f"Gracias {nombre} 🙌\n\n"
                    "Seleccioná una opción:\n"
                    "1️⃣ Enviar tu CV a rekar.salud@gmail.com\n"
                    "2️⃣ Requisitos para trabajar en REKAR\n"
                    "3️⃣ Ingresar a nuestra web\n"
                    "4️⃣ Formulario para base de datos\n"
                    "5️⃣ Información sobre REKAR\n"
                    "6️⃣ Hablar con un representante humano"
                )
                send_whatsapp_message(phone, menu)

            elif text == "1":
                send_whatsapp_message(phone, "📧 Podés enviar tu CV a: rekar.salud@gmail.com")
            elif text == "2":
                send_whatsapp_message(phone,
                    "🩺 Requisitos:\n"
                    "- Kinesiólogo/a con matrícula provincial y nacional.\n"
                    "- Enfermero/a profesional o licenciado/a con matrícula provincial y nacional.\n"
                    "- Monotributista activo y seguro de mala praxis vigente.")
            elif text == "3":
                send_whatsapp_message(phone, "🌐 Podés visitar nuestra web: [agregar_link_aquí]")
            elif text == "4":
                send_whatsapp_message(phone, "📝 Accedé al formulario de base de datos: [agregar_link_aquí]")
            elif text == "5":
                send_whatsapp_message(phone,
                    "🏥 Somos *REKAR*, una red de enfermería y kinesiología.\n"
                    "Trabajamos principalmente en zona sur y oeste.\n"
                    "Conectamos pacientes con profesionales según la demanda de obras sociales.\n"
                    "Capacitamos y ofrecemos sueldos competitivos para fomentar una atención de calidad.")
            elif text == "6":
                send_whatsapp_message(phone, "👨‍⚕️ En unos minutos un representante humano se pondrá en contacto contigo.")
                send_telegram_message(f"👤 Cliente {contact_names.get(phone, phone)} pidió hablar con un representante.")
            else:
                send_whatsapp_message(phone, "🤖 No entendí tu mensaje. Por favor, elegí una opción del menú.")

    except Exception as e:
        print("❌ Error procesando mensaje:", e)

    return jsonify({"status": "ok"}), 200


@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    print("📨 Telegram mensaje:", data)
    if "message" in data and "text" in data["message"]:
        text = data["message"]["text"]
        if text.startswith("+549"):
            parts = text.split(" ", 1)
            if len(parts) == 2:
                phone, msg = parts
                send_whatsapp_message(phone.replace("+", ""), msg)
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
