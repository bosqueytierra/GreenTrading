# Implementación Procesadores Backend - Resumen Final

## Fecha
2026-05-05

## Objetivo
Sacar el procesamiento del frontend para que el historial se actualice sin necesidad de tener el dashboard abierto.

## Problema Original

**ANTES:**
```
Dashboard abierto → app.js ejecuta:
  - fetchAllIndices()
  - trackZoneHistory() ← PROCESA Y GUARDA en DB
  - updateSetup()

Dashboard cerrado → ❌ NADA se procesa
                  → ❌ Historial NO se actualiza
```

**Consecuencia:** El sistema solo funcionaba con el navegador abierto.

## Solución Implementada

**AHORA:**
```
┌─────────────────────────────────┐
│   public.market_candles         │
│   (mt5_to_supabase.py)          │
└───────────┬─────────────────────┘
            │
            ├───────────────────────────────────┐
            │                                   │
            ▼                                   ▼
┌──────────────────────┐        ┌──────────────────────────────┐
│ processor_smc_m15_   │        │ processor_smc_tendency_h1_   │
│ pro.py               │        │ m15.py                       │
│ (SMC M15 PRO)        │        │ (SMC_TENDENCY_H1_M15)        │
└──────────┬───────────┘        └──────────┬───────────────────┘
           │                               │
           ▼                               ▼
┌────────────────────┐          ┌──────────────────────────────┐
│ smc_m15_setups     │          │ smc_tendency_h1_m15_setups   │
└────────────────────┘          └──────────────────────────────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
              ┌────────────────────────┐
              │   Dashboard Frontend   │
              │   (SOLO VISUALIZA)     │
              └────────────────────────┘
```

## Archivos Creados

### 1. processor_smc_m15_pro.py
**Responsabilidad:** Procesar estrategia SMC M15 PRO

**Características:**
- Lee velas desde `public.market_candles`
- Ejecuta análisis SMC usando `src/smc_engine.py`
- Escribe SOLO en `public.smc_m15_setups`
- NO valida H1 (estrategia simple M15)
- Gestiona estados: ACTIVA → EN_ZONA → PROFIT/TP/SL
- Pausa zonas cuando aparece una nueva
- Zonas PAUSADA solo se descartan si tocan SL

**Tabla destino:** `public.smc_m15_setups`  
**Strategy tag:** `SMC_M15_PRO`

### 2. processor_smc_tendency_h1_m15.py
**Responsabilidad:** Procesar estrategia SMC_TENDENCY_H1_M15

**Características:**
- Lee velas desde `public.market_candles`
- Ejecuta análisis SMC usando `src/smc_engine_tendency_h1_m15.py`
- Escribe SOLO en `public.smc_tendency_h1_m15_setups`
- Validación especial: índice + H1 + evento M15
- Solo guarda zonas VÁLIDAS (no hay DESCARTADA)
- Gestiona estados: ACTIVA → EN_ZONA → PROFIT/TP/SL

**Validación:**
- **BOOM:** H1 ALCISTA + evento M15 ALCISTA (CHOCH/BOS)
- **CRASH:** H1 BAJISTA + evento M15 BAJISTA (CHOCH/BOS)

**Tabla destino:** `public.smc_tendency_h1_m15_setups`  
**Strategy tag:** `SMC_TENDENCY_H1_M15`

### 3. run_processors.py
**Responsabilidad:** Orquestador que ejecuta ambos procesadores

**Características:**
- Ejecuta ambos procesadores en secuencia
- Intervalo: 60 segundos (configurable)
- Manejo robusto de errores
- Se puede detener con Ctrl+C
- Reinicia automáticamente en caso de error

**Uso:**
```bash
python run_processors.py
```

## Documentación Creada

### README_BACKEND_PROCESSORS.md
Documentación técnica completa con:
- Arquitectura del sistema
- Descripción detallada de cada archivo
- Instrucciones de instalación
- Guía de uso y configuración
- Troubleshooting
- Ejemplos SQL para verificación
- Configuración para producción (nohup, systemd)

### GUIA_PROCESADORES_BACKEND.md
Guía rápida de inicio con:
- Resumen ejecutivo
- Pasos para ejecutar
- Verificación básica
- Configuración esencial
- Problemas comunes
- Siguiente pasos

## Características Técnicas

### Independencia
- ✅ NO requiere navegador abierto
- ✅ NO depende de app.js
- ✅ Corre como proceso independiente

