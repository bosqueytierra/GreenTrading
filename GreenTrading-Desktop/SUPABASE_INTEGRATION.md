# Integración Supabase - GreenTrading Desktop

## 📋 Resumen

Esta integración permite persistir los setups detectados por SMC M15 PRO en Supabase, con una pantalla de historial que se actualiza en tiempo real tipo terminal de trading profesional.

## 🎯 Características Principales

### Dashboard
- Detección de zonas SMC M15 PRO cada 1 segundo
- Cálculo automático de entrada, stoploss y TP 1:1
- Sincronización automática con Supabase en background
- Zero impacto visual en el dashboard actual

### Historial
- **Auto-refresh cada 5 segundos** con actualización incremental silenciosa
- **Diff-based updates**: Solo actualiza celdas que cambiaron
- **Preserva scroll position**: Mantiene posición visual del usuario
- **Preserva filtros activos**: Los filtros persisten entre refreshes
- **NO reconstruye DOM completo**: Zero flickering
- **Transiciones CSS suaves**: Cambios visuales profesionales
- **Indicador live discreto**: Punto pulsante sin loaders grandes

### Estados

**Estados Dashboard:**
- `SIN_SETUP`: No hay zona válida
- `ESPERANDO_ENTRADA`: Zona válida, precio lejos (>50 puntos)
- `LLEGANDO_A_ZONA`: Precio acercándose (10-50 puntos)
- `EN_ZONA`: Precio dentro de la zona
- `PROFIT`: Precio superó entrada en dirección esperada

**Estados Historial:**
- `ESPERANDO_ENTRADA`: Setup activo, esperando
- `LLEGANDO_A_ZONA`: Precio acercándose
- `EN_ZONA`: Precio en zona
- `PROFIT`: En ganancia flotante
- `TP`: Take profit alcanzado (cerrado)
- `SL`: Stop loss alcanzado (cerrado)
- `DESCARTADA`: Zona invalidada (no usado en SMC_M15_PRO)

## ⚙️ Configuración

### 1. Instalar Dependencias Python

```bash
cd GreenTrading-Desktop/backend
pip install -r requirements.txt
```

Esto instalará:
- `supabase==2.3.0` - Cliente de Supabase

### 2. Configurar Variables de Entorno

Copiar el template de configuración:

```bash
cp backend/.env.example backend/.env
```

