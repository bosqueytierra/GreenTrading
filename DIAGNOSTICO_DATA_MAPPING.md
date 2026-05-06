# Diagnóstico: Data Mapping Frontend

## Problema
El backend Electron interno (puerto 8765) funciona correctamente:
- ✅ Análisis SMC ejecutándose
- ✅ Zonas detectadas
- ✅ Scores detectados
- ✅ Estados ACTIVOS
- ✅ Datos MT5 reales

El frontend SÍ muestra:
- ✅ Precios
- ✅ Timestamps
- ✅ Conexión MT5

El frontend NO muestra:
- ❌ Tendencias (tendencia_h1, tendencia_m15)
- ❌ Eventos (ultimo_evento_m15)
- ❌ Zonas (zona_madre_m15)

## Hipótesis
El problema es de ESTRUCTURA DE DATOS o MAPPING, no de conexión.

## Logging Agregado

### En main.js (IPC Handler)
```javascript
console.log('🔍 BACKEND RESPONSE - Number of items:', data.length);
console.log('🔍 BACKEND RESPONSE - First item:', data[0]);
```

### En dashboard.js (loadDashboardData)
```javascript
console.log('🔍 DEBUG 1 - RESULT OBJECT:', result);
console.log('🔍 DEBUG 2 - RESULT.DATA:', result.data);
console.log('🔍 DEBUG 3 - SNAPSHOTS ARRAY:', snapshots);
console.log('🔍 DEBUG 4 - BOOM DATA:', boomData);
console.log('🔍 DEBUG 5 - CRASH DATA:', crashData);
```

### En dashboard.js (createTableRow)
```javascript
console.log('🔍 DEBUG 6 - SNAPSHOT OBJECT IN createTableRow:', snapshot);
console.log('🔍 DEBUG 7 - snapshot.tendencia_h1:', snapshot.tendencia_h1);
console.log('🔍 DEBUG 8 - snapshot.tendencia_m15:', snapshot.tendencia_m15);
console.log('🔍 DEBUG 9 - snapshot.ultimo_evento_m15:', snapshot.ultimo_evento_m15);
console.log('🔍 DEBUG 10 - snapshot.zona_madre_m15:', snapshot.zona_madre_m15);
console.log('🔍 DEBUG 11 - snapshot.score:', snapshot.score);
console.log('🔍 DEBUG 12 - snapshot.price:', snapshot.price);
```

## Qué Buscar en la Consola

### Escenario 1: Data anidado incorrectamente
Si ves:
```javascript
DEBUG 2 - RESULT.DATA: { data: [...] }  // Anidado extra!
```

Entonces el problema es que `result.data` contiene OTRO objeto con propiedad `data`.

**Solución:** Cambiar en `loadDashboardData()`:
```javascript
const snapshots = result.data.data;  // En lugar de result.data
```

### Escenario 2: Array vacío o undefined
Si ves:
```javascript
DEBUG 3 - SNAPSHOTS ARRAY: undefined
// o
DEBUG 3 - SNAPSHOTS ARRAY: []
```

Entonces `result.data` no contiene lo esperado.

**Revisar:** El valor de `DEBUG 1` y `DEBUG 2` para ver la estructura real.

### Escenario 3: Snapshot llega vacío al render
Si ves:
```javascript
DEBUG 6 - SNAPSHOT OBJECT: { symbol: "Boom 1000", price: 123.45 }
DEBUG 7 - snapshot.tendencia_h1: undefined
DEBUG 8 - snapshot.tendencia_m15: undefined
```

Entonces el objeto `snapshot` SÍ llega pero sin las propiedades SMC.

**Posibles causas:**
- El backend devuelve estructura diferente
- Hay un paso intermedio que filtra/transforma los datos
- El filter en `boomData/crashData` está alterando los objetos

### Escenario 4: Propiedades existen pero con nombres diferentes
Si ves:
```javascript
DEBUG 6 - SNAPSHOT OBJECT: {
  symbol: "Boom 1000",
  price: 123.45,
  tendenciaH1: "ALCISTA",    // camelCase!
  tendenciaM15: "ALCISTA",
  ...
}
```

Entonces el backend está enviando nombres en camelCase, no snake_case.

**Solución:** Ajustar el destructuring en `createTableRow()` o mapear las propiedades.

### Escenario 5: Todo existe en DEBUG 6 pero no se renderiza
Si ves:
```javascript
DEBUG 6 - SNAPSHOT OBJECT: {
  symbol: "Boom 1000",
  price: 123.45,
  tendencia_h1: "ALCISTA",
  tendencia_m15: "ALCISTA",
  ultimo_evento_m15: "BOS-ALCISTA",
  zona_madre_m15: { desde: 123.00, hasta: 125.00 },
  score: 7
}
DEBUG 7 - snapshot.tendencia_h1: "ALCISTA"
DEBUG 8 - snapshot.tendencia_m15: "ALCISTA"
```

