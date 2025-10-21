import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate

app = Flask(__name__)

# ========= Variables de entorno =========
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") # WhatsApp
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # Telegram
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # ID del grupo/canal donde avisa

# Email (opcional para avisos y/o fallback de registro)
EMAIL_SENDER = os.getenv("EMAIL_SENDER") # ej: rekar.salud@gmail.com
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # App Password (16 caracteres)
EMAIL_DESTINATION = os.getenv("EMAIL_DESTINATION", EMAIL_SENDER) # si no hay destino, usa remitente
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# Registro en Google Sheets (opcional). Si no lo definís, cae a email.
# Configurá en SHEET_WEBHOOK_URL una “Web App” de Apps Script que agregue filas.
SHEET_WEBHOOK_URL = os.getenv("SHEET_WEBHOOK_URL", "").strip()

# ========= Estado en memoria =========
last_contact = {} # phone -> ts último saludo para “cooldown”
active_conversations = {} # phone -> {"mode": "menu"|"humano"|"asistente"|"silencio", "until": ts, "name": str}

# ========= Utilidades =========
def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def within(sec: int, ts: float) -> bool:
    return (time.time() - ts) < sec

# ========= Envíos =========
def send_whatsapp_message(phone: str, text: str) -> bool:
    """Envía texto por WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
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
    r = requests.post(url, headers=headers, json=data)
    print("📤 WA ->", r.status_code, r.text)
    return r.status_code == 200

def send_telegram_message(text: str):
    """Envía mensaje al grupo/canal de Telegram (si está configurado)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram no configurado.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    r = requests.post(url, json=payload)
    print("📨 TG ->", r.status_code, r.text)

def send_email(subject: str, body: str):
    """Envío SMTP (opcional)."""
    if not (EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_DESTINATION):
        print("ℹ️ Email no configurado; omitido.")
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_DESTINATION
        msg["Date"] = formatdate(localtime=True)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls()
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.send_message(msg)
        print("📧 Email OK")
    except Exception as e:
        print("❌ Email error:", e)

def append_to_sheet(name: str, phone: str, source: str = "WhatsApp"):
    """Registra contacto en Google Sheets vía webhook Apps Script (opcional)."""
    if not SHEET_WEBHOOK_URL:
        # Fallback: avisa por email para dejar rastro
        send_email(
            "Registro de contacto (fallback)",
            f"{now_iso()} | {source}\nNombre: {name or '-'}\nTel: {phone}"
        )
        return

    try:
        payload = {
            "timestamp": now_iso(),
            "name": name or "",
            "phone": phone,
            "source": source
        }
        r = requests.post(SHEET_WEBHOOK_URL, json=payload, timeout=10)
        print("🧾 Sheet webhook ->", r.status_code, r.text)
    except Exception as e:
        print("❌ Sheet webhook error:", e)

# ========= Plantillas =========
def saludo_inicial() -> str:
    return (
        "¡Hola! Soy *RekyBot 🤖* de *REKAR*, red de enfermería y kinesiología.\n"
        "Atendemos *lunes a sábado de 9 a 19 hs*.\n\n"
        "¿Cómo te llamás?"
    )

def menu_principal(nombre: str = "") -> str:
    pref = f"Gracias {nombre} 🙌\n" if nombre else ""
    return (
        f"{pref}Seleccioná una opción:\n"
        "1️⃣ Enviar tu CV a rekar.salud@gmail.com\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a nuestra web\n"
        "4️⃣ Formulario para base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante humano\n"
        "7️⃣ Seguir chateando con *RekyBot* (IA)\n"
    )

def post_accion() -> str:
    return "¿Querés *volver al menú* o *salir*?"

# ========= Lógica auxiliar =========
def need_new_greeting(phone: str) -> bool:
    """Saluda si es primer contacto o pasaron 30 min desde la última vez."""
    now = time.time()
    last = last_contact.get(phone, 0)
    if (now - last) > 1800: # 30 minutos
        last_contact[phone] = now
        return True
    return False

def set_mode(phone: str, mode: str, ttl_sec: int = 600):
    active_conversations[phone] = {
        "mode": mode,
        "until": time.time() + ttl_sec,
        "name": active_conversations.get(phone, {}).get("name", "")
    }

def get_mode(phone: str) -> str:
    info = active_conversations.get(phone)
    if not info:
        return "menu"
    if time.time() > info.get("until", 0):
        return "menu"
    return info.get("mode", "menu")

def set_name(phone: str, name: str):
    info = active_conversations.get(phone, {})
    info["name"] = name
    info["until"] = time.time() + 600
    info["mode"] = info.get("mode", "menu")
    active_conversations[phone] = info

