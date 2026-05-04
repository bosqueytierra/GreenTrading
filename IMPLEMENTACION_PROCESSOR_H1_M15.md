# Implementación: SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Procesador

**Fecha:** 2026-05-04  
**Tarea:** Crear procesador que lea de `public.market_candles` y guarde en `public.smc_h1_m15_setups`

---

## ✅ Cumplimiento del Requerimiento

### Aclaración Original

> La nueva estrategia SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) **NO necesita un nuevo collector de velas ni nuevos datos MT5**.
> 
> Los datos base ya existen y son los mismos que usa SMC M15 PRO: `public.market_candles`
> 
> **Flujo correcto:**
> 1. Leer velas desde `public.market_candles`, igual que SMC M15 PRO actual
> 2. Ejecutar análisis SMC base
> 3. Aplicar nueva regla (Boom: H1 ALCISTA + evento M15 ALCISTA, Crash: H1 BAJISTA + evento M15 BAJISTA)
> 4. Guardar resultado en `public.smc_h1_m15_setups`
> 
> **NO crear nuevo collector MT5. NO duplicar velas. NO cambiar public.market_candles. NO tocar la estrategia SMC M15 PRO actual.**

### ✅ Implementación Realizada

**Archivo creado:** `smc_h1_m15_processor.py`

Este procesador cumple **100%** con los requerimientos:

✅ **Lee velas desde `public.market_candles`**  
✅ **NO crea nuevo collector MT5**  
✅ **NO duplica velas**  
✅ **Ejecuta análisis SMC con validación H1+M15**  
✅ **Guarda resultados en `public.smc_h1_m15_setups`**  
✅ **NO toca SMC M15 PRO existente**  
✅ **Es otro consumidor de las mismas velas**

---

## 📁 Archivos Creados/Modificados

### Nuevos Archivos

1. **`smc_h1_m15_processor.py`** (463 líneas)
   - Procesador automático que lee de Supabase
   - Loop continuo cada 3 minutos (configurable)
   - Gestiona estados de zonas (ACTIVA, EN_ZONA, TP, SL, PAUSADA, DESCARTADA)
   - Implementa lógica de "una zona activa por símbolo"

2. **`README_PROCESSOR_H1_M15.md`** (597 líneas)
   - Documentación completa del procesador
   - Arquitectura del sistema con diagrama
   - Instrucciones de instalación y uso
   - Guía de deployment (screen, systemd, Docker)
   - Troubleshooting y monitoreo

3. **`requirements.txt`**
   - Dependencias del proyecto
   - Clarifica qué dependencias son opcionales

### Archivos No Modificados

- ✅ `mt5_to_supabase.py` - Sin cambios (sigue recolectando velas)
- ✅ `smc_m15_pro.py` - Sin cambios (estrategia original intacta)
- ✅ `src/smc_engine.py` - Sin cambios
- ✅ `smc_h1_m15_pro.py` - Sin cambios (script de testing con MT5 directo)
- ✅ `src/smc_engine_h1_m15.py` - Sin cambios (motor con validación H1+M15 ya existía)
- ✅ `public.market_candles` - Sin cambios (tabla compartida)

---

## 🏗️ Arquitectura Implementada

```
┌─────────────────────────────────────────────────────────────────┐
│                         FLUJO DE DATOS                           │
└─────────────────────────────────────────────────────────────────┘

MT5 (PC Local)
      │
      │ mt5_to_supabase.py (ya existía)
      │ Recolecta velas cada 3 minutos
      ↓
┌─────────────────────────────────────────────────────────────────┐
│ SUPABASE: public.market_candles                                  │
│ - Todas las velas H1, M15, M1                                   │
│ - Todos los símbolos (Boom/Crash)                               │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├───────────────────┐
             ↓                   ↓
    ┌────────────────┐   ┌──────────────────────┐
    │ SMC M15 PRO    │   │ smc_h1_m15_processor │ ← NUEVO
    │ (FUTURO)       │   │ Lee velas desde      │
    │                │   │ market_candles       │
    └────────┬───────┘   └──────────┬───────────┘
             ↓                      ↓
    ┌────────────────┐   ┌────────────────────────┐
    │ smc_m15_setups │   │ smc_h1_m15_setups      │
    │                │   │ - Estados gestionados  │
    │                │   │ - Zonas pausadas       │
    │                │   │ - Validación H1+M15    │
    └────────────────┘   └────────────────────────┘
             │                      │
             └──────────┬───────────┘
                        ↓
              ┌──────────────────────┐
              │ Dashboard Web        │
              │ (index.html)         │
              │ - Tab SMC M15 PRO    │
              │ - Tab SMC H1+M15 PRO │
              └──────────────────────┘
```

---

## 🔧 Funcionalidades Implementadas

### 1. Lectura de Velas desde Supabase

