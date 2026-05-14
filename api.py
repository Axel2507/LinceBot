from flask import Flask, jsonify, request
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()  # Carga tus contraseñas del .env

app = Flask(__name__)


# Función para conectarse a la BD
def conectar_bd():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# --- RUTAS DE TU API (Las "ventanillas") ---

# Ruta de prueba para saber si funciona
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"mensaje": "La API está funcionando correctamente"})


# Ruta para que el .exe pida información (Ejemplo: obtener usuarios)
@app.route('/obtener_usuarios', methods=['GET'])
def obtener_usuarios():
    conexion = conectar_bd()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT * FROM tabla_usuarios")  # Cambia esto por tu tabla real
    resultados = cursor.fetchall()

    cursor.close()
    conexion.close()

    return jsonify({"usuarios": resultados})


# Arrancar el servidor web
if __name__ == '__main__':
    # host='0.0.0.0' permite que acepte conexiones desde internet
    # port=5000 es el puerto que usaremos
    app.run(host='0.0.0.0', port=5000)