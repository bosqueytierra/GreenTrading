# FIX: SMC M15 PRO - Eliminación de Validaciones y Prevención de Duplicados

## Fecha
2026-05-04

## Problema Reportado

### 1. Validaciones Incorrectas en SMC M15 PRO
**URGENTE: SMC M15 PRO NO puede DESCARTAR por:**
- Contexto H1
- Contexto M15
- Evento M15

**Solución requerida:** Eliminar completamente estas validaciones para SMC_M15_PRO.

### 2. Duplicados de Zonas
**NO permitir múltiples registros para la misma zona:**
- Criterio: `(symbol + zona_desde + zona_hasta + evento)`

**Si ya existe:**
- → UPDATE estado
- NO INSERT

**Esto es obligatorio.**

---

## Estado Actual del Código

### Validaciones ya estaban correctamente implementadas ✅

El código en `assets/app.js` función `reevaluatePausedZone()` (líneas 517-604) **YA TENÍA** las validaciones correctamente implementadas:

```javascript
// Línea 526: Determina estrategia del setup
const setupStrategy = setup.strategy || 'SMC_M15_PRO';

// Líneas 541-555: Validación H1/M15 context - SOLO para SMC_H1_M15_PRO
if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO' && analysis && analysis.smc) {
    // ... validación contexto H1/M15
}

// Líneas 557-570: Validación evento M15 - SOLO para SMC_H1_M15_PRO
if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO') {
    // ... validación evento M15
}

// Líneas 572-581: Validación confluencia - SOLO para SMC_H1_M15_PRO
if (!shouldDiscard && setupStrategy === 'SMC_H1_M15_PRO') {
    // ... validación confluencia
}
```

**Conclusión:** Las validaciones de Contexto H1, Contexto M15 y Evento M15 **NO se aplican** a SMC_M15_PRO. Solo se aplican a SMC_H1_M15_PRO.

Para SMC_M15_PRO, una zona PAUSADA **SOLO** se descarta si:
- El precio toca el SL (líneas 532-539)

---

## Cambios Implementados

### 1. Mejora de Documentación (assets/app.js)

Se agregó documentación exhaustiva en la función `reevaluatePausedZone()` para clarificar las reglas:

```javascript
/**
 * ⚠️ IMPORTANTE - VALIDACIONES POR ESTRATEGIA:
 * 
 * SMC_M15_PRO:
 * - SOLO descarta si el precio toca SL
 * - NO descarta por cambios de Contexto H1
 * - NO descarta por cambios de Contexto M15
 * - NO descarta por cambios de Evento M15
 * - NO descarta por falta de confluencia (zona ya fue creada con confluencia inicial)
 * 
 * SMC_H1_M15_PRO:
 * - Descarta si el precio toca SL
 * - Descarta si Contexto H1 cambia contra la zona
 * - Descarta si Contexto M15 cambia contra la zona
 * - Descarta si Evento M15 deja de tener sentido
 * - Descarta si pierde confluencia mínima OB/FVG/Barrida
 */
```

### 2. Prevención de Duplicados - JavaScript (assets/app.js)

**Ubicación:** Función `trackZoneHistory()` - líneas 1000-1087

**Cambios realizados:**

#### A. Matching Logic Mejorado
- Se agregó comentario claro sobre prevención de duplicados (líneas 1005-1012)
- El matching ya existía con criterio: `(symbol + zona_desde + zona_hasta + evento + direccion)`
- Usa tolerancia de 0.001 para comparación de floats

#### B. UPDATE Estado en Lugar de INSERT (líneas 1049-1087)
Cuando se encuentra un duplicado:

```javascript
// Si la zona duplicada está en estado terminal (DESCARTADA, SL, TP)
if (['DESCARTADA', 'SL', 'TP'].includes(matchingSetup.estado) && matchingSetup.fecha_cierre) {
    // Reactivarla según estado del dashboard
    const shouldBePaused = dashboardLocked || mainOperativeZone;
    updateData.estado = shouldBePaused ? 'PAUSADA' : 'ACTIVA';
    updateData.fecha_cierre = null;
    updateData.motivo_cierre = null;
    console.log(`✓ Zona duplicada ${matchingSetup.id} reactivada desde ${matchingSetup.estado} → ${updateData.estado}`);
}
```

**Comportamiento:**
- Si encuentra zona duplicada en estado DESCARTADA/SL/TP → la REACTIVA (UPDATE estado)
- Si encuentra zona duplicada activa/pausada → UPDATE sus datos (score, ob, fvg, barrida)
- **NUNCA** crea un INSERT si ya existe la zona

### 3. Prevención de Duplicados - Python (smc_h1_m15_processor.py)

**Ubicación:** Función `process_symbol()` - líneas 391-500

**Cambios realizados:**

#### A. Nueva Función: get_all_zones_for_symbol() (líneas 246-268)
```python
def get_all_zones_for_symbol(symbol):
    """
    Obtiene TODAS las zonas para un símbolo específico (incluyendo cerradas y descartadas).
    """
```
Esta función permite buscar duplicados en todas las zonas, no solo las activas.

