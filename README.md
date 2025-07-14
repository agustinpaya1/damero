# Documentación de la Aplicación de Mapa de Calor para Calibración de Cámaras

## Descripción General

Esta aplicación permite visualizar qué parte de un patrón de damero ha sido completada antes de procesar las imágenes para calcular la distorsión de cada cámara. La herramienta genera un mapa de calor que muestra las áreas del damero que han sido capturadas en las imágenes.

## Requisitos del Sistema

- Windows 10 o superior
- Python 3.8 o superior (solo para desarrollo, no necesario para el .exe)
- OpenCV
- NumPy
- Matplotlib
- Tkinter

## Instalación

1. Descargue el archivo `HeatmapApp.exe` desde la ubicación proporcionada.
2. Guarde el archivo en una carpeta de su elección.
3. Ejecute el archivo `HeatmapApp.exe` para iniciar la aplicación.

## Uso de la Aplicación

### Interfaz Principal

La interfaz principal de la aplicación consta de las siguientes secciones:

1. **Modo de Procesamiento**: Seleccione entre "Carpeta única (una cámara)" o "Carpeta con subcarpetas (múltiples cámaras)".
2. **Seleccionar Carpeta**: Seleccione la carpeta que contiene las imágenes del damero.
3. **Configuración**: Configure el tamaño del damero y la resolución de la imagen.
4. **Botones de Acción**: Generar mapa de calor, limpiar historial y cancelar procesamiento.
5. **Barra de Progreso**: Muestra el progreso del procesamiento.
6. **Log de Procesamiento**: Muestra los mensajes de log durante el procesamiento.

### Pasos para Generar un Mapa de Calor

1. **Seleccionar el Modo de Procesamiento**:
   - **Carpeta única**: Para procesar imágenes de una sola cámara.
   - **Carpeta con subcarpetas**: Para procesar imágenes de múltiples cámaras, donde cada subcarpeta representa una cámara diferente.

2. **Seleccionar la Carpeta**:
   - Haga clic en el botón "Examinar..." para seleccionar la carpeta que contiene las imágenes.
   - La carpeta seleccionada aparecerá en el cuadro de texto y se actualizará la información de la carpeta.

3. **Configurar Parámetros**:
   - **Tamaño del damero**: Introduzca el número de esquinas interiores del damero (por ejemplo, 10x7).
   - **Resolución de imagen**: Introduzca la resolución de las imágenes (por ejemplo, 4096x3000).

4. **Generar Mapa de Calor**:
   - Haga clic en el botón "Generar Mapa(s) de Calor" para iniciar el procesamiento.
   - El progreso se mostrará en la barra de progreso y en el log de procesamiento.

5. **Visualizar Resultados**:
   - Una vez completado el procesamiento, se abrirá una ventana con el mapa de calor interactivo.
   - En el modo de múltiples cámaras, se abrirá una galería con miniaturas de los mapas de calor de cada cámara.

### Mapa de Calor Interactivo

La ventana del mapa de calor interactivo permite:

- **Seleccionar/Desseleccionar Imágenes**: Use las casillas de verificación para seleccionar o deseccionar imágenes individuales.
- **Guardar Mapa**: Haga clic en el botón "Guardar Mapa" para guardar el mapa de calor actual.
- **Cerrar**: Haga clic en el botón "Cerrar" para cerrar la ventana.

### Galería de Mapas de Calor

En el modo de múltiples cámaras, se abrirá una galería con miniaturas de los mapas de calor de cada cámara. Haga doble clic en una miniatura para abrir el mapa de calor interactivo de esa cámara.

## Configuración Avanzada

- **Guardar mapas individuales**: Marque esta opción para guardar mapas de calor individuales para cada imagen.
- **Mostrar gráficos**: Marque esta opción para mostrar gráficos durante el procesamiento.
- **Optimizar rendimiento**: Marque esta opción para optimizar el rendimiento durante el procesamiento.

## Solución de Problemas

- **Error al cargar imágenes**: Asegúrese de que las imágenes estén en un formato compatible (JPG, JPEG, PNG, BMP, TIFF) y que la carpeta seleccionada contenga imágenes válidas.
- **Problemas de rendimiento**: Si la aplicación se ejecuta lentamente, asegúrese de que la opción "Optimizar rendimiento" esté marcada y reduzca el tamaño de las imágenes si es posible.

## Contacto

Para cualquier problema o pregunta, póngase en contacto con el departamento de soporte técnico de la empresa.

---

Esta documentación proporciona una guía básica para el uso de la aplicación. Para obtener más información detallada, consulte el código fuente o póngase en contacto con el desarrollador.
