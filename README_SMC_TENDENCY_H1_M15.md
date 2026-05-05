# SMC_TENDENCY_H1_M15 - Nueva Estrategia

## Resumen

**SMC_TENDENCY_H1_M15** es una estrategia NUEVA creada desde cero que valida zonas SMC usando SOLO:
- Dirección del índice (Boom/Crash)
- Tendencia H1
- Evento M15 (CHOCH/BOS)

**NO valida** la tendencia M15 (solo es informativa).

## Diferencias con otras estrategias

| Aspecto | SMC M15 PRO | SMC H1+M15 PRO | SMC_TENDENCY_H1_M15 |
|---------|-------------|----------------|---------------------|
| Tabla | `smc_m15_setups` | `smc_h1_m15_setups` | `smc_tendency_h1_m15_setups` |
| Valida H1 | ❌ No | ✅ Sí | ✅ Sí |
| Valida M15 trend | ❌ No | ✅ Sí | ❌ No (solo info) |
| Valida M15 event | ❌ No | ✅ Sí | ✅ Sí |
| Registros DESCARTADA | ❌ No (filtrados) | ✅ Sí | ❌ No (no se guardan) |
| Estados permitidos | ACTIVA, EN_ZONA, PROFIT, TP, SL, PAUSADA | ACTIVA, EN_ZONA, PROFIT, TP, SL, PAUSADA, DESCARTADA | ACTIVA, EN_ZONA, PROFIT, TP, SL, PAUSADA |

## Reglas de validación

### Para índices BOOM:
```
✅ VÁLIDO cuando:
- Tendencia H1 = ALCISTA
- Evento M15 = CHOCH_ALCISTA o BOS_ALCISTA

❌ INVÁLIDO en cualquier otro caso (zona NO se guarda)
```

### Para índices CRASH:
```
✅ VÁLIDO cuando:
- Tendencia H1 = BAJISTA
- Evento M15 = CHOCH_BAJISTA o BOS_BAJISTA

❌ INVÁLIDO en cualquier otro caso (zona NO se guarda)
```

### Importante:
- **La tendencia M15 NO valida** esta estrategia
- Solo se puede guardar/mostrar como dato informativo
- NO decide si la zona es válida
- Score, OB, FVG y Barrida se mantienen como información, pero NO son filtros excluyentes

## Comportamiento de zonas inválidas

Si una zona NO cumple la validación (H1 + evento M15):
- ❌ NO se guarda en la base de datos
- ❌ NO aparece en dashboard
- ❌ NO aparece en historial
- ❌ NO queda PAUSADA
- ❌ NO queda DESCARTADA

**Simplemente se ignora.** No hay registros DESCARTADA en esta estrategia.

## Estados de zona

### Estados activos (pueden ser actualizados por precio):
- **ACTIVA**: Zona detectada, esperando que el precio entre
- **EN_ZONA**: Precio dentro de la zona
- **PROFIT**: Precio en profit, fuera de zona pero antes de TP
- **PAUSADA**: Zona reemplazada por otra nueva (solo se descarta si toca SL)
- **TP**: Take Profit alcanzado (1:1)

### Estados terminales (zona cerrada):
- **SL**: Stop Loss alcanzado
- **TP**: Take Profit alcanzado y liberado (1:2 o retroceso a SL)

### Estado NO usado:
- ~~**DESCARTADA**~~: NO se usa en esta estrategia (las zonas inválidas nunca se guardan)

## Zonas PAUSADA

Las zonas PAUSADA en SMC_TENDENCY_H1_M15 se comportan como en SMC M15 PRO:
- ✅ Solo se descartan si el precio toca SL
- ❌ NO se descartan por cambios en H1
- ❌ NO se descartan por cambios en M15 trend
- ❌ NO se descartan por cambios en evento M15
- ❌ NO se reevalúan por confluencia

## Archivos de la estrategia

### Backend (Python):
- `src/smc_engine_tendency_h1_m15.py` - Motor de análisis SMC con validación simplificada
- `smc_tendency_h1_m15_processor.py` - Procesador que lee velas y guarda zonas válidas

### Frontend (JavaScript):
- `assets/app.js` - Configuración de estrategia y lógica de validación
- `index.html` - Tabs de Dashboard e Historial