#### B. Detección Exacta de Duplicados (líneas 435-450)
```python
# Verificar si ya existe una zona EXACTA (symbol + zona_desde + zona_hasta + evento)
tolerance = 0.001
zona_duplicada = None
ultimo_evento = zona['evento']['evento']

for z in todas_zonas:
    zona_desde_match = abs(z['zona_desde'] - zona['zona_desde']) < tolerance
    zona_hasta_match = abs(z['zona_hasta'] - zona['zona_hasta']) < tolerance
    evento_match = z['evento'] == ultimo_evento
    
    if zona_desde_match and zona_hasta_match and evento_match:
        zona_duplicada = z
        break
```

#### C. UPDATE en Lugar de INSERT (líneas 451-492)
Si se encuentra duplicado:

```python
if zona_duplicada:
    # Calcular nuevo estado según validación y estado de dashboard
    if not es_valido:
        nuevo_estado = 'DESCARTADA'
    elif zona_duplicada['estado'] in ['DESCARTADA', 'SL', 'TP'] and zona_duplicada.get('fecha_cierre'):
        # Reactivar zona que estaba cerrada
        nuevo_estado = 'PAUSADA' if dashboard_locked else 'ACTIVA'
        print(f"  🔄 Reactivando zona desde {zona_duplicada['estado']} → {nuevo_estado}")
    else:
        # Zona ya activa, mantener estado
        nuevo_estado = zona_duplicada['estado']
    
    # UPDATE la zona duplicada (PATCH request)
    # ... actualizar score, ob, fvg, barrida, tendencias, estado
    return  # No hacer INSERT
```

---

## Archivos Modificados

1. **assets/app.js**
   - Documentación mejorada en `reevaluatePausedZone()`
   - Lógica de reactivación de zonas duplicadas en `trackZoneHistory()`
   - Comentarios clarificando prevención de duplicados

2. **smc_h1_m15_processor.py**
   - Nueva función `get_all_zones_for_symbol()`
   - Detección exacta de duplicados en `process_symbol()`
   - Lógica UPDATE en lugar de INSERT para duplicados

---

## Validación

### Para Validar Prevención de Duplicados:

#### En Supabase:
```sql
-- Buscar duplicados en smc_m15_setups
SELECT 
    symbol,
    zona_desde,
    zona_hasta,
    evento,
    COUNT(*) as count
FROM public.smc_m15_setups
GROUP BY symbol, zona_desde, zona_hasta, evento
HAVING COUNT(*) > 1;

-- Buscar duplicados en smc_h1_m15_setups
SELECT 
    symbol,
    zona_desde,
    zona_hasta,
    evento,
    COUNT(*) as count
FROM public.smc_h1_m15_setups
GROUP BY symbol, zona_desde, zona_hasta, evento
HAVING COUNT(*) > 1;
```

**Resultado esperado:** 0 duplicados después del fix.

#### En Logs:
Buscar mensajes como:
```
✓ Zona duplicada 123 reactivada desde DESCARTADA → ACTIVA para Boom 1000 Index
✓ Zona duplicada actualizada: ID 456 → estado: PAUSADA
```

### Para Validar que SMC M15 PRO NO Descarta por H1/M15/Evento:

#### En Supabase:
```sql
SELECT 
    motivo_cierre,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
GROUP BY motivo_cierre
ORDER BY cantidad DESC;
```

**Resultado esperado:** 
- ❌ NO deben aparecer: "Contexto H1 cambió contra la zona"
- ❌ NO deben aparecer: "Contexto M15 cambió contra la zona"
- ❌ NO deben aparecer: "Evento M15 dejó de tener sentido para la zona"
- ✅ Solo debe aparecer: "Precio tocó SL de zona pausada"

---

## Resumen

### ✅ Validaciones SMC M15 PRO
- **YA ESTABAN CORRECTAS:** Las validaciones de H1/M15/Evento **NO se aplican** a SMC_M15_PRO
- **CONFIRMADO:** Solo se descarta por precio tocando SL
- **MEJORA:** Documentación exhaustiva agregada

### ✅ Prevención de Duplicados
- **IMPLEMENTADO:** Detección exacta por `(symbol + zona_desde + zona_hasta + evento)`
- **IMPLEMENTADO:** UPDATE estado en lugar de INSERT cuando se detecta duplicado
- **IMPLEMENTADO:** Reactivación automática de zonas terminales cuando reaparecen
- **COBERTURA:** JavaScript (app.js) y Python (smc_h1_m15_processor.py)

### 🎯 Impacto
- **Sin cambios** en comportamiento de SMC_M15_PRO (validaciones ya eran correctas)
- **Elimina duplicados** en ambas estrategias (SMC_M15_PRO y SMC_H1_M15_PRO)
- **Reutiliza zonas** existentes en lugar de crear duplicados
- **Mantiene integridad** de datos en base de datos

---

## Commits
1. `c8cc13c` - Implement duplicate zone prevention with estado UPDATE
2. `428bb08` - Add documentation for validation rules and duplicate prevention

## Branch
`copilot/smc-m15-pro-remove-validations`
