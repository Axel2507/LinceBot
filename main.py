from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts
import tempfile
import os
import base64
import re
import mysql.connector
from datetime import datetime
from groq import Groq
import os
from dotenv import load_dotenv




def es_nombre_valido(nombre):
    return len(nombre) >= 3 and not nombre.isdigit()

def es_edad_valida(edad):
    return edad.isdigit() and 14 <= int(edad) <= 60

def es_telefono_valido(telefono):
    tel_limpio = telefono.replace(" ", "")
    return bool(re.match(r"^\d{10}$", tel_limpio))

def es_correo_valido(correo):
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", correo))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Groq (Sustituye por tu API Key gratuita de console.groq.com)
load_dotenv()
client = Groq(api_key = os.getenv("GROQ_API_KEY"))

estado_conversacion = {
    "paso_actual": "pidiendo_nombre", # Empezamos el embudo aquí
    "datos_usuario": {}
}


class MensajeUsuario(BaseModel):
    texto: str


# Diccionario de carreras (Se queda igual, es eficiente)
info_carreras = {
    "electromecanica": {
        "nombre": "Ingeniería Electromecánica",
        "duracion": "9 semestres",
        "especialidad": "Automatización industrial",
        "perfil": "Ideal si tienes creatividad e interés por la aplicación de la ciencia y la tecnología.",
        "campo_laboral": "Audi, Volkswagen, CFE, Pemex o el Clúster energético de Puebla.",
        "plan_estudios": "https://atlixco.tecnm.mx/ingenieria/Electromec%C3%A1nica"
    },
    "sistemas": {
        "nombre": "Ingeniería en Sistemas Computacionales",
        "duracion": "9 Semestres",
        "especialidad": "Ingeniería de Software",
        "perfil": "Interés por el uso de computadoras y razonamiento lógico.",
        "campo_laboral": "Desarrollo de software, sitios web, bases de datos e IoT.",
        "plan_estudios": "https://atlixco.tecnm.mx/ingenieria/Sistemas-Computacionales"
    },
    "gastronomia": {
        "nombre": "Licenciatura en Gastronomía",
        "duracion": "9 Semestres",
        "especialidad": "Cocina mexicana",
        "perfil": "Creatividad, sensibilidad artística y espíritu innovador.",
        "campo_laboral": "Restaurantes, hoteles, cruceros o emprendimiento propio.",
        "plan_estudios": "https://atlixco.tecnm.mx/ingenieria/Gastronomia"
    },
    "bioquimica": {
        "nombre": "Ingeniería Bioquímica",
        "duracion": "9 Semestres",
        "especialidad": "Alimentos",
        "perfil": "Competencias en Matemáticas y Ciencias Experimentales.",
        "campo_laboral": "Industrias de alimentos y biotecnología (Bimbo, Coca Cola).",
        "plan_estudios": "https://atlixco.tecnm.mx/ingenieria/Bioquimica"
    },
    "industrial": {
        "nombre": "Ingeniería Industrial",
        "duracion": "9 Semestres",
        "especialidad": "Calidad y productividad",
        "perfil": "Interés por la aplicación de la ciencia para optimizar procesos.",
        "campo_laboral": "Sectores manufactureros, logística y consultoría.",
        "plan_estudios": "https://atlixco.tecnm.mx/ingenieria/Industrial"
    },
    "mecatronica": {
        "nombre": "Ingeniería Mecatrónica",
        "duracion": "9 Semestres",
        "especialidad": "Automatización de procesos",
        "perfil": "Interés por robótica, programación y diseño.",
        "campo_laboral": "Industria automotriz, aeroespacial y robótica.",
        "plan_estudios": "https://atlixco.tecnm.mx/ingenieria/Mecatronica"
    }
}


async def generar_audio_neuronal(texto):
    voz = "es-MX-JorgeNeural"
    comunicate = edge_tts.Communicate(texto, voz)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        ruta_temporal = fp.name
    await comunicate.save(ruta_temporal)
    with open(ruta_temporal, "rb") as archivo_audio:
        audio_base64 = base64.b64encode(archivo_audio.read()).decode('utf-8')
    os.remove(ruta_temporal)
    return audio_base64


