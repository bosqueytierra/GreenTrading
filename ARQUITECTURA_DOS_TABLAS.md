# Arquitectura de Dos Tablas - Aislamiento Real por Estrategia

## Fecha de Implementación
4 de Mayo de 2026

## Problema Resuelto
La implementación anterior usaba **una sola tabla** (`smc_m15_setups`) con **filtrado visual** para simular dos estrategias. Esto NO proporcionaba aislamiento real.

## Solución Implementada

### Arquitectura Correcta: Dos Tablas Independientes

#### 1. SMC M15 PRO (Estrategia Original)
```
Tabla: public.smc_m15_setups
- Dashboard lee/escribe SOLO de/a esta tabla
- Historial lee SOLO de esta tabla
- NO aplica validación H1+M15
- Lógica original sin modificaciones
- Lee velas de: public.market_candles
```

#### 2. SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) (Estrategia Nueva)
```
Tabla: public.smc_h1_m15_setups
- Dashboard lee/escribe SOLO de/a esta tabla
- Historial lee SOLO de esta tabla
- APLICA validación H1+M15 al CREAR setups
- Si no cumple → estado DESCARTADA
- Lee velas de: public.market_candles
```

## Cambios Implementados

### 1. Función `getStrategyTable()` (línea ~329)
```javascript
function getStrategyTable(strategy = null) {
    // Retorna la tabla correspondiente a cada estrategia
    const strat = strategy || currentStrategy;
    return STRATEGIES[strat]?.table || 'smc_m15_setups';
}
```

**Comportamiento:**
- SMC_M15_PRO → retorna `'smc_m15_setups'`
- SMC_H1_M15_PRO → retorna `'smc_h1_m15_setups'`

### 2. Función `cumpleValidacionH1M15()` (línea ~830)
```javascript
function cumpleValidacionH1M15(symbol, tendenciaH1, eventoM15) {
    const tipoIndice = symbol.includes('Boom') ? 'Boom' : 'Crash';
    
    if (tipoIndice === 'Boom') {
        // Boom: H1 ALCISTA + M15 ALCISTA (CHOCH o BOS)
        return tendenciaH1 === 'ALCISTA' && 
               (eventoM15.includes('CHOCH_ALCISTA') || eventoM15.includes('BOS_ALCISTA'));
    }
    
    if (tipoIndice === 'Crash') {
        // Crash: H1 BAJISTA + M15 BAJISTA (CHOCH o BOS)
        return tendenciaH1 === 'BAJISTA' && 
               (eventoM15.includes('CHOCH_BAJISTA') || eventoM15.includes('BOS_BAJISTA'));
    }
    
    return false;
}
```

**Propósito:** Validación al CREAR el setup, NO para filtrado visual.

### 3. Validación en `trackZoneHistory()` (línea ~1026)
```javascript
// VALIDACIÓN H1+M15: Si estamos en estrategia H1+M15, validar antes de determinar el estado
let estadoInicial;
if (currentStrategy === 'SMC_H1_M15_PRO') {
    // Validar H1+M15
    const cumpleH1M15 = cumpleValidacionH1M15(
        symbol, 
        analysis.smc.tendenciaH1 || '--', 
        ultimo_evento_m15
    );
    
    if (!cumpleH1M15) {
        // No cumple validación → DESCARTADA
        newSetup.estado = 'DESCARTADA';
        newSetup.motivo_cierre = razonDescarte;
        newSetup.fecha_cierre = new Date().toISOString();
        
        await createSetup(newSetup);
        return; // No continuar con lógica de zona operativa
    }
    
    // Cumple validación → continuar normalmente
    estadoInicial = dashboardLocked || mainOperativeZone ? 'PAUSADA' : 'ACTIVA';
} else {
    // SMC M15 PRO: No aplicar validación H1+M15
    estadoInicial = dashboardLocked || mainOperativeZone ? 'PAUSADA' : 'ACTIVA';
}
```

**Comportamiento:**
- **SMC M15 PRO**: Crea setups sin validación H1+M15
- **SMC H1+M15 PRO**: Valida antes de crear:
  - ✅ Cumple → crea como ACTIVA o PAUSADA
  - ❌ No cumple → crea como DESCARTADA y retorna

## Flujo de Datos

### Dashboard
```
Usuario selecciona estrategia (tab) → currentStrategy se actualiza
                                    ↓
                     fetchAllIndices() → llama trackZoneHistory()
                                    ↓
                     getStrategyTable() → retorna tabla correcta
                                    ↓
              Todas las lecturas/escrituras usan la tabla correcta
```

