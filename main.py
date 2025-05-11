import streamlit as st
import sqlite3
import requests
import json
from datetime import datetime
import os

# --- Configuración de la Base de Datos ---
DB_FILE = 'reading_comprehension.db'

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                difficulty_level INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                difficulty_level INTEGER NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL, -- e.g., 'vocabulario', 'inferencia', 'pensamiento_critico'
                FOREIGN KEY (text_id) REFERENCES texts (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                is_correct BOOLEAN NOT NULL,
                FOREIGN KEY (question_id) REFERENCES questions (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                selected_option_id INTEGER, -- Puede ser NULL si no respondió
                is_correct BOOLEAN, -- Puede ser NULL si no respondió
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (text_id) REFERENCES texts (id),
                FOREIGN KEY (question_id) REFERENCES questions (id),
                FOREIGN KEY (selected_option_id) REFERENCES options (id)
            )
        ''')
        conn.commit()

# --- Funciones de Usuario y Autenticación ---

def register_user(username, password):
    """Registra un nuevo usuario en la base de datos."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return True, "Registro exitoso. Por favor, inicia sesión."
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe."
    except Exception as e:
        return False, f"Error al registrar usuario: {e}"

def login_user(username, password):
    """Verifica las credenciales del usuario y devuelve el ID del usuario si son correctas."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, difficulty_level FROM users WHERE username = ? AND password = ?", (username, password))
        result = cursor.fetchone()
        if result:
            return result[0], result[1] # user_id, difficulty_level
        return None, None

def get_user_difficulty(user_id):
    """Obtiene el nivel de dificultad actual del usuario."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT difficulty_level FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 1 # Default to 1 if not found

def update_user_difficulty(user_id, new_difficulty):
    """Actualiza el nivel de dificultad del usuario."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET difficulty_level = ? WHERE id = ?", (new_difficulty, user_id))
        conn.commit()

# --- Interacción con OpenRouter API ---

def get_text_and_questions_from_api(topic, difficulty_level, api_key):
    """
    Obtiene un texto y preguntas de la API de OpenRouter.
    Solicita un texto y 5 preguntas (vocabulario, inferencia, pensamiento crítico)
    en formato JSON.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    model = "meta-llama/llama-4-maverick:free" # Usando el modelo especificado

    prompt = f"""
    Genera un texto de comprensión lectora para estudiantes de bachillerato sobre el tema "{topic}".
    El nivel de dificultad debe ser apropiado para el nivel {difficulty_level}.
    El texto debe tener aproximadamente 200-300 palabras.
    Después del texto, genera 5 preguntas de opción múltiple (con 4 opciones cada una) sobre el texto.
    Asegúrate de incluir:
    - Al menos 1 pregunta de vocabulario.
    - Al menos 2 preguntas de inferencia.
    - Al menos 2 preguntas de pensamiento crítico.
    Para cada pregunta, indica claramente cuál es la respuesta correcta.
    Formatea la respuesta como un objeto JSON con las siguientes claves:
    "text": "El contenido del texto aquí.",
    "questions": [
        {{
            "question_text": "¿Pregunta aquí?",
            "question_type": "vocabulario" o "inferencia" o "pensamiento_critico",
            "options": [
                {{"option_text": "Opción A", "is_correct": false}},
                {{"option_text": "Opción B", "is_correct": true}},
                {{"option_text": "Opción C", "is_correct": false}},
                {{"option_text": "Opción D", "is_correct": false}}
            ]
        }},
        ... (4 preguntas más)
    ]
    Asegúrate de que el JSON sea válido y esté completo.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() # Lanza una excepción para códigos de estado de error
        result = response.json()
        # Intentar parsear el contenido de la respuesta
        api_content = result['choices'][0]['message']['content']

        # La API a veces envuelve el JSON en bloques de código markdown, intentar limpiarlo
        if api_content.startswith("```json"):
            api_content = api_content[7:]
            if api_content.endswith("```"):
                api_content = api_content[:-3]

        # Intentar cargar el contenido como JSON
        parsed_content = json.loads(api_content)
        return parsed_content
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la API de OpenRouter: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Error al parsear la respuesta JSON de la API: {e}. Respuesta recibida: {api_content}")
        return None
    except KeyError as e:
        st.error(f"La respuesta de la API no tiene el formato esperado. Falta la clave: {e}. Respuesta completa: {result}")
        return None
    except Exception as e:
        st.error(f"Ocurrió un error inesperado al obtener datos de la API: {e}")
        return None


# --- Funciones de Datos y Progreso ---

def save_text_and_questions(topic, difficulty_level, api_response):
    """Guarda el texto y las preguntas en la base de datos."""
    text_content = api_response['text']
    questions_data = api_response['questions']

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO texts (topic, content, difficulty_level) VALUES (?, ?, ?)",
                       (topic, text_content, difficulty_level))
        text_id = cursor.lastrowid

        for q_data in questions_data:
            cursor.execute("INSERT INTO questions (text_id, question_text, question_type) VALUES (?, ?, ?)",
                           (text_id, q_data['question_text'], q_data['question_type']))
            question_id = cursor.lastrowid

            for opt_data in q_data['options']:
                cursor.execute("INSERT INTO options (question_id, option_text, is_correct) VALUES (?, ?, ?)",
                               (question_id, opt_data['option_text'], opt_data['is_correct']))
        conn.commit()
    return text_id

def get_text_and_questions(text_id):
    """Recupera un texto y sus preguntas de la base de datos."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, topic, content, difficulty_level FROM texts WHERE id = ?", (text_id,))
        text_data = cursor.fetchone()

        if not text_data:
            return None, None

        text = {
            'id': text_data[0],
            'topic': text_data[1],
            'content': text_data[2],
            'difficulty_level': text_data[3]
        }

        cursor.execute("SELECT id, question_text, question_type FROM questions WHERE text_id = ?", (text_id,))
        questions_data = cursor.fetchall()

        questions = []
        for q_data in questions_data:
            question_id = q_data[0]
            cursor.execute("SELECT id, option_text, is_correct FROM options WHERE question_id = ?", (question_id,))
            options_data = cursor.fetchall()
            options = [{'id': opt[0], 'option_text': opt[1], 'is_correct': bool(opt[2])} for opt in options_data]
            questions.append({
                'id': question_id,
                'question_text': q_data[1],
                'question_type': q_data[2],
                'options': options
            })
        return text, questions

def record_progress(user_id, text_id, question_id, selected_option_id, is_correct):
    """Registra el progreso del usuario en la base de datos."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user_progress (user_id, text_id, question_id, selected_option_id, is_correct) VALUES (?, ?, ?, ?, ?)",
                       (user_id, text_id, question_id, selected_option_id, is_correct))
        conn.commit()

def get_user_performance_metrics(user_id):
    """Calcula métricas de rendimiento del usuario (ej. porcentaje de respuestas correctas)."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_progress WHERE user_id = ?", (user_id,))
        total_attempts = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_progress WHERE user_id = ? AND is_correct = 1", (user_id,))
        correct_answers = cursor.fetchone()[0]

        if total_attempts == 0:
            return 0, 0
        accuracy = (correct_answers / total_attempts) * 100
        return total_attempts, accuracy

def get_user_reading_history(user_id):
    """Obtiene el historial de lectura del usuario."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                t.topic,
                t.difficulty_level,
                COUNT(up.question_id) as total_questions,
                SUM(up.is_correct) as correct_answers,
                MAX(up.timestamp) as last_attempt
            FROM user_progress up
            JOIN questions q ON up.question_id = q.id
            JOIN texts t ON q.text_id = t.id
            WHERE up.user_id = ?
            GROUP BY t.id, t.topic, t.difficulty_level
            ORDER BY last_attempt DESC
        """, (user_id,))
        return cursor.fetchall()

# --- Lógica de Ajuste de Dificultad (Ejemplo Simple) ---
# Esto es un ejemplo básico. Una implementación más sofisticada podría
# considerar una ventana de respuestas recientes, tipos de preguntas, etc.

def adjust_difficulty(user_id):
    """Ajusta el nivel de dificultad del usuario basado en su rendimiento reciente."""
    # Obtener las últimas N respuestas (ej. 10)
    N = 10
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_correct FROM user_progress
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, N))
        recent_results = cursor.fetchall()

    if len(recent_results) < N:
        # No hay suficientes datos para ajustar la dificultad
        return

    correct_count = sum([r[0] for r in recent_results if r[0] is not None]) # Sumar solo si is_correct no es NULL
    accuracy = (correct_count / N) * 100

    current_difficulty = get_user_difficulty(user_id)
    new_difficulty = current_difficulty

    # Umbrales de ejemplo para ajuste
    if accuracy >= 80 and current_difficulty < 5: # Si el rendimiento es alto, aumenta la dificultad (máx 5)
        new_difficulty = current_difficulty + 1
    elif accuracy < 40 and current_difficulty > 1: # Si el rendimiento es bajo, disminuye la dificultad (mín 1)
        new_difficulty = current_difficulty - 1

    if new_difficulty != current_difficulty:
        update_user_difficulty(user_id, new_difficulty)
        st.session_state.user_difficulty = new_difficulty # Actualizar en el estado de sesión

# --- Interfaz de Usuario de Streamlit ---

st.set_page_config(page_title="Comprensión Lectora para Bachillerato", layout="wide")

# Inicializar la base de datos al inicio
init_db()

# Estado de sesión
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_difficulty' not in st.session_state:
    st.session_state.user_difficulty = 1 # Dificultad por defecto
if 'current_text_id' not in st.session_state:
    st.session_state.current_text_id = None
if 'current_text' not in st.session_state:
    st.session_state.current_text = None
if 'current_questions' not in st.session_state:
    st.session_state.current_questions = None
if 'answers_submitted' not in st.session_state:
    st.session_state.answers_submitted = False
if 'selected_options' not in st.session_state:
    st.session_state.selected_options = {}
if 'show_registration' not in st.session_state:
    st.session_state.show_registration = False
if 'feedback_displayed' not in st.session_state: # Initialize feedback_displayed
    st.session_state.feedback_displayed = False


# --- Pantalla de Registro/Login ---
if not st.session_state.logged_in:
    st.title("Bienvenido a la Aplicación de Comprensión Lectora")

    if st.session_state.show_registration:
        st.subheader("Registro de Nuevo Usuario")
        new_username = st.text_input("Nombre de Usuario", key="reg_username")
        new_password = st.text_input("Contraseña", type="password", key="reg_password")
        if st.button("Registrarse"):
            if new_username and new_password:
                success, message = register_user(new_username, new_password)
                if success:
                    st.success(message)
                    st.session_state.show_registration = False # Volver a la pantalla de login
                    st.rerun() # Rerun para mostrar el formulario de login actualizado
                else:
                    st.error(message)
            else:
                st.warning("Por favor, ingresa nombre de usuario y contraseña.")
        if st.button("Ya tengo cuenta (Ir a Iniciar Sesión)"):
             st.session_state.show_registration = False
             st.rerun() # Forzar un rerun para mostrar el formulario de login

    else:
        st.subheader("Iniciar Sesión")
        username = st.text_input("Nombre de Usuario", key="login_username")
        password = st.text_input("Contraseña", type="password", key="login_password")
        if st.button("Iniciar Sesión"):
            if username and password:
                user_id, difficulty = login_user(username, password)
                if user_id:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.session_state.username = username
                    st.session_state.user_difficulty = difficulty
                    st.success(f"¡Bienvenido, {username}!")
                    st.rerun() # Forzar un rerun para mostrar el contenido principal
                else:
                    st.error("Nombre de usuario o contraseña incorrectos.")
            else:
                st.warning("Por favor, ingresa nombre de usuario y contraseña.")
        if st.button("¿No tienes cuenta? Regístrate aquí."):
            st.session_state.show_registration = True
            st.rerun() # Forzar un rerun para mostrar el formulario de registro

# --- Contenido Principal de la Aplicación (si está logueado) ---
if st.session_state.logged_in:
    st.sidebar.title(f"Usuario: {st.session_state.username}")
    st.sidebar.write(f"Nivel de Dificultad: {st.session_state.user_difficulty}")

    if st.sidebar.button("Cerrar Sesión"):
        # Limpiar estado de sesión al cerrar sesión
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.user_difficulty = 1
        st.session_state.current_text_id = None
        st.session_state.current_text = None
        st.session_state.current_questions = None
        st.session_state.answers_submitted = False
        st.session_state.selected_options = {}
        st.session_state.show_registration = False # Asegurarse de que no muestre registro al volver
        st.session_state.feedback_displayed = False # Clear feedback state on logout
        st.rerun()

    st.title("Mejora tu Comprensión Lectora")

    # --- Sección para obtener nuevo texto ---
    st.subheader("Obtener un Nuevo Texto")
    topics = ["Cultura General", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"]
    selected_topic = st.selectbox("Selecciona un tema:", topics)

    # Obtener la API Key de los secrets de Streamlit
    api_key = st.secrets["OPENROUTER_API_KEY"]

    # Botón para generar nuevo texto - Resetea el estado relevante
    if st.button("Generar Texto y Preguntas"):
        # Reset relevant session state variables
        st.session_state.current_text_id = None
        st.session_state.current_text = None
        st.session_state.current_questions = None
        st.session_state.answers_submitted = False
        st.session_state.selected_options = {}
        st.session_state.feedback_displayed = False

        with st.spinner("Generando texto y preguntas..."):
            api_response = get_text_and_questions_from_api(selected_topic, st.session_state.user_difficulty, api_key)
            if api_response:
                try:
                    # Validar que la respuesta de la API tenga el formato esperado
                    if 'text' in api_response and 'questions' in api_response and isinstance(api_response['questions'], list) and len(api_response['questions']) == 5:
                        text_id = save_text_and_questions(selected_topic, st.session_state.user_difficulty, api_response)
                        st.session_state.current_text_id = text_id
                        st.session_state.current_text, st.session_state.current_questions = get_text_and_questions(text_id)
                        st.success("Texto y preguntas generados con éxito.")
                        st.rerun() # Rerun to display the new text and questions
                    else:
                         st.error("La API no devolvió el formato de datos esperado. Por favor, inténtalo de nuevo.")
                         st.write("Respuesta de la API (para depuración):", api_response) # Mostrar respuesta para depurar
                except Exception as e:
                    st.error(f"Error al procesar la respuesta de la API o guardar en la base de datos: {e}")
                    st.write("Respuesta de la API (para depuración):", api_response) # Mostrar respuesta para depurar
            else:
                 st.error("No se pudo obtener el texto y las preguntas de la API.")


    # --- Sección para mostrar texto y preguntas (antes de enviar respuestas) ---
    # Solo mostrar si hay texto y preguntas cargadas Y las respuestas NO han sido enviadas
    if st.session_state.current_text_id and st.session_state.current_text and st.session_state.current_questions and not st.session_state.answers_submitted:
        st.subheader(f"Texto sobre: {st.session_state.current_text['topic']}")
        st.write(st.session_state.current_text['content'])

        st.subheader("Preguntas de Comprensión")

        # Mostrar preguntas y opciones como radio buttons
        for i, question in enumerate(st.session_state.current_questions):
            st.markdown(f"**Pregunta {i+1}:** {question['question_text']}")
            options_list = [opt['option_text'] for opt in question['options']]

            # Usar un key único para cada radio button group
            # Guardar la opción seleccionada en el estado de sesión
            st.session_state.selected_options[question['id']] = st.radio(
                f"Selecciona una opción para la pregunta {i+1}:",
                options_list,
                key=f"question_{question['id']}",
                index=None # Start with no option selected
            )

        # Botón para enviar respuestas - Solo visible si las respuestas no han sido enviadas
        if st.button("Enviar Respuestas"):
            st.session_state.answers_submitted = True
            correct_count = 0
            total_questions = len(st.session_state.current_questions)

            # Process and record answers
            for question in st.session_state.current_questions:
                selected_option_text = st.session_state.selected_options.get(question['id'])
                selected_option_id = None
                is_correct = False

                if selected_option_text is not None:
                     # Find the selected option ID and check if it's correct
                    selected_option = None
                    for opt in question['options']:
                        if opt['option_text'] == selected_option_text:
                            selected_option_id = opt['id']
                            if opt['is_correct']:
                                is_correct = True
                                correct_count += 1
                            break # Found the selected option

                    # Record progress with the selected option ID
                    record_progress(st.session_state.user_id, st.session_state.current_text_id, question['id'], selected_option_id, is_correct)
                else:
                    # Record progress for unanswered questions
                    record_progress(st.session_state.user_id, st.session_state.current_text_id, question['id'], None, None)


            # Adjust difficulty after completing a text
            adjust_difficulty(st.session_state.user_id)

            # Mark that feedback should be displayed
            st.session_state.feedback_displayed = True

            st.rerun() # Rerun to display the results and feedback


    # --- Sección para mostrar Resultados y Retroalimentación (después de enviar respuestas) ---
    # Solo mostrar si las respuestas han sido enviadas AND feedback_displayed is True
    if st.session_state.answers_submitted and st.session_state.feedback_displayed and st.session_state.current_text and st.session_state.current_questions:
         st.subheader(f"Texto sobre: {st.session_state.current_text['topic']}")
         st.write(st.session_state.current_text['content'])

         st.subheader("Resultados y Retroalimentación")
         correct_count = 0
         total_questions = len(st.session_state.current_questions)

         for i, question in enumerate(st.session_state.current_questions):
             # Get the selected option text from session state
             selected_option_text = st.session_state.selected_options.get(question['id'])
             correct_option_text = None
             is_correct = False

             # Find the correct option text and check if the selected answer was correct
             for opt in question['options']:
                 if opt['is_correct']:
                     correct_option_text = opt['option_text']
                 if opt['option_text'] == selected_option_text and opt['is_correct']:
                      is_correct = True


             st.markdown(f"**Pregunta {i+1}:** {question['question_text']}")

             if selected_option_text is not None:
                 if is_correct:
                     st.success(f"Tu respuesta: {selected_option_text} - ¡Correcto!")
                     correct_count += 1
                 else:
                     st.error(f"Tu respuesta: {selected_option_text} - Incorrecto. La respuesta correcta es: {correct_option_text}")
             else:
                 st.warning(f"No respondiste a esta pregunta. La respuesta correcta es: {correct_option_text}")


         st.subheader("Resumen")
         st.write(f"Obtuviste {correct_count} de {total_questions} respuestas correctas.")
         st.write(f"Tu nuevo nivel de dificultad es: {st.session_state.user_difficulty}")


    # --- Sección de Progreso del Estudiante ---
    st.sidebar.subheader("Tu Progreso")
    if st.session_state.user_id: # Asegurarse de que el usuario está logueado antes de mostrar progreso
        total_attempts, accuracy = get_user_performance_metrics(st.session_state.user_id)
        st.sidebar.write(f"Intentos Totales: {total_attempts}")
        st.sidebar.write(f"Precisión General: {accuracy:.2f}%")

        st.sidebar.subheader("Historial de Lectura")
        reading_history = get_user_reading_history(st.session_state.user_id)
        if reading_history:
            for history_item in reading_history:
                topic, difficulty, total_q, correct_q, last_attempt = history_item
                history_accuracy = (correct_q / total_q) * 100 if total_q > 0 else 0
                st.sidebar.markdown(f"- **{topic}** (Nivel {difficulty}): {correct_q}/{total_q} correctas ({history_accuracy:.1f}%)")
        else:
            st.sidebar.info("Aún no tienes historial de lectura.")
    else:
        st.sidebar.info("Inicia sesión para ver tu progreso.")
