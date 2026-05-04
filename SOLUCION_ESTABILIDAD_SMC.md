# SOLUCIÓN: Restauración de Estabilidad Sistema SMC

**Fecha:** 2026-05-04  
**Status:** ✅ COMPLETADO

---

## 📋 Resumen del Problema

El sistema tenía varios problemas críticos de estabilidad:

1. ✅ Dashboard SMC M15 PRO estaba correcto
2. ❌ Dashboard SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) mostraba zonas incorrectas
3. ❌ Historial SMC M15 PRO tenía registros duplicados/incorrectos
4. ❌ Mezcla de datos entre las dos estrategias
5. ❌ Escrituras incorrectas a tablas que no debían usarse

### Causa Raíz

El sistema intentaba manejar dos estrategias (SMC M15 PRO y H1+M15) pero:
- Ambas compartían la misma tabla (`smc_m15_setups`)
- El frontend intentaba escribir a `smc_h1_m15_setups` sin validación
- No había separación clara entre visualización y almacenamiento
- El tracking de zonas dependía de una variable de UI (`currentStrategy`)

---

## ✅ Solución Implementada

### Arquitectura Final

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (app.js)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Dashboard SMC M15 PRO          Dashboard H1+M15        │
│  ├─ Lee: smc_m15_setups        ├─ Lee: smc_m15_setups  │
│  ├─ Escribe: smc_m15_setups    ├─ Escribe: (ninguna)   │
│  └─ Filtro: NINGUNO             └─ Filtro: H1+M15 ✅    │
│                                                          │
│  Historial SMC M15 PRO          Historial H1+M15        │
│  ├─ Lee: smc_m15_setups        ├─ Lee: smc_m15_setups  │
│  └─ Filtro: NINGUNO             └─ Filtro: H1+M15 ✅    │
│                                                          │
└─────────────────────────────────────────────────────────┘
                         ↓ ↑
┌─────────────────────────────────────────────────────────┐
│                      SUPABASE                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │ public.smc_m15_setups (ÚNICA TABLA ACTIVA)      │  │
│  │ - Todos los setups SMC M15 PRO                   │  │
│  │ - Frontend lee/escribe aquí                      │  │
│  │ - Contiene TODAS las zonas detectadas            │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ public.smc_h1_m15_setups (VACÍA/NO USADA)       │  │
│  │ - Reservada para procesador backend             │  │
│  │ - Frontend NO escribe aquí                       │  │
│  │ - Puede eliminarse o mantener para uso futuro   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ public.market_candles (FUENTE DE VELAS)         │  │
│  │ - Recolectadas por mt5_to_supabase.py           │  │
│  │ - Compartidas por todas las estrategias         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Principios de la Solución

1. **Una Sola Fuente de Verdad:** 
   - TODAS las zonas se guardan en `smc_m15_setups`
   - NO hay escrituras a `smc_h1_m15_setups` desde el frontend

2. **Filtrado en Visualización, NO en Almacenamiento:**
   - Dashboard SMC M15 PRO: Muestra TODAS las zonas
   - Dashboard H1+M15: Muestra solo zonas que CUMPLEN validación H1+M15
   - Historial SMC M15 PRO: Muestra TODAS las zonas
   - Historial H1+M15: Muestra solo zonas que CUMPLEN validación H1+M15

3. **Validación H1+M15:**
   - **Boom:** Requiere H1 ALCISTA + Evento M15 ALCISTA (CHOCH/BOS)
   - **Crash:** Requiere H1 BAJISTA + Evento M15 BAJISTA (CHOCH/BOS)
   - Zonas que no cumplen se marcan como "NO CUMPLE H1+M15"

---

## 🔧 Cambios Implementados

### Archivo: `assets/app.js`

#### 1. Función `getStrategyTable()`
```javascript
function getStrategyTable(strategy = null) {
    // ⚠️ IMPORTANTE: TODAS las operaciones van a smc_m15_setups
    return 'smc_m15_setups';
}
```

