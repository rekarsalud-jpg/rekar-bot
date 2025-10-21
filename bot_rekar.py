import os
import time
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate

app = Flask(__name__)

# ====== ENTORNO ======
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip()

# Registro opcional (Google Sheets via webhook) o email fallback
SHEET_WEBHOOK_URL = os.getenv("SHEET_WEBHOOK_URL", "").strip()
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_DESTINATION = os.getenv("EMAIL_DESTINATION", EMAIL_SENDER)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# ====== ESTADO EN MEMORIA ======
# phone -> estado
conversations = {} # { phone: {"mode": "menu|espera_nombre|humano|asistente", "name": str, "last_ts": float, "notified_first": bool} }
tg_msgid_to_phone = {} # tg_message_id -> phone (para reply)
phone_to_tgmsg_id = {} # phone -> último message_id anunciado

HUMAN_TTL = 15 * 60 # 15 minutos de silencio de bot cuando un humano toma la conversación
GREETING_COOLDOWN = 30 * 60 # 30 minutos para re-saludo

# ====== UTILS ======
def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_contact(phone):
    if phone not in conversations:
        conversations[phone] = {
            "mode": "espera_nombre",
            "name": "",
            "last_ts": 0,
            "notified_first": False
        }
    return conversations[phone]

def set_mode(phone, mode):
    info = ensure_contact(phone)
    info["mode"] = mode
    info["last_ts"] = time.time()

def set_name(phone, name):
    info = ensure_contact(phone)
    info["name"] = (name or "").strip().title()
    info["last_ts"] = time.time()

def get_name(phone):
    return ensure_contact(phone).get("name", "")

def is_human_active(phone):
    info = ensure_contact(phone)
    if info.get("mode") != "humano":
        return False
    return (time.time() - info.get("last_ts", 0)) < HUMAN_TTL

def should_greet(phone):
    info = ensure_contact(phone)
    # no saludar si está en modo humano activo
    if is_human_active(phone):
        return False
    # saludar si nunca saludamos o pasaron 30 min desde la última interacción "no humana"
    last = info.get("last_ts", 0)
    return (time.time() - last) > GREETING_COOLDOWN or info.get("mode") == "espera_nombre"

# ====== ENVÍOS ======
def send_whatsapp_text(phone: str, text: str) -> bool:
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    r = requests.post(url, headers=headers, json=data)
    print("📤 WA ->", r.status_code, r.text)
    return r.status_code == 200

def send_telegram_text(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram no configurado.")
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=15)
    print("📨 TG ->", r.status_code, r.text)
    try:
        js = r.json()
        return js.get("result", {}).get("message_id")
    except Exception:
        return None

def send_email(subject: str, body: str):
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

def append_to_sheet(name: str, phone: str, last_msg: str, source: str = "WhatsApp"):
    if SHEET_WEBHOOK_URL:
        try:
            payload = {"timestamp": now_iso(), "name": name or "", "phone": phone, "message": last_msg or "", "source": source}
            r = requests.post(SHEET_WEBHOOK_URL, json=payload, timeout=10)
            print("🧾 Sheet ->", r.status_code, r.text)
            return
        except Exception as e:
            print("❌ Sheet error:", e)
    # Fallback por email si no hay Sheets
    send_email("Registro de contacto", f"{now_iso()} | {source}\nNombre: {name or '(desconocido)'}\nTel: {phone}\nMensaje: {last_msg}")

# ====== MENSAJES ======
def greeting() -> str:
    return (
        "👋 ¡Hola! Soy *🤖RekyBot 1.3*, asistente virtual de *REKAR*. 😊\n"
        "¡Gracias por escribirnos! Atendemos *lunes a sábado de 9 a 19 hs*.\n\n"
        "¿Cómo es tu nopmbre?"
    )

