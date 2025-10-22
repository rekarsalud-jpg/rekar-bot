
# ==========================================
# 🤖 REKYBOT v1.5.1 – WhatsApp + Telegram + Gemini + Sheets (estable)
# ==========================================

import os, time, json, re
import requests
from flask import Flask, request, jsonify

# === Google Sheets (opcional) ===
USE_SHEETS = False
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    USE_SHEETS = True
except Exception:
    USE_SHEETS = False

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FORM_URL = os.getenv("FORM_URL", "https://forms.gle/tu-formulario")
EMAIL_DESTINATION = os.getenv("EMAIL_DESTINATION", "rekar.salud@gmail.com") # solo texto en opciones

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")

# Google Sheets (opcional)
GSHEETS_CREDENTIALS_FILE = os.getenv("GSHEETS_CREDENTIALS_FILE", "") # JSON del service account (contenido)
GSHEETS_SHEET_NAME = os.getenv("GSHEETS_SHEET_NAME", "Contactos") # nombre de la hoja

# === VARIABLES INTERNAS ===
sessions = {} # {phone: {"state":..., "name":..., "time":..., "human_since":...}}
last_user_text = {} # anti-duplicado por texto
HUMAN_TTL = 60 * 60 # 60 min
GREETING_VERSION = "1.5.1"

# ======= HELPERS =======

def now():
    return int(time.time())

def send_whatsapp_text(phone, text):
    """Envia texto a WhatsApp API."""
    if not (ACCESS_TOKEN and PHONE_NUMBER_ID):
        print("❌ Falta ACCESS_TOKEN o PHONE_NUMBER_ID")
        return False

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
        r = requests.post(url, headers=headers, json=data, timeout=20)
        ok = (r.status_code == 200)
        if not ok:
            print("❌ WhatsApp error:", r.text)
        return ok
    except Exception as e:
        print("⚠️ Excepción WhatsApp:", e)
        return False

