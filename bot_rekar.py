@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json(force=True, silent=True)
    print("📩 EVENTO COMPLETO RECIBIDO:")
    print(data)

    if not data:
        print("⚠️ No se recibió JSON válido")
        return "EVENT_RECEIVED", 200

    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            message = messages[0]
            from_number = message.get("from")
            msg_body = message.get("text", {}).get("body", "")
            print(f"🧾 MENSAJE DETECTADO — De: {from_number} | Texto: {msg_body}")

            # Preparar respuesta automática
            url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": "text",
                "text": {"body": f"Hola 👋 soy RekarBot. Recibí tu mensaje: '{msg_body}'."}
            }

            response = requests.post(url, headers=headers, json=payload)
            print(f"➡️ RESPUESTA ENVIADA — Código {response.status_code}")
            print(response.text)
        else:
            print("⚠️ No hay mensajes en la estructura recibida.")
    except Exception as e:
        print(f"❌ ERROR procesando el webhook: {e}")

    return "EVENT_RECEIVED", 200
