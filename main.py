from fastapi import FastAPI
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


estado_conversacion = {
    "paso_actual": "saludo_inicial",
    "datos_usuario": {},
    "codigo_verificacion": None # Para guardar el código temporal del correo
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
        conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507", database="itsabot", collation="utf8mb4_unicode_ci")
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
        conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507", database="itsabot", collation="utf8mb4_unicode_ci")
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
            paso = estado_conversacion["paso_actual"]

            # --- DEFINICIÓN DEL MENÚ PRINCIPAL UNIFICADO ---
            # Esto lo usaremos en varios lugares para que siempre sea igual
            MENU_PRINCIPAL_TEXTO = "¡Excelente! Ya estamos en el menú principal. ✨||¿En qué puedo ayudarte el día de hoy? Tengo toda esta información para ti:"
            MENU_PRINCIPAL_OPCIONES = [
                "1️⃣ Información de carreras",
                "2️⃣ Proceso de inscripción",
                "3️⃣ Fechas de admisión",
                "4️⃣ Costos",
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
                conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507",database="itsabot", collation="utf8mb4_unicode_ci")
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
                        conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507",database="itsabot", collation="utf8mb4_unicode_ci")

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
                    conexion = mysql.connector.connect(host="localhost", user="root", password="blaky2507",database="itsabot", collation="utf8mb4_unicode_ci")
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
                    opciones_lista = ["Sistemas", "Mecatrónica", "Industrial", "Bioquímica", "Electromecánica",
                                      "Gastronomía", "🎯 Menú Principal"]

                elif "2️⃣" in texto or "inscripción" in texto or "inscripcion" in texto:
                    respuesta_texto = "El proceso es muy sencillo:||1. Realizas tu registro aquí.||2. Pagas tu ficha.||3. Presentas examen de admisión.||4. Entrega de documentos.||¿Te gustaría saber los requisitos de documentos?"
                    opciones_lista = ["Requisitos", "🎯 Menú Principal"]

                elif "3️⃣" in texto or "fechas" in texto:
                    respuesta_texto = "📅 El próximo examen de admisión es el **24 de Junio**.||La entrega de fichas cierra el 15 de Junio. ¡No te quedes fuera!"
                    opciones_lista = ["🎯 Menú Principal"]

                elif "4️⃣" in texto or "costos" in texto:
                    respuesta_texto = "💳 La ficha de admisión tiene un costo de **$850 MXN**.||La inscripción semestral es de **$2,400 MXN**. ¿Deseas información de becas?"
                    opciones_lista = ["Becas", "🎯 Menú Principal"]

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



def guardar_en_mysql(datos):
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="blaky2507",
            database="itsabot",
            collation="utf8mb4_unicode_ci"
        )
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