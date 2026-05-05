# Separación Real del Render: SMC_TENDENCY_H1_M15 vs SMC M15 PRO

## Problema Original

El dashboard SMC_TENDENCY_H1_M15 estaba compartiendo la misma función de renderizado (`createTableRow`) con SMC M15 PRO, lo que causaba que ambos dashboards mostraran los mismos datos sin aplicar correctamente la validación específica de SMC_TENDENCY_H1_M15.

## Solución Implementada

Se creó un **sistema de renderizado completamente separado** para SMC_TENDENCY_H1_M15:

### 1. Nueva Función: `getSetupEnZonaOrProfit_SMC_TENDENCY_H1_M15(symbol)`

**Ubicación:** `assets/app.js` líneas 498-538

**Características:**
- Lee **EXCLUSIVAMENTE** de la tabla `smc_tendency_h1_m15_setups`
- NO consulta tablas de otras estrategias
- Busca setups en estados: ACTIVA, EN_ZONA, PROFIT, TP
- Filtra TPs liberados (released)
- Retorna `null` si no hay setup válido

```javascript
const table = 'smc_tendency_h1_m15_setups'; // Tabla hardcoded, no usa getStrategyTable()
```

### 2. Nueva Función: `createTableRow_SMC_TENDENCY_H1_M15(symbol, data)`

**Ubicación:** `assets/app.js` líneas 1773-2004 (aprox.)

**Características:**

#### Validación Estricta (Líneas 1803-1824)
```javascript
// Para BOOM:
cumpleValidacion = tendenciaH1 === 'ALCISTA' && 
    (ultimoEventoM15.includes('CHOCH_ALCISTA') || ultimoEventoM15.includes('BOS_ALCISTA'));

// Para CRASH:
cumpleValidacion = tendenciaH1 === 'BAJISTA' && 
    (ultimoEventoM15.includes('CHOCH_BAJISTA') || ultimoEventoM15.includes('BOS_BAJISTA'));
```

#### Flujo de Renderizado

**Si validación FALLA (`!cumpleValidacion`):**
- Zona madre: `--`
- Score: `0`
- OB: `NO`
- FVG: `NO`
- Barrida: `NO`
- Estado: `SIN_SETUP`
- **NO consulta setup guardado**
- **NO crea historial**
- **NO guarda nada**

**Si validación PASA (`cumpleValidacion`):**
1. Busca setup guardado con `getSetupEnZonaOrProfit_SMC_TENDENCY_H1_M15(symbol)`
2. Si existe setup guardado → usa sus datos
3. Si no existe setup pero hay zona en análisis → muestra zona nueva
4. Si no hay zona → muestra SIN_SETUP

### 3. Actualización de `updateBoomTable()` y `updateCrashTable()`

**Ubicación:** `assets/app.js` líneas 1536-1566

**Lógica:**
```javascript
if (currentStrategy === 'SMC_TENDENCY_H1_M15') {
    row = await createTableRow_SMC_TENDENCY_H1_M15(symbol, results[symbol]);
} else {
    row = await createTableRow(symbol, results[symbol]);
}
```

**Resultado:**
- SMC_TENDENCY_H1_M15 → usa `createTableRow_SMC_TENDENCY_H1_M15`
- SMC M15 PRO → usa `createTableRow` original
- SMC H1+M15 PRO → usa `createTableRow` original

### 4. Limpieza de la Función Original

**`createTableRow(symbol, data)`** (SMC M15 PRO y SMC H1+M15 PRO):
- Se **eliminó** toda lógica de validación de SMC_TENDENCY_H1_M15
- Ya NO contiene el `if (currentStrategy === 'SMC_TENDENCY_H1_M15')` 
- Función pura sin condiciones para otras estrategias

**`SMC_TENDENCY_H1_M15_isValidSetup()`:**
- **Función eliminada completamente**
- La validación ahora está directamente en `createTableRow_SMC_TENDENCY_H1_M15`

## Diferencias Clave vs Implementación Anterior

### Antes (Compartido)
```
✗ Ambas estrategias usaban createTableRow()
✗ Validación dentro de createTableRow con if/else
✗ getSetupEnZonaOrProfit() consultaba getStrategyTable()
✗ SMC_TENDENCY_H1_M15_isValidSetup() como función separada
✗ Podía mostrar datos de fallback incorrectos
```

