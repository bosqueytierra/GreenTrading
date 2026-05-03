# GreenTrading Dashboard - GitHub Pages

Dashboard web con diseño moderno estilo Alinear para visualizar análisis SMC de todos los índices en tiempo real desde Supabase.

## 🚀 Configuración

### 1. Configurar credenciales de Supabase

Las credenciales ya están configuradas en `assets/app.js`:

```javascript
const SUPABASE_URL = 'https://rqjmndaqxxgljpubnfkg.supabase.co';
const SUPABASE_ANON_KEY = '...'; // Ya configurado
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
├── index.html           # Página principal con login y dashboard
├── graficos/
│   └── Green.png       # Logo de GreenTrading
├── assets/
│   ├── style.css       # Estilos modernos (tema claro Alinear + login oscuro)
│   └── app.js          # Lógica de login y conexión a Supabase
└── README_DASHBOARD.md # Este archivo
```

## ✨ Características

### Login
- 🔐 Autenticación con usuario y contraseña
- 💾 Sesión persistente con localStorage
- 🚪 Botón de cerrar sesión
- 👤 Usuarios válidos:
  - **LCarvajal** / MarioTonga
  - **SMorales** / MarioTonga

### Dashboard
- ✅ Diseño moderno estilo Alinear (tema claro profesional)
- ✅ Vista de todos los índices simultáneamente (10 índices)
- ✅ Tablas separadas para índices Boom y Crash
- ✅ Análisis SMC completo por cada índice
- ✅ Selector de estrategia (SMC M15 PRO)
- ✅ Auto-refresh cada 30 segundos
- ✅ Información detallada por índice:
  - Tendencia H1 y M15
  - Dirección operativa
  - Último evento M15
  - Zona madre M15 (desde/hasta)
  - Zona fina M1 (desde/hasta)
  - Score del setup
  - Order Block (OB)
  - Fair Value Gap (FVG)
  - Barrida detectada
  - Estado (En Zona / Fuera Zona)
  - Precio actual
  - Hora de actualización
- ✅ Responsive (compatible con móviles)
- ✅ 100% estático (sin backend, sin Python en frontend)
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

1. Abre el dashboard en tu navegador
2. Ingresa con uno de los usuarios válidos:
   - Usuario: **LCarvajal** / Contraseña: **MarioTonga**
   - Usuario: **SMorales** / Contraseña: **MarioTonga**
3. El dashboard mostrará todos los índices con análisis SMC en tiempo real
4. Los datos se actualizarán automáticamente cada 30 segundos
5. El script `mt5_to_supabase.py` debe estar corriendo en tu PC local para alimentar datos

## 🎨 Diseño

### Tema Login (Oscuro)
- Fondo degradado oscuro con efectos visuales
- Card centrada con bordes redondeados
- Logo de GreenTrading
- Formulario minimalista

### Tema Dashboard (Claro - Estilo Alinear)
- Fondo gris muy suave (#f5f7fa)
- Cards blancas con sombras sutiles
- Verde como color principal (#22c55e)
- Rojo suave para alertas (#ef4444)
- Tipografía limpia y profesional
- Tablas con hover effects
- Badges de estado con colores

## 🔧 Personalización

### Cambiar intervalo de auto-refresh

Edita en `assets/app.js`:
```javascript
const AUTO_REFRESH_SECONDS = 30; // Cambiar a los segundos deseados
```

### Agregar nuevos usuarios

Edita en `assets/app.js`:
```javascript
const VALID_USERS = {
    'NuevoUsuario': 'ContraseñaSegura',
    'LCarvajal': 'MarioTonga',
    'SMorales': 'MarioTonga'
};
```

### Agregar más estrategias

Edita en `index.html` la sección de `<select id="strategySelect">` y agrega nuevas opciones. Luego implementa la lógica en `app.js`.

## 📝 Notas

- No se requiere Flask ni Python en el frontend
- Los datos se leen directamente desde Supabase vía REST API
- Compatible con cualquier hosting estático (GitHub Pages, Netlify, Vercel, etc.)
- El dashboard solo lee datos, no los modifica
- El análisis SMC se ejecuta en el navegador con JavaScript
- La sesión persiste entre recargas de página usando localStorage
