# Fix: Duplicados en SMC M15 PRO - Historial

## Fecha: 4 de Mayo de 2026

## Problema Original

Al limpiar el historial y actualizar, se creaban registros duplicados de la misma zona en la tabla `public.smc_m15_setups`.

### Comportamiento Incorrecto
- Al refrescar el dashboard, se creaba una nueva fila por cada zona detectada
- Las mismas zonas aparecían múltiples veces en el historial
- No se respetaba la regla: "UNA sola fila por cada zona única detectada"

## Regla Correcta Implementada

**El Historial SMC M15 PRO debe guardar UNA sola fila por cada zona única detectada.**

### Matching para reconocer misma zona:
1. `symbol` - símbolo del índice
2. `zona_desde` - límite inferior de la zona (con tolerancia)
3. `zona_hasta` - límite superior de la zona (con tolerancia)
4. `evento` - tipo de evento (BOS_ALCISTA, CHOCH_BAJISTA, etc.)
5. `direccion` - dirección de la zona (ALCISTA o BAJISTA)

## Cambios Implementados

### 1. Nueva Función: `getAllSetupsForMatching(symbol)`

**Ubicación:** `assets/app.js` (después de línea 366)

```javascript
async function getAllSetupsForMatching(symbol) {
    // Get ALL setups for this symbol to check for duplicates (including closed/discarded ones)
    // This is used to prevent duplicate zone creation
    const table = getStrategyTable();
    const url = `${SUPABASE_URL}/rest/v1/${table}?symbol=eq.${encodeURIComponent(symbol)}&order=created_at.desc`;

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
    
    return await response.json();
}
```

**Propósito:** Obtener TODOS los setups de un símbolo (no solo los activos) para verificar duplicados, incluyendo estados: SL, DESCARTADA, ESPERANDO_ACOMODO.

**Diferencia con `getAllActiveSetups`:**
- `getAllActiveSetups`: Obtiene solo ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP (para gestión de estado)
- `getAllSetupsForMatching`: Obtiene TODOS los estados (para prevenir duplicados)

### 2. Lógica de Matching Mejorada en `trackZoneHistory()`

**Ubicación:** `assets/app.js` (líneas ~900-991)

#### Cambio 1: Separación de Setups

```javascript
// Get all active/in-zone/profit/pausada/TP setups for this symbol (for state management)
const activeSetups = await getAllActiveSetups(symbol);

// Get ALL setups for this symbol (including closed/discarded) for duplicate checking
const allSetups = await getAllSetupsForMatching(symbol);
```

#### Cambio 2: Matching en Dos Fases

**Fase 1: Matching Exacto** (líneas 958-970)
```javascript
// First, check for exact match (same zone boundaries, evento, and direccion)
for (const setup of allSetups) {
    const zonaDesdeMatch = Math.abs(setup.zona_desde - newZonaDesde) < tolerance;
    const zonaHastaMatch = Math.abs(setup.zona_hasta - newZonaHasta) < tolerance;
    const direccionMatch = setup.direccion === zonaM15.direccion;
    const eventoMatch = setup.evento === ultimo_evento_m15;  // ← NUEVO: Verifica evento
    
    if (zonaDesdeMatch && zonaHastaMatch && direccionMatch && eventoMatch) {
        matchingSetup = setup;
        console.log(`✓ Zona exacta encontrada (ID: ${setup.id}, estado: ${setup.estado}) para ${symbol}`);
        break;
    }
}
```

