# ✅ Checklist de Verificación - SMC_TENDENCY_H1_M15

## Pre-requisitos
- [ ] Acceso a Supabase SQL Editor
- [ ] Variables de entorno configuradas (.env con SUPABASE_URL y SUPABASE_ANON_KEY)
- [ ] Python 3.x instalado
- [ ] Dependencias Python instaladas (requirements.txt)

---

## 🗄️ Paso 1: Configuración Base de Datos

### 1.1 Crear Tabla
- [ ] Abrir Supabase SQL Editor
- [ ] Ejecutar script: `create_smc_tendency_h1_m15_table.sql`
- [ ] Verificar creación exitosa:
  ```sql
  SELECT table_name FROM information_schema.tables 
  WHERE table_name = 'smc_tendency_h1_m15_setups';
  ```
  **Resultado esperado**: Una fila con el nombre de la tabla

### 1.2 Verificar Estructura
- [ ] Verificar columnas creadas:
  ```sql
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name = 'smc_tendency_h1_m15_setups'
  ORDER BY ordinal_position;
  ```
  **Resultado esperado**: ~28 columnas incluyendo id, symbol, estado, tendencia_h1, tendencia_m15, etc.

### 1.3 Verificar Índices
- [ ] Verificar índices creados:
  ```sql
  SELECT indexname FROM pg_indexes 
  WHERE tablename = 'smc_tendency_h1_m15_setups';
  ```
  **Resultado esperado**: Al menos 5 índices

### 1.4 Verificar Políticas RLS
- [ ] Verificar políticas de seguridad:
  ```sql
  SELECT policyname, cmd FROM pg_policies 
  WHERE tablename = 'smc_tendency_h1_m15_setups';
  ```
  **Resultado esperado**: Al menos 3 políticas (SELECT, INSERT, UPDATE)

---

## 🐍 Paso 2: Ejecutar Procesador Python

### 2.1 Verificar Configuración
- [ ] Archivo `.env` existe en la raíz del proyecto
- [ ] `.env` contiene `SUPABASE_URL=...`
- [ ] `.env` contiene `SUPABASE_ANON_KEY=...`

### 2.2 Iniciar Procesador
- [ ] Ejecutar: `python3 smc_tendency_h1_m15_processor.py`
- [ ] Verificar mensaje de inicio:
  ```
  ====================================================================
   SMC_TENDENCY_H1_M15 PROCESSOR
  ====================================================================
  Tabla objetivo: smc_tendency_h1_m15_setups
  ```

### 2.3 Verificar Procesamiento
- [ ] Esperar al menos 3-5 minutos
- [ ] Verificar mensajes de procesamiento en consola:
  ```
  🔍 Procesando Boom 1000 Index...
  📊 Tendencia H1: ALCISTA
  🔍 Validación: ✅ VÁLIDO...
  ✅ Zona guardada: Boom 1000 Index ALCISTA (ACTIVA)
  ```

### 2.4 Verificar Zonas Creadas
- [ ] Consultar zonas en Supabase:
  ```sql
  SELECT symbol, direccion, estado, tendencia_h1, evento, created_at
  FROM public.smc_tendency_h1_m15_setups
  ORDER BY created_at DESC
  LIMIT 10;
  ```
  **Resultado esperado**: Al menos algunas zonas (depende de condiciones de mercado)

---

## 🌐 Paso 3: Verificar UI Web

### 3.1 Dashboard Tab
- [ ] Abrir dashboard web en navegador
- [ ] Verificar que existen 2 tabs:
  - `SMC M15 PRO` (existente)
  - `SMC_TENDENCY_H1_M15` (nuevo)
- [ ] Click en tab `SMC_TENDENCY_H1_M15`
- [ ] Verificar que carga datos
- [ ] Verificar que NO hay errores en consola del navegador

### 3.2 Dashboard - Datos Mostrados
- [ ] Verificar que muestra índices BOOM
- [ ] Verificar que muestra índices CRASH
- [ ] Verificar que muestra columnas: Tendencia H1, Tendencia M15, Evento M15, Zona, Score, etc.
- [ ] Verificar que los datos son consistentes (H1 + Evento alineados)

### 3.3 Historial Tab
- [ ] Click en sidebar: "Historial SMC M15 PRO"
- [ ] Verificar que existen 2 tabs en la parte superior:
  - `Historial SMC M15 PRO` (existente)
  - `Historial SMC_TENDENCY_H1_M15` (nuevo)
- [ ] Click en tab `Historial SMC_TENDENCY_H1_M15`
- [ ] Verificar que carga historial
- [ ] Verificar que NO aparecen registros con estado DESCARTADA

### 3.4 Historial - Filtros
- [ ] Probar filtro por símbolo (Boom/Crash)
- [ ] Probar filtro por estado
- [ ] Verificar que los filtros funcionan correctamente

---

## 🧪 Paso 4: Validación de Reglas

### 4.1 Validación BOOM
- [ ] Consultar zonas BOOM:
  ```sql
  SELECT symbol, tendencia_h1, evento, direccion
  FROM public.smc_tendency_h1_m15_setups
  WHERE tipo_indice = 'BOOM'
  LIMIT 10;
  ```
- [ ] Verificar que TODAS cumplen:
  - `tendencia_h1 = 'ALCISTA'`
  - `evento = 'CHOCH_ALCISTA'` o `'BOS_ALCISTA'`
  - `direccion = 'ALCISTA'`

### 4.2 Validación CRASH
- [ ] Consultar zonas CRASH:
  ```sql
  SELECT symbol, tendencia_h1, evento, direccion
  FROM public.smc_tendency_h1_m15_setups
  WHERE tipo_indice = 'CRASH'
  LIMIT 10;
  ```