### Ahora (Separado)
```
✓ SMC_TENDENCY_H1_M15 usa createTableRow_SMC_TENDENCY_H1_M15()
✓ SMC M15 PRO usa createTableRow() original
✓ getSetupEnZonaOrProfit_SMC_TENDENCY_H1_M15() tabla hardcoded
✓ Validación integrada en el renderer
✓ NO hay fallback si validación falla
✓ Separación real de lógica
```

## Casos de Prueba

### ✅ Caso 1: BOOM Válido
- Symbol: `Boom 1000 Index`
- H1: `ALCISTA`
- M15: `CHOCH_ALCISTA`
- **Resultado:** Muestra zona completa con score, OB, FVG, Barrida, estado

### ❌ Caso 2: BOOM Inválido (H1 opuesto)
- Symbol: `Boom 1000 Index`
- H1: `BAJISTA`
- M15: `CHOCH_ALCISTA` (correcto para BOOM pero H1 está mal)
- **Resultado:** 
  - Console: `❌ SMC_TENDENCY_H1_M15: Boom 1000 Index NO cumple validación`
  - Zona: `--`
  - Score: `0`
  - OB/FVG/Barrida: `NO`
  - Estado: `SIN_SETUP`

### ❌ Caso 3: CRASH Inválido (M15 opuesto)
- Symbol: `Crash 1000 Index`
- H1: `BAJISTA` (correcto)
- M15: `CHOCH_ALCISTA` (incorrecto para CRASH)
- **Resultado:** Igual que Caso 2

### ✅ Caso 4: CRASH Válido
- Symbol: `Crash 1000 Index`
- H1: `BAJISTA`
- M15: `BOS_BAJISTA`
- **Resultado:** Muestra zona completa

### ⚠️ Caso 5: Validación OK pero sin zona
- H1 y M15 correctos
- Pero `smc.zonaM15.es_util === false`
- **Resultado:** 
  - Console: `⚠️ SMC_TENDENCY_H1_M15: ... cumple validación pero sin zona útil`
  - Muestra: `SIN_SETUP`

## Logging de Debugging

La función registra en consola cada decisión:

```javascript
// Validación falla
❌ SMC_TENDENCY_H1_M15: Boom 1000 Index NO cumple validación (H1=BAJISTA, M15=CHOCH_ALCISTA)

// Usando setup guardado
✅ SMC_TENDENCY_H1_M15: Boom 1000 Index usando setup guardado (estado=EN_ZONA)

// Zona nueva detectada
✅ SMC_TENDENCY_H1_M15: Boom 1000 Index zona nueva detectada (no guardada aún)

// Validación OK pero sin zona
⚠️ SMC_TENDENCY_H1_M15: Boom 1000 Index cumple validación pero sin zona útil
```

## Resultado Esperado

### SMC M15 PRO
- Muestra **todas** las zonas detectadas
- Si hay 10 zonas, muestra las 10

### SMC_TENDENCY_H1_M15
- Muestra **solo** zonas que cumplen:
  - BOOM: H1=ALCISTA + M15 evento CHOCH/BOS_ALCISTA
  - CRASH: H1=BAJISTA + M15 evento CHOCH/BOS_BAJISTA
- Si hay 10 zonas pero solo 3 cumplen validación, muestra 3 válidas + 7 `SIN_SETUP`

## Archivos Modificados

- `assets/app.js`
  - **Nueva:** `getSetupEnZonaOrProfit_SMC_TENDENCY_H1_M15()` (líneas 498-538)
  - **Nueva:** `createTableRow_SMC_TENDENCY_H1_M15()` (líneas 1773-2004)
  - **Modificada:** `updateBoomTable()` (líneas 1536-1550)
  - **Modificada:** `updateCrashTable()` (líneas 1552-1566)
  - **Limpiada:** `createTableRow()` (eliminada validación SMC_TENDENCY_H1_M15)
  - **Eliminada:** `SMC_TENDENCY_H1_M15_isValidSetup()`

## Verificación

Para verificar que funciona correctamente:

1. Abrir dashboard SMC M15 PRO
   - Debe mostrar todas las zonas sin filtros
   
2. Cambiar a SMC_TENDENCY_H1_M15
   - Debe aplicar validación estricta
   - Zonas inválidas muestran `SIN_SETUP`
   - Console muestra logs de validación

3. Verificar que ambos dashboards son independientes
   - Los datos NO deben coincidir si hay zonas inválidas

## Fecha
2026-05-05

## Autor
GitHub Copilot Agent
