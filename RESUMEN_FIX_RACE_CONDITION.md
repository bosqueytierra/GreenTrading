# Resumen: Fix Race Condition - SMC M15 PRO DESCARTADAS Incorrectas

## Problema Reportado

En `public.smc_m15_setups` aparecían registros con:
```
estado = 'DESCARTADA'
motivo_cierre = 'Contexto M15 cambió contra la zona'
```

Esto **NO debería ocurrir** en SMC M15 PRO. Solo en SMC H1+M15 PRO.

## Causa Raíz Identificada

**Race condition con variable global `currentStrategy`:**

1. Usuario crea zona en SMC M15 PRO → guarda en `smc_m15_setups`
2. Usuario cambia a tab SMC H1+M15 PRO → `currentStrategy = 'SMC_H1_M15_PRO'`
3. Background refresh ejecuta `reevaluatePausedZone()` para zona antigua
4. Función usa `currentStrategy` global (ahora incorrecta)
5. Aplica validación H1+M15 a zona SMC M15 PRO
6. Zona descartada incorrectamente

## Solución Implementada

### 1. Agregar campo `strategy` a cada setup
- Al crear setup, guardar `strategy: currentStrategy`
- Cada setup "conoce" su estrategia independiente del estado global

### 2. Modificar `reevaluatePausedZone()`
- Usar `setup.strategy` en vez de `currentStrategy` global
- Determinar tabla correcta basado en `setup.strategy`
- Aplicar validaciones según estrategia del setup, no estado global

### 3. Modificar `updateSetup()`
- Aceptar parámetro opcional `explicitTable`
- Si se provee, usar esa tabla
- Si no, usar `getStrategyTable()` (backward compatible)

### 4. Actualizar todas las llamadas
- `updateSetupState()` → pasa `setup.strategy`
- `ensureSingleOperativeZone()` → pasa `zone.strategy`
- `handleSLHitAndReactivatePausedZones()` → pasa `zone.strategy`
- `trackZoneHistory()` → pasa `matchingSetup.strategy`

## Archivos Cambiados

1. **`assets/app.js`**
   - 7 funciones modificadas
   - ~50 líneas cambiadas

2. **`add_strategy_column.sql`** (NUEVO)
   - Migración de base de datos
   - Agregar columna `strategy` a ambas tablas
   - Actualizar registros existentes
   - Crear índices

3. **`FIX_RACE_CONDITION_STRATEGY.md`** (NUEVO)
   - Documentación completa del problema y solución
   - Explicación técnica detallada

4. **`TESTING_GUIDE_STRATEGY_FIX.md`** (NUEVO)
   - Guía de testing paso a paso
   - Queries de verificación
   - Criterios de éxito

## Pasos para Desplegar

### Paso 1: Ejecutar SQL Migration (CRÍTICO - PRIMERO)
```bash
# En Supabase SQL Editor:
# Copiar y ejecutar contenido de: add_strategy_column.sql
```

### Paso 2: Verificar Migración
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'smc_m15_setups' AND column_name = 'strategy';
```
Debe retornar 1 fila.

### Paso 3: Desplegar Código JS
```bash
# Hacer merge de la PR o copiar assets/app.js actualizado
# Refrescar aplicación en navegador
```

### Paso 4: Verificar Funcionamiento (Primeras 2 horas)
```sql
-- Verificar que nuevas zonas tienen strategy field
SELECT id, symbol, strategy, created_at
FROM public.smc_m15_setups
WHERE created_at > NOW() - INTERVAL '2 hours'
ORDER BY created_at DESC;
```

### Paso 5: Monitorear (Primeras 48 horas)
```sql
-- Verificar que NO aparecen DESCARTADAS incorrectas
SELECT COUNT(*) as incorrect_descartadas
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '48 hours'
  AND (
    motivo_cierre LIKE '%Contexto H1%' 
    OR motivo_cierre LIKE '%Contexto M15%'
    OR motivo_cierre LIKE '%Evento M15%'
  );
```
Resultado esperado: **0**

## Criterios de Éxito

✅ Fix exitoso si después de 48 horas:

1. **Cero** SMC M15 PRO con DESCARTADA + motivos de contexto (post-deploy)
2. **Todos** los nuevos setups tienen campo `strategy` poblado
3. **PAUSADA** en SMC M15 PRO solo → DESCARTADA cuando toca SL
4. **SMC H1+M15 PRO** sigue funcionando con todas sus validaciones

## Rollback Plan

Si el fix no funciona:

```bash
# Revertir commits
git revert HEAD~3
git push origin copilot/smc-m15-pro-fix-close-setup-usage

# La columna strategy en DB puede quedarse (no causa problemas)
```

## Queries Útiles

### Ver DESCARTADAS recientes por estrategia
```sql
SELECT 
    strategy,
    motivo_cierre,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND fecha_cierre > NOW() - INTERVAL '24 hours'
GROUP BY strategy, motivo_cierre
ORDER BY strategy, cantidad DESC;
```

### Ver PAUSADAS actuales
```sql
SELECT 
    id,
    symbol,
    strategy,
    direccion,
    sl_price,
    created_at
FROM public.smc_m15_setups
WHERE estado = 'PAUSADA'
ORDER BY created_at DESC;
```

### Alerta: DESCARTADAS incorrectas
```sql
-- Ejecutar cada hora
SELECT id, symbol, motivo_cierre, fecha_cierre
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '1 hour'
  AND motivo_cierre NOT LIKE '%SL%';
```
Si retorna filas: **ALERTA - fix no está funcionando**

## Documentos de Referencia

1. **FIX_RACE_CONDITION_STRATEGY.md** - Documentación técnica completa
2. **TESTING_GUIDE_STRATEGY_FIX.md** - Guía de testing detallada
3. **add_strategy_column.sql** - Script de migración
4. **assets/app.js** - Código modificado

## Reglas de Negocio (Confirmadas)

### SMC M15 PRO:
- PAUSADA → DESCARTADA **SOLO** por: Precio toca SL
- PAUSADA **NO** se descarta por:
  - ❌ Contexto H1 cambió
  - ❌ Contexto M15 cambió  
  - ❌ Evento M15 cambió
  - ❌ Falta de confluencia

### SMC H1+M15 PRO:
- PAUSADA → DESCARTADA por:
  - ✅ Precio toca SL
  - ✅ Contexto H1 cambió
  - ✅ Contexto M15 cambió
  - ✅ Evento M15 cambió
  - ✅ Falta de confluencia

## Notas Importantes

- ⚠️ **EJECUTAR SQL ANTES** de desplegar JS (orden crítico)
- 📊 **Monitorear 48 horas** para confirmar fix
- 🔄 **Backward compatible** (registros sin strategy usan default)
- 🏷️ **Índices agregados** para mejor performance
- 📝 **Registros existentes** actualizados automáticamente

## Contacto / Issues

Si después del deploy aparecen DESCARTADAS incorrectas:
1. Verificar que SQL migration se ejecutó
2. Verificar que nuevos setups tienen `strategy` field
3. Revisar browser console por errores JS
4. Ejecutar queries de verificación del testing guide

---

**Fecha:** 2026-05-04
**Branch:** `copilot/smc-m15-pro-fix-close-setup-usage`
**Commits:** 3 (code, migration, testing guide)
