# FIX: Race Condition con currentStrategy Global

## Problema Identificado

### Síntoma
Registros en `public.smc_m15_setups` con:
- `estado = 'DESCARTADA'`
- `motivo_cierre = 'Contexto M15 cambió contra la zona'` (u otros motivos de contexto H1/M15)

Esto **NO debería ocurrir** en `SMC_M15_PRO`, solo en `SMC_H1_M15_PRO`.

### Causa Raíz

El problema era una **race condition** causada por el uso de la variable global `currentStrategy`:

1. **Usuario en pestaña SMC M15 PRO**: `currentStrategy = 'SMC_M15_PRO'`
2. **Se crean zonas** en tabla `smc_m15_setups`
3. **Usuario cambia a pestaña SMC H1+M15 PRO**: `currentStrategy = 'SMC_H1_M15_PRO'`
4. **Background refresh ejecuta** y llama a `reevaluatePausedZone()` para zonas antiguas
5. **Problema**: `reevaluatePausedZone()` usa `currentStrategy` global (ahora `'SMC_H1_M15_PRO'`)
6. **Resultado**: Aplica lógica de validación H1+M15 a zonas SMC M15 PRO
7. **Zonas descartadas incorrectamente** con motivos de contexto H1/M15

### Flujo del Problema

```
Usuario en SMC M15 PRO tab
  ↓
Zona creada en smc_m15_setups (sin campo strategy)
  ↓
Usuario cambia a SMC H1+M15 PRO tab
  ↓
currentStrategy = 'SMC_H1_M15_PRO' (global cambia)
  ↓
Background refresh (cada 30s)
  ↓
reevaluatePausedZone(zona_antigua, ...)
  ↓
Usa currentStrategy (ahora 'SMC_H1_M15_PRO')
  ↓
Aplica validación H1/M15 incorrecta
  ↓
updateSetup(id, {estado: 'DESCARTADA', ...})
  ↓
Zona SMC M15 PRO marcada como DESCARTADA ❌
```

## Solución Implementada

### 1. Agregar campo `strategy` a los setups

**Cambio en `trackZoneHistory()` línea ~1092:**

```javascript
const newSetup = {
    // ... otros campos ...
    strategy: currentStrategy  // ✅ Almacenar estrategia al crear
};
```

Ahora cada setup **guarda** qué estrategia lo creó, independiente de la variable global.

### 2. Modificar `updateSetup()` para aceptar tabla explícita

**Cambio en función `updateSetup()` línea ~415:**

```javascript
async function updateSetup(id, updateData, explicitTable = null) {
    // Si se provee tabla explícita, usarla; sino usar currentStrategy
    const table = explicitTable || getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}?id=eq.${id}`;
    // ...
}
```

Ahora `updateSetup()` puede recibir la tabla correcta explícitamente, en vez de depender solo del estado global.

### 3. Modificar `reevaluatePausedZone()` para usar strategy del setup

**Cambio clave en `reevaluatePausedZone()` línea ~516:**

```javascript
async function reevaluatePausedZone(setup, currentPrice, analysis) {
    // ✅ Usar setup.strategy en vez de currentStrategy global
    const setupStrategy = setup.strategy || 'SMC_M15_PRO';
    const setupTable = STRATEGIES[setupStrategy]?.table || 'smc_m15_setups';
    
    // ... validaciones ...
    
    // ✅ Validación 2: Solo para SMC_H1_M15_PRO
    if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO' && ...) {
        // Aplicar validación H1/M15
    }
    
    // ✅ Validación 3: Solo para SMC_H1_M15_PRO
    if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO') {
        // Aplicar validación evento M15
    }
    
    // ✅ Validación 4: Solo para SMC_H1_M15_PRO
    if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO') {
        // Aplicar validación confluencia
    }
    
    if (shouldDiscard) {
        // ✅ Actualizar usando tabla correcta
        await updateSetup(setup.id, updateData, setupTable);
    }
}
```

### 4. Actualizar todas las llamadas a `updateSetup()`

Se actualizaron todas las funciones que llaman a `updateSetup()` para pasar la tabla correcta:

- **`updateSetupState()`** línea ~774
- **`ensureSingleOperativeZone()`** línea ~1220
- **`handleSLHitAndReactivatePausedZones()`** línea ~844
- **`trackZoneHistory()` (matching setup)** línea ~1059

Todas ahora pasan `setupTable` basado en `setup.strategy`.

## Migración de Base de Datos

### Script SQL: `add_strategy_column.sql`

```sql
-- Agregar columna strategy a ambas tablas
ALTER TABLE public.smc_m15_setups 
ADD COLUMN IF NOT EXISTS strategy VARCHAR(50) DEFAULT 'SMC_M15_PRO';

ALTER TABLE public.smc_h1_m15_setups 
ADD COLUMN IF NOT EXISTS strategy VARCHAR(50) DEFAULT 'SMC_H1_M15_PRO';

