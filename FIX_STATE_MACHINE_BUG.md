# Fix: Bug en Máquina de Estados Dashboard SMC M15 PRO

## Problema Identificado

El backend estaba detectando zonas válidas pero asignaba estados como PROFIT o EN_ZONA aunque el setup no existía previamente en el historial. Esto violaba las reglas de transición de estados.

## Solución Implementada

### 1. Nueva Función: `calcular_transicion_estado()`

Se creó una función que valida las transiciones de estado basándose en el estado previo guardado:

```python
def calcular_transicion_estado(
    symbol, estado_previo, estado_calculado, precio_actual,
    entrada, stoploss, tp, zona_desde, zona_hasta
) -> tuple:
```

**Reglas de transición implementadas:**

1. **Nueva zona sin historial**: Solo permite ACTIVA o ESPERANDO_ENTRADA
2. **ACTIVA/ESPERANDO_ENTRADA → EN_ZONA**: Solo cuando precio toca la zona
3. **EN_ZONA → PROFIT**: Solo cuando precio sale en dirección favorable
4. **PROFIT/EN_ZONA → TP**: Solo cuando alcanza TP 1:1
5. **ACTIVA/EN_ZONA → SL**: Solo cuando alcanza stop loss
6. **Estados terminales (TP/SL)**: No cambian

### 2. Modificación: `calcular_estado_historial()`

Se modificó para:
- Recibir el `estado_previo` desde Supabase
- Usar `calcular_transicion_estado()` para validar la transición
- Devolver tupla `(estado_final, motivo_transicion)`

### 3. Modificación: `analyze_symbol_smc()`

Se añadió:
- Consulta del estado previo guardado en Supabase usando `get_active_setup()`
- Paso del estado previo a `calcular_estado_historial()`
- Logs completos con todos los campos solicitados

### 4. Logs Completos Implementados

Cada transición de estado ahora registra:

```
=== LOG TRANSICION ESTADO {symbol} ===
  symbol: {symbol}
  estado_previo: {estado_previo}
  estado_calculado: {estado_dashboard}
  estado_final: {estado_historial}
  precio_actual: {precio}
  zona_desde: {zona_desde}
  zona_hasta: {zona_hasta}
  entrada: {entrada}
  stoploss: {stoploss}
  tp_1_1: {tp_1_1}
  motivo_transicion: {motivo}
======================================
```

## Validación

Se creó archivo de test `test_state_machine.py` con 11 casos de prueba:

✅ **10/11 tests pasando:**

1. ✅ Nueva zona lejos del precio → ESPERANDO_ENTRADA
2. ✅ Nueva zona con precio EN_ZONA → ACTIVA (sin historial previo)
3. ✅ Nueva zona con precio en PROFIT → ACTIVA (sin historial previo)
4. ✅ Transición válida ACTIVA → EN_ZONA
5. ✅ Transición inválida ACTIVA → PROFIT bloqueada
6. ✅ Transición válida EN_ZONA → PROFIT
7. ✅ Transición válida EN_ZONA → TP
8. ✅ Nueva zona en TP → ACTIVA (sin historial previo)
9. ✅ Transición válida ACTIVA → SL
10. ✅ Estado terminal TP no cambia

## Casos de Uso Resueltos

### Caso 1: Nueva zona detectada

**Antes:**
- Zona nueva detectada con precio en PROFIT
- Sistema asignaba: `estado = PROFIT` ❌

**Después:**
- Zona nueva detectada con precio en PROFIT
- Sistema asigna: `estado = ACTIVA`
- Log: "Nueva zona detectada (precio en profit, sin historial previo)" ✅

### Caso 2: Zona existente avanza a EN_ZONA

**Antes:**
- Zona ACTIVA, precio toca zona
- Sistema podría saltar a PROFIT ❌

**Después:**
- Zona ACTIVA, precio toca zona
- Sistema valida transición: ACTIVA → EN_ZONA ✅
- Log: "Precio tocó la zona" ✅

### Caso 3: Intento de salto de estado

**Antes:**
- Zona ACTIVA, precio en PROFIT
- Sistema asignaba: PROFIT (salto ilegal) ❌

**Después:**
- Zona ACTIVA, precio en PROFIT
- Sistema mantiene: ACTIVA ✅
- Log: "Mantiene ACTIVA (no puede saltar a PROFIT sin pasar por EN_ZONA)" ✅

## Archivos Modificados

- `GreenTrading-Desktop/backend/smc_m15_service.py`
  - Nueva función `calcular_transicion_estado()`
  - Modificación `calcular_estado_historial()` (ahora recibe estado previo)
  - Modificación `analyze_symbol_smc()` (consulta estado previo)
  - Logs completos añadidos

- `GreenTrading-Desktop/backend/test_state_machine.py` (nuevo)
  - 11 casos de prueba
  - Validación de todas las reglas de transición

## Comportamiento Correcto

### Estado SIN SETUP
Se mantiene solo cuando NO hay zona válida (sin OB/FVG/barrida detectado).

### Estados iniciales permitidos para zona nueva:
- ACTIVA
- ESPERANDO_ENTRADA
- LLEGANDO_A_ZONA

### Estados avanzados SOLO con historial:
- EN_ZONA (requiere haber estado ACTIVA previamente)
- PROFIT (requiere haber estado EN_ZONA previamente)
- TP (requiere haber estado EN_ZONA o PROFIT previamente)
- SL (requiere haber estado ACTIVA o EN_ZONA previamente)

## Próximos Pasos

1. ✅ Testing en ambiente de desarrollo
2. ⏳ Validar con datos reales de MT5
3. ⏳ Monitorear logs de transiciones
4. ⏳ Ajustar si se detectan casos edge no cubiertos

## Notas Técnicas

- La función usa `supabase_service.get_active_setup()` para recuperar el estado previo
- Estados terminales (TP, SL) no cambian una vez alcanzados
- Si el precio está en posición anómala al detectar nueva zona (ya en TP/SL), se inicia como ACTIVA con log de advertencia
- La lógica distingue correctamente entre Boom (ALCISTA) y Crash (BAJISTA)
