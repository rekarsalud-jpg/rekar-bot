import os
import time
import requests
# import pandas as pd
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# === Variables de entorno ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SHEET_URL = os.getenv("SHEET_URL")

# === Variables internas ===
last_contact = {}
active_sessions = {}  # Para modo conversacional
csv_filename = "contactos_rekar.csv"

# === Funciones básicas ===

def send_whatsapp(phone, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    r = requests.post(url, headers=headers, json=data)
    print("📤 Enviado a WhatsApp:", r.status_code, r.text)
    return r.status_code == 200

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    r = requests.post(url, data=data)
    print("📨 Enviado a Telegram:", r.status_code, r.text)

def save_contact(phone, name=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[phone, name or "", now]], columns=["Teléfono", "Nombre", "Fecha"])
    try:
        if os.path.exists(csv_filename):
            df = pd.read_csv(csv_filename)
            df = df[df["Teléfono"] != phone]
            df = pd.concat([df, new_entry], ignore_index=True)
        else:
            df = new_entry
        df.to_csv(csv_filename, index=False)
        print("💾 Contacto guardado en CSV")
    except Exception as e:
        print("❌ Error al guardar CSV:", e)

# === Módulo conversacional híbrido ===
def rekybot_reply(text):
    text = text.lower()
    respuestas = {
        "servicio": "Ofrecemos servicios de kinesiología y enfermería domiciliaria, con profesionales matriculados y cobertura de distintas obras sociales.",
        "zona": "Actualmente trabajamos en zona sur y zona oeste del Gran Buenos Aires.",
        "trabajar": "Podés postularte enviando tu CV a rekar.salud@gmail.com o completando el formulario de ingreso. Requerimos matrícula nacional y provincial, monotributo activo y seguro de mala praxis.",
        "pago": "Los honorarios varían según la prestación y la obra social. Siempre buscamos ofrecer valores competitivos para nuestros profesionales.",
        "obra social": "Sí, trabajamos con distintas obras sociales y prepagas. Podés consultarme por alguna en particular.",
        "paciente": "Atendemos pacientes con patologías respiratorias, traumatológicas, neurológicas y postquirúrgicas. La atención es personalizada.",
        "hola": "¡Hola! Soy RekyBot 🤖, el asistente virtual de REKAR. ¿En qué puedo ayudarte hoy?",
        "gracias": "¡De nada! Si querés volver al menú principal, escribí 'salir' o 'menú'."
    }

    for key, val in respuestas.items():
        if key in text:
            return val

    return ("Soy RekyBot 🤖, tu asistente virtual de Rekar. "
            "Puedo ayudarte con información sobre nuestros servicios, zonas, requisitos para trabajar o atención a pacientes.")

# === Menú principal ===
def menu_principal():
    return (
        "👋 ¡Hola! Soy *RekyBot 🤖* de *REKAR*, red de enfermería y kinesiología.\n\n"
        "Por favor elegí una opción:\n"
        "1️⃣ Enviar tu CV por mail\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar el formulario de ingreso\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante humano\n"
        "7️⃣ Continuar hablando con RekyBot 🤖"
    )

# === Webhooks ===
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📥 Mensaje recibido:", data)

    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = msg["from"]
        text = msg["text"]["body"].strip().lower()

        # Modo conversacional activo
        if active_sessions.get(phone):
            if any(word in text for word in ["salir", "menu", "menú", "volver"]):
                active_sessions.pop(phone, None)
                send_whatsapp(phone, "Has salido del modo conversación. Volviendo al menú principal ⤴️")
                send_whatsapp(phone, menu_principal())
            else:
                reply = rekybot_reply(text)
                send_whatsapp(phone, reply)
            return jsonify({"status": "ok"}), 200

        # Nuevo contacto o reanudación
        if phone not in last_contact or (time.time() - last_contact.get(phone, 0)) > 1800:
            last_contact[phone] = time.time()
            send_whatsapp(phone, menu_principal())
            save_contact(phone)
            send_telegram(f"📞 Nuevo contacto desde WhatsApp: {phone}")
            return jsonify({"status": "ok"}), 200

        # Opciones del menú
        if text == "1":
            send_whatsapp(phone, "Podés enviar tu CV a 📧 rekar.salud@gmail.com")
        elif text == "2":
            send_whatsapp(phone, "Requisitos: Kinesiólogo o enfermero con matrícula nacional y provincial, monotributo activo y seguro de mala praxis.")
        elif text == "3":
            send_whatsapp(phone, "🌐 Web: [Agregá tu link aquí]")
        elif text == "4":
            send_whatsapp(phone, "📋 Formulario de ingreso: [Agregá tu link aquí]")
        elif text == "5":
            send_whatsapp(phone, "Somos una red de kinesiología y enfermería que conecta pacientes, profesionales y obras sociales. Operamos en zona sur y oeste del GBA.")
        elif text == "6":
            send_whatsapp(phone, "Un representante humano se pondrá en contacto contigo en breve. ¡Gracias por tu mensaje!")
            send_telegram(f"📩 Cliente quiere hablar con un representante: {phone}")
        elif text == "7":
            active_sessions[phone] = True
            send_whatsapp(phone, "Entraste al modo conversación con RekyBot 🤖. Podés hacerme preguntas sobre nuestros servicios, requisitos o zonas. Escribí 'salir' para volver al menú.")
        else:
            send_whatsapp(phone, "Por favor elegí una opción válida del menú principal.")
            send_whatsapp(phone, menu_principal())

    except Exception as e:
        print("❌ Error procesando mensaje:", e)

    return jsonify({"status": "ok"}), 200

# === Telegram webhook opcional (/enviar) ===
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    print("📥 Telegram:", data)

    if "message" in data:
        msg = data["message"]["text"]
        if msg.startswith("/enviar"):
            parts = msg.split(" ", 2)
            if len(parts) == 3:
                phone, text = parts[1], parts[2]
                send_whatsapp(phone, text)
                send_telegram(f"✅ Mensaje enviado a {phone}")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