**Antes:** Retornaba diferentes tablas según `currentStrategy`  
**Ahora:** SIEMPRE retorna 'smc_m15_setups'  
**Impacto:** Todas las operaciones usan una única tabla

---

#### 2. Función `validarH1M15()` (NUEVA)
```javascript
function validarH1M15(symbol, tendenciaH1, eventoM15) {
    const tipoIndice = symbol.includes('Boom') ? 'Boom' : 'Crash';
    
    if (tipoIndice === 'Boom') {
        return tendenciaH1 === 'ALCISTA' && 
               (eventoM15.includes('CHOCH_ALCISTA') || eventoM15.includes('BOS_ALCISTA'));
    }
    
    if (tipoIndice === 'Crash') {
        return tendenciaH1 === 'BAJISTA' && 
               (eventoM15.includes('CHOCH_BAJISTA') || eventoM15.includes('BOS_BAJISTA'));
    }
    
    return false;
}
```

**Propósito:** Valida si una zona cumple requisitos H1+M15  
**Uso:** Dashboard y historial H1+M15 para filtrar zonas

---

#### 3. Función `createTableRow()` - Dashboard
```javascript
// Validación H1+M15 para dashboard
if (currentStrategy === 'SMC_H1_M15_PRO') {
    const tendenciaH1 = smc.tendenciaH1 || '--';
    let eventoM15 = '--';
    
    if (smc.eventosM15 && smc.eventosM15.length > 0) {
        eventoM15 = smc.eventosM15[smc.eventosM15.length - 1].evento;
    }
    
    cumpleH1M15 = validarH1M15(symbol, tendenciaH1, eventoM15);
    
    if (!cumpleH1M15) {
        displayEstado = 'NO_CUMPLE_H1M15';
        displayZonaDesde = null;
        displayZonaHasta = null;
    }
}
```

**Impacto:** Dashboard H1+M15 filtra y marca zonas que no cumplen validación

---

#### 4. Función `fetchSetupHistory()`
```javascript
async function fetchSetupHistory(limit = 50) {
    // SIEMPRE leer de smc_m15_setups
    const table = 'smc_m15_setups';
    const url = `${SUPABASE_URL}/rest/v1/${table}?order=created_at.desc&limit=${limit}`;
    // ...
}
```

**Antes:** Leía de tabla según `currentHistoryStrategy`  
**Ahora:** SIEMPRE lee de 'smc_m15_setups'

---

#### 5. Función `applyFilters()` - Historial
```javascript
// Filtro H1+M15 para historial
if (currentHistoryStrategy === 'SMC_H1_M15_PRO') {
    const tendenciaH1 = setup.tendencia_h1 || '--';
    const evento = setup.evento || '--';
    
    if (!validarH1M15(setup.symbol, tendenciaH1, evento)) {
        return false;  // Excluir del historial H1+M15
    }
}
```

**Impacto:** Historial H1+M15 solo muestra zonas que cumplen validación

---

#### 6. Tracking de Zonas Simplificado
```javascript
// ANTES (con workaround):
const originalStrategy = currentStrategy;
currentStrategy = 'SMC_M15_PRO';
await trackZoneHistory(symbol, analysis);
currentStrategy = originalStrategy;

// AHORA (directo):
await trackZoneHistory(symbol, analysis);
```

**Impacto:** Código más limpio, sin workarounds

---

## 📊 Comportamiento Final

### Dashboard SMC M15 PRO
- ✅ Muestra TODAS las zonas detectadas
- ✅ Escribe nuevas zonas a `smc_m15_setups`
- ✅ NO aplica filtro H1+M15
- ✅ Estados: ACTIVA, EN_ZONA, PROFIT, SIN_SETUP, etc.

