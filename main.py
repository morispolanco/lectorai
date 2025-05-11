import streamlit as st
import db
import utils

st.set_page_config(page_title="LectorAI", page_icon="📚")

# Inicializar base de datos
db.init_db()

# Estado de sesión
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'student_id' not in st.session_state:
    st.session_state.student_id = None
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = ""
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'text' not in st.session_state:
    st.session_state.text = ""

# Menú lateral
with st.sidebar:
    if st.session_state.logged_in:
        st.write(f"Bienvenido, {st.session_state.username}")
        if st.button("Cerrar sesión"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.student_id = None
            st.rerun()
    else:
        option = st.selectbox("Acceso", ["Iniciar sesión", "Registrarse"])
        if option == "Iniciar sesión":
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.button("Entrar"):
                user = db.login_student(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.student_id = user[0]
                    st.success("Inicio de sesión exitoso")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
        elif option == "Registrarse":
            new_user = st.text_input("Nuevo usuario")
            new_pass = st.text_input("Nueva contraseña", type="password")
            if st.button("Registrar"):
                if db.register_student(new_user, new_pass):
                    st.success("Registro exitoso")
                else:
                    st.error("El nombre de usuario ya existe")

if st.session_state.logged_in:
    st.title("📚 LectorAI - Mejora tu comprensión lectora")

    col1, col2 = st.columns(2)
    with col1:
        topic = st.selectbox("Tema", ["Cultura general", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"])
    with col2:
        difficulty = st.selectbox("Dificultad", ["Fácil", "Medio", "Avanzado"])

    if st.button("Obtener texto"):
        with st.spinner("Generando texto..."):
            st.session_state.text = utils.generate_text(topic, difficulty)
            st.session_state.questions = utils.generate_questions(st.session_state.text)
            st.session_state.current_topic = topic

    if st.session_state.text:
        if "[ERROR]" in st.session_state.text:
            st.error(st.session_state.text)
        else:
            st.markdown("### 📘 Texto generado:")
            st.write(st.session_state.text)

    if st.session_state.questions:
        st.markdown("### ❓ Preguntas")
        answers = []
        correct_count = 0

        for i, q in enumerate(st.session_state.questions):
            st.markdown(f"**{i+1}. {q['question']}**")
            answer = st.radio("", options=q["options"], key=f"q{i}")
            answers.append(answer)
            if answer == q["correct"]:
                correct_count += 1
                st.success("✅ Correcto")
            elif answer:
                st.error(f"❌ Incorrecto. La respuesta correcta era: {q['correct']}")

        if all(answers):
            score = correct_count / len(answers)
            st.info(f"Tuviste {correct_count} respuestas correctas de {len(answers)}")
            db.save_progress(st.session_state.student_id, st.session_state.current_topic, difficulty, score)

    # Mostrar progreso
    st.sidebar.markdown("### 📊 Tu progreso")
    progress = db.get_progress(st.session_state.student_id)
    if progress:
        for p in progress:
            st.sidebar.write(f"{p[0]} | Nivel: {p[1]} | Acierto: {p[2]*100:.1f}%")
    else:
        st.sidebar.write("No hay registros aún.")
