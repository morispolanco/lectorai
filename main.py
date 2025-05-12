import streamlit as st
import sqlite3
import requests
import os
import json

# Configuración de la API de OpenRouter
openrouter_api_key = st.secrets["OPENROUTER_API_KEY"]
openrouter_api_url = "https://openrouter.ai/api/v1/chat/completions"

# Conexión a la base de datos SQLite
conn = sqlite3.connect("estudiantes.db")
cursor = conn.cursor()

# Creación de la tabla de estudiantes
cursor.execute("""
    CREATE TABLE IF NOT EXISTS estudiantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        tema TEXT,
        puntaje REAL
    );
""")

# Función para generar texto y preguntas a través de la API de OpenRouter
def generar_texto_y_preguntas(tema):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openrouter_api_key}"
    }
    data = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Generar un texto sobre {tema}"
                    }
                ]
            }
        ]
    }
    response = requests.post(openrouter_api_url, headers=headers, data=json.dumps(data))
    return response.json()

# Función para registrar la actividad del estudiante
def registrar_actividad(estudiante, tema, puntaje):
    cursor.execute("INSERT INTO estudiantes (nombre, tema, puntaje) VALUES (?, ?, ?)", (estudiante, tema, puntaje))
    conn.commit()

# Interfaz de la aplicación
st.title("Aplicación de Comprensión Lectora")

# Registro de estudiantes
estudiante = st.text_input("Ingrese su nombre")

# Selección de tema
temas = ["Cultura General", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"]
tema_seleccionado = st.selectbox("Seleccione un tema", temas)

# Generación de texto y preguntas
if st.button("Generar texto y preguntas"):
    texto_y_preguntas = generar_texto_y_preguntas(tema_seleccionado)
    st.write(texto_y_preguntas)

# Presentación de texto y preguntas
if st.button("Presentar texto y preguntas"):
    # Presentar el texto y las preguntas al estudiante
    st.write("Texto y preguntas")

    # Retroalimentación inmediata
    respuesta = st.text_input("Ingrese su respuesta")
    if st.button("Enviar respuesta"):
        # Evaluar la respuesta y proporcionar retroalimentación
        st.write("Retroalimentación")

        # Registrar la actividad del estudiante
        registrar_actividad(estudiante, tema_seleccionado, 0)

# Cerrar la conexión a la base de datos
conn.close()