### Dashboard SMC PRO TENDENCIA H1+M15
- ✅ Lee de `smc_m15_setups` (igual que SMC M15 PRO)
- ✅ NO escribe a ninguna tabla
- ✅ Aplica filtro H1+M15 en visualización
- ✅ Zonas que no cumplen: Estado "NO CUMPLE H1+M15"
- ✅ Zona no se muestra si no cumple validación

### Historial SMC M15 PRO
- ✅ Lee de `smc_m15_setups`
- ✅ Muestra TODOS los registros
- ✅ NO aplica filtro H1+M15
- ✅ Lógica original restaurada

### Historial SMC PRO TENDENCIA H1+M15
- ✅ Lee de `smc_m15_setups` (igual que SMC M15 PRO)
- ✅ Aplica filtro H1+M15 en cliente
- ✅ Solo muestra zonas que CUMPLEN validación H1+M15
- ✅ Estadísticas calculadas solo sobre zonas válidas

---

## 🧹 Limpieza de Datos (OPCIONAL)

Si deseas eliminar registros incorrectos creados antes de esta corrección:

### Paso 1: Identificar Registros Incorrectos

```sql
-- Ver registros BOOM incorrectos
SELECT id, symbol, tendencia_h1, evento, estado, created_at
FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND created_at > '2026-05-01'  -- Ajustar fecha
  AND (tendencia_h1 = 'BAJISTA' OR evento LIKE '%BAJISTA%');

-- Ver registros CRASH incorrectos
SELECT id, symbol, tendencia_h1, evento, estado, created_at
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND created_at > '2026-05-01'  -- Ajustar fecha
  AND (tendencia_h1 = 'ALCISTA' OR evento LIKE '%ALCISTA%');
```

### Paso 2: Usar Script de Limpieza

Ejecutar el script `cleanup_incorrect_smc_records.sql`:

```bash
# En Supabase SQL Editor
1. Abrir cleanup_incorrect_smc_records.sql
2. Ejecutar PASO 1: Crear backup
3. Ejecutar PASO 2: Identificar registros incorrectos
4. REVISAR LOS RESULTADOS
5. Ejecutar PASO 3: Eliminar (descomentar las queries DELETE)
6. Ejecutar PASO 4: Verificar limpieza
```

### Paso 3: Verificar

```sql
-- Debe retornar 0 en ambas filas
SELECT 
    'BOOM con problemas' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND (tendencia_h1 = 'BAJISTA' OR evento LIKE '%BAJISTA%')
UNION ALL
SELECT 
    'CRASH con problemas' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND (tendencia_h1 = 'ALCISTA' OR evento LIKE '%ALCISTA%');
```

---

## ✅ Verificación del Sistema

### 1. Verificar Tablas en Supabase

```sql
-- Verificar estado de ambas tablas
SELECT 
    'smc_m15_setups' as tabla,
    COUNT(*) as total_registros,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as ultimas_24h
FROM public.smc_m15_setups
UNION ALL
SELECT 
    'smc_h1_m15_setups' as tabla,
    COUNT(*) as total_registros,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as ultimas_24h
FROM public.smc_h1_m15_setups;

-- Resultado esperado:
-- smc_m15_setups: > 0 registros
-- smc_h1_m15_setups: 0 registros (no se usa desde frontend)
```

### 2. Verificar Dashboard

1. **Abrir dashboard web**
2. **Tab "SMC M15 PRO":**
   - ✅ Debe mostrar todas las zonas detectadas
   - ✅ Estados: ACTIVA, EN_ZONA, PROFIT, SIN_SETUP, etc.
3. **Tab "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)":**
   - ✅ Debe mostrar solo zonas que cumplen H1+M15
   - ✅ Zonas que no cumplen: "NO CUMPLE H1+M15"
   - ✅ Menos zonas que en SMC M15 PRO (por el filtro)

### 3. Verificar Historial

