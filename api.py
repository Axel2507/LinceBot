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
        database=os.getenv("DB_NAME"),
        collation="utf8mb4_unicode_ci"
    )


# --- RUTAS DE TU API (Las "ventanillas") ---

# Ruta de prueba para saber si funciona
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"mensaje": "La API está funcionando correctamente"})

#   Iniciar Sesión
@app.route('/api/login', methods=['POST'])
def login():
    datos = request.json
    correo = datos.get("correo")
    password_hash = datos.get("password") # La app ya lo manda hasheado

    try:
        conexion = conectar_bd()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s AND activo = 1 LIMIT 1", (correo,))
        user = cursor.fetchone()

        if user and user.get("password") == password_hash:
            return jsonify(user), 200
        else:
            return jsonify({"error": "Credenciales inválidas"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conexion' in locals() and conexion.is_connected(): conexion.close()

# 3. Ruta para registrar usuarios
@app.route('/api/register', methods=['POST'])
def register():
    datos = request.json
    nombre = datos.get("nombre")
    correo = datos.get("correo")
    password_hash = datos.get("password")

    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, password) VALUES (%s, %s, %s)",
            (nombre, correo, password_hash)
        )
        conexion.commit()
        return jsonify({"mensaje": "Registrado correctamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conexion' in locals() and conexion.is_connected(): conexion.close()


# 4. Ruta para obtener prospectos (con filtros de carrera y búsqueda)
@app.route('/api/prospectos', methods=['GET'])
def get_prospectos():
    carrera = request.args.get("carrera")
    busqueda = request.args.get("busqueda")

    try:
        conexion = conectar_bd()
        cursor = conexion.cursor(dictionary=True)

        query = "SELECT * FROM v_prospectos WHERE 1=1"
        params = []

        if carrera:
            query += " AND nombre_carrera = %s"
            params.append(carrera)

        if busqueda:
            query += " AND (nombre_completo LIKE %s OR correo LIKE %s)"
            termino = f"%{busqueda}%"
            params.extend([termino, termino])

        query += " ORDER BY fecha_registro DESC"

        cursor.execute(query, tuple(params))
        prospectos = cursor.fetchall()
        return jsonify(prospectos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conexion' in locals() and conexion.is_connected(): conexion.close()

# 5. Ruta para obtener estadísticas
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor(dictionary=True)
        stats = {}

        # Stats generales
        cursor.execute("SELECT * FROM v_estadisticas")
        v_stats = cursor.fetchone()

        if v_stats:
            stats["total"] = v_stats.get("total_prospectos", 0)
            stats["mes"] = v_stats.get("prospectos_mes_actual", 0)
            stats["bachilleratos"] = v_stats.get("bachilleratos_distintos", 0)
            stats["carrera_top"] = v_stats.get("carrera_mas_popular", "N/A")
            stats["finalizados"] = v_stats.get("prospectos_finalizados", 0)

        # Stats de bachilleratos
        cursor.execute("SELECT nombre_bachillerato AS bach, COUNT(*) AS cnt FROM v_prospectos GROUP BY nombre_bachillerato ORDER BY cnt DESC LIMIT 6")
        stats["bach_stats"] = cursor.fetchall()

        # Stats de carreras
        cursor.execute("SELECT nombre_carrera AS nombre_carrera, COUNT(*) AS cnt FROM v_prospectos GROUP BY nombre_carrera ORDER BY cnt DESC LIMIT 6")
        stats["carrera_stats"] = cursor.fetchall()

        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conexion' in locals() and conexion.is_connected(): conexion.close()

# --- ARRANQUE DEL SERVIDOR ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)