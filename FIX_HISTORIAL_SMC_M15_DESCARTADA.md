# Fix: Historial SMC M15 PRO - Excluir Registros DESCARTADA

## Fecha de Corrección
4 de Mayo de 2026

## Problema Identificado

En el **Historial SMC M15 PRO** aparecían registros con estado **DESCARTADA** que no deberían estar ahí.

### Síntomas
- Al abrir "Historial SMC M15 PRO", se mostraban registros con estado DESCARTADA
- Estos registros parecían venir de la lógica H1+M15

### Causa Raíz
La función `fetchSetupHistory()` en `assets/app.js` (línea 2223) leía **TODOS** los registros de la tabla `smc_m15_setups` sin ningún filtro de estado.

```javascript
// ANTES (INCORRECTO)
async function fetchSetupHistory(limit = 50) {
    const table = getStrategyTable(currentHistoryStrategy);
    const url = `${SUPABASE_URL}/rest/v1/${table}?order=created_at.desc&limit=${limit}`;
    // ❌ Sin filtro de estado - mostraba todo incluyendo DESCARTADA
}
```

## Regla de Estados

### SMC M15 PRO - Estados Válidos
La estrategia **SMC M15 PRO** debe mostrar **SOLO** los siguientes estados:
- ✅ **ACTIVA**: Zona detectada y operativa
- ✅ **EN_ZONA**: Precio dentro de la zona
- ✅ **PROFIT**: Precio salió en profit
- ✅ **TP**: Take Profit alcanzado
- ✅ **SL**: Stop Loss alcanzado
- ✅ **PAUSADA**: Zona válida pero pausada

### SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Estados Válidos
La estrategia **SMC H1+M15 PRO** muestra **TODOS** los estados, incluyendo:
- ✅ **ACTIVA**, **EN_ZONA**, **PROFIT**, **TP**, **SL**, **PAUSADA** (igual que M15 PRO)
- ✅ **DESCARTADA**: Zona que NO cumplió validación H1+M15

## Solución Implementada

Se agregó un **filtro de estado** en la función `fetchSetupHistory()` para excluir registros DESCARTADA cuando se lee el historial de SMC M15 PRO.

```javascript
// DESPUÉS (CORRECTO)
async function fetchSetupHistory(limit = 50) {
    const table = getStrategyTable(currentHistoryStrategy);
    
    // FILTRO CRÍTICO: SMC M15 PRO NO debe mostrar DESCARTADA
    let url = `${SUPABASE_URL}/rest/v1/${table}?order=created_at.desc&limit=${limit}`;
    
    if (currentHistoryStrategy === 'SMC_M15_PRO') {
        // Filtrar estados válidos para SMC M15 PRO
        url += `&estado=in.(ACTIVA,EN_ZONA,PROFIT,TP,SL,PAUSADA)`;
    }
    // SMC_H1_M15_PRO muestra todos los estados (sin filtro adicional)
}
```

### Comportamiento Correcto

| Estrategia | Historial Muestra | Filtro Aplicado |
|------------|------------------|-----------------|
| **SMC M15 PRO** | ACTIVA, EN_ZONA, PROFIT, TP, SL, PAUSADA | ✅ Sí - excluye DESCARTADA |
| **SMC H1+M15 PRO** | Todos los estados incluyendo DESCARTADA | ❌ No - muestra todo |

## Verificación de Corrección

### ✅ Historial SMC M15 PRO
1. Leer desde tabla: `public.smc_m15_setups`
2. Filtrar estados: `estado=in.(ACTIVA,EN_ZONA,PROFIT,TP,SL,PAUSADA)`
3. **NO** muestra: DESCARTADA

### ✅ Historial SMC H1+M15 PRO
1. Leer desde tabla: `public.smc_h1_m15_setups`
2. **SIN** filtro de estado
3. Muestra: Todos los estados incluyendo DESCARTADA

### ✅ Dashboard SMC M15 PRO
- **NO AFECTADO** por este cambio
- La función `getSetupEnZonaOrProfit()` ya filtraba correctamente (EN_ZONA, PROFIT, TP)
- El Dashboard no mostraba ni muestra DESCARTADA

## Archivo Modificado

- **`assets/app.js`** (líneas 2223-2250)
  - Función: `fetchSetupHistory()`
  - Cambio: Agregado filtro condicional de estado para SMC_M15_PRO

## Notas Importantes

1. **Dashboard SMC M15 PRO**: No tocado (como solicitado)
2. **Lectura del Historial**: Ahora filtra correctamente por estrategia
3. **Escritura de Datos**: No modificada (ya funcionaba correctamente)
4. **Tabla Independiente**: Cada estrategia sigue usando su tabla independiente

## Estados DESCARTADA

### ¿Por Qué Existen Registros DESCARTADA?

Los registros DESCARTADA **solo deben existir en** `public.smc_h1_m15_setups` porque:
- Se crean cuando una zona NO cumple la validación H1+M15
- Esta validación **solo aplica** a la estrategia SMC H1+M15 PRO
- SMC M15 PRO **NO aplica** esta validación

### ¿Dónde Pertenece DESCARTADA?

| Estado | Tabla Correcta | Historial Correcto |
|--------|---------------|-------------------|
| DESCARTADA | `smc_h1_m15_setups` | Historial SMC H1+M15 PRO |
| ~~DESCARTADA~~ | ~~`smc_m15_setups`~~ | ~~Historial SMC M15 PRO~~ ❌ |

## Resultado Final

✅ **Historial SMC M15 PRO** ahora muestra **SOLO** los registros con estados válidos de SMC M15 PRO.

✅ **Historial SMC H1+M15 PRO** sigue mostrando **TODOS** los registros incluyendo DESCARTADA.

✅ **Dashboard SMC M15 PRO** no fue modificado (como solicitado).

## Autor
- Implementación: GitHub Copilot Agent
- Fecha: 4 de Mayo de 2026
