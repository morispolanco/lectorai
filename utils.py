import os
import requests
import json
import streamlit as st

# Obtener clave desde secrets
API_KEY = st.secrets["openrouter_api_key"]

def generate_text(topic, difficulty):
    prompt = f"Genera un texto corto nivel {difficulty} sobre: {topic}. Incluye vocabulario apropiado para estudiantes de bachillerato."
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions ",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "meta-llama/llama-4-maverick:free",
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return "Hubo un error al generar el texto."

def generate_questions(text):
    prompt = f"""
    Basado en este texto: "{text}"
    
    Crea 5 preguntas de opción múltiple con 4 opciones cada una. 
    - 2 de vocabulario
    - 2 de inferencia
    - 1 de pensamiento crítico
    
    Formato JSON:
    [
      {{
        "question": "¿Cuál es el significado de X?",
        "options": ["A", "B", "C", "D"],
        "correct": "A"
      }},
      ...
    ]
    """
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions ",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "meta-llama/llama-4-maverick:free",
            "messages": [{"role": "user", "content": prompt}]
        }
    )

    if response.status_code == 200:
        content = response.json()['choices'][0]['message']['content']
        try:
            return json.loads(content)
        except:
            return []
    else:
        return []
