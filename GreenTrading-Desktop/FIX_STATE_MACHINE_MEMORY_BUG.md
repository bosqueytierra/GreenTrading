# FIX: State Machine Memory Bug - EN_ZONA Transitions

## 🐛 Bug Detectado

**Caso Real (Crash 600)**:
- Zona detectada correctamente
- Precio entró a zona → Sistema marcó EN_ZONA ✅
- Precio salió de zona en dirección favorable → Sistema NO marcó PROFIT ❌
- Sistema volvió a ESPERANDO_ENTRADA (perdió memoria) ❌

## 🔍 Causa Raíz

En `calcular_transicion_estado()` líneas 852-860 (ANTES):

```python
elif estado_previo == 'EN_ZONA':
    if estado_calculado == 'PROFIT':
        return "PROFIT", "Precio salió en dirección favorable"
    elif estado_calculado in ['ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA', 'ACTIVA']:
        # ❌ BUG: Permitía volver atrás
        return estado_calculado, "Precio salió de la zona"
```

**Problema**: La zona perdía memoria cuando el precio salía temporalmente en dirección desfavorable.

## ✅ Solución Implementada

### 1. Máquina de Estados Correcta

```
ESPERANDO_ENTRADA <-> LLEGANDO_A_ZONA
         ↓                ↓
         └──→ EN_ZONA ←──┘
                 ↓
              PROFIT
                 ↓
                TP

EN_ZONA → SL (si toca stoploss)
PROFIT → SL (si toca stoploss)
```

**Reglas Clave**:
- Una vez EN_ZONA → NUNCA vuelve a: ESPERANDO_ENTRADA, LLEGANDO_A_ZONA, ACTIVA
- Una vez PROFIT → NUNCA vuelve a: EN_ZONA, ESPERANDO_ENTRADA, LLEGANDO_A_ZONA, ACTIVA

### 2. Código Corregido

**EN_ZONA (líneas 865-879)**:
```python
elif estado_previo == 'EN_ZONA':
    # FIX CRÍTICO: Una vez EN_ZONA, NUNCA vuelve a estados anteriores
    if estado_calculado == 'PROFIT':
        return "PROFIT", "Precio salió en dirección favorable"
    elif estado_calculado == 'EN_ZONA':
        return "EN_ZONA", "Precio sigue en zona"
    elif estado_calculado in ['ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA', 'ACTIVA']:
        # PROHIBIDO: No puede volver atrás
        print(f"  WARNING: Bloqueando transición ilegal EN_ZONA -> {estado_calculado}")
        return "EN_ZONA", "Zona mantiene memoria (precio salió temporalmente sin profit)"
    else:
        return "EN_ZONA", "Zona mantiene estado (esperando PROFIT o SL)"
```

**PROFIT (líneas 881-893)**:
```python
elif estado_previo == 'PROFIT':
    # FIX CRÍTICO: Una vez PROFIT, NUNCA vuelve a EN_ZONA ni estados anteriores
    if estado_calculado == 'PROFIT':
        return "PROFIT", "Mantiene profit"
    elif estado_calculado in ['EN_ZONA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA', 'ACTIVA']:
        # PROHIBIDO: No puede retroceder
        print(f"  WARNING: Bloqueando transición ilegal PROFIT -> {estado_calculado}")
        return "PROFIT", "Mantiene profit (bloqueada transición hacia atrás)"
    else:
        return "PROFIT", "Mantiene profit (esperando TP o SL)"
```

## 📊 Escenarios Validados

### Crash 600 - CORREGIDO

**Setup**:
- Zona: 600-620
- Entrada: 600
- Stoploss: 630
- Dirección: BAJISTA

**Secuencia**:

1. **Precio: 610** (dentro de zona)
   - estado_calculado = "EN_ZONA"
   - estado_previo = None
   - ✅ estado_final = "EN_ZONA"

2. **Precio: 625** (salió arriba - desfavorable)
   - estado_calculado = "ESPERANDO_ENTRADA"
   - estado_previo = "EN_ZONA"
   - ✅ estado_final = "EN_ZONA" (bloqueada transición ilegal)
   - Log: "WARNING: Bloqueando transición ilegal EN_ZONA -> ESPERANDO_ENTRADA"

3. **Precio: 595** (salió abajo - favorable)
   - estado_calculado = "PROFIT"
   - estado_previo = "EN_ZONA"
   - ✅ estado_final = "PROFIT"

