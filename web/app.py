import os
import requests
from flask import Flask, render_template_string
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Template HTML inline
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenTrading - Análisis de Zonas</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .stats {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 20px 40px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #667eea;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .stat-card .number {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .error {
            background: #ff4444;
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            font-size: 1.2em;
        }
        table {
            width: 100%;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        thead {
            background: #667eea;
            color: white;
        }
        th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
        }
        tr:last-child td {
            border-bottom: none;
        }
        tbody tr:hover {
            background: #f5f5f5;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .badge-alcista {
            background: #4caf50;
            color: white;
        }
        .badge-bajista {
            background: #f44336;
            color: white;
        }
        .badge-boom {
            background: #ff9800;
            color: white;
        }
        .badge-crash {
            background: #9c27b0;
            color: white;
        }
        .badge-true {
            background: #2196f3;
            color: white;
        }
        .badge-false {
            background: #ccc;
            color: #666;
        }
        .score {
            font-weight: bold;
            font-size: 1.1em;
        }
        .score-high {
            color: #4caf50;
        }
        .score-medium {
            color: #ff9800;
        }
        .score-low {
            color: #f44336;
        }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #666;
            font-size: 1.2em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌿 GreenTrading - Dashboard</h1>
        
        {% if error %}
        <div class="error">
            ❌ {{ error }}
        </div>
        {% else %}
        <div class="stats">
            <div class="stat-card">
                <h3>Total Registros</h3>
                <div class="number">{{ total }}</div>
            </div>
            <div class="stat-card">
                <h3>Alcistas</h3>
                <div class="number" style="color: #4caf50;">{{ alcistas }}</div>
            </div>
            <div class="stat-card">
                <h3>Bajistas</h3>
                <div class="number" style="color: #f44336;">{{ bajistas }}</div>
            </div>
        </div>
        
        {% if zonas %}
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Índice</th>
                    <th>Tipo</th>
                    <th>Dirección</th>
                    <th>Temporalidad</th>
                    <th>Zona (Desde-Hasta)</th>
                    <th>Score</th>
                    <th>Evento</th>
                    <th>OB</th>
                    <th>FVG</th>
                    <th>Barrida</th>
                    <th>Comentario</th>
                </tr>
            </thead>
            <tbody>
                {% for zona in zonas %}
                <tr>
                    <td>{{ zona.id }}</td>
                    <td>{{ zona.indice }}</td>
                    <td>
                        <span class="badge badge-{{ zona.tipo_indice|lower }}">
                            {{ zona.tipo_indice }}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-{{ zona.direccion_buscada|lower }}">
                            {{ zona.direccion_buscada }}
                        </span>
                    </td>
                    <td>{{ zona.temporalidad }}</td>
                    <td>
                        {{ "%.2f"|format(zona.zona_desde) }} - {{ "%.2f"|format(zona.zona_hasta) }}
                    </td>
                    <td>
                        <span class="score {% if zona.score >= 7 %}score-high{% elif zona.score >= 5 %}score-medium{% else %}score-low{% endif %}">
                            {{ zona.score }}
                        </span>
                    </td>
                    <td>{{ zona.evento }}</td>
                    <td>
                        <span class="badge badge-{{ 'true' if zona.ob else 'false' }}">
                            {{ 'SÍ' if zona.ob else 'NO' }}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-{{ 'true' if zona.fvg else 'false' }}">
                            {{ 'SÍ' if zona.fvg else 'NO' }}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-{{ 'true' if zona.barrida else 'false' }}">
                            {{ 'SÍ' if zona.barrida else 'NO' }}
                        </span>
                    </td>
                    <td>{{ zona.comentario or '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="no-data">
            No hay datos disponibles
        </div>
        {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""


def obtener_zonas_supabase():
    """Lee los últimos 20 registros de analisis_zonas desde Supabase"""
    
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None, "No se encontró configuración de Supabase (SUPABASE_URL o SUPABASE_ANON_KEY en .env)"
    
    try:
        # Endpoint de Supabase con orden descendente y límite de 20
        url = f"{SUPABASE_URL}/rest/v1/analisis_zonas"
        
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json"
        }
        
        # Parámetros para ordenar por ID descendente y limitar a 20
        params = {
            "order": "id.desc",
            "limit": 20
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"Error al obtener datos: {response.status_code} - {response.text}"
            
    except Exception as e:
        return None, f"Error de conexión: {str(e)}"


@app.route('/')
def index():
    """Endpoint principal que muestra los últimos 20 análisis de zonas"""
    
    zonas, error = obtener_zonas_supabase()
    
    if error:
        return render_template_string(HTML_TEMPLATE, error=error, zonas=[], total=0, alcistas=0, bajistas=0)
    
    # Calcular estadísticas
    total = len(zonas)
    alcistas = sum(1 for z in zonas if z.get('direccion_buscada') == 'ALCISTA')
    bajistas = sum(1 for z in zonas if z.get('direccion_buscada') == 'BAJISTA')
    
    return render_template_string(
        HTML_TEMPLATE,
        zonas=zonas,
        error=None,
        total=total,
        alcistas=alcistas,
        bajistas=bajistas
    )


if __name__ == '__main__':
    print("🌿 GreenTrading Web App")
    print("=" * 50)
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"Supabase Key configurada: {'✅' if SUPABASE_ANON_KEY else '❌'}")
    print("=" * 50)
    print("\n🚀 Iniciando servidor en http://localhost:5000")
    print("\nPresiona Ctrl+C para detener\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