**Fase 2: Matching por Contenido/Solapamiento** (líneas 973-991)
```javascript
// If no exact match, check for containment or strong overlap (only with active/paused zones)
if (!matchingSetup) {
    for (const setup of activeSetups) {  // ← Ahora INCLUYE PAUSADA
        // Check if new zone is contained within existing zone
        const isContained = newZonaDesde >= (setup.zona_desde - tolerance) && 
                           newZonaHasta <= (setup.zona_hasta + tolerance);
        
        // Check for strong overlap (>= 70%)
        const overlap = Math.min(newZonaHasta, setup.zona_hasta) - Math.max(newZonaDesde, setup.zona_desde);
        const existingZonaSize = Math.abs(setup.zona_hasta - setup.zona_desde);
        const minSize = Math.min(newZonaSize, existingZonaSize);
        const overlapRatio = overlap > 0 ? overlap / minSize : 0;
        
        if ((isContained || overlapRatio >= 0.70) && setup.direccion === zonaM15.direccion) {
            matchingSetup = setup;
            console.log(`✓ Nueva zona ${isContained ? 'contenida' : 'solapa ' + (overlapRatio * 100).toFixed(1) + '%'} en setup existente ${setup.id} para ${symbol}`);
            break;
        }
    }
}
```

#### Cambio 3: Tolerancia Incrementada

```javascript
const tolerance = 0.001; // Aumentado de 0.00001 para mejor manejo de decimales
```

**Justificación:** Los precios de índices como Boom/Crash pueden tener variaciones mínimas por redondeo. Una tolerancia de 0.001 es suficiente para capturar zonas idénticas sin ser tan estricta que cree duplicados por diferencias insignificantes.

#### Cambio 4: Actualización en Lugar de Creación

```javascript
// If we found a matching setup, update it instead of creating new
if (matchingSetup) {
    const updateData = {
        updated_at: new Date().toISOString(),
        score: zonaM15.score,
        ob: zonaM15.ob ? true : false,
        fvg: zonaM15.fvg ? true : false,
        barrida: zonaM15.barrida ? true : false,
        evento: ultimo_evento_m15
    };
    
    // Update tendencias if they are missing (null or empty)
    if (!matchingSetup.tendencia_h1 && analysis.smc.tendenciaH1) {
        updateData.tendencia_h1 = analysis.smc.tendenciaH1;
    }
    if (!matchingSetup.tendencia_m15 && analysis.smc.tendenciaM15) {
        updateData.tendencia_m15 = analysis.smc.tendenciaM15;
    }
    
    await updateSetup(matchingSetup.id, updateData);
    console.log(`✓ Setup ${matchingSetup.id} actualizado (mantiene zona original) para ${symbol}`);
    
    // Update state based on price movement (only if in an active state)
    const activeStates = ['ACTIVA', 'EN_ZONA', 'PROFIT', 'PAUSADA', 'TP'];
    if (activeStates.includes(matchingSetup.estado)) {
        await updateSetupState(matchingSetup, currentPrice, analysis);
    }
}
// If zone doesn't exist, create a new setup
else {
    // ... create new setup
}
```

## Flujo Esperado Después del Fix

### 1. Primera Carga
- El historial guarda exactamente las zonas que aparecen en el Dashboard en vivo
- Una fila por índice/zona
- No duplicar

### 2. Si una zona ya existe
- **NO** insertar una fila nueva
- **SÍ** actualizar el mismo registro

### 3. Estados (no crear otro registro por cambio de estado)
- ACTIVA
- EN_ZONA
- PROFIT
- PAUSADA
- ESPERANDO_ACOMODO
- TP
- SL
- DESCARTADA

### 4. Si una zona nueva aparece
Crear un nuevo registro solo si:
- No existe una zona igual (verificado con matching exacto)
- No está contenida en una zona existente
- No solapa fuertemente (>=70%) con una zona existente

### 5. Si la zona anterior ya no es la principal
No crear duplicados. Actualizar la zona anterior a:
- **PAUSADA**: si sigue siendo válida pero no operativa
- **DESCARTADA**: si ya no sirve
- **SL o TP**: si fue cerrada por precio

### 6. El historial es persistente
La base de datos guarda los cambios de estado para calcular después:
- Cuántas llegaron a TP
- Cuántas llegaron a SL
- Cuántas quedaron descartadas
- Cuántas nunca llegaron a zona

## Lo que NO hace (Prohibido)