### Historial
```
Usuario selecciona estrategia (tab) → currentHistoryStrategy se actualiza
                                    ↓
                     fetchSetupHistory() → llama getStrategyTable(currentHistoryStrategy)
                                    ↓
                     Lee de la tabla correcta según estrategia
```

## Aislamiento Real Garantizado

### ✅ Escritura Independiente
- SMC M15 PRO escribe SOLO a `smc_m15_setups`
- SMC H1+M15 PRO escribe SOLO a `smc_h1_m15_setups`
- NO hay compartición de tabla de resultados

### ✅ Lectura Independiente
- Dashboard SMC M15 PRO lee SOLO de `smc_m15_setups`
- Dashboard SMC H1+M15 PRO lee SOLO de `smc_h1_m15_setups`
- Historial SMC M15 PRO lee SOLO de `smc_m15_setups`
- Historial SMC H1+M15 PRO lee SOLO de `smc_h1_m15_setups`

### ✅ Validación en Escritura (No Visual)
- La validación H1+M15 se aplica al **CREAR** el setup
- Las zonas descartadas quedan registradas en la tabla con estado DESCARTADA
- NO se usa filtrado visual para ocultar datos

### ✅ Datos Compartidos
- Ambas estrategias leen velas de `public.market_candles`
- Esta es la única fuente de datos compartida (correcto)

## Funciones Afectadas

Todas las funciones que leen/escriben setups ahora usan `getStrategyTable()`:
- `getAllActiveSetups()`
- `createSetup()`
- `updateSetup()`
- `getSetupEnZonaOrProfit()`
- `fetchSetupHistory()`
- `trackZoneHistory()`
- `ensureSingleOperativeZone()`
- `handleSLHitAndReactivatePausedZones()`

## Estados de Setup en H1+M15

La estrategia H1+M15 PRO puede tener setups en los siguientes estados:

1. **DESCARTADA**: No cumple validación H1+M15 al momento de creación
2. **PAUSADA**: Cumple validación pero hay otra zona operativa activa
3. **ACTIVA**: Cumple validación y es la zona operativa principal
4. **EN_ZONA**: Precio entró en la zona
5. **PROFIT**: Precio salió de la zona en profit
6. **TP**: Take Profit 1:1 alcanzado
7. **SL**: Stop Loss alcanzado

## Diferencias Clave con Implementación Anterior

| Aspecto | ❌ Implementación Incorrecta | ✅ Implementación Correcta |
|---------|------------------------------|----------------------------|
| Tablas | Una sola (`smc_m15_setups`) | Dos independientes |
| Separación | Visual (filtrado en frontend) | Real (tablas separadas) |
| Validación H1+M15 | En lectura (filtro visual) | En escritura (al crear setup) |
| Zonas descartadas | No se guardan | Se guardan con estado DESCARTADA |
| Historial | Mismo para ambas (filtrado) | Independiente por estrategia |
| Aislamiento | NO | SÍ ✓ |

## Verificación de Aislamiento

Para verificar que el aislamiento funciona correctamente:

1. **En SMC M15 PRO**: 
   - Crear una zona con H1 BAJISTA y M15 ALCISTA
   - Debe crearse como ACTIVA/PAUSADA (sin validación)
   - Debe aparecer en `smc_m15_setups`

2. **En SMC H1+M15 PRO (Boom)**:
   - Crear una zona con H1 BAJISTA y M15 ALCISTA
   - Debe crearse como DESCARTADA
   - Debe aparecer en `smc_h1_m15_setups`
   - NO debe aparecer en `smc_m15_setups`

3. **Historial**:
   - Historial SMC M15 PRO debe mostrar SOLO setups de `smc_m15_setups`
   - Historial H1+M15 PRO debe mostrar SOLO setups de `smc_h1_m15_setups`

## Próximos Pasos

- [ ] Testing en ambiente real con ambas estrategias
- [ ] Verificar que los setups se crean en las tablas correctas
- [ ] Verificar que el historial muestra datos independientes
- [ ] Confirmar que no hay compartición de resultados
- [ ] Documentar comportamiento observado

## Notas Importantes

1. **NO modificar** `getStrategyTable()` para forzar una tabla específica
2. **NO agregar** filtrado visual adicional (la separación es real, no visual)
3. **Mantener** la validación H1+M15 SOLO en `trackZoneHistory()` al crear setups
4. **NO aplicar** validación H1+M15 en SMC M15 PRO

## Autores
- Implementación: GitHub Copilot Agent
- Especificación: bosqueytierra
- Fecha: 4 de Mayo de 2026
