from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts
import tempfile
import base64
import re
import mysql.connector
from groq import Groq
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
from fastapi.staticfiles import StaticFiles
import hashlib


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


# Ahora es un diccionario que guardará a TODOS los usuarios separados por su IP
sesiones_usuarios = {}

def obtener_sesion(ip_usuario):
    # Si es la primera vez que esta IP escribe, le creamos su expediente en blanco
    if ip_usuario not in sesiones_usuarios:
        sesiones_usuarios[ip_usuario] = {
            "paso_actual": "saludo_inicial",
            "datos_usuario": {},
            "codigo_verificacion": None
        }
    return sesiones_usuarios[ip_usuario]

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
        conexion = get_db_connection()
        if not conexion: return {}
        cursor = conexion.cursor()

        # Sacamos las escuelas de la BD
        cursor.execute("SELECT id, nombre FROM bachilleratos")
        escuelas_db = cursor.fetchall()

        # Diccionario para buscar rápido ignorando mayúsculas
        diccionario_escuelas = {nombre.lower(): id_bach for id_bach, nombre in escuelas_db}
        nombres_db_str = "\n".join([f"- {nombre}" for id_bach, nombre in escuelas_db])

        prompt = f"""
        Actúa como un validador de escuelas preparatorias de México.
        El usuario ingresó: "{nombre_usuario}"

        Tengo esta lista de escuelas oficiales en mi base de datos:
        {nombres_db_str}

        REGLAS DE BÚSQUEDA:
        1. Analiza si lo que escribió el usuario es una abreviación o variación de alguna escuela de la lista (ej. "prepa buap" = "Preparatoria BUAP", "cbtis 16" = "CBTis No. 16", "cobaep" = "Colegio de Bachilleres").
        2. Si logras relacionarlo con una de la lista, responde: OK_EXISTE|Nombre Exacto de la Lista
        3. Si NO está en la lista, pero claramente es un nombre o sigla válida de una preparatoria real, responde: OK_NUEVA|Nombre Formal y Corregido
        4. Solo rechaza si es texto sin sentido ("asdfg"), solo números o groserías. En ese caso responde: FALSO

        FORMATO ESTRICTO:
        Responde ÚNICAMENTE con el formato (OK_EXISTE|..., OK_NUEVA|... o FALSO). Cero texto extra.
        """

        chat_completion = cliente_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0
        )
        respuesta_original = chat_completion.choices[0].message.content.strip()

        # Separamos la respuesta en dos partes usando el símbolo |
        partes = respuesta_original.split("|", 1)
        palabra_clave = partes[0].upper()  # Convertimos el "ok_existe" a "OK_EXISTE"

        if palabra_clave == "OK_EXISTE" and len(partes) > 1:
            nombre_db = partes[1].strip()
            if nombre_db.lower() in diccionario_escuelas:
                print(f"🤖 IA vinculó '{nombre_usuario}' con '{nombre_db}'")
                return diccionario_escuelas[nombre_db.lower()]
            else:
                print(f"⚠️ IA dijo OK_EXISTE, pero '{nombre_db}' no estaba en el diccionario. Guardando como nueva...")
                cursor.execute("INSERT INTO bachilleratos (nombre) VALUES (%s)", (nombre_db,))
                conexion.commit()
                return cursor.lastrowid

        elif palabra_clave == "OK_NUEVA" and len(partes) > 1:
            nombre_nuevo = partes[1].strip()
            cursor.execute("INSERT INTO bachilleratos (nombre) VALUES (%s)", (nombre_nuevo,))
            conexion.commit()
            print(f"🤖 IA agregó escuela nueva: '{nombre_nuevo}'")
            return cursor.lastrowid

        print(f"🤖 IA rechazó la escuela: '{nombre_usuario}' -> Respuesta: {respuesta_original}")
        return None

    except Exception as e:
        print(f"❌ Error en IA Bachillerato: {e}")
        return None
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()


def validar_nombre_ia(nombre_usuario, cliente_groq):
    try:
        prompt = f"""
        Actúa como un validador de nombres para un sistema de admisiones en México.
        El usuario ha ingresado este nombre: "{nombre_usuario}"

        REGLAS ESTRICTAS DE VALIDACIÓN:
        1. ACEPTA el nombre si tiene estructura humana, incluso si es raro. 
        2. IMPORTANTE: En México existen apellidos de origen náhuatl/indígena (ej. Coyotl, Tepetl, Xicoténcatl), nombres astronómicos/mitológicos (ej. Aldebaran, Venus) y nombres extranjeros. ACEPTALOS TODOS sin dudar.
        3. Solo RECHAZA (respondiendo FALSO) si es:
           - Puro tecleo al azar (ej. "asdfgh", "qwerty").
           - Insultos o palabras obscenas.
           - Objetos inanimados obvios usados a modo de burla (ej. "Mesa de Madera").
           - Solo números.
        4. Si es válido, devuélvelo con la primera letra en mayúscula de cada palabra.

        FORMATO DE RESPUESTA ESPERADO:
        - Si es válido: OK|Nombre Corregido
        - Si es inválido: FALSO

        Responde ÚNICAMENTE con el formato, sin saludos ni explicaciones.
        """

        chat_completion = cliente_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0
        )
        respuesta_ai = chat_completion.choices[0].message.content.strip()

        # Hacemos la validación más flexible por si la IA pone mayúsculas o minúsculas
        if respuesta_ai.upper().startswith("OK|"):
            # Separamos por la barra vertical | para sacar solo el nombre
            nombre_limpio = respuesta_ai.split("|")[1].strip()
            print(f"🤖 IA aceptó y limpió el nombre: '{nombre_limpio}'")
            return nombre_limpio

        # Le agregamos {respuesta_ai} al print para que veas EXACTAMENTE qué contestó la IA
        print(f"🤖 IA rechazó el nombre: '{nombre_usuario}' -> Respuesta de la IA: {respuesta_ai}")
        return None

    except Exception as e:
        print(f"❌ Error en IA Nombre: {e}")
        # Si la API falla por internet, regresa el nombre con mayúsculas como respaldo
        return nombre_usuario.title() if len(nombre_usuario) >= 3 else None


