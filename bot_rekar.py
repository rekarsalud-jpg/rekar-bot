# ==========================================
# 🤖 REKYBOT 1.4 – híbrido con Gemini (Render)
# ==========================================
import os, time, requests, json
from flask import Flask, request, jsonify

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN       = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID    = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN       = os.getenv("VERIFY_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = str(os.getenv("TELEGRAM_CHAT_ID") or "")

# IA (usa una u otra; si ninguna está presente se usa fallback interno)
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")       # ej: AIza...
GEMINI_LOCAL_URL   = os.getenv("GEMINI_LOCAL_URL")     # ej: https://tu-servidor-ia/prompt

# Info de la empresa (poné tus links reales cuando los tengas)
COMPANY_EMAIL = os.getenv("EMAIL_DESTINATION", "rekar.salud@gmail.com")
WEB_URL       = os.getenv("WEB_URL", "https://rekarsalud.blogspot.com/?m=1")
FORM_URL      = os.getenv("FORM_URL", "https://forms.gle/poner-link-form")

# === VARIABLES INTERNAS ===
SEEN_TTL       = 120          # segundos para ignorar duplicados de WhatsApp
HUMAN_TTL      = 60 * 60      # 60 minutos de ventana de humano
active_sessions      = {}     # phone -> {state, name, time}
active_conversations = {}     # phone -> bool (humano activo)
last_seen             = {}     # phone -> (last_text, ts)

# ==============================================
# UTILIDADES
# ==============================================
def now():
    return time.time()

def log(msg):
    print(msg, flush=True)

def send_whatsapp_text(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        ok = r.status_code == 200
        if not ok:
            log(f"❌ WA send error {r.status_code}: {r.text}")
        return ok
    except Exception as e:
        log(f"⚠️ WA send exception: {e}")
        return False

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=20)
        log(f"📤 TG: {text[:120]}")
    except Exception as e:
        log(f"⚠️ TG send exception: {e}")

def is_duplicate_wa(phone, text):
    """Evita loops por reintentos de WhatsApp (mismo texto en ventana corta)."""
    text = (text or "").strip()
    last_text, ts = last_seen.get(phone, ("", 0))
    if text and text == last_text and (now() - ts) < SEEN_TTL:
        log(f"⚠️ Duplicado WA ignorado para {phone}")
        return True
    last_seen[phone] = (text, now())
    return False

def clear_session(phone, silent=False):
    active_sessions.pop(phone, None)
    active_conversations.pop(phone, None)
    last_seen.pop(phone, None)
    if not silent:
        log(f"🧹 Sesión cerrada para {phone}")

# ==============================================
# CONTENIDOS
# ==============================================
def greeting():
    return (
        "👋 ¡Hola! Soy 🤖 *RekyBot 1.4*, asistente virtual de *REKAR*. 😊\n"
        "Gracias por escribirnos. Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
        "¿Cómo es tu nombre?"
    )

def main_menu(name=""):
    nombre = name or "¡gracias!"
    return (
        f"¡Genial, {nombre}! 🌟\n"
        "Elegí una opción:\n\n"
        f"1️⃣ Enviar tu CV ({COMPANY_EMAIL})\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        f"3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante de REKAR\n"
        "7️⃣ Seguir chateando con RekyBot (modo asistente)\n"
        "8️⃣ Salir ❌\n\n"
        "Escribí *M* para ver el menú o *S* para salir."
    )

# Fallback FAQ simple si no hay IA disponible o falla
def faq_fallback(q):
    t = q.lower()
    if any(k in t for k in ["cv", "curriculum", "currículum", "correo", "mail"]):
        return f"Podés enviar tu CV a {COMPANY_EMAIL}. Recordá adjuntar datos de contacto y zona de trabajo."
    if any(k in t for k in ["requisit", "matrícula", "monotrib", "mala praxis"]):
        return ("Requisitos: Kinesiólogo/a o Enfermero/a profesional con matrícula provincial y nacional, "
                "monotributo activo y seguro de mala praxis.")
    if any(k in t for k in ["web", "página", "site"]):
        return f"Nuestra web: {WEB_URL}"
    if any(k in t for k in ["form", "base de datos", "registr"]):
        return f"Formulario (base de datos): {FORM_URL}"
    if any(k in t for k in ["zona", "cobertura", "dónde", "donde"]):
        return "Operamos principalmente en Zona Sur y Zona Oeste (CABA y GBA)."
    if any(k in t for k in ["pago", "sueldo", "cuánto pagan", "cuanto pagan", "honorarios", "tarifa"]):
        return ("Los honorarios son competitivos y dependen de la prestación, zona y obra social. "
                "Te contamos detalles cuando completes requisitos.")
    if any(k in t for k in ["guardia", "prestación", "prestaciones", "servicio", "servicios"]):
        return ("Prestamos servicios de enfermería y kinesiología domiciliaria: AKM, AKT, prestaciones "
                "y guardias según cobertura.")
    return None

# ==============================================
# IA: Gemini (API pública o servidor local)
# ==============================================
def ask_gemini(question, context):
    """Devuelve string con respuesta de IA o None si falla o no hay proveedor."""
    prompt = (
        "Actuá como asistente de REKAR (red de servicios domiciliarios de kinesiología y enfermería). "
        "Respondé breve, cálido, claro y en castellano rioplatense. "
        "Usá solo la información de contexto si aplica y evitá inventar datos.\n\n"
        f"Contexto:\n{context}\n\n"
        f"Pregunta del usuario: {question}"
    )

    # 1) Google Generative Language API (Gemini)
    if GEMINI_API_KEY:
        try:
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "gemini-1.5-flash-latest:generateContent?key=" + GEMINI_API_KEY)
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            r = requests.post(url, json=body, timeout=25)
            if r.status_code == 200:
                data = r.json()
                # Navegación defensiva por si cambia el schema
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            log(f"⚠️ Gemini API fail {r.status_code}: {r.text[:180]}")
        except Exception as e:
            log(f"⚠️ Gemini API exception: {e}")

    # 2) Servidor local/propio (si configurás GEMINI_LOCAL_URL)
    if GEMINI_LOCAL_URL:
        try:
            r = requests.post(GEMINI_LOCAL_URL, json={"prompt": prompt}, timeout=25)
            if r.status_code == 200:
                j = r.json()
                # intentamos campos típicos
                return (j.get("text") or j.get("answer") or j.get("response") or "").strip() or None
            log(f"⚠️ Local IA fail {r.status_code}: {r.text[:180]}")
        except Exception as e:
            log(f"⚠️ Local IA exception: {e}")

    # 3) Sin IA: usamos fallback
    return None

