#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validación para verificar que las estrategias SMC
usan las tablas correctas.

Este script verifica:
1. Que smc_h1_m15_processor.py use SOLO smc_h1_m15_setups
2. Que no haya referencias cruzadas incorrectas
3. Que el frontend lea de las tablas correctas
"""

import os
import re
import sys

# Colores para terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_file_for_wrong_table(filepath, correct_table, wrong_table):
    """
    Verifica que un archivo use la tabla correcta y no la incorrecta.
    
    Args:
        filepath: Ruta del archivo a verificar
        correct_table: Tabla que debería usar
        wrong_table: Tabla que NO debería usar
    
    Returns:
        Tuple (es_correcto, errores_encontrados)
    """
    if not os.path.exists(filepath):
        return None, [f"Archivo no existe: {filepath}"]
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    errors = []
    
    # Buscar referencias a la tabla incorrecta
    wrong_patterns = [
        rf'/rest/v1/{wrong_table}',
        rf'"{wrong_table}"',
        rf"'{wrong_table}'",
        rf'table.*{wrong_table}',
        rf'INSERT INTO.*{wrong_table}',
        rf'UPDATE.*{wrong_table}',
        rf'DELETE FROM.*{wrong_table}',
    ]
    
    for i, line in enumerate(content.split('\n'), 1):
        for pattern in wrong_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                # Excluir comentarios y documentación
                if not re.match(r'^\s*[#/*]', line) and 'NO' not in line.upper():
                    errors.append(f"Línea {i}: Referencia incorrecta a '{wrong_table}': {line.strip()}")
    
    # Verificar que tenga al menos una referencia a la tabla correcta
    has_correct_table = False
    correct_patterns = [
        rf'/rest/v1/{correct_table}',
        rf'"{correct_table}"',
        rf"'{correct_table}'",
    ]
    
    for pattern in correct_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            has_correct_table = True
            break
    
    is_correct = len(errors) == 0 and (has_correct_table or 'test' in filepath.lower())
    
    return is_correct, errors


def main():
    print("="*80)
    print(f"{BLUE}Validación de Tablas SMC - GreenTrading{RESET}")
    print("="*80)
    print()
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Archivos a verificar para H1+M15
    h1_m15_files = [
        'smc_h1_m15_processor.py',
        'smc_h1_m15_pro.py',
        'src/smc_engine_h1_m15.py',
    ]
    
    # Archivos a verificar para M15 PRO
    m15_pro_files = [
        'smc_m15_pro.py',
        'src/smc_engine.py',
    ]
    
    # Frontend
    frontend_files = [
        'assets/app.js',
        'index.html',
    ]
    
    all_correct = True
    
    # Verificar archivos H1+M15
    print(f"{BLUE}1. Verificando estrategia H1+M15 (debe usar smc_h1_m15_setups):{RESET}")
    print("-" * 80)
    
    for file in h1_m15_files:
        filepath = os.path.join(base_path, file)
        is_correct, errors = check_file_for_wrong_table(
            filepath, 
            'smc_h1_m15_setups',
            'smc_m15_setups'
        )
        
        if is_correct is None:
            print(f"  {YELLOW}⚠️  {file}: Archivo no encontrado{RESET}")
        elif is_correct:
            print(f"  {GREEN}✅ {file}: Correcto{RESET}")
        else:
            print(f"  {RED}❌ {file}: Errores encontrados:{RESET}")
            for error in errors:
                print(f"     {RED}{error}{RESET}")
            all_correct = False
    
    print()
    
    # Verificar archivos M15 PRO
    print(f"{BLUE}2. Verificando estrategia M15 PRO (debe usar smc_m15_setups):{RESET}")
    print("-" * 80)
    
    for file in m15_pro_files:
        filepath = os.path.join(base_path, file)
        is_correct, errors = check_file_for_wrong_table(
            filepath,
            'smc_m15_setups',
            'smc_h1_m15_setups'
        )
        
        if is_correct is None:
            print(f"  {YELLOW}⚠️  {file}: Archivo no encontrado{RESET}")
        elif is_correct:
            print(f"  {GREEN}✅ {file}: Correcto{RESET}")
        else:
            print(f"  {RED}❌ {file}: Errores encontrados:{RESET}")
            for error in errors:
                print(f"     {RED}{error}{RESET}")
            all_correct = False
    
    print()
    
    # Verificar frontend
    print(f"{BLUE}3. Verificando configuración de frontend:{RESET}")
    print("-" * 80)
    
    for file in frontend_files:
        filepath = os.path.join(base_path, file)
        
        if not os.path.exists(filepath):
            print(f"  {YELLOW}⚠️  {file}: Archivo no encontrado{RESET}")
            continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar que el frontend tenga las dos estrategias configuradas correctamente
        has_m15_pro = 'smc_m15_setups' in content
        has_h1_m15 = 'smc_h1_m15_setups' in content
        
        if has_m15_pro and has_h1_m15:
            print(f"  {GREEN}✅ {file}: Ambas estrategias configuradas{RESET}")
        else:
            print(f"  {RED}❌ {file}: Falta configuración{RESET}")
            if not has_m15_pro:
                print(f"     {RED}No se encontró referencia a smc_m15_setups{RESET}")
            if not has_h1_m15:
                print(f"     {RED}No se encontró referencia a smc_h1_m15_setups{RESET}")
            all_correct = False
    
    print()
    print("="*80)
    
    if all_correct:
        print(f"{GREEN}✅ VALIDACIÓN EXITOSA: Todas las tablas están correctamente mapeadas{RESET}")
        print()
        print("Resumen de configuración correcta:")
        print("  • SMC M15 PRO → smc_m15_setups")
        print("  • SMC PRO TENDENCIA H1+M15 → smc_h1_m15_setups")
        return 0
    else:
        print(f"{RED}❌ VALIDACIÓN FALLIDA: Se encontraron errores en el mapeo de tablas{RESET}")
        print()
        print("Acción requerida:")
        print("  1. Revisar los archivos marcados con ❌")
        print("  2. Corregir las referencias a las tablas incorrectas")
        print("  3. Ejecutar este script nuevamente")
        return 1


if __name__ == "__main__":
    sys.exit(main())
