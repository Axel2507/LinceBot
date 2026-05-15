import requests
from tkinter import messagebox
import hashlib

URL_API = "http://18.188.220.164:5001"

class Database:
    def __init__(self):
        self.api_url = URL_API



    def login(self, correo: str, password: str):
        try:
            hash_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            respuesta = requests.post(
                f"{self.api_url}/api/login",
                json={"correo": correo, "password": hash_password},
                timeout=5
            )
            if respuesta.status_code == 200:
                return respuesta.json()  # La API nos devuelve los datos del usuario
            return None
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error login", f"No se pudo conectar a la API:\n\n{e}")
            return None

    def register(self, nombre, correo, password) -> bool:
        try:
            hash_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

            respuesta = requests.post(
                f"{self.api_url}/api/register",
                json={"nombre": nombre, "correo": correo, "password": hash_password},
                timeout=5
            )

            # Si la API responde con un 200 OK o 201 Created, el registro fue un éxito
            return respuesta.status_code in [200, 201]

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error al registrar", f"No se pudo conectar a la API:\n\n{e}")
            return False

    def get_prospectos(self, filtro_carrera_nombre=None):
        try:
            parametros = {}
            # Si hay un filtro, se lo mandamos a la API en la URL
            if filtro_carrera_nombre and filtro_carrera_nombre != "Todas las carreras":
                parametros = {"carrera": filtro_carrera_nombre}

            respuesta = requests.get(
                f"{self.api_url}/api/prospectos",
                params=parametros,
                timeout=5
            )

            if respuesta.status_code == 200:
                return respuesta.json()  # Devuelve la lista de prospectos
            return []

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error consulta", f"Fallo al obtener prospectos:\n\n{e}")
            return []

    def get_stats(self) -> dict:
        try:
            respuesta = requests.get(f"{self.api_url}/api/stats", timeout=5)

            if respuesta.status_code == 200:
                return respuesta.json()  # Devuelve el diccionario con las estadísticas
            return {}

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error estadísticas", f"Fallo al obtener estadísticas:\n\n{e}")
            return {}

    def get_prospectos(self, filtro_carrera_nombre=None, busqueda=""):
        try:
            parametros = {}
            if filtro_carrera_nombre and filtro_carrera_nombre != "Todas las carreras":
                parametros["carrera"] = filtro_carrera_nombre

            if busqueda:
                parametros["busqueda"] = busqueda

            respuesta = requests.get(
                f"{self.api_url}/api/prospectos",
                params=parametros,
                timeout=5
            )

            if respuesta.status_code == 200:
                return respuesta.json()
            return []
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error consulta", f"Fallo al obtener prospectos:\n\n{e}")
            return []