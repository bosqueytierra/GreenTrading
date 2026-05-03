# GreenTrading Dashboard - GitHub Pages

Dashboard web estático para visualizar datos de trading en tiempo real desde Supabase.

## 🚀 Configuración

### 1. Configurar credenciales de Supabase

Edita el archivo `assets/app.js` y reemplaza estas líneas con tus credenciales reales:

```javascript
const SUPABASE_URL = 'https://tu-proyecto.supabase.co';
const SUPABASE_ANON_KEY = 'tu-anon-key-aqui';
```

### 2. Publicar en GitHub Pages

1. Ve a Settings > Pages en tu repositorio
2. En "Source", selecciona la rama que contiene estos archivos
3. Selecciona "/ (root)" como carpeta
4. Guarda los cambios
5. Tu dashboard estará disponible en: `https://bosqueytierra.github.io/GreenTrading/`

## 📁 Estructura

```
GreenTrading/
├── index.html           # Página principal del dashboard
├── assets/
│   ├── style.css       # Estilos (tema oscuro profesional)
│   └── app.js          # Lógica de conexión a Supabase
└── README_DASHBOARD.md # Este archivo
```

## ✨ Características

- ✅ Diseño oscuro y profesional
- ✅ Conexión directa a Supabase desde JavaScript
- ✅ Selector de símbolo (Boom/Crash indices)
- ✅ Selector de timeframe (M1, M15, H1)
- ✅ Auto-refresh cada 30 segundos
- ✅ Muestra últimas 10 velas en tabla
- ✅ Tarjetas con métricas principales
- ✅ Responsive (compatible con móviles)
- ✅ 100% estático (sin backend, sin Python)
- ✅ Compatible con GitHub Pages

## 🔒 Seguridad de Supabase

Asegúrate de configurar las políticas RLS (Row Level Security) en Supabase para la tabla `market_candles`:

```sql
-- Permitir lectura anónima de market_candles
CREATE POLICY "Enable read access for all users" ON "public"."market_candles"
FOR SELECT
USING (true);
```

## 🎯 Uso

1. El script `mt5_to_supabase.py` debe estar corriendo en tu PC local
2. Abre el dashboard en tu navegador
3. Selecciona símbolo y timeframe
4. Los datos se actualizarán automáticamente cada 30 segundos

## 🔧 Personalización

### Cambiar intervalo de auto-refresh

Edita en `assets/app.js`:
```javascript
const AUTO_REFRESH_SECONDS = 30; // Cambiar a los segundos deseados
```

### Agregar más símbolos

Edita `index.html` en la sección de `<select id="symbolSelect">` y agrega nuevas opciones.

## 📝 Notas

- No se requiere Flask ni Python en el frontend
- Los datos se leen directamente desde Supabase vía REST API
- Compatible con cualquier hosting estático (GitHub Pages, Netlify, Vercel, etc.)
- El dashboard solo lee datos, no los modifica
