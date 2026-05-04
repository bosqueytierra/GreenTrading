# Lógica de Zonas PAUSADAS / BACKUP en SMC M15 PRO

## Resumen

Este documento describe la nueva lógica de gestión de zonas PAUSADAS implementada en el sistema SMC M15 PRO. Esta capa de gestión permite mantener zonas válidas en estado de pausa en lugar de descartarlas inmediatamente, y reactivarlas cuando la zona operativa principal alcanza su SL.

## Estados de Zona

### Estados Operativos (Zona Principal)
- **ACTIVA**: Zona operativa principal detectada, esperando que el precio entre
- **EN ZONA**: Precio dentro de la zona operativa
- **PROFIT**: Zona operativa ya reaccionando favorablemente

### Estados Finales
- **TP**: Zona alcanzó Take Profit 1:1
- **SL**: Zona alcanzó Stop Loss
- **DESCARTADA**: Zona invalidada definitivamente

### Nuevo Estado: PAUSADA
- **PAUSADA**: Zona válida pero no operativa (en espera como backup)

## Regla Fundamental

**Solo puede existir UNA zona operativa principal por símbolo** en estados ACTIVA, EN ZONA o PROFIT.

Si se detectan múltiples zonas válidas:
- La más próxima al precio actual queda como operativa
- Las demás quedan como PAUSADA

## Flujo de Gestión de Zonas

### 1. Detección de Nueva Zona

Cuando se detecta una nueva zona válida:

```
¿Existe zona operativa (ACTIVA/EN_ZONA/PROFIT)?
│
├─ SÍ → Nueva zona se crea como PAUSADA
│
└─ NO → Nueva zona se crea como ACTIVA
```

### 2. Múltiples Zonas Operativas

Si hay múltiples zonas en estados operativos:
- Calcular distancia al precio actual para cada zona
- La más cercana permanece operativa
- Las demás pasan a PAUSADA

### 3. Reevaluación de Zonas PAUSADAS

En cada actualización del Dashboard, todas las zonas PAUSADAS son reevaluadas.

Una zona **permanece PAUSADA** solo si:
- ✅ No ha tocado su SL
- ✅ La estructura sigue siendo coherente
- ✅ Su tendencia H1/M15 sigue compatible con la dirección buscada
- ✅ El evento M15 sigue teniendo sentido para esa zona
- ✅ Tiene confluencia mínima (OB/FVG/Barrida)

Una zona **pasa a DESCARTADA** si:
- ❌ El precio tocó su SL
- ❌ El contexto H1/M15 cambió contra la zona
- ❌ El evento M15 dejó de tener sentido
- ❌ Aparece una invalidación estructural clara
- ❌ La zona ya no tiene confluencia OB/FVG/Barrida mínima

### 4. Reactivación Tras SL

Cuando la zona operativa actual alcanza su SL:

```
1. Obtener todas las zonas PAUSADAS del símbolo
2. Reevaluar cada zona PAUSADA
3. Descartar las que ya no sean válidas
4. Si quedan zonas PAUSADAS válidas:
   ├─ Activar la más próxima al precio actual
   └─ Transición: PAUSADA → ACTIVA
5. Si no quedan zonas válidas:
   └─ Esperar nueva detección de zona
```

## Funciones Implementadas

### `reevaluatePausedZone(setup, currentPrice, analysis)`
Reevalúa una zona PAUSADA para determinar si sigue siendo válida o debe descartarse.

**Validaciones:**
1. Verificar si precio tocó SL
2. Verificar compatibilidad de tendencias H1/M15
3. Verificar coherencia del evento M15
4. Verificar confluencia mínima (OB/FVG/Barrida)

**Retorno:**
- `'PAUSADA'`: Zona sigue válida
- `'DESCARTADA'`: Zona fue descartada

### `handleSLHitAndReactivatePausedZones(symbol, currentPrice, analysis)`
Gestiona el hit de SL y la reactivación de zonas pausadas.

**Flujo:**
1. Obtener todas las zonas PAUSADAS del símbolo
2. Reevaluar cada una
3. Mantener solo las válidas
4. Activar la más cercana al precio actual

### `ensureSingleOperativeZone(symbol, currentPrice, analysis)`
Garantiza que solo exista una zona operativa por símbolo.

**Flujo:**
1. Obtener todas las zonas operativas (ACTIVA/EN_ZONA/PROFIT)
2. Si hay más de una:
   - Calcular distancia al precio para cada una
   - Mantener la más cercana como operativa
   - Pausar todas las demás

### `calculateDistanceToZone(zone, currentPrice)`
Calcula la distancia desde el precio actual a una zona.

**Retorno:**
- `0`: Precio dentro de la zona
- `number`: Distancia mínima a los límites de la zona