def main_menu(nombre="") -> str:
    pref = f"¡Genial, *{nombre}*! 🌟\n" if nombre else ""
    return (
        f"{pref}Elegí una opción:\n"
        "1️⃣ Enviar tu CV (rekar.salud@gmail.com)\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante de REKAR\n"
        "7️⃣ Seguir chateando con *RekyBot* (modo asistente)\n"
    )

def post_action_hint() -> str:
    return "Escribí *M* para volver al *menú* o *S* para *salir*."

# ====== ASISTENTE HÍBRIDO (simple) ======
FAQ = [
    (["requisito","trabajar","matricula","monotributo","mala praxis"],
     "Requisitos: Kinesiólogos/as y Enfermeros/as con *matrícula nacional y provincial*, *monotributo activo* y *seguro de mala praxis*."),
    (["zona","sur","oeste","dónde trabajan","donde trabajan","cobertura"],
     "Hoy operamos en *Zona Sur* y *Zona Oeste* del AMBA. Vamos ampliando según demanda."),
    (["prestación","servicio","guardia","visita","domiciliaria","akm","akt"],
     "Conectamos pacientes con profesionales para *atención domiciliaria*, guardias de enfermería y prestaciones (AKM, AKT, etc.)."),
    (["pago","honorario","sueldo","cuánto pagan","cuanto pagan","valores"],
     "Honorarios *competitivos*, buscando mejores condiciones para brindar atención de *alta calidad*."),
    (["particular","precio","costo","cuánto sale","cuanto sale"],
     "Podemos cotizar atención particular. Decinos *zona*, *necesidad* y si tenés *cobertura*."),
    (["obra social","prepaga","institución","institucion","convenio"],
     "Trabajamos con obras sociales y entidades. Contanos la necesidad y armamos el nodo de profesionales.")
]

def assistant_reply(text: str) -> str:
    t = text.lower()
    for kws, ans in FAQ:
        if any(k in t for k in kws):
            return ans
    return ("Soy *RekyBot 1.3* 🤖. Puedo ayudarte con *servicios, zonas, requisitos, documentación, obras sociales*.\n"
            "¿Podés contarme un poco más?")

# ====== WEBHOOKS ======
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Token inválido", 403

