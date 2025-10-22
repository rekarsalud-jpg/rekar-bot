# ==========================================
# 🤖 REKYBOT 1.5.1 – Bidireccional Estable
# ==========================================

import os, time, requests, json
from flask import Flask, request, jsonify

app = Flask(__name__)

# === VARIABLES DE ENTORNO ===
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = os.getenv("GEMINI_URL")

# === VARIABLES INTERNAS ===
sessions = {}
last_messages = {}
HUMAN_TTL = 3600 # 1 hora

# ==============================================
# FUNCIONES BASE
# ==============================================

def send_whatsapp(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        print(f"📤 WhatsApp → {phone}: {text}")
        return r.status_code == 200
    except Exception as e:
        print("⚠️ Error enviando WhatsApp:", e)
        return False


def send_telegram(text, reply_to=None):
    """Envía mensaje al canal de Telegram, opcionalmente como respuesta."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        requests.post(url, json=data)
        print(f"📩 Telegram → {text}")
    except Exception as e:
        print("⚠️ Error enviando Telegram:", e)


def ask_gemini(prompt):
    if not GEMINI_API_KEY or not GEMINI_URL:
        return None
    try:
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                          headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return None
    except requests.Timeout:
        print("⏳ Gemini timeout")
        return None
    except Exception as e:
        print("⚠️ Error Gemini:", e)
        return None


def clear_session(phone):
    sessions.pop(phone, None)
    last_messages.pop(phone, None)
    print(f"🧹 Sesión cerrada para {phone}")


def duplicate(phone, text):
    if last_messages.get(phone) == text:
        return True
    last_messages[phone] = text
    return False


# ==============================================
# TEXTOS BASE
# ==============================================

def greeting():
    return ("👋 ¡Hola! Soy *RekyBot 1.5.1*, asistente virtual de *REKAR* 💚\n"
            "Gracias por contactarte. Atendemos de *lunes a sábado de 9 a 19 hs.*\n\n"
            "¿Cómo es tu nombre?")

def main_menu(name):
    return (f"¡Genial, {name}! 🌟\n"
            "Elegí una opción:\n\n"
            "1️⃣ Enviar tu CV (rekar.salud@gmail.com)\n"
            "2️⃣ Requisitos para trabajar en REKAR\n"
            "3️⃣ Ingresar a la web institucional\n"
            "4️⃣ Completar formulario de base de datos\n"
            "5️⃣ Información sobre REKAR\n"
            "6️⃣ Hablar con un representante humano\n"
            "7️⃣ Chatear con RekyBot (IA Gemini 🤖)\n"
            "8️⃣ Salir ❌\n\n"
            "Escribí *M* para volver al menú o *S* para salir.")


# ==============================================
# WHATSAPP → WEBHOOK
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
        print(f"📥 Mensaje de {phone}: {text}")

        if duplicate(phone, text):
            return jsonify({"ok": True}), 200

        info = sessions.get(phone, {"state": "start", "time": time.time()})

        # Salir
        if text.lower() in ["s","salir"]:
            send_whatsapp(phone, "👋 ¡Gracias por contactarte con REKAR! 💚")
            clear_session(phone)
            return jsonify({"ok": True}), 200

        # Inicio
        if info["state"] == "start":
            send_whatsapp(phone, greeting())
            info["state"]="awaiting_name"
            sessions[phone]=info
            return jsonify({"ok":True}),200

        elif info["state"]=="awaiting_name":
            name = text.split(" ")[0].capitalize()
            info["name"]=name
            send_whatsapp(phone, main_menu(name))
            info["state"]="menu"
            sessions[phone]=info
            send_telegram(f"📞 Nuevo contacto: {name} (+{phone})")
            return jsonify({"ok":True}),200

        # Menú
        elif info["state"]=="menu":
            name = info.get("name","cliente")
            choice = text.lower()

            if choice=="1":
                send_whatsapp(phone,"📧 Enviá tu CV a *rekar.salud@gmail.com* 🙌")
            elif choice=="2":
                send_whatsapp(phone,"✅ Requisitos: Título habilitante, matrícula vigente, monotributo activo y seguro de mala praxis.")
            elif choice=="3":
                send_whatsapp(phone,"🌐 https://rekarsalud.blogspot.com/?m=1")
            elif choice=="4":
                send_whatsapp(phone,"🗂️ Formulario: [colocar enlace]")
            elif choice=="5":
                send_whatsapp(phone,"🏥 Somos *REKAR*, red de kinesiología y enfermería domiciliaria. CABA, Zona Sur y Oeste.")
            elif choice=="6":
                send_whatsapp(phone,"🧑‍💼 Un representante fue notificado, te contactará a la brevedad.")
                send_telegram(f"📲 {name} (+{phone}) quiere hablar con un representante.")
                info["state"]="human_mode"
                info["time"]=time.time()
            elif choice=="7":
                send_whatsapp(phone,"💬 Estás en modo IA Gemini. Escribí tu consulta (espera 10 s).")
                info["state"]="ia"
            elif choice=="8":
                send_whatsapp(phone,"👋 Gracias por contactarte con REKAR. ¡Hasta pronto!")
                clear_session(phone)
                return jsonify({"ok":True}),200
            elif choice in ["m","menu"]:
                send_whatsapp(phone, main_menu(name))
            else:
                send_whatsapp(phone,"No entendí la opción. Escribí el número o M para volver al menú.")
            sessions[phone]=info
            return jsonify({"ok":True}),200

        # Modo humano – Canal directo
        elif info["state"]=="human_mode":
            elapsed = time.time()-info.get("time",0)
            if elapsed < HUMAN_TTL:
                send_telegram(f"💬 {info.get('name','Cliente')} (+{phone}): {text}")
            else:
                send_whatsapp(phone,"⏳ La conversación finalizó. Escribí 6 para contactar de nuevo.")
                info["state"]="menu"
            sessions[phone]=info
            return jsonify({"ok":True}),200

        # Modo IA
        elif info["state"]=="ia":
            send_whatsapp(phone,"⏳ Procesando tu pregunta...")
            ans = ask_gemini(text)
            if not ans:
                send_whatsapp(phone,"🤖 No pude conectarme a la IA. Escribí M para volver al menú.")
            else:
                send_whatsapp(phone,ans)
            return jsonify({"ok":True}),200

    except Exception as e:
        print("⚠️ Error webhook:",e)
        return jsonify({"error":str(e)}),200

    return jsonify({"ok":True}),200


# ==============================================
# TELEGRAM → WEBHOOK
# ==============================================

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok":True}),200

    msg = data["message"]
    text = msg.get("text","").strip()
    reply = msg.get("reply_to_message")

    # Responder directo Telegram → WhatsApp
    if reply and "💬" in reply.get("text",""):
        try:
            phone = reply["text"].split("(+")[1].split(")")[0]
            send_whatsapp(phone,text)
            print(f"🔁 Telegram respuesta → {phone}")
        except Exception as e:
            print("⚠️ Error reenvío directo:", e)
        return jsonify({"ok":True}),200

    # Comandos manuales
    if text.startswith("/cerrar"):
        parts = text.split(" ",1)
        if len(parts)==2:
            phone = parts[1].strip()
            clear_session(phone)
            send_telegram(f"✅ Sesión cerrada manual para {phone}")
    elif text.startswith("/enviar"):
        try:
            _,phone,message = text.split(" ",2)
            send_whatsapp(phone,message)
        except:
            send_telegram("❌ Formato: /enviar <número> <mensaje>")

    return jsonify({"ok":True}),200


# ==============================================
# RUN
# ==============================================

if __name__=="__main__":
    port=int(os.getenv("PORT",10000))
    app.run(host="0.0.0.0",port=port)