def obtener_id_carrera(nombre_buscado):
    try:
        conexion = get_db_connection()
        if not conexion: return []

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
async def procesar_chat(mensaje: MensajeUsuario, request: Request):
            # Identificamos a la persona por su IP de internet
            ip_usuario = request.client.host
            # Sacamos su expediente único (adiós al global)
            estado_conversacion = obtener_sesion(ip_usuario)
            texto = mensaje.texto.lower().strip()
            respuesta_texto = ""
            opciones_lista = []
            paso = estado_conversacion["paso_actual"]

            # --- DEFINICIÓN DEL MENÚ PRINCIPAL UNIFICADO ---
            # Esto lo usaremos en varios lugares para que siempre sea igual
            MENU_PRINCIPAL_TEXTO = "¡Excelente! Ya estamos en el menú principal. ✨||¿En qué puedo ayudarte el día de hoy? Tengo toda esta información para ti:"
            MENU_PRINCIPAL_OPCIONES = [
                "1️⃣ Información de carreras",
                "2️⃣ Proceso de inscripción",
                "3️⃣ Fechas de admisión",
                "4️⃣ Costos",
                "5️⃣ Cursos de idioma",
                "6️⃣ Actividades extraescolares",
                "🚪 Cerrar Sesión"
            ]
            # --- FLUJO 0: SALUDO INICIAL ---
            if texto in ["hola", "inicio", "comenzar"] or paso == "saludo_inicial":
                estado_conversacion["paso_actual"] = "seleccion_tipo_usuario"
                # Solo asignamos variables, SIN usar return
                respuesta_texto = "¡Hola! Qué gusto saludarte. 🌟 Soy ItsaBot, el asistente de admisiones. Estoy súper emocionado de ayudarte || ¿Es tu primera vez por aquí o ya iniciaste tu proceso?"
                opciones_lista = ["Nuevo Registro", "Ya soy aspirante"]

            # --- FLUJO 1: SELECCIÓN ---
            elif paso == "seleccion_tipo_usuario":
                if "nuevo" in texto:
                    estado_conversacion["paso_actual"] = "pidiendo_nombre"
                    respuesta_texto = "¡Qué emoción! 🎉 Para empezar, ¿me podrías decir tu **nombre completo**?"
                elif "aspirante" in texto:
                    estado_conversacion["paso_actual"] = "login_esperando_correo"
                    respuesta_texto = "¡Qué gusto verte de nuevo! 🐾||Por favor, ingresa el **correo electrónico** de tu registro."
                else:
                    respuesta_texto = "Por favor, elige una opción:||¿Nuevo Registro o Ya soy aspirante?"
                    opciones_lista = ["Nuevo Registro", "Ya soy aspirante"]

            # --- FLUJO 2: LOGIN (YA SOY ASPIRANTE) ---
            elif paso == "login_esperando_correo":
                # Aquí verificamos si el correo existe en la base de datos
                conexion = get_db_connection()
                if not conexion: return None
                if conexion:
                    cursor = conexion.cursor(dictionary=True)
                    cursor.execute("SELECT nombre_completo, pin_seguridad FROM prospectos WHERE correo = %s",
                                   (texto,))
                    usuario = cursor.fetchone()
                    conexion.close()

                    if usuario:
                        estado_conversacion["datos_usuario"]["correo"] = texto
                        estado_conversacion["datos_usuario"]["nombre"] = usuario["nombre_completo"]
                        estado_conversacion["paso_actual"] = "login_esperando_pin"
                        respuesta_texto = f"¡Te encontré!🥳 || ¡Hola {usuario['nombre_completo']}! || Por favor, ingresa tu **PIN de 4 dígitos**."
                        opciones_lista = ["olvide mi pin"]
                    else:

                        respuesta_texto = "No encontré ningún registro con ese correo. Inténtalo de nuevo o elige 'Nuevo Registro'."

            elif paso == "login_esperando_pin":
                if texto in ["olvide mi pin", "olvidé mi pin"]:
                    # Generar código de 4 dígitos y enviar correo
                    codigo = str(random.randint(1000, 9999))
                    estado_conversacion["codigo_verificacion"] = codigo
                    correo = estado_conversacion["datos_usuario"]["correo"]



                    if enviar_correo_recuperacion(correo, codigo):
                        estado_conversacion["paso_actual"] = "esperando_codigo_correo"
                        respuesta_texto= f"Te he enviado un código de seguridad a **{correo}**.||Por favor, escríbelo aquí para crear un nuevo PIN."
                    else:
                        respuesta_texto="Hubo un error al enviar el correo. Intenta más tarde."
                        opciones_lista = ["Olvidé mi PIN"]
                else:
                    try:
                        pin_ingresado_hash = hashlib.sha256(texto.encode('utf-8')).hexdigest()

                # Lógica de verificación de PIN normal
                        conexion = get_db_connection()
                        if not conexion: return False

                        cursor = conexion.cursor(dictionary=True)
                        cursor.execute("SELECT pin_seguridad FROM prospectos WHERE correo = %s",
                                       (estado_conversacion["datos_usuario"]["correo"],))
                        res = cursor.fetchone()
                        conexion.close()

                        if res and pin_ingresado_hash== res["pin_seguridad"]:
                            estado_conversacion["paso_actual"] = "menu_libre"
                            respuesta_texto = f"¡Acceso concedido! ✅ Bienvenido de vuelta. {MENU_PRINCIPAL_TEXTO}"
                            opciones_lista = MENU_PRINCIPAL_OPCIONES

                        else:
                            respuesta_texto = "PIN incorrecto. Inténtalo de nuevo o selecciona 'Olvidé mi PIN'."
                            opciones_lista = ["Olvidé mi PIN"]

                    except Exception as e:
                        print(f"Error verificando PIN: {e}")
                        respuesta_texto = "Hubo un error al verificar tu PIN en el servidor."
                        opciones_lista = ["Olvidé mi PIN"]


            # --- FLUJO 3: RECUPERACIÓN DE PIN ---
            elif paso == "esperando_codigo_correo":
                if texto == estado_conversacion["codigo_verificacion"]:
                    estado_conversacion["paso_actual"] = "creando_nuevo_pin"
                    respuesta_texto="¡Código correcto! Ahora, por favor ingresa tu **nuevo PIN de 4 dígitos**."
                else:
                    respuesta_texto="Código incorrecto. Revisa tu correo nuevamente."

            elif paso == "creando_nuevo_pin":
                if len(texto) == 4 and texto.isdigit():
                    # Actualizar en la base de datos
                    nuevo_pin_hash = hashlib.sha256(texto.encode('utf-8')).hexdigest()
                    conexion = get_db_connection()
                    if not conexion: return False
                    cursor = conexion.cursor()
                    cursor.execute("UPDATE prospectos SET pin_seguridad = %s WHERE correo = %s",
                                   (nuevo_pin_hash, estado_conversacion["datos_usuario"]["correo"]))
                    conexion.commit()
                    conexion.close()

                    estado_conversacion["paso_actual"] = "menu_libre"
                    respuesta_texto = f"¡PIN actualizado con éxito! || ¡Acceso concedido! ✅ Bienvenido de vuelta. {MENU_PRINCIPAL_TEXTO}"
                    opciones_lista = MENU_PRINCIPAL_OPCIONES
                else:
                    respuesta_texto="El PIN debe ser de 4 números exactamente."

            elif paso == "pidiendo_nombre":

                if texto in ["hola", "inicio", "arrancar", "menú", "🎯 menú principal", ""]:
                    respuesta_texto = "¡Hola! Qué gusto saludarte. 🌟 Soy ItsaBot, el asistente de admisiones. Estoy súper emocionado de ayudarte. Para darte la mejor atención, ¿me podrías regalar tu nombre completo por favor?"
                else:
                    # ¡Llamamos a la nueva función de IA!
                    nombre_validado = validar_nombre_ia(texto, client)

                    if nombre_validado:
                        estado_conversacion["datos_usuario"]["nombre"] = nombre_validado
                        estado_conversacion["paso_actual"] = "pidiendo_edad"
                        respuesta_texto = f"¡Mucho gusto, {nombre_validado}! 🤝 Oye, y cuéntame, ¿qué edad tienes?"
                    else:
                        respuesta_texto = "Mmm, ese no parece un nombre real. 🤔 Por favor, escríbeme tu nombre y apellido verdaderos para poder registrarte correctamente."

            elif paso == "pidiendo_edad":
                if es_edad_valida(texto):
                    estado_conversacion["datos_usuario"]["edad"] = int(texto)
                    estado_conversacion["paso_actual"] = "pidiendo_telefono"
                    respuesta_texto = "¡Súper! 🚀 ¿Cuál es tu número de teléfono a 10 dígitos?"
                else:
                    respuesta_texto = "Escribe solo tu edad en números (ejemplo: 17)."

            elif paso == "pidiendo_telefono":
                if es_telefono_valido(texto):
                    estado_conversacion["datos_usuario"]["telefono"] = texto
                    estado_conversacion["paso_actual"] = "pidiendo_correo"
                    respuesta_texto = "¡Anotado! 📱 Ahora, ¿cuál es tu correo electrónico?"
                else:
                    respuesta_texto = "Escribe un número a 10 dígitos (ejemplo: 2441234567)."

            elif paso == "pidiendo_correo":
                if es_correo_valido(texto):
                    estado_conversacion["datos_usuario"]["correo"] = texto
                    estado_conversacion["paso_actual"] = "pidiendo_bachillerato"
                    respuesta_texto = "¡Gracias! 📧 ¿De qué bachillerato o preparatoria vienes?"
                else:
                    respuesta_texto = "Escribe un correo válido (ejemplo: usuario@gmail.com)."

            elif paso == "pidiendo_bachillerato":
                # Llamamos a nuestra nueva súper-función con IA, pasándole el cliente de Groq
                id_bach = validar_y_obtener_bachillerato(texto, client)

                if id_bach:  # Si la IA nos devolvió un ID (ya sea existente o nuevo)
                    estado_conversacion["datos_usuario"]["id_bachillerato"] = id_bach
                    estado_conversacion["paso_actual"] = "pidiendo_carrera"
                    respuesta_texto = "¡Excelente escuela! 🏫 Ahora dime, ¿qué carrera te interesa estudiar?"
                    opciones_lista = ["Sistemas", "Mecatrónica", "Industrial", "Bioquímica", "Electromecánica",
                                      "Gastronomía"]
                else:
                    # Si la IA dijo que es falsa o no tiene sentido
                    respuesta_texto = "Hmm, no logré reconocer esa preparatoria o bachillerato. 🤔 ¿Podrías escribir el nombre completo o las siglas correctas de tu escuela, por favor?"

            elif paso == "pidiendo_carrera":
                # Buscamos qué carrera eligió
                id_car = obtener_id_carrera(texto)
                if id_car:
                    estado_conversacion["datos_usuario"]["id_carrera"] = id_car

                    # CAMBIO: En lugar de finalizar, pedimos el PIN
                    estado_conversacion["paso_actual"] = "creando_pin_registro"
                    respuesta_texto= "¡Excelente elección! 🎓||Ya casi terminamos. Para que puedas consultar tu estatus después, **crea un PIN de 4 números** (ejemplo: 1234)."
                    opciones_lista= []

                else:
                    respuesta_texto= "Por favor, elige una de las carreras de los botones."

            elif paso == "creando_pin_registro":
                # Validamos que sean 4 dígitos exactos
                if len(texto) == 4 and texto.isdigit():
                    estado_conversacion["datos_usuario"]["pin"] = texto

                    # GUARDAR EN BASE DE DATOS
                    guardar_en_mysql(estado_conversacion["datos_usuario"])


                    estado_conversacion["paso_actual"] = "menu_libre"
                    respuesta_texto = f"¡Registro completo! 🎉 Ya eres parte de nuestros aspirantes. Bienvenido. {MENU_PRINCIPAL_TEXTO}"
                    opciones_lista = MENU_PRINCIPAL_OPCIONES
                else:
                    return {"respuesta": "El PIN debe ser de **4 números**. Inténtalo de nuevo."}

        # ==========================================
        # 2. ZONA LIBRE (El usuario ya nos dio sus datos)
        # ==========================================
            elif paso == "menu_libre":
                if "cerrar sesión" in texto or "cerrar sesion" in texto:
                    estado_conversacion = {"paso_actual": "saludo_inicial", "datos_usuario": {}}
                    respuesta_texto = "Has cerrado sesión correctamente. 🔒||¡Vuelve pronto! Escribe 'Hola' si necesitas algo más."
                    opciones_lista = ["Inicio"]

                elif "1️⃣" in texto or "carreras" in texto:
                    respuesta_texto = "Nuestra oferta educativa es excelente. ¿De qué carrera te gustaría saber más?"
                    opciones_lista = ["Sistemas", "Mecatrónica", "Industrial", "Bioquímica",
                                      "Electromecánica", "Gastronomía", "Turismo", "Ciencia de Datos",
                                      "🎯 Menú Principal"]
                    # ===== ELECTROMECÁNICA =====
                elif "electromecánica" in texto or "electromecanica" in texto:
                    respuesta_texto = (
                        "⚡ Ingeniería Electromecánica||"
                        "Especialidad: Automatización Industrial||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Electromecánica",
                        "Perfil de egreso Electromecánica",
                        "Campo laboral Electromecánica",
                        "Empresas Electromecánica",
                        "Plan de estudios Electromecánica",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO ELECTROMECÁNICA =====
                elif "perfil de ingreso electromecánica" in texto or "perfil de ingreso electromecanica" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Ingeniería Electromecánica||"
                        "• Egresado(a) de preparatoria o bachillerato||"
                        "• Convicción por el logro de metas profesionales||"
                        "• Conocimientos de matemáticas y física||"
                        "• Comprensión lectora y competencias comunicativas||"
                        "• Creatividad e interés por la ciencia y tecnología||"
                        "• Destreza manual y solución de problemas mediante el análisis"
                    )

                    opciones_lista = [
                        "Perfil de egreso Electromecánica",
                        "Campo laboral Electromecánica",
                        "Empresas Electromecánica",
                        "Plan de estudios Electromecánica",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO ELECTROMECÁNICA =====
                elif "perfil de egreso electromecánica" in texto or "perfil de egreso electromecanica" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Ingeniería Electromecánica||"
                        "El egresado será capaz de identificar, diseñar, implementar y evaluar proyectos relacionados con sistemas electromecánicos y automatización industrial.||"
                        "También podrá diseñar sistemas eficientes para el control y automatización de procesos productivos, considerando ahorro de energía, seguridad industrial y desarrollo sustentable.||"
                        "Además, podrá planificar, gestionar y evaluar proyectos de ingeniería con tecnologías de vanguardia."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Electromecánica",
                        "Campo laboral Electromecánica",
                        "Empresas Electromecánica",
                        "Plan de estudios Electromecánica",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL ELECTROMECÁNICA =====
                elif "campo laboral electromecánica" in texto or "campo laboral electromecanica" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Ingeniería Electromecánica||"
                        "• Automatización industrial||"
                        "• Sistemas electromecánicos||"
                        "• Control de procesos productivos||"
                        "• Mantenimiento industrial||"
                        "• Sector energético||"
                        "• Industria automotriz||"
                        "• Gestión y evaluación de proyectos de ingeniería||"
                        "• Optimización de procesos industriales"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Electromecánica",
                        "Perfil de egreso Electromecánica",
                        "Empresas Electromecánica",
                        "Plan de estudios Electromecánica",
                        "🎯 Menú Principal"
                    ]


                # ===== EMPRESAS ELECTROMECÁNICA =====
                elif "empresas electromecánica" in texto or "empresas electromecanica" in texto:
                    respuesta_texto = (
                        "🏢 Algunas empresas donde laboran egresados de Ingeniería Electromecánica||"
                        "• Audi||"
                        "• Coca Cola||"
                        "• CFE (Comisión Federal de Electricidad)||"
                        "• Continental||"
                        "• Sunpower||"
                        "• Volkswagen||"
                        "• Clúster Energético de Puebla||"
                        "• Pemex||"
                        "• Ayuntamiento de Atlixco"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Electromecánica",
                        "Perfil de egreso Electromecánica",
                        "Campo laboral Electromecánica",
                        "Plan de estudios Electromecánica",
                        "🎯 Menú Principal"
                    ]


                # ===== PLAN DE ESTUDIOS ELECTROMECÁNICA =====
                elif "plan de estudios electromecánica" in texto or "plan de estudios electromecanica" in texto:
                    respuesta_texto = (
                        "📚 Plan de estudios - Ingeniería Electromecánica||"
                        "Consulta el plan completo aquí:||"
                        "https://atlixco.tecnm.mx/ingenieria/Electromec%C3%A1nica"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Electromecánica",
                        "Perfil de egreso Electromecánica",
                        "Campo laboral Electromecánica",
                        "Empresas Electromecánica",
                        "🎯 Menú Principal"
                    ]

                    # ===== TURISMO =====
                elif "turismo" in texto:
                    respuesta_texto = (
                        "🌍 Licenciatura en Turismo||"
                        "Formación enfocada en proyectos turísticos sustentables||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Objetivo Turismo",
                        "Perfil de ingreso Turismo",
                        "Perfil de egreso Turismo",
                        "Campo laboral Turismo",
                        "Áreas de aplicación Turismo",
                        "🎯 Menú Principal"
                    ]


                # ===== OBJETIVO TURISMO =====
                elif "objetivo turismo" in texto:
                    respuesta_texto = (
                        "🎯 Objetivo general - Licenciatura en Turismo||"
                        "Formar profesionales capaces de emprender, gestionar e innovar proyectos turísticos sustentables.||"
                        "La carrera promueve la calidad, el sentido ético y el respeto al patrimonio natural y cultural, respondiendo a las necesidades y tendencias globales del turismo."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Turismo",
                        "Perfil de egreso Turismo",
                        "Campo laboral Turismo",
                        "Áreas de aplicación Turismo",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO TURISMO =====
                elif "perfil de ingreso turismo" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Turismo||"
                        "• Interés por el turismo, la cultura y el medio ambiente||"
                        "• Habilidades para trabajo en equipo y liderazgo||"
                        "• Comunicación básica y aprendizaje de idiomas||"
                        "• Actitud de servicio y proactividad||"
                        "• Interés por el desarrollo turístico sustentable"
                    )

                    opciones_lista = [
                        "Objetivo Turismo",
                        "Perfil de egreso Turismo",
                        "Campo laboral Turismo",
                        "Áreas de aplicación Turismo",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO TURISMO =====
                elif "perfil de egreso turismo" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Turismo||"
                        "El egresado adquiere competencias en gestión sustentable y aplicación de proyectos turísticos.||"
                        "También podrá dirigir operaciones en empresas turísticas, administrar recursos, comercializar destinos y analizar tendencias globales.||"
                        "Además, aplicará tecnologías de la información en el sector turístico."
                    )

                    opciones_lista = [
                        "Objetivo Turismo",
                        "Perfil de ingreso Turismo",
                        "Campo laboral Turismo",
                        "Áreas de aplicación Turismo",
                        "🎯 Menú Principal"
                    ]


                # ===== ÁREAS DE APLICACIÓN TURISMO =====
                elif "áreas de aplicación turismo" in texto or "areas de aplicación turismo" in texto:
                    respuesta_texto = (
                        "🧭 Áreas de aplicación - Turismo||"
                        "• Gestión y operación turística en hoteles, restaurantes y agencias de viajes||"
                        "• Turismo sustentable y de naturaleza||"
                        "• Diseño de actividades de ecoturismo y turismo rural||"
                        "• Planeación y consultoría turística||"
                        "• Mercadotecnia y comercialización de destinos turísticos"
                    )

                    opciones_lista = [
                        "Objetivo Turismo",
                        "Perfil de ingreso Turismo",
                        "Perfil de egreso Turismo",
                        "Campo laboral Turismo",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL TURISMO =====
                elif "campo laboral turismo" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Turismo||"
                        "• Cadenas hoteleras y empresas de hospedaje||"
                        "• Cruceros y agencias de viajes||"
                        "• Empresas de hospitalidad||"
                        "• Secretarías de turismo y áreas de planeación turística||"
                        "• Emprendimiento de negocios turísticos sustentables||"
                        "• Parques ecoturísticos y turismo de aventura||"
                        "• Organización de congresos, convenciones y eventos"
                    )

                    opciones_lista = [
                        "Objetivo Turismo",
                        "Perfil de ingreso Turismo",
                        "Perfil de egreso Turismo",
                        "Áreas de aplicación Turismo",
                        "🎯 Menú Principal"
                    ]

                    # ===== SISTEMAS COMPUTACIONALES =====
                elif "sistemas" in texto or "sistemas computacionales" in texto:
                    respuesta_texto = (
                        "💻 Ingeniería en Sistemas Computacionales||"
                        "Especialidad: Ingeniería de Software||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Objetivo Sistemas",
                        "Perfil de ingreso Sistemas",
                        "Perfil de egreso Sistemas",
                        "Campo laboral Sistemas",
                        "Plan de estudios Sistemas",
                        "🎯 Menú Principal"
                    ]


                # ===== OBJETIVO SISTEMAS =====
                elif "objetivo sistemas" in texto:
                    respuesta_texto = (
                        "🎯 Objetivo general - Sistemas Computacionales||"
                        "Formar profesionistas líderes con visión estratégica y sentido ético, capaces de diseñar, desarrollar, implementar y administrar tecnología computacional.||"
                        "El egresado podrá aportar soluciones innovadoras en beneficio de la sociedad dentro de un contexto global, multidisciplinario y sostenible."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Sistemas",
                        "Perfil de egreso Sistemas",
                        "Campo laboral Sistemas",
                        "Plan de estudios Sistemas",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO SISTEMAS =====
                elif "perfil de ingreso sistemas" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Sistemas Computacionales||"
                        "• Habilidades informáticas||"
                        "• Interés por computadoras y dispositivos móviles||"
                        "• Capacidad de análisis, abstracción y síntesis||"
                        "• Razonamiento lógico para resolver problemas||"
                        "• Interés por las Tecnologías de la Información||"
                        "• Facilidad para comprender textos técnicos||"
                        "• Habilidad numérica e interés por la ciencia y tecnología"
                    )

                    opciones_lista = [
                        "Objetivo Sistemas",
                        "Perfil de egreso Sistemas",
                        "Campo laboral Sistemas",
                        "Plan de estudios Sistemas",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO SISTEMAS =====
                elif "perfil de egreso sistemas" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Sistemas Computacionales||"
                        "El egresado podrá desarrollar, integrar y administrar soluciones computacionales utilizando diferentes tecnologías y plataformas.||"
                        "También podrá configurar bases de datos, diseñar redes computacionales y desarrollar aplicaciones de software eficientes.||"
                        "Además, podrá participar en proyectos interdisciplinarios considerando aspectos éticos, legales y de desarrollo sustentable."
                    )

                    opciones_lista = [
                        "Objetivo Sistemas",
                        "Perfil de ingreso Sistemas",
                        "Campo laboral Sistemas",
                        "Plan de estudios Sistemas",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL SISTEMAS =====
                elif "campo laboral sistemas" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Sistemas Computacionales||"
                        "• Desarrollo y gestión de proyectos de software||"
                        "• Administración de bases de datos||"
                        "• Desarrollo de aplicaciones móviles||"
                        "• Creación de sitios web||"
                        "• Automatización de procesos y sistemas en tiempo real||"
                        "• Desarrollo de aplicaciones IoT||"
                        "• Diseño y monitoreo de redes de cómputo||"
                        "• Evaluación y optimización de software"
                    )

                    opciones_lista = [
                        "Objetivo Sistemas",
                        "Perfil de ingreso Sistemas",
                        "Perfil de egreso Sistemas",
                        "Plan de estudios Sistemas",
                        "🎯 Menú Principal"
                    ]


                # ===== PLAN DE ESTUDIOS SISTEMAS =====
                elif "plan de estudios sistemas" in texto:
                    respuesta_texto = (
                        "📚 Plan de estudios - Sistemas Computacionales||"
                        "Consulta el plan completo aquí:||"
                        "https://atlixco.tecnm.mx/ingenieria/Sistemas-Computacionales"
                    )

                    opciones_lista = [
                        "Objetivo Sistemas",
                        "Perfil de ingreso Sistemas",
                        "Perfil de egreso Sistemas",
                        "Campo laboral Sistemas",
                        "🎯 Menú Principal"
                    ]


                # ===== CIENCIA DE DATOS =====
                elif "ciencia de datos" in texto or "ciencias de datos" in texto:
                    respuesta_texto = (
                        "📊 Ingeniería en Ciencia de Datos||"
                        "Formación enfocada en análisis de datos e inteligencia artificial||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Objetivo Ciencia de Datos",
                        "Perfil de ingreso Ciencia de Datos",
                        "Perfil de egreso Ciencia de Datos",
                        "Áreas de aplicación Ciencia de Datos",
                        "Campo laboral Ciencia de Datos",
                        "🎯 Menú Principal"
                    ]


                # ===== OBJETIVO CIENCIA DE DATOS =====
                elif "objetivo ciencia de datos" in texto:
                    respuesta_texto = (
                        "🎯 Objetivo general - Ciencia de Datos||"
                        "Formar ingenieros capaces de modelar, implementar y evaluar datos provenientes de entornos complejos.||"
                        "El estudiante utilizará técnicas de vanguardia para identificar patrones y facilitar la toma de decisiones estratégicas en sectores educativos, empresariales, sociales e industriales.||"
                        "La formación tiene un enfoque ético, sostenible y multidisciplinario."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Ciencia de Datos",
                        "Perfil de egreso Ciencia de Datos",
                        "Áreas de aplicación Ciencia de Datos",
                        "Campo laboral Ciencia de Datos",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO CIENCIA DE DATOS =====
                elif "perfil de ingreso ciencia de datos" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Ciencia de Datos||"
                        "• Habilidades lógico-matemáticas y de programación||"
                        "• Pensamiento crítico y analítico||"
                        "• Capacidad creativa y resolución de problemas||"
                        "• Liderazgo y trabajo en equipo multidisciplinario||"
                        "• Conciencia ética y compromiso social||"
                        "• Aprendizaje autónomo y capacidad de síntesis"
                    )

                    opciones_lista = [
                        "Objetivo Ciencia de Datos",
                        "Perfil de egreso Ciencia de Datos",
                        "Áreas de aplicación Ciencia de Datos",
                        "Campo laboral Ciencia de Datos",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO CIENCIA DE DATOS =====
                elif "perfil de egreso ciencia de datos" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Ciencia de Datos||"
                        "El egresado dominará técnicas de recolección, limpieza y análisis de datos para apoyar la toma de decisiones estratégicas.||"
                        "También podrá desarrollar arquitecturas de datos, modelos de aprendizaje automático y soluciones basadas en inteligencia artificial.||"
                        "Además, podrá gestionar proyectos de ciencia de datos con responsabilidad ética y social."
                    )

                    opciones_lista = [
                        "Objetivo Ciencia de Datos",
                        "Perfil de ingreso Ciencia de Datos",
                        "Áreas de aplicación Ciencia de Datos",
                        "Campo laboral Ciencia de Datos",
                        "🎯 Menú Principal"
                    ]


                # ===== ÁREAS DE APLICACIÓN CIENCIA DE DATOS =====
                elif "áreas de aplicación ciencia de datos" in texto or "areas de aplicación ciencia de datos" in texto:
                    respuesta_texto = (
                        "🧠 Áreas de aplicación - Ciencia de Datos||"
                        "• Análisis predictivo y prescriptivo||"
                        "• Inteligencia Artificial y Machine Learning||"
                        "• Visualización de datos y dashboards||"
                        "• Gestión de bases de datos y Big Data||"
                        "• Optimización de procesos empresariales||"
                        "• Desarrollo de soluciones inteligentes"
                    )

                    opciones_lista = [
                        "Objetivo Ciencia de Datos",
                        "Perfil de ingreso Ciencia de Datos",
                        "Perfil de egreso Ciencia de Datos",
                        "Campo laboral Ciencia de Datos",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL CIENCIA DE DATOS =====
                elif "campo laboral ciencia de datos" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Ciencia de Datos||"
                        "• Empresas de consultoría||"
                        "• Sector financiero y aseguradoras||"
                        "• Comercio electrónico y marketing digital||"
                        "• Institutos de investigación y centros de datos||"
                        "• Instituciones públicas y bancos centrales||"
                        "• Startups tecnológicas||"
                        "• Empresas de tecnología, banca y manufactura"
                    )

                    opciones_lista = [
                        "Objetivo Ciencia de Datos",
                        "Perfil de ingreso Ciencia de Datos",
                        "Perfil de egreso Ciencia de Datos",
                        "Áreas de aplicación Ciencia de Datos",
                        "🎯 Menú Principal"
                    ]


                # ===== GASTRONOMÍA =====
                elif "gastronomía" in texto or "gastronomia" in texto:
                    respuesta_texto = (
                        "🍳 Licenciatura en Gastronomía||"
                        "Especialidad: Cocina Mexicana||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Gastronomía",
                        "Perfil de egreso Gastronomía",
                        "Campo laboral Gastronomía",
                        "Plan de estudios Gastronomía",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO GASTRONOMÍA =====
                elif "perfil de ingreso gastronomía" in texto or "perfil de ingreso gastronomia" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Gastronomía||"
                        "• Bachillerato concluido, preferentemente en áreas técnicas, administrativas o de salud||"
                        "• Creatividad y sensibilidad artística||"
                        "• Facilidad para el trabajo en equipo||"
                        "• Dominio del español y bases de idioma inglés||"
                        "• Ética de servicio y espíritu innovador||"
                        "• Enfoque en metas y disciplina"
                    )

                    opciones_lista = [
                        "Perfil de egreso Gastronomía",
                        "Campo laboral Gastronomía",
                        "Plan de estudios Gastronomía",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO GASTRONOMÍA =====
                elif "perfil de egreso gastronomía" in texto or "perfil de egreso gastronomia" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Gastronomía||"
                        "El egresado será capaz de ejecutar técnicas culinarias nacionales e internacionales con creatividad y calidad.||"
                        "También podrá administrar negocios de alimentos y bebidas, garantizando normas de higiene e inocuidad alimentaria.||"
                        "Además, podrá diseñar experiencias y conceptos gastronómicos innovadores basados en tendencias del mercado."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Gastronomía",
                        "Campo laboral Gastronomía",
                        "Plan de estudios Gastronomía",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL GASTRONOMÍA =====
                elif "campo laboral gastronomía" in texto or "campo laboral gastronomia" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Gastronomía||"
                        "• Restaurantes y hoteles||"
                        "• Cruceros y clubes privados||"
                        "• Bares y coctelería||"
                        "• Comedores industriales||"
                        "• Empresas de catering y eventos||"
                        "• Industria alimentaria||"
                        "• Consultoría gastronómica||"
                        "• Emprendimiento propio y docencia"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Gastronomía",
                        "Perfil de egreso Gastronomía",
                        "Plan de estudios Gastronomía",
                        "🎯 Menú Principal"
                    ]


                # ===== PLAN DE ESTUDIOS GASTRONOMÍA =====
                elif "plan de estudios gastronomía" in texto or "plan de estudios gastronomia" in texto:
                    respuesta_texto = (
                        "📚 Plan de estudios - Gastronomía||"
                        "Consulta el plan completo aquí:||"
                        "https://atlixco.tecnm.mx/ingenieria/Gastronomia"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Gastronomía",
                        "Perfil de egreso Gastronomía",
                        "Campo laboral Gastronomía",
                        "🎯 Menú Principal"
                    ]

                    # ===== MECATRÓNICA =====
                elif "mecatrónica" in texto or "mecatronica" in texto:
                    respuesta_texto = (
                        "🤖 Ingeniería Mecatrónica||"
                        "Especialidad: Automatización de procesos||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Objetivo Mecatrónica",
                        "Perfil de ingreso Mecatrónica",
                        "Perfil de egreso Mecatrónica",
                        "Campo laboral Mecatrónica",
                        "Plan de estudios Mecatrónica",
                        "🎯 Menú Principal"
                    ]


                # ===== OBJETIVO MECATRÓNICA =====
                elif "objetivo mecatrónica" in texto or "objetivo mecatronica" in texto:
                    respuesta_texto = (
                        "🎯 Objetivo general - Mecatrónica||"
                        "Formar profesionistas capaces de diseñar, construir, innovar y administrar sistemas mecatrónicos y robóticos.||"
                        "El egresado podrá integrar, operar y mantener sistemas automatizados con liderazgo, creatividad y compromiso ético dentro de un marco sustentable."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Mecatrónica",
                        "Perfil de egreso Mecatrónica",
                        "Campo laboral Mecatrónica",
                        "Plan de estudios Mecatrónica",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO MECATRÓNICA =====
                elif "perfil de ingreso mecatrónica" in texto or "perfil de ingreso mecatronica" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Mecatrónica||"
                        "• Conocimientos básicos en ciencias naturales y exactas||"
                        "• Habilidades de análisis, síntesis y autoaprendizaje||"
                        "• Interés por la robótica, programación y tecnología||"
                        "• Capacidad de trabajo individual y en equipo||"
                        "• Interés por el diseño y emprendimiento||"
                        "• Disposición para aprender y mejorar continuamente"
                    )

                    opciones_lista = [
                        "Objetivo Mecatrónica",
                        "Perfil de egreso Mecatrónica",
                        "Campo laboral Mecatrónica",
                        "Plan de estudios Mecatrónica",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO MECATRÓNICA =====
                elif "perfil de egreso mecatrónica" in texto or "perfil de egreso mecatronica" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Mecatrónica||"
                        "El egresado será capaz de diseñar, automatizar, controlar y mantener sistemas mecatrónicos utilizando tecnologías eléctricas, electrónicas y computacionales.||"
                        "También podrá liderar proyectos multidisciplinarios, innovar soluciones tecnológicas y participar en procesos industriales con responsabilidad social y sustentable."
                    )

                    opciones_lista = [
                        "Objetivo Mecatrónica",
                        "Perfil de ingreso Mecatrónica",
                        "Campo laboral Mecatrónica",
                        "Plan de estudios Mecatrónica",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL MECATRÓNICA =====
                elif "campo laboral mecatrónica" in texto or "campo laboral mecatronica" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Mecatrónica||"
                        "• Industria automotriz||"
                        "• Robótica industrial||"
                        "• Automatización y control de procesos||"
                        "• Industria aeroespacial||"
                        "• Mantenimiento industrial||"
                        "• Industria energética||"
                        "• Área médica y tecnológica||"
                        "• Desarrollo de proyectos independientes"
                    )

                    opciones_lista = [
                        "Objetivo Mecatrónica",
                        "Perfil de ingreso Mecatrónica",
                        "Perfil de egreso Mecatrónica",
                        "Plan de estudios Mecatrónica",
                        "🎯 Menú Principal"
                    ]


                # ===== PLAN DE ESTUDIOS MECATRÓNICA =====
                elif "plan de estudios mecatrónica" in texto or "plan de estudios mecatronica" in texto:
                    respuesta_texto = (
                        "📚 Plan de estudios - Mecatrónica||"
                        "Consulta el plan completo aquí:||"
                        "https://atlixco.tecnm.mx/ingenieria/Mecatronica"
                    )

                    opciones_lista = [
                        "Objetivo Mecatrónica",
                        "Perfil de ingreso Mecatrónica",
                        "Perfil de egreso Mecatrónica",
                        "Campo laboral Mecatrónica",
                        "🎯 Menú Principal"
                    ]



                # ===== INDUSTRIAL =====
                elif "industrial" in texto or "ingeniería industrial" in texto or "ingenieria industrial" in texto:
                    respuesta_texto = (
                        "🏭 Ingeniería Industrial||"
                        "Especialidad: Calidad y productividad||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Industrial",
                        "Perfil de egreso Industrial",
                        "Campo laboral Industrial",
                        "Plan de estudios Industrial",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO INDUSTRIAL =====
                elif "perfil de ingreso industrial" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Ingeniería Industrial||"
                        "• Egresado(a) de preparatoria o bachillerato||"
                        "• Interés por la ciencia y la tecnología||"
                        "• Creatividad e innovación||"
                        "• Interés por la mejora continua||"
                        "• Deseo de superación y excelencia profesional"
                    )

                    opciones_lista = [
                        "Perfil de egreso Industrial",
                        "Campo laboral Industrial",
                        "Plan de estudios Industrial",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO INDUSTRIAL =====
                elif "perfil de egreso industrial" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Ingeniería Industrial||"
                        "El egresado podrá optimizar procesos productivos, mejorar la calidad y productividad de las organizaciones y tomar decisiones estratégicas mediante el uso de ciencia y tecnología.||"
                        "También desarrollará habilidades de liderazgo, innovación y trabajo en equipo, aplicando nuevas tecnologías como inteligencia artificial para resolver problemas industriales."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Industrial",
                        "Campo laboral Industrial",
                        "Plan de estudios Industrial",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL INDUSTRIAL =====
                elif "campo laboral industrial" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Ingeniería Industrial||"
                        "• Industria manufacturera||"
                        "• Logística y cadena de suministro||"
                        "• Consultoría empresarial||"
                        "• Gestión de calidad y productividad||"
                        "• Administración de proyectos||"
                        "• Empresas nacionales e internacionales||"
                        "• Optimización de procesos y recursos"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Industrial",
                        "Perfil de egreso Industrial",
                        "Plan de estudios Industrial",
                        "🎯 Menú Principal"
                    ]


                # ===== PLAN DE ESTUDIOS INDUSTRIAL =====
                elif "plan de estudios industrial" in texto:
                    respuesta_texto = (
                        "📚 Plan de estudios - Ingeniería Industrial||"
                        "Consulta el plan completo aquí:||"
                        "https://atlixco.tecnm.mx/ingenieria/Industrial"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Industrial",
                        "Perfil de egreso Industrial",
                        "Campo laboral Industrial",
                        "🎯 Menú Principal"
                    ]



                # ===== BIOQUÍMICA =====
                elif "bioquímica" in texto or "bioquimica" in texto:
                    respuesta_texto = (
                        "🧪 Ingeniería Bioquímica||"
                        "Especialidad: Alimentos||"
                        "Duración: 9 semestres||"
                        "¿Qué te gustaría conocer de esta carrera?"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Bioquímica",
                        "Perfil de egreso Bioquímica",
                        "Campo laboral Bioquímica",
                        "Empresas Bioquímica",
                        "Plan de estudios Bioquímica",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE INGRESO BIOQUÍMICA =====
                elif "perfil de ingreso bioquímica" in texto or "perfil de ingreso bioquimica" in texto:
                    respuesta_texto = (
                        "📘 Perfil de ingreso - Bioquímica||"
                        "• Conocimientos en matemáticas y ciencias experimentales||"
                        "• Capacidad de análisis y solución de problemas||"
                        "• Habilidad para trabajar en equipo||"
                        "• Comunicación oral y escrita||"
                        "• Actitud crítica y reflexiva||"
                        "• Valores de honestidad y respeto"
                    )

                    opciones_lista = [
                        "Perfil de egreso Bioquímica",
                        "Campo laboral Bioquímica",
                        "Empresas Bioquímica",
                        "Plan de estudios Bioquímica",
                        "🎯 Menú Principal"
                    ]


                # ===== PERFIL DE EGRESO BIOQUÍMICA =====
                elif "perfil de egreso bioquímica" in texto or "perfil de egreso bioquimica" in texto:
                    respuesta_texto = (
                        "🎓 Perfil de egreso - Bioquímica||"
                        "El egresado será capaz de aplicar conocimientos de ciencia y tecnología de alimentos, aseguramiento de calidad e inocuidad alimentaria.||"
                        "También podrá desarrollar productos innovadores, optimizar procesos productivos y contribuir al sector agroalimentario con enfoque sustentable."
                    )

                    opciones_lista = [
                        "Perfil de ingreso Bioquímica",
                        "Campo laboral Bioquímica",
                        "Empresas Bioquímica",
                        "Plan de estudios Bioquímica",
                        "🎯 Menú Principal"
                    ]


                # ===== CAMPO LABORAL BIOQUÍMICA =====
                elif "campo laboral bioquímica" in texto or "campo laboral bioquimica" in texto:
                    respuesta_texto = (
                        "💼 Campo laboral - Bioquímica||"
                        "• Industria alimentaria||"
                        "• Empresas de bebidas y alimentos||"
                        "• Biotecnología vegetal||"
                        "• Ingeniería ambiental||"
                        "• Centros de investigación||"
                        "• Instituciones educativas||"
                        "• Desarrollo y aseguramiento de calidad||"
                        "• Emprendimiento propio"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Bioquímica",
                        "Perfil de egreso Bioquímica",
                        "Empresas Bioquímica",
                        "Plan de estudios Bioquímica",
                        "🎯 Menú Principal"
                    ]


                # ===== EMPRESAS BIOQUÍMICA =====
                elif "empresas bioquímica" in texto or "empresas bioquimica" in texto:
                    respuesta_texto = (
                        "🏢 Algunas empresas donde laboran egresados de Bioquímica||"
                        "• Bimbo||"
                        "• Coca Cola||"
                        "• Italpasta||"
                        "• Sabormex||"
                        "• Leonali||"
                        "• Ayuntamiento de Atlixco"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Bioquímica",
                        "Perfil de egreso Bioquímica",
                        "Campo laboral Bioquímica",
                        "Plan de estudios Bioquímica",
                        "🎯 Menú Principal"
                    ]


                # ===== PLAN DE ESTUDIOS BIOQUÍMICA =====
                elif "plan de estudios bioquímica" in texto or "plan de estudios bioquimica" in texto:
                    respuesta_texto = (
                        "📚 Plan de estudios - Bioquímica||"
                        "Consulta el plan completo aquí:||"
                        "https://atlixco.tecnm.mx/ingenieria/Bioquimica"
                    )

                    opciones_lista = [
                        "Perfil de ingreso Bioquímica",
                        "Perfil de egreso Bioquímica",
                        "Campo laboral Bioquímica",
                        "Empresas Bioquímica",
                        "🎯 Menú Principal"
                    ]

                elif "2️⃣" in texto or "inscripción" in texto or "inscripcion" in texto:
                    respuesta_texto = (
                        "¡Excelente decisión! 🤩 Inscribirte a nuestra comunidad Tec es el primer paso hacia tu éxito profesional, y el proceso es súper sencillo. Te guío paso a paso: ||"
                        "1️⃣ <b>Pago de Ficha:</b> Ingresa a la página oficial de pagos del Estado en <a href='https://rl.puebla.gob.mx/' target='_blank'>rl.puebla.gob.mx</a>. En la sección de Educación busca 'ITSA' o 'Tecnológico de Atlixco' y genera tu línea de captura para la ficha de admisión. ||"
                        "2️⃣ <b>Registro en Línea:</b> Llena el formulario con tus datos y sube en formato PDF tu Acta de Nacimiento, CURP actualizada, constancia de bachillerato y comprobante de domicilio. ||"
                        "3️⃣ <b>Examen de Admisión:</b> Preséntate en nuestro campus el día que te corresponda con tu pase de ingreso, identificación con foto, lápiz y goma. ¡Ve con toda la actitud ganadora! 🧠✨ ||"
                        "4️⃣ <b>Inscripción Presencial:</b> ¡Si fuiste aceptado, felicidades! Solo tendrás que llevar tus papeles originales a Control Escolar y ponerte una camisa blanca para la foto de tu nueva credencial de estudiante. 📸 ||"
                        "¿Te gustaría conocer las fechas exactas de este proceso o prefieres que hablemos de los costos?"
                    )
                    opciones_lista = [
                        "3️⃣ Fechas de admisión",
                        "4️⃣ Costos",
                        "🎯 Menú Principal"
                    ]

                elif "3️⃣" in texto or "fechas" in texto:
                    respuesta_texto = (
                        "¡Que no se te pasen las fechas clave! 📅 Toma nota de nuestra convocatoria más reciente para que asegures tu lugar a tiempo: ||"
                        "📝 <b>Entrega de Fichas:</b> Tenemos periodo abierto del 2 de junio al 20 de julio. ¡No lo dejes para el último día! ||"
                        "💻 <b>Curso de preparación:</b> Miércoles 23 de julio (modalidad en línea para tu comodidad). ||"
                        "✍️ <b>Examen de Admisión:</b> Se aplicará de forma presencial los días viernes 25 y sábado 26 de julio en nuestras instalaciones del ITSA. ||"
                        "📢 <b>Resultados:</b> El lunes 28 de julio a las 15:00 horas publicaremos la lista de aceptados en nuestra página y en tu correo electrónico. ||"
                        "Puedes revisar nuestra convocatoria completa en <a href='https://atlixco.tecnm.mx/' target='_blank'>atlixco.tecnm.mx</a>. ¿Te ayudo con los costos o quieres explorar las carreras?"
                    )
                    opciones_lista = [
                        "4️⃣ Costos",
                        "1️⃣ Información de carreras",
                        "🎯 Menú Principal"
                    ]

                elif "4️⃣" in texto or "costos" in texto:
                    respuesta_texto = (
                        "¡Hablemos de tu inversión educativa! 🤩 Déjame decirte que estudiar en el ITSA es una de las opciones más accesibles y con mejor nivel académico de la región. Te desgloso los costos oficiales aproximados para nuevo ingreso: ||"
                        "💳 <b>Ficha de admisión y examen:</b> $860.00 pesos (ojo, en rondas extraordinarias podría llegar a $1,340.00, ¡así que aprovecha a tiempo!). ||"
                        "📚 <b>Curso propedéutico:</b> De $725.00 a $2,130.00 pesos, dependiendo de la convocatoria vigente. ||"
                        "🏫 <b>Inscripción Semestral:</b> Entre $1,300.00 y $1,375.00 pesos. ¡Y lo mejor de todo es que NO cobramos mensualidades! ||"
                        "🪪 <b>Credencial de estudiante:</b> Solo de $75.00 a $80.00 pesos. ||"
                        "💡 <b>¡Súper Tip!</b> En algunas convocatorias lanzamos un <b>Pago Único Anticipado</b> por aproximadamente $2,240.00 pesos que ya te incluye inscripción, examen diagnóstico y propedéutico. ¡Un gran ahorro! ||"
                        "¿Quieres que te cuente sobre nuestro departamento de idiomas o prefieres ver las fechas de admisión?"
                    )
                    opciones_lista = [
                        "5️⃣ Lenguas extranjeras",
                        "3️⃣ Fechas de admisión",
                        "🎯 Menú Principal"
                    ]

                elif "5️⃣" in texto or "cursos de idioma" in texto:
                    respuesta_texto = (
                        "¡Yes! ¡Oui! 🌎 Hoy en día dominar otro idioma ya no es un lujo, ¡es una necesidad para destacar en el mundo profesional y viajar! En el ITSA tenemos un Departamento de Lenguas Extranjeras de primer nivel. Te cuento cómo funciona: ||"
                        "🗣️ <b>¿Qué idiomas ofrecemos?</b> El <b>Inglés</b> es nuestra lengua principal y es requisito para titularte en todas las ingenierías. Pero, ¡atención! Si vas para la Licenciatura en Gastronomía, tienes el privilegio de elegir entre estudiar Inglés o Francés. Solo piénsalo bien, porque una vez que inicias un idioma, no se permiten cambios (permutas). ||"
                        "💰 <b>Inversión por nivel:</b> El curso regular o semipresencial es súper accesible, solo $1,000.00 pesos. Si prefieres avanzar rápido, el curso intensivo está en $2,000.00 pesos. ||"
                        "💻 <b>Material digital:</b> Olvídate de cargar libros pesados. Aquí usamos plataformas interactivas (como la plataforma Sonhos) que cuestan alrededor de $525.00 pesos por nivel. ||"
                        "¡Prepárate para ser un profesional sin fronteras! ✈️ ¿Te gustaría volver al menú de carreras o revisar los costos?"
                    )
                    opciones_lista = [
                        "1️⃣ Información de carreras",
                        "4️⃣ Costos",
                        "🎯 Menú Principal"
                    ]
                 # ==========================================
                 # FLUJO 6: ACTIVIDADES EXTRAESCOLARES
                # ==========================================
                elif "6️⃣" in texto or "extraescolares" in texto:
                    estado_conversacion["paso_actual"] = "menu_principal"
                    respuesta_texto = (
                        "¡No todo es estar en el salón de clases! 🏃‍♂️🎨 En el ITSA sabemos que la vida universitaria debe ser increíble, por eso tenemos un montón de Actividades Extraescolares donde harás amigos, liberarás estrés y, lo mejor de todo, ¡te darán créditos complementarios para tu titulación! ||"
                        "Tenemos opciones para todos los gustos: ||"
                        "🏆 <b>Deportivas:</b> Saca tu lado competitivo en nuestros equipos de Fútbol (varonil y femenil), Baloncesto, Voleibol, Ping Pong, Ajedrez o incluso Football Americano y Flag. ¡Únete a la Porra Lince! ||"
                        "🎭 <b>Culturales y Artísticas:</b> Si lo tuyo es el arte, te encantará el Taller de Pirograbado y Dibujo, Danza Folklórica, Teatro, Banda de Música y hasta nuestro taller de Radio. ||"
                        "🇲🇽 <b>Cívicas e Inclusivas:</b> Participa con orgullo en la Escolta o aprende Lenguaje de Señas Mexicana, una habilidad increíble para tu currículum. ||"
                        "Recuerda que cada taller tiene cupo limitado y puedes inscribirte en el portal oficial <a href='https://atlixco.tecnm.mx/alumnos/complementarias' target='_blank'>atlixco.tecnm.mx/alumnos/complementarias</a>. ||"
                        "¿Qué te parece? ¡Serás un Lince de corazón! 🐾 ¿Te cuento del proceso de inscripción o prefieres ver las carreras que ofrecemos?"
                    )
                    opciones_lista = [
                        "2️⃣ Proceso de inscripción",
                        "1️⃣ Información de carreras",
                        "🎯 Menú Principal"
                    ]

                elif "🎯 menú principal" in texto or "menu" in texto:
                    respuesta_texto = MENU_PRINCIPAL_TEXTO
                    opciones_lista = MENU_PRINCIPAL_OPCIONES

                # PREGUNTA LIBRE (USANDO LA API DE GROQ CON LABIA)
                    # PREGUNTA LIBRE (USANDO LA API DE GROQ CON LABIA)
                else:
                    try:
                        chat_completion = client.chat.completions.create(
                            messages=[
                                {"role": "system",
                                 "content": "Eres ItsaBot, un asistente de admisiones del ITSA. Tienes una personalidad carismática, alegre y servicial. Usa emojis para expresarte. Si no sabes algo, dirige amablemente al WhatsApp 244 120 90 50., ademas se breve y amable"},
                                {"role": "user", "content": texto},
                            ],
                            model="llama-3.1-8b-instant",
                        )
                        respuesta_texto = chat_completion.choices[0].message.content
                        opciones_lista = ["🎯 Menú Principal"]
                    except Exception as e:
                        # 👉 ESTA ES LA LÍNEA NUEVA: Imprimirá en tu terminal por qué falló Groq
                        print(f"❌ ERROR DE GROQ: {e}")

                        respuesta_texto = "Ay, caray. 😅 Tuve un problema técnico momentáneo. Por favor contacta a admisiones al 244 120 90 50."
                        opciones_lista = MENU_PRINCIPAL_OPCIONES


            # ==========================================
            # 3. GENERAR AUDIO Y RESPUESTA FINAL HTML
            # ==========================================
            try:
                # Quitamos etiquetas HTML y reemplazamos los '||' por puntos para que la voz haga pausas
                t_hablar = re.sub(r'<[^>]+>', '', respuesta_texto.replace("||", ". "))
                audio_b64 = await generar_audio_neuronal(t_hablar)

                # Enviamos la respuesta cambiando '||' por <br><br> para que se vea bonito en pantalla
                return {
                    "respuesta": respuesta_texto,
                    "opciones": opciones_lista,
                    "audio": audio_b64
                }
            except:
                return {
                    "respuesta": respuesta_texto,
                    "opciones": opciones_lista,
                    "audio": None
                }


def get_db_connection():
    """Crea y devuelve una conexión a la base de datos usando variables de entorno."""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            collation=os.getenv("DB_COLLATION")
        )
    except mysql.connector.Error as err:
        print(f"❌ Error crítico de conexión: {err}")
        return None

