@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.get_json()
    print("📥 Evento recibido desde Slack:", data)

    # ✅ Slack URL verification (challenge)
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    try:
        event = data.get("event", {})
        subtype = event.get("subtype", "")
        user = event.get("user")
        text = event.get("text", "").strip()

        # Evita loops o mensajes del bot mismo
        if subtype == "bot_message" or user is None:
            return "OK", 200

        # Si empieza con +549 se interpreta como número de WhatsApp
        if text.startswith("+549"):
            partes = text.split(" ", 1)
            if len(partes) == 2:
                numero, mensaje = partes
                enviar_whatsapp(numero, mensaje)
                print(f"✅ Enviado a WhatsApp {numero}: {mensaje}")
            else:
                print("⚠️ Formato incorrecto. Usa: +549XXXXXXXX mensaje")

        # Si el mensaje NO empieza con número, el bot responde pidiendo nombre
        else:
            slack_response = {
                "text": "Por favor, escribí tu número de WhatsApp (con +549...) y tu nombre para registrarte 🙌"
            }
            requests.post(SLACK_WEBHOOK_URL, json=slack_response)
            print("ℹ️ Solicitud de nombre enviada a Slack")

    except Exception as e:
        print("⚠️ Error procesando evento Slack:", e)

    return "OK", 200