- [ ] Verificar que TODAS cumplen:
  - `tendencia_h1 = 'BAJISTA'`
  - `evento = 'CHOCH_BAJISTA'` o `'BOS_BAJISTA'`
  - `direccion = 'BAJISTA'`

### 4.3 Verificar NO hay DESCARTADA
- [ ] Ejecutar:
  ```sql
  SELECT COUNT(*) as descartadas
  FROM public.smc_tendency_h1_m15_setups
  WHERE estado = 'DESCARTADA';
  ```
  **Resultado esperado**: `descartadas = 0`

### 4.4 Verificar Estados Permitidos
- [ ] Ejecutar:
  ```sql
  SELECT DISTINCT estado 
  FROM public.smc_tendency_h1_m15_setups
  ORDER BY estado;
  ```
  **Resultado esperado**: Solo estados de la lista: ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL

---

## 🔒 Paso 5: Verificar Aislamiento SMC M15 PRO

### 5.1 Tab SMC M15 PRO Intacto
- [ ] Click en tab `SMC M15 PRO` en dashboard
- [ ] Verificar que funciona normalmente
- [ ] Verificar que muestra zonas
- [ ] Verificar que NO hay errores

### 5.2 Historial SMC M15 PRO Intacto
- [ ] Click en tab `Historial SMC M15 PRO`
- [ ] Verificar que funciona normalmente
- [ ] Verificar que muestra historial
- [ ] Verificar que NO muestra registros DESCARTADA

### 5.3 Tabla smc_m15_setups No Contaminada
- [ ] Ejecutar:
  ```sql
  SELECT COUNT(*) as contaminados
  FROM public.smc_m15_setups
  WHERE strategy = 'SMC_TENDENCY_H1_M15';
  ```
  **Resultado esperado**: `contaminados = 0`

### 5.4 Tabla smc_tendency_h1_m15_setups No Contaminada
- [ ] Ejecutar:
  ```sql
  SELECT COUNT(*) as contaminados
  FROM public.smc_tendency_h1_m15_setups
  WHERE strategy != 'SMC_TENDENCY_H1_M15'
  OR strategy IS NULL;
  ```
  **Resultado esperado**: `contaminados = 0`

---

## 📊 Paso 6: Monitoreo Continuo

### 6.1 Logs del Procesador
- [ ] Verificar que el procesador sigue corriendo
- [ ] Verificar que procesa cada 3 minutos (180 segundos)
- [ ] Verificar que NO hay errores recurrentes en logs

### 6.2 Crecimiento de Datos
- [ ] Después de 1 hora, verificar:
  ```sql
  SELECT COUNT(*) as total_zonas,
         COUNT(DISTINCT symbol) as indices_procesados
  FROM public.smc_tendency_h1_m15_setups;
  ```
  **Resultado esperado**: Números crecientes con el tiempo

### 6.3 Distribución de Estados
- [ ] Verificar distribución:
  ```sql
  SELECT estado, COUNT(*) as cantidad
  FROM public.smc_tendency_h1_m15_setups
  GROUP BY estado
  ORDER BY cantidad DESC;
  ```
  **Resultado esperado**: Distribución razonable (más ACTIVA que cerradas)

---

## ✅ Paso 7: Verificación Final

### Checklist General
- [ ] Tabla `smc_tendency_h1_m15_setups` existe y tiene datos
- [ ] Procesador Python está corriendo sin errores
- [ ] Tab `SMC_TENDENCY_H1_M15` aparece en Dashboard
- [ ] Tab `Historial SMC_TENDENCY_H1_M15` aparece en Historial
- [ ] Todas las zonas cumplen validación H1 + Evento M15
- [ ] NO existen registros DESCARTADA
- [ ] SMC M15 PRO sigue funcionando normalmente
- [ ] NO hay cross-contamination entre estrategias

### Documentos de Referencia
- [ ] `README_SMC_TENDENCY_H1_M15.md` - Documentación completa
- [ ] `IMPLEMENTACION_SMC_TENDENCY_H1_M15.md` - Resumen de implementación
- [ ] `create_smc_tendency_h1_m15_table.sql` - Script SQL
- [ ] Este archivo `CHECKLIST_VERIFICACION.md` - Checklist

---

## 🐛 Troubleshooting

### Problema: No aparecen zonas
**Posibles causas**:
- Procesador no está corriendo → Iniciar procesador
- No hay velas en `market_candles` → Verificar collector MT5
- Condiciones de mercado no cumplen validación → Normal, esperar

### Problema: Error en UI
**Posibles causas**:
- Tabla no existe → Ejecutar SQL script
- Permisos RLS incorrectos → Verificar políticas
- Error en configuración STRATEGIES → Revisar app.js

### Problema: Aparecen registros DESCARTADA
**Solución**:
- Esto NO debería pasar en esta estrategia
- Limpiar registros:
  ```sql
  DELETE FROM public.smc_tendency_h1_m15_setups 
  WHERE estado = 'DESCARTADA';
  ```
- Reiniciar procesador con código correcto

### Problema: SMC M15 PRO dejó de funcionar
**Solución**:
- Verificar que tabla `smc_m15_setups` no fue modificada
- Verificar que procesador SMC M15 PRO está corriendo
- Revisar código en app.js no fue alterado

---

## 📞 Soporte

Si todos los checks están ✅, la implementación está completa y funcionando correctamente.

Si encuentras problemas, revisar:
1. Logs del procesador Python
2. Consola del navegador (F12)
3. Políticas RLS en Supabase
4. Documentación en README_SMC_TENDENCY_H1_M15.md

---

**Fecha de checklist**: 2026-05-05  
**Versión**: 1.0.0
