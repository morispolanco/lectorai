import streamlit as st
import sqlite3
import requests
import hashlib
from streamlit import secrets

# Configuración inicial
st.set_page_config(page_title="Lector AI", layout="wide")

# Conexión a SQLite
conn = sqlite3.connect("lectorai.db")
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        score REAL NOT NULL,
        difficulty REAL NOT NULL,
        category TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
""")

conn.commit()

# Función para generar texto desde la API de OpenRouter
def generate_text(category, difficulty):
    api_key = secrets["OPENROUTER_API_KEY"]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Generate a text about {category} for a {difficulty} level student."
                    }
                ]
            }
        ]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"]

# Función para hashificar contraseñas
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Función para verificar contraseñas
def check_password(stored_password, provided_password):
    return stored_password == hashlib.sha256(provided_password.encode()).hexdigest()

# Función para generar preguntas y respuestas
def generate_questions(text):
    # Lógica para generar preguntas basadas en el texto
    # Esto puede ser mejorado usando NLP o modelos de lenguaje
    # Por ahora, devolvemos preguntas estáticas
    questions = [
        {
            "question": "¿Cuál es el tema principal del texto?",
            "options": ["Ciencia", "Historia", "Filosofía", "Tecnología"],
            "correct": 0
        },
        {
            "question": "¿Quién es el autor mencionado?",
            "options": ["Albert Einstein", "Charles Darwin", "Platón", "Nikola Tesla"],
            "correct": 1
        }
    ]
    return questions

# Interfaz de usuario
st.title("Lector AI - Mejora tu comprensión lectora")

# Menú lateral para registro y login
with st.sidebar:
    option = st.selectbox("¿Qué deseas hacer?", ("Registro", "Login"))
    
    if option == "Registro":
        st.subheader("Registro de nuevo usuario")
        username = st.text_input("Nombre de usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Registro"):
            hashed_password = hash_password(password)
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            st.success("Usuario registrado exitosamente")
    else:
        st.subheader("Login")
        username = st.text_input("Nombre de usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Login"):
            cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
            stored_password = cursor.fetchone()
            if stored_password and check_password(stored_password[0], password):
                st.success("Login exitoso")
                # Aquí iría la lógica para cargar el perfil del usuario
            else:
                st.error("Nombre de usuario o contraseña incorrectos")

# Contenido principal
main_col1, main_col2 = st.columns(2)

with main_col1:
    st.subheader("Categorías disponibles")
    categories = ["Ciencia", "Historia", "Filosofía", "Tecnología"]
    selected_category = st.selectbox("Selecciona una categoría", categories)

with main_col2:
    st.subheader("Nivel de dificultad")
    difficulty_level = st.slider("Selecciona tu nivel de dificultad", 1, 5, 3)

if st.button("Generar texto"):
    text = generate_text(selected_category, difficulty_level)
    st.write(text)
    
    # Generar preguntas
    questions = generate_questions(text)
    
    # Mostrar preguntas y opciones
    score = 0
    for i, question in enumerate(questions):
        st.subheader(f"Pregunta {i+1}: {question['question']}")
        options = question["options"]
        user_answer = st.selectbox(f"Selecciona una respuesta", options)
        if user_answer == question["correct"]:
            score += 20
            st.success("Respuesta correcta!")
        else:
            st.error(f"Respuesta incorrecta. La correcta era {options[question['correct']]}")
    
    total_score = score
    st.write(f"Puntuación total: {total_score}")
    
    # Guardar progreso en la base de datos
    cursor.execute("INSERT INTO progress (user_id, score, difficulty, category) VALUES (?, ?, ?, ?)", 
                  (1, total_score, difficulty_level, selected_category))
    conn.commit()

# Cerrar conexión
conn.close()
