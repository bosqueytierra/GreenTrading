# Limpieza de Zonas SMC M15 PRO por Proximidad

## Resumen
Se implementó un sistema automático de limpieza de zonas competidoras para el SMC M15 PRO. Este sistema mantiene activa únicamente la zona más cercana al precio actual para cada símbolo, descartando automáticamente las demás zonas "vivas".

## Problema Solucionado
**Antes:** Cuando se detectaban múltiples zonas para un mismo índice, todas quedaban activas simultáneamente, lo que podía generar confusión y señales contradictorias.

**Ahora:** Solo se mantiene activa la zona con menor distancia al precio actual, las demás se descartan automáticamente.

## Implementación

### 1. Función: `calculateDistanceToZone()`
**Ubicación:** `assets/app.js` líneas 363-378

**Propósito:** Calcular la distancia entre el precio actual y una zona.

**Lógica:**
- Si el precio está **dentro de la zona**: distancia = 0
- Si el precio está **fuera de la zona**: distancia = mínimo de:
  - `abs(precio_actual - zona_desde)`
  - `abs(precio_actual - zona_hasta)`

**Ejemplo:**
```javascript
// Zona: 4500 - 4600
// Precio actual: 4550 (dentro de zona)
// Distancia: 0

// Precio actual: 4400 (fuera de zona)
// Distancia: min(abs(4400 - 4500), abs(4400 - 4600)) = 100
```

### 2. Función: `cleanupZonesByProximity()`
**Ubicación:** `assets/app.js` líneas 380-445

**Propósito:** Mantener solo la zona más cercana al precio para cada símbolo.

**Estados evaluados (zonas "vivas"):**
- ✅ `ACTIVA`
- ✅ `EN_ZONA`
- ✅ `PROFIT`
- ✅ `ESPERANDO_ACOMODO` (si aplica)

**Estados NO tocados:**
- ❌ `TP` (Take Profit alcanzado)
- ❌ `SL` (Stop Loss alcanzado)
- ❌ `DESCARTADA` (ya descartada previamente)

**Proceso:**
1. Obtiene todas las zonas vivas del símbolo
2. Calcula la distancia de cada zona al precio actual
3. Ordena por distancia (ascendente)
4. Mantiene la zona más cercana
5. Descarta todas las demás con motivo: `"Nueva zona descartada por menor proximidad / zona menos cercana al precio actual"`

**Logs generados:**
```
🔍 Limpieza por proximidad para Boom 1000 Index: 3 zonas vivas detectadas
   ✓ Zona más cercana (ID 123): distancia = 0.000, estado = EN_ZONA
   ❌ Descartando zona ID 122: distancia = 45.320, estado = ACTIVA
   ❌ Descartando zona ID 121: distancia = 78.100, estado = PROFIT
✅ Limpieza completada: 1 zona activa, 2 zona(s) descartada(s)
```

### 3. Integración en `trackZoneHistory()`
**Ubicación:** `assets/app.js` línea 805

La limpieza se ejecuta automáticamente después de:
1. Crear un nuevo setup
2. Actualizar un setup existente
3. Actualizar los estados de todos los setups

**Orden de ejecución:**
```javascript
async function trackZoneHistory(symbol, analysis) {
    // 1. Obtener zonas existentes
    // 2. Verificar si hay zona exacta
    // 3. Crear o actualizar setup
    // 4. Actualizar estados de setups
    // 5. NUEVA: Limpiar zonas por proximidad ⭐
    await cleanupZonesByProximity(symbol, currentPrice);
}
```

## Comportamiento por Escenario

### Escenario 1: Precio dentro de una zona
```
Zona A: 4500-4550 (distancia = 0) ✅ MANTENER
Zona B: 4600-4650 (distancia = 50) ❌ DESCARTAR
Zona C: 4400-4450 (distancia = 50) ❌ DESCARTAR
```

### Escenario 2: Precio entre dos zonas
```
Precio actual: 4575

Zona A: 4500-4550 (distancia = 25) ❌ DESCARTAR
Zona B: 4600-4650 (distancia = 25) ❌ DESCARTAR (empate)
```
En caso de empate, se mantiene la primera en el ordenamiento (más reciente por `created_at.desc`).

### Escenario 3: Precio alejado de todas las zonas
```
Precio actual: 5000

Zona A: 4500-4550 (distancia = 450) ❌ DESCARTAR
Zona B: 4600-4650 (distancia = 350) ❌ DESCARTAR
Zona C: 4700-4750 (distancia = 250) ✅ MANTENER (más cercana)
```

## Ventajas del Sistema

### 1. Señales Más Claras
- Solo una zona activa por símbolo
- Elimina confusión de múltiples señales

### 2. Dashboard Limpio
- Menos clutter visual
- Fácil identificar la zona relevante

### 3. Gestión Automática
- No requiere intervención manual
- Se ejecuta en cada actualización (cada 30 segundos)

### 4. Respeta Estados Finales
- No toca zonas con TP alcanzado
- No toca zonas con SL alcanzado
- No modifica zonas ya descartadas manualmente

### 5. Trazabilidad Completa
- Motivo de cierre claro y específico
- Logs detallados en consola
- Timestamp de descarte registrado

## Lógica SMC Intacta

### ✅ NO se modificó:
- Detección de swings
- Detección de BOS/CHOCH
- Detección de FVG
- Detección de Order Blocks
- Detección de barridas
- Cálculo de score
- Cálculo de TP/SL (ratio 1:1, 1:2)
- Transiciones de estado (ACTIVA → EN_ZONA → PROFIT → TP)