### Base de datos:
- `public.market_candles` - Fuente de datos (compartida con otras estrategias)
- `public.smc_tendency_h1_m15_setups` - Tabla exclusiva para esta estrategia

## Instalación y uso

### 1. Crear tabla en Supabase

Ejecutar SQL para crear la tabla `public.smc_tendency_h1_m15_setups`:

```sql
-- La tabla debe tener la misma estructura que smc_m15_setups
-- pero con nombre: smc_tendency_h1_m15_setups
-- (El SQL debe ser proporcionado por separado)
```

### 2. Ejecutar el procesador

```bash
python3 smc_tendency_h1_m15_processor.py
```

El procesador:
- Lee velas desde `public.market_candles`
- Analiza zonas SMC
- Valida con regla H1 + evento M15
- Guarda solo zonas válidas en `public.smc_tendency_h1_m15_setups`

### 3. Usar la UI

1. Abrir el dashboard web
2. Seleccionar tab **"SMC_TENDENCY_H1_M15"**
3. Ver zonas activas en tiempo real
4. Ir a **"Historial"** → **"Historial SMC_TENDENCY_H1_M15"** para ver histórico

## Verificación

Para verificar que la estrategia funciona correctamente:

1. **Verificar tabla existe**:
   ```sql
   SELECT COUNT(*) FROM public.smc_tendency_h1_m15_setups;
   ```

2. **Verificar solo estados permitidos**:
   ```sql
   SELECT DISTINCT estado FROM public.smc_tendency_h1_m15_setups;
   -- Debe retornar solo: ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL
   -- NO debe aparecer: DESCARTADA
   ```

3. **Verificar validación H1+M15**:
   ```sql
   -- Para BOOM: tendencia_h1 debe ser ALCISTA y evento CHOCH_ALCISTA/BOS_ALCISTA
   SELECT symbol, tendencia_h1, evento 
   FROM public.smc_tendency_h1_m15_setups 
   WHERE tipo_indice = 'BOOM';
   
   -- Para CRASH: tendencia_h1 debe ser BAJISTA y evento CHOCH_BAJISTA/BOS_BAJISTA
   SELECT symbol, tendencia_h1, evento 
   FROM public.smc_tendency_h1_m15_setups 
   WHERE tipo_indice = 'CRASH';
   ```

4. **Verificar aislamiento de SMC M15 PRO**:
   ```sql
   -- Verificar que SMC M15 PRO sigue usando su tabla
   SELECT COUNT(*) FROM public.smc_m15_setups;
   
   -- Verificar que no hay cross-contamination
   SELECT COUNT(*) FROM public.smc_m15_setups 
   WHERE strategy = 'SMC_TENDENCY_H1_M15';
   -- Debe retornar 0
   ```

## Notas importantes

### ⚠️ PROHIBIDO:
- ❌ NO modificar SMC M15 PRO
- ❌ NO escribir en `smc_m15_setups`
- ❌ NO leer historial desde `smc_m15_setups`
- ❌ NO usar `smc_h1_m15_setups`
- ❌ NO reciclar lógica vieja rota
- ❌ NO agregar reglas creativas
- ❌ NO cambiar nombres de código

### ✅ PERMITIDO:
- ✅ Usar las mismas velas desde `public.market_candles`
- ✅ Leer código de referencia (sin copiar bugs)
- ✅ Mantener la misma estructura de tabla
- ✅ Compartir configuración de índices y timeframes

## Mantenimiento

### Monitoreo:
- Revisar logs del procesador para errores
- Verificar que se crean zonas nuevas periódicamente
- Confirmar que zonas inválidas NO se guardan

### Troubleshooting:

**Problema**: No aparecen zonas en el dashboard
- Verificar que el procesador está corriendo
- Verificar que hay datos en `public.market_candles`
- Verificar que las zonas cumplen validación H1+M15

**Problema**: Aparecen registros DESCARTADA
- Esto NO debería pasar
- Verificar que el procesador está usando la versión correcta del código
- Limpiar registros DESCARTADA manualmente si existen

**Problema**: SMC M15 PRO dejó de funcionar
- Verificar que no se modificó `smc_m15_setups`
- Verificar que el procesador SMC M15 PRO sigue corriendo
- Verificar que las funciones en app.js no fueron modificadas

## Autor

Creado como estrategia aislada y limpia para validación H1 + evento M15 sin contaminar otras estrategias existentes.

Fecha: 2026-05-05
