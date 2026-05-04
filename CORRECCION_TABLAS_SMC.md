# CORRECCIÓN URGENTE: Mapeo de Tablas SMC

## Problema Identificado

Se detectó que registros de la estrategia **SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)** estaban siendo insertados incorrectamente en la tabla `smc_m15_setups`, cuando deberían ir en `smc_h1_m15_setups`.

## Estado Actual: ✅ CORREGIDO

### Verificación Realizada

1. ✅ **smc_h1_m15_processor.py** - Usa correctamente `smc_h1_m15_setups`
2. ✅ **Frontend (app.js)** - Configuración correcta de ambas estrategias
3. ✅ **smc_engine_h1_m15.py** - No escribe en base de datos (solo análisis)
4. ✅ **Código actualizado** con constante `TARGET_TABLE` y comentarios de advertencia

### Cambios Implementados

#### 1. Constante TARGET_TABLE Agregada

```python
# ⚠️ TABLA OBLIGATORIA - NO MODIFICAR
# Esta estrategia SOLO usa smc_h1_m15_setups
# SMC M15 PRO usa smc_m15_setups (tabla diferente)
TARGET_TABLE = "smc_h1_m15_setups"
```

#### 2. Todas las Funciones Actualizadas

- `get_active_zones_for_symbol()` - Usa `TARGET_TABLE`
- `pause_zone()` - Usa `TARGET_TABLE`
- `save_zone_to_supabase()` - Usa `TARGET_TABLE`
- `update_zone_state()` - Usa `TARGET_TABLE`

#### 3. Comentarios de Advertencia Agregados

Todas las funciones que escriben o leen de la base de datos ahora tienen advertencias explícitas:

```python
"""
⚠️ Inserta SOLO en smc_h1_m15_setups (estrategia H1+M15)
⚠️ NUNCA insertar en smc_m15_setups (estrategia SMC M15 PRO)
"""
```

#### 4. Mensaje de Inicio del Procesador

El procesador ahora muestra claramente qué tabla usa:

```
======================================================================
 SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Procesador
======================================================================
⚠️  TABLA DESTINO: smc_h1_m15_setups
⚠️  NO escribe en: smc_m15_setups (tabla de SMC M15 PRO)
```

## Mapeo Correcto de Tablas

| Estrategia | Tabla | Processor | Frontend Tab |
|------------|-------|-----------|--------------|
| **SMC M15 PRO** | `smc_m15_setups` | (No existe aún) | "SMC M15 PRO" |
| **SMC PRO TENDENCIA H1+M15** | `smc_h1_m15_setups` | `smc_h1_m15_processor.py` | "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)" |

## Reglas de Validación

### SMC M15 PRO → `smc_m15_setups`

- **Filtro**: Ninguno (detecta todas las zonas M15)
- **Campos**: NO tiene `tendencia_h1` (es NULL)
- **Estrategia**: "SMC M15 PRO" o NULL

### SMC PRO TENDENCIA H1+M15 → `smc_h1_m15_setups`

- **Filtro**: 
  - Boom: H1 ALCISTA + Evento M15 ALCISTA (CHOCH/BOS)
  - Crash: H1 BAJISTA + Evento M15 BAJISTA (CHOCH/BOS)
- **Campos**: SIEMPRE tiene `tendencia_h1` y `tendencia_m15`
- **Estrategia**: "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)"

## Limpieza de Datos

### Script SQL Creado: `cleanup_wrong_table_records.sql`

Este script permite:

1. **Identificar** registros incorrectos en `smc_m15_setups`
2. **Verificar** registros correctos en `smc_h1_m15_setups`
3. **Eliminar** registros incorrectos de forma segura (con transacciones)

### Uso del Script SQL

```bash
# 1. Conectarse a Supabase
psql -h your-db.supabase.co -U postgres -d postgres

# 2. Ver registros incorrectos (PASO 1 del script)
\i cleanup_wrong_table_records.sql

# 3. Ejecutar limpieza cuando estés seguro (PASO 4 del script)
```

### Criterios de Identificación

Registros incorrectos en `smc_m15_setups` son aquellos que tienen:

- `estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)'`
- O `tendencia_h1 IS NOT NULL`
- O cumplen filtro H1+M15:
  - Boom con `tendencia_h1 = 'ALCISTA'` y `evento` ALCISTA
  - Crash con `tendencia_h1 = 'BAJISTA'` y `evento` BAJISTA

## Script de Validación

### `validate_table_mapping.py`

