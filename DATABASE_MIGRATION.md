# Migración de Base de Datos - SMC M15 PRO

## Objetivo
Agregar campos para almacenar el contexto completo del análisis SMC al momento de crear un setup.

## Cambios Requeridos en Supabase

### Tabla: `smc_m15_setups`

Necesitas agregar las siguientes 3 columnas a la tabla `smc_m15_setups`:

```sql
-- Agregar columnas para tendencias y último evento M15
ALTER TABLE smc_m15_setups 
ADD COLUMN tendencia_h1 TEXT,
ADD COLUMN tendencia_m15 TEXT,
ADD COLUMN ultimo_evento_m15 TEXT;
```

### Descripción de los Campos

| Campo | Tipo | Descripción | Valores Posibles |
|-------|------|-------------|------------------|
| `tendencia_h1` | TEXT | Tendencia en timeframe H1 al momento de detectar el setup | `ALCISTA`, `BAJISTA`, `null` |
| `tendencia_m15` | TEXT | Tendencia en timeframe M15 al momento de detectar el setup | `ALCISTA`, `BAJISTA`, `null` |
| `ultimo_evento_m15` | TEXT | Último evento de estructura detectado en M15 | `BOS_ALCISTA`, `BOS_BAJISTA`, `CHOCH_ALCISTA`, `CHOCH_BAJISTA`, `null` |

## ¿Por Qué Estos Campos?

Estos campos permiten analizar retrospectivamente qué condiciones de mercado llevaron a que un setup alcanzara TP o SL:

1. **tendencia_h1**: Muestra si el setup estaba a favor o en contra de la tendencia mayor (H1)
2. **tendencia_m15**: Muestra la tendencia del timeframe donde se detectó el setup
3. **ultimo_evento_m15**: Indica si fue un BOS (Break of Structure) o CHOCH (Change of Character) lo que creó la zona

## Ejemplo de Análisis

Con estos datos, puedes analizar patrones como:

- ¿Los setups con tendencia H1 y M15 alineadas tienen mejor winrate?
- ¿Los CHOCH tienen mejor performance que los BOS?
- ¿Qué índices funcionan mejor con ciertos patrones de estructura?

## Migración de Datos Antiguos

**NO es necesario migrar datos antiguos** ya que empezarás con un historial limpio. Los registros nuevos incluirán automáticamente estos campos.

Si en el futuro quieres llenar los datos históricos (opcional):

```sql
-- Los registros viejos tendrán NULL en estos campos
-- Esto es aceptable ya que el dashboard los mostrará como '--'
UPDATE smc_m15_setups 
SET tendencia_h1 = NULL,
    tendencia_m15 = NULL,
    ultimo_evento_m15 = NULL
WHERE tendencia_h1 IS NULL;
```

## Verificación Post-Migración

Después de ejecutar el ALTER TABLE, verifica que los campos existan:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'smc_m15_setups'
  AND column_name IN ('tendencia_h1', 'tendencia_m15', 'ultimo_evento_m15');
```

Deberías ver algo como:

```
column_name         | data_type | is_nullable
--------------------|-----------|------------
tendencia_h1        | text      | YES
tendencia_m15       | text      | YES
ultimo_evento_m15   | text      | YES
```

## Notas Importantes

- ✅ Los campos son opcionales (nullable) para permitir compatibilidad con registros antiguos
- ✅ El código JavaScript ya está actualizado para guardar estos campos
- ✅ El dashboard mostrará estos campos en el historial
- ✅ No se requieren cambios en las políticas RLS de Supabase
- ✅ El rendimiento no se ve afectado (campos de texto simples)

## Próximos Pasos

1. Ejecutar el ALTER TABLE en Supabase
2. Borrar el historial anterior si lo deseas: `DELETE FROM smc_m15_setups;`
3. Reiniciar el sistema para empezar a registrar datos nuevos
4. Los nuevos setups incluirán automáticamente estos campos
