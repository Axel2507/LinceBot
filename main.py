from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts
import tempfile
import os
import base64
import re
import ollama
import mysql.connector
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

estado_conversacion = {
    "paso_actual": "inicio",
    "datos_usuario": {}
}


class MensajeUsuario(BaseModel):
    texto: str


# =========================================================
# FUNCIÓN PARA GUARDAR EN MYSQL (CON RELACIÓN DE TABLAS)
# =========================================================
def guardar_en_mysql(datos):
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="blaky2507",
            database="lincebot",
            port=3307
        )
        cursor = conexion.cursor()

        # 1. Obtenemos la fecha exacta
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 2. DICCIONARIO TRADUCTOR: Convierte el texto del chat al ID de tu tabla 'carreras'
        # ¡OJO! Verifica que estos números coincidan con tu tabla carreras en phpMyAdmin
        diccionario_carreras = {
            "sistemas": 1,
            "bioquímica": 3,
            "mecatrónica": 4,
            "industrial": 5,
            "electromecánica": 2,
            "gastronomía": 6,
            "maestria en ingenieria": 7,
            "maestria en inteligencia artificial": 8,
            "aún no lo sé": None  # Si no sabe, lo dejamos vacío (NULL en MySQL)
        }

        # Leemos lo que escribió el usuario (en minúsculas para evitar errores)
        carrera_texto = datos.get("carrera", "").lower()

        # Buscamos el número de ID. Si escribe algo raro, guardamos None (NULL)
        id_carrera = diccionario_carreras.get(carrera_texto, None)

        # 3. Guardamos en la base de datos (ahora sí, pasando el número de ID)
        sql = "INSERT INTO prospectos (nombre_completo, correo, bachillerato_origen, id_carrera_interes, fecha_registro) VALUES (%s, %s, %s, %s, %s)"

        # Pasamos id_carrera en lugar del texto
        valores = (datos.get("nombre"), datos.get("correo"), datos.get("prepa"), id_carrera, fecha_actual)

        cursor.execute(sql, valores)
        conexion.commit()
        cursor.close()
        conexion.close()
        print(f"✅ Alumno {datos.get('nombre')} guardado exitosamente en BD con ID de carrera: {id_carrera}")
    except Exception as e:
        print(f"❌ Error al guardar en MySQL: {e}")


# =========================================================
# FUNCIÓN PARA GENERAR LA VOZ NEURONAL (IA)
# =========================================================
async def generar_audio_neuronal(texto):
    voz = "es-MX-JorgeNeural"  # Voz masculina joven (El Lince)
    comunicate = edge_tts.Communicate(texto, voz)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        ruta_temporal = fp.name

    await comunicate.save(ruta_temporal)

    with open(ruta_temporal, "rb") as archivo_audio:
        audio_base64 = base64.b64encode(archivo_audio.read()).decode('utf-8')

    os.remove(ruta_temporal)
    return audio_base64


