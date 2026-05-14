import tkinter as tk
from tkinter import ttk

# PALETA DE COLORES Y TIPOGRAFIA
C_VINO       = "#7A0000"
C_ROJO_BTN   = "#B71C1C"
C_ROJO_HOV   = "#C62828"
C_BLANCO     = "#FFFFFF"
C_GRIS_BG    = "#F5F5F5"
C_GRIS_CARD  = "#FFFFFF"
C_GRIS_HDR   = "#FAFAFA"
C_GRIS_BORDE = "#E0E0E0"
C_GRIS_ROW   = "#F9F9F9"
C_TEXTO      = "#212121"
C_SUBTEXTO   = "#757575"
C_AZUL_TAG   = "#1565C0"
C_VERDE_TAG  = "#2E7D32"
C_NARANJO    = "#E65100"
C_MORADO_TAG = "#6A1B9A"

F_TITULO = ("Georgia",    22, "bold")
F_NAV    = ("Helvetica",  11, "bold")
F_H2     = ("Helvetica",  15, "bold")
F_H3     = ("Helvetica",  12, "bold")
F_BODY   = ("Helvetica",  10)
F_BOLD   = ("Helvetica",  10, "bold")
F_SMALL  = ("Helvetica",   9)
F_STAT_N = ("Helvetica",  26, "bold")
F_STAT_L = ("Helvetica",   8)

# DICCIONARIOS
# DICCIONARIOS
CARRERAS_NOMBRE = {
    1: "Ing. en Sistemas", 2: "Electromecánica", 3: "Bioquímica", 4: "Mecatrónica",
    5: "Ing. Industrial", 6: "Gastronomía", 7: "Maestría en Ingeniería", 8: "Maestría en IA", None: "Por definir",
}

DICCIONARIO_CARRERAS = {
    "Todas las carreras": None,
    "Ing. en Sistemas": 1,
    "Electromecánica": 2,
    "Bioquímica": 3,
    "Mecatrónica": 4,
    "Ing. Industrial": 5,
    "Gastronomía": 6,
    "Maestría en Ingeniería": 7,
    "Maestría en IA": 8
}


# HELPERS UI
def btn_pill(parent, text, cmd, bg=C_ROJO_BTN, fg=C_BLANCO, font=F_BOLD, px=20, py=7):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=font, relief="flat", bd=0, cursor="hand2", padx=px, pady=py)
    b.bind("<Enter>", lambda e, _bg=bg: b.config(bg=C_ROJO_HOV if _bg == C_ROJO_BTN else _bg))
    b.bind("<Leave>", lambda e, _bg=bg: b.config(bg=_bg))
    return b

def card_frame(parent):
    return tk.Frame(parent, bg=C_GRIS_CARD, highlightbackground=C_GRIS_BORDE, highlightthickness=1)

def h_sep(parent):
    tk.Frame(parent, bg=C_GRIS_BORDE, height=1).pack(fill="x")

def tag_pill(parent, text, bg):
    return tk.Label(parent, text=text, bg=bg, fg=C_BLANCO, font=F_SMALL, padx=6, pady=2)

def apply_style(root):
    style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("TCombobox", fieldbackground="#F0F0F0", background="#F0F0F0", relief="flat")