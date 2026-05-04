# SMC PRO TENDENCIA H1 + CHOCH/BOS (M15) - Nueva Estrategia

## Descripción

Esta es una nueva estrategia de trading basada en Smart Money Concepts (SMC) que agrega validación obligatoria de alineación entre la tendencia H1 y los eventos M15.

**Importante:** Esta estrategia es **completamente independiente** de SMC M15 PRO. No modifica ni afecta la estrategia original.

---

## Diferencias con SMC M15 PRO

### Lógica Base (Igual)
- ✅ Detección de swings
- ✅ Detección de BOS / CHOCH
- ✅ Detección de Order Blocks (OB)
- ✅ Detección de Fair Value Gaps (FVG)
- ✅ Detección de barridas
- ✅ Construcción de zona M15
- ✅ Cálculo de score
- ✅ Cálculo TP / SL
- ✅ Estados: ACTIVA / EN_ZONA / PROFIT / TP / SL / PAUSADA / DESCARTADA
- ✅ Control de zonas pausadas
- ✅ Historial y métricas

### Nueva Regla de Validación (Diferencia Clave)

**Para que una zona sea válida, debe cumplir:**

#### 1. Tendencia H1 acorde al tipo de índice

- **Boom** → H1 debe ser **ALCISTA**
- **Crash** → H1 debe ser **BAJISTA**

#### 2. Último evento M15 acorde al tipo de índice

**Para Boom:**
- ✅ CHOCH_ALCISTA = válido
- ✅ BOS_ALCISTA = válido
- ❌ CHOCH_BAJISTA = descartado
- ❌ BOS_BAJISTA = descartado

**Para Crash:**
- ✅ CHOCH_BAJISTA = válido
- ✅ BOS_BAJISTA = válido
- ❌ CHOCH_ALCISTA = descartado
- ❌ BOS_ALCISTA = descartado

---

## Ejemplos de Validación

### Boom 1000

| H1 | Evento M15 | Resultado |
|---|---|---|
| ALCISTA | CHOCH_ALCISTA | ✅ Válido |
| ALCISTA | BOS_ALCISTA | ✅ Válido |
| ALCISTA | CHOCH_BAJISTA | ❌ Descartado |
| ALCISTA | BOS_BAJISTA | ❌ Descartado |
| BAJISTA | CHOCH_ALCISTA | ❌ Descartado |
| BAJISTA | BOS_ALCISTA | ❌ Descartado |

### Crash 900

| H1 | Evento M15 | Resultado |
|---|---|---|
| BAJISTA | CHOCH_BAJISTA | ✅ Válido |
| BAJISTA | BOS_BAJISTA | ✅ Válido |
| BAJISTA | CHOCH_ALCISTA | ❌ Descartado |
| BAJISTA | BOS_ALCISTA | ❌ Descartado |
| ALCISTA | CHOCH_BAJISTA | ❌ Descartado |
| ALCISTA | BOS_BAJISTA | ❌ Descartado |

---

## Estructura de Archivos

### Backend (Python)

```
/src/smc_engine_h1_m15.py    # Motor SMC con validación H1+M15
/smc_h1_m15_pro.py            # Script principal para pruebas
```

**Características:**
- Código separado de `smc_engine.py` y `smc_m15_pro.py`
- Funciones propias para análisis y validación
- Función `analyze_smc_h1_m15()` retorna:
  - Análisis completo de SMC
  - `es_valido`: boolean indicando si cumple validación
  - `razon_validacion`: mensaje explicativo

### Frontend (HTML/CSS/JS)

**Cambios en UI:**

1. **Dashboard en vivo**: Pestañas tipo Excel
   - Tab 1: SMC M15 PRO
   - Tab 2: SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)

2. **Historial**: Pestañas tipo Excel
   - Tab 1: Historial SMC M15 PRO
   - Tab 2: Historial SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)

**Archivos modificados:**
- `index.html` - Agregadas pestañas
- `assets/style.css` - Estilos para pestañas
- `assets/app.js` - Lógica de cambio de estrategia

**Variables globales en app.js:**
```javascript
let currentStrategy = 'SMC_M15_PRO';        // Dashboard
let currentHistoryStrategy = 'SMC_M15_PRO'; // Historial

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

---

## Base de Datos

### Tabla Nueva: `smc_h1_m15_setups`

**Características:**
- Misma estructura que `smc_m15_setups`
- Columna adicional: `estrategia` (default: 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)')
- No reutiliza ni modifica `smc_m15_setups`

**Creación:**
Ver archivo `DATABASE_MIGRATION_H1_M15.md` para:
- SQL de creación de tabla
- Índices recomendados
- Políticas RLS
- Triggers

**Estados posibles:**
- `ACTIVA`: Zona detectada, esperando entrada
- `EN_ZONA`: Precio dentro de la zona
- `PROFIT`: Precio salió favorablemente pero no alcanzó TP 1:1
- `TP`: Take Profit 1:1 alcanzado
- `SL`: Stop Loss alcanzado
- `PAUSADA`: Zona pausada (otra zona activa en mismo símbolo)
- `DESCARTADA`: Zona rechazada por no cumplir validación H1+M15

**Motivo de descarte:**
```
"Descartada por filtro H1 + Evento M15 no alineado"
```

---

## Uso

### 1. Crear la tabla en Supabase

Ejecutar el SQL de `DATABASE_MIGRATION_H1_M15.md`:

```sql
create table if not exists public.smc_h1_m15_setups (
  -- ... ver archivo completo ...
);
```

### 2. Probar el motor Python

```bash
python smc_h1_m15_pro.py
```

Salida esperada:
```
==========================================================
 SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)
