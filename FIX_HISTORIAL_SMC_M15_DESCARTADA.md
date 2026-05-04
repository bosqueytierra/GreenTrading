# FIX: PAUSADA → DESCARTADA en SMC M15 PRO

## Problema Identificado

En `public.smc_m15_setups` se encontraron muchas zonas en estado DESCARTADA:
- 89 por "Contexto H1 cambió contra la zona"
- 2 por "Contexto M15 cambió contra la zona"

Esto confirmaba que **SMC M15 PRO** estaba descartando zonas PAUSADAS por cambios de contexto H1/M15, lo cual es **INCORRECTO**.

## Regla de Negocio

### Para SMC M15 PRO:
- Una zona PAUSADA **NO** debe pasar a DESCARTADA por:
  - Contexto H1 cambió contra la zona
  - Contexto M15 cambió contra la zona
  - Evento M15 dejó de tener sentido para la zona
- PAUSADA debe mantenerse como PAUSADA, salvo que se defina una invalidación propia por precio (SL)

### Para SMC H1+M15 PRO:
- Una zona PAUSADA **SÍ** puede pasar a DESCARTADA por:
  - Contexto H1 cambió contra la zona
  - Contexto M15 cambió contra la zona
  - Evento M15 dejó de tener sentido para la zona
- Esta lógica de descarte por H1/M15/evento es específica de esta estrategia

## Solución Implementada

### Archivo: `assets/app.js`

#### Función Modificada: `reevaluatePausedZone()` (línea 508-579)

**Cambios realizados:**

1. **Validación 2: Check H1/M15 context compatibility**
   - **ANTES**: Se aplicaba a todas las estrategias
   - **AHORA**: Solo se aplica si `currentStrategy === 'SMC_H1_M15_PRO'`
   - Código:
   ```javascript
   // 2. Check H1/M15 context compatibility (ONLY for SMC_H1_M15_PRO)
   // For SMC_M15_PRO, PAUSADA zones should NOT be discarded by H1/M15 context changes
   if (!shouldDiscard && currentStrategy === 'SMC_H1_M15_PRO' && analysis && analysis.smc) {
       const tendenciaH1 = analysis.smc.tendenciaH1;
       const tendenciaM15 = analysis.smc.tendenciaM15;
       
       if (tendenciaH1 && tendenciaH1 !== setup.direccion) {
           shouldDiscard = true;
           discardReason = 'Contexto H1 cambió contra la zona';
       } else if (tendenciaM15 && tendenciaM15 !== setup.direccion) {
           shouldDiscard = true;
           discardReason = 'Contexto M15 cambió contra la zona';
       }
   }
   ```

2. **Validación 3: Check if M15 event still makes sense**
   - **ANTES**: Se aplicaba a todas las estrategias
   - **AHORA**: Solo se aplica si `currentStrategy === 'SMC_H1_M15_PRO'`
   - Código:
   ```javascript
   // 3. Check if M15 event still makes sense (ONLY for SMC_H1_M15_PRO)
   // For SMC_M15_PRO, PAUSADA zones should NOT be discarded by M15 event changes
   if (!shouldDiscard && currentStrategy === 'SMC_H1_M15_PRO') {
       const ultimoEvento = getUltimoEventoM15(analysis);
       if (ultimoEvento) {
           const lastEventDireccion = ultimoEvento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';
           
           if (lastEventDireccion !== setup.direccion) {
               shouldDiscard = true;
               discardReason = 'Evento M15 dejó de tener sentido para la zona';
           }
       }
   }
   ```

3. **Logging mejorado**
   - Se agregó la estrategia actual a los mensajes de log para facilitar debugging

### Validaciones que SÍ se aplican a ambas estrategias:

1. **Check if price touched SL** (Validación 1)
   - Aplica a todas las estrategias
   - Si el precio toca el SL, la zona PAUSADA pasa a DESCARTADA

2. **Check minimum confluence** (Validación 4)
   - Aplica a todas las estrategias
   - Si la zona no tiene confluencia OB/FVG/Barrida mínima, se descarta

## Impacto

### ✅ Lo que cambia:
- En **SMC M15 PRO**: Las zonas PAUSADAS ya NO se descartarán por cambios de contexto H1/M15 o eventos M15
- En **SMC H1+M15 PRO**: Las zonas PAUSADAS SÍ se siguen descartando por cambios de contexto H1/M15 o eventos M15 (comportamiento sin cambios)

### ✅ Lo que NO cambia:
- Estados ACTIVA, EN_ZONA, PROFIT, TP, SL: No se tocan
- Dashboard SMC M15 PRO: Sin cambios
- Lógica de creación de zonas: Sin cambios
- Validación H1+M15 al crear zonas en SMC H1+M15 PRO: Sin cambios

## Puntos de Llamada

La función `reevaluatePausedZone()` es llamada desde 4 lugares en `assets/app.js`:

1. **Línea 800**: `handleSLHitAndReactivatePausedZones()` - Cuando se toca SL
2. **Línea 892**: `processSMCM15DataV2()` - Cuando no hay zona válida (SIN SETUP)
3. **Línea 914**: `processSMCM15DataV2()` - Cuando no hay evento M15 válido
4. **Línea 938**: `processSMCM15DataV2()` - Reevaluación regular de zonas pausadas

En todos estos puntos, `currentStrategy` es la variable global que determina qué tabla se está usando (`smc_m15_setups` o `smc_h1_m15_setups`).

## Verificación

Para verificar que el fix funciona correctamente:

### En Supabase:

1. **Revisar zonas DESCARTADAS en SMC M15 PRO**:
```sql
SELECT 
    motivo_cierre,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
GROUP BY motivo_cierre
ORDER BY cantidad DESC;
```

Después del fix, NO deberían aparecer nuevas zonas DESCARTADAS con los siguientes motivos:
- "Contexto H1 cambió contra la zona"
- "Contexto M15 cambió contra la zona"
- "Evento M15 dejó de tener sentido para la zona"

2. **Revisar zonas PAUSADAS actuales**:
```sql
SELECT 
    symbol,
    direccion,
    evento,
    fecha_detectada,
    zona_desde,
    zona_hasta
FROM public.smc_m15_setups
WHERE estado = 'PAUSADA'
ORDER BY fecha_detectada DESC;
```

Estas zonas deberían mantenerse como PAUSADA a menos que:
- El precio toque su SL
- No tengan confluencia OB/FVG/Barrida

### Logs de Aplicación:

Buscar en los logs mensajes como:
```
✓ Zona PAUSADA {id} mantiene estado PAUSADA para {symbol} (estrategia: SMC_M15_PRO)
```

Confirma que las zonas PAUSADAS se mantienen en SMC M15 PRO.

## Archivos Afectados

- ✅ `assets/app.js` - Función `reevaluatePausedZone()` modificada
- ✅ `FIX_HISTORIAL_SMC_M15_DESCARTADA.md` - Este documento de explicación

## Estados NO Afectados

- ACTIVA
- EN_ZONA
- PROFIT
- TP
- SL

Estos estados NO fueron tocados por este fix.