# ==============================================
# WEBHOOK WHATSAPP
# ==============================================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json(silent=True) or {}
    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return jsonify({"ok": True}), 200

        msg = messages[0]
        phone = msg.get("from")
        text  = msg.get("text", {}).get("body", "").strip()

        if not phone or is_duplicate_wa(phone, text):
            return jsonify({"ok": True}), 200

        # Estado inicial
        info = active_sessions.get(phone) or {"state": "start", "time": now()}
        state = info["state"]

        # Comandos globales
        low = text.lower()
        if low in ("s", "salir"):
            send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
            clear_session(phone)
            return jsonify({"ok": True}), 200
        if low in ("m", "menu", "menú"):
            send_whatsapp_text(phone, main_menu(info.get("name", "")))
            info["state"] = "menu"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        # Flujo por estado
        if state == "start":
            send_whatsapp_text(phone, greeting())
            info["state"] = "awaiting_name"
            active_sessions[phone] = info
            return jsonify({"ok": True}), 200

        if state == "awaiting_name":
            name = (text.split()[0] if text else "Cliente").capitalize()
            info["name"] = name
            info["state"] = "menu"
            active_sessions[phone] = info
            send_whatsapp_text(phone, main_menu(name))
            # Aviso de nuevo contacto (una vez)
            send_telegram_message(f"📞 Nuevo contacto: +{phone}\nMensaje inicial: {text or '(sin texto)'}")
            return jsonify({"ok": True}), 200

        if state == "menu":
            if low == "1":
                send_whatsapp_text(phone, f"📧 Enviá tu CV a: {COMPANY_EMAIL}\n¡Gracias por postularte! 🙌")
            elif low == "2":
                send_whatsapp_text(
                    phone,
                    "✅ Requisitos:\n• Kinesiólogo/a o Enfermero/a profesional\n"
                    "• Matrícula provincial y nacional\n• Monotributo activo\n• Seguro de mala praxis"
                )
            elif low == "3":
                send_whatsapp_text(phone, f"🌐 Nuestra web: {WEB_URL}")
            elif low == "4":
                send_whatsapp_text(phone, f"🗂️ Formulario para base de datos: {FORM_URL}")
            elif low == "5":
                send_whatsapp_text(
                    phone,
                    "🏥 REKAR conecta pacientes con profesionales de calidad en Zona Sur y Zona Oeste. "
                    "Capacitamos a nuestro equipo y buscamos siempre el mejor beneficio para el profesional."
                )
            elif low == "6":
                send_whatsapp_text(phone, "🧑‍💼 Perfecto, te conecta un representante humano. Podés escribir tu consulta.")
                info["state"] = "human_mode"
                info["time"]  = now()
                active_sessions[phone] = info
                nm = info.get("name", "Cliente")
                send_telegram_message(f"🟢 {nm} (+{phone}) solicita hablar con un representante.")
            elif low == "7":
                send_whatsapp_text(phone, "💬 Estás chateando con *RekyBot Asistente*. Contame, ¿qué necesitás?")
                info["state"] = "assistant_mode"
                info["time"]  = now()
                active_sessions[phone] = info
            elif low == "8":
                send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Que tengas un gran día.")
                clear_session(phone)
            else:
                send_whatsapp_text(phone, "No entendí. Escribí el *número* de la opción, *M* para menú o *S* para salir.")
            return jsonify({"ok": True}), 200

        if state == "human_mode":
            # Dentro de la ventana, relay a Telegram sin spamear al cliente
            elapsed = now() - info.get("time", 0)
            nm = info.get("name", "Cliente")
            if elapsed <= HUMAN_TTL:
                send_telegram_message(f"💬 {nm} (+{phone}): {text}")
                # Mensaje corto de recepción solo si el cliente inicia (no repetir en cada turno)
                if not active_conversations.get(phone):
                    send_whatsapp_text(phone, "✅ Recibido. Un representante te responderá por este mismo chat.")
                    active_conversations[phone] = True
            else:
                send_whatsapp_text(phone, "⏳ La conversación anterior finalizó. Escribí *6* si querés hablar con alguien.")
                info["state"] = "menu"
                active_sessions[phone] = info
                send_whatsapp_text(phone, main_menu(info.get("name", "")))
            return jsonify({"ok": True}), 200

        if state == "assistant_mode":
            # Intento IA
            context = (
                f"Nombre: {info.get('name')}\n"
                f"Web: {WEB_URL}\n"
                f"Email: {COMPANY_EMAIL}\n"
                "Zonas: Zona Sur y Zona Oeste (CABA y GBA)\n"
                "Servicios: enfermería y kinesiología domiciliaria; AKM/AKT; guardias según cobertura.\n"
                "Requisitos profesionales: matrículas, monotributo, mala praxis."
            )
            ai = ask_gemini(text, context)
            if not ai:
                ai = faq_fallback(text) or (
                    "Gracias por tu consulta. Podés preguntarme por *requisitos, zonas, web, formulario, servicios* "
                    "o escribí *M* para volver al menú."
                )
            send_whatsapp_text(phone, ai)
            return jsonify({"ok": True}), 200

        # Si llega acá por algún motivo, reseteamos flujo con saludo
        send_whatsapp_text(phone, greeting())
        info["state"] = "awaiting_name"
        active_sessions[phone] = info
        return jsonify({"ok": True}), 200

    except Exception as e:
        log(f"⚠️ Error webhook WA: {e}")
        return jsonify({"ok": True}), 200

