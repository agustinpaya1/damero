<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documentación - Generador de Mapas de Calor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        h1 {
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            background-color: #f8f9fa;
            padding: 8px;
            border-left: 4px solid #3498db;
        }
        code {
            background-color: #f0f0f0;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: monospace;
        }
        .note {
            background-color: #e7f5fe;
            border-left: 4px solid #3498db;
            padding: 12px;
            margin: 15px 0;
        }
        .warning {
            background-color: #fff3bf;
            border-left: 4px solid #ffd43b;
            padding: 12px;
            margin: 15px 0;
        }
        .screenshot {
            border: 1px solid #ddd;
            max-width: 100%;
            height: auto;
            margin: 15px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>Documentación - Generador de Mapas de Calor para Calibración de Cámaras</h1>

    <div class="note">
        <p>Esta herramienta genera mapas de calor que muestran la cobertura del patrón de damero en imágenes de calibración, permitiendo verificar la distribución de las imágenes antes del cálculo de distorsión.</p>
    </div>

    <h2>Instrucciones de Uso</h2>

    <h3>1. Configuración Inicial</h3>
    <p>Al abrir la aplicación, seleccione el modo de operación:</p>
    <ul>
        <li><strong>Carpeta única:</strong> Para procesar imágenes de una sola cámara</li>
        <li><strong>Carpeta con subcarpetas:</strong> Para procesar múltiples cámaras organizadas en subcarpetas</li>
    </ul>

    <h3>2. Selección de Carpeta</h3>
    <p>Haga clic en "Examinar..." para seleccionar la carpeta que contiene:</p>
    <ul>
        <li>Las imágenes directamente (modo carpeta única)</li>
        <li>Subcarpetas por cámara (modo múltiple)</li>
    </ul>

    <h3>3. Parámetros de Configuración</h3>
    <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse;">
        <tr>
            <th>Parámetro</th>
            <th>Descripción</th>
            <th>Valor Típico</th>
        </tr>
        <tr>
            <td>Tamaño del damero</td>
            <td>Número de esquinas interiores (ancho x alto)</td>
            <td>10x7</td>
        </tr>
        <tr>
            <td>Resolución de imagen</td>
            <td>Resolución nativa de la cámara (ancho x alto)</td>
            <td>4096x3000</td>
        </tr>
    </table>

    <h3>4. Procesamiento</h3>
    <ol>
        <li>Haga clic en "Generar Mapa(s) de Calor"</li>
        <li>Espere a que complete el procesamiento (barra de progreso)</li>
        <li>Revise los resultados en la ventana interactiva</li>
    </ol>

    <div class="warning">
        <p><strong>Nota:</strong> Para cancelar el procesamiento, use el botón "Cancelar". Esto detendrá la operación después de terminar la imagen actual.</p>
    </div>

    <h2>Interpretación de Resultados</h2>

    <h3>Mapa de Calor Interactivo</h3>
    <ul>
        <li><strong>Panel izquierdo:</strong> Muestra el mapa de calor combinado</li>
        <li><strong>Panel derecho:</strong> Lista de imágenes procesadas (puede seleccionar/deseleccionar)</li>
        <li><strong>Escala de colores:</strong>
            <ul>
                <li>Azul: Zonas con poca cobertura</li>
                <li>Rojo: Zonas con alta cobertura</li>
            </ul>
        </li>
    </ul>

    <h3>Galería (Modo Múltiple)</h3>
    <p>Muestra miniaturas de todos los mapas generados. Haga doble clic en cualquier miniatura para abrir el visor detallado.</p>

    <h2>Requisitos y Compatibilidad</h2>
    <ul>
        <li><strong>Sistemas operativos:</strong> Windows 10/11 (64-bit)</li>
        <li><strong>Formatos soportados:</strong> JPG, JPEG, PNG, BMP, TIFF</li>
        <li><strong>Estructura de carpetas (modo múltiple):</strong>
            <pre>
Carpeta_Principal/
├── Camara_1/
│   ├── img1.jpg
│   └── img2.jpg
└── Camara_2/
    ├── img1.jpg
    └── img2.jpg</pre>
        </li>
    </ul>

    <h2>Solución de Problemas</h2>

    <h3>Problemas Comunes</h3>
    <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse; margin-bottom: 20px;">
        <tr>
            <th>Problema</th>
            <th>Solución</th>
        </tr>
        <tr>
            <td>Imágenes no detectadas</td>
            <td>Verifique que estén en la carpeta correcta y con formatos compatibles</td>
        </tr>
        <tr>
            <td>Procesamiento lento</td>
            <td>Active "Optimizar rendimiento" o reduzca el tamaño de las imágenes</td>
        </tr>
        <tr>
            <td>Mapa de calor vacío</td>
            <td>Revise el tamaño del damero y que las imágenes contengan el patrón completo</td>
        </tr>
        <tr>
            <td>Error al guardar</td>
            <td>Verifique permisos de escritura en la carpeta de destino</td>
        </tr>
    </table>

    <div class="note">
        <p><strong>Nota final:</strong> La aplicación no modifica las imágenes originales. Todos los resultados se guardan como nuevos archivos PNG en la carpeta de origen.</p>
    </div>
</body>
</html>