def guardar_en_mysql(datos):
    try:
        conexion = get_db_connection()
        if not conexion: return
        cursor = conexion.cursor()
        pin_plano = datos.get("pin")
        pin_hash = hashlib.sha256(pin_plano.encode('utf-8')).hexdigest()

        sql = """INSERT INTO prospectos 
                 (nombre_completo, correo, telefono, edad, id_bachillerato, id_carrera_interes, canal, pin_seguridad) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""

        valores = (
            datos.get("nombre"),
            datos.get("correo"),
            datos.get("telefono"),
            datos.get("edad"),
            datos.get("id_bachillerato"),  # ID obtenido de la BD
            datos.get("id_carrera"),  # ID obtenido de la BD
            "chatbot",
            pin_hash
        )

        cursor.execute(sql, valores)
        conexion.commit()
        cursor.close()
        conexion.close()
        print("✅ Registro guardado con éxito en la base de datos.")
    except Exception as e:
        print(f"❌ Error crítico al guardar: {e}")


def enviar_correo_recuperacion(correo_destino, codigo_generado):
    # Ahora las leemos de forma segura
    correo_bot = os.getenv("EMAIL_BOT")
    password_bot = os.getenv("PASSWORD_BOT")

    mensaje = MIMEMultipart()
    mensaje['From'] = f"LinceBot ITSA <{correo_bot}>"
    mensaje['To'] = correo_destino
    mensaje['Subject'] = "Código de Recuperación - Admisiones ITSA"

    cuerpo = f"""
    Hola,

    Se ha solicitado recuperar el PIN de acceso para tu proceso de admisión.
    Tu código de seguridad es: {codigo_generado}

    Por favor, escribe este código en el chat para continuar.

    Saludos,
    LinceBot 🐾
    """
    mensaje.attach(MIMEText(cuerpo, 'plain'))

    try:
        # Nos conectamos al servidor de Gmail
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()  # Encriptamos la conexión
        servidor.login(correo_bot, password_bot)

        # Enviamos el correo
        servidor.send_message(mensaje)
        servidor.quit()
        return True
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
        return False




# Esto le dice a tu servidor que cuando alguien entre a la raíz, muestre el frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")