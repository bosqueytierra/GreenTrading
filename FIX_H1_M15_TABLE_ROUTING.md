# FIX: H1+M15 Strategy Table Routing Issue

## PROBLEMA IDENTIFICADO

La estrategia SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) estaba escribiendo registros en la tabla equivocada debido a que el frontend usaba la variable `currentStrategy` (controlada por las pestañas de UI) para determinar a qué tabla escribir.

### Estado Actual del Sistema

#### SMC M15 PRO (Estrategia Original)
- ✅ **Motor de análisis**: `src/smc_engine.py` (sin validación H1)
- ✅ **Script de prueba**: `smc_m15_pro.py`
- ✅ **Tabla**: `public.smc_m15_setups`
- ✅ **Frontend**: Funciona correctamente, escribe a `smc_m15_setups`
- ✅ **Lógica**: Detecta zonas M15 según análisis SMC estándar

#### SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) (Estrategia Nueva)
- ✅ **Motor de análisis**: `src/smc_engine_h1_m15.py` (CON validación H1)
- ✅ **Script de prueba**: `smc_h1_m15_pro.py`
- ✅ **Tabla**: `public.smc_h1_m15_setups`
- ❌ **Processor/Backend**: **NO EXISTE** - no hay código que escriba a esta tabla
- ⚠️ **Frontend**: Solo LECTURA desde tabla, NO tiene lógica de escritura con validación
- ⚠️ **Problema**: Frontend intentaba escribir a esta tabla sin ejecutar la validación H1+M15

## CAUSA RAÍZ

El archivo `assets/app.js`:
1. Solo ejecuta análisis SMC M15 PRO (función `analyzeSMC()`)
2. NO ejecuta la validación H1+M15 (`validar_h1_m15_alignment`)
3. Usa `getStrategyTable()` que retorna tabla basada en `currentStrategy`
4. `currentStrategy` cambia cuando el usuario hace clic en las pestañas de UI
5. **Resultado**: Cuando `currentStrategy = 'SMC_H1_M15_PRO'`, TODAS las zonas se escribían a `smc_h1_m15_setups` sin validación

## SOLUCIÓN APLICADA

### Fix Inmediato (Líneas 1106-1119 en `assets/app.js`)

```javascript
// IMPORTANTE: Siempre trackear usando tabla SMC M15 PRO
// Esto asegura compatibilidad y previene escrituras accidentales a tabla H1+M15
if (analysis && !analysis.error) {
    // Forzar temporalmente estrategia a SMC_M15_PRO para tracking
    const originalStrategy = currentStrategy;
    currentStrategy = 'SMC_M15_PRO';
    
    await trackZoneHistory(symbol, analysis);
    
    // Restaurar estrategia original
    currentStrategy = originalStrategy;
}
```

### Efecto del Fix

- ✅ **SMC M15 PRO**: Escribe correctamente a `smc_m15_setups`
- ✅ **Prevención**: Ya no se escriben registros incorrectos a `smc_h1_m15_setups`
- ✅ **UI**: Las pestañas siguen funcionando (solo afectan qué tabla se LEE para mostrar)
- ⚠️ **Limitación**: `smc_h1_m15_setups` permanece vacía (solo lectura)

## TAREAS PENDIENTES

### 1. Limpiar Registros Incorrectos en `smc_m15_setups`

Los registros creados erróneamente desde que se implementó la estrategia nueva deben eliminarse.

**SQL para identificar registros incorrectos:**
```sql
-- Identificar registros que NO cumplen validación H1+M15
-- pero que fueron creados recientemente
SELECT 
    id,
    symbol,
    tendencia_h1,
    evento,
    created_at,
    estado
FROM public.smc_m15_setups
WHERE created_at > '2026-05-04'  -- Ajustar fecha según cuándo se implementó la estrategia nueva
ORDER BY created_at DESC;
```

**Criterios para eliminar:**
- Registros que tienen `tendencia_h1` no null (indica que fueron creados con lógica nueva)
- Registros que NO cumplen la regla H1+M15:
  - Boom con H1 BAJISTA o evento M15 BAJISTA
  - Crash con H1 ALCISTA o evento M15 ALCISTA

**SQL para eliminar registros incorrectos (EJECUTAR CON PRECAUCIÓN):**
```sql
-- BACKUP PRIMERO
CREATE TABLE smc_m15_setups_backup_20260504 AS 
SELECT * FROM public.smc_m15_setups;

-- Eliminar registros BOOM con validación incorrecta
DELETE FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND created_at > '2026-05-04'
  AND (
    tendencia_h1 = 'BAJISTA' 
    OR evento LIKE '%BAJISTA%'
  );

-- Eliminar registros CRASH con validación incorrecta  
DELETE FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND created_at > '2026-05-04'
  AND (
    tendencia_h1 = 'ALCISTA'
    OR evento LIKE '%ALCISTA%'
  );
```

### 2. Decisión sobre Estrategia H1+M15

Hay dos opciones:

#### Opción A: Mantener H1+M15 como View-Only (Recomendado para ahora)

**Pros:**
- Menos complejidad
- No requiere procesador backend nuevo
- Usuarios pueden seguir viendo la pestaña H1+M15 aunque esté vacía

**Cons:**
- La tabla `smc_h1_m15_setups` permanece vacía
- No se utiliza la validación H1+M15

**Acción requerida:**
- Ninguna adicional (ya está implementado)
- Opcional: Ocultar pestaña H1+M15 en UI hasta implementar processor

#### Opción B: Implementar Processor Completo para H1+M15

**Pros:**
- Estrategia completamente funcional
- Aprovechar validación H1+M15
- Separación limpia entre estrategias

