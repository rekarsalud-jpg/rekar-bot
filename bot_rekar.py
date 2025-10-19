from flask import Flask, request
import requests
import os

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

@app.route('/')
def home():
    return "RekarBot está activo ✅"

# Validación del webhook
@app.route('/webhook', methods=['GET'])
def verify():
    verify_token = VERIFY_TOKEN
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == verify_token:
            print("✅ Webhook verificado correctamente.")
            return challenge, 200
        else:
            return "Token inválido", 403
    return "Faltan parámetros", 400

# Recepción de mensajes
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_number = message["from"]
        text = message["text"]["body"].lower()

        # Respuesta simple
        send_message(phone_number, """*Hola 👋 soy RekarBot*, tu asistente automático. 
Por el momento este medio estará *fuera de servicio*.

📧 Podés comunicarte por email: rekar.salud@gmail.com""")
    except Exception as e:
        print("⚠️ Error al procesar el mensaje:", e)

    return "OK", 200


def send_message(to, message):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviado:", response.text)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