# ==============================================
# WEBHOOK TELEGRAM (respuestas del equipo)
# ==============================================
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    msg  = data.get("message") or {}
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))

    # Solo aceptamos mensajes del grupo/canal configurado
    if not TELEGRAM_CHAT_ID or chat_id != TELEGRAM_CHAT_ID:
        return jsonify({"ok": True}), 200

    text = (msg.get("text") or "").strip()
    if not text:
        return jsonify({"ok": True}), 200

    # Comandos:
    # /enviar <telefono> <mensaje>
    # /cerrar <telefono>
    if text.startswith("/cerrar"):
        parts = text.split(" ", 1)
        if len(parts) == 2:
            phone = parts[1].strip()
            clear_session(phone)
            send_telegram_message(f"✅ Sesión cerrada para {phone}")
        else:
            send_telegram_message("Uso: /cerrar <telefono>")
        return jsonify({"ok": True}), 200

    if text.startswith("/enviar"):
        try:
            _, phone, message = text.split(" ", 2)
            if send_whatsapp_text(phone.strip(), message.strip()):
                send_telegram_message(f"✅ Enviado a +{phone}")
            else:
                send_telegram_message("❌ No se pudo enviar a WhatsApp.")
        except ValueError:
            send_telegram_message("Uso: /enviar <telefono> <mensaje>")
        return jsonify({"ok": True}), 200

    # Responder a la última conversación marcada como humana:
    # Formato sugerido: +54911...: tu mensaje
    if ":" in text and text.strip().startswith("+"):
        phone_part, reply = text.split(":", 1)
        phone = phone_part.replace("+", "").strip()
        reply = reply.strip()
        if send_whatsapp_text(phone, reply):
            send_telegram_message(f"✅ Respuesta enviada a +{phone}")
        else:
            send_telegram_message("❌ No se pudo enviar la respuesta.")
    else:
        send_telegram_message("ℹ️ Para responder: '+<telefono>: <mensaje>'\nO usá /enviar <telefono> <mensaje>.")

    return jsonify({"ok": True}), 200

# ==============================================
# APP
# ==============================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