def get_name(phone: str) -> str:
    return active_conversations.get(phone, {}).get("name", "")

# ========= Asistente híbrido =========
FAQ = [
    # Requisitos profesionales
    (["requisito", "trabajar", "matricula", "monotributo", "mala praxis"],
     "Para trabajar con REKAR: *Kinesiólogos* y *Enfermeros/as* con matrícula *provincial y nacional*, monotributo activo y *seguro de mala praxis*."),
    # Zonas
    (["zona", "sur", "oeste", "cobertura", "donde trabajan"],
     "Hoy operamos en *Zona Sur* y *Zona Oeste* del AMBA. Vamos ampliando según la demanda."),
    # Servicios
    (["prestación", "servicio", "guardia", "visita", "domiciliaria", "akm", "akt"],
     "Conectamos pacientes con profesionales de calidad para *atención domiciliaria*, guardias de enfermería y prestaciones varias (AKM, AKT, etc.)."),
    # Sueldos / honorarios
    (["pago", "honorario", "sueldo", "cuánto pagan"],
     "Los honorarios son competitivos y buscamos mejorar las condiciones para que puedas brindar una atención de *alta calidad*."),
    # Pacientes particulares
    (["particular", "precio", "costo", "cuánto sale"],
     "Podemos cotizar atención particular. Decinos zona, necesidad y cobertura (si tenés). ¡Te orientamos!"),
    # Documentación / problemas con carga
    (["documento", "documentación", "subir", "cargar", "problema"],
     "Si tuviste problemas para subir documentación, indicanos *qué paso falló* y tu *correo*. Te ayudamos a completarlo."),
    # Obras sociales
    (["obra social", "prepaga", "institución", "convenio"],
     "Trabajamos con instituciones y obras sociales. Contanos tu necesidad y armamos el nodo de profesionales.")
]

def assistant_reply(text: str) -> str:
    low = text.lower()
    for keywords, answer in FAQ:
        if any(k in low for k in keywords):
            return answer
    return ("Puedo ayudarte con información sobre REKAR, nuestros *servicios*, "
            "*requisitos* para trabajar, *zonas* y *documentación*. "
            "¿Podés contarme un poco más?")