def send_telegram(text, reply_to_message_id=None):
    """Envía un mensaje al grupo de Telegram."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print("⚠️ Excepción Telegram:", e)

def parse_phone_from_telegram_message(text):
    """
    Extrae +549... o 549... o 11... entre paréntesis si viene de un mensaje re-enviado.
    Ej: "Rodrigo (+5491168543959): Hola" -> +5491168543959
    """
    # Busca (+549...) o (549...) dentro del texto
    m = re.search(r"\((\+?\d{6,20})\)", text)
    if m:
        return m.group(1)
    # como fallback, intenta detectar un número suelto largo
    m2 = re.search(r"(\+?\d{10,20})", text)
    if m2:
        return m2.group(1)
    return None

# ======= MENSAJES =======

def greeting():
    return (
        f"👋 ¡Hola! Soy 🤖 *RekyBot {GREETING_VERSION}*, asistente virtual de *REKAR*. 😊\n"
        "Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
        "¿Cómo es tu *nombre*?"
    )

def menu_for(name):
    n = name or "¡genial!"
    return (
        f"¡Genial, {n}! ✨\n"
        "Elegí una opción:\n\n"
        f"1️⃣ Enviar tu CV ({EMAIL_DESTINATION})\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante de REKAR\n"
        "7️⃣ Seguir chateando con RekyBot (modo asistente IA)\n"
        "8️⃣ Salir ❌\n\n"
        "Si querés volver al *menú*, escribí *M*.\n"
        "Para *salir*, escribí *S*."
    )

def info_requisitos():
    return (
        "✅ *Requisitos para trabajar en REKAR:*\n"
        "• Título y matrícula habilitante (según profesión).\n"
        "• DNI y CBU.\n"
        "• Seguro/ART o voluntad de gestionarlo con nosotros.\n"
        "• Disponibilidad horaria (guardias/visitas a acordar).\n"
        "• Buena comunicación y trato con pacientes/familias."
    )

def info_empresa():
    return (
        "🏥 *Sobre REKAR*\n"
        "Brindamos *servicios domiciliarios* de *kinesiología* y *enfermería* en *CABA* y *GBA*.\n"
        "• Prestaciones planificadas y guardias de enfermería.\n"
        "• Atención particular y convenios con obras sociales.\n"
        "• Equipo humano con foco en la calidad y el respeto."
    )

def after_human_ack():
    return "🕐 Gracias por tu mensaje. Nuestro representante ya fue notificado y te responderá a la brevedad."

def bye_msg():
    return "¡Gracias por contactarte con *REKAR*! 👋 Cuando necesites, escribinos de nuevo."

# ======= GOOGLE SHEETS =======

def sheets_client():
    """Devuelve cliente de gspread si hay credenciales en env (contenido JSON)."""
    if not (USE_SHEETS and GSHEETS_CREDENTIALS_FILE):
        return None
    try:
        creds_json = json.loads(GSHEETS_CREDENTIALS_FILE)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        gc = gspread.authorize(creds)
        return gc
    except Exception as e:
        print("⚠️ Sheets no disponible:", e)
        return None

def save_contact_to_sheet(phone, name):
    gc = sheets_client()
    if not gc:
        return
    try:
        sh = None
        # abre por nombre de spreadsheet igual a "Contactos_REKAR" (o crea)
        title = "Contactos_REKAR"
        try:
            sh = gc.open(title)
        except Exception:
            sh = gc.create(title)
        try:
            ws = sh.worksheet(GSHEETS_SHEET_NAME)
        except Exception:
            ws = sh.add_worksheet(GSHEETS_SHEET_NAME, rows=1000, cols=6)
            ws.update("A1:D1", [["FechaUnix", "Telefono", "Nombre", "Fuente"]])
        # busca si ya existe el teléfono
        rows = ws.get_all_records()
        exists_row = next((r for r in rows if str(r.get("Telefono", "")) == str(phone)), None)
        if exists_row:
            # actualizar nombre
            idx = rows.index(exists_row) + 2
            ws.update_cell(idx, 3, name)
        else:
            ws.append_row([now(), str(phone), name, "WhatsApp"])
        print("✅ Guardado en Google Sheets")
    except Exception as e:
        print("⚠️ Error guardando en Sheets:", e)

# ======= GEMINI =======

def ask_gemini(prompt, context_hint=""):
    """
    Llama a Gemini 1.5 Flash (latest).
    Fallback: devuelve None si hay error para que el flujo responda modo "híbrido".
    """
    if not GEMINI_API_KEY:
        return None
    try:
        url = f"{GEMINI_URL}/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        system_hint = (
            "Sos el asistente de REKAR. Respondé breve, amable y claro. "
            "Si preguntan por precios, horarios o zonas, respondé con la info conocida: "
            "horario 9 a 19 hs, zonas CABA y GBA, servicios de kinesiología y enfermería. "
            "Si falta info exacta, sugerí 'te puede contactar un representante (opción 6)'."
        )
        parts = []
        if context_hint:
            parts.append({"text": context_hint})
        parts.append({"text": prompt})
        body = {"contents": [{"parts": parts}],
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 256}
        }
        # prepend system hint vía "system_instruction" (nuevo formato beta)
        body["systemInstruction"] = {"parts": [{"text": system_hint}]}

        r = requests.post(url, headers=headers, json=body, timeout=25)
        if r.status_code != 200:
            send_telegram(f"⚠️ Gemini respondió con código {r.status_code}. Error: {r.text[:500]}")
            return None
        data = r.json()
        # navega candidates->content->parts->text
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            return None
        return parts[0].get("text", "").strip()
    except Exception as e:
        send_telegram(f"⚠️ Error llamando a Gemini: {e}")
        return None

# ======= CONTROL DE SESIÓN =======

def clear_session(phone):
    sessions.pop(phone, None)
    last_user_text.pop(phone, None)
    print(f"🧹 Sesión cerrada para {phone}")

def ensure_session(phone):
    if phone not in sessions:
        sessions[phone] = {"state": "start", "time": now(), "name": ""}
    return sessions[phone]

def is_duplicate(phone, text):
    prev = last_user_text.get(phone)
    if prev and prev.strip() == text.strip():
        return True
    last_user_text[phone] = text
    return False

# ======= WEBHOOK WHATSAPP =======

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge", "")
        return "Invalid token", 403

    data = request.get_json(silent=True) or {}
    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" not in changes:
            return jsonify({"ok": True}), 200

        msg = changes["messages"][0]
        phone = msg.get("from")
        text = msg.get("text", {}).get("body", "").strip()

        if not phone:
            return jsonify({"ok": True}), 200

        # Anti eco / duplicado
        if text and is_duplicate(phone, text):
            return jsonify({"ok": True}), 200

        info = ensure_session(phone)

        # Comandos globales
        if text.lower() in ["s", "salir"]:
            send_whatsapp_text(phone, bye_msg())
            clear_session(phone)
            return jsonify({"ok": True}), 200

        if text.lower() in ["m", "menu"]:
            info["state"] = "menu"
            send_whatsapp_text(phone, menu_for(info.get("name", "")))
            return jsonify({"ok": True}), 200

        # Estados
        if info["state"] == "start":
            send_whatsapp_text(phone, greeting())
            info["state"] = "awaiting_name"
            return jsonify({"ok": True}), 200

        elif info["state"] == "awaiting_name":
            name = text.split(" ")[0].strip().title() if text else "Cliente"
            info["name"] = name
            send_whatsapp_text(phone, menu_for(name))
            # guardar en sheet (opcional)
            try:
                save_contact_to_sheet(phone, name)
            except Exception as e:
                print("Sheets skip:", e)
            info["state"] = "menu"
            return jsonify({"ok": True}), 200

        elif info["state"] == "menu":
            ch = text.strip()
            if ch == "1":
                send_whatsapp_text(phone, f"📧 Enviá tu CV a: {EMAIL_DESTINATION}\n¡Gracias por postularte! 🙌")
            elif ch == "2":
                send_whatsapp_text(phone, info_requisitos())
            elif ch == "3":
                send_whatsapp_text(phone, "🌐 Visitá nuestra web: https://rekarsalud.blogspot.com/?m=1")
            elif ch == "4":
                send_whatsapp_text(phone, f"🗂️ Completá el formulario: {FORM_URL}")
            elif ch == "5":
                send_whatsapp_text(phone, info_empresa())
            elif ch == "6":
                # activar modo humano (silenciar bot y reenviar a Telegram)
                info["state"] = "human_mode"
                info["human_since"] = now()
                send_whatsapp_text(phone, "📞 *Listo.* Un representante fue notificado. Te responderá por este chat.")
                send_telegram(f"📞 Nuevo cliente quiere hablar con un representante:\n{info.get('name','Cliente')} (+{phone})")
            elif ch == "7":
                info["state"] = "assistant_mode"
                info["assistant_since"] = now()
                send_whatsapp_text(phone, "💬 Ahora estás chateando con *RekyBot Asistente*. Podés hacerme preguntas sobre nuestros servicios.")
            elif ch == "8":
                send_whatsapp_text(phone, bye_msg())
                clear_session(phone)
            else:
                send_whatsapp_text(phone, "No entendí. Indicá el *número* de la opción, *M* para menú o *S* para salir.")
            return jsonify({"ok": True}), 200

        elif info["state"] == "human_mode":
            # si está dentro del TTL, NO contestamos; solo reenviamos a Telegram
            if now() - info.get("human_since", 0) < HUMAN_TTL:
                send_telegram(f"💬 {info.get('name','Cliente')} (+{phone}): {text}")
                # Respuesta mínima automática para que el cliente sepa que está en cola
                send_whatsapp_text(phone, after_human_ack())
            else:
                # expiró conversación, volvemos al menú
                info["state"] = "menu"
                send_whatsapp_text(phone, "⏳ La conversación anterior finalizó por inactividad. Volvemos al menú.")
                send_whatsapp_text(phone, menu_for(info.get("name","")))
            return jsonify({"ok": True}), 200

        elif info["state"] == "assistant_mode":
            # Primero intentamos Gemini
            ctx = "Empresa REKAR: kinesiología y enfermería domiciliaria en CABA y GBA. Horario 9-19 hs."
            answer = ask_gemini(text, context_hint=ctx)
            if not answer:
                # Fallback híbrido simple
                low = text.lower()
                if any(k in low for k in ["zona", "dónde", "caba", "gba", "burzaco", "adrogué"]):
                    answer = "Trabajamos en CABA y GBA. Contanos tu barrio y te confirmamos."
                elif "precio" in low or "cuánto" in low or "pagan" in low:
                    answer = "Los costos varían según la prestación. Si querés, un representante te asesora (opción 6)."
                elif "horario" in low or "atienden" in low:
                    answer = "Nuestro horario de atención es de lunes a sábado de 9 a 19 hs."
                elif "cv" in low or "postular" in low:
                    answer = f"Podés enviar tu CV a {EMAIL_DESTINATION} o completar el formulario (opción 4)."
                else:
                    answer = "Gracias por tu consulta. Si querés info precisa, podés hablar con un representante (opción 6)."

            send_whatsapp_text(phone, answer + "\n\nEscribí *M* para volver al menú o *S* para salir.")
            return jsonify({"ok": True}), 200

    except Exception as e:
        print("⚠️ Error webhook WA:", e)
        return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200

# ======= WEBHOOK TELEGRAM (responder directo y comandos) =======

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", {})
    if not msg:
        return jsonify({"ok": True}), 200

    chat_id = str(msg.get("chat", {}).get("id", ""))
    if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
        # Ignora otros chats
        return jsonify({"ok": True}), 200

    text = (msg.get("text") or "").strip()
    reply = msg.get("reply_to_message")

    # /cerrar <telefono>
    if text.startswith("/cerrar"):
        try:
            _, phone = text.split(" ", 1)
            phone = phone.strip()
            clear_session(phone)
            send_telegram(f"✅ Sesión cerrada para {phone}")
            return jsonify({"ok": True}), 200
        except Exception:
            send_telegram("❌ Uso: /cerrar <número>")
            return jsonify({"ok": True}), 200

    # /enviar <telefono> <mensaje>
    if text.startswith("/enviar"):
        try:
            _, rest = text.split(" ", 1)
            phone, message = rest.split(" ", 1)
            send_whatsapp_text(phone.strip(), message.strip())
            return jsonify({"ok": True}), 200
        except Exception:
            send_telegram("❌ Formato: /enviar <número> <mensaje>")
            return jsonify({"ok": True}), 200

    # Responder con “Responder” a un mensaje del bot
    if reply:
        original_text = reply.get("text", "")
        phone = parse_phone_from_telegram_message(original_text)
        if phone:
            send_whatsapp_text(phone, text)
            # mantener estado human_mode vivo si existe
            info = sessions.get(phone)
            if info and info.get("state") == "human_mode":
                info["human_since"] = now()
        else:
            send_telegram("❌ No pude detectar el número en el mensaje citado.")
        return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200

# ======= SALUD =======

@app.route("/", methods=["GET"])
def health():
    return jsonify({"service": "RekyBot", "version": GREETING_VERSION, "ok": True})

# ======= RUN =======

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)