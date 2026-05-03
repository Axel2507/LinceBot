let audioActual = null;
// Obtenemos el contenedor donde se dibujan los chats
const chatBox = document.getElementById("chat-box");

// Función para dibujar los mensajes del usuario
function agregarMensajeUsuario(texto) {
    // Truco: Si el texto es "hola" y el chat está vacío, no lo dibujamos
    // para que parezca que el bot inicia la conversación.
    if (texto === "hola" && chatBox.innerHTML.trim() === "") return;

    const div = document.createElement("div");
    div.className = "mensaje usuario"; // Asegúrate de tener esto en tu CSS
    div.innerText = texto;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll hacia abajo
}

// Función para dibujar los mensajes del LinceBot
function agregarMensajeBot(texto) {
    const div = document.createElement("div");
    div.className = "mensaje lince";
    div.innerHTML = texto;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Función principal para enviar el texto a Python
async function enviarMensaje(texto) {
    agregarMensajeUsuario(texto);
    document.getElementById("contenedor-botones").innerHTML = ""; // Oculta botones viejos

    try {
        const response = await fetch("http://localhost:8000/chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto: texto })
        });

        const data = await response.json();

        // 1. DIBUJAR LAS BURBUJAS (Separando por ||)
        const fragmentos = data.respuesta.split("||");
        fragmentos.forEach((fragmento, index) => {
            setTimeout(() => {
                agregarMensajeBot(fragmento.trim());
            }, index * 800); // Aparecen con 800ms de diferencia
        });

        // 2. DIBUJAR LOS BOTONES DINÁMICOS
        setTimeout(() => {
            if (data.opciones && data.opciones.length > 0) {
                const contenedor = document.getElementById("contenedor-botones");
                data.opciones.forEach(opcion => {
                    const btn = document.createElement("button");
                    btn.className = "btn-flujo"; // Usamos la clase de tus botones originales
                    btn.innerText = opcion;
                    btn.onclick = () => enviarMensaje(opcion);
                    contenedor.appendChild(btn);
                });
            }
        }, fragmentos.length * 800);

        if (data.audio) {
            // 1. Si ya hay un audio sonando, lo pausamos y reiniciamos
            if (audioActual) {
                audioActual.pause();
                audioActual.currentTime = 0;
            }
            // 2. Cargamos el nuevo audio en la variable global y le damos play
            audioActual = new Audio("data:audio/mp3;base64," + data.audio);
            audioActual.play();
        }

    } catch (error) {
        console.error("Error de conexión:", error);
        agregarMensajeBot("Uy, parece que no puedo conectar con mi cerebro en este momento. 🐾");
    }
}

// Nota: A veces las voces tardan un segundo en cargar, este pequeño bloque ayuda a prepararlas
window.speechSynthesis.onvoiceschanged = function() {
    window.speechSynthesis.getVoices();
};