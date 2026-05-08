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

1. **Nueva zona sin historial**: Solo permite ACTIVA, ESPERANDO_ENTRADA, o **EN_ZONA si precio está realmente dentro de la zona**
2. **ACTIVA/ESPERANDO_ENTRADA → EN_ZONA**: Solo cuando precio toca la zona
3. **EN_ZONA → PROFIT**: Solo cuando precio sale en dirección favorable
4. **PROFIT/EN_ZONA → TP**: Solo cuando alcanza TP 1:1
5. **ACTIVA/EN_ZONA → SL**: Solo cuando alcanza stop loss
6. **Estados terminales (TP/SL)**: No cambian

### 2. Lógica Refinada para Nuevas Zonas

**CORRECCIÓN CRÍTICA**: Para zonas nuevas sin historial, se verifica el orden correcto:

1. **Primero**: Si calculado=EN_ZONA Y precio está REALMENTE en zona → Permitir EN_ZONA
2. **Segundo**: Verificar si precio ya tocó TP/SL (anómalo) → Retornar ACTIVA con advertencia
3. **Tercero**: Otros estados iniciales válidos (ESPERANDO_ENTRADA, LLEGANDO_A_ZONA, ACTIVA)
4. **Cuarto**: Bloquear PROFIT sin historial → Retornar ACTIVA

**Código implementado:**

```python
# CHECK 1: Si NO hay estado previo, solo permitir ACTIVA/ESPERANDO_ENTRADA
if not estado_previo:
    # ORDEN DE VALIDACION:
    # 1. Primero verificar si precio está en zona (permitir EN_ZONA si es el caso)
    # 2. Luego verificar TP/SL (situaciones anómalas)
    # 3. Finalmente, otros estados iniciales válidos
    
    # Verificar si precio está realmente dentro de la zona
    en_zona_real = zona_desde <= precio_actual <= zona_hasta
    
    # Si calculado es EN_ZONA Y precio está realmente en zona, permitirlo
    if estado_calculado == 'EN_ZONA' and en_zona_real:
        return "EN_ZONA", "Nueva zona detectada (precio dentro de zona)"
    
    # Si no está en zona, verificar si ya tocó TP/SL (situación anómala)
    if en_tp:
        return "ACTIVA", "Nueva zona detectada (precio en TP, requiere monitoreo)"
    elif en_sl:
        return "ACTIVA", "Nueva zona detectada (precio en SL, requiere monitoreo)"
```

### 3. Modificación: `calcular_estado_historial()`

Se modificó para:
- Recibir el `estado_previo` desde Supabase
- Usar `calcular_transicion_estado()` para validar la transición
- Devolver tupla `(estado_final, motivo_transicion)`

### 4. Modificación: `analyze_symbol_smc()`

Se añadió:
- Consulta del estado previo guardado en Supabase usando `get_active_setup()`
- Paso del estado previo a `calcular_estado_historial()`
- Logs completos con todos los campos solicitados

### 5. Logs Completos Implementados

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

✅ **11/11 tests pasando:**

1. ✅ Nueva zona lejos del precio → ESPERANDO_ENTRADA
2. ✅ Nueva zona con precio EN_ZONA realmente en zona → EN_ZONA (permitido)
3. ✅ Nueva zona calculado EN_ZONA pero precio fuera → ACTIVA
4. ✅ Nueva zona con precio en PROFIT → ACTIVA (sin historial previo)
5. ✅ Transición válida ACTIVA → EN_ZONA
6. ✅ Transición inválida ACTIVA → PROFIT bloqueada
7. ✅ Transición válida EN_ZONA → PROFIT
8. ✅ Transición válida EN_ZONA → TP
9. ✅ Nueva zona en TP → ACTIVA (sin historial previo)
10. ✅ Transición válida ACTIVA → SL
11. ✅ Estado terminal TP no cambia

## Casos de Uso Resueltos

### Caso 1: Nueva zona detectada con precio EN ZONA

**Antes:**
- Zona nueva detectada con precio dentro de zona
- Sistema bloqueaba: `estado = ACTIVA` ❌

**Después:**
- Zona nueva detectada con precio dentro de zona
- Sistema permite: `estado = EN_ZONA` ✅
- Log: "Nueva zona detectada (precio dentro de zona)" ✅

### Caso 2: Nueva zona detectada con precio en PROFIT

**Antes:**
- Zona nueva detectada con precio en PROFIT
- Sistema asignaba: `estado = PROFIT` ❌

**Después:**
- Zona nueva detectada con precio en PROFIT
- Sistema asigna: `estado = ACTIVA` ✅
- Log: "Nueva zona detectada (precio en profit, sin historial previo)" ✅

### Caso 3: Zona existente avanza a EN_ZONA

**Antes:**
- Zona ACTIVA, precio toca zona
- Sistema podría saltar a PROFIT ❌

**Después:**
- Zona ACTIVA, precio toca zona
- Sistema valida transición: ACTIVA → EN_ZONA ✅
- Log: "Precio tocó la zona" ✅

### Caso 4: Intento de salto de estado

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
  - **CORRECCIÓN CRÍTICA**: Orden de validación para nuevas zonas (zona real → TP/SL → otros)

- `GreenTrading-Desktop/backend/test_state_machine.py`
  - 11 casos de prueba (100% passing)
  - Validación de todas las reglas de transición
  - Test específico para EN_ZONA con precio realmente en zona

## Comportamiento Correcto

### Estado SIN SETUP
Se mantiene solo cuando NO hay zona válida (sin OB/FVG/barrida detectado).

### Estados iniciales permitidos para zona nueva:
- ACTIVA
- ESPERANDO_ENTRADA
- LLEGANDO_A_ZONA
- **EN_ZONA** (solo si precio está REALMENTE dentro de zona_desde y zona_hasta)

### Estados avanzados SOLO con historial:
- PROFIT (requiere haber estado EN_ZONA previamente)
- TP (requiere haber estado EN_ZONA o PROFIT previamente)
- SL (requiere haber estado ACTIVA o EN_ZONA previamente)

### Estados NUNCA permitidos para zona nueva:
- ❌ PROFIT sin historial → se convierte en ACTIVA
- ❌ TP sin historial → se convierte en ACTIVA
- ❌ SL sin historial → se convierte en ACTIVA
- ❌ EN_ZONA sin precio realmente en zona → se convierte en ACTIVA

## Próximos Pasos

1. ✅ Testing en ambiente de desarrollo
2. ✅ Todos los tests pasando (11/11)
3. ⏳ Validar con datos reales de MT5
4. ⏳ Monitorear logs de transiciones

## Notas Técnicas

- La función usa `supabase_service.get_active_setup()` para recuperar el estado previo
- Estados terminales (TP, SL) no cambian una vez alcanzados
- Si el precio está en posición anómala al detectar nueva zona (ya en TP/SL), se inicia como ACTIVA con log de advertencia
- La lógica distingue correctamente entre Boom (ALCISTA) y Crash (BAJISTA)
- **IMPORTANTE**: EN_ZONA se permite como estado inicial SOLO si el precio está físicamente dentro de los límites de la zona (zona_desde <= precio <= zona_hasta)