**Cons:**
- Más complejidad
- Requiere:
  1. Modificar `assets/app.js` para ejecutar ambos análisis en paralelo
  2. Implementar función `validarH1M15Alignment()` en JavaScript
  3. Escribir a `smc_h1_m15_setups` solo cuando validación pase
  4. Mantener dos flujos de tracking separados

**Acción requerida:**
1. Agregar función de validación H1+M15 en `assets/app.js`
2. Modificar `refreshDashboard()` para ejecutar ambas estrategias
3. Modificar `trackZoneHistory()` para aceptar parámetro de tabla
4. Testing extensivo de ambas estrategias

### 3. Verificar Estado de Tablas

**Comandos SQL para verificar:**

```sql
-- Verificar conteo de registros en SMC M15 PRO
SELECT 
    COUNT(*) as total_registros,
    COUNT(CASE WHEN estado = 'ACTIVA' THEN 1 END) as activas,
    COUNT(CASE WHEN estado = 'DESCARTADA' THEN 1 END) as descartadas
FROM public.smc_m15_setups;

-- Verificar conteo de registros en SMC H1+M15
SELECT 
    COUNT(*) as total_registros,
    COUNT(CASE WHEN estado = 'ACTIVA' THEN 1 END) as activas,
    COUNT(CASE WHEN estado = 'DESCARTADA' THEN 1 END) as descartadas
FROM public.smc_h1_m15_setups;

-- Debe devolver:
-- smc_m15_setups: > 0 registros (estrategia activa)
-- smc_h1_m15_setups: 0 registros (no hay processor)
```

## REGLAS OBLIGATORIAS

Para evitar este problema en el futuro:

### 1. Separación de Responsabilidades

```
SMC M15 PRO:
  - Tabla: smc_m15_setups
  - Lógica: Solo análisis SMC M15 estándar
  - Sin validación H1

SMC H1+M15:
  - Tabla: smc_h1_m15_setups  
  - Lógica: Análisis SMC M15 + validación H1+M15
  - Filtro: Boom=H1 ALCISTA+M15 ALCISTA, Crash=H1 BAJISTA+M15 BAJISTA
```

### 2. Principio de Escritura

- **Una función NO debe escribir a múltiples tablas de estrategias**
- **La tabla de destino debe ser explícita, no basada en variable de UI**
- **Cada estrategia debe tener su propio flujo de tracking**

### 3. Validación Antes de Escritura

```javascript
// ❌ MAL - Escribe sin validar
if (zonaM15) {
    await createSetup(setupData);
}

// ✅ BIEN - Valida antes de escribir a H1+M15
if (zonaM15 && validarH1M15Alignment(symbol, tendenciaH1, evento)) {
    await createSetup(setupData, 'smc_h1_m15_setups');
} else if (zonaM15) {
    // Guardar como DESCARTADA en H1+M15 o no guardar
}
```

## TESTING

### Verificar Fix Actual

1. **Abrir dashboard en navegador**
2. **Cambiar entre pestañas** (SMC M15 PRO ↔ SMC H1+M15)
3. **Verificar consola del navegador**:
   - No deben aparecer errores
   - Debe mostrar logs de tracking a `smc_m15_setups`
4. **Verificar base de datos**:
   ```sql
   -- Nuevos registros solo deben aparecer en smc_m15_setups
   SELECT * FROM public.smc_m15_setups 
   WHERE created_at > NOW() - INTERVAL '1 hour';
   
   -- Esta tabla debe permanecer sin cambios
   SELECT * FROM public.smc_h1_m15_setups 
   WHERE created_at > NOW() - INTERVAL '1 hour';
   ```

### Si se Implementa Opción B (Processor Completo)

1. **Testing de validación H1+M15**:
   ```javascript
   // Test Boom con H1 ALCISTA + M15 ALCISTA = válido
   const result1 = validarH1M15Alignment(
       'Boom 1000 Index', 
       'ALCISTA',
       { evento: 'CHOCH_ALCISTA' }
   );
   console.assert(result1.esValido === true);
   
   // Test Boom con H1 BAJISTA = inválido
   const result2 = validarH1M15Alignment(
       'Boom 1000 Index',
       'BAJISTA',
       { evento: 'CHOCH_ALCISTA' }
   );
   console.assert(result2.esValido === false);
   ```

2. **Testing de escritura dual**:
   - Verificar que zonas válidas van a `smc_h1_m15_setups`
   - Verificar que zonas NO válidas se marcan como DESCARTADA
   - Verificar que `smc_m15_setups` sigue recibiendo TODAS las zonas (sin filtro H1)

## RESUMEN

### ✅ Completado

1. Identificado problema de routing de tabla
2. Aplicado fix para forzar escritura a `smc_m15_setups`
3. Prevenido nuevas escrituras incorrectas a `smc_h1_m15_setups`
4. Documentado causa raíz y solución

### ⏳ Pendiente

1. Limpiar registros incorrectos de `smc_m15_setups`
2. Decidir: View-Only vs Processor Completo para H1+M15
3. Si Processor Completo: Implementar validación y dual-tracking
4. Testing completo de ambas estrategias

### 📋 Checklist Final

- [ ] Ejecutar SQL de limpieza en `smc_m15_setups`
- [ ] Verificar que `smc_m15_setups` solo tiene registros válidos para SMC M15 PRO
- [ ] Decidir sobre implementación H1+M15
- [ ] Si H1+M15: Implementar processor completo
- [ ] Testing en producción
- [ ] Actualizar README con estado actual

---

**Fecha del Fix**: 2026-05-04  
**Archivos Modificados**: `assets/app.js` (líneas 1106-1119)  
**Estado**: ✅ Fix inmediato aplicado, pendiente limpieza y decisión sobre H1+M15