Editar `backend/.env` con tus credenciales de Supabase:

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_ANON_KEY=tu-anon-key-aqui
```

### 3. Crear Tabla en Supabase

Ejecutar el siguiente SQL en Supabase SQL Editor:

```sql
-- Create green_trading_setups table
CREATE TABLE IF NOT EXISTS green_trading_setups (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    tendencia_h1 TEXT,
    tendencia_m15 TEXT,
    ultimo_evento_m15 TEXT,
    entrada DECIMAL(10, 2),
    stoploss DECIMAL(10, 2),
    tp_1_1 DECIMAL(10, 2),
    score INTEGER DEFAULT 0,
    ob BOOLEAN DEFAULT FALSE,
    fvg BOOLEAN DEFAULT FALSE,
    barrida BOOLEAN DEFAULT FALSE,
    estado TEXT NOT NULL,
    estado_dashboard TEXT,
    precio_detectado DECIMAL(10, 2),
    precio_actual DECIMAL(10, 2),
    resultado DECIMAL(10, 2),
    resultado_puntos DECIMAL(10, 2),
    motivo_cierre TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_green_trading_setups_symbol ON green_trading_setups(symbol);
CREATE INDEX IF NOT EXISTS idx_green_trading_setups_estado ON green_trading_setups(estado);
CREATE INDEX IF NOT EXISTS idx_green_trading_setups_strategy ON green_trading_setups(strategy_id);
CREATE INDEX IF NOT EXISTS idx_green_trading_setups_created_at ON green_trading_setups(created_at DESC);

-- Enable RLS
ALTER TABLE green_trading_setups ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Allow SELECT for all" ON green_trading_setups FOR SELECT USING (true);
CREATE POLICY "Allow INSERT for all" ON green_trading_setups FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow UPDATE for all" ON green_trading_setups FOR UPDATE USING (true);
```

## 🚀 Uso

### Iniciar el Backend

```bash
cd GreenTrading-Desktop/backend
python api_server.py
```

El backend iniciará en `http://127.0.0.1:8765`

### Iniciar la Aplicación Electron

```bash
cd GreenTrading-Desktop
npm start
```

### Navegación

1. **Dashboard**: Pantalla principal que se actualiza cada 1 segundo
2. **Historial**: Click en "📜 Historial" en el sidebar
   - Auto-refresh cada 5 segundos (silencioso)
   - Filtros por símbolo, estado, fechas
   - Estadísticas TP/SL por símbolo

## 📊 Flujo de Datos

```
MT5 → Backend API → SMC Service → Dashboard
                         ↓
                    Supabase
                         ↓
                    Historial
```

1. **Dashboard detecta zona válida** (cada 1s)
2. **SMC service calcula** entrada, stoploss, TP, estados
3. **Dashboard sincroniza con Supabase** (background, no bloquea UI)
4. **Historial lee desde Supabase** (cada 5s)
5. **Historial actualiza solo celdas cambiadas** (diff-based)

## 🔧 API Endpoints

### POST /api/setups
Crear o actualizar un setup.

**Request Body:**
```json
{
    "strategy_id": "SMC_M15_PRO",
    "strategy_name": "SMC M15 PRO",
    "symbol": "Boom 1000 Index",
    "tendencia_h1": "ALCISTA",
    "tendencia_m15": "ALCISTA",
    "ultimo_evento_m15": "CHOCH ALCISTA",
    "entrada": 1234.56,
    "stoploss": 1230.00,
    "tp_1_1": 1239.12,
    "score": 3,
    "ob": true,
    "fvg": true,
    "barrida": true,
    "estado": "ESPERANDO_ENTRADA",
    "estado_dashboard": "ESPERANDO_ENTRADA",
    "precio_detectado": 1250.00,
    "precio_actual": 1250.00
}
```

**Response:**
```json
{
    "success": true,
    "action": "created" | "updated",
    "data": { ... }
}
```

### GET /api/setups/active
Obtener setup activo por estrategia, símbolo, entrada y stoploss.

**Query Params:**
- `strategy_id`: Strategy ID (e.g., "SMC_M15_PRO")
- `symbol`: Symbol name
- `entrada`: Entry price
- `stoploss`: Stop loss price

### GET /api/setups/history
Obtener historial con filtros.

**Query Params:**
- `symbol`: Filter by symbol (optional)
- `estado`: Filter by estado (optional)
- `from_date`: Filter from date ISO format (optional)
- `to_date`: Filter to date ISO format (optional)
- `limit`: Max results (default 100)

### GET /api/setups/summary
Obtener resumen TP/SL por símbolo.

**Response:**
```json
{
    "success": true,
    "data": {
        "Boom 1000 Index": {"tp": 5, "sl": 2},
        "Crash 1000 Index": {"tp": 3, "sl": 4}
    }
}
```

## 🎨 UX Profesional

La pantalla de historial está diseñada para sentirse como un terminal de trading profesional:

### Características UX:
- ✅ **Zero flickering**: NO hay reconstrucción completa del DOM
- ✅ **Scroll preservado**: Mantiene posición visual del usuario
- ✅ **Filtros preservados**: Los filtros persisten entre refreshes
- ✅ **Transiciones suaves**: CSS transitions para cambios de estado
- ✅ **Indicador discreto**: Punto pulsante sin loaders grandes
- ✅ **Actualización silenciosa**: Los datos cambian en vivo

### Inspiración:
- TradingView
- MetaTrader 5
- Binance
- Quantower

## 📝 Notas Importantes

1. **NO se guardan velas en Supabase**: Solo setups con contexto pre-calculado
2. **NO se agrega SQLite**: Supabase es la única base de datos
3. **MT5 sigue siendo la fuente de datos**: Las velas se leen desde MT5
4. **Lógica SMC base NO se toca**: Solo se agregan cálculos de estados
5. **Dashboard NO cambia visualmente**: La sincronización es background

## 🐛 Troubleshooting

### Error: "Supabase service not available"
- Verificar que `supabase==2.3.0` está instalado
- Verificar que `.env` existe y tiene las variables correctas

### Error: "Failed to load historial data"
- Verificar que el backend está corriendo en `http://127.0.0.1:8765`
- Verificar que la tabla `green_trading_setups` existe en Supabase
- Verificar las políticas RLS en Supabase

### El historial no se actualiza
- Abrir la consola del navegador (F12)
- Verificar logs de `🔄 Auto-refresh triggered`
- Verificar que no hay errores de CORS

### Los setups no se sincronizan
- Verificar logs del backend Python
- Verificar que el dashboard detecta zonas válidas
- Verificar que los setups tienen `entrada` y `stoploss` calculados

## 📚 Archivos Modificados

### Nuevos Archivos:
- `backend/supabase_service.py` - Servicio de Supabase
- `backend/.env.example` - Template de configuración
- `frontend/pages/historial.html` - Pantalla de historial
- `frontend/assets/js/historial.js` - Lógica de actualización incremental
- `frontend/assets/css/historial.css` - Estilos profesionales

### Archivos Modificados:
- `backend/requirements.txt` - Agregado supabase==2.3.0
- `backend/api_server.py` - Agregados endpoints REST
- `backend/smc_m15_service.py` - Agregados cálculos de niveles y estados
- `frontend/pages/dashboard.html` - Agregado link a historial
- `frontend/assets/js/dashboard.js` - Agregada sincronización Supabase

## 🔐 Seguridad

- Las credenciales de Supabase se almacenan en `.env` (NO en git)
- RLS (Row Level Security) está habilitado en Supabase
- Políticas configuradas: SELECT, INSERT, UPDATE (NO DELETE)
- El backend valida campos requeridos antes de guardar

## 🚀 Próximos Pasos

1. Configurar variables de entorno
2. Crear tabla en Supabase
3. Testing completo del flujo
4. Monitorear logs del backend
5. Validar UX en historial
