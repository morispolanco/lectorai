import streamlit as st
import sqlite3
import hashlib
import requests
import json
import re
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Mentor de Lectura IA", layout="wide")

# --- Configuración de la API de OpenRouter ---
# ¡IMPORTANTE! Guarda tu API Key en .streamlit/secrets.toml
# Ejemplo de .streamlit/secrets.toml:
# OPENROUTER_API_KEY = "sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "TU_API_KEY_AQUI_SI_NO_USAS_SECRETS")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- Funciones de Base de Datos (SQLite) ---
DB_NAME = "reading_comprehension_app.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Tabla de usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        level TEXT DEFAULT 'principiante' 
    )
    """)
    # Nivel puede ser 'principiante', 'intermedio', 'avanzado'

    # Tabla de textos generados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS texts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        content TEXT NOT NULL,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de preguntas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL, -- 'A', 'B', 'C', or 'D'
        question_type TEXT, -- 'Vocabulario', 'Inferencia', 'Pensamiento Crítico', 'Detalle', 'Global'
        FOREIGN KEY (text_id) REFERENCES texts (id)
    )
    """)

    # Tabla de progreso del estudiante
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        text_id INTEGER NOT NULL, 
        selected_option TEXT NOT NULL,
        is_correct BOOLEAN NOT NULL,
        answered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (question_id) REFERENCES questions (id),
        FOREIGN KEY (text_id) REFERENCES texts(id)
    )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                       (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError: # Username already exists
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash, level FROM users WHERE username = ?", (username,))
    user_record = cursor.fetchone()
    conn.close()
    if user_record and user_record[1] == hash_password(password):
        return {"id": user_record[0], "username": username, "level": user_record[2]}
    return None

def get_user_level(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT level FROM users WHERE id = ?", (user_id,))
    level = cursor.fetchone()
    conn.close()
    return level[0] if level else 'principiante'

def update_user_level(user_id, new_level):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET level = ? WHERE id = ?", (new_level, user_id))
    conn.commit()
    conn.close()

def store_text_and_questions(topic, difficulty, text_content, questions_data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO texts (topic, difficulty, content) VALUES (?, ?, ?)",
                   (topic, difficulty, text_content))
    text_id = cursor.lastrowid
    
    for q_data in questions_data:
        cursor.execute("""
        INSERT INTO questions (text_id, question_text, option_a, option_b, option_c, option_d, correct_option, question_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (text_id, q_data['pregunta'], q_data['opciones']['A'], q_data['opciones']['B'], 
              q_data['opciones']['C'], q_data['opciones']['D'], q_data['respuesta_correcta'], q_data['tipo']))
    conn.commit()
    conn.close()
    return text_id

def record_progress(user_id, text_id, question_id, selected_option, is_correct):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO progress (user_id, text_id, question_id, selected_option, is_correct)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, text_id, question_id, selected_option, is_correct))
    conn.commit()
    conn.close()

def get_progress(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.topic, t.difficulty, q.question_text, p.selected_option, p.is_correct, p.answered_at
    FROM progress p
    JOIN questions q ON p.question_id = q.id
    JOIN texts t ON q.text_id = t.id
    WHERE p.user_id = ?
    ORDER BY p.answered_at DESC
    """, (user_id,))
    progress_data = cursor.fetchall()
    conn.close()
    return progress_data

def get_recent_performance(user_id, num_texts=3):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Obtener los IDs de los últimos 'num_texts' textos respondidos
    cursor.execute("""
        SELECT DISTINCT text_id 
        FROM progress 
        WHERE user_id = ? 
        ORDER BY answered_at DESC 
        LIMIT ?
    """, (user_id, num_texts))
    text_ids_tuples = cursor.fetchall()
    
    if not text_ids_tuples:
        conn.close()
        return None

    text_ids = [tid[0] for tid in text_ids_tuples]
    
    # Calcular la precisión para esos textos
    placeholders = ','.join('?' for _ in text_ids)
    cursor.execute(f"""
        SELECT SUM(is_correct), COUNT(is_correct)
        FROM progress
        WHERE user_id = ? AND text_id IN ({placeholders})
    """, (user_id, *text_ids))
    
    result = cursor.fetchone()
    conn.close()
    
    if result and result[1] > 0: # count > 0
        correct_answers, total_questions = result
        return correct_answers / total_questions
    return None

def get_questions_for_text(text_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_text, option_a, option_b, option_c, option_d, correct_option, question_type FROM questions WHERE text_id = ?", (text_id,))
    questions = cursor.fetchall()
    conn.close()
    # Convertir a lista de diccionarios
    return [
        {
            "id": q[0], "pregunta": q[1], 
            "opciones": {"A": q[2], "B": q[3], "C": q[4], "D": q[5]},
            "respuesta_correcta": q[6], "tipo": q[7]
        } for q in questions
    ]


# --- Funciones de API de OpenRouter ---
def generate_text_via_api(topic, difficulty_level):
    """Genera texto usando la API de OpenRouter."""
    prompt = f"""Eres un asistente experto en crear contenido educativo en español.
Por favor, genera un texto de aproximadamente 200-250 palabras en español para un estudiante de bachillerato (15-18 años).
El nivel de lectura del estudiante es: '{difficulty_level}'.
El tema del texto es: '{topic}'.
El texto debe ser claro, conciso, informativo y atractivo. No incluyas títulos ni encabezados, solo el cuerpo del texto.
Asegúrate de que el lenguaje sea apropiado para el nivel de dificultad especificado.
"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "meta-llama/llama-3-8b-instruct:free", # Usando un modelo más reciente y capaz si el original no funciona bien
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}] }]
    }
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        response_json = response.json()
        text_content = response_json['choices'][0]['message']['content']
        return text_content.strip()
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la API de OpenRouter para generar texto: {e}")
        return None
    except (KeyError, IndexError) as e:
        st.error(f"Error al procesar la respuesta de la API (texto): {e} - Respuesta: {response_json}")
        return None

def generate_questions_via_api(text_content, topic, difficulty_level):
    """Genera preguntas usando la API de OpenRouter, solicitando JSON."""
    prompt = f"""Eres un asistente experto en crear evaluaciones de comprensión lectora en español.
Basándote ESTRICTAMENTE en el siguiente texto:
--- INICIO DEL TEXTO ---
{text_content}
--- FIN DEL TEXTO ---

Genera EXACTAMENTE 5 preguntas de opción múltiple en español. Cada pregunta debe tener 4 opciones (A, B, C, D).
Debes indicar cuál es la opción correcta.
Las preguntas deben evaluar una variedad de habilidades, incluyendo:
1.  Vocabulario (definición, sinónimo o antónimo de una palabra clave del texto)
2.  Inferencia (algo que se puede deducir del texto pero no está explícitamente dicho)
3.  Pensamiento Crítico (idea principal, propósito del autor, o evaluación de argumentos presentados en el texto)
4.  Detalle Específico (localizar información puntual en el texto)
5.  Comprensión Global (resumir una sección o el mensaje principal del texto)

Formatea la salida EXCLUSIVAMENTE como un string JSON que represente una lista de objetos. Cada objeto debe tener las siguientes claves:
-   "pregunta": (string) El texto de la pregunta.
-   "opciones": (diccionario) Un diccionario con claves "A", "B", "C", "D" y sus respectivos strings de opción.
-   "respuesta_correcta": (string) La letra de la opción correcta (ej: "A", "B", "C", o "D").
-   "tipo": (string) El tipo de habilidad que evalúa la pregunta (ej: "Vocabulario", "Inferencia", "Pensamiento Crítico", "Detalle Específico", "Comprensión Global").

NO incluyas ningún texto explicativo, comentarios, ni nada antes o después del string JSON. Solo el JSON puro.
Ejemplo de formato de un objeto en la lista JSON:
{{
  "pregunta": "¿Cuál es la idea principal del primer párrafo?",
  "opciones": {{
    "A": "Opción A...",
    "B": "Opción B...",
    "C": "Opción C...",
    "D": "Opción D..."
  }},
  "respuesta_correcta": "B",
  "tipo": "Comprensión Global"
}}
Asegúrate que el JSON sea válido.
"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "meta-llama/llama-3-8b-instruct:free", # Usando un modelo más reciente y capaz
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}] }]
    }
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=90) # Mayor timeout para generación compleja
        response.raise_for_status()
        response_content = response.json()['choices'][0]['message']['content']
        
        # Limpiar el string de respuesta para asegurar que sea solo JSON
        # A veces los modelos añaden ```json ... ``` o texto explicativo
        match = re.search(r'\[.*\]', response_content, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            # Si no se encuentra un array JSON, intentar buscar un objeto JSON (menos probable para una lista)
            match_obj = re.search(r'\{.*\}', response_content, re.DOTALL)
            if match_obj:
                json_str = match_obj.group(0) # Podría ser un solo objeto si el LLM se equivoca
            else: # Si no, tomar todo y esperar que sea JSON
                 json_str = response_content.strip()


        questions_data = json.loads(json_str)
        
        # Validación básica de la estructura
        if not isinstance(questions_data, list) or len(questions_data) != 5:
            st.warning(f"La API devolvió un formato inesperado para las preguntas (no es una lista de 5). Contenido: {json_str}")
            # Intentar usar las que sí estén bien formadas si es una lista
            if isinstance(questions_data, list):
                 valid_questions = [q for q in questions_data if isinstance(q, dict) and all(k in q for k in ["pregunta", "opciones", "respuesta_correcta", "tipo"])]
                 if valid_questions:
                     st.info(f"Se usarán {len(valid_questions)} preguntas válidas de las {len(questions_data)} recibidas.")
                     return valid_questions
            return None # O manejar el error de forma más robusta

        return questions_data
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la API de OpenRouter para generar preguntas: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Error al decodificar JSON de la API (preguntas): {e}. Respuesta recibida: {response_content}")
        return None
    except (KeyError, IndexError) as e:
        st.error(f"Error al procesar la respuesta de la API (preguntas): {e} - Respuesta: {response.json()}")
        return None

# --- Lógica de la Aplicación Streamlit ---
def main():
    init_db() # Asegura que las tablas existan

    if "logged_in_user" not in st.session_state:
        st.session_state.logged_in_user = None
    if "current_text_id" not in st.session_state:
        st.session_state.current_text_id = None
    if "current_questions" not in st.session_state:
        st.session_state.current_questions = []
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = {}
    if "feedback" not in st.session_state:
        st.session_state.feedback = {}
    if "show_results" not in st.session_state:
        st.session_state.show_results = False

    if st.session_state.logged_in_user is None:
        login_register_page()
    else:
        app_page()

def login_register_page():
    st.title("Bienvenido al Mentor de Lectura IA")
    
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Iniciar Sesión")
        with st.form("login_form"):
            login_username = st.text_input("Nombre de Usuario", key="login_user")
            login_password = st.text_input("Contraseña", type="password", key="login_pass")
            login_button = st.form_submit_button("Ingresar")

            if login_button:
                if not login_username or not login_password:
                    st.error("Por favor, ingresa usuario y contraseña.")
                else:
                    user = verify_user(login_username, login_password)
                    if user:
                        st.session_state.logged_in_user = user
                        st.session_state.current_text_id = None # Resetear al loguear
                        st.session_state.current_questions = []
                        st.session_state.user_answers = {}
                        st.session_state.feedback = {}
                        st.session_state.show_results = False
                        st.success(f"Bienvenido de nuevo, {user['username']}!")
                        st.rerun() # Forzar recarga para ir a la app_page
                    else:
                        st.error("Nombre de usuario o contraseña incorrectos.")
    
    with col2:
        st.subheader("Registrarse")
        with st.form("register_form"):
            reg_username = st.text_input("Nuevo Nombre de Usuario", key="reg_user")
            reg_password = st.text_input("Nueva Contraseña", type="password", key="reg_pass")
            reg_password_confirm = st.text_input("Confirmar Contraseña", type="password", key="reg_pass_confirm")
            register_button = st.form_submit_button("Registrar")

            if register_button:
                if not reg_username or not reg_password or not reg_password_confirm:
                    st.error("Por favor, completa todos los campos.")
                elif reg_password != reg_password_confirm:
                    st.error("Las contraseñas no coinciden.")
                elif len(reg_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    if add_user(reg_username, reg_password):
                        st.success("¡Registro exitoso! Ahora puedes iniciar sesión.")
                    else:
                        st.error("El nombre de usuario ya existe.")

def app_page():
    user = st.session_state.logged_in_user
    st.sidebar.title(f"Hola, {user['username']}")
    st.sidebar.write(f"Nivel Actual: {user['level'].capitalize()}")
    
    menu_choice = st.sidebar.radio(
        "Menú Principal",
        ("Nueva Lectura", "Mi Progreso", "Ajustar Nivel (Demo)", "Cerrar Sesión")
    )

    if menu_choice == "Cerrar Sesión":
        st.session_state.logged_in_user = None
        st.session_state.current_text_id = None
        st.session_state.current_questions = []
        st.session_state.user_answers = {}
        st.session_state.feedback = {}
        st.session_state.show_results = False
        st.sidebar.info("Has cerrado sesión.")
        st.rerun()

    elif menu_choice == "Nueva Lectura":
        display_new_reading_page()

    elif menu_choice == "Mi Progreso":
        display_progress_page()
    
    elif menu_choice == "Ajustar Nivel (Demo)":
        display_level_adjustment_demo()


def display_new_reading_page():
    st.header("📚 Nueva Lectura Guiada")
    user = st.session_state.logged_in_user

    if st.session_state.current_text_id is None or not st.session_state.current_questions:
        # No hay lectura activa, permitir generar una nueva
        topics = ["Cultura General", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"]
        selected_topic = st.selectbox("Elige un tema:", topics)
        
        # El nivel de dificultad se toma del perfil del usuario
        difficulty = user['level']
        st.info(f"Se generará un texto de nivel '{difficulty.capitalize()}' sobre '{selected_topic}'.")

        if st.button("✨ Generar Lectura y Preguntas"):
            if OPENROUTER_API_KEY == "TU_API_KEY_AQUI_SI_NO_USAS_SECRETS" or not OPENROUTER_API_KEY:
                st.error("API Key de OpenRouter no configurada. Por favor, configúrala en los secrets de Streamlit.")
                return

            with st.spinner(f"Generando texto sobre {selected_topic} ({difficulty})..."):
                text_content = generate_text_via_api(selected_topic, difficulty)
            
            if text_content:
                st.success("Texto generado exitosamente.")
                with st.spinner("Generando preguntas..."):
                    questions_data = generate_questions_via_api(text_content, selected_topic, difficulty)
                
                if questions_data and len(questions_data) > 0:
                    st.success(f"{len(questions_data)} preguntas generadas exitosamente.")
                    try:
                        text_id = store_text_and_questions(selected_topic, difficulty, text_content, questions_data)
                        st.session_state.current_text_id = text_id
                        st.session_state.current_questions = get_questions_for_text(text_id) # Recargar desde DB
                        st.session_state.user_answers = {q['id']: None for q in st.session_state.current_questions}
                        st.session_state.feedback = {}
                        st.session_state.show_results = False
                        st.rerun() # Recargar para mostrar el texto y las preguntas
                    except Exception as e:
                        st.error(f"Error al guardar en la base de datos: {e}")
                else:
                    st.error("No se pudieron generar las preguntas o el formato fue incorrecto. Intenta de nuevo o con otro tema.")
            else:
                st.error("No se pudo generar el texto. Verifica la API Key y tu conexión.")
    else:
        # Hay una lectura activa
        text_id = st.session_state.current_text_id
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT content, topic, difficulty FROM texts WHERE id = ?", (text_id,))
        text_data = cursor.fetchone()
        conn.close()

        if not text_data:
            st.error("No se pudo cargar el texto. Por favor, genera uno nuevo.")
            st.session_state.current_text_id = None # Resetear
            st.session_state.current_questions = []
            if st.button("Generar Nueva Lectura"):
                 st.rerun()
            return

        text_content, topic, difficulty = text_data
        st.subheader(f"Tema: {topic} (Nivel: {difficulty.capitalize()})")
        
        with st.expander("📖 Leer Texto Completo", expanded=True):
            st.markdown(text_content)
        
        st.markdown("---")
        st.subheader("📝 Preguntas de Comprensión")

        if not st.session_state.show_results:
            # Mostrar preguntas para responder
            answers_complete = True
            for i, q_data in enumerate(st.session_state.current_questions):
                st.markdown(f"**{i+1}. {q_data['pregunta']}** ({q_data['tipo']})")
                options = list(q_data['opciones'].keys()) # A, B, C, D
                display_options = [f"{opt_key}) {q_data['opciones'][opt_key]}" for opt_key in options]
                
                # Usar q_data['id'] para la clave única del radio button
                user_choice_key = f"q_{q_data['id']}_choice"
                
                # Mantener la selección si ya existe
                current_selection_index = None
                if st.session_state.user_answers.get(q_data['id']):
                    try:
                        current_selection_index = options.index(st.session_state.user_answers[q_data['id']])
                    except ValueError:
                        current_selection_index = None # La opción guardada no es válida

                user_choice_display = st.radio(
                    "Elige una opción:", 
                    display_options, 
                    key=user_choice_key, 
                    index=current_selection_index,
                    label_visibility="collapsed"
                )
                
                if user_choice_display:
                    # Extraer la letra de la opción (A, B, C, D)
                    st.session_state.user_answers[q_data['id']] = user_choice_display.split(')')[0]
                else:
                    answers_complete = False
            
            if st.button("✔️ Enviar Respuestas", disabled=not answers_complete):
                if not all(st.session_state.user_answers.get(q['id']) for q in st.session_state.current_questions):
                    st.warning("Por favor, responde todas las preguntas.")
                else:
                    # Procesar respuestas
                    num_correct = 0
                    for q_data in st.session_state.current_questions:
                        user_ans = st.session_state.user_answers[q_data['id']]
                        is_correct = (user_ans == q_data['correct_option'])
                        if is_correct:
                            num_correct += 1
                        st.session_state.feedback[q_data['id']] = {
                            "correct": is_correct,
                            "chosen": user_ans,
                            "actual": q_data['correct_option'],
                            "explanation": q_data['opciones'][q_data['correct_option']]
                        }
                        record_progress(user['id'], text_id, q_data['id'], user_ans, is_correct)
                    
                    st.session_state.show_results = True
                    
                    # Lógica de ajuste de nivel
                    performance = get_recent_performance(user['id'])
                    if performance is not None:
                        current_level = get_user_level(user['id'])
                        new_level = current_level
                        if performance >= 0.8: # 80% de aciertos
                            if current_level == 'principiante': new_level = 'intermedio'
                            elif current_level == 'intermedio': new_level = 'avanzado'
                        elif performance < 0.5: # Menos de 50%
                            if current_level == 'avanzado': new_level = 'intermedio'
                            elif current_level == 'intermedio': new_level = 'principiante'
                        
                        if new_level != current_level:
                            update_user_level(user['id'], new_level)
                            st.session_state.logged_in_user['level'] = new_level # Actualizar en sesión
                            st.toast(f"¡Tu nivel ha sido actualizado a {new_level.capitalize()}!", icon="🎉")
                    st.rerun()

        if st.session_state.show_results:
            # Mostrar resultados y feedback
            st.subheader("📊 Resultados y Retroalimentación")
            score = 0
            for i, q_data in enumerate(st.session_state.current_questions):
                feedback = st.session_state.feedback.get(q_data['id'])
                if feedback:
                    st.markdown(f"**{i+1}. {q_data['pregunta']}**")
                    st.write(f"   Tu respuesta: {feedback['chosen']}) {q_data['opciones'].get(feedback['chosen'], 'N/A')}")
                    st.write(f"   Respuesta correcta: {feedback['actual']}) {feedback['explanation']}")
                    if feedback['correct']:
                        st.success("   ¡Correcto! 👍")
                        score +=1
                    else:
                        st.error("   Incorrecto. 👎")
                    st.markdown("---")
            
            st.markdown(f"### Puntaje Final: {score} de {len(st.session_state.current_questions)} correctas.")

            if st.button("🔄 Intentar otra lectura"):
                st.session_state.current_text_id = None
                st.session_state.current_questions = []
                st.session_state.user_answers = {}
                st.session_state.feedback = {}
                st.session_state.show_results = False
                st.rerun()

def display_progress_page():
    st.header("📈 Mi Progreso")
    user = st.session_state.logged_in_user
    progress_data = get_progress(user['id'])

    if not progress_data:
        st.info("Aún no has completado ninguna lectura. ¡Anímate a empezar!")
        return

    st.write(f"Historial de respuestas para {user['username']}:")
    
    # Métricas generales
    total_questions_answered = len(progress_data)
    correct_answers = sum(1 for p_item in progress_data if p_item[4]) # p_item[4] is is_correct
    accuracy = (correct_answers / total_questions_answered * 100) if total_questions_answered > 0 else 0
    
    st.metric(label="Preguntas Totales Respondidas", value=total_questions_answered)
    st.metric(label="Respuestas Correctas", value=correct_answers)
    st.metric(label="Precisión General", value=f"{accuracy:.2f}%")

    st.subheader("Detalle de Actividad Reciente:")
    # Mostrar los últimos 10 resultados para no saturar
    for i, p_item in enumerate(progress_data[:10]):
        topic, difficulty, q_text, sel_opt, is_corr, ts = p_item
        with st.expander(f"{ts.split('.')[0]} - Tema: {topic} - {'Correcta' if is_corr else 'Incorrecta'}"):
            st.write(f"**Pregunta:** {q_text}")
            st.write(f"**Tu respuesta:** {sel_opt}")
            st.write(f"**Nivel del texto:** {difficulty}")
            if is_corr:
                st.success("Resultado: Correcto")
            else:
                st.error("Resultado: Incorrecto")

def display_level_adjustment_demo():
    st.header("🛠️ Ajustar Nivel de Dificultad (Demo)")
    user = st.session_state.logged_in_user
    st.write(f"Tu nivel actual es: **{user['level'].capitalize()}**")

    new_level_demo = st.selectbox(
        "Selecciona un nuevo nivel (para demostración):",
        ['principiante', 'intermedio', 'avanzado'],
        index=['principiante', 'intermedio', 'avanzado'].index(user['level'])
    )

    if st.button("Actualizar Nivel (Demo)"):
        update_user_level(user['id'], new_level_demo)
        st.session_state.logged_in_user['level'] = new_level_demo
        st.success(f"Nivel actualizado a {new_level_demo.capitalize()} para demostración.")
        st.rerun()
    
    st.info("""
    **Nota:** En el uso normal, el nivel se ajusta automáticamente según tu desempeño.
    - Si aciertas más del 80% en las últimas lecturas, tu nivel puede subir.
    - Si aciertas menos del 50%, tu nivel puede bajar.
    Esta página es solo para fines de demostración y prueba.
    """)


if __name__ == "__main__":
    # Verificar si la API key está cargada
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "TU_API_KEY_AQUI_SI_NO_USAS_SECRETS":
        st.error("Error Crítico: La API Key de OpenRouter no está configurada.")
        st.info("Por favor, crea un archivo .streamlit/secrets.toml y añade tu API key así:")
        st.code("OPENROUTER_API_KEY = \"sk-or-v1-tu_clave_aqui\"")
        st.stop()
    main()
