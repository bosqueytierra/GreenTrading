# Backend Processors - Documentación

## Resumen

Se ha creado un sistema de procesadores backend que **NO depende del dashboard abierto**. Los procesadores corren independientemente, leen datos desde `public.market_candles` y actualizan sus tablas correspondientes cada 60 segundos.

## Arquitectura

```
┌──────────────────────────────────────┐
│   public.market_candles (fuente)    │
│   Alimentado por mt5_to_supabase.py  │
└────────────┬─────────────────────────┘
             │
             ├─────────────────────────────────┐
             │                                 │
             ▼                                 ▼
┌────────────────────────┐    ┌────────────────────────────┐
│ processor_smc_m15_pro  │    │ processor_smc_tendency_... │
│ (SMC M15 PRO)          │    │ (SMC_TENDENCY_H1_M15)      │
└────────┬───────────────┘    └────────┬───────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────────┐      ┌─────────────────────────────┐
│ smc_m15_setups       │      │ smc_tendency_h1_m15_setups  │
└──────────────────────┘      └─────────────────────────────┘
         │                              │
         └──────────────┬───────────────┘
                        ▼
           ┌────────────────────────┐
           │   Frontend Dashboard   │
           │   (SOLO VISUALIZA)     │
           └────────────────────────┘
```

## Archivos Creados

### 1. `processor_smc_m15_pro.py`
**Estrategia:** SMC M15 PRO  
**Tabla:** `public.smc_m15_setups`  
**Función:** Procesa zonas SMC M15 sin validación H1

**Características:**
- Lee velas de H1, M15 (y opcionalmente M1)
- Ejecuta análisis SMC usando `src/smc_engine.py`
- Crea zonas ACTIVAS
- Actualiza estados: ACTIVA → EN_ZONA → PROFIT/TP/SL
- Pausa zonas cuando aparece una nueva
- Las zonas PAUSADA solo se descartan si tocan SL
- NO usa estado DESCARTADA

### 2. `processor_smc_tendency_h1_m15.py`
**Estrategia:** SMC_TENDENCY_H1_M15  
**Tabla:** `public.smc_tendency_h1_m15_setups`  
**Función:** Procesa zonas SMC con validación H1 + evento M15

**Características:**
- Lee velas de H1, M15 (y opcionalmente M1)
- Ejecuta análisis SMC usando `src/smc_engine_tendency_h1_m15.py`
- **Validación especial:**
  - BOOM: H1 ALCISTA + evento M15 ALCISTA (CHOCH/BOS)
  - CRASH: H1 BAJISTA + evento M15 BAJISTA (CHOCH/BOS)
- Solo guarda zonas VÁLIDAS (no hay DESCARTADA)
- Las zonas inválidas simplemente NO se guardan
- Estados: ACTIVA → EN_ZONA → PROFIT/TP/SL

### 3. `run_processors.py`
**Función:** Script principal que ejecuta ambos procesadores cada 60 segundos

**Características:**
- Ejecuta ambos procesadores en secuencia
- Intervalo configurable (por defecto 60 segundos)
- Manejo de errores robusto
- Se puede detener con Ctrl+C

## Instalación

### Pre-requisitos

1. Python 3.8 o superior
2. Dependencias instaladas:
```bash
pip install -r requirements.txt
```

3. Variables de entorno configuradas en `.env`:
```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_ANON_KEY=tu-clave-anonima
```

4. Collector MT5 corriendo:
```bash
python mt5_to_supabase.py
```
Este debe estar alimentando `public.market_candles` antes de ejecutar los procesadores.

## Uso

### Opción 1: Ejecutar Runner Principal (Recomendado)

```bash
python run_processors.py
```

Este script:
- ✅ Ejecuta ambos procesadores automáticamente
- ✅ Corre cada 60 segundos
- ✅ Maneja errores sin detenerse
- ✅ Se puede detener con Ctrl+C