@app.route("/webhook", methods=["POST"])
def whatsapp_in():
    data = request.get_json()
    print("📥 WA in:", data)
    try:
        changes = data["entry"][0]["changes"][0]["value"]
        if "messages" not in changes:
            return jsonify({"status": "ack"}), 200

        msg = changes["messages"][0]
        phone = msg.get("from")
        text = msg.get("text", {}).get("body", "").strip()
        info = ensure_contact(phone)

        # --- REGISTRO EN SHEETS / EMAIL (solo al primer mensaje de la sesión) ---
        first_of_session = False
        if not info["notified_first"] or should_greet(phone):
            first_of_session = True

        # --- SALUDO INICIAL / PEDIDO NOMBRE (solo si corresponde) ---
        if should_greet(phone) and not info["notified_first"]:
            set_mode(phone, "espera_nombre")
            send_whatsapp_text(phone, greeting())
            info["notified_first"] = True # Marca como ya saludado
            info["last_ts"] = time.time()
            return jsonify({"ok": True}), 200

        # --- NOMBRE PENDIENTE ---
        if info["mode"] == "espera_nombre":
            low = text.lower()
            possible = ""
            if any(p in low for p in ["soy ", "me llamo", "mi nombre"]):
                possible = (low.replace("me llamo","")
                              .replace("mi nombre es","")
                              .replace("soy","")).strip().title()
            else:
                tokens = [tok for tok in text.title().split() if tok.isalpha()]
                possible = " ".join(tokens[:2])
            if possible:
                set_name(phone, possible)
                set_mode(phone, "menu")
                # Notificar UNA VEZ a Telegram con nombre + número + mensaje
                if not info["notified_first"]:
                    mid = send_telegram_text(f"📲 {possible} (+{phone}) inició contacto: {text or '(sin texto)'}")
                    if mid:
                        tg_msgid_to_phone[mid] = phone
                        phone_to_tgmsg_id[phone] = mid
                    append_to_sheet(possible, phone, text, source="WhatsApp")
                    info["notified_first"] = True
                send_whatsapp_text(phone, f"¡Encantado, *{possible}*! 😊")
                send_whatsapp_text(phone, main_menu(possible))
            else:
                send_whatsapp_text(phone, "¿Me decís tu *nombre*? (Ej: *Soy Ana Pérez*)")
            return jsonify({"ok": True}), 200

        # --- MODO HUMANO ACTIVO: reenviar SOLO los mensajes del cliente a Telegram, bot callado ---
        if is_human_active(phone):
            info["last_ts"] = time.time()
            # En humano sólo avisamos a Telegram cuando el cliente escribe
            mid = send_telegram_text(f"💬 {get_name(phone) or '(sin nombre)'} (+{phone}): {text or '(sin texto)'}")
            if mid:
                tg_msgid_to_phone[mid] = phone
                phone_to_tgmsg_id[phone] = mid
            append_to_sheet(get_name(phone), phone, text, source="WhatsApp")
            return jsonify({"ok": True}), 200

        # --- ATALHOS MENU/SALIR ---
        if text.lower() == "m":
            set_mode(phone, "menu")
            send_whatsapp_text(phone, main_menu(get_name(phone)))
            return jsonify({"ok": True}), 200
        if text.lower() == "s":
            set_mode(phone, "menu")
            send_whatsapp_text(phone, "¡Gracias por contactarte con *REKAR*! 🙌 Cuando necesites, escribinos de nuevo.")
            return jsonify({"ok": True}), 200

        # --- MODO ASISTENTE ---
        if info["mode"] == "asistente":
            if text.lower() in ("menu","menú","m"):
                set_mode(phone, "menu")
                send_whatsapp_text(phone, main_menu(get_name(phone)))
            else:
                ans = assistant_reply(text)
                send_whatsapp_text(phone, ans + "\n\n" + post_action_hint())
            info["last_ts"] = time.time()
            return jsonify({"ok": True}), 200

        # --- MODO MENÚ (default) ---
        if info["mode"] == "menu":
            # Notificar a TG SOLO una vez por sesión (primer texto tras saludo/nombre)
            if first_of_session and not info["notified_first"]:
                mid = send_telegram_text(f"📲 {get_name(phone) or '(sin nombre)'} (+{phone}) escribió: {text or '(sin texto)'}")
                if mid:
                    tg_msgid_to_phone[mid] = phone
                    phone_to_tgmsg_id[phone] = mid
                append_to_sheet(get_name(phone), phone, text, source="WhatsApp")
                info["notified_first"] = True

            if text == "1":
                send_whatsapp_text(phone, "Podés enviar tu *CV* a: rekar.salud@gmail.com\n" + post_action_hint())
            elif text == "2":
                send_whatsapp_text(
                    phone,
                    "Requisitos REKAR:\n"
                    "• Kinesiólogo/a con *matrícula provincial y nacional*\n"
                    "• Enfermero/a prof. o Licenciado/a con *matrícula prov. y nac.*\n"
                    "• *Monotributo* activo\n"
                    "• *Seguro de mala praxis*\n\n" + post_action_hint()
                )
            elif text == "3":
                send_whatsapp_text(phone, "🌐 Web: https://rekarsalud.blogspot.com/?m=1\n" + post_action_hint())
            elif text == "4":
                send_whatsapp_text(phone, "📋 Formulario de base de datos: [pendiente de link]\n" + post_action_hint())
            elif text == "5":
                send_whatsapp_text(
                    phone,
                    "Somos *REKAR*: conectamos pacientes con profesionales de calidad.\n"
                    "Operamos en *Zona Sur* y *Zona Oeste* del AMBA, formando *nodos* según demanda.\n"
                    "Capacitamos profesionales y buscamos honorarios *competitivos*.\n\n" + post_action_hint()
                )
            elif text == "6":
                set_mode(phone, "humano")
                info["last_ts"] = time.time()
                send_whatsapp_text(phone, "Perfecto. Un representante de REKAR se comunicara por este medio. 😊")
                # Aviso ÚNICO a Telegram al entrar en modo humano
                mid = send_telegram_text(f"📞 {get_name(phone) or '(sin nombre)'} (+{phone}) solicitó hablar con un representante.")
                if mid:
                    tg_msgid_to_phone[mid] = phone
                    phone_to_tgmsg_id[phone] = mid
            elif text == "7":
                set_mode(phone, "asistente")
                info["last_ts"] = time.time()
                send_whatsapp_text(
                    phone,
                    "Entraste al modo *RekyBot* 🤖. Preguntame sobre *requisitos, zonas, servicios, honorarios o documentación*.\n"
                    "Escribí *M* para volver al menú."
                )
            else:
                # recordatorio de control por teclas
                send_whatsapp_text(phone, "Si querés volver al *menú*, escribí *M*. Para salir, *S*.")
            return jsonify({"ok": True}), 200

    except Exception as e:
        print("❌ Error WA webhook:", e)

    return jsonify({"ok": True}), 200

