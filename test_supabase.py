import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ No se encontró SUPABASE_URL o SUPABASE_ANON_KEY en .env")
    quit()

url = f"{SUPABASE_URL}/rest/v1/analisis_zonas"

headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

data = {
    "indice": "Boom 1000 Index",
    "tipo_indice": "BOOM",
    "precio_actual": 14188.388,
    "direccion_buscada": "ALCISTA",
    "temporalidad": "M15",
    "zona_desde": 14187.974,
    "zona_hasta": 14217.166,
    "score": 6,
    "evento": "BOS_ALCISTA",
    "ob": True,
    "fvg": True,
    "barrida": False,
    "zona_util": True,
    "estado_inicial": "PRECIO_DENTRO_DE_ZONA",
    "comentario": "Prueba de conexión desde Felipito Trading"
}

response = requests.post(url, headers=headers, json=data)

print("Status:", response.status_code)
print("Respuesta:")
print(response.text)