==========================================================
Índice: Boom 1000 Index
Precio actual: 5432.123
----------------------------------------------------------
Tendencia H1: ALCISTA
Tendencia M15: ALCISTA
Último evento H1: BOS_ALCISTA | nivel: 5420.500
Último evento M15: CHOCH_ALCISTA | nivel: 5428.300
----------------------------------------------------------

🔍 VALIDACIÓN H1 + M15:
Estado: ✅ VÁLIDO
Razón: Válido: H1 ALCISTA + Evento M15 ALCISTA en Boom
----------------------------------------------------------

ZONA DEPURADA M15:
Dirección: ALCISTA
Desde: 5425.000
Hasta: 5430.000
Score: 8 / 10 aprox.
...
```

### 3. Dashboard Web

1. Abrir `index.html` en navegador
2. Hacer login
3. Usar las pestañas para cambiar entre estrategias:
   - Click en "SMC M15 PRO" para ver estrategia original
   - Click en "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)" para ver nueva estrategia

Cada pestaña:
- Muestra datos de su propia tabla Supabase
- Mantiene estados independientes
- Historial separado

---

## Integración con Colector MT5

Para integrar con `mt5_to_supabase.py` o similar:

1. Importar el motor:
```python
from src.smc_engine_h1_m15 import analyze_smc_h1_m15
```

2. Analizar:
```python
result = analyze_smc_h1_m15(symbol, df_h1, df_m15)

if result['zona'] and result['es_valido']:
    # Zona válida, guardar en smc_h1_m15_setups
    setup_data = {
        'symbol': symbol,
        'tipo_indice': 'Boom' if 'Boom' in symbol else 'Crash',
        'direccion': result['zona']['direccion'],
        'zona_desde': result['zona']['zona_desde'],
        'zona_hasta': result['zona']['zona_hasta'],
        'score': result['zona']['score'],
        'evento': result['zona']['evento']['evento'],
        'ob': bool(result['zona']['ob']),
        'fvg': bool(result['zona']['fvg']),
        'barrida': bool(result['zona']['barrida']),
        'estado': 'ACTIVA',
        'tendencia_h1': result['tendencia_h1'],
        'tendencia_m15': result['tendencia_m15'],
        # ... otros campos
    }
    # Insertar en smc_h1_m15_setups
elif result['zona'] and not result['es_valido']:
    # Zona descartada, guardar como DESCARTADA
    setup_data['estado'] = 'DESCARTADA'
    setup_data['motivo_cierre'] = result['razon_validacion']
    # Insertar en smc_h1_m15_setups para auditoría
```

---

## Testing

### Validar motor Python:

```bash
# Test con Boom 1000
python smc_h1_m15_pro.py

# Editar SYMBOL en smc_h1_m15_pro.py para probar otros índices
```

### Validar UI:

1. Abrir navegador en `index.html`
2. Login
3. Verificar pestañas en Dashboard
4. Verificar pestañas en Historial
5. Cambiar entre pestañas y confirmar datos separados

---

## Mantenimiento

### Dos estrategias, dos códigos

| Aspecto | SMC M15 PRO | SMC H1 M15 PRO |
|---------|-------------|----------------|
| Motor Python | `smc_engine.py` | `smc_engine_h1_m15.py` |
| Script | `smc_m15_pro.py` | `smc_h1_m15_pro.py` |
| Tabla Supabase | `smc_m15_setups` | `smc_h1_m15_setups` |
| Validación H1 | No | Sí |
| UI Tab | "SMC M15 PRO" | "SMC PRO TENDENCIA H1..." |

**Regla de oro:** No mezclar estrategias. Mantener código separado.

---

## Troubleshooting

### ❌ "No se encuentra la tabla smc_h1_m15_setups"

**Solución:** Ejecutar el SQL de `DATABASE_MIGRATION_H1_M15.md`

### ❌ "Todas las zonas salen como DESCARTADA"

**Posibles causas:**
1. H1 no está alineado con el tipo de índice
2. Evento M15 no está alineado con el tipo de índice
3. Revisar logs para ver `razon_validacion`

**Debug:**
```python
result = analyze_smc_h1_m15(symbol, df_h1, df_m15)
print(f"Es válido: {result['es_valido']}")
print(f"Razón: {result['razon_validacion']}")
```

### ❌ "Las pestañas no cambian de estrategia"

**Solución:** 
1. Verificar que `currentStrategy` y `currentHistoryStrategy` se actualizan
2. Revisar consola del navegador para errores
3. Confirmar que `getStrategyTable()` retorna tabla correcta

---

## Conclusión

Esta implementación:

✅ Mantiene SMC M15 PRO intacto  
✅ Agrega nueva estrategia con validación H1+M15  
✅ Código completamente separado  
✅ UI con pestañas tipo Excel  
✅ Base de datos independiente  
✅ Fácil mantenimiento  
✅ Historial auditado (zonas descartadas se guardan)  

**Contacto:** Ver README.md principal para más información.