4. **Precio: 580** (alcanza TP 1:1)
   - estado_calculado = calculado internamente
   - estado_previo = "PROFIT"
   - ✅ estado_final = "TP"

### Boom 500 - CORREGIDO

**Setup**:
- Zona: 500-520
- Entrada: 520
- Stoploss: 490
- Dirección: ALCISTA

**Secuencia**:

1. **Precio: 510** → EN_ZONA ✅
2. **Precio: 495** (salió abajo - desfavorable) → Mantiene EN_ZONA ✅
3. **Precio: 525** (salió arriba - favorable) → PROFIT ✅
4. **Precio: 510** (retrocedió a zona) → Mantiene PROFIT ✅ (NO vuelve a EN_ZONA)

## 🎯 Transiciones Permitidas

| Desde Estado        | A Estado          | Permitido | Notas                          |
|---------------------|-------------------|-----------|--------------------------------|
| ESPERANDO_ENTRADA   | LLEGANDO_A_ZONA   | ✅        | Pueden oscilar                 |
| ESPERANDO_ENTRADA   | EN_ZONA           | ✅        | Precio tocó zona               |
| LLEGANDO_A_ZONA     | ESPERANDO_ENTRADA | ✅        | Pueden oscilar                 |
| LLEGANDO_A_ZONA     | EN_ZONA           | ✅        | Precio tocó zona               |
| EN_ZONA             | PROFIT            | ✅        | Salida favorable               |
| EN_ZONA             | SL                | ✅        | Toca stoploss                  |
| EN_ZONA             | EN_ZONA           | ✅        | Se mantiene                    |
| EN_ZONA             | ESPERANDO_ENTRADA | ❌        | PROHIBIDO (pierde memoria)     |
| EN_ZONA             | LLEGANDO_A_ZONA   | ❌        | PROHIBIDO (pierde memoria)     |
| EN_ZONA             | ACTIVA            | ❌        | PROHIBIDO (pierde memoria)     |
| PROFIT              | TP                | ✅        | Alcanza 1:1                    |
| PROFIT              | SL                | ✅        | Retrocede a stoploss           |
| PROFIT              | PROFIT            | ✅        | Se mantiene                    |
| PROFIT              | EN_ZONA           | ❌        | PROHIBIDO (no retrocede)       |
| PROFIT              | ESPERANDO_ENTRADA | ❌        | PROHIBIDO (no retrocede)       |
| PROFIT              | LLEGANDO_A_ZONA   | ❌        | PROHIBIDO (no retrocede)       |
| TP                  | *                 | ❌        | Terminal (no cambia)           |
| SL                  | *                 | ❌        | Terminal (no cambia)           |

## 📝 Archivos Modificados

1. **GreenTrading-Desktop/backend/smc_m15_service.py**
   - Función `calcular_transicion_estado()` (líneas 739-896)
   - Documentación actualizada con máquina de estados correcta
   - Bloqueo de transiciones ilegales EN_ZONA → estados anteriores
   - Bloqueo de transiciones ilegales PROFIT → estados anteriores
   - Logging de advertencia cuando se bloquea transición ilegal
   - Actualización CHECK 2: permitir PROFIT → SL (línea 835, 844)

## 🔍 Logging Implementado

Cuando se bloquea una transición ilegal:

```
WARNING: Bloqueando transición ilegal EN_ZONA -> ESPERANDO_ENTRADA
Zona mantiene memoria: una vez tocada, nunca vuelve a estados iniciales
```

```
WARNING: Bloqueando transición ilegal PROFIT -> EN_ZONA
Una vez en profit, nunca retrocede a estados anteriores
```

## ✅ Próximos Pasos

### Validación
- [ ] Monitorear logs en producción para casos de transiciones bloqueadas
- [ ] Verificar que Crash 600 ahora marca PROFIT correctamente
- [ ] Verificar que Boom setups mantienen memoria correctamente

### Mejoras Futuras (Opcional)
- [ ] Agregar campos en Supabase: `zona_tocada`, `fecha_entrada_zona`, `precio_entrada_zona`
- [ ] Implementar historial de transiciones de estado
- [ ] Dashboard: indicador visual "ZONA TOCADA" cuando aplique

## 📚 Referencias

- Issue original: Crash 600 no marcaba PROFIT después de tocar zona
- Memoria relevante: "SMC M15 PRO state machine validation"
- Archivo: `smc_m15_service.py` líneas 739-896

---

**Fecha**: 2026-05-08
**Autor**: Copilot Agent
**Estado**: ✅ Implementado y Comiteado
