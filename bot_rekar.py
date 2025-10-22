# ==========================================
# 🤖 REKYBOT 1.5.1 – estable (Render)
# ==========================================

import os, time, requests, json
from flask import Flask, request, jsonify

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN       = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID    = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN       = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = str(os.getenv("TELEGRAM_CHAT_ID", ""))
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL         = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent")
GEMINI_MODEL       = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# === VARIABLES INTERNAS ===
sessions = {}             # {phone: {"state":..., "name":..., "time":..., "human_notified":bool}}
last_user_text = {}       # evita loops
HUMAN_TTL = 3600          # 60 minutos

# ==============================================
# HELPERS
# ==============================================

def send_whatsapp_text(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code == 200:
            print(f"✅ WhatsApp -> {phone}")
            last_user_text[phone] = text
            return True
        print(f"❌ WA error: {r.text}")
    except Exception as e:
        print(f"⚠️ WA exception: {e}")
    return False


def send_telegram_message(text, reply_to=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        requests.post(url, json=payload, timeout=15)
        print("📤 TG -> grupo")
    except Exception as e:
        print(f"⚠️ TG exception: {e}")


def clear_session(phone):
    sessions.pop(phone, None)
    last_user_text.pop(phone, None)
    print(f"🧹 Sesión cerrada {phone}")


def is_duplicate(phone, text):
    return last_user_text.get(phone, "").strip() == str(text).strip()


def get_greeting():
    return (
        "👋 ¡Hola! Soy 🤖 *RekyBot*, asistente virtual de *REKAR*. 😊\n"
        "Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
        "¿Cómo es tu nombre?"
    )


def main_menu(name):
    n = name if name else "¡Genial!"
    return (
        f"¡Genial, {n}! 🌟\n"
        "Elegí una opción:\n\n"
        "1️⃣ Enviar tu CV (rekar.salud@gmail.com)\n"
        "2️⃣ Requisitos para trabajar en REKAR\n"
        "3️⃣ Ingresar a la web institucional\n"
        "4️⃣ Completar formulario de base de datos\n"
        "5️⃣ Información sobre REKAR\n"
        "6️⃣ Hablar con un representante de REKAR\n"
        "7️⃣ Seguir chateando con RekyBot (modo asistente IA)\n"
        "8️⃣ Salir ❌\n\n"
        "📎 También podés usar nuestro asistente (opción 7).\n"
        "Si querés volver al *menú*, escribí M. Para *salir*, S."
    )

# ==============================================
# GEMINI
# ==============================================

def ask_gemini(prompt, context_hint=""):
    """Llama a Gemini 2.0-flash. Devuelve string o None en error."""
    if not GEMINI_API_KEY:
        return None
    try:
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    system_hint = (
        "Sos *RekyBot IA 1.5.2*, el asistente oficial de *REKAR – Red de Enfermería y Kinesiología Argentina*. "
        "Tu misión es representar a REKAR con calidez, claridad y profesionalismo. "
        "Tu estilo debe ser humano, empático y confiable, reflejando siempre nuestro lema: "
        "'Cuidamos con compromiso, sanamos con empatía'. "
        "Debés transmitir cercanía, tranquilidad y conocimiento técnico, hablando de manera sencilla, sin tecnicismos innecesarios. "
        "En REKAR brindamos atención domiciliaria de kinesiología y enfermería, priorizando la calidad humana y la formación continua. "
        "Nuestro objetivo es acompañar tanto al paciente como a su familia, en un proceso de recuperación seguro y digno dentro del hogar. "
        "Atendemos de lunes a sábado, de 9 a 19 hs, en Zona Sur, Zona Oeste y Zona Norte del GBA. "
        "Las sesiones se organizan por paquetes (10 o 20) o mensualmente, buscando la mejor relación costo-calidad. "
        "La osteopatía se abona por sesión individual ($60.000 aprox.), mientras que la kinesiología ronda entre $25.000 y $30.000, "
        "y la enfermería entre $10.000 y $20.000 según la prestación. "
        "Si el usuario es paciente, destacá los beneficios de recibir atención en casa: comodidad, confianza, continuidad del tratamiento. "
        "Si el usuario es profesional, explicá los requisitos: matrícula provincial y nacional, seguro de mala praxis, monotributo activo. "
        "Resaltá que REKAR ofrece honorarios competitivos, formación, soporte constante y asignación de pacientes por cercanía. "
        "Si el usuario es una obra social o institución, mostrale seguridad y ofrecé soluciones: coordinación de prestaciones, control de insumos y seguimiento digital. "
        "Las urgencias médicas no son parte de nuestro servicio: indicá siempre comunicarse con el 107, SAME o su cobertura médica. "
        "Los cuidadores acompañan y asisten, pero no realizan prácticas médicas ni kinésicas. "
        "Si alguien es irrespetuoso o usa malas palabras, respondé con calma y cortá la conversación educadamente. "
        "Si no sabés algo, indicá que puede escribir a rekar.salud@gmail.com o elegir la opción 6 del menú para hablar con un representante. "
        "Finalizá siempre tus respuestas recordando: 🗂 'Si querés volver al menú principal, escribí M. Para salir, S.'"
    )

    faq = {
        "precio": (
            "💰 En REKAR organizamos los tratamientos por paquetes de sesiones (10 o 20), "
            "ya que creemos que la recuperación es un proceso continuo y no una sesión aislada. "
            "Kinesiología cuesta entre $25.000 y $30.000 por sesión (con descuento por paquete), "
            "osteopatía $60.000, y enfermería entre $10.000 y $20.000 según la prestación. "
            "Los pagos pueden realizarse por transferencia o plan mensual."
        ),
        "zona": (
            "📍 Atendemos actualmente en Gran Buenos Aires — Zonas Sur, Oeste y Norte. "
            "Siempre buscamos que el profesional esté cerca del domicilio del paciente, para garantizar continuidad y comodidad."
        ),
        "obras sociales": (
            "🏥 No trabajamos con obras sociales directamente, pero sí realizamos servicios para obras sociales que nos contratan "
            "y derivan pacientes a nuestra red de profesionales."
        ),
        "diferencia": (
            "🌟 REKAR se diferencia por su enfoque humano y tecnológico. "
            "Geolocalizamos pacientes y profesionales, capacitamos continuamente a nuestro equipo, "
            "hacemos seguimiento de cada caso y registramos las evoluciones clínicas. "
            "Además, desarrollamos una app con historia clínica digital, firma electrónica y control de insumos."
        ),
        "seguimiento": (
            "📋 Cada atención queda registrada en planillas y evoluciones kinésicas y de enfermería. "
            "En breve todos los registros estarán en formato digital, para mayor trazabilidad y transparencia. "
            "Supervisamos los tratamientos y acompañamos tanto al paciente como al profesional."
        ),
        "evaluacion": (
            "🧑‍⚕️ Sí, ofrecemos evaluaciones iniciales sin compromiso a través de Zoom. "
            "Es una excelente oportunidad para conocernos y planificar juntos el mejor tratamiento."
        ),
        "profesionales": (
            "👩‍⚕️ Buscamos kinesiólogos, enfermeros y cuidadores con vocación, compromiso y empatía. "
            "En REKAR priorizamos las ganas de trabajar y crecer. "
            "Brindamos capacitaciones y acompañamiento constante a nuestros profesionales."
        ),
        "habilitacion": (
            "✅ Para trabajar con nosotros necesitás: matrícula provincial y nacional habilitante, "
            "seguro de mala praxis vigente, CV actualizado, certificado de antecedentes penales y monotributo activo."
        ),
        "pacientes": (
            "🩺 Atendemos pacientes con patologías respiratorias, motoras, neurológicas, deportivas, pediátricas, posquirúrgicas "
            "y crónicas. También trabajamos en rehabilitación motora y cuidados paliativos."
        ),
        "urgencias": (
            "🚨 En caso de urgencias médicas, comunicate con el 107 (SAME) o tu cobertura médica. "
            "REKAR se dedica al seguimiento y recuperación funcional, no a emergencias. "
            "Podés contactarnos ante cualquier duda o síntoma para recibir orientación."
        ),
        "cuidador": (
            "👵 Los cuidadores acompañan, asisten en higiene, alimentación y control de alarmas, "
            "pero no realizan intervenciones médicas ni kinésicas. Su rol es contener y avisar al equipo de salud ante cualquier cambio."
        ),
        "medicos": (
            "👨‍⚕️ Contamos con médicos coordinadores que supervisan la evolución de los pacientes cada 15 días, "
            "evaluando progresos y garantizando la calidad del tratamiento."
        ),
        "contacto": (
            "📩 Para consultas, postulaciones o convenios, escribinos a rekar.salud@gmail.com "
            "o elegí la opción 6 del menú para hablar con un representante humano."
        )
    }
        
        parts = []
        if context_hint:
            parts.append({"text": context_hint})
        parts.append({"text": prompt})
        body = {
            "contents": [{"parts": parts}],
            "systemInstruction": {"role": "system", "parts": [{"text": system_hint}]}
        }
        r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=10)
        if r.status_code != 200:
            # log a Telegram para diagnosticar
            try:
                send_telegram_message(f"⚠️ Gemini respondió {r.status_code}. Error: {r.text[:700]}")
            except:
                pass
            return None
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts_out = candidates[0].get("content", {}).get("parts", [])
        if not parts_out:
            return None
        return parts_out[0].get("text", "").strip()
    except Exception as e:
        send_telegram_message(f"⚠️ Error llamando a Gemini: {e}")
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

    data = request.get_json()
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = msg["from"]
        text = msg.get("text", {}).get("body", "").strip()

        # Evita eco/duplicado
        if is_duplicate(phone, text):
            return jsonify({"ok": True}), 200

        info = sessions.get(phone, {"state": "start", "time": time.time(), "human_notified": False})

        # Comandos universales
        if text.lower() in ["m", "menu"]:
            info["state"] = "menu"
            sessions[phone] = info
            send_whatsapp_text(phone, main_menu(info.get("name")))
            return jsonify({"ok": True}), 200

        if text.lower() in ["s", "salir"]:
            send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
            clear_session(phone)
            return jsonify({"ok": True}), 200

        # === ESTADOS ===
        if info["state"] == "start":
            send_whatsapp_text(phone, get_greeting())
            info["state"] = "awaiting_name"
            sessions[phone] = info
            return jsonify({"ok": True}), 200

        elif info["state"] == "awaiting_name":
            name = text.split(" ")[0].capitalize()
            info["name"] = name
            info["state"] = "menu"
            sessions[phone] = info
            # (acá podrías guardar a Sheets si querés)
            send_whatsapp_text(phone, main_menu(name))
            return jsonify({"ok": True}), 200

        elif info["state"] == "menu":
            choice = text.lower()
            if choice == "1":
                send_whatsapp_text(phone, "📧 Enviá tu CV a: rekar.salud@gmail.com\n¡Gracias por postularte! 🙌")
            elif choice == "2":
                send_whatsapp_text(phone, "✅ Requisitos: título habilitante, matrícula vigente, seguro de mala praxis y monotributo activo.")
            elif choice == "3":
                send_whatsapp_text(phone, "🌐 Visitá nuestra web: https://rekarsalud.blogspot.com/?m=1")
            elif choice == "4":
                send_whatsapp_text(phone, "🗂️ Completá el formulario: [agregar enlace Google Form]")
            elif choice == "5":
                send_whatsapp_text(phone, "🏥 REKAR brinda servicios domiciliarios de kinesiología y enfermería en CABA y GBA.")
            elif choice == "6":
                # activar modo humano (silencio del bot)
                if not info.get("human_notified"):
                    send_whatsapp_text(phone, "🧑‍💼 Un representante fue notificado. Te contactará a la brevedad.")
                    send_telegram_message(f"📞 Nuevo cliente quiere hablar con un representante:\n{info.get('name','Cliente')} (+{phone})")
                    info["human_notified"] = True
                info["state"] = "human_mode"
                info["time"] = time.time()
                sessions[phone] = info
            elif choice == "7":
                send_whatsapp_text(phone, "💬 Activando *RekyBot IA*... Podés hacerme preguntas sobre nuestros servicios, horarios o cómo trabajar con nosotros.")
                info["state"] = "assistant_mode"
                info["time"] = time.time()
                sessions[phone] = info
            elif choice == "8":
                send_whatsapp_text(phone, "¡Gracias por contactarte con REKAR! 👋 Cuando necesites, escribinos de nuevo.")
                clear_session(phone)
                return jsonify({"ok": True}), 200
            else:
                send_whatsapp_text(phone, "No entendí tu respuesta. Enviá el número de la opción o M para menú.")
            return jsonify({"ok": True}), 200

        elif info["state"] == "human_mode":
            # Silencio del bot: solo forward a Telegram
            elapsed = time.time() - info.get("time", 0)
            if elapsed > HUMAN_TTL:
                info["state"] = "menu"
                info["human_notified"] = False
                sessions[phone] = info
                send_whatsapp_text(phone, "⏳ La conversación con el representante finalizó. Escribí 6 para volver a hablar o M para el menú.")
            else:
                send_telegram_message(f"💬 {info.get('name','Cliente')} (+{phone}): {text}")
            return jsonify({"ok": True}), 200

        elif info["state"] == "assistant_mode":
            # Mensaje “procesando”
            send_whatsapp_text(phone, "⏳ Procesando tu pregunta...")
            # Pregunta a Gemini (con timeout y fallback)
            answer = ask_gemini(text, context_hint=f"Cliente: {info.get('name','')}, teléfono: +{phone}")
            if answer:
                answer = (answer.strip() + "\n\n🗂️ Si querés volver al *menú*, escribí M. Para *salir*, S.")
                send_whatsapp_text(phone, answer)
            else:
                # Fallback híbrido
                fallback = (
                    "🤖 Nuestra IA está un poco ocupada, pero te ayudo igual. "
                    "Podés preguntarme sobre nuestros *servicios*, *zonas* (CABA y GBA) o *cómo sumarte al equipo*. \n"
                    "📋 Si querés volver al *menú principal*, escribí M. Para *salir*, S."
                )
                send_whatsapp_text(phone, fallback)
            return jsonify({"ok": True}), 200

    except Exception as e:
        print("⚠️ Error webhook:", e)
        return jsonify({"error": str(e)}), 200

    return jsonify({"ok": True}), 200

# ==============================================
# WEBHOOK TELEGRAM (responder -> WhatsApp)
# ==============================================

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": True}), 200

    msg = data["message"]
    chat_id = str(msg["chat"]["id"])
    if chat_id != TELEGRAM_CHAT_ID:
        # ignorar otros chats
        return jsonify({"ok": True}), 200

    text = msg.get("text", "").strip()

    # /cerrar <numero>
    if text.startswith("/cerrar"):
        try:
            _, phone = text.split(" ", 1)
            clear_session(phone.strip())
            send_telegram_message(f"✅ Sesión cerrada para {phone.strip()}")
        except:
            send_telegram_message("❌ Usa: /cerrar <número>")
        return jsonify({"ok": True}), 200

    # /enviar <numero> <mensaje>  (queda por compatibilidad)
    if text.startswith("/enviar"):
        try:
            _, phone, payload = text.split(" ", 2)
            send_whatsapp_text(phone.strip(), payload)
        except:
            send_telegram_message("❌ Formato: /enviar <número> <mensaje>")
        return jsonify({"ok": True}), 200

    # Si el mensaje de Telegram es RESPUESTA a un mensaje reenviado, extraemos el número
    if "reply_to_message" in msg:
        original = msg["reply_to_message"].get("text", "")
        # El formato que reenviamos es: "💬 Nombre (+549...) : contenido"
        phone = None
        if "(" in original and ")" in original and "+" in original:
            try:
                phone = original.split("(")[1].split(")")[0].replace("+", "").strip()
            except:
                phone = None
        if phone:
            send_whatsapp_text(phone, text)
            send_telegram_message(f"✅ Enviado a +{phone}", reply_to=msg["message_id"])
            # Mantener modo humano activo mientras se conversa
            info = sessions.get(phone, {"state": "human_mode", "time": time.time(), "human_notified": True})
            info["state"] = "human_mode"
            info["time"] = time.time()
            info["human_notified"] = True
            sessions[phone] = info
            return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200

# ==============================================
# RUN
# ==============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
