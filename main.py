import streamlit as st
import sqlite3
import requests
import json

# Configuración de la API de OpenRouter
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Conexión a la base de datos SQLite
conn = sqlite3.connect("progreso.db")
cursor = conn.cursor()

# Crear tabla para registrar estudiantes
cursor.execute("""
    CREATE TABLE IF NOT EXISTS estudiantes (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        progreso REAL DEFAULT 0
    );
""")

# Crear tabla para registrar respuestas
cursor.execute("""
    CREATE TABLE IF NOT EXISTS respuestas (
        id INTEGER PRIMARY KEY,
        estudiante_id INTEGER NOT NULL,
        pregunta TEXT NOT NULL,
        respuesta TEXT NOT NULL,
        correcta INTEGER NOT NULL,
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes (id)
    );
""")

# Función para generar texto dinámico
def generar_texto(area):
    payload = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [
            {
                "role": "user",
                "content": f"Genera un texto sobre {area} para un estudiante de bachillerato."
            }
        ]
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}"
    }
    response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return None

# Función para generar preguntas
def generar_preguntas(texto):
    preguntas = []
    for i in range(5):
        pregunta = f"Pregunta {i+1}: {texto.split('.')[i%len(texto.split('.'))]}"
        opciones = [f"Respuesta {j+1}" for j in range(4)]
        respuesta_correcta = f"Respuesta {i%4 + 1}"
        preguntas.append((pregunta, opciones, respuesta_correcta))
    return preguntas

# Página de inicio
st.title("Mejora tu comprensión lectora")
st.write("Bienvenido a nuestra aplicación de comprensión lectora.")

# Registro de estudiantes
st.subheader("Registro de estudiantes")
nombre = st.text_input("Ingrese su nombre:")
if st.button("Registrarse"):
    cursor.execute("INSERT INTO estudiantes (nombre) VALUES (?)", (nombre,))
    conn.commit()
    st.success("Registro exitoso!")

# Selección de área de interés
st.subheader("Seleccione un área de interés")
area = st.selectbox("Área de interés", ["Cultura general", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"])

# Generación de texto y preguntas
texto = generar_texto(area)
if texto:
    st.subheader("Texto")
    st.write(texto)
    preguntas = generar_preguntas(texto)
    for i, (pregunta, opciones, respuesta_correcta) in enumerate(preguntas):
        st.subheader(f"Pregunta {i+1}")
        st.write(pregunta)
        respuesta = st.selectbox("Seleccione una respuesta", opciones)
        if st.button("Enviar respuesta"):
            # Verificar respuesta
            if respuesta == respuesta_correcta:
                st.success("Respuesta correcta!")
                cursor.execute("INSERT INTO respuestas (estudiante_id, pregunta, respuesta, correcta) VALUES (?, ?, ?, ?)",
                               (1, pregunta, respuesta, 1))
            else:
                st.error("Respuesta incorrecta")
                cursor.execute("INSERT INTO respuestas (estudiante_id, pregunta, respuesta, correcta) VALUES (?, ?, ?, ?)",
                               (1, pregunta, respuesta, 0))
            conn.commit()
else:
    st.error("No se pudo generar texto")

# Página de progreso
st.subheader("Progreso")
cursor.execute("SELECT progreso FROM estudiantes WHERE id = 1")
progreso = cursor.fetchone()[0]
st.write(f"Progreso: {progreso}%")

# Cerrar conexión a la base de datos
conn.close()