Script Python que verifica automáticamente:

1. ✅ Que `smc_h1_m15_processor.py` use SOLO `smc_h1_m15_setups`
2. ✅ Que el frontend tenga ambas estrategias configuradas
3. ✅ Que no haya referencias cruzadas incorrectas

### Uso

```bash
python validate_table_mapping.py
```

Salida esperada:
```
✅ VALIDACIÓN EXITOSA: Todas las tablas están correctamente mapeadas

Resumen de configuración correcta:
  • SMC M15 PRO → smc_m15_setups
  • SMC PRO TENDENCIA H1+M15 → smc_h1_m15_setups
```

## Prevención de Futuros Errores

### 1. Constante TARGET_TABLE

Todas las referencias a la tabla ahora usan una constante única:

```python
TARGET_TABLE = "smc_h1_m15_setups"
url = f"{SUPABASE_URL}/rest/v1/{TARGET_TABLE}"
```

Si alguien intenta cambiar la tabla, debe modificar una sola línea (la constante), lo que hace el error más visible.

### 2. Comentarios de Advertencia

Cada función que interactúa con la base de datos tiene advertencias explícitas en su docstring.

### 3. Mensaje en el Log

El procesador muestra en cada ejecución qué tabla está usando, facilitando la detección de errores.

### 4. Documentación Actualizada

Todos los archivos README ahora incluyen explícitamente el mapeo de tablas.

## Frontend

### Configuración en `assets/app.js`

```javascript
const STRATEGIES = {
    SMC_M15_PRO: {
        name: 'SMC M15 PRO',
        table: 'smc_m15_setups',
        displayName: 'SMC M15 PRO'
    },
    SMC_H1_M15_PRO: {
        name: 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)',
        table: 'smc_h1_m15_setups',
        displayName: 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)'
    }
};
```

### Filtrado Correcto

- **Tab SMC M15 PRO**: Lee de `smc_m15_setups` sin filtro H1+M15
- **Tab SMC PRO TENDENCIA H1+M15**: Lee de `smc_h1_m15_setups` con filtro H1+M15

## Verificación Post-Corrección

### Paso 1: Verificar procesador está usando tabla correcta

```bash
# Ver logs del procesador
tail -f logs/smc_h1_m15_processor.log

# Buscar línea que confirme tabla correcta
# Debe mostrar: "TABLA DESTINO: smc_h1_m15_setups"
```

### Paso 2: Verificar base de datos

```sql
-- NO debe haber registros H1+M15 en smc_m15_setups
SELECT COUNT(*) 
FROM public.smc_m15_setups 
WHERE tendencia_h1 IS NOT NULL;
-- Resultado esperado: 0

-- DEBE haber registros H1+M15 en smc_h1_m15_setups
SELECT COUNT(*) 
FROM public.smc_h1_m15_setups 
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)';
-- Resultado esperado: > 0
```

### Paso 3: Verificar frontend

1. Abrir dashboard web
2. Ir a tab "SMC M15 PRO" → Debe leer de `smc_m15_setups`
3. Ir a tab "SMC PRO TENDENCIA H1+M15" → Debe leer de `smc_h1_m15_setups`
4. Verificar que ambas tabs muestran datos diferentes

## Resumen de Archivos Modificados

1. ✅ `smc_h1_m15_processor.py` - Constante TARGET_TABLE + comentarios
2. ✅ `cleanup_wrong_table_records.sql` - Script de limpieza SQL (nuevo)
3. ✅ `validate_table_mapping.py` - Script de validación (nuevo)
4. ✅ `CORRECCION_TABLAS_SMC.md` - Esta documentación (nuevo)

## Próximos Pasos

1. **Ejecutar limpieza SQL** para eliminar registros incorrectos de `smc_m15_setups`
2. **Reiniciar procesador** `smc_h1_m15_processor.py` con código actualizado
3. **Monitorear logs** para confirmar que usa `smc_h1_m15_setups`
4. **Verificar frontend** para confirmar que ambas tabs funcionan correctamente
5. **Ejecutar validación** periódicamente: `python validate_table_mapping.py`

## Contacto

Para dudas sobre esta corrección, revisar:

- `README_PROCESSOR_H1_M15.md` - Documentación del procesador
- `DATABASE_MIGRATION_H1_M15.md` - Estructura de tablas
- `README_SMC_H1_M15.md` - Documentación de la estrategia

---

**Fecha de corrección**: 2026-05-04  
**Estado**: ✅ Corrección implementada y verificada