# =========================================================
# EL CEREBRO PRINCIPAL DEL CHATBOT
# =========================================================
@app.post("/chat/")
async def procesar_chat(mensaje: MensajeUsuario):
    global estado_conversacion
    texto = mensaje.texto.lower().strip()

    respuesta_texto = ""
    opciones_lista = []



    # ---------------------------------------------------------
    # BLOQUE 1: MODO REGISTRO (Flujo 6 del PDF)
    # ---------------------------------------------------------
    if estado_conversacion["paso_actual"] == "pidiendo_nombre":
        estado_conversacion["datos_usuario"]["nombre"] = mensaje.texto
        estado_conversacion["paso_actual"] = "pidiendo_correo"
        respuesta_texto = f"¡Mucho gusto, {mensaje.texto}! ¿Me proporcionas tu correo electrónico?"
        opciones_lista = []

    elif estado_conversacion["paso_actual"] == "pidiendo_correo":
        estado_conversacion["datos_usuario"]["correo"] = mensaje.texto
        estado_conversacion["paso_actual"] = "pidiendo_prepa"
        respuesta_texto = "¡Anotado! Ahora dime, ¿De qué bachillerato o preparatoria nos visitas?"
        opciones_lista = []

    elif estado_conversacion["paso_actual"] == "pidiendo_prepa":
        estado_conversacion["datos_usuario"]["prepa"] = mensaje.texto
        estado_conversacion["paso_actual"] = "pidiendo_carrera"
        respuesta_texto = "Perfecto. Y por último, ¿A qué carrera te gustaría ingresar?"
        opciones_lista = ["Sistemas", "Bioquímica", "Mecatrónica", "Industrial", "Electromecánica", "Gastronomía",
                          "Aún no lo sé"]

    elif estado_conversacion["paso_actual"] == "pidiendo_carrera":
        estado_conversacion["datos_usuario"]["carrera"] = mensaje.texto

        # ¡AQUÍ GUARDAMOS EN LA BASE DE DATOS!
        guardar_en_mysql(estado_conversacion["datos_usuario"])

        estado_conversacion["paso_actual"] = "inicio"
        respuesta_texto = "¡Excelente! Tus datos han sido guardados. 🐾||Aquí tienes los pasos exactos para tu inscripción:||1. Ve a <a href='https://rl.puebla.gob.mx' target='_blank' style='color: #0000EE; font-weight: bold; text-decoration: underline;'>rl.puebla.gob.mx</a>||2. En 'Educación' busca FICHA DE ADMISIÓN ($885.00) y CURSO PROPEDÉUTICO ($755.00).||3. Paga y registra tus datos.||📍 O visítanos en: Prolongación Heliotropo No. 1201, Atlixco.||📞 WhatsApp: 244 120 90 50."
        opciones_lista = ["🎯 Volver al menú principal"]

    # ---------------------------------------------------------
    # BLOQUE 2: MENÚ PRINCIPAL Y FLUJOS FIJOS
    # ---------------------------------------------------------
    elif texto in ["hola", "inicio", "menú", "volver al menú principal", "🎯 volver al menú principal", ""]:
        respuesta_texto = "¡Hola! soy LinceBot tu asistente de admisiones del Instituto Tecnológico del ITSA.||Estoy aquí para ayudarte con todo lo que necesitas saber sobre nuestras carreras y nuestro proceso de inscripción.||¿Qué te gustaría saber?"
        opciones_lista = ["1️⃣ Información sobre las carreras", "2️⃣ Requisitos y fechas de admisión",
                          "3️⃣ Costos del proceso", "4️⃣ Modalidades de estudio", "5️⃣ Cursos de idiomas",
                          "6️⃣ Registro como aspirante", "7️⃣ Pregunta libre"]

    elif "1️⃣" in texto or "información sobre las carreras" in texto:
        respuesta_texto = "Actualmente contamos con las siguientes carreras:||• Ingenierías: Sistemas Computacionales, Bioquímica, Mecatrónica, Industrial, Electromecánica.||• Licenciatura: Gastronomía.||• Posgrados: Maestría en Ingeniería, Maestría en Inteligencia Artificial.||¿De cuál carrera te gustaría recibir más información?"
        opciones_lista = ["Sistemas Computacionales", "Bioquímica", "Mecatrónica", "Industrial", "Electromecánica",
                          "Gastronomía", "Maestrías", "6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif any(carrera in texto for carrera in
             ["sistemas", "bioquímica", "mecatrónica", "industrial", "electromecánica", "gastronomía", "maestrías"]):
        respuesta_texto = "Aquí te comparto información completa sobre la carrera.||Plan de estudios, campo laboral y material multimedia para que la conozcas a fondo, incluso los logros que han realizado para que te sientas motivado(a) 😉.||¿Qué más quieres saber?"
        opciones_lista = ["Perfil de ingreso", "Oportunidades laborales", "6️⃣ Registro como aspirante",
                          "🎯 Volver al menú principal"]

    elif "perfil de ingreso" in texto:
        respuesta_texto = "El perfil de ingreso busca aspirantes con interés en las ciencias exactas, proactividad y disposición para el trabajo en equipo (puedes consultar el detalle exacto de tu carrera en nuestra web). ¿Tienes alguna otra duda?"
        opciones_lista = ["Oportunidades laborales", "6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif "oportunidades laborales" in texto:
        respuesta_texto = "Nuestros egresados tienen un alto índice de empleabilidad en la región y a nivel nacional, abarcando sectores industriales, tecnológicos, empresariales y de servicios. ¿Tienes otra duda?"
        opciones_lista = ["Perfil de ingreso", "6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif "2️⃣" in texto or "requisitos y fechas" in texto:
        respuesta_texto = "📅 Fechas Ronda 1:||• Solicitud de ficha: 9 feb al 22 abr.||• Examen: 24 abr.||• Resultados: 27 abr.||• Propedéutico: 27 jul al 14 ago.||• Clases: 24 ago.||📝 Requisitos:||Acta de Nacimiento, CURP, Identificación, Constancia de procedencia, Comprobante de domicilio y Comprobante fiscal de pago. ¿Tienes otra duda?"
        opciones_lista = ["6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif "3️⃣" in texto or "costos" in texto:
        respuesta_texto = "💰 Estos son los costos del proceso de ingreso:||• Ficha de admisión: $885.00 MXN||• Curso Propedéutico: $755.00 MXN||• Inscripción: $1,430.00 MXN||Nota: Tanto en modalidad normal como virtual, la inscripción tiene el mismo costo. ¿Te puedo ayudar con algo más?"
        opciones_lista = ["6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif "4️⃣" in texto or "modalidades" in texto:
        respuesta_texto = "🏢 Modalidad Mixta (Sabatina): Cursas materias principalmente los sábados. Aplica para Ing. Industrial, Sistemas o Mecatrónica.||💻 Modalidad Virtual / A Distancia: A través del aula virtual Moodle. Aplica para Ing. Industrial, Gestión Empresarial, Sistemas Computacionales y Maestría en IA. ¿Tienes otra duda?"
        opciones_lista = ["6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif "5️⃣" in texto or "idiomas" in texto:
        respuesta_texto = "🗣️ Contamos con Inglés y Francés:||• Curso de inglés/francés (Presencial o Línea): $1,040.00 por nivel.||• Curso de Inglés Intensivo: $2,080.00.||• Plataforma Digital (Sonhos): $555.00.||El pago se hace igual en el buscador de puebla buscando el curso al que se pagará. ¿Tienes otra duda?"
        opciones_lista = ["6️⃣ Registro como aspirante", "🎯 Volver al menú principal"]

    elif "6️⃣" in texto or "registro" in texto:
        estado_conversacion["paso_actual"] = "pidiendo_nombre"
        respuesta_texto = "¡Excelente decisión! Vamos a comenzar tu pre-registro. Por favor, escribe tu NOMBRE COMPLETO:"
        opciones_lista = []

    # ---------------------------------------------------------
    # BLOQUE 3: LA MAGIA DE LA IA (LLAMA 3)
    # ---------------------------------------------------------
    else:
        # Instrucciones estrictas para Llama 3
        prompt_sistema = """Eres LinceBot, la mascota y asistente virtual del Instituto Tecnológico Superior de Atlixco (ITSA).
        Tu tono debe ser súper amigable, universitario y directo. 
        Misión 1: Responde la duda del aspirante con la información que sepas.
        Misión 2: Si te preguntan algo específico que no sepas, NO INVENTES NADA. Responde exactamente esto: 
        "¡Esa es una pregunta muy interesante! Para darte la información oficial más exacta, te recomiendo enviar un mensaje de WhatsApp directo a nuestro Jefe de Departamento de Admisiones al número 244 120 90 50."
        """

        try:
            # Llamamos a Ollama (Asegúrate de tener la aplicación Ollama corriendo en tu PC)
            respuesta_ia = ollama.chat(model='llama3', messages=[
                {'role': 'system', 'content': prompt_sistema},
                {'role': 'user', 'content': texto}
            ])
            # Extraemos lo que contestó la IA
            respuesta_texto = respuesta_ia['message']['content']

        except Exception as e:
            # Si Ollama está apagado, damos la respuesta de emergencia que querías
            print("Error con Ollama:", e)
            respuesta_texto = "Esa es una pregunta muy interesante, pero en este momento mi sistema está saturado. Para darte la información oficial, te pido que envíes un WhatsApp a nuestro Jefe de Departamento al 244 120 90 50. ¡Te atenderán con gusto!"

        opciones_lista = ["🎯 Volver al menú principal", "6️⃣ Registro como aspirante"]

    # =========================================================
    # GENERACIÓN DE AUDIO Y ENVÍO FINAL AL NAVEGADOR
    # =========================================================
    try:
        texto_para_hablar = respuesta_texto.replace("||", ". ")
        texto_para_hablar = re.sub(r'<[^>]+>', '', texto_para_hablar)

        audio_b64 = await generar_audio_neuronal(texto_para_hablar)

        return {
            "respuesta": respuesta_texto,
            "opciones": opciones_lista,
            "audio": audio_b64
        }
    except Exception as e:
        print(f"Error generando audio: {e}")
        return {
            "respuesta": respuesta_texto,
            "opciones": opciones_lista,
            "audio": None
        }