## Ejemplo de Flujo Completo

### Escenario: Múltiples Zonas Detectadas

```
Símbolo: Boom 1000 Index
Precio Actual: 1000

Zona A: [990-995]  → Distancia: 5 puntos  → ACTIVA (más cercana)
Zona B: [980-985]  → Distancia: 15 puntos → PAUSADA
Zona C: [970-975]  → Distancia: 25 puntos → PAUSADA
```

### Actualización 1: Precio sube a 1010
```
Zona A: EN_ZONA → PROFIT
Zona B: PAUSADA → Reevaluada → PAUSADA (válida)
Zona C: PAUSADA → Reevaluada → PAUSADA (válida)
```

### Actualización 2: Precio baja a 985 (SL de Zona A)
```
Zona A: PROFIT → SL (cerrada)

Reevaluación de zonas pausadas:
Zona B: PAUSADA → Reevaluada → PAUSADA (válida)
Zona C: PAUSADA → Reevaluada → DESCARTADA (contexto cambió)

Reactivación:
Zona B: PAUSADA → ACTIVA (más cercana y única válida)
```

### Actualización 3: Precio entra en Zona B (990)
```
Zona A: SL (cerrada)
Zona B: ACTIVA → EN_ZONA
Zona C: DESCARTADA
```

## Modificaciones No Realizadas

Como se especificó en los requisitos, **NO se modificaron**:
- ❌ Cálculo de TP
- ❌ Cálculo de SL
- ❌ Detección de Order Blocks (OB)
- ❌ Detección de Fair Value Gaps (FVG)
- ❌ Detección de Barridas
- ❌ Cálculo de Score
- ❌ Lógica SMC core

**Solo se agregó la capa de gestión de estados.**

## Integración con Dashboard

### Estados Visuales

El Dashboard muestra el estado PAUSADA con su propio estilo visual:

```css
.status-pausada {
    background: #fef3c7;  /* Amarillo claro */
    color: #92400e;       /* Marrón oscuro */
}
```

### Historial SMC M15 PRO

Las zonas PAUSADAS aparecen en el historial con:
- Badge visual "PAUSADA"
- Columnas de datos completas (zona, TP, SL, score, etc.)
- Max Reacción muestra "--" (igual que ACTIVA)

## Notas Técnicas

### Base de Datos
El estado PAUSADA se almacena en la columna `estado` de la tabla `smc_m15_setups`.

No se requieren cambios en el esquema de la base de datos.

### Query de Zonas Activas
```sql
SELECT * FROM smc_m15_setups 
WHERE symbol = ? 
  AND estado IN ('ACTIVA', 'EN_ZONA', 'PROFIT', 'PAUSADA', 'TP')
ORDER BY created_at DESC
```

### Frecuencia de Reevaluación
Las zonas PAUSADAS se reevalúan en cada refresh del Dashboard (configurable, típicamente cada 10-30 segundos).

## Beneficios de la Implementación

1. **No se pierden zonas válidas**: Las zonas que no son la principal no se descartan inmediatamente
2. **Continuidad operativa**: Si la zona principal falla, hay backups listos para activarse
3. **Gestión inteligente**: Solo se mantienen zonas que siguen siendo válidas según SMC
4. **Sin acumulación**: Las zonas pausadas que pierden validez son descartadas automáticamente
5. **Claridad visual**: El Dashboard muestra claramente qué zona es operativa y cuáles están en espera

## Casos de Prueba Sugeridos

### Test 1: Creación de Zona PAUSADA
1. Sistema detecta Zona A (se crea como ACTIVA)
2. Sistema detecta Zona B
3. **Esperado**: Zona B se crea como PAUSADA

### Test 2: Reevaluación con Contexto Cambiado
1. Zona A está PAUSADA
2. Tendencia H1 cambia de ALCISTA a BAJISTA
3. Zona A es ALCISTA
4. **Esperado**: Zona A → DESCARTADA

### Test 3: Reactivación Tras SL
1. Zona A está EN_ZONA
2. Zona B está PAUSADA (válida)
3. Precio toca SL de Zona A
4. **Esperado**: Zona A → SL, Zona B → ACTIVA

### Test 4: Zona PAUSADA Toca su SL
1. Zona A está PAUSADA
2. Precio toca el SL de Zona A
3. **Esperado**: Zona A → DESCARTADA

## Conclusión

La implementación de la lógica de zonas PAUSADAS proporciona un sistema robusto de gestión de múltiples zonas válidas por símbolo, manteniendo la claridad operativa (una sola zona principal) mientras conserva backups válidos que pueden ser reactivados cuando sea necesario.

El sistema es completamente automático y no requiere intervención manual, reevaluando constantemente las zonas pausadas y descartando las que pierden validez según los criterios SMC.