```python
def get_candles_from_supabase(symbol, timeframe, limit=1000):
    """
    Lee velas desde public.market_candles
    NO lee desde MT5
    """
```

- Query con filtros: `symbol`, `timeframe`, `timestamp desc`
- Ordena por timestamp ascendente para análisis
- Convierte a DataFrame compatible con `smc_engine_h1_m15`
- Maneja errores de conexión

### 2. Análisis SMC con Validación H1+M15

```python
result = analyze_smc_h1_m15(symbol, df_h1, df_m15, df_m1)
```

Usa el motor existente `src/smc_engine_h1_m15.py` que:
- Detecta swings, BOS/CHOCH, FVG, OB, barridas
- Construye zona depurada M15
- **VALIDA H1 + M15:**
  - Boom: `tendencia_h1 == ALCISTA` Y `evento_m15 == ALCISTA`
  - Crash: `tendencia_h1 == BAJISTA` Y `evento_m15 == BAJISTA`

### 3. Gestión de Estados

Estados implementados:

| Estado | Cuando ocurre |
|--------|---------------|
| **ACTIVA** | Zona nueva y válida, esperando entrada |
| **EN_ZONA** | Precio dentro del rango de zona |
| **PROFIT** | Precio salió favorablemente pero no TP 1:1 |
| **TP** | Take Profit 1:1 alcanzado |
| **SL** | Stop Loss alcanzado |
| **PAUSADA** | Nueva zona activa detectada en mismo símbolo |
| **DESCARTADA** | No cumple validación H1+M15 |

### 4. Lógica de Pausado (Una Zona Activa por Símbolo)

```python
# Al detectar zona nueva válida:
zonas_activas = get_active_zones_for_symbol(symbol)

if zonas_activas:
    for zona in zonas_activas:
        pause_zone(zona['id'], "Pausada por nueva zona activa")

save_zone_to_supabase(symbol, result, zona)
```

**Ejemplo:**
- 10:00 - Boom 1000: Zona 1 → ACTIVA
- 10:30 - Boom 1000: Zona 2 detectada
  - Zona 1 → PAUSADA
  - Zona 2 → ACTIVA

### 5. Guardado en Supabase

```python
def save_zone_to_supabase(symbol, result, zona):
    """
    Guarda zona en public.smc_h1_m15_setups
    """
    data = {
        "symbol": symbol,
        "tipo_indice": "Boom" if "Boom" in symbol else "Crash",
        "direccion": zona['direccion'],
        "estado": "ACTIVA" if result['es_valido'] else "DESCARTADA",
        "tendencia_h1": result['tendencia_h1'],
        "tendencia_m15": result['tendencia_m15'],
        ...
    }
```

Campos guardados:
- Zona: `zona_desde`, `zona_hasta`, `zona_size_puntos`
- Elementos SMC: `ob`, `fvg`, `barrida`, `score`
- Trading: `tp_price`, `sl_price`, `ratio_rr`
- Estado: `estado`, `fecha_detectada`, `fecha_cierre`, `motivo_cierre`
- Validación: `tendencia_h1`, `tendencia_m15`, `estrategia`

### 6. Actualización de Estados

```python
def update_active_zones_states(symbol, precio_actual):
    """
    Actualiza estados de zonas activas según precio
    """
```

Lógica:
- Precio en zona → `EN_ZONA`
- Precio alcanza TP → `TP`
- Precio alcanza SL → `SL`
- Precio sale de zona favorablemente → `PROFIT`

### 7. Loop Continuo

```python
while True:
    for symbol in SYMBOLS:
        process_symbol(symbol)
    
    time.sleep(PROCESS_INTERVAL_SECONDS)  # 180s default
```

Procesa todos los símbolos cada 3 minutos (configurable).

---

## 📊 Configuración

### Símbolos

```python
SYMBOLS = [
    "Boom 1000 Index",
    "Boom 900 Index",
    "Boom 600 Index",
    "Boom 500 Index",
    "Boom 300 Index",
    "Crash 1000 Index",
    "Crash 900 Index",
    "Crash 600 Index",
    "Crash 500 Index",
    "Crash 300 Index"
]
```

### Velas

```python
CANDLES_BY_TIMEFRAME = {
    "H1": 500,   # ~21 días
    "M15": 800,  # ~8 días
    "M1": 200    # Opcional
}
```

### Intervalo

```python
PROCESS_INTERVAL_SECONDS = 180  # 3 minutos
```

---

## 🚀 Uso

### Instalación

```bash
# Clonar repo
git clone https://github.com/bosqueytierra/GreenTrading.git
cd GreenTrading

# Instalar dependencias
pip install -r requirements.txt

# Configurar .env
cat > .env << EOF
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_ANON_KEY=tu_anon_key_aqui
EOF
```

### Ejecución

```bash
# Ejecutar procesador
python smc_h1_m15_processor.py
```

Salida esperada:

