import mysql.connector
from mysql.connector import Error
from tkinter import messagebox
import hashlib

class Database:
    def __init__(self):
        self.conn = None
        self._connect()

    def _connect(self):
        try:
            self.conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="blaky2507",
                database="itsabot",
                port=3306,
                collation="utf8mb4_unicode_ci",
                connection_timeout=6,
            )
        except Error as e:
            messagebox.showerror("Error de conexion", f"No se pudo conectar a la base de datos:\n\n{e}")

    def _ok(self) -> bool:
        try:
            if self.conn and self.conn.is_connected(): return True
            self._connect()
            return self.conn is not None
        except Exception:
            return False

    def login(self, correo: str, password: str):
        if not self._ok(): return None
        try:
            cur = self.conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM usuarios WHERE correo = %s AND activo = 1 LIMIT 1", (correo,))
            user = cur.fetchone()
            cur.close()
            if not user: return None
            hash_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if user.get("password") == hash_password:
                return user
            return None
        except Exception as e:
            messagebox.showerror("Error login", str(e))
            return None

    def register(self, nombre, correo, password) -> bool:
        if not self._ok(): return False
        try:
            hash_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO usuarios (nombre, correo, password) VALUES (%s, %s, %s)",
                (nombre, correo, hash_password)
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            messagebox.showerror("Error al registrar", str(e))
            return False

    def get_prospectos(self, filtro_carrera_nombre=None):
        if not self._ok(): return []
        try:
            cur = self.conn.cursor(dictionary=True)
            if filtro_carrera_nombre and filtro_carrera_nombre != "Todas las carreras":
                cur.execute("SELECT * FROM v_prospectos WHERE nombre_carrera = %s ORDER BY fecha_registro DESC",
                            (filtro_carrera_nombre,))
            else:
                cur.execute("SELECT * FROM v_prospectos ORDER BY fecha_registro DESC")
            rows = cur.fetchall()
            cur.close()
            return rows
        except Exception as e:
            messagebox.showerror("Error consulta", str(e))
            return []

    def get_stats(self) -> dict:
        if not self._ok(): return {}
        stats = {}
        try:
            cur = self.conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM v_estadisticas")
            v_stats = cur.fetchone()

            if v_stats:
                stats["total"] = v_stats["total_prospectos"]
                stats["mes"] = v_stats["prospectos_mes_actual"]
                stats["bachilleratos"] = v_stats["bachilleratos_distintos"]
                stats["carrera_top"] = v_stats["carrera_mas_popular"]
                stats["finalizados"] = v_stats.get("prospectos_finalizados", 0)

            cur.execute("SELECT nombre_bachillerato AS bach, COUNT(*) AS cnt FROM v_prospectos GROUP BY nombre_bachillerato ORDER BY cnt DESC LIMIT 6")
            stats["bach_stats"] = cur.fetchall()

            cur.execute("SELECT nombre_carrera AS nombre_carrera, COUNT(*) AS cnt FROM v_prospectos GROUP BY nombre_carrera ORDER BY cnt DESC LIMIT 6")
            stats["carrera_stats"] = cur.fetchall()

            cur.close()
        except Exception as e:
            messagebox.showerror("Error estadisticas", str(e))
        return stats