# ====== TELEGRAM WEBHOOK (responder por REPLY) ======
@app.route("/telegram", methods=["POST"])
def telegram_in():
    data = request.get_json()
    print("🤖 TG in:", data)
    try:
        if "message" not in data:
            return jsonify({"ok": True}), 200

        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
            return jsonify({"ok": True}), 200

        text = msg.get("text", "")
        reply_to = msg.get("reply_to_message")

        # 1) Responder por REPLY mantiene la conversación sin /enviar
        if reply_to:
            replied_id = reply_to.get("message_id")
            phone = tg_msgid_to_phone.get(replied_id)
            if phone:
                ok = send_whatsapp_text(phone, text)
                if ok:
                    set_mode(phone, "humano")
                    conversations[phone]["last_ts"] = time.time()
                    send_telegram_text(f"✅ Enviado a +{phone}")
                else:
                    send_telegram_text(f"❌ No se pudo enviar a +{phone}")
                return jsonify({"ok": True}), 200

        # 2) Fallback: +54911... mensaje
        if text.startswith(("+", "549", "54")) and " " in text:
            parts = text.split(" ", 1)
            phone_guess = parts[0].replace("+", "")
            body = parts[1].strip()
            ok = send_whatsapp_text(phone_guess, body)
            if ok:
                set_mode(phone_guess, "humano")
                conversations[phone_guess]["last_ts"] = time.time()
                send_telegram_text(f"✅ Enviado a +{phone_guess}")
            else:
                send_telegram_text(f"❌ No se pudo enviar a +{phone_guess}")
            return jsonify({"ok": True}), 200

        # 3) Cerrar manualmente una conversación
        if text.startswith("/cerrar"):
            parts = text.split()
            if len(parts) >= 2:
                phone = parts[1].replace("+", "")
                set_mode(phone, "menu")
                send_whatsapp_text(phone, "Cierro la conversación. Si necesitás algo más, escribí *M* para ver el menú. ¡Gracias! 🙌")
                send_telegram_text(f"🔚 Conversación con +{phone} cerrada.")
            else:
                send_telegram_text("Uso: /cerrar 54911xxxxxx")
            return jsonify({"ok": True}), 200

        # Si escriben otra cosa sin reply, solo instruimos
        send_telegram_text("💡 Respondé por *Responder/Reply* al mensaje del cliente para contestarle directo en WhatsApp.\nTambién podés escribir: `+54911... tu mensaje`")
        return jsonify({"ok": True}), 200

    except Exception as e:
        print("❌ TG webhook error:", e)

    return jsonify({"ok": True}), 200

# ====== MAIN ======
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)