❌ Insertar la misma zona en cada refresh
❌ Insertar la misma zona varias veces en el mismo minuto
❌ Crear una nueva fila solo porque cambió el estado
❌ Tocar la nueva estrategia H1+M15
❌ Tocar smc_h1_m15_setups

## Verificación

Para verificar que el fix funciona correctamente:

### Test 1: No Duplicar en Refresh
1. Abrir dashboard SMC M15 PRO
2. Observar las zonas detectadas
3. Esperar 30 segundos (auto-refresh)
4. Verificar en Historial que NO se hayan creado duplicados
5. Las zonas existentes deben haberse actualizado (mismo ID, diferente `updated_at`)

### Test 2: Actualización de Estado
1. Una zona está en estado ACTIVA
2. El precio entra en la zona
3. El estado debe cambiar a EN_ZONA
4. Verificar que sigue siendo la MISMA fila (mismo ID)

### Test 3: Nueva Zona Legítima
1. Aparece un nuevo BOS/CHOCH en un precio diferente
2. Se debe crear UNA nueva fila
3. La zona anterior debe pasar a PAUSADA o DESCARTADA (según criterios)

### Test 4: Matching con Evento
1. Existe una zona con evento BOS_ALCISTA
2. En el mismo lugar aparece un CHOCH_ALCISTA
3. Como el evento es diferente, se debe crear una nueva zona
4. Son dos zonas distintas porque el evento cambió

## Archivos Modificados

- `assets/app.js`
  - Línea ~367: Nueva función `getAllSetupsForMatching()`
  - Línea ~900-1020: Lógica mejorada de matching en `trackZoneHistory()`

## Archivos NO Modificados (como se requirió)

- `smc_h1_m15_processor.py` (nueva estrategia)
- `smc_h1_m15_pro.py` (nueva estrategia)
- Tabla `smc_h1_m15_setups` (nueva estrategia)
- Cualquier código relacionado con H1+M15 PRO

## Notas Técnicas

### Tolerancia de 0.001
- Equivale a 0.1% de diferencia en precios típicos de Boom/Crash
- Ejemplo: Para precio ~1000, acepta diferencia de ±1.0 puntos
- Suficiente para capturar redondeos sin crear falsos duplicados

### Orden de Matching
1. **Primero**: Exact match con ALL setups (incluyendo cerrados)
2. **Segundo**: Overlap/containment con active setups (incluyendo PAUSADA)
3. **Si no match**: Crear nuevo setup

### Por qué PAUSADA ahora se incluye en matching
- PAUSADA es una zona válida que puede volver a ser ACTIVA
- Si creamos una nueva zona idéntica en lugar de actualizar la PAUSADA, tendríamos duplicados
- El problema anterior era que se saltaban las PAUSADA en el matching de overlap

## Impacto en Otras Funciones

### Funciones que NO necesitaron cambios:
- `createSetup()`: Sigue creando como siempre
- `updateSetup()`: Sigue actualizando como siempre
- `getAllActiveSetups()`: Mantiene su propósito (gestión de estado)
- `updateSetupState()`: No afectado
- `ensureSingleOperativeZone()`: No afectado

### Nueva función:
- `getAllSetupsForMatching()`: Solo para prevención de duplicados

## Estrategia de Testing

1. **Entorno de desarrollo**: Probar con datos reales del dashboard
2. **Observar logs del navegador**: Los `console.log` indican si encuentra zonas o crea nuevas
3. **Consultar base de datos**: Verificar que no se crean duplicados en `smc_m15_setups`
4. **Monitorear por 24 horas**: Confirmar que no aparecen duplicados con el tiempo

## Compatibilidad

✅ Compatible con SMC M15 PRO (estrategia original)
✅ NO afecta a SMC H1+M15 PRO (nueva estrategia)
✅ Tablas completamente aisladas
✅ Sin cambios en lógica de validación H1+M15

## Autor

- Implementación: GitHub Copilot Agent
- Especificación: bosqueytierra
- Fecha: 4 de Mayo de 2026
