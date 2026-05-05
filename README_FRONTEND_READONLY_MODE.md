# Frontend Read-Only Mode - BACKEND_PROCESSORS_ENABLED

## Resumen

Se ha añadido un flag `BACKEND_PROCESSORS_ENABLED` en `assets/app.js` para prevenir **doble escritura** cuando los procesadores backend están activos.

## Problema

Antes de esta implementación:
- ✅ Backend processors creados: escriben en las tablas
- ❌ Frontend aún procesa: también escribe en las tablas
- ❌ **CONFLICTO:** Dos procesos escribiendo simultáneamente

Consecuencia: Duplicación de zonas, inconsistencia de estados, condiciones de carrera.

## Solución

### Flag de Control

```javascript
// assets/app.js (línea ~77)
const BACKEND_PROCESSORS_ENABLED = true;
```

**Cuando `BACKEND_PROCESSORS_ENABLED = true`:**
- ✅ Frontend SOLO lee datos
- ✅ Frontend SOLO visualiza
- ❌ Frontend NO procesa SMC
- ❌ Frontend NO crea setups
- ❌ Frontend NO actualiza estados
- ❌ Frontend NO escribe en base de datos

## Funciones Protegidas

Todas las funciones de escritura tienen un guard al inicio:

### 1. `createSetup()`
```javascript
async function createSetup(setupData) {
    // GUARD: No escribir si backend processors están habilitados
    if (BACKEND_PROCESSORS_ENABLED) {
        console.log('⚠️ BACKEND_PROCESSORS_ENABLED: createSetup() deshabilitado - solo lectura');
        return null;
    }
    // ... resto del código
}
```

**Qué hace:** Impide crear nuevos setups desde el frontend.

### 2. `updateSetup()`
```javascript
async function updateSetup(id, updateData, explicitTable = null) {
    // GUARD: No escribir si backend processors están habilitados
    if (BACKEND_PROCESSORS_ENABLED) {
        console.log('⚠️ BACKEND_PROCESSORS_ENABLED: updateSetup() deshabilitado - solo lectura');
        return null;
    }
    // ... resto del código
}
```

**Qué hace:** Impide actualizar setups existentes desde el frontend.

**Nota:** `closeSetup()` también está protegido porque llama a `updateSetup()`.

### 3. `trackZoneHistory()`
```javascript
async function trackZoneHistory(symbol, analysis) {
    // GUARD: No procesar ni escribir si backend processors están habilitados
    if (BACKEND_PROCESSORS_ENABLED) {
        console.log(`⚠️ BACKEND_PROCESSORS_ENABLED: trackZoneHistory() deshabilitado para ${symbol} - solo lectura`);
        return;
    }
    // ... resto del código
}
```

**Qué hace:** Impide toda la lógica de procesamiento de zonas en el frontend.

### 4. `updateSetupState()`
```javascript
async function updateSetupState(setup, currentPrice, analysis = null) {
    // GUARD: No escribir si backend processors están habilitados
    if (BACKEND_PROCESSORS_ENABLED) {
        return false;
    }
    // ... resto del código
}
```

**Qué hace:** Impide actualizar estados de zonas (ACTIVA → EN_ZONA → PROFIT, etc.).

### 5. `reevaluatePausedZone()`
```javascript
async function reevaluatePausedZone(setup, currentPrice, analysis) {
    // GUARD: No escribir si backend processors están habilitados
    if (BACKEND_PROCESSORS_ENABLED) {
        return 'PAUSADA'; // Retornar sin cambios
    }
    // ... resto del código
}
```

**Qué hace:** Impide reevaluar zonas PAUSADA para cambiarlas a DESCARTADA o SL.

## Comportamiento del Frontend

### Con `BACKEND_PROCESSORS_ENABLED = true` (RECOMENDADO)

**Dashboard:**
- ✅ Fetch de datos desde Supabase
- ✅ Análisis SMC en memoria (para visualización)
- ✅ Mostrar zonas, scores, indicadores
- ✅ Actualización cada 60 segundos
- ❌ NO crear zonas en DB
- ❌ NO actualizar estados en DB

**Historial:**
- ✅ Leer setups desde tablas
- ✅ Mostrar historial completo
- ✅ Filtros y búsquedas
- ✅ Estadísticas TP/SL
- ❌ NO modificar registros

**Logs en consola:**
```
⚠️ BACKEND_PROCESSORS_ENABLED: trackZoneHistory() deshabilitado para Boom 1000 Index - solo lectura
⚠️ BACKEND_PROCESSORS_ENABLED: trackZoneHistory() deshabilitado para Crash 1000 Index - solo lectura
...
```

### Con `BACKEND_PROCESSORS_ENABLED = false` (LEGACY)

Vuelve al comportamiento anterior:
- Frontend procesa SMC
- Frontend crea y actualiza zonas
- Frontend escribe en base de datos

**⚠️ ADVERTENCIA:** Solo usar `false` si NO están corriendo los procesadores backend. De lo contrario, habrá doble escritura.

## Cómo Usar

### Escenario 1: Backend Processors Activos (PRODUCCIÓN)

