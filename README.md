Documentación para la Aplicación de Generación de Mapas de Calor
Propósito de la Aplicación
Esta herramienta genera mapas de calor que muestran la cobertura del patrón de damero en imágenes de calibración de cámaras. Ayuda a verificar si las imágenes capturadas cubren adecuadamente el campo de visión antes de realizar el cálculo de distorsión.

Instrucciones de Uso
Selección de Carpeta

Carpeta Única: Usa cuando todas las imágenes sean de una misma cámara.

Carpeta con Subcarpetas: Usa cuando tengas imágenes organizadas en subcarpetas por cámara.

Haz clic en "Examinar..." para seleccionar la carpeta con las imágenes.

Configuración

Tamaño del Damero: Número de esquinas interiores del patrón (ej: 10x7).

Resolución de Imagen: Resolución nativa de las imágenes (ej: 4096x3000).

Opciones:

Guardar mapas individuales: Genera un mapa para cada cámara.

Mostrar gráficos: Muestra los mapas interactivos.

Optimizar rendimiento: Acelera el procesamiento.

Generación del Mapa

Haz clic en "Generar Mapa(s) de Calor".

La barra de progreso mostrará el avance.

Usa "Cancelar" para detener el procesamiento.

Resultados

Mapa de Calor Interactivo:

Selecciona/deselecciona imágenes en el panel derecho.

El mapa se actualiza en tiempo real.

Guarda el mapa con el botón correspondiente.

Galería (Modo Múltiple):

Vista previa de todos los mapas generados.

Doble clic para abrir un mapa en detalle.

Requisitos Técnicos
Formatos de Imagen Soportados: JPG, JPEG, PNG, BMP, TIFF.

Estructura de Carpetas (Modo Múltiple):

text
Carpeta_Principal/
  ├── Camara_1/
  │   ├── img1.jpg
  │   └── img2.jpg
  └── Camara_2/
      ├── img1.jpg
      └── img2.jpg
Solución de Problemas Comunes
Imágenes no detectadas:

Verifica que estén en la carpeta correcta.

Asegúrate de usar formatos compatibles.

Procesamiento lento:

Activa "Optimizar rendimiento".

Reduce la resolución si las imágenes son muy grandes.

Mapa vacío:

Revisa el tamaño del damero.

Asegúrate de que las imágenes contengan el patrón completo.

Salida
Los mapas se guardan como archivos PNG en la carpeta de origen con el nombre mapa_calor_[nombre_cámara].png.

El mapa de calor usa una escala de colores:

Azul: Zonas con poca cobertura.

Rojo: Zonas con alta cobertura.

Notas Importantes
El historial de carpetas se guarda automáticamente.

Usa "Limpiar Historial" para borrar carpetas anteriores.

La aplicación no modifica las imágenes originales.

Esta documentación permite a los usuarios utilizar la herramienta sin necesidad de acceder al código fuente.