# ========= WhatsApp Webhook =========
@app.route("/webhook", methods=["GET"])
def verify_token():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()
    print("📥 WA in:", data)

    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" in changes:
            msg = changes["messages"][0]
            phone = msg.get("from")
            # texto puede no venir si es botón/interactive; contemplamos fallback
            text = msg.get("text", {}).get("body", "").strip()
            text_low = text.lower()

            # 1) Saludo + pedido de nombre (cuando corresponde)
            if need_new_greeting(phone):
                set_mode(phone, "menu")
                set_name(phone, "")
                send_whatsapp_message(phone, saludo_inicial())
                send_telegram_message(f"📞 Nuevo contacto: {phone}\nMensaje: {text or '(sin texto)'}")
                append_to_sheet("", phone, "WhatsApp")
                return jsonify({"status": "ok"}), 200

            mode = get_mode(phone)
            name = get_name(phone)

            # 2) Captura de nombre (si no lo tenemos aún)
            if not name:
                # Aceptamos “soy …”, “me llamo …” o una sola palabra como nombre
                if any(p in text_low for p in ["soy ", "me llamo", "mi nombre"]):
                    possible = (text_low.replace("me llamo", "")
                                      .replace("mi nombre es", "")
                                      .replace("soy", "")).strip().title()
                else:
                    # Si escribió una o dos palabras, tomarlas como nombre
                    tokens = [t for t in text.title().split() if t.isalpha()]
                    possible = " ".join(tokens[:2])

                if possible:
                    set_name(phone, possible)
                    append_to_sheet(possible, phone, "WhatsApp")
                    send_whatsapp_message(phone, menu_principal(possible))
                    return jsonify({"status":"ok"}), 200
                else:
                    # Re-pedir nombre
                    send_whatsapp_message(phone, "¿Podés decirme tu *nombre*? (por ej: *Soy Ana Pérez*)")
                    return jsonify({"status":"ok"}), 200

            # 3) Si está hablando con humano, no interrumpir
            if mode == "humano":
                # reenviar al Telegram lo que diga el cliente
                send_telegram_message(f"💬 {name} ({phone}): {text}")
                return jsonify({"status":"ok"}), 200

            # 4) Modo asistente IA
            if mode == "asistente":
                if text_low in ("menu", "menú", "volver", "salir"):
                    set_mode(phone, "menu")
                    send_whatsapp_message(phone, menu_principal(name))
                else:
                    reply = assistant_reply(text)
                    send_whatsapp_message(phone, reply + "\n\n" + post_accion())
                return jsonify({"status":"ok"}), 200

            # 5) Modo menú (default)
            # Normalizar selecciones
            if text_low in ("menu", "menú"):
                send_whatsapp_message(phone, menu_principal(name))
                return jsonify({"status":"ok"}), 200

            if text in ("1", "2", "3", "4", "5", "6", "7"):
                option = text
            else:
                # Si no es un número, recordatorio de menú
                send_whatsapp_message(phone, "Si querés volver al *menú*, escribí *menu*.")
                return jsonify({"status":"ok"}), 200

            if option == "1":
                send_whatsapp_message(phone, "Podés enviar tu *CV* a: rekar.salud@gmail.com")
                send_whatsapp_message(phone, post_accion())

            elif option == "2":
                send_whatsapp_message(
                    phone,
                    "Requisitos REKAR:\n"
                    "• *Kinesiólogo/a* con *matrícula provincial y nacional*\n"
                    "• *Enfermero/a prof. o Lic. en Enfermería* con *matrícula prov. y nac.*\n"
                    "• *Monotributo* activo\n"
                    "• *Seguro de mala praxis*"
                )
                send_whatsapp_message(phone, post_accion())

            elif option == "3":
                send_whatsapp_message(
                    phone,
                    "Nuestra web (reemplazar cuando tengas el link definitivo):\n"
                    "https://rekarsalud.blogspot.com/?m=1"
                )
                send_whatsapp_message(phone, post_accion())

            elif option == "4":
                send_whatsapp_message(
                    phone,
                    "Formulario para base de datos (agregá tu link cuando lo tengas):\n"
                    "👉 [pendiente de cargar]"
                )
                send_whatsapp_message(phone, post_accion())

            elif option == "5":
                send_whatsapp_message(
                    phone,
                    "Somos *REKAR*: conectamos pacientes con profesionales de calidad.\n"
                    "Operamos en *Zona Sur* y *Zona Oeste* del AMBA.\n"
                    "Creamos *nodos* donde hay demanda para que tengas *cartera cerca*.\n"
                    "Capacitamos a profesionales y buscamos honorarios *competitivos*."
                )
                send_whatsapp_message(phone, post_accion())

            elif option == "6":
                set_mode(phone, "humano", ttl_sec=3600) # 1 hora
                send_whatsapp_message(phone, "Perfecto. Un representante humano te escribirá por este medio. 😊")
                send_telegram_message(f"📞 {name} ({phone}) solicita hablar con un representante.")
                # No mostramos menú para no interrumpir

            elif option == "7":
                set_mode(phone, "asistente")
                send_whatsapp_message(
                    phone,
                    "Entraste al modo *RekyBot* (IA liviana). Preguntame sobre requisitos, zonas, servicios, "
                    "honorarios o documentación. Escribí *menu* para volver."
                )

            return jsonify({"status":"ok"}), 200

        # Si llegó “statuses” (confirmaciones de entrega), ignorar
    except Exception as e:
        print("❌ Error WA webhook:", e)

    return jsonify({"status": "ok"}), 200

# ========= Telegram webhook (para /enviar desde el grupo) =========
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    print("🤖 TG in:", data)

    try:
        if "message" not in data:
            return jsonify({"status":"ignored"}), 200

        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "")

        # Asegurar que venga del grupo/canal que configuraste
        if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
            print("Mensaje de otro chat; ignorado.")
            return jsonify({"status":"ignored"}), 200

        if text and text.startswith("/enviar"):
            # Formato: /enviar 54911xxxxxx mensaje libre
            try:
                parts = text.split(" ", 2)
                if len(parts) < 3:
                    send_telegram_message("⚠️ Formato: /enviar <5491xxxxxxxx> <mensaje>")
                    return jsonify({"status":"ok"}), 200

                phone = parts[1].replace("+", "").strip()
                reply = parts[2].strip()

                if send_whatsapp_message(phone, reply):
                    # Activamos modo humano para ese phone y no interrumpir con menú por 10 min
                    set_mode(phone, "humano", ttl_sec=600)
                    send_telegram_message(f"✅ Enviado a {phone}")
                else:
                    send_telegram_message(f"❌ No se pudo enviar a {phone}")
            except Exception as e:
                print("❌ Error /enviar:", e)
                send_telegram_message("❌ Error procesando /enviar")

        else:
            # Cualquier otro texto en el grupo se ignora para no hacer eco
            pass

    except Exception as e:
        print("❌ TG webhook error:", e)

    return jsonify({"status":"ok"}), 200

# ========= Inicio (solo desarrollo local) =========
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
