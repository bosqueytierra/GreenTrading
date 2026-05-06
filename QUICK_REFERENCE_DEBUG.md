# Quick Reference: Data Mapping Debug

## 🎯 Objetivo
Identificar dónde se pierden las propiedades SMC (tendencias, eventos, zonas) entre backend y frontend render.

## ✅ Cambios Aplicados
- ✅ Puerto 8765 (arquitectura autónoma)
- ✅ Backend Python interno automático
- ✅ 12 puntos de logging diagnóstico
- ✅ Backend SMC NO tocado

## 🔍 Cómo Debuggear

### 1. Ejecutar App
```bash
cd GreenTrading-Desktop
npm start
```

### 2. Abrir DevTools
Presionar: **Ctrl+Shift+I** (Windows/Linux) o **Cmd+Option+I** (Mac)

### 3. Buscar en Consola

#### Buscar "🔍 BACKEND RESPONSE"
```
🔍 BACKEND RESPONSE - Number of items: 10
🔍 BACKEND RESPONSE - First item: {...}
```
**¿Qué verificar?**
- ✅ ¿Tiene 10 items?
- ✅ ¿First item tiene tendencia_h1, tendencia_m15, etc.?

#### Buscar "🔍 DEBUG 1"
```
🔍 DEBUG 1 - RESULT OBJECT: { success: true, data: [...] }
```
**¿Qué verificar?**
- ✅ ¿success es true?
- ✅ ¿data es un array?

#### Buscar "🔍 DEBUG 2"
```
🔍 DEBUG 2 - RESULT.DATA: [...]
```
**¿Qué verificar?**
- ✅ ¿Es un array de 10 objetos?
- ❌ ¿Es un objeto con propiedad "data"? → **PROBLEMA: Anidamiento extra**

#### Buscar "🔍 DEBUG 3"
```
🔍 DEBUG 3 - SNAPSHOTS ARRAY: [...]
```
**¿Qué verificar?**
- ✅ ¿Tiene 10 objetos?
- ✅ ¿Cada objeto tiene tendencia_h1, tendencia_m15, etc.?

#### Buscar "🔍 DEBUG 6"
```
🔍 DEBUG 6 - SNAPSHOT OBJECT IN createTableRow: {...}
```
**¿Qué verificar?**
- ✅ ¿Tiene symbol, price?
- ❌ ¿NO tiene tendencia_h1, tendencia_m15? → **PROBLEMA: Propiedades perdidas**

#### Buscar "🔍 DEBUG 7" a "🔍 DEBUG 12"
```
🔍 DEBUG 7 - snapshot.tendencia_h1: "ALCISTA"
🔍 DEBUG 8 - snapshot.tendencia_m15: "ALCISTA"
🔍 DEBUG 9 - snapshot.ultimo_evento_m15: "BOS-ALCISTA"
🔍 DEBUG 10 - snapshot.zona_madre_m15: { desde: 123, hasta: 125 }
🔍 DEBUG 11 - snapshot.score: 7
🔍 DEBUG 12 - snapshot.price: 12345.67
```
**¿Qué verificar?**
- ✅ ¿Todos tienen valores?
- ❌ ¿Algunos son undefined? → **PROBLEMA: Propiedades específicas faltantes**

## 🚨 Escenarios Comunes

### Escenario A: DEBUG 2 muestra `{ data: [...] }`
**Problema:** Anidamiento extra  
**Solución:** En `dashboard.js` línea ~56, cambiar:
```javascript
const snapshots = result.data.data;  // En lugar de result.data
```

### Escenario B: DEBUG 6 muestra objeto sin tendencia_h1
**Problema:** Propiedades perdidas en filter/iteration  
**Verificar:** DEBUG 4 y DEBUG 5 para ver si las propiedades existen ahí  
**Posible causa:** El `.filter()` está creando nuevos objetos sin copiar todas las propiedades

### Escenario C: DEBUG 7-11 muestran undefined, pero DEBUG 12 (price) funciona
**Problema:** Propiedades específicas no llegan desde backend  
**Pero:** El problema dice que backend funciona, así que revisar transformación intermedia

### Escenario D: DEBUG 7-11 muestran valores, pero UI muestra "--"
**Problema:** Rendering o CSS  
**Verificar:** Inspeccionar elemento HTML en DevTools para ver si el valor está en el DOM

## 📋 Reporte al Desarrollador

Copia y pega los valores de estos logs:

```
REPORTE DEBUG:

🔍 BACKEND RESPONSE - Number of items: [VALOR AQUÍ]
🔍 BACKEND RESPONSE - First item: [COPIAR OBJETO COMPLETO]

🔍 DEBUG 2 - RESULT.DATA: [¿Es array o tiene .data?]
🔍 DEBUG 3 - SNAPSHOTS ARRAY: [¿Cuántos items?]

🔍 DEBUG 6 - SNAPSHOT (primer Boom): [COPIAR OBJETO]
🔍 DEBUG 7 - tendencia_h1: [VALOR]
🔍 DEBUG 8 - tendencia_m15: [VALOR]
🔍 DEBUG 9 - ultimo_evento_m15: [VALOR]
🔍 DEBUG 10 - zona_madre_m15: [VALOR]
🔍 DEBUG 11 - score: [VALOR]
🔍 DEBUG 12 - price: [VALOR]
```

## 📚 Documentos Completos

- `DIAGNOSTICO_DATA_MAPPING.md` - Guía detallada con 5 escenarios
- `RESUMEN_CORRECCION_DATA_MAPPING.md` - Resumen de cambios y approach

## ⚡ Quick Fix Candidates

Según experiencia común, el problema probablemente es uno de estos:

### 1. Anidamiento extra (más probable)
```javascript
// En dashboard.js, loadDashboardData()
// Cambiar línea ~56:
const snapshots = result.data;
// Por:
const snapshots = result.data.data;  // Si DEBUG 2 muestra anidamiento
```

### 2. Nombres en camelCase
```javascript
// En dashboard.js, createTableRow()
// Cambiar línea ~130:
const {
  symbol,
  price,
  tendencia_h1,
  // ...
} = snapshot;
// Por:
const {
  symbol,
  price,
  tendenciaH1: tendencia_h1,  // Si backend usa camelCase
  tendenciaM15: tendencia_m15,
  // ...
} = snapshot;
```

### 3. Filter destructivo
```javascript
// En dashboard.js, loadDashboardData()
// Líneas ~64-65, si filter está alterando objetos:
const boomData = snapshots.filter(s => s.symbol.includes('Boom'));
// Asegurar que mantiene todas las propiedades (debería, pero verificar)
```

## 🎬 Próximos Pasos

1. ✅ Ejecutar app
2. ✅ Revisar consola
3. ✅ Identificar escenario
4. ✅ Reportar findings
5. ⏳ Aplicar fix específico
6. ⏳ Limpiar console.logs
7. ⏳ Commit final

---

**Recuerda:** Los logs no mienten. Van a revelar exactamente dónde está el problema.