### ✅ SOLO se agregó:
- Limpieza automática de zonas competidoras
- Criterio: proximidad al precio actual
- Aplicación: por símbolo (no global)

## Ejemplo Real de Ejecución

### T0: Detección Inicial
```
Symbol: Boom 1000 Index
Precio actual: 4530

Nueva zona detectada:
- ID: 100
- Zona: 4500-4550
- Estado: ACTIVA → EN_ZONA (precio dentro)
- Distancia: 0
```

### T1: Nueva Zona Detectada (Precio se movió)
```
Precio actual: 4680

Nueva zona detectada:
- ID: 101
- Zona: 4650-4700
- Estado: ACTIVA

Limpieza por proximidad:
  Zona 100: distancia = 130 ❌ DESCARTADA
  Zona 101: distancia = 20  ✅ MANTENIDA
  
Resultado: Solo Zona 101 activa
```

### T2: Precio Regresa
```
Precio actual: 4520

Zonas existentes:
- Zona 101: 4650-4700, distancia = 130
- Zona 100: DESCARTADA (no se reevalúa)

Nueva zona detectada:
- ID: 102
- Zona: 4500-4550
- Estado: ACTIVA → EN_ZONA

Limpieza por proximidad:
  Zona 101: distancia = 130 ❌ DESCARTADA
  Zona 102: distancia = 0   ✅ MANTENIDA
```

## Testing Recomendado

### Pruebas Manuales
1. ✅ Verificar que solo queda 1 zona activa por símbolo
2. ✅ Verificar que zonas TP/SL no se tocan
3. ✅ Verificar logs en consola del navegador
4. ✅ Verificar motivo_cierre en base de datos
5. ✅ Verificar comportamiento con precio dentro/fuera de zona

### Verificación en Supabase
```sql
-- Ver zonas descartadas por proximidad
SELECT 
    id,
    symbol,
    estado,
    fecha_cierre,
    motivo_cierre,
    zona_desde,
    zona_hasta
FROM smc_m15_setups
WHERE motivo_cierre LIKE '%menor proximidad%'
ORDER BY fecha_cierre DESC
LIMIT 20;
```

### Verificación de Estados Activos
```sql
-- Contar zonas vivas por símbolo
SELECT 
    symbol,
    COUNT(*) as zonas_vivas,
    STRING_AGG(estado, ', ') as estados
FROM smc_m15_setups
WHERE estado IN ('ACTIVA', 'EN_ZONA', 'PROFIT', 'ESPERANDO_ACOMODO')
GROUP BY symbol
ORDER BY zonas_vivas DESC;

-- Debe mostrar máximo 1 zona viva por símbolo
```

## Monitoreo

### Consola del Navegador
Buscar logs con los siguientes prefijos:
- `🔍 Limpieza por proximidad`: Inicio del proceso
- `✓ Zona más cercana`: Zona que se mantiene
- `❌ Descartando zona`: Zonas eliminadas
- `✅ Limpieza completada`: Resumen del proceso

### Supabase Dashboard
Monitorear tabla `smc_m15_setups`:
- Campo `estado`: Solo 1 zona en ACTIVA/EN_ZONA/PROFIT por símbolo
- Campo `motivo_cierre`: Verificar mensajes de proximidad
- Campo `fecha_cierre`: Timestamp de descarte

## Consideraciones Importantes

### ⚠️ Rendimiento
- La limpieza se ejecuta para CADA símbolo en CADA ciclo (30 segundos)
- Total: 10 símbolos × 1 limpieza = 10 consultas extra por ciclo
- Impacto: Mínimo (consultas son rápidas y filtradas por estado)

### ⚠️ Zonas TP en Proceso
Las zonas en estado `TP` (esperando alcanzar 1:2) **NO** se descartan:
- Siguen siendo monitoreadas
- Pueden ser liberadas cuando alcancen 1:2
- No compiten con nuevas zonas

### ⚠️ Empates en Distancia
Si dos zonas tienen la misma distancia:
- Se mantiene la más **reciente** (por `created_at.desc`)
- Esto favorece las señales más actuales

## Archivos Modificados

| Archivo | Líneas | Cambio |
|---------|--------|--------|
| `assets/app.js` | 363-378 | Nueva función `calculateDistanceToZone()` |
| `assets/app.js` | 380-445 | Nueva función `cleanupZonesByProximity()` |
| `assets/app.js` | 805 | Integración en `trackZoneHistory()` |

## Compatibilidad

### ✅ Compatible con:
- Sistema de estados existente
- Transiciones ACTIVA → EN_ZONA → PROFIT → TP
- Cálculo de max_reaccion_puntos
- Dashboard en vivo
- Historial SMC M15 PRO
- Filtros y estadísticas

### ✅ No afecta:
- Lógica de detección SMC
- Cálculos de TP/SL
- Zonas ya finalizadas (TP/SL)
- Base de datos existente

## Conclusión

La implementación de limpieza por proximidad mejora significativamente la claridad y usabilidad del sistema SMC M15 PRO, manteniendo solo las zonas más relevantes (cercanas al precio) y descartando automáticamente las competidoras, todo esto sin afectar la lógica core de Smart Money Concepts.

---

**Fecha de implementación:** 2026-05-04  
**Versión:** SMC M15 PRO v2.1 - Zone Proximity Cleanup
