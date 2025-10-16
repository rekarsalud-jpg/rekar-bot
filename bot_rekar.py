from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return "REKAR Bot activo ✅"

@app.route("/bot", methods=["GET"])
def bot():
    now = datetime.now()
    day = now.weekday()
    hour = now.hour

    if day in range(0, 6) and 9 <= hour < 19:
        msg = (
            "👋 ¡Hola! Gracias por comunicarte con *REKAR*.\n"
            "Por favor seleccioná una opción:\n"
            "1️⃣ Profesional de la salud\n"
            "2️⃣ Paciente\n"
            "3️⃣ Obra social o entidad\n\n"
            "En breve uno de nuestros operadores se comunicará con usted."
        )
    else:
        msg = (
            "🌙 ¡Hola! Gracias por comunicarte con *REKAR*.\n"
            "Nuestro horario de atención es de *lunes a sábado de 9:00 a 19:00 hs*.\n"
            "Podés dejar tu mensaje y te responderemos a la brevedad.\n\n"
            "💙 REKAR – Atención y rehabilitación domiciliaria"
        )
    return msg

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