def validar_y_obtener_bachillerato(nombre_usuario, cliente_groq):
    try:
        conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507", database="itsabot")
        cursor = conexion.cursor()

        # 1. Sacamos la lista de bachilleratos que YA tienes en tu base de datos
        cursor.execute("SELECT id, nombre FROM bachilleratos")
        escuelas_db = cursor.fetchall()
        lista_nombres = [escuela[1] for escuela in escuelas_db]
        diccionario_escuelas = {escuela[1]: escuela[0] for escuela in escuelas_db}  # Para encontrar el ID rápido

        # 2. Le damos instrucciones súper estrictas a la IA
        prompt = f"""
        Eres un validador estricto de escuelas de nivel medio superior (bachilleratos/preparatorias) en México.
        Lista de escuelas ya registradas en nuestra base de datos: {lista_nombres}

        Escuela escrita por el usuario: "{nombre_usuario}"

        Reglas:
        1. Si lo que escribió el usuario es una variación, sinónimo, acrónimo o está mal escrito pero claramente se refiere a una escuela de la lista (ej. "cecyte 5" = "CECyTE 5", o "centro de bachillerato 16" = "CBTis 16"), responde SOLAMENTE con: EXISTE:|Nombre exacto de la lista
        2. Si NO está en la lista, analiza si es un bachillerato real (especialmente en Puebla o México). Si es real, corrige su ortografía y responde SOLAMENTE con: NUEVA:|Nombre formal corregido
        3. Si el usuario escribió groserías, letras al azar (ej. "asdf"), un preescolar, o algo que claramente no es una escuela, responde SOLAMENTE con: FALSA

        No des saludos ni explicaciones, solo la respuesta con ese formato.
        """

        # 3. Le preguntamos a Groq (usamos temperature=0.1 para que no sea creativo, sino analítico)
        chat_completion = cliente_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.1
        )
        respuesta_ai = chat_completion.choices[0].message.content.strip()

        # 4. Procesamos la decisión de la IA
        if respuesta_ai.startswith("EXISTE:|"):
            nombre_db = respuesta_ai.split("|")[1].strip()
            if nombre_db in diccionario_escuelas:
                print(f"🤖 IA vinculó '{nombre_usuario}' con '{nombre_db}'")
                return diccionario_escuelas[nombre_db]  # Devolvemos el ID existente

        elif respuesta_ai.startswith("NUEVA:|"):
            nombre_nuevo = respuesta_ai.split("|")[1].strip()
            # Como es nueva y real, la guardamos en el catálogo para el futuro
            cursor.execute("INSERT INTO bachilleratos (nombre) VALUES (%s)", (nombre_nuevo,))
            conexion.commit()
            print(f"🤖 IA detectó y agregó escuela nueva: '{nombre_nuevo}'")
            return cursor.lastrowid

        # Si la IA respondió "FALSA" o no cumplió el formato, lo rebotamos
        print(f"🤖 IA rechazó la escuela: '{nombre_usuario}'")
        return None

    except Exception as e:
        print(f"❌ Error en IA Bachillerato: {e}")
        return None
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conexion' in locals(): conexion.close()


def obtener_id_carrera(nombre_buscado):
    try:
        conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507", database="itsabot")
        cursor = conexion.cursor()
        # Buscamos la carrera que coincida con lo que escribió el usuario
        cursor.execute("SELECT id FROM carreras WHERE nombre LIKE %s", (f"%{nombre_buscado}%",))
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Error Carrera: {e}")
        return None