Pero la UI muestra `--`, entonces el problema está en el RENDER, no en los datos.

**Posibles causas:**
- CSS ocultando los valores
- HTML mal formado
- Template string con error
- Valores siendo sobreescritos después del render

## Pasos de Diagnóstico

1. **Abrir DevTools** (Ctrl+Shift+I) en Electron
2. **Refrescar el dashboard** (botón refresh o automático)
3. **Buscar en consola:**
   - `🔍 BACKEND RESPONSE` - Ver estructura desde backend
   - `🔍 DEBUG 1` a `🔍 DEBUG 5` - Ver flujo de datos
   - `🔍 DEBUG 6` a `🔍 DEBUG 12` - Ver cada snapshot en render
4. **Comparar:**
   - ¿`DEBUG 12` (price) tiene valor? → SÍ (sabemos que precios funcionan)
   - ¿`DEBUG 7` (tendencia_h1) tiene valor? → Verificar
   - ¿`DEBUG 8` (tendencia_m15) tiene valor? → Verificar
5. **Identificar dónde se pierde la data:**
   - Si está en BACKEND RESPONSE pero no en DEBUG 3 → Problema en IPC o result.data
   - Si está en DEBUG 3 pero no en DEBUG 4/5 → Problema en filter
   - Si está en DEBUG 4/5 pero no en DEBUG 6 → Problema en iteration
   - Si está en DEBUG 6 pero no se renderiza → Problema en HTML/CSS

## Acciones Según Resultado

### Si falta nesting:
```javascript
// En loadDashboardData(), cambiar:
const snapshots = result.data;
// Por:
const snapshots = result.data.data;  // o lo que muestre DEBUG 2
```

### Si nombres diferentes:
```javascript
// En createTableRow(), mapear:
const {
  symbol,
  price,
  tendenciaH1: tendencia_h1,  // Renombrar
  tendenciaM15: tendencia_m15,
  // ...
} = snapshot;
```

### Si propiedades no llegan:
Verificar backend - pero el problema dice que backend funciona, así que revisar:
- ¿Hay middleware que transforma los datos?
- ¿Hay algún .map() o .filter() que modifica el array?

### Si todo llega pero no se renderiza:
- Inspeccionar elemento HTML en DevTools
- Ver si el valor está en el DOM pero invisible
- Verificar que los spans se están creando correctamente

## Resultado Esperado

Cuando esté funcionando correctamente, deberías ver:

```javascript
🔍 BACKEND RESPONSE - Number of items: 10
🔍 BACKEND RESPONSE - First item: {
  symbol: "Boom 1000 Index",
  price: 12345.67,
  tendencia_h1: "ALCISTA",
  tendencia_m15: "ALCISTA",
  ultimo_evento_m15: "BOS-ALCISTA",
  zona_madre_m15: { desde: 12300.00, hasta: 12320.00 },
  score: 7,
  ob: "SÍ",
  fvg: "SÍ",
  barrida: "NO",
  estado: "ACTIVA",
  updated_at: "2026-05-06T06:00:00Z"
}

🔍 DEBUG 1 - RESULT OBJECT: { success: true, data: [...] }
🔍 DEBUG 2 - RESULT.DATA: [Array de 10 objetos con todas las propiedades]
🔍 DEBUG 3 - SNAPSHOTS ARRAY: [Mismo array]
🔍 DEBUG 4 - BOOM DATA: [5 objetos Boom con todas las propiedades]
🔍 DEBUG 5 - CRASH DATA: [5 objetos Crash con todas las propiedades]

🔍 DEBUG 6 - SNAPSHOT OBJECT IN createTableRow: {objeto completo}
🔍 DEBUG 7 - snapshot.tendencia_h1: "ALCISTA"
🔍 DEBUG 8 - snapshot.tendencia_m15: "ALCISTA"
🔍 DEBUG 9 - snapshot.ultimo_evento_m15: "BOS-ALCISTA"
🔍 DEBUG 10 - snapshot.zona_madre_m15: { desde: 12300, hasta: 12320 }
🔍 DEBUG 11 - snapshot.score: 7
🔍 DEBUG 12 - snapshot.price: 12345.67
```

Y en la UI deberías ver:
- Tendencias: "ALCISTA" / "BAJISTA" (no "--")
- Eventos: "BOS-ALCISTA", "CHOCH-BAJISTA", etc. (no "--")
- Zonas: "12300.00 - 12320.00" (no "--")
- Scores: 7, 8, etc. (no 0)

## Limpieza Posterior

Una vez identificado y corregido el problema, eliminar los console.log de DEBUG 1-12 para limpiar la consola.