Salida esperada:
```
======================================================================
 RUN PROCESSORS - Backend Processors Runner
======================================================================
 Procesadores:
   1. SMC M15 PRO        → smc_m15_setups
   2. SMC_TENDENCY_H1_M15 → smc_tendency_h1_m15_setups

 Intervalo: 60 segundos
 Fuente: public.market_candles
======================================================================

Presiona Ctrl+C para detener

######################################################################
# CICLO #1
######################################################################

======================================================================
 CICLO DE PROCESAMIENTO - 2026-05-05 03:30:00
======================================================================

📊 Ejecutando: SMC M15 PRO
──────────────────────────────────────────────────────────────────────
...
```

### Opción 2: Ejecutar Procesadores Individualmente

**Procesador SMC M15 PRO:**
```bash
python processor_smc_m15_pro.py
```

**Procesador SMC_TENDENCY_H1_M15:**
```bash
python processor_smc_tendency_h1_m15.py
```

⚠️ **NOTA:** Estos ejecutan UNA SOLA VEZ. Para ejecución continua, usa `run_processors.py`.

## Verificación

### 1. Verificar que los datos fluyen

```sql
-- Verificar velas en market_candles
SELECT symbol, timeframe, COUNT(*) as velas
FROM public.market_candles
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
```

### 2. Verificar zonas creadas

```sql
-- SMC M15 PRO
SELECT symbol, estado, COUNT(*) as zonas
FROM public.smc_m15_setups
GROUP BY symbol, estado
ORDER BY symbol, estado;

-- SMC_TENDENCY_H1_M15
SELECT symbol, estado, COUNT(*) as zonas
FROM public.smc_tendency_h1_m15_setups
GROUP BY symbol, estado
ORDER BY symbol, estado;
```

### 3. Verificar última actualización

```sql
-- SMC M15 PRO - últimas zonas
SELECT symbol, direccion, estado, fecha_detectada, updated_at
FROM public.smc_m15_setups
ORDER BY updated_at DESC
LIMIT 10;

-- SMC_TENDENCY_H1_M15 - últimas zonas
SELECT symbol, direccion, estado, fecha_detectada, updated_at
FROM public.smc_tendency_h1_m15_setups
ORDER BY updated_at DESC
LIMIT 10;
```

## Configuración

### Intervalo de Ejecución

Para cambiar el intervalo de ejecución (por defecto 60 segundos):

**En `run_processors.py`:**
```python
INTERVAL_SECONDS = 120  # Cambiar a 2 minutos
```

### Símbolos a Procesar

Los símbolos se configuran en cada procesador. Por defecto procesa:
- Boom 1000, 900, 600, 500, 300
- Crash 1000, 900, 600, 500, 300

Para modificar, edita la variable `SYMBOLS` en:
- `processor_smc_m15_pro.py`
- `processor_smc_tendency_h1_m15.py`

### Cantidad de Velas

Para cambiar cuántas velas se leen por timeframe:

```python
CANDLES_BY_TIMEFRAME = {
    "H1": 500,   # Cambiar según necesidad
    "M15": 800,  # Cambiar según necesidad
    "M1": 200    # Opcional
}
```

## Monitoreo

### Logs en Terminal

Los procesadores imprimen logs detallados:
- ✅ Zonas detectadas y guardadas
- ⏸️ Zonas pausadas
- 📊 Cambios de estado
- ❌ Errores (sin detener el proceso)

### Recomendación: Usar nohup (Linux/Mac)

Para correr en background sin que se detenga al cerrar terminal:

```bash
nohup python run_processors.py > processors.log 2>&1 &
```

Ver logs:
```bash
tail -f processors.log
```

Detener:
```bash
ps aux | grep run_processors
kill <PID>
```

### Recomendación: Usar systemd (Linux)

Crear `/etc/systemd/system/greentrading-processors.service`:

```ini
[Unit]
Description=GreenTrading Backend Processors
After=network.target

[Service]
Type=simple
User=tu-usuario
WorkingDirectory=/ruta/a/GreenTrading
ExecStart=/usr/bin/python3 run_processors.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable greentrading-processors
sudo systemctl start greentrading-processors
sudo systemctl status greentrading-processors
```

## Troubleshooting

### Error: "No se encontró SUPABASE_URL o SUPABASE_ANON_KEY"