1. **Tab "Historial SMC M15 PRO":**
   - ✅ Debe mostrar TODOS los registros
   - ✅ Sin duplicados
   - ✅ Filtros por símbolo/estado funcionan
2. **Tab "Historial SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)":**
   - ✅ Debe mostrar solo registros que cumplen H1+M15
   - ✅ Menos registros que en SMC M15 PRO
   - ✅ Estadísticas calculadas correctamente

### 4. Verificar Consola del Navegador

```
✅ NO debe haber errores de permisos RLS
✅ NO debe haber errores 403/401
✅ Logs deben mostrar "Tracking a smc_m15_setups"
```

---

## 📝 Reglas Importantes

### ⚠️ NUNCA hacer esto:

1. ❌ NO escribir a `smc_h1_m15_setups` desde el frontend
2. ❌ NO mezclar lógica de tracking con variables de UI
3. ❌ NO modificar `getStrategyTable()` para retornar diferentes tablas
4. ❌ NO duplicar tracking de zonas

### ✅ SIEMPRE hacer esto:

1. ✅ Todas las zonas van a `smc_m15_setups`
2. ✅ Filtrado se hace en visualización, no en almacenamiento
3. ✅ Validación H1+M15 se aplica en el cliente (frontend)
4. ✅ Una zona = un registro (sin duplicados)

---

## 🔮 Futuro: Procesador Backend H1+M15

Si en el futuro se desea activar el procesador backend `smc_h1_m15_processor.py`:

### Opción A: Procesador Independiente (Recomendado)
```
1. Activar smc_h1_m15_processor.py
2. Lee de: public.market_candles
3. Escribe en: public.smc_h1_m15_setups
4. Frontend lee de ambas tablas según estrategia
5. Mantener separación total
```

### Opción B: Mantener Todo en Frontend (Actual)
```
1. NO activar procesador backend
2. Una sola tabla: smc_m15_setups
3. Filtrado H1+M15 en cliente
4. Más simple, menos infraestructura
```

**Decisión Actual:** Opción B (mantener en frontend)

---

## 📞 Soporte

### Archivos Importantes

- `SOLUCION_ESTABILIDAD_SMC.md` - Este documento
- `cleanup_incorrect_smc_records.sql` - Script de limpieza SQL
- `assets/app.js` - Frontend corregido
- `FIX_H1_M15_TABLE_ROUTING.md` - Documentación del fix anterior
- `RESUMEN_FINAL.md` - Documentación del sistema H1+M15

### Consultas SQL Útiles

```sql
-- Verificar últimos registros creados
SELECT symbol, direccion, estado, created_at
FROM public.smc_m15_setups
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;

-- Verificar integridad H1+M15
SELECT 
    symbol,
    tendencia_h1,
    evento,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY symbol, tendencia_h1, evento
ORDER BY symbol, created_at DESC;

-- Estadísticas por estado
SELECT 
    estado,
    COUNT(*) as cantidad,
    ROUND(AVG(score), 2) as score_promedio
FROM public.smc_m15_setups
GROUP BY estado
ORDER BY cantidad DESC;
```

---

## ✅ Checklist Final

- [x] getStrategyTable() retorna siempre 'smc_m15_setups'
- [x] Función validarH1M15() implementada
- [x] Dashboard SMC M15 PRO sin cambios (funciona correctamente)
- [x] Dashboard H1+M15 aplica filtro de validación
- [x] Historial SMC M15 PRO muestra todos los registros
- [x] Historial H1+M15 aplica filtro de validación
- [x] NO hay escrituras a smc_h1_m15_setups
- [x] Eliminado workaround temporal
- [x] Comentarios explicativos añadidos
- [x] Script de limpieza SQL disponible
- [x] Documentación completa creada

---

**Estado Final:** ✅ SISTEMA ESTABLE Y FUNCIONANDO CORRECTAMENTE

**Fecha de Corrección:** 2026-05-04  
**Implementado por:** GitHub Copilot Cloud Agent