@app.post("/chat/")
async def procesar_chat(mensaje: MensajeUsuario):
        global estado_conversacion
        texto = mensaje.texto.lower().strip()
        respuesta_texto = ""
        opciones_lista = []

        # --- FLUJO DE REGISTRO EXTENDIDO ---
        if estado_conversacion["paso_actual"] == "pidiendo_nombre":
            # (Se mantiene igual que el anterior...)
            if texto in ["hola", "inicio"]:
                respuesta_texto = "¡Hola! Soy ItsaBot. 🌟 ¿Me podrías decir tu nombre completo?"
            elif es_nombre_valido(texto):
                estado_conversacion["datos_usuario"]["nombre"] = mensaje.texto.title()
                estado_conversacion["paso_actual"] = "pidiendo_edad"
                respuesta_texto = f"¡Mucho gusto, {mensaje.texto.title()}! 🤝 ¿Qué edad tienes?"
            else:
                respuesta_texto = "Por favor, escribe un nombre válido."

        elif estado_conversacion["paso_actual"] == "pidiendo_edad":
            if es_edad_valida(texto):
                estado_conversacion["datos_usuario"]["edad"] = int(texto)
                estado_conversacion["paso_actual"] = "pidiendo_telefono"
                respuesta_texto = "¡Súper! 🚀 ¿Cuál es tu número de teléfono a 10 dígitos?"
            else:
                respuesta_texto = "Escribe solo tu edad en números (ejemplo: 17)."

        elif estado_conversacion["paso_actual"] == "pidiendo_telefono":
            if es_telefono_valido(texto):
                estado_conversacion["datos_usuario"]["telefono"] = texto
                estado_conversacion["paso_actual"] = "pidiendo_correo"
                respuesta_texto = "¡Anotado! 📱 Ahora, ¿cuál es tu correo electrónico?"
            else:
                respuesta_texto = "Escribe un número a 10 dígitos (ejemplo: 2441234567)."

        elif estado_conversacion["paso_actual"] == "pidiendo_correo":
            if es_correo_valido(texto):
                estado_conversacion["datos_usuario"]["correo"] = texto
                estado_conversacion["paso_actual"] = "pidiendo_bachillerato"
                respuesta_texto = "¡Gracias! 📧 ¿De qué bachillerato o preparatoria vienes?"
            else:
                respuesta_texto = "Escribe un correo válido (ejemplo: usuario@gmail.com)."

        elif estado_conversacion["paso_actual"] == "pidiendo_bachillerato":
            # Llamamos a nuestra nueva súper-función con IA, pasándole el cliente de Groq
            id_bach = validar_y_obtener_bachillerato(texto, client)

            if id_bach:  # Si la IA nos devolvió un ID (ya sea existente o nuevo)
                estado_conversacion["datos_usuario"]["id_bachillerato"] = id_bach
                estado_conversacion["paso_actual"] = "pidiendo_carrera"
                respuesta_texto = "¡Excelente escuela! 🏫 Por último, ¿qué carrera te interesa estudiar?"
                opciones_lista = ["Sistemas", "Mecatrónica", "Industrial", "Bioquímica", "Electromecánica",
                                  "Gastronomía"]
            else:
                # Si la IA dijo que es falsa o no tiene sentido
                respuesta_texto = "Hmm, no logré reconocer esa preparatoria o bachillerato. 🤔 ¿Podrías escribir el nombre completo o las siglas correctas de tu escuela, por favor?"

        elif estado_conversacion["paso_actual"] == "pidiendo_carrera":
            id_car = obtener_id_carrera(texto)
            if id_car:
                estado_conversacion["datos_usuario"]["id_carrera"] = id_car
                # ¡AHORA SÍ GUARDAMOS CON TODOS LOS DATOS!
                guardar_en_mysql(estado_conversacion["datos_usuario"])
                estado_conversacion["paso_actual"] = "menu_libre"
                respuesta_texto = "¡Registro completo! 🎉 Ya eres parte de nuestros aspirantes. ¿En qué más puedo ayudarte hoy?"
                opciones_lista = ["1️⃣ Información de carreras", "2️⃣ Costos"]
            else:
                respuesta_texto = "Lo siento, actualmente no contamos con esa carrera. 😅 ¿Te interesa alguna de estas?"
                opciones_lista = ["Sistemas", "Mecatrónica", "Industrial", "Bioquímica", "Electromecánica",
                                  "Gastronomía"]

    # ==========================================
    # 2. ZONA LIBRE (El usuario ya nos dio sus datos)
    # ==========================================
        elif estado_conversacion["paso_actual"] == "menu_libre":

            # Volver al menú
            if texto in ["🎯 menú principal", "inicio", "menú"]:
                respuesta_texto = "¿En qué más puedo ayudarte hoy?"
                opciones_lista = ["1️⃣ Información de carreras", "2️⃣ Fechas de admisión", "3️⃣ Costos"]

            # Menú de carreras
            elif "1️⃣" in texto or "carreras" in texto:
                respuesta_texto = "Contamos con:||• Ingenierías: Sistemas, Bioquímica, Mecatrónica, Industrial, Electromecánica.||• Licenciatura: Gastronomía.||¿De cuál deseas detalles?"
                opciones_lista = ["Sistemas", "Bioquímica", "Mecatrónica", "Industrial", "Electromecánica", "Gastronomía",
                                  "🎯 Menú principal"]

            # DETALLE DE CARRERAS (DINÁMICO - Tu lógica intacta)
            elif any(c in texto for c in
                     ["sistemas", "bioquímica", "mecatrónica", "industrial", "electromecánica", "gastronomía"]):
                c_clave = ""
                if "sistemas" in texto:
                    c_clave = "sistemas"
                elif "bioquímica" in texto or "bioquimica" in texto:
                    c_clave = "bioquimica"
                elif "mecatrónica" in texto or "mecatronica" in texto:
                    c_clave = "mecatronica"
                elif "industrial" in texto:
                    c_clave = "industrial"
                elif "electromecánica" in texto or "electromecanica" in texto:
                    c_clave = "electromecanica"
                elif "gastronomía" in texto or "gastronomia" in texto:
                    c_clave = "gastronomia"

                info = info_carreras[c_clave]
                respuesta_texto = f"La {info['nombre']} tiene una duración de {info['duracion']} con especialidad en {info['especialidad']}.||🎯 Perfil: {info['perfil']}||💼 Campo Laboral: {info['campo_laboral']}||🔗 <a href='{info['plan_estudios']}' target='_blank'>Ver plan de estudios</a>"
                opciones_lista = ["🎯 Menú principal"]

            # PREGUNTA LIBRE (USANDO LA API DE GROQ CON LABIA)
                # PREGUNTA LIBRE (USANDO LA API DE GROQ CON LABIA)
            else:
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system",
                             "content": "Eres ItsaBot, un asistente de admisiones del ITSA. Tienes una personalidad carismática, alegre y servicial. Usa emojis para expresarte. Si no sabes algo, dirige amablemente al WhatsApp 244 120 90 50."},
                            {"role": "user", "content": texto},
                        ],
                        model="llama3-8b-8192",
                    )
                    respuesta_texto = chat_completion.choices[0].message.content
                except Exception as e:
                    # 👉 ESTA ES LA LÍNEA NUEVA: Imprimirá en tu terminal por qué falló Groq
                    print(f"❌ ERROR DE GROQ: {e}")

                    respuesta_texto = "Ay, caray. 😅 Tuve un problema técnico momentáneo. Por favor contacta a admisiones al 244 120 90 50."
                opciones_lista = ["🎯 Menú principal"]


        # ==========================================
        # 3. GENERAR AUDIO Y RESPUESTA FINAL HTML
        # ==========================================
        try:
            # Quitamos etiquetas HTML y reemplazamos los '||' por puntos para que la voz haga pausas
            t_hablar = re.sub(r'<[^>]+>', '', respuesta_texto.replace("||", ". "))
            audio_b64 = await generar_audio_neuronal(t_hablar)

            # Enviamos la respuesta cambiando '||' por <br><br> para que se vea bonito en pantalla
            return {
                "respuesta": respuesta_texto.replace("||", "<br><br>"),
                "opciones": opciones_lista,
                "audio": audio_b64
            }
        except:
            return {
                "respuesta": respuesta_texto.replace("||", "<br><br>"),
                "opciones": opciones_lista,
                "audio": None
            }


def guardar_en_mysql(datos):
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="blaky2507",
            database="itsabot"
        )
        cursor = conexion.cursor()

        sql = """INSERT INTO prospectos 
                 (nombre_completo, correo, telefono, edad, id_bachillerato, id_carrera_interes, canal) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""

        valores = (
            datos.get("nombre"),
            datos.get("correo"),
            datos.get("telefono"),
            datos.get("edad"),
            datos.get("id_bachillerato"),  # ID obtenido de la BD
            datos.get("id_carrera"),  # ID obtenido de la BD
            "chatbot"
        )

        cursor.execute(sql, valores)
        conexion.commit()
        cursor.close()
        conexion.close()
        print("✅ Registro guardado con éxito en la base de datos.")
    except Exception as e:
        print(f"❌ Error crítico al guardar: {e}")