**Solución:** Verifica que existe el archivo `.env` con:
```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

### Error: "No hay suficientes velas para [símbolo]"

**Causas posibles:**
1. `mt5_to_supabase.py` no está corriendo
2. MT5 no tiene conexión
3. No hay datos históricos para ese símbolo

**Solución:**
```bash
# Verificar collector MT5
python mt5_to_supabase.py

# Verificar datos en Supabase
SELECT symbol, timeframe, COUNT(*) 
FROM public.market_candles 
GROUP BY symbol, timeframe;
```

### Error: "ImportError: No module named 'src.smc_engine'"

**Solución:** Asegúrate de ejecutar desde el directorio raíz del proyecto:
```bash
cd /ruta/a/GreenTrading
python run_processors.py
```

### Los procesadores corren pero no crean zonas

**Verificar:**
1. ¿Hay eventos M15 detectados? (CHOCH/BOS)
2. Para SMC_TENDENCY_H1_M15: ¿La validación H1+M15 pasa?

**Debug:**
Revisar los logs del procesador. Debe mostrar:
```
Zona detectada: ALCISTA | Score: 3
Validación H1+M15: ✅ VÁLIDO - ...
✅ Zona guardada: Boom 1000 Index ALCISTA (ACTIVA)
```

## Frontend (Dashboard)

**IMPORTANTE:** El frontend ahora **SOLO LEE Y VISUALIZA**.

### Qué hace el frontend:
- ✅ Lee zonas desde tablas
- ✅ Muestra dashboard con zonas activas
- ✅ Muestra historial de zonas
- ✅ Actualiza visualización cada 60 segundos

### Qué NO hace el frontend:
- ❌ NO procesa SMC
- ❌ NO crea zonas nuevas
- ❌ NO actualiza estados de zonas
- ❌ NO ejecuta trackZoneHistory() para PROCESAR

**ANTES (malo):**
```
Dashboard abierto → app.js ejecuta:
  - fetchAllIndices()
  - trackZoneHistory() ← PROCESA Y GUARDA
  - updateSetup()

Dashboard cerrado → NADA SE PROCESA ❌
```

**AHORA (correcto):**
```
run_processors.py → Corre cada 60s:
  - processor_smc_m15_pro
  - processor_smc_tendency_h1_m15
  → PROCESA Y GUARDA ✅

Dashboard → SOLO LEE Y MUESTRA ✅
```

## Separación de Responsabilidades

| Componente | Responsabilidad |
|------------|-----------------|
| **mt5_to_supabase.py** | Collector: Lee MT5 → Escribe `market_candles` |
| **processor_smc_m15_pro.py** | Backend: Lee `market_candles` → Procesa SMC M15 PRO → Escribe `smc_m15_setups` |
| **processor_smc_tendency_h1_m15.py** | Backend: Lee `market_candles` → Procesa SMC_TENDENCY → Escribe `smc_tendency_h1_m15_setups` |
| **run_processors.py** | Orchestrator: Ejecuta ambos procesadores cada 60s |
| **Frontend (app.js)** | Visualizador: Lee tablas → Muestra dashboard/historial |

## Siguiente Paso: Modificar Frontend

**⚠️ NO INCLUIDO EN ESTA IMPLEMENTACIÓN**

Para completar la separación, el frontend debe:
1. ELIMINAR lógica de procesamiento en `trackZoneHistory()`
2. Solo LEER zonas desde tablas
3. No ejecutar análisis SMC en el navegador

Esto se hará en una futura iteración según las instrucciones.

## Resumen

✅ **Creado:**
- `processor_smc_m15_pro.py` - Procesador SMC M15 PRO
- `processor_smc_tendency_h1_m15.py` - Procesador SMC_TENDENCY_H1_M15  
- `run_processors.py` - Runner que ejecuta ambos cada 60s

✅ **Cada procesador:**
- Lee desde `public.market_candles`
- Procesa independientemente
- Escribe en su tabla exclusiva
- NO depende del dashboard

✅ **Para ejecutar:**
```bash
python run_processors.py
```

✅ **Frontend queda como:**
- SOLO visualizador
- Lee zonas ya procesadas
- Actualiza cada 60 segundos

🎯 **Objetivo logrado:** Procesamiento backend independiente del navegador.
