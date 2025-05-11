import streamlit as st
import requests
import sqlite3
import json
import random
import re
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Mejora tu Comprensión Lectora", layout="wide")

# Conexión a SQLite
conn = sqlite3.connect('students.db', check_same_thread=False)
c = conn.cursor()

# Crear tablas si no existen
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    level INTEGER DEFAULT 1
)''')
c.execute('''CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text_id INTEGER,
    score INTEGER,
    date TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)''')
conn.commit()

# Función para obtener texto y preguntas de la API
def get_text_and_questions(level, topic):
    api_key = st.secrets["OPENROUTER_API_KEY"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    difficulty = {1: "básico", 2: "intermedio", 3: "avanzado"}
    prompt = f"""Genera un texto educativo de nivel {difficulty[level]} sobre {topic} (150-200 palabras) para estudiantes de bachillerato. 
El texto debe ser claro, informativo y adecuado para mejorar la comprensión lectora. 
Además, proporciona 5 preguntas de opción múltiple (4 opciones cada una) que evalúen vocabulario, inferencia y pensamiento crítico. 
Incluye la respuesta correcta y una breve explicación para cada pregunta. 
Devuelve el resultado **estrictamente en formato JSON** (sin texto adicional ni comentarios) con esta estructura:
{{
    "text": "texto generado",
    "questions": [
        {{
            "question": "texto de la pregunta",
            "options": ["opción 1", "opción 2", "opción 3", "opción 4"],
            "correct": "opción correcta",
            "explanation": "explicación de la respuesta"
        }}
    ]
}}
"""
    
    data = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        if 'choices' not in result or not result['choices']:
            st.error("Respuesta de la API vacía o inválida")
            return None
        
        content = result['choices'][0]['message']['content']
        
        # Log the raw content for debugging (visible in Streamlit logs)
        st.write("### Respuesta cruda de la API (para depuración):")
        st.code(content)
        
        # Clean the response to extract JSON (remove code fences or extra text)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            cleaned_content = json_match.group(0)
        else:
            st.error("No se encontró un JSON válido en la respuesta de la API")
            return None
        
        # Parse the cleaned JSON
        return json.loads(cleaned_content)
    
    except json.JSONDecodeError as je:
        st.error(f"Error al parsear la respuesta de la API: {je}")
        return None
    except requests.RequestException as re:
        st.error(f"Error en la solicitud a la API: {re}")
        return None
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return None

# Función para registrar usuario
def register_user(username, password):
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# Función para verificar login
def login_user(username, password):
    c.execute("SELECT id, level FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    return user if user else None

# Función para actualizar nivel del usuario
def update_level(user_id, score):
    c.execute("SELECT level FROM users WHERE id = ?", (user_id,))
    current_level = c.fetchone()[0]
    
    if score >= 80 and current_level < 3:
        new_level = current_level + 1
        c.execute("UPDATE users SET level = ? WHERE id = ?", (new_level, user_id))
    elif score < 40 and current_level > 1:
        new_level = current_level - 1
        c.execute("UPDATE users SET level = ? WHERE id = ?", (new_level, user_id))
    conn.commit()

# Función para guardar progreso
def save_progress(user_id, text_id, score):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO progress (user_id, text_id, score, date) VALUES (?, ?, ?, ?)",
              (user_id, text_id, score, date))
    conn.commit()

# Función para obtener progreso del usuario
def get_progress(user_id):
    c.execute("SELECT date, score FROM progress WHERE user_id = ? ORDER BY date DESC", (user_id,))
    return c.fetchall()

# Interfaz principal
def main():
    if 'user' not in st.session_state:
        st.session_state.user = None
        st.session_state.page = 'login'

    if st.session_state.user is None:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Iniciar Sesión")
            login_username = st.text_input("Usuario", key="login_user")
            login_password = st.text_input("Contraseña", type="password", key="login_pass")
            if st.button("Iniciar Sesión"):
                user = login_user(login_username, login_password)
                if user:
                    st.session_state.user = {'id': user[0], 'level': user[1], 'username': login_username}
                    st.session_state.page = 'main'
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")

        with col2:
            st.subheader("Registrarse")
            reg_username = st.text_input("Nuevo usuario", key="reg_user")
            reg_password = st.text_input("Nueva contraseña", type="password", key="reg_pass")
            if st.button("Registrarse"):
                if register_user(reg_username, reg_password):
                    st.success("Usuario registrado con éxito")
                else:
                    st.error("El usuario ya existe")

    else:
        st.sidebar.title(f"Bienvenido, {st.session_state.user['username']}")
        if st.sidebar.button("Cerrar Sesión"):
            st.session_state.user = None
            st.session_state.page = 'login'
            st.rerun()

        topics = ["Cultura general", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"]
        selected_topic = st.selectbox("Selecciona un tema", topics)
        
        if st.button("Generar nuevo texto"):
            st.session_state.content = get_text_and_questions(st.session_state.user['level'], selected_topic)
            st.session_state.answers = {}
            st.session_state.feedback = {}
        
        if 'content' in st.session_state and st.session_state.content:
            st.write("### Texto")
            st.write(st.session_state.content['text'])
            
            st.write("### Preguntas")
            for i, q in enumerate(st.session_state.content['questions']):
                st.write(q['question'])
                options = q['options']
                answer = st.radio("Selecciona una opción:", options, key=f"q{i}")
                st.session_state.answers[i] = answer
                
                if st.button("Enviar respuesta", key=f"submit{i}"):
                    correct = q['correct']
                    if answer == correct:
                        st.session_state.feedback[i] = f"¡Correcto! {q['explanation']}"
                    else:
                        st.session_state.feedback[i] = f"Incorrecto. {q['explanation']}"
                
                if i in st.session_state.feedback:
                    st.write(st.session_state.feedback[i])
            
            if len(st.session_state.answers) == 5:
                score = sum(1 for i in range(5) if st.session_state.answers[i] == st.session_state.content['questions'][i]['correct']) * 20
                st.write(f"### Puntuación: {score}%")
                save_progress(st.session_state.user['id'], random.randint(1, 1000), score)
                update_level(st.session_state.user['id'], score)
                
                # Mostrar progreso
                st.write("### Progreso")
                progress = get_progress(st.session_state.user['id'])
                for date, prog_score in progress[:5]:  # Mostrar últimos 5 intentos
                    st.write(f"Fecha: {date}, Puntuación: {prog_score}%")

if __name__ == "__main__":
    main()
