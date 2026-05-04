# GUÍA RÁPIDA: Corrección de Tablas SMC

## 🎯 ¿Qué se corrigió?

Se reforzó el código para asegurar que cada estrategia SMC use su tabla correcta:

| Estrategia | Tabla Correcta | Procesador |
|------------|----------------|------------|
| **SMC M15 PRO** | `smc_m15_setups` | (No existe aún) |
| **SMC PRO TENDENCIA H1+M15** | `smc_h1_m15_setups` | `smc_h1_m15_processor.py` ✅ |

## ✅ Estado del Código

El código actual **YA ESTÁ CORRECTO**:
- ✅ `smc_h1_m15_processor.py` usa `smc_h1_m15_setups`
- ✅ Frontend (`app.js`) tiene mapeo correcto
- ✅ Constante `TARGET_TABLE` agregada
- ✅ Comentarios de advertencia en funciones críticas

## 🚨 Acciones Inmediatas Requeridas

### 1. Verificar Base de Datos (URGENTE)

```sql
-- ¿Hay registros incorrectos en smc_m15_setups?
SELECT COUNT(*) 
FROM public.smc_m15_setups 
WHERE tendencia_h1 IS NOT NULL 
   OR estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)';
```

**Si resultado > 0:** Ejecutar limpieza inmediatamente (ver paso 3)

### 2. Verificar Procesador (URGENTE)

```bash
# Ver logs del procesador
tail -50 /path/to/logs/smc_h1_m15_processor.log | grep "TABLA DESTINO"

# Resultado esperado:
# ⚠️  TABLA DESTINO: smc_h1_m15_setups
```

**Si no aparece o es diferente:** Reiniciar procesador (ver paso 4)

### 3. Limpiar Datos Incorrectos (Si aplica)

```bash
# Conectar a Supabase
psql -h your-db.supabase.co -U postgres -d postgres

# Ejecutar script de limpieza
\i cleanup_wrong_table_records.sql

# Seguir pasos 1-5 del script
```

### 4. Reiniciar Procesador con Código Nuevo

```bash
# Actualizar código
cd /path/to/GreenTrading
git pull origin main

# Reiniciar procesador
# Opción A: Si está en screen
screen -r smc_h1_m15
# Ctrl+C, luego
python smc_h1_m15_processor.py

# Opción B: Si está como servicio
sudo systemctl restart smc_h1_m15_processor
```

## 📁 Archivos Creados

### Herramientas
1. **validate_table_mapping.py** - Validación automática del código
2. **cleanup_wrong_table_records.sql** - Limpieza de datos incorrectos

### Documentación
1. **RESUMEN_CORRECCION.md** - Resumen ejecutivo (LEER PRIMERO)
2. **CORRECCION_TABLAS_SMC.md** - Documentación completa
3. **GUIA_RAPIDA.md** - Esta guía (referencia rápida)

## 🔍 Validación Rápida

```bash
# Ejecutar validación automática
python validate_table_mapping.py

# Resultado esperado:
# ✅ VALIDACIÓN EXITOSA: Todas las tablas están correctamente mapeadas
```

## 📋 Checklist

- [ ] Base de datos verificada (0 registros incorrectos)
- [ ] Procesador reiniciado con código nuevo
- [ ] Log muestra "TABLA DESTINO: smc_h1_m15_setups"
- [ ] Validación ejecutada: `python validate_table_mapping.py` ✅
- [ ] Frontend verificado (ambas tabs funcionan)

## ❓ Preguntas Frecuentes

### ¿Por qué smc_h1_m15_setups tiene 0 registros?

Puede ser porque:
1. El procesador aún no ha corrido
2. No hay zonas válidas (filtro H1+M15 muy estricto)
3. Todas las zonas fueron descartadas por validación

**Solución:** Ver logs del procesador para entender qué está detectando.

### ¿Cómo sé si el procesador está usando la tabla correcta?

Busca esta línea en los logs del procesador:
```
⚠️  TABLA DESTINO: smc_h1_m15_setups
```

### ¿Qué hago si encuentro registros en la tabla incorrecta?

Ejecuta `cleanup_wrong_table_records.sql` siguiendo los pasos 1-5.

### ¿Cómo prevenir este problema en el futuro?

1. ✅ No modificar la constante `TARGET_TABLE`
2. ✅ Ejecutar `validate_table_mapping.py` antes de desplegar
3. ✅ Monitorear logs del procesador regularmente

## 🔗 Referencias

- **Documentación completa:** `CORRECCION_TABLAS_SMC.md`
- **Resumen ejecutivo:** `RESUMEN_CORRECCION.md`
- **Manual del procesador:** `README_PROCESSOR_H1_M15.md`
- **Migración de BD:** `DATABASE_MIGRATION_H1_M15.md`

## 📞 Soporte

1. Revisar logs del procesador
2. Ejecutar `python validate_table_mapping.py`
3. Consultar `RESUMEN_CORRECCION.md`
4. Verificar registros en base de datos con queries del script SQL

---

**IMPORTANTE:** Este problema se refiere al mapeo de tablas, NO a la lógica de la estrategia H1+M15.  
La estrategia y su validación están correctamente implementadas.

**Fecha:** 2026-05-04  
**Estado:** ✅ Código correcto, acción requerida en BD y procesador
