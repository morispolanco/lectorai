import streamlit as st
import requests
import sqlite3
import hashlib
from streamlit import secrets

# Configuración inicial
st.title("Comprensión Lectora para Bachillerato")

# Conexión a SQLite
conn = sqlite3.connect("estudiantes.db")
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute("""
    CREATE TABLE IF NOT EXISTS estudiantes (
        username TEXT PRIMARY KEY,
        password TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS progreso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        fecha DATE,
        nivel_dificultad INTEGER,
        puntuacion INTEGER,
        categoria TEXT,
        FOREIGN KEY(username) REFERENCES estudiantes(username)
    )
""")

# Función para generar texto y preguntas desde la API
def generar_contenido(categoria, nivel_dificultad):
    api_key = secrets["API_KEY"]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Genera un texto sobre {categoria} con 5 preguntas de opción múltiple. Nivel de dificultad: {nivel_dificultad}"
                }
            ]
        }]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    return response.json()

# Función para registrar estudiantes
def registrar_estudiante(username, password):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("INSERT INTO estudiantes VALUES (?, ?)", (username, hashed_password))
    conn.commit()

# Función para iniciar sesión
def iniciar_sesion(username, password):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT * FROM estudiantes WHERE username = ? AND password = ?", (username, hashed_password))
    return cursor.fetchone() is not None

# Interfaz del usuario
with st.sidebar:
    st.header("Inicio de Sesión")
    username = st.text_input("Nombre de usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if iniciar_sesion(username, password):
            st.success("Bienvenido " + username)
        else:
            st.error("Usuario o contraseña incorrectos")
    st.button("Registro")

# Página principal
if username and password:
    st.header("Categorías")
    categorias = ["Cultura General", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"]
    categoria_seleccionada = st.selectbox("Seleccione una categoría", categorias)
    
    if categoria_seleccionada:
        # Obtener contenido de la API
        response = generar_contenido(categoria_seleccionada, 1)  # Nivel de dificultad inicial
        texto = response["choices"][0]["message"]["text"]
        preguntas = response["choices"][0]["message"]["preguntas"]
        
        st.subheader("Texto")
        st.markdown(texto)
        
        st.subheader("Preguntas")
        score = 0
        for i, pregunta in enumerate(preguntas):
            st.write(f"Pregunta {i+1}: {pregunta['pregunta']}")
            opciones = pregunta["opciones"]
            respuesta_usuario = st.selectbox(f"Seleccione la respuesta", opciones)
            if respuesta_usuario == pregunta["respuesta_correcta"]:
                score += 1
                st.success("Respuesta correcta!")
            else:
                st.error(f"Respuesta incorrecta. La respuesta correcta era {pregunta['respuesta_correcta']}")
        
        # Actualizar progreso
        cursor.execute("INSERT INTO progreso (username, fecha, nivel_dificultad, puntuacion, categoria) VALUES (?, DATE('now'), 1, ?, ?)",
                       (username, score, categoria_seleccionada))
        conn.commit()

# Registro de nuevos estudiantes
if st.button("Registro"):
    with st.form("registro_form"):
        new_username = st.text_input("Nombre de usuario")
        new_password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Registrar"):
            if cursor.execute("SELECT username FROM estudiantes WHERE username = ?", (new_username,)).fetchone():
                st.error("Este nombre de usuario ya existe")
            else:
                registrar_estudiante(new_username, new_password)
                st.success("Registro exitoso!")

# Cerrar conexión
conn.close()
