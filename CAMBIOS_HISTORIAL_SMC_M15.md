# Cambios Implementados - Historial SMC M15 PRO

## Fecha: 2026-05-04

## Resumen
Se ajustó el **Historial SMC M15 PRO** para usar correctamente las columnas de la tabla `public.smc_m15_setups` y se eliminó la columna "Dirección" del Dashboard y del Historial.

---

## Cambios Realizados

### 1. ✅ Actualización de Campos Guardados en Supabase

**Archivo:** `assets/app.js` - Función `trackZoneHistory()`

#### Nuevos Setups (Creación)
Al crear un nuevo setup en `public.smc_m15_setups`, ahora se guardan:
- `tendencia_h1`: Tomada desde `analysis.smc.tendenciaH1`
- `tendencia_m15`: Tomada desde `analysis.smc.tendenciaM15`
- `evento`: Último evento M15 (antes se llamaba `ultimo_evento_m15`)

**Eliminado:**
- Campo `ultimo_evento_m15` (redundante, ahora se usa `evento`)

#### Setups Existentes (Actualización)
Cuando un setup está ACTIVA/EN_ZONA/PROFIT/TP y se actualiza:
- Se actualizan `tendencia_h1` y `tendencia_m15` **solo si están vacíos/null**
- Esto permite completar los datos faltantes en registros antiguos
- Se mantiene `evento` actualizado con el último evento M15

---

### 2. ✅ Lectura Correcta en el Historial

**Archivo:** `assets/app.js` - Función `createHistoryRow()`

El historial ahora lee correctamente:
- **Tendencia H1** → `setup.tendencia_h1` (muestra "--" si es null/vacío)
- **Tendencia M15** → `setup.tendencia_m15` (muestra "--" si es null/vacío)
- **Último Evento M15** → `setup.evento` (en lugar de `ultimo_evento_m15`)

---

### 3. ✅ Eliminación de Columna "Dirección"

**Archivos modificados:**
- `index.html`: Eliminados filtros de "Dirección" del HTML
- `assets/app.js`: Eliminada lógica de filtro por dirección

**Razón:**
- Boom siempre se trabaja como entrada ALCISTA
- Crash siempre se trabaja como entrada BAJISTA
- La columna `direccion` sigue existiendo en la base de datos para lógica interna, pero ya no se muestra ni filtra en la UI

---

## Estructura de Columnas en Historial

El historial ahora muestra estas columnas en este orden:

1. **Fecha** - `setup.created_at`
2. **Índice** - `setup.symbol`
3. **Tendencia H1** - `setup.tendencia_h1` (o "--")
4. **Tendencia M15** - `setup.tendencia_m15` (o "--")
5. **Último Evento M15** - `setup.evento` (o "--")
6. **Zona** - `setup.zona_desde` - `setup.zona_hasta`
7. **TP** - `setup.tp_price`
8. **SL** - `setup.sl_price`
9. **Score** - `setup.score`
10. **OB** - `setup.ob` (SÍ/NO)
11. **FVG** - `setup.fvg` (SÍ/NO)
12. **Barrida** - `setup.barrida` (SÍ/NO)
13. **Estado** - `setup.estado`
14. **Resultado (pts)** - `setup.resultado_puntos`
15. **Max Reacción (pts)** - `setup.max_reaccion_puntos`

---

## Filtros Disponibles en Historial

Ahora solo hay **2 grupos de filtros**:

### 1. Filtro por Símbolo
- Todos
- Boom 1000, 900, 600, 500, 300
- Crash 1000, 900, 600, 500, 300

### 2. Filtro por Estado
- Todos
- ACTIVA
- EN ZONA
- PROFIT
- TP
- SL
- DESCARTADA

**Eliminado:** Filtro por Dirección (ALCISTA/BAJISTA)

---

## Comportamiento con Registros Antiguos

### Registros Antiguos (antes de este cambio)
- Si `tendencia_h1` o `tendencia_m15` son **null/vacíos** → Se muestra "**--**"
- Esto es **correcto** y esperado para registros históricos

### Registros Nuevos (después de este cambio)
- `tendencia_h1` y `tendencia_m15` **SIEMPRE** se guardan con valores del Dashboard en vivo
- No deben quedar como "--" a menos que genuinamente no haya datos de tendencia

### Registros Vivos en Actualización
- Si un setup está en estado **ACTIVA**, **EN_ZONA**, **PROFIT** o **TP** (no liberado)
- Y tiene `tendencia_h1` o `tendencia_m15` vacíos
- Al refrescar, se intentará completar con los datos actuales del análisis SMC

---

## Migración Requerida en Supabase

**IMPORTANTE:** Antes de usar estos cambios, debes agregar las columnas en Supabase:

```sql
ALTER TABLE public.smc_m15_setups 
ADD COLUMN IF NOT EXISTS tendencia_h1 text,
ADD COLUMN IF NOT EXISTS tendencia_m15 text;
```

**Nota:** La columna `evento` ya existe en la tabla.

---

## Lógica SMC Intacta

✅ No se tocaron estos componentes:
- Detección de zonas
- Cálculo de eventos (BOS/CHOCH)
- Cálculo de Score
- Detección de OB (Order Block)
- Detección de FVG (Fair Value Gap)
- Detección de Barrida
- Cálculo de TP/SL
- Estados y transiciones
- Cálculo de resultado
- Cálculo de max reacción

---

## URL de Consulta

El historial sigue consultando desde:
```
https://rqjmndaqxxgljpubnfkg.supabase.co/rest/v1/smc_m15_setups?order=created_at.desc&limit=50
```

---

## Testing Recomendado

1. ✅ Verificar que nuevos setups se creen con `tendencia_h1` y `tendencia_m15` poblados
2. ✅ Verificar que el historial muestre "--" para registros antiguos sin tendencias
3. ✅ Verificar que setups en vivo actualicen tendencias si están vacías
4. ✅ Verificar que la columna "Último Evento M15" lea desde `evento`
5. ✅ Verificar que no haya errores por falta de columna `ultimo_evento_m15`
6. ✅ Verificar que los filtros de "Dirección" ya no aparezcan
7. ✅ Verificar que los filtros por Símbolo y Estado funcionen correctamente

---

## Archivos Modificados

1. `assets/app.js`
   - Función `trackZoneHistory()` - líneas 614-640 (update) y 674-700 (create)
   - Función `createHistoryRow()` - línea 2117
   - Función `initializeHistoryFilters()` - eliminado filtro dirección
   - Función `applyFilters()` - eliminada lógica de filtro dirección
   - Variables globales `currentFilters` - eliminado campo dirección

2. `index.html`
   - Sección de filtros del historial - eliminado grupo de filtros "Dirección"

---

## Mantenimiento Futuro

- La columna `direccion` **sigue existiendo** en la base de datos para lógica interna
- **NO eliminar** la columna `direccion` de Supabase
- Solo se eliminó su visualización y filtrado en la interfaz de usuario
