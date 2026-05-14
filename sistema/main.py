import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

# Importamos nuestros propios módulos
from database import Database
from config_ui import *
from main_window import MainWin

class LoginRoot(tk.Tk):
    """
    Ventana de login construida sobre la raíz Tk.
    """

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.title("Sistema ITSA — Iniciar Sesión")  # Nuevo nombre
        self.geometry("860x520")
        self.resizable(False, False)
        self.configure(bg=C_VINO)

        # Centrar en pantalla
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 860) // 2
        y = (self.winfo_screenheight() - 520) // 2
        self.geometry(f"860x520+{x}+{y}")

        # --- AQUÍ CARGAMOS LA IMAGEN DE FONDO ---
        try:
            # Asegúrate de tener una imagen llamada "fondo_login.jpg" en la misma carpeta
            self.img_obj = Image.open("fondo_login.png")
            self.img_obj = self.img_obj.resize((860, 520), Image.Resampling.LANCZOS)
            self.img_tk = ImageTk.PhotoImage(self.img_obj)

            # Ponemos el Label de fondo primero para que quede atrás de todo
            self.lbl_fondo = tk.Label(self, image=self.img_tk)
            self.lbl_fondo.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:
            print(f"⚠️ No se pudo cargar la imagen de fondo: {e}")
            # Si falla la imagen, simplemente se queda el fondo C_VINO que configuramos arriba
        # ------------------------------------------

        self._ui()

    def _ui(self):
        # Tarjeta blanca central
        f = tk.Frame(self, bg=C_BLANCO)
        f.place(relx=.5, rely=.5, anchor="center", width=370, height=330)

        # Franja decorativa roja en la tarjeta
        tk.Frame(f, bg=C_VINO, height=4).pack(fill="x")

        tk.Label(f, text="Iniciar Sesión", bg=C_BLANCO, fg=C_VINO,
                 font=("Georgia", 18, "bold")).pack(pady=(22, 16))

        self._e_correo = self._field(f, "Correo electrónico", False)
        self._e_correo.pack(fill="x", padx=30, ipady=9, pady=(0, 10))

        self._e_pass = self._field(f, "Contraseña", True)
        self._e_pass.pack(fill="x", padx=30, ipady=9, pady=(0, 2))

        # --- NUEVO: CHECKBOX PARA VER CONTRASEÑA ---
        self.show_pwd_var = tk.BooleanVar()
        self.chk_show = tk.Checkbutton(f, text="Mostrar contraseña",
                                       variable=self.show_pwd_var, command=self._toggle_pwd,
                                       bg=C_GRIS_CARD, fg=C_SUBTEXTO, font=F_SMALL,
                                       activebackground=C_GRIS_CARD, cursor="hand2")
        self.chk_show.pack(anchor="w",padx=30, pady=(0, 10))

        btn_pill(f, "  Entrar  ", self._login, py=9).pack(
            fill="x", padx=30, pady=(0, 10))

        lnk = tk.Label(f, text="Crear cuenta", bg=C_BLANCO,
                       fg=C_SUBTEXTO, font=F_BOLD, cursor="hand2")
        lnk.pack(pady=(5, 0))
        lnk.bind("<Button-1>", lambda _: self._ir_reg())
        lnk.bind("<Enter>", lambda _: lnk.config(fg=C_VINO))
        lnk.bind("<Leave>", lambda _: lnk.config(fg=C_SUBTEXTO))

    def _field(self, parent, ph, secret):
        e = tk.Entry(parent, font=F_BODY, bg="#F0F0F0", fg=C_SUBTEXTO,
                     relief="flat", bd=0, insertbackground=C_VINO)
        e.insert(0, ph)
        if secret:
            e.bind("<FocusIn>", lambda _: (e.get() == ph and (
                e.delete(0, "end"), e.config(show="*", fg=C_TEXTO))))
            e.bind("<FocusOut>", lambda _: (not e.get() and (
                e.config(show="", fg=C_SUBTEXTO), e.insert(0, ph))))
        else:
            e.bind("<FocusIn>", lambda _: (e.get() == ph and (
                e.delete(0, "end"), e.config(fg=C_TEXTO))))
            e.bind("<FocusOut>", lambda _: (not e.get() and (
                e.config(fg=C_SUBTEXTO), e.insert(0, ph))))
        return e

    def _login(self):
        c = self._e_correo.get().strip()
        p = self._e_pass.get().strip()
        if c in ("", "Correo electrónico") or p in ("", "Contraseña"):
            messagebox.showwarning("Campos vacíos",
                                   "Ingresa correo y contraseña.", parent=self)
            return
        user = self.db.login(c, p)
        if user:
            self._abrir_main(user)
        else:
            messagebox.showerror("Acceso denegado",
                                 "Correo o contraseña incorrectos.", parent=self)

    def _ir_reg(self):
        self.withdraw()
        reg = RegisterRoot(self, self.db)
        reg.grab_set()

    def _abrir_main(self, user):
        self.destroy()
        root_main = tk.Tk()
        root_main.withdraw()
        _apply_style(root_main)
        app = MainWin(root_main, self.db, user)
        app.protocol("WM_DELETE_WINDOW", root_main.destroy)
        root_main.mainloop()

    def _toggle_pwd(self):
        """Alterna entre ocultar (*) y mostrar (texto plano) la contraseña"""
        if self.show_pwd_var.get():
            self._e_pass.config(show="")
        else:
            self._e_pass.config(show="*")



