import cv2
import numpy as np
import os
import glob
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor, as_completed

# --- CONFIGURACIÓN ---
CHESSBOARD_SIZE = (10, 7)  # Esquinas interiores del damero
IMAGES_PATH = './fotos_calibracion'
OUTPUT_IMAGE_PATH = './mapa_cobertura.png'
IMAGE_RESOLUTION = (4096, 3000)
# --- FIN CONFIGURACIÓN ---

def procesar_imagen(filename, chessboard_size, image_resolution, criteria):
    """
    Procesa una única imagen para encontrar el damero y devuelve una máscara de su área.
    Esta función está diseñada para ser ejecutada en un proceso separado.
    """
    img = cv2.imread(filename)
    if img is None:
        print(f"  - Advertencia: No se pudo leer la imagen: {os.path.basename(filename)}")
        return None, filename

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK
    ret, corners = cv2.findChessboardCorners(gray, chessboard_size, flags=flags)

    if not ret:
        return None, filename

    corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    # Usar convexHull es más robusto que seleccionar las 4 esquinas manualmente
    hull = cv2.convexHull(corners_subpix)
    mask = np.zeros((image_resolution[1], image_resolution[0]), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32(hull), 1)

    return mask.astype(np.float32), filename

def crear_mapa_de_cobertura():
    heatmap = np.zeros((IMAGE_RESOLUTION[1], IMAGE_RESOLUTION[0]), dtype=np.float32)
    
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    image_files = glob.glob(os.path.join(IMAGES_PATH, '*.jpg')) + \
                  glob.glob(os.path.join(IMAGES_PATH, '*.png')) + \
                  glob.glob(os.path.join(IMAGES_PATH, '*.bmp'))

    if not image_files:
        print(f"Error: No se encontraron imágenes en la carpeta '{IMAGES_PATH}'.")
        return

    print(f"Procesando {len(image_files)} imágenes...")

    # Usamos un ProcessPoolExecutor para procesar las imágenes en paralelo
    with ProcessPoolExecutor() as executor:
        # Enviamos todos los trabajos a la piscina de procesos
        futures = [executor.submit(procesar_imagen, f, CHESSBOARD_SIZE, IMAGE_RESOLUTION, criteria) for f in image_files]
        
        # A medida que cada trabajo termina, procesamos su resultado
        for future in as_completed(futures):
            mask, filename = future.result()
            if mask is not None:
                heatmap += mask
                print(f"  - Damero encontrado en: {os.path.basename(filename)}")
            else:
                print(f"  - No se pudo encontrar el damero en: {os.path.basename(filename)}")

    # Normalizar y colorear el mapa de calor final
    heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
    cv2.imwrite(OUTPUT_IMAGE_PATH, color_map)
    print(f"\n✅ Mapa de calor guardado en: {OUTPUT_IMAGE_PATH}")

    # Mostrar con matplotlib (una sola ventana)
    plt.figure(figsize=(10, 6))
    plt.imshow(cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB))
    plt.title("Mapa de Calor de Cobertura del Damero")
    plt.axis('off')
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    crear_mapa_de_cobertura()
