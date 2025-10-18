// === REKAR BOT v2 ===
// Bot oficial de WhatsApp REKAR Salud
// Compatible con Meta Graph API v21 + Render Hosting

import express from "express";
import bodyParser from "body-parser";
import fetch from "node-fetch";

const app = express();
app.use(bodyParser.json());

// 🧠 Variables de entorno (Render)
const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const ACCESS_TOKEN = process.env.ACCESS_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;

// ✅ Ruta de verificación del webhook
app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode && token === VERIFY_TOKEN) {
    console.log("🟢 Webhook verificado correctamente");
    res.status(200).send(challenge);
  } else {
    console.log("❌ Error de verificación");
    res.status(403).send("Error de verificación");
  }
});

// 📩 Ruta para recibir mensajes de WhatsApp
app.post("/webhook", async (req, res) => {
  try {
    const data = req.body;

    if (data.object === "whatsapp_business_account") {
      const entry = data.entry?.[0];
      const changes = entry?.changes?.[0];
      const messages = changes?.value?.messages;

      if (messages && messages[0]) {
        const message = messages[0];
        const from = message.from; // número del usuario
        const text = message.text?.body || "";

        console.log("📩 Mensaje recibido:", text);

        // 💬 Respuesta automática personalizada
        const reply = `
Hola 👋, soy el asistente automático de *REKAR Salud*.
Recibí tu mensaje: "${text}".
En breve uno de nuestros operadores se comunicará con vos.
Horario de atención: Lunes a Sábado de 9 a 19 hs.`;

        await sendMessage(from, reply);
      }
    }

    res.sendStatus(200);
  } catch (err) {
    console.error("❌ Error al procesar mensaje:", err);
    res.sendStatus(500);
  }
});

// 🧠 Función para enviar mensajes
async function sendMessage(to, message) {
  const url = `https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages`;

  const body = {
    messaging_product: "whatsapp",
    to,
    type: "text",
    text: { body: message },
  };

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${ACCESS_TOKEN}`,
  };

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("❌ Error al enviar mensaje:", errorText);
  } else {
    console.log(`✅ Respuesta enviada correctamente a ${to}`);
  }
}

// 🚀 Servidor en Render
app.listen(10000, () => {
  console.log("🚀 REKAR BOT corriendo en puerto 10000");
});