class RegisterRoot(tk.Toplevel):
    """
    Registro de usuario (Tarjeta centrada con fondo, validaciones y ojito)
    """

    def __init__(self, login_root: LoginRoot, db: Database):
        super().__init__(login_root)
        self.login_root = login_root
        self.db = db
        self.title("Sistema ITSA — Crear Cuenta")
        self.geometry("860x540")
        self.resizable(False, False)

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 860) // 2
        y = (self.winfo_screenheight() - 540) // 2
        self.geometry(f"860x540+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self._volver)

        # --- CARGAMOS LA IMAGEN DE FONDO ---
        try:
            self.img_obj = Image.open("fondo_formulario.png")  # Reutilizamos la misma imagen
            self.img_obj = self.img_obj.resize((860, 540), Image.Resampling.LANCZOS)
            self.img_tk = ImageTk.PhotoImage(self.img_obj)

            self.lbl_fondo = tk.Label(self, image=self.img_tk)
            self.lbl_fondo.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:
            print(f"⚠️ No se pudo cargar la imagen de fondo: {e}")

        self._ui()

    def _ui(self):
        # Tarjeta blanca central
        f = tk.Frame(self, bg=C_BLANCO)
        f.place(relx=.5, rely=.5, anchor="center", width=380, height=440)

        # Franja decorativa roja
        tk.Frame(f, bg=C_VINO, height=4).pack(fill="x")

        tk.Label(f, text="Crear Cuenta", bg=C_BLANCO, fg=C_VINO,
                 font=("Georgia", 18, "bold")).pack(pady=(20, 5))
        tk.Label(f, text="Sistema de Admisiones ITSA",
                 bg=C_BLANCO, fg=C_SUBTEXTO, font=F_SMALL).pack(pady=(0, 20))

        self._ef = {}
        self.show_pwd = False  # Estado del ojito de contraseña

        # CAMPOS CON LOGICA MEJORADA
        campos = [
            ("nombre", "Nombre completo", False),
            ("correo", "Correo electrónico", False),
            ("password", "Contraseña", True),
            ("confirm", "Confirmar contraseña", True),
        ]

        for key, ph, sec in campos:
            # Contenedor para el Entry y el Icono
            frame_input = tk.Frame(f, bg="#F0F0F0")
            frame_input.pack(fill="x", padx=30, pady=6)

            e = tk.Entry(frame_input, font=F_BODY, bg="#F0F0F0",
                         fg=C_SUBTEXTO, relief="flat", bd=0, insertbackground=C_VINO)
            e.insert(0, ph)

            if sec:
                e.bind("<FocusIn>", lambda ev, en=e, p=ph: self._on_focus_in_sec(en, p))
                e.bind("<FocusOut>", lambda ev, en=e, p=ph: self._on_focus_out_sec(en, p))

                # Agregar el Ojito solo al primer campo de contraseña
                if key == "password":
                    self.lbl_ojo = tk.Label(frame_input, text="👁️", bg="#F0F0F0", fg=C_SUBTEXTO, cursor="hand2")
                    self.lbl_ojo.pack(side="right", padx=10)
                    self.lbl_ojo.bind("<Button-1>", self._toggle_pwd)
            else:
                e.bind("<FocusIn>", lambda ev, en=e, p=ph: self._on_focus_in(en, p))
                e.bind("<FocusOut>", lambda ev, en=e, p=ph: self._on_focus_out(en, p))

            e.pack(side="left", fill="both", expand=True, padx=10, ipady=8)
            self._ef[key] = e

        btn_pill(f, "Registrarse", self._reg, py=10).pack(fill="x", padx=30, pady=(20, 10))

        lnk = tk.Label(f, text="¿Ya tienes cuenta? Inicia sesión",
                       bg=C_BLANCO, fg=C_SUBTEXTO, font=F_SMALL, cursor="hand2")
        lnk.pack(pady=5)
        lnk.bind("<Button-1>", lambda _: self._volver())
        lnk.bind("<Enter>", lambda _: lnk.config(fg=C_VINO))
        lnk.bind("<Leave>", lambda _: lnk.config(fg=C_SUBTEXTO))

    # --- FUNCIONES PARA QUITAR/PONER EL TEXTO DE RELLENO ---
    def _on_focus_in(self, e, ph):
        if e.get() == ph:
            e.delete(0, "end")
            e.config(fg=C_TEXTO)

    def _on_focus_out(self, e, ph):
        if not e.get():
            e.config(fg=C_SUBTEXTO)
            e.insert(0, ph)

    def _on_focus_in_sec(self, e, ph):
        if e.get() == ph:
            e.delete(0, "end")
            e.config(fg=C_TEXTO)
            if not self.show_pwd:
                e.config(show="*")  # Ocultar texto solo si el ojito no está activo

    def _on_focus_out_sec(self, e, ph):
        if not e.get():
            e.config(show="")  # Mostrar el texto normal para que se lea la palabra "Contraseña"
            e.config(fg=C_SUBTEXTO)
            e.insert(0, ph)

    def _toggle_pwd(self, event):
        self.show_pwd = not self.show_pwd
        self.lbl_ojo.config(text="🙈" if self.show_pwd else "👁️")

        pwd = self._ef["password"]
        conf = self._ef["confirm"]

        if pwd.get() != "Contraseña":
            pwd.config(show="" if self.show_pwd else "*")
        if conf.get() != "Confirmar contraseña":
            conf.config(show="" if self.show_pwd else "*")

    def _volver(self):
        self.destroy()
        self.login_root.deiconify()

    def _reg(self):
        import re  # Importado aquí para las validaciones

        ph = {"Nombre completo", "Correo electrónico", "Contraseña", "Confirmar contraseña"}
        vals = {k: e.get().strip() for k, e in self._ef.items()}

        # 1. Validar campos vacíos
        if any(v in ph or not v for v in vals.values()):
            messagebox.showwarning("Campos incompletos", "Completa todos los campos.", parent=self)
            return

        # 2. Validar Nombre (Solo letras y espacios, funciona con acentos)
        if not all(c.isalpha() or c.isspace() for c in vals["nombre"]):
            messagebox.showerror("Error de formato", "El nombre solo debe contener letras.", parent=self)
            return

        # 3. Validar Correo (Usa expresión regular para el formato @ y .)
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", vals["correo"]):
            messagebox.showerror("Error de formato", "Ingresa un correo electrónico válido.", parent=self)
            return

        # 4. Validar Contraseña Segura (Mínimo 8 letras, 1 mayúscula, 1 número)
        pwd = vals["password"]
        if len(pwd) < 8 or not re.search(r"[A-Z]", pwd) or not re.search(r"\d", pwd):
            mensaje = "La contraseña es muy débil. Debe contener:\n\n• Al menos 8 caracteres\n• Una letra mayúscula\n• Un número"
            messagebox.showerror("Contraseña débil", mensaje, parent=self)
            return

        # 5. Validar que coincidan
        if vals["password"] != vals["confirm"]:
            messagebox.showerror("Error", "Las contraseñas no coinciden.", parent=self)
            return

        # Si todo es correcto, registramos en la BD
        if self.db.register(vals["nombre"], vals["correo"], vals["password"]):
            messagebox.showinfo("Cuenta creada", "Registro exitoso. Ahora puedes iniciar sesión.", parent=self)
            self._volver()


def _apply_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TCombobox",
                    fieldbackground="#F0F0F0",
                    background="#F0F0F0",
                    relief="flat")
    style.configure("Vertical.TScrollbar",
                    troughcolor=C_GRIS_BG,
                    background="#BDBDBD",
                    relief="flat")


if __name__ == "__main__":
    db = Database()
    app = LoginRoot(db)
    _apply_style(app)
    app.mainloop()