```bash
# Terminal 1: Correr backend processors
python run_processors.py
```

```javascript
// assets/app.js
const BACKEND_PROCESSORS_ENABLED = true; // ← MANTENER EN TRUE
```

**Resultado:**
- Backend procesa cada 60s
- Frontend solo visualiza
- Sin duplicación ni conflictos

### Escenario 2: Solo Frontend (DESARROLLO/PRUEBAS)

```javascript
// assets/app.js
const BACKEND_PROCESSORS_ENABLED = false; // ← CAMBIAR A FALSE
```

**Resultado:**
- Frontend procesa y escribe
- Útil para desarrollo sin backend
- **NO usar en producción con backend activo**

## Verificación

### En Browser Console

Con `BACKEND_PROCESSORS_ENABLED = true`, deberías ver:

```
⚠️ BACKEND_PROCESSORS_ENABLED: trackZoneHistory() deshabilitado para Boom 1000 Index - solo lectura
⚠️ BACKEND_PROCESSORS_ENABLED: trackZoneHistory() deshabilitado para Boom 900 Index - solo lectura
...
```

### En Base de Datos

```sql
-- Verificar que solo backend escribe
-- Los created_at deben mostrar procesamiento continuo cada 60s
SELECT symbol, estado, fecha_detectada, updated_at
FROM public.smc_m15_setups
ORDER BY updated_at DESC
LIMIT 10;
```

Si `updated_at` se actualiza cada ~60 segundos → Backend funcionando ✅  
Si no hay actualizaciones → Verificar que `run_processors.py` está corriendo

## Ventajas

✅ **Previene doble escritura:** Solo una fuente de verdad (backend)  
✅ **Evita condiciones de carrera:** No hay competencia por escribir  
✅ **Mejor separación:** Frontend = visualización, Backend = procesamiento  
✅ **Fácil de cambiar:** Solo modificar un flag  
✅ **No elimina código:** Lógica vieja intacta, solo deshabilitada  
✅ **Reversible:** Cambiar flag vuelve al comportamiento anterior  

## Desventajas

⚠️ **Dependencia:** Frontend depende de backend para ver datos actualizados  
⚠️ **Debugging:** Frontend no puede crear zonas de prueba manualmente  
⚠️ **Configuración manual:** Hay que recordar cambiar el flag según entorno  

## Mejoras Futuras

### Detección Automática

En lugar de un flag estático, detectar automáticamente si backend está activo:

```javascript
// Futuro: Detectar automáticamente
async function checkBackendProcessorsActive() {
    // Verificar si hay actualizaciones recientes (últimos 2 minutos)
    const recentUpdates = await fetch(
        `${SUPABASE_URL}/rest/v1/smc_m15_setups?select=updated_at&order=updated_at.desc&limit=1`,
        { headers: {...} }
    );
    const data = await recentUpdates.json();
    if (data.length > 0) {
        const lastUpdate = new Date(data[0].updated_at);
        const now = new Date();
        const minutesAgo = (now - lastUpdate) / 1000 / 60;
        return minutesAgo < 2; // Backend activo si actualizó hace menos de 2 min
    }
    return false;
}
```

### Variable de Entorno

Configurar el flag desde `.env` o variable de entorno:

```javascript
// Futuro: Desde variable de entorno
const BACKEND_PROCESSORS_ENABLED = 
    typeof BACKEND_PROCESSORS !== 'undefined' 
    ? BACKEND_PROCESSORS 
    : true; // default true
```

## Troubleshooting

### Dashboard no muestra zonas nuevas

**Causa:** Backend processors no están corriendo.

**Solución:**
```bash
python run_processors.py
```

### Zonas duplicadas

**Causa:** `BACKEND_PROCESSORS_ENABLED = false` con backend activo.

**Solución:**
1. Cambiar flag a `true`
2. Limpiar duplicados en DB

### Frontend no procesa (esperado)

**Causa:** `BACKEND_PROCESSORS_ENABLED = true` (comportamiento correcto).

**Confirmación:** Logs en consola deben mostrar mensajes de "deshabilitado".

## Resumen

| Aspecto | ENABLED = true | ENABLED = false |
|---------|----------------|-----------------|
| Frontend procesa SMC | ❌ No | ✅ Sí |
| Frontend crea setups | ❌ No | ✅ Sí |
| Frontend actualiza estados | ❌ No | ✅ Sí |
| Frontend escribe DB | ❌ No | ✅ Sí |
| Requiere backend corriendo | ✅ Sí | ❌ No |
| Modo recomendado | ✅ Producción | ⚠️ Solo desarrollo |

## Conclusión

El flag `BACKEND_PROCESSORS_ENABLED = true` es **CRÍTICO** para evitar doble escritura cuando los procesadores backend están activos. Debe mantenerse en `true` en producción.

La lógica vieja del frontend NO se elimina, solo se desactiva. Esto permite:
- Reversibilidad fácil
- Debugging cuando sea necesario
- Transición gradual
- Rollback inmediato si hay problemas

🎯 **Objetivo logrado:** Frontend en modo read-only cuando backend está activo.
