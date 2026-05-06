# DIAGNÓSTICO DEFINITIVO - Logs Críticos Agregados

## Problema Identificado

El backend de Electron está devolviendo `"--"` para tendencias y eventos, mientras que el backend manual probado con `python -m uvicorn api_server:app --reload` devuelve datos válidos (`ALCISTA`, `BAJISTA`, `CHOCH_BAJISTA`, etc.).

**Conclusión**: Electron NO está ejecutando la misma versión del backend.

## Logs Críticos Agregados

### 1. main.js (Electron)

**Ubicación**: `/GreenTrading-Desktop/main.js` líneas 65-67

```javascript
// CRITICAL LOGS: Confirm Python backend path and executable
console.log('PYTHON BACKEND CWD:', path.dirname(PYTHON_BACKEND.script));
console.log('PYTHON BACKEND SCRIPT:', PYTHON_BACKEND.script);
console.log('PYTHON EXEC:', pythonCmd);
```

**Qué verifica**:
- El directorio de trabajo (cwd) del backend Python
- La ruta completa del script `api_server.py` que Electron está ejecutando
- El ejecutable de Python usado (`python` o `python3`)

### 2. api_server.py (Backend Principal)

**Ubicación**: `/GreenTrading-Desktop/backend/api_server.py` línea 470

```python
print("API_SERVER_PATH:", __file__)
```

**Qué verifica**:
- La ruta absoluta del archivo `api_server.py` que realmente se está ejecutando
- Confirma si es la versión correcta o una versión vieja/desalineada

### 3. smc_m15_service.py (Servicio SMC)

**Ubicación**: `/GreenTrading-Desktop/backend/smc_m15_service.py` línea 26

```python
# CRITICAL LOG: Confirm which file is being executed
print("SMC_SERVICE_PATH:", __file__)
```

**Qué verifica**:
- La ruta absoluta del archivo `smc_m15_service.py` que está siendo importado
- Confirma si `api_server.py` está importando el servicio correcto

## Cómo Usar Estos Logs

1. **Ejecutar Electron normalmente**:
   ```bash
   npm start
   ```

2. **Revisar la consola de Electron**:
   - Los logs de `main.js` aparecerán en la consola del proceso principal
   - Los logs de `api_server.py` y `smc_m15_service.py` aparecerán como `[Python]` en la consola

3. **Comparar rutas**:
   - Verificar que `PYTHON BACKEND SCRIPT` apunte a `/GreenTrading-Desktop/backend/api_server.py`
   - Verificar que `API_SERVER_PATH` muestre la misma ruta
   - Verificar que `SMC_SERVICE_PATH` apunte al archivo correcto en el mismo directorio

4. **Diagnóstico esperado**:
   - Si las rutas NO coinciden → Electron está ejecutando un backend de otra ubicación
   - Si las rutas SÍ coinciden → El problema está en el código del backend (no en la ruta)

## Próximos Pasos

Una vez confirmada la ruta exacta del backend que Electron ejecuta:

- **Si es la ruta incorrecta**: Corregir la configuración en `main.js`
- **Si es la ruta correcta**: Investigar diferencias en el código entre ejecución manual vs Electron
- **Si falta algún import**: Verificar dependencias y configuración de Python

## Archivos Modificados

1. `GreenTrading-Desktop/main.js` - Logs de Electron
2. `GreenTrading-Desktop/backend/api_server.py` - Log de ruta del servidor
3. `GreenTrading-Desktop/backend/smc_m15_service.py` - Log de ruta del servicio SMC

## Notas Importantes

⚠️ **Logs Temporales para Diagnóstico**

Estos logs son **temporales** y están diseñados exclusivamente para diagnóstico:
- Se imprimen cada vez que se inicia el servidor (intencional para confirmar ruta en cada ejecución)
- `SMC_SERVICE_PATH` se imprime al importar el módulo (intencional para confirmar cuál se importa)
- Una vez identificado el problema, estos logs pueden ser removidos o condicionados a un modo debug

⚠️ **Aclaración sobre "CWD"**

El log `PYTHON BACKEND CWD` en `main.js` usa `path.dirname()` que devuelve el directorio del script, no el verdadero working directory del proceso. Esto es suficiente para el diagnóstico actual ya que muestra dónde está ubicado el script que Electron intenta ejecutar.

## NO Tocado

✅ Frontend (sin cambios)  
✅ Render (sin cambios)  
✅ dashboard.js (sin cambios)  
✅ MT5 (sin cambios)

Solo se agregaron logs de diagnóstico, sin modificar la lógica existente.