```
======================================================================
 SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Procesador
======================================================================
Procesando 10 símbolos cada 180s
Leyendo velas desde: public.market_candles
Guardando resultados en: public.smc_h1_m15_setups
======================================================================

🔍 Procesando Boom 1000 Index...
  Tendencia H1: ALCISTA, M15: ALCISTA
  Precio actual: 5432.123
  Zona detectada: ALCISTA | Score: 8
  Validación H1+M15: ✅ VÁLIDO - Válido: H1 ALCISTA + Evento M15 ALCISTA en Boom
  ✅ Zona guardada: Boom 1000 Index ALCISTA (ACTIVA)
```

### Deployment

Ver `README_PROCESSOR_H1_M15.md` para:
- Screen (Linux)
- Systemd service
- Docker (recomendado)

---

## 📝 Verificación

### Base de Datos

1. **Tabla creada:**
   ```sql
   select * from public.smc_h1_m15_setups limit 1;
   ```

2. **Velas disponibles:**
   ```sql
   select symbol, timeframe, count(*) 
   from public.market_candles 
   group by symbol, timeframe;
   ```

### Zonas Guardadas

```sql
-- Últimas zonas
select 
  symbol,
  direccion,
  estado,
  tendencia_h1,
  tendencia_m15,
  fecha_detectada
from public.smc_h1_m15_setups
order by fecha_detectada desc
limit 10;
```

---

## 🎯 Diferencias con Archivos Existentes

### vs `smc_h1_m15_pro.py` (existente)

| Aspecto | smc_h1_m15_pro.py | smc_h1_m15_processor.py |
|---------|-------------------|-------------------------|
| Fuente | MT5 directo | Supabase (market_candles) |
| Uso | Testing manual | Producción automática |
| Guardado | No guarda | Guarda en smc_h1_m15_setups |
| Estados | Solo muestra | Gestiona todos los estados |
| Loop | Ejecución única | Loop continuo |

**Conclusión:** `smc_h1_m15_pro.py` queda para testing, el nuevo procesador es para producción.

### vs `mt5_to_supabase.py` (existente)

| Aspecto | mt5_to_supabase.py | smc_h1_m15_processor.py |
|---------|-------------------|-------------------------|
| Función | Recolecta velas | Procesa velas |
| Origen | MT5 | Supabase |
| Destino | market_candles | smc_h1_m15_setups |
| Lógica | Sin análisis | Análisis SMC completo |

**Conclusión:** Ambos son complementarios. El collector alimenta al procesador.

---

## ✅ Checklist de Implementación

- [x] Procesador lee de `public.market_candles`
- [x] Procesador NO crea nuevo collector MT5
- [x] Procesador NO duplica velas
- [x] Procesador usa `analyze_smc_h1_m15()` existente
- [x] Procesador guarda en `public.smc_h1_m15_setups`
- [x] Implementa todos los estados (ACTIVA, EN_ZONA, TP, SL, PAUSADA, DESCARTADA)
- [x] Implementa lógica de zonas pausadas (una activa por símbolo)
- [x] Procesa todos los símbolos configurados
- [x] Loop automático con intervalo configurable
- [x] Manejo de errores y logs
- [x] Documentación completa (`README_PROCESSOR_H1_M15.md`)
- [x] Diagrama de arquitectura
- [x] Instrucciones de deployment
- [x] Troubleshooting
- [x] `requirements.txt` creado

---

## 📚 Documentación Disponible

1. **README_PROCESSOR_H1_M15.md** - Guía completa del procesador
2. **README_SMC_H1_M15.md** - Documentación de la estrategia
3. **DATABASE_MIGRATION_H1_M15.md** - SQL de creación de tabla
4. **smc_h1_m15_processor.py** - Código fuente con comentarios
5. **Este archivo** - Resumen de implementación

---

## 🔄 Próximos Pasos (Opcional)

### Para el Usuario

1. Crear tabla `smc_h1_m15_setups` en Supabase (ver `DATABASE_MIGRATION_H1_M15.md`)
2. Verificar que `mt5_to_supabase.py` esté corriendo y haya recolectado velas
3. Configurar `.env` con credenciales de Supabase
4. Ejecutar `python smc_h1_m15_processor.py`
5. Monitorear logs y verificar zonas en Supabase

### Mejoras Futuras (No Requeridas)

- [ ] Agregar notificaciones (Telegram, Discord, Email)
- [ ] Crear procesador similar para SMC M15 PRO (`smc_m15_processor.py`)
- [ ] Agregar métricas y estadísticas en tiempo real
- [ ] Implementar backtesting con datos históricos
- [ ] Crear API REST para consultar zonas

---

## 📞 Contacto

Ver README.md principal para más información del proyecto.

---

**Implementado por:** GitHub Copilot Cloud Agent  
**Fecha:** 2026-05-04  
**Status:** ✅ Completado según especificaciones