-- Actualizar registros existentes
UPDATE public.smc_m15_setups 
SET strategy = 'SMC_M15_PRO' 
WHERE strategy IS NULL;

UPDATE public.smc_h1_m15_setups 
SET strategy = 'SMC_H1_M15_PRO' 
WHERE strategy IS NULL;

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_smc_m15_setups_strategy 
ON public.smc_m15_setups(strategy);

CREATE INDEX IF NOT EXISTS idx_smc_h1_m15_setups_strategy 
ON public.smc_h1_m15_setups(strategy);
```

**Ejecutar este script en Supabase SQL Editor ANTES de desplegar el código JS actualizado.**

## Verificación

### 1. Verificar que el campo strategy existe

```sql
SELECT strategy, COUNT(*) 
FROM public.smc_m15_setups 
GROUP BY strategy;
```

Resultado esperado:
```
strategy        | count
----------------|------
SMC_M15_PRO     | N
```

### 2. Verificar que no hay DESCARTADAS incorrectas

```sql
SELECT id, symbol, estado, motivo_cierre, strategy
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA' 
  AND strategy = 'SMC_M15_PRO'
  AND (
    motivo_cierre LIKE '%Contexto H1%' 
    OR motivo_cierre LIKE '%Contexto M15%'
    OR motivo_cierre LIKE '%Evento M15%'
  );
```

Resultado esperado: **0 registros**

Si hay registros, son datos históricos del bug. Los nuevos registros (después del fix) NO deberían aparecer.

### 3. Monitorear nuevos registros DESCARTADA

Después de desplegar el fix, monitorear por 24-48 horas:

```sql
-- Monitorear nuevos DESCARTADA en SMC M15 PRO
SELECT 
    DATE_TRUNC('hour', fecha_cierre) as hora,
    motivo_cierre,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '48 hours'
GROUP BY hora, motivo_cierre
ORDER BY hora DESC;
```

**Resultado esperado**: Solo motivos de "SL":
- ✅ `'Precio tocó SL de zona pausada'`
- ❌ NO debe aparecer `'Contexto M15 cambió contra la zona'`
- ❌ NO debe aparecer `'Contexto H1 cambió contra la zona'`
- ❌ NO debe aparecer `'Evento M15 dejó de tener sentido'`

## Beneficios del Fix

1. ✅ **Aislamiento real entre estrategias**: Cada setup conoce su estrategia
2. ✅ **Sin race conditions**: Cambios de tab no afectan evaluación de zonas existentes
3. ✅ **Lógica correcta garantizada**: SMC M15 PRO nunca aplica validaciones H1+M15
4. ✅ **Tabla correcta siempre**: Updates van a la tabla correcta, no dependen de estado global
5. ✅ **Future-proof**: Nuevas estrategias pueden agregarse sin conflictos

## Estados Válidos

### Para SMC M15 PRO:

**PAUSADA → DESCARTADA solo por:**
- ✅ Precio tocó SL

**PAUSADA NO se descarta por:**
- ❌ Contexto H1 cambió
- ❌ Contexto M15 cambió
- ❌ Evento M15 cambió
- ❌ Falta de confluencia

### Para SMC H1+M15 PRO:

**PAUSADA → DESCARTADA por:**
- ✅ Precio tocó SL
- ✅ Contexto H1 cambió contra la zona
- ✅ Contexto M15 cambió contra la zona
- ✅ Evento M15 dejó de tener sentido
- ✅ Falta de confluencia OB/FVG/Barrida

## Archivos Modificados

- ✅ `assets/app.js` - Funciones actualizadas:
  - `updateSetup()` - Acepta tabla explícita
  - `reevaluatePausedZone()` - Usa setup.strategy
  - `trackZoneHistory()` - Agrega strategy al crear
  - `updateSetupState()` - Pasa tabla correcta
  - `ensureSingleOperativeZone()` - Pasa tabla correcta
  - `handleSLHitAndReactivatePausedZones()` - Pasa tabla correcta
  - `closeSetup()` - Acepta tabla explícita (por completitud)

- ✅ `add_strategy_column.sql` - Migración de base de datos

- ✅ `FIX_RACE_CONDITION_STRATEGY.md` - Esta documentación

## Próximos Pasos

1. **Ejecutar** `add_strategy_column.sql` en Supabase SQL Editor
2. **Desplegar** código JS actualizado (`assets/app.js`)
3. **Verificar** que no aparecen nuevas DESCARTADAS incorrectas
4. **Monitorear** por 48 horas
5. **Confirmar** que el problema está resuelto

## Notas Técnicas

- El campo `strategy` se agregó a nivel de base de datos, pero también podría manejarse en memoria
- Default `'SMC_M15_PRO'` para backward compatibility con registros sin strategy
- El índice en `strategy` mejora performance de queries filtradas por estrategia
- La función `updateSetup()` mantiene backward compatibility (tabla opcional)
