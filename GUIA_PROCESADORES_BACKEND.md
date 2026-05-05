# GUÍA RÁPIDA - Procesadores Backend

## ¿Qué se creó?

Se han creado 3 archivos nuevos para sacar el procesamiento del frontend:

1. **`processor_smc_m15_pro.py`** - Procesador para SMC M15 PRO
2. **`processor_smc_tendency_h1_m15.py`** - Procesador para SMC_TENDENCY_H1_M15
3. **`run_processors.py`** - Script que ejecuta ambos cada 60 segundos

## ¿Cómo funciona ahora?

### ANTES (problema):
```
Dashboard abierto → app.js procesa → guarda en DB
Dashboard cerrado → ❌ NADA se procesa
```

### AHORA (solución):
```
run_processors.py → Corre cada 60s en background
  ├─ processor_smc_m15_pro → public.smc_m15_setups
  └─ processor_smc_tendency_h1_m15 → public.smc_tendency_h1_m15_setups

Dashboard → SOLO lee y visualiza ✅
```

## Cómo ejecutar

### Paso 0: Verificar flag en frontend

Abrir `assets/app.js` y verificar que el flag esté habilitado:

```javascript
const BACKEND_PROCESSORS_ENABLED = true; // ← Debe estar en true
```

**¿Por qué?** Para evitar que frontend y backend escriban simultáneamente (doble escritura).

Ver más: `README_FRONTEND_READONLY_MODE.md`

### Paso 1: Asegurar que el collector MT5 está corriendo

```bash
python mt5_to_supabase.py
```

Este debe estar alimentando `public.market_candles` primero.

### Paso 2: Ejecutar los procesadores

```bash
python run_processors.py
```

✅ Esto ejecuta ambos procesadores cada 60 segundos  
✅ Corre independientemente del navegador  
✅ Para detener: `Ctrl+C`

## Qué hace cada procesador

### processor_smc_m15_pro.py
- Lee velas de `public.market_candles`
- Procesa SMC M15 PRO (sin validación H1)
- Guarda SOLO en `public.smc_m15_setups`
- Crea zonas ACTIVAS
- Actualiza estados: ACTIVA → EN_ZONA → PROFIT/TP/SL
- Pausa zonas cuando aparece una nueva

### processor_smc_tendency_h1_m15.py
- Lee velas de `public.market_candles`
- Procesa SMC_TENDENCY_H1_M15 (con validación H1 + evento M15)
- Guarda SOLO en `public.smc_tendency_h1_m15_setups`
- Solo guarda zonas VÁLIDAS
- Actualiza estados: ACTIVA → EN_ZONA → PROFIT/TP/SL

## Verificar que funciona

### 1. Ver logs en terminal

Debe mostrar:
```
======================================================================
 CICLO DE PROCESAMIENTO - 2026-05-05 03:30:00
======================================================================

📊 Ejecutando: SMC M15 PRO
──────────────────────────────────────────────────────────────────────
📊 Procesando: Boom 1000 Index
  Tendencia H1: ALCISTA, M15: ALCISTA
  Precio actual: 1234.567
  Zona detectada: ALCISTA | Score: 3
  ✅ Zona guardada: Boom 1000 Index ALCISTA (ACTIVA)
...
```

### 2. Verificar en base de datos

```sql
-- Ver últimas zonas creadas
SELECT symbol, direccion, estado, fecha_detectada 
FROM public.smc_m15_setups 
ORDER BY fecha_detectada DESC 
LIMIT 5;

SELECT symbol, direccion, estado, fecha_detectada 
FROM public.smc_tendency_h1_m15_setups 
ORDER BY fecha_detectada DESC 
LIMIT 5;
```

### 3. Verificar en dashboard

- Abrir dashboard en navegador
- Debe mostrar zonas procesadas por los procesadores backend
- Dashboard se actualiza cada 60 segundos automáticamente

## Configuración

### Cambiar intervalo de ejecución

Edita `run_processors.py`:
```python
INTERVAL_SECONDS = 120  # Cambiar de 60 a 120 segundos
```

### Cambiar símbolos a procesar

Edita en cada procesador la variable `SYMBOLS`:
```python
SYMBOLS = [
    "Boom 1000 Index",
    "Crash 1000 Index"
    # Agregar o quitar según necesidad
]
```

## Ejecutar en producción

### Opción 1: nohup (Linux/Mac)

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

### Opción 2: systemd (Linux)

Crear servicio en `/etc/systemd/system/greentrading-processors.service`:

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
```

## Problemas comunes

### "No se encontró SUPABASE_URL"

Solución: Verifica archivo `.env`:
```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_ANON_KEY=tu-clave-anonima
```

### "No hay suficientes velas"

Solución: Asegúrate que `mt5_to_supabase.py` está corriendo y hay datos en `public.market_candles`.

### Los procesadores corren pero no crean zonas

1. Verifica que hay eventos M15 (CHOCH/BOS) en los logs
2. Para SMC_TENDENCY_H1_M15: verifica que pasa validación H1+M15

## Siguiente paso

~~Este trabajo crea los procesadores backend. El siguiente paso sería:~~

~~**Modificar el frontend para que NO procese**:~~
~~- Eliminar lógica de procesamiento en `trackZoneHistory()`~~
~~- Solo leer y visualizar zonas~~
~~- No ejecutar análisis SMC en navegador~~

✅ **COMPLETADO:** Frontend ahora tiene modo read-only con `BACKEND_PROCESSORS_ENABLED = true`.

Ver documentación completa: `README_FRONTEND_READONLY_MODE.md`

⚠️ **IMPORTANTE:** El flag debe mantenerse en `true` cuando los procesadores backend están corriendo para evitar doble escritura.

## Resumen

✅ **Creado:**
- `processor_smc_m15_pro.py`
- `processor_smc_tendency_h1_m15.py`
- `run_processors.py`
- `README_BACKEND_PROCESSORS.md` (documentación completa)
- `README_FRONTEND_READONLY_MODE.md` (modo read-only del frontend)

✅ **Flag añadido:**
```javascript
// assets/app.js
const BACKEND_PROCESSORS_ENABLED = true;
```

✅ **Para ejecutar:**
```bash
python run_processors.py
```

✅ **Resultado:**
- Procesamiento independiente del navegador
- Actualización cada 60 segundos
- Frontend en modo read-only (no escribe)
- Sin doble escritura ni conflictos

🎯 **Objetivo logrado:** El historial se actualiza sin necesidad de tener el dashboard abierto y sin conflictos de escritura.