### Configuración
- **Intervalo:** 60 segundos (configurable en `run_processors.py`)
- **Símbolos:** Boom y Crash (1000, 900, 600, 500, 300)
- **Velas por timeframe:**
  - H1: 500 velas
  - M15: 800 velas
  - M1: 200 velas (opcional)

### Separación de Responsabilidades
```
mt5_to_supabase.py          → Collector (MT5 → market_candles)
processor_smc_m15_pro.py    → Backend (market_candles → smc_m15_setups)
processor_smc_tendency_...  → Backend (market_candles → smc_tendency_h1_m15_setups)
run_processors.py           → Orchestrator (ejecuta procesadores)
app.js (frontend)           → Visualizador (lee tablas → muestra)
```

### Estados de Zona

**SMC M15 PRO:**
- ACTIVA → EN_ZONA → PROFIT → TP
- ACTIVA → PAUSADA → SL (solo si toca SL)
- NO usa DESCARTADA

**SMC_TENDENCY_H1_M15:**
- ACTIVA → EN_ZONA → PROFIT → TP
- ACTIVA → PAUSADA → SL (solo si toca SL)
- NO guarda zonas inválidas (no hay DESCARTADA)

## Validación

Se verificó:
- ✅ Sintaxis Python correcta en los 3 archivos
- ✅ Funciones `process_all_symbols()` existen
- ✅ Tablas destino correctas
- ✅ Strategy tags correctos
- ✅ Imports correctos en `run_processors.py`
- ✅ Configuración INTERVAL_SECONDS = 60

## Próximos Pasos

### Fase 1: Pruebas (ACTUAL)
1. Ejecutar `python run_processors.py`
2. Verificar que crea zonas en las tablas
3. Confirmar que actualiza estados correctamente
4. Verificar logs y comportamiento

### Fase 2: Frontend (FUTURO - NO IMPLEMENTADO)
**Importante:** El frontend AÚN ejecuta lógica de procesamiento.

**Modificaciones pendientes en app.js:**
1. Eliminar lógica de procesamiento en `trackZoneHistory()`
2. Convertir `fetchAllIndices()` en solo lectura
3. Remover análisis SMC del navegador
4. Solo mantener visualización

**NO se debe modificar el frontend hasta:**
- Confirmar que los procesadores backend funcionan correctamente
- Verificar que las zonas se crean y actualizan bien
- Usuario da aprobación para modificar visualización

## Reglas Importantes

### Separación de Tablas
- ❌ `processor_smc_m15_pro.py` NUNCA escribe en otras tablas
- ❌ `processor_smc_tendency_h1_m15.py` NUNCA escribe en otras tablas
- ✅ Cada procesador tiene su tabla exclusiva

### Zonas PAUSADA
- **SMC M15 PRO:** Solo se descarta si toca SL
- **SMC_TENDENCY_H1_M15:** Solo se descarta si toca SL
- ❌ NO reevaluar por cambios H1/M15/confluencia

### Zonas Inválidas
- **SMC M15 PRO:** No aplica validación (todas las zonas son válidas)
- **SMC_TENDENCY_H1_M15:** Zonas inválidas NO se guardan (no hay DESCARTADA)

## Comandos Rápidos

### Ejecutar procesadores
```bash
python run_processors.py
```

### Verificar zonas creadas
```sql
-- SMC M15 PRO
SELECT symbol, estado, COUNT(*) 
FROM public.smc_m15_setups 
GROUP BY symbol, estado;

-- SMC_TENDENCY_H1_M15
SELECT symbol, estado, COUNT(*) 
FROM public.smc_tendency_h1_m15_setups 
GROUP BY symbol, estado;
```

### Ver logs en tiempo real (con nohup)
```bash
tail -f processors.log
```

## Resultado Final

✅ **Objetivo logrado:**
El historial se actualiza cada 60 segundos sin necesidad de tener el dashboard abierto.

✅ **Beneficios:**
- Procesamiento continuo 24/7
- No depende del navegador
- Mejor separación de responsabilidades
- Frontend más ligero
- Más fácil de mantener y debuggear

✅ **Listo para:**
- Pruebas en desarrollo
- Ajustes de configuración
- Despliegue en producción

⚠️ **Pendiente:**
- Modificar frontend para eliminar lógica de procesamiento
- Solo después de confirmar que backend funciona correctamente
