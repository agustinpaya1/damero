import cv2
import numpy as np
import os
from datetime import datetime
try:
    from pypylon import pylon
    PYLON_AVAILABLE = True
except ImportError:
    PYLON_AVAILABLE = False
    print("PyPylon no disponible. Usando cámara web como alternativa.")

class CalibrationViewer:
    def __init__(self, grid_rows=3, grid_cols=4, save_folder="calibration_images"):
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.save_folder = save_folder
        self.capture_count = 0
        self.grid_coverage = np.zeros((grid_rows, grid_cols), dtype=int)
        
        # Crear carpeta para guardar imágenes
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        
        # Configurar cámara
        self.camera = None
        self.converter = None
        self.setup_camera()
    
    def setup_camera(self):
        """Configurar cámara Basler o webcam como fallback"""
        global PYLON_AVAILABLE
        
        if PYLON_AVAILABLE:
            try:
                # Configurar cámara Basler
                self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
                self.camera.Open()
                
                # Configurar parámetros básicos
                self.camera.Width.SetValue(self.camera.Width.GetMax())
                self.camera.Height.SetValue(self.camera.Height.GetMax())
                
                # Configurar para captura continua
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                
                # Converter para formato OpenCV
                self.converter = pylon.ImageFormatConverter()
                self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
                
                print("Cámara Basler conectada exitosamente")
                return True
                
            except Exception as e:
                print(f"Error conectando cámara Basler: {e}")
                print("Usando webcam como alternativa...")
                PYLON_AVAILABLE = False
        
        # Usar webcam como alternativa
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            raise Exception("No se pudo abrir ninguna cámara")
        
        # Configurar resolución máxima
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        print("Webcam conectada exitosamente")
        return True
    
    def capture_frame(self):
        """Capturar frame de la cámara"""
        global PYLON_AVAILABLE
        
        if PYLON_AVAILABLE and self.camera:
            try:
                grabResult = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                
                if grabResult.GrabSucceeded():
                    # Convertir a formato OpenCV
                    image = self.converter.Convert(grabResult)
                    img = image.GetArray()
                    grabResult.Release()
                    return img
                else:
                    grabResult.Release()
                    return None
                    
            except Exception as e:
                print(f"Error capturando frame Basler: {e}")
                return None
        else:
            # Usar webcam
            ret, frame = self.camera.read()
            return frame if ret else None
    
    def draw_grid_overlay(self, img):
        """Dibujar rejilla superpuesta en la imagen"""
        h, w = img.shape[:2]
        
        # Calcular dimensiones de cada celda
        cell_width = w // self.grid_cols
        cell_height = h // self.grid_rows
        
        # Crear copia para overlay
        overlay = img.copy()
        
        # Dibujar líneas de la rejilla
        for i in range(1, self.grid_rows):
            y = i * cell_height
            cv2.line(overlay, (0, y), (w, y), (0, 255, 0), 2)
        
        for j in range(1, self.grid_cols):
            x = j * cell_width
            cv2.line(overlay, (x, 0), (x, h), (0, 255, 0), 2)
        
        # Dibujar marco exterior
        cv2.rectangle(overlay, (0, 0), (w-1, h-1), (0, 255, 0), 3)
        
        # Mostrar cobertura de cada celda
        for i in range(self.grid_rows):
            for j in range(self.grid_cols):
                x = j * cell_width + cell_width // 2
                y = i * cell_height + cell_height // 2
                
                count = self.grid_coverage[i, j]
                color = (0, 255, 0) if count >= 2 else (0, 255, 255) if count == 1 else (0, 0, 255)
                
                # Círculo indicador
                cv2.circle(overlay, (x, y), 15, color, -1)
                
                # Número de capturas
                cv2.putText(overlay, str(count), (x-8, y+5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        return overlay
    
    def detect_checkerboard_region(self, img):
        """Detectar en qué región de la rejilla está el damero"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detectar esquinas del damero (10x7)
        ret, corners = cv2.findChessboardCorners(gray, (10, 7), None)
        
        if ret:
            # Calcular centro del damero
            center = np.mean(corners, axis=0)[0]
            
            # Determinar qué celda de la rejilla contiene el centro
            h, w = img.shape[:2]
            cell_width = w // self.grid_cols
            cell_height = h // self.grid_rows
            
            grid_x = int(center[0] // cell_width)
            grid_y = int(center[1] // cell_height)
            
            # Asegurar que esté dentro de los límites
            grid_x = max(0, min(grid_x, self.grid_cols - 1))
            grid_y = max(0, min(grid_y, self.grid_rows - 1))
            
            return grid_y, grid_x, corners
        
        return None, None, None
    
    def save_image(self, img, grid_y, grid_x):
        """Guardar imagen con información de la región"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"calib_{self.capture_count:03d}_r{grid_y}c{grid_x}_{timestamp}.png"
        filepath = os.path.join(self.save_folder, filename)
        
        cv2.imwrite(filepath, img)
        self.capture_count += 1
        
        print(f"Imagen guardada: {filename} (Región: {grid_y},{grid_x})")
        return filepath
    
    def show_instructions(self, img):
        """Mostrar instrucciones en pantalla"""
        instructions = [
            "CALIBRACION DE CAMARAS - GUIA:",
            "ESPACIO: Capturar imagen",
            "R: Reiniciar contadores",
            "Q/ESC: Salir",
            "",
            f"Imagenes capturadas: {self.capture_count}",
            "Verde: 2+ capturas, Amarillo: 1 captura, Rojo: 0 capturas"
        ]
        
        # Fondo semi-transparente
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (500, 200), (0, 0, 0), -1)
        img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)
        
        # Texto de instrucciones
        for i, instruction in enumerate(instructions):
            cv2.putText(img, instruction, (20, 30 + i * 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return img
    
    def run(self):
        """Ejecutar el visor de calibración"""
        print("Iniciando visor de calibración...")
        print("Controles:")
        print("  ESPACIO: Capturar imagen")
        print("  R: Reiniciar contadores de región")
        print("  Q o ESC: Salir")
        
        while True:
            # Capturar frame
            frame = self.capture_frame()
            if frame is None:
                continue
            
            # Detectar damero y región
            grid_y, grid_x, corners = self.detect_checkerboard_region(frame)
            
            # Dibujar rejilla
            display_frame = self.draw_grid_overlay(frame)
            
            # Dibujar esquinas del damero si se detecta
            if corners is not None:
                cv2.drawChessboardCorners(display_frame, (10, 7), corners, True)
                
                # Resaltar región actual
                h, w = frame.shape[:2]
                cell_width = w // self.grid_cols
                cell_height = h // self.grid_rows
                
                x1 = grid_x * cell_width
                y1 = grid_y * cell_height
                x2 = (grid_x + 1) * cell_width
                y2 = (grid_y + 1) * cell_height
                
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 0, 0), 4)
            
            # Mostrar instrucciones
            display_frame = self.show_instructions(display_frame)
            
            # Mostrar frame
            cv2.imshow('Calibracion de Camaras - Visor con Rejilla', display_frame)
            
            # Manejar teclas
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # Q o ESC
                break
            elif key == ord(' '):  # ESPACIO - capturar
                if corners is not None:
                    self.save_image(frame, grid_y, grid_x)
                    self.grid_coverage[grid_y, grid_x] += 1
                else:
                    print("No se detectó damero. Asegúrate de que esté visible.")
            elif key == ord('r'):  # R - reiniciar
                self.grid_coverage = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
                print("Contadores de región reiniciados")
        
        self.cleanup()
    
    def cleanup(self):
        """Limpiar recursos"""
        global PYLON_AVAILABLE
        
        if PYLON_AVAILABLE and self.camera:
            self.camera.StopGrabbing()
            self.camera.Close()
        elif self.camera:
            self.camera.release()
        
        cv2.destroyAllWindows()
        
        # Mostrar resumen
        print(f"\nResumen de calibración:")
        print(f"Total de imágenes capturadas: {self.capture_count}")
        print(f"Cobertura por región:")
        for i in range(self.grid_rows):
            for j in range(self.grid_cols):
                print(f"  Región ({i},{j}): {self.grid_coverage[i,j]} imágenes")

def main():
    # Configurar el visor
    # Puedes cambiar grid_rows y grid_cols según tus necesidades
    viewer = CalibrationViewer(grid_rows=3, grid_cols=4, save_folder="calibration_images")
    
    try:
        viewer.run()
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario")
        viewer.cleanup()
    except Exception as e:
        print(f"Error: {e}")
        viewer.cleanup()

if __name__ == "__main__":
    main()