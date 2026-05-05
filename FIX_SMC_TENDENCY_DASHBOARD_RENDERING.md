# Fix: SMC_TENDENCY_H1_M15 Dashboard Rendering

## Problema Original

El dashboard SMC_TENDENCY_H1_M15 estaba mostrando la misma zona cruda que SMC M15 PRO sin aplicar la validación específica de la estrategia.

### Síntomas
- Zonas inválidas (que no cumplían H1+M15) se mostraban como válidas
- Se renderizaba `analysis.smc.zonaM15` directamente sin filtrar
- Score, OB, FVG, Barrida y zona madre se mostraban para zonas que no cumplían validación

## Solución Implementada

### 1. Nueva Función de Validación

Se creó `SMC_TENDENCY_H1_M15_isValidSetup()` en `assets/app.js` (líneas 1509-1556):

```javascript
function SMC_TENDENCY_H1_M15_isValidSetup(symbol, smc) {
    // Solo aplica si currentStrategy === 'SMC_TENDENCY_H1_M15'
    
    // Para BOOM:
    //   ✅ H1 = ALCISTA + M15 evento = CHOCH_ALCISTA o BOS_ALCISTA
    //   ❌ Cualquier otra combinación
    
    // Para CRASH:
    //   ✅ H1 = BAJISTA + M15 evento = CHOCH_BAJISTA o BOS_BAJISTA
    //   ❌ Cualquier otra combinación
}
```

**Características:**
- Usa case-insensitive matching para símbolos (seguridad)
- Usa `.includes()` para eventos (consistencia con backend)
- Registra en consola cuando una zona NO cumple validación
- Retorna `false` para zonas inválidas

### 2. Modificación de createTableRow()

En `assets/app.js` (líneas 1579-1583):

```javascript
// Determine if there's a valid zone
let hasValidZone = smc.zonaM15 && smc.zonaM15.es_util;

// Apply SMC_TENDENCY_H1_M15 validation filter BEFORE rendering
if (currentStrategy === 'SMC_TENDENCY_H1_M15') {
    const isValidForStrategy = SMC_TENDENCY_H1_M15_isValidSetup(symbol, smc);
    hasValidZone = hasValidZone && isValidForStrategy;
}
```

**Flujo de renderizado:**
1. Si existe `setupEnZonaOrProfit` en DB → usar datos guardados
2. Si `!hasValidZone` → mostrar `SIN_SETUP` (score=0, NO indicadores)
3. Si `hasValidZone` → mostrar zona con datos completos

### 3. Actualización de getSetupEnZonaOrProfit()

En `assets/app.js` (líneas 451-491):

**Cambios:**
- Ahora incluye `ACTIVA` en la query (además de EN_ZONA, PROFIT, TP)
- Usa `getStrategyTable()` para consultar tabla correcta
- Evita mostrar zonas raw cuando ya existe setup guardado

```javascript
const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${symbol}&estado=in.(ACTIVA,EN_ZONA,PROFIT,TP)&order=created_at.desc&limit=5`;
```

## Validación Backend (Ya Existía)

La validación en `trackZoneHistory()` (líneas 1157-1179) ya implementaba las mismas reglas:

```javascript
if (currentStrategy === 'SMC_TENDENCY_H1_M15') {
    let cumpleValidacion = false;
    if (tipoIndice === 'Boom') {
        cumpleValidacion = tendenciaH1 === 'ALCISTA' && 
            (ultimo_evento_m15.includes('CHOCH_ALCISTA') || ultimo_evento_m15.includes('BOS_ALCISTA'));
    } else if (tipoIndice === 'Crash') {
        cumpleValidacion = tendenciaH1 === 'BAJISTA' && 
            (ultimo_evento_m15.includes('CHOCH_BAJISTA') || ultimo_evento_m15.includes('BOS_BAJISTA'));
    }
    
    if (!cumpleValidacion) {
        console.log(`✗ Zona NO creada - NO cumple validación SMC_TENDENCY_H1_M15`);
        return; // No crear zona, no guardar DESCARTADA
    }
}
```

## Resultado

### Antes del Fix
```
Dashboard SMC_TENDENCY_H1_M15:
  Boom 1000 Index:
    H1: BAJISTA
    M15: CHOCH_BAJISTA
    Zona: 1234.56 - 1235.78 ❌ (NO debería mostrarse)
    Score: 8 ❌
    OB: SÍ ❌
    Estado: ACTIVA ❌
```

### Después del Fix
```
Dashboard SMC_TENDENCY_H1_M15:
  Boom 1000 Index:
    H1: BAJISTA
    M15: CHOCH_BAJISTA
    Zona: -- ✅
    Score: 0 ✅
    OB: NO ✅
    FVG: NO ✅
    Barrida: NO ✅
    Estado: SIN_SETUP ✅

Console: ❌ SMC_TENDENCY_H1_M15 filter: Boom 1000 Index NO cumple...
```

## Casos de Prueba

### ✅ Caso 1: BOOM Válido
- Symbol: Boom 1000 Index
- H1: ALCISTA
- M15: CHOCH_ALCISTA
- **Resultado:** Zona se muestra completa con score, OB, FVG, etc.

### ❌ Caso 2: BOOM Inválido (H1 equivocada)
- Symbol: Boom 1000 Index
- H1: BAJISTA
- M15: CHOCH_ALCISTA
- **Resultado:** SIN_SETUP (score=0, NO indicadores)

### ❌ Caso 3: BOOM Inválido (M15 equivocado)
- Symbol: Boom 1000 Index
- H1: ALCISTA
- M15: CHOCH_BAJISTA
- **Resultado:** SIN_SETUP (score=0, NO indicadores)

### ✅ Caso 4: CRASH Válido
- Symbol: Crash 1000 Index
- H1: BAJISTA
- M15: BOS_BAJISTA
- **Resultado:** Zona se muestra completa con score, OB, FVG, etc.

## Características Mantenidas

✅ **Aislamiento de tablas:**
- SMC M15 PRO → `smc_m15_setups`
- SMC H1+M15 PRO → `smc_h1_m15_setups`
- SMC_TENDENCY_H1_M15 → `smc_tendency_h1_m15_setups`

✅ **Zonas PAUSADA:**
- Solo se descartan si precio toca SL
- NO se descartan por cambios en H1/M15
- Comportamiento igual que SMC M15 PRO

✅ **Estados permitidos:**
- ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL
- NO se crean registros DESCARTADA

✅ **SMC M15 PRO:**
- Completamente sin afectar
- Usa código path diferente (no entra al `if` de SMC_TENDENCY_H1_M15)

## Debugging

Los logs de consola ayudan a identificar por qué una zona no se muestra:

```javascript
// Log cuando validación falla
❌ SMC_TENDENCY_H1_M15 filter: Boom 1000 Index NO cumple (BOOM requiere H1=ALCISTA + M15=CHOCH/BOS_ALCISTA, actual: H1=BAJISTA, M15=CHOCH_BAJISTA)
```

## Archivos Modificados

- `assets/app.js`
  - Nueva función: `SMC_TENDENCY_H1_M15_isValidSetup()` (líneas 1509-1556)
  - Modificación: `createTableRow()` (líneas 1579-1583)
  - Modificación: `getSetupEnZonaOrProfit()` (líneas 451-491)

## Fecha
2026-05-05

## Autor
GitHub Copilot Agent
