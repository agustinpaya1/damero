import cv2
import numpy as np
import os
import glob
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading
from datetime import datetime
import gc
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk
import concurrent.futures
import queue
import math

# --- CONFIGURACIÓN ---
CHESSBOARD_SIZE = (10, 7)  # Esquinas interiores del damero
IMAGE_RESOLUTION = (4096, 3000)
MAX_WORKERS = 8  # Número máximo de hilos para procesamiento concurrente
REDUCED_RESOLUTION = (1024, 768)  # Resolución reducida para procesamiento interno
# --- FIN CONFIGURACIÓN ---

class HeatmapViewer(tk.Toplevel):
    def __init__(self, parent, initial_heatmap, polygons_info, camera_name, output_path, image_resolution, show_plots=True):
        super().__init__(parent)
        self.title(f"Mapa de Calor Interactivo - {camera_name}")
        self.geometry("1200x800")
        
        self.initial_heatmap = initial_heatmap
        self.polygons_info = polygons_info  # (filename, polygon, bbox, centroid)
        self.camera_name = camera_name
        self.output_path = output_path
        self.image_resolution = image_resolution
        self.show_plots = show_plots
        self.hover_info = None
        self.hover_rect = None
        self.hover_text = None
        self.current_highlight = None
        
        # Estado de selección
        self.selected = [True] * len(polygons_info)
        self.current_heatmap = np.copy(initial_heatmap)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel de la imagen
        img_frame = ttk.Frame(main_frame)
        img_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Figura de matplotlib
        self.fig = Figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=img_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Configurar eventos de ratón
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        
        # Frame para información de hover
        self.hover_frame = ttk.Frame(img_frame)
        self.hover_frame.pack(fill=tk.X, pady=(5, 0))
        self.hover_label = ttk.Label(self.hover_frame, text="Pase el ratón sobre el mapa para ver detalles", font=("Arial", 9))
        self.hover_label.pack()
        
        # Actualizar imagen inicial
        self.update_heatmap_display()
        
        # Panel lateral
        side_frame = ttk.Frame(main_frame, width=300)
        side_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))
        
        # Título
        ttk.Label(side_frame, text="Imágenes Procesadas", font=('Arial', 12, 'bold')).pack(pady=(0,10))
        
        # Frame para la lista de checkboxes con scrollbar
        list_container = ttk.Frame(side_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas para las checkboxes
        self.checkbox_canvas = tk.Canvas(list_container, yscrollcommand=scrollbar.set)
        self.checkbox_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.checkbox_canvas.yview)
        
        # Frame dentro del canvas para las checkboxes
        self.checkbox_frame = ttk.Frame(self.checkbox_canvas)
        self.checkbox_canvas_window = self.checkbox_canvas.create_window((0,0), window=self.checkbox_frame, anchor=tk.NW)
        
        # Botones
        btn_frame = ttk.Frame(side_frame)
        btn_frame.pack(fill=tk.X, pady=(10,0))
        
        save_btn = ttk.Button(btn_frame, text="Guardar Mapa", command=self.save_heatmap)
        save_btn.pack(side=tk.LEFT, padx=(0,5))
        
        save_selection_btn = ttk.Button(btn_frame, text="Guardar Selección", command=self.save_selected_images)
        save_selection_btn.pack(side=tk.LEFT, padx=(0,5))

        close_btn = ttk.Button(btn_frame, text="Cerrar", command=self.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        # Configurar eventos
        self.checkbox_frame.bind("<Configure>", self.on_frame_configure)
        self.checkbox_canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Crear checkboxes numeradas
        self.checkboxes = []
        for i, (filename, _, _, _) in enumerate(self.polygons_info):
            var = tk.BooleanVar(value=True)
            
            # Crear frame para cada elemento de la lista
            item_frame = ttk.Frame(self.checkbox_frame)
            item_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Número de imagen
            num_label = ttk.Label(item_frame, text=f"{i+1}.", width=3, anchor=tk.E)
            num_label.pack(side=tk.LEFT, padx=(0, 5))
            
            # Checkbox
            chk = ttk.Checkbutton(
                item_frame, 
                text=os.path.basename(filename), 
                variable=var,
                command=lambda idx=i: self.on_checkbox_change(idx)
            )
            chk.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Botón para resaltar esta imagen en el mapa
            highlight_btn = ttk.Button(item_frame, text="🔍", width=2,
                                     command=lambda idx=i: self.highlight_image(idx))
            highlight_btn.pack(side=tk.RIGHT, padx=(5,0))
            
            self.checkboxes.append(var)
            
    def save_selected_images(self):
        import shutil
        from tkinter import messagebox

        # Crear carpeta "seleccionadas" junto al output actual
        out_dir = os.path.join(os.path.dirname(self.output_path), "seleccionadas")
        os.makedirs(out_dir, exist_ok=True)

        saved = 0
        for i, selected in enumerate(self.checkboxes):
            if selected.get():
                image_path = self.polygons_info[i][0]  # ruta original de la imagen
                dest_path = os.path.join(out_dir, os.path.basename(image_path))
                shutil.copy(image_path, dest_path)
                saved += 1

        messagebox.showinfo("Guardado", f"{saved} imágenes guardadas en:\n{out_dir}")
        
    def on_frame_configure(self, event):
        self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))
        
    def on_canvas_configure(self, event):
        canvas_width = event.width
        self.checkbox_canvas.itemconfig(self.checkbox_canvas_window, width=canvas_width)
            
    def on_checkbox_change(self, index):
        self.selected[index] = self.checkboxes[index].get()
        self.update_heatmap(index)  # Pasar el índice como parámetro
        
    # Añadir parámetro 'index' a la función
    def update_heatmap(self, index):
        # Actualizar solo el área afectada para mejorar rendimiento
        _, polygon, bbox, _ = self.polygons_info[index]
        
        # Crear máscara solo para el área del bounding box
        x_min, y_min, x_max, y_max = bbox
        width = x_max - x_min + 1
        height = y_max - y_min + 1
        
        # Si el área es demasiado grande, usar solo el polígono
        if width * height > 1000000:  # 1M píxeles
            mask = np.zeros(self.image_resolution[::-1], dtype=np.float32)
            cv2.fillConvexPoly(mask, polygon, 1.0)
            if self.selected[index]:
                self.current_heatmap += mask
            else:
                self.current_heatmap -= mask
        else:
            # Crear máscara solo para el área del bounding box
            local_mask = np.zeros((height, width), dtype=np.float32)
            local_polygon = polygon.copy()
            local_polygon[:, :, 0] -= x_min
            local_polygon[:, :, 1] -= y_min
            cv2.fillConvexPoly(local_mask, local_polygon, 1.0)
            
            # Actualizar solo la región relevante
            if self.selected[index]:
                self.current_heatmap[y_min:y_max+1, x_min:x_max+1] += local_mask
            else:
                self.current_heatmap[y_min:y_max+1, x_min:x_max+1] -= local_mask
        
        self.update_heatmap_display()
        
    def update_heatmap_display(self):
        heatmap_normalized = cv2.normalize(self.current_heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        self.color_map_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
        
        self.ax.clear()
        self.ax.imshow(self.color_map_rgb)
        
        # Mostrar números de imagen si hay menos de 50
        if len(self.polygons_info) <= 50:
            for i, (_, _, _, centroid) in enumerate(self.polygons_info):
                if self.selected[i]:
                    center_x, center_y = centroid
                    self.ax.text(center_x, center_y, str(i+1), 
                                color='white', fontsize=8, 
                                ha='center', va='center',
                                bbox=dict(facecolor='black', alpha=0.5, boxstyle='round,pad=0.2'))
        
        self.ax.set_title(f"Mapa de Calor - {self.camera_name}\n{np.count_nonzero(self.selected)}/{len(self.polygons_info)} imágenes seleccionadas")
        self.ax.axis('off')
        self.fig.tight_layout()
        self.canvas.draw()
        
    def save_heatmap(self):
        heatmap_normalized = cv2.normalize(self.current_heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        cv2.imwrite(self.output_path, color_map)
        messagebox.showinfo("Guardado", f"Mapa de calor guardado en:\n{self.output_path}")
    
    def highlight_image(self, index):
        """Resalta una imagen específica en el mapa de calor"""
        filename, polygon, _, centroid = self.polygons_info[index]
        
        # Crear una copia del mapa de calor actual
        highlight_map = np.copy(self.color_map_rgb)
        
        # Crear máscara temporal para esta imagen
        mask = np.zeros(self.image_resolution[::-1], dtype=np.uint8)
        cv2.fillConvexPoly(mask, polygon, 1)
        
        # Encontrar contornos de la máscara
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Dibujar contorno rojo alrededor del área
        cv2.drawContours(highlight_map, contours, -1, (255, 0, 0), 20)
        
        # Actualizar la visualización
        self.ax.clear()
        self.ax.imshow(highlight_map)
        
        # Mostrar información
        self.ax.set_title(f"Imagen resaltada: #{index+1} - {os.path.basename(filename)}")
        self.ax.axis('off')
        self.fig.tight_layout()
        self.canvas.draw()
        
        # Guardar referencia para poder quitarlo
        self.current_highlight = index
        
        # Configurar para volver al mapa completo después de 3 segundos
        self.after(3000, self.remove_highlight)
    
    def remove_highlight(self):
        """Vuelve a mostrar el mapa de calor completo"""
        if self.current_highlight is not None:
            self.update_heatmap_display()
            self.current_highlight = None
    
    def on_hover(self, event):
        """Muestra información cuando el ratón pasa sobre una imagen en el mapa"""
        if event.inaxes == self.ax:
            x, y = int(event.xdata), int(event.ydata)
            
            # Buscar qué imágenes cubren este píxel
            covering_images = []
            for i, (filename, polygon, bbox, _) in enumerate(self.polygons_info):
                if self.selected[i]:
                    # Primero verificar el bounding box para optimización
                    x_min, y_min, x_max, y_max = bbox
                    if x_min <= x <= x_max and y_min <= y <= y_max:
                        # Luego verificar el polígono
                        if cv2.pointPolygonTest(polygon, (x, y), False) >= 0:
                            covering_images.append((i+1, filename))
            
            if covering_images:
                # Crear texto informativo
                if len(covering_images) == 1:
                    img_num, filename = covering_images[0]
                    text = f"Imagen #{img_num}: {os.path.basename(filename)}"
                else:
                    nums = ", ".join([f"#{num}" for num, _ in covering_images[:3]])
                    if len(covering_images) > 3:
                        nums += f" y {len(covering_images)-3} más"
                    text = f"Píxel cubierto por: {nums}"
                
                self.hover_label.config(text=text)
            else:
                self.hover_label.config(text="Pase el ratón sobre un área cubierta para ver detalles")
    
    def on_click(self, event):
        """Muestra la imagen completa cuando se hace clic en un área del mapa"""
        if event.inaxes == self.ax and event.button == 1:  # Botón izquierdo
            x, y = int(event.xdata), int(event.ydata)
            
            # Buscar la primera imagen que cubre este píxel
            for i, (filename, polygon, bbox, _) in enumerate(self.polygons_info):
                if self.selected[i]:
                    # Primero verificar el bounding box para optimización
                    x_min, y_min, x_max, y_max = bbox
                    if x_min <= x <= x_max and y_min <= y <= y_max:
                        # Luego verificar el polígono
                        if cv2.pointPolygonTest(polygon, (x, y), False) >= 0:
                            self.show_full_image(filename, i+1)
                            break
    
    def show_full_image(self, image_path, image_num):
        """Muestra la imagen original en una nueva ventana"""
        img = cv2.imread(image_path)
        if img is not None:
            # Convertir a RGB para visualización
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Crear ventana para mostrar la imagen
            img_window = tk.Toplevel(self)
            img_window.title(f"Imagen #{image_num}: {os.path.basename(image_path)}")
            
            # Redimensionar si es muy grande
            max_size = (800, 600)
            height, width = img_rgb.shape[:2]
            if width > max_size[0] or height > max_size[1]:
                scale = min(max_size[0]/width, max_size[1]/height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img_resized = cv2.resize(img_rgb, (new_width, new_height))
            else:
                img_resized = img_rgb
            
            # Convertir a formato Tkinter
            img_pil = Image.fromarray(img_resized)
            img_tk = ImageTk.PhotoImage(image=img_pil)
            
            # Mostrar imagen
            label = ttk.Label(img_window, image=img_tk)
            label.image = img_tk  # Mantener referencia
            label.pack(padx=10, pady=10)
            
            # Botón de cierre
            close_btn = ttk.Button(img_window, text="Cerrar", command=img_window.destroy)
            close_btn.pack(pady=(0, 10))


class HeatmapGallery(tk.Toplevel):
    """Clase para mostrar una galería de miniaturas de mapas de calor"""
    def __init__(self, parent, gallery_items, image_resolution, show_plots):
        super().__init__(parent)
        self.title("Galería de Mapas de Calor")
        self.geometry("1200x800")
        self.gallery_items = gallery_items
        self.image_resolution = image_resolution
        self.show_plots = show_plots
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Canvas con scroll
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Crear una cuadrícula de 3 columnas
        cols = 3
        for i, item in enumerate(self.gallery_items):
            row = i // cols
            col = i % cols
            frame = ttk.Frame(scrollable_frame, padding=10, relief="groove", borderwidth=1)
            frame.grid(row=row, column=col, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
            
            # Título con número de cámara
            label = ttk.Label(frame, text=f"Cámara #{i+1}: {item['camera_name']}", font=('Arial', 10, 'bold'))
            label.pack(pady=(0, 5))
            
            # Generar miniatura
            heatmap_normalized = cv2.normalize(item['heatmap'], None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
            img_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
            
            # Reducir tamaño para miniatura
            preview = cv2.resize(img_rgb, (300, 225))
            img_tk = self.convert_to_tk(preview)
            
            # Mostrar miniatura
            img_label = ttk.Label(frame, image=img_tk,cursor="hand2")
            img_label.image = img_tk  # mantener referencia
            img_label.pack()
            
            # Hacer clic sobre la miniatura para abrir visor
            img_label.bind("<Double-Button-1>", lambda e, item=item: self.open_heatmap_viewer(item))
        
            # Texto informativo
            info_label = ttk.Label(frame, text=f"{item['processed_count']}/{item['total_files']} imágenes")
            info_label.pack(pady=(5, 0))
    
    def convert_to_tk(self, img_rgb):
        """Convierte una imagen RGB a formato Tkinter"""
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(image=img_pil)
        return img_tk
    
    def open_heatmap_viewer(self, item):
        """Abre el visor interactivo para el mapa seleccionado"""
        HeatmapViewer(
            self.master, 
            item['heatmap'], 
            item['polygons_info'], 
            item['camera_name'], 
            item['output_path'], 
            self.image_resolution, 
            self.show_plots
        )


class HeatmapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Mapa de Calor - Calibración Multi-Cámara")
        self.root.geometry("1000x800")
        
        # Variables
        self.selected_folder = tk.StringVar()
        self.folders_history = []
        self.processing_mode = tk.StringVar(value="single")
        self.camera_folders = []
        
        # Cargar historial de carpetas
        self.load_folder_history()
        
        self.setup_ui()
        
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        title_label = ttk.Label(main_frame, text="Generador de Mapa de Calor Multi-Cámara", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Modo de procesamiento
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Procesamiento", padding="10")
        mode_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Radiobutton(mode_frame, text="Carpeta única (una cámara)", 
                       variable=self.processing_mode, value="single",
                       command=self.on_mode_change).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        
        ttk.Radiobutton(mode_frame, text="Carpeta con subcarpetas (múltiples cámaras)", 
                       variable=self.processing_mode, value="multi",
                       command=self.on_mode_change).grid(row=0, column=1, sticky=tk.W)
        
        # Selección de carpeta
        folder_frame = ttk.LabelFrame(main_frame, text="Seleccionar Carpeta", padding="10")
        folder_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Combobox para carpetas recientes
        ttk.Label(folder_frame, text="Carpeta:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.folder_combobox = ttk.Combobox(folder_frame, textvariable=self.selected_folder, 
                                           values=self.folders_history, width=70)
        self.folder_combobox.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Botón examinar
        browse_btn = ttk.Button(folder_frame, text="Examinar...", 
                               command=self.browse_folder)
        browse_btn.grid(row=1, column=1, padx=(0, 10))
        
        # Botón actualizar lista
        refresh_btn = ttk.Button(folder_frame, text="↻", width=3,
                                command=self.refresh_folder_info)
        refresh_btn.grid(row=1, column=2)
        
        # Información de la carpeta
        info_frame = ttk.Frame(folder_frame)
        info_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.info_text = tk.Text(info_frame, height=8, width=80, wrap=tk.WORD)
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar para el texto
        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text.config(yscrollcommand=scrollbar.set)
        
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        
        # Configuración
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding="10")
        config_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Tamaño del damero
        ttk.Label(config_frame, text="Tamaño del damero (esquinas interiores):").grid(row=0, column=0, sticky=tk.W)
        
        chess_frame = ttk.Frame(config_frame)
        chess_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        self.chess_width = tk.StringVar(value=str(CHESSBOARD_SIZE[0]))
        self.chess_height = tk.StringVar(value=str(CHESSBOARD_SIZE[1]))
        
        ttk.Entry(chess_frame, textvariable=self.chess_width, width=5).grid(row=0, column=0)
        ttk.Label(chess_frame, text="x").grid(row=0, column=1, padx=5)
        ttk.Entry(chess_frame, textvariable=self.chess_height, width=5).grid(row=0, column=2)
        
        # Resolución de imagen
        ttk.Label(config_frame, text="Resolución de imagen:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        res_frame = ttk.Frame(config_frame)
        res_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(10, 0))
        
        self.img_width = tk.StringVar(value=str(IMAGE_RESOLUTION[0]))
        self.img_height = tk.StringVar(value=str(IMAGE_RESOLUTION[1]))
        
        ttk.Entry(res_frame, textvariable=self.img_width, width=6).grid(row=0, column=0)
        ttk.Label(res_frame, text="x").grid(row=0, column=1, padx=5)
        ttk.Entry(res_frame, textvariable=self.img_height, width=6).grid(row=0, column=2)
        
        # Opciones adicionales
        options_frame = ttk.Frame(config_frame)
        options_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        self.save_individual = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Guardar mapas individuales", 
                       variable=self.save_individual).grid(row=0, column=0, sticky=tk.W)
        
        self.show_plots = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Mostrar gráficos", 
                       variable=self.show_plots).grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        self.optimize_performance = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Optimizar rendimiento", 
                       variable=self.optimize_performance).grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        self.save_debug_images = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Guardar imágenes de depuración", 
                       variable=self.save_debug_images).grid(row=1, column=1, sticky=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Control de sensibilidad de detección
        sensitivity_frame = ttk.Frame(config_frame)
        sensitivity_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        ttk.Label(sensitivity_frame, text="Sensibilidad de detección:").grid(row=0, column=0, sticky=tk.W)
        
        self.detection_sensitivity = tk.DoubleVar(value=3.0)
        sensitivity_scale = ttk.Scale(sensitivity_frame, from_=1.0, to=5.0, 
                                     variable=self.detection_sensitivity, 
                                     orient=tk.HORIZONTAL, length=200)
        sensitivity_scale.grid(row=0, column=1, padx=(10, 0))
        
        # Etiquetas para la escala
        ttk.Label(sensitivity_frame, text="Baja").grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        ttk.Label(sensitivity_frame, text="Alta").grid(row=1, column=1, sticky=tk.E)
        
        # Botones de acción
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=4, column=0, columnspan=3, pady=(0, 20))
        
        self.generate_btn = ttk.Button(action_frame, text="Generar Mapa(s) de Calor", 
                                      command=self.generate_heatmap_threaded, 
                                      style="Accent.TButton")
        self.generate_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_btn = ttk.Button(action_frame, text="Limpiar Historial", 
                              command=self.clear_history)
        clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.cancel_btn = ttk.Button(action_frame, text="Cancelar", 
                                    command=self.cancel_processing, state='disabled')
        self.cancel_btn.grid(row=0, column=2)
        
        # Barra de progreso
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="")
        self.progress_label.grid(row=0, column=1)
        
        progress_frame.columnconfigure(0, weight=1)
        
        # Log de procesamiento
        log_frame = ttk.LabelFrame(main_frame, text="Log de Procesamiento", padding="10")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        log_text_frame = ttk.Frame(log_frame)
        log_text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = tk.Text(log_text_frame, height=6, width=80, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        log_scrollbar = ttk.Scrollbar(log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
        log_text_frame.columnconfigure(0, weight=1)
        log_text_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Configurar columnas para que se expandan
        main_frame.columnconfigure(0, weight=1)
        folder_frame.columnconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Variables de control
        self.cancel_processing_flag = False
        self.processing_thread = None
        
        # Bind eventos
        self.folder_combobox.bind('<<ComboboxSelected>>', self.on_folder_selected)
        self.folder_combobox.bind('<Return>', self.on_folder_selected)
        
        # Actualizar información inicial
        if self.folders_history:
            self.selected_folder.set(self.folders_history[0])
            self.refresh_folder_info()
        
        self.on_mode_change()
    
    def on_mode_change(self):
        self.refresh_folder_info()
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta")
        if folder:
            self.selected_folder.set(folder)
            self.add_to_history(folder)
            self.refresh_folder_info()
    
    def on_folder_selected(self, event=None):
        self.refresh_folder_info()
    
    def refresh_folder_info(self):
        folder = self.selected_folder.get()
        if not folder or not os.path.exists(folder):
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, "Selecciona una carpeta válida...")
            self.generate_btn.config(state='disabled')
            return
        
        self.info_text.delete(1.0, tk.END)
        mode = self.processing_mode.get()
        
        if mode == "single":
            self.process_single_folder_info(folder)
        else:
            self.process_multi_folder_info(folder)
    
    def process_single_folder_info(self, folder):
        # Buscar imágenes en la carpeta
        image_files = self.find_images_in_folder(folder)
        
        self.info_text.insert(tk.END, f"📁 Modo: Carpeta única\n")
        self.info_text.insert(tk.END, f"📂 Carpeta: {folder}\n")
        
        if not image_files:
            self.info_text.insert(tk.END, f"❌ No se encontraron imágenes\n")
            self.generate_btn.config(state='disabled')
        else:
            self.info_text.insert(tk.END, f"📸 Imágenes encontradas: {len(image_files)}\n\n")
            
            # Mostrar algunas imágenes de ejemplo
            sample_files = image_files[:5]
            self.info_text.insert(tk.END, "Ejemplos de archivos:\n")
            for i, file in enumerate(sample_files):
                self.info_text.insert(tk.END, f"  • {os.path.basename(file)}\n")
            
            if len(image_files) > 5:
                self.info_text.insert(tk.END, f"  ... y {len(image_files) - 5} más\n")
            
            self.generate_btn.config(state='normal')
    
    def process_multi_folder_info(self, folder):
        # Buscar subcarpetas
        subfolders = [f for f in os.listdir(folder) 
                     if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
        
        self.info_text.insert(tk.END, f"📁 Modo: Múltiples cámaras\n")
        self.info_text.insert(tk.END, f"📂 Carpeta principal: {folder}\n")
        
        if not subfolders:
            self.info_text.insert(tk.END, f"❌ No se encontraron subcarpetas\n")
            self.generate_btn.config(state='disabled')
            return
        
        self.camera_folders = []
        total_images = 0
        
        self.info_text.insert(tk.END, f"📷 Subcarpetas encontradas: {len(subfolders)}\n\n")
        
        for subfolder in sorted(subfolders):
            subfolder_path = os.path.join(folder, subfolder)
            image_files = self.find_images_in_folder(subfolder_path)
            
            if image_files:
                self.camera_folders.append({
                    'name': subfolder,
                    'path': subfolder_path,
                    'images': image_files
                })
                total_images += len(image_files)
                
                self.info_text.insert(tk.END, f"📷 {subfolder}:\n")
                self.info_text.insert(tk.END, f"  └── {len(image_files)} imágenes\n")
            else:
                self.info_text.insert(tk.END, f"⚠️ {subfolder}:\n")
                self.info_text.insert(tk.END, f"  └── Sin imágenes válidas\n")
        
        if self.camera_folders:
            self.info_text.insert(tk.END, f"\n📊 Total: {len(self.camera_folders)} cámaras, {total_images} imágenes\n")
            self.generate_btn.config(state='normal')
        else:
            self.info_text.insert(tk.END, f"\n❌ No se encontraron carpetas con imágenes válidas\n")
            self.generate_btn.config(state='disabled')
    
    def find_images_in_folder(self, folder):
            image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff']
            image_files = []
            for ext in image_extensions:
                image_files.extend(glob.glob(os.path.join(folder, ext)))
                image_files.extend(glob.glob(os.path.join(folder, ext.upper())))
            
            # Eliminar duplicados usando rutas reales normalizadas
            unique_files = set()
            result = []
            for file_path in image_files:
                # Obtener la ruta real (resuelve enlaces simbólicos)
                real_path = os.path.realpath(file_path)
                # Normalizar la ruta para comparación consistente
                normalized_path = os.path.normcase(real_path)
                if normalized_path not in unique_files:
                    unique_files.add(normalized_path)
                    result.append(file_path)
            return result
    
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def generate_heatmap_threaded(self):
        """Ejecuta el procesamiento en un hilo separado"""
        self.cancel_processing_flag = False
        self.processing_thread = threading.Thread(target=self.generate_heatmap)
        self.processing_thread.daemon = True
        self.processing_thread.start()
    
    def cancel_processing(self):
        """Cancela el procesamiento"""
        self.cancel_processing_flag = True
        self.log_message("🛑 Cancelando procesamiento...")
    
    def generate_heatmap(self):
        folder = self.selected_folder.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Error", "Selecciona una carpeta válida")
            return
        
        try:
            # Obtener configuración
            chess_size = (int(self.chess_width.get()), int(self.chess_height.get()))
            img_resolution = (int(self.img_width.get()), int(self.img_height.get()))
            detection_sensitivity = self.detection_sensitivity.get()
            save_debug_images = self.save_debug_images.get()
            
            # Validar configuración
            if chess_size[0] <= 0 or chess_size[1] <= 0:
                raise ValueError("El tamaño del damero debe ser positivo")
            if img_resolution[0] <= 0 or img_resolution[1] <= 0:
                raise ValueError("La resolución de imagen debe ser positiva")
                
        except ValueError as e:
            messagebox.showerror("Error de configuración", f"Configuración inválida: {str(e)}")
            return
        
        # Actualizar historial
        self.add_to_history(folder)
        
        # Configurar UI para procesamiento
        self.generate_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_message(f"🔍 Sensibilidad de detección: {detection_sensitivity:.1f}")
        if save_debug_images:
            self.log_message("🔍 Guardando imágenes de depuración")
        
        try:
            mode = self.processing_mode.get()
            
            if mode == "single":
                self.process_single_camera(folder, chess_size, img_resolution, detection_sensitivity, save_debug_images)
            else:
                self.process_multiple_cameras(folder, chess_size, img_resolution, detection_sensitivity, save_debug_images)
                
        except Exception as e:
            self.log_message(f"❌ Error: {str(e)}")
            messagebox.showerror("Error", f"Error al generar el mapa de calor:\n{str(e)}")
        
        finally:
            self.generate_btn.config(state='normal')
            self.cancel_btn.config(state='disabled')
            self.progress.config(value=0)
            self.progress_label.config(text="")
    
    def process_single_camera(self, folder, chess_size, img_resolution, detection_sensitivity, save_debug_images):
        self.log_message("🎯 Procesando cámara única...")
        
        output_path = os.path.join(os.path.dirname(folder), f"mapa_calor_{os.path.basename(folder)}.png")
        
        success, heatmap, polygons_info, processed_count, total_files = self.crear_mapa_de_cobertura(
            folder, chess_size, img_resolution, output_path, "Cámara única", detection_sensitivity, save_debug_images
        )
        
        if success:
            # Guardar el mapa inicial
            heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
            cv2.imwrite(output_path, color_map)
            
            # Abrir visor interactivo
            self.open_heatmap_viewer(heatmap, polygons_info, "Cámara única", output_path, img_resolution)
            
            self.log_message(f"✅ Mapa de calor generado: {output_path}")
        else:
            self.log_message("❌ No se pudo procesar ninguna imagen válida")
            messagebox.showwarning("Advertencia", "No se pudo procesar ninguna imagen válida")
    
    def process_multiple_cameras(self, folder, chess_size, img_resolution, detection_sensitivity, save_debug_images):
        if not self.camera_folders:
            self.log_message("❌ No hay carpetas de cámaras para procesar")
            return
        
        self.log_message(f"🎯 Procesando {len(self.camera_folders)} cámaras...")
        
        total_cameras = len(self.camera_folders)
        successful_cameras = 0
        gallery_items = []  # Lista para almacenar los resultados para la galería
        
        for i, camera_info in enumerate(self.camera_folders):
            if self.cancel_processing_flag:
                self.log_message("🛑 Procesamiento cancelado por el usuario")
                break
                
            camera_name = camera_info['name']
            camera_path = camera_info['path']
            
            # Actualizar progreso
            progress = (i / total_cameras) * 100
            self.progress.config(value=progress)
            self.progress_label.config(text=f"Procesando {camera_name}...")
            self.root.update_idletasks()
            
            self.log_message(f"📷 Procesando cámara: {camera_name}")
            
            # Generar nombre de archivo de salida
            output_path = os.path.join(folder, f"mapa_calor_{camera_name}.png")
            
            success, heatmap, polygons_info, processed_count, total_files = self.crear_mapa_de_cobertura(
                camera_path, chess_size, img_resolution, output_path, camera_name, detection_sensitivity, save_debug_images
            )
            
            if success:
                # Guardar el mapa inicial
                heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
                cv2.imwrite(output_path, color_map)
                
                # Guardar datos para la galería
                gallery_items.append({
                    'camera_name': camera_name,
                    'heatmap': heatmap,
                    'polygons_info': polygons_info,
                    'output_path': output_path,
                    'processed_count': processed_count,
                    'total_files': total_files
                })
                
                successful_cameras += 1
                self.log_message(f"✅ {camera_name}: Completado")
            else:
                self.log_message(f"❌ {camera_name}: Sin imágenes válidas")
        
        # Progreso final
        self.progress.config(value=100)
        self.progress_label.config(text="Completado")
        
        if successful_cameras > 0:
            # Abrir la galería con todos los mapas de calor
            self.root.after(0, lambda: HeatmapGallery(
                self.root, 
                gallery_items, 
                img_resolution, 
                self.show_plots.get()
            ))
            
            self.log_message(f"🎉 Procesamiento completado: {successful_cameras}/{total_cameras} cámaras")
            messagebox.showinfo("Éxito", 
                f"Procesamiento completado exitosamente:\n"
                f"• {successful_cameras} de {total_cameras} cámaras procesadas\n"
                f"• Mapas guardados en: {folder}")
        else:
            self.log_message("❌ No se pudo procesar ninguna cámara")
            messagebox.showwarning("Advertencia", "No se pudo procesar ninguna cámara")
    
    def crear_mapa_de_cobertura(self, images_path, chessboard_size, image_resolution, output_path, camera_name, detection_sensitivity, save_debug_images):
        heatmap = np.zeros((image_resolution[1], image_resolution[0]), dtype=np.float32)
        polygons_info = []  # (filename, polygon, bbox, centroid)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        
        # Crear carpeta para imágenes de depuración si es necesario
        debug_folder = None
        if save_debug_images:
            debug_folder = os.path.join(os.path.dirname(output_path), f"debug_{os.path.basename(images_path)}")
            os.makedirs(debug_folder, exist_ok=True)
            self.log_message(f"📁 Carpeta de depuración: {debug_folder}")
        
        image_files = self.find_images_in_folder(images_path)
        total_files = len(image_files)
        if not image_files:
            return False, None, [], 0, 0
        
        processed_count = 0
        progress_lock = threading.Lock()  # Para actualizar progress de manera segura
        
        def procesar_imagen(filename):
            if self.cancel_processing_flag:
                return None
                
            img = cv2.imread(filename)
            if img is None:
                return None
            
            # Reducir la imagen para procesamiento
            original_height, original_width = img.shape[:2]
            scale_factor = min(REDUCED_RESOLUTION[0]/original_width, REDUCED_RESOLUTION[1]/original_height)
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)
            img_resized = cv2.resize(img, (new_width, new_height))
            
            # Mejoras en la detección del damero
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            # Usar el nivel de sensibilidad pasado como parámetro
            sensitivity = detection_sensitivity
            
            # Ajustar parámetros basados en la sensibilidad
            # Mayor sensibilidad = procesamiento más agresivo y más variantes
            blur_size = max(3, int(5 - sensitivity))
            clahe_clip = 2.0 + sensitivity / 2.0
            gamma_value = 1.0 + sensitivity / 5.0
            canny_threshold1 = int(70 - sensitivity * 10)
            canny_threshold2 = int(150 + sensitivity * 10)
            
            # Aplicar múltiples técnicas de preprocesamiento para mejorar la detección
            img_versions = []
            
            # Siempre incluir la imagen original
            img_versions.append(gray)
            
            # Versión 1: Ecualización de histograma con filtro gaussiano
            gray_eq = cv2.equalizeHist(gray)
            gray_eq_blur = cv2.GaussianBlur(gray_eq, (blur_size, blur_size), 1.0)
            img_versions.append(gray_eq_blur)
            
            # Versión 2: Filtro adaptativo para mejorar contraste local
            clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
            gray_clahe = clahe.apply(gray)
            gray_clahe_blur = cv2.GaussianBlur(gray_clahe, (blur_size, blur_size), 1.0)
            img_versions.append(gray_clahe_blur)
            
            # Versión 3: Ajuste de gamma para mejorar detalles en áreas oscuras
            gray_gamma = np.array(255 * (gray / 255) ** gamma_value, dtype='uint8')
            img_versions.append(gray_gamma)
            
            # Versión 4: Filtro bilateral para preservar bordes
            gray_bilateral = cv2.bilateralFilter(gray, 11, 17, 17)
            img_versions.append(gray_bilateral)
            
            # Versión 5: Detección de bordes con Canny + dilatación para conectar bordes
            edges = cv2.Canny(gray, canny_threshold1, canny_threshold2)
            kernel = np.ones((5, 5), np.uint8)
            edges_dilated = cv2.dilate(edges, kernel, iterations=1)
            img_versions.append(255 - edges_dilated)  # Invertir para que los bordes sean oscuros
            
            # Con alta sensibilidad, añadir versiones adicionales
            if sensitivity > 3.0:
                # Versión 6: Combinación de CLAHE y gamma
                gray_clahe_gamma = np.array(255 * (gray_clahe / 255) ** gamma_value, dtype='uint8')
                img_versions.append(gray_clahe_gamma)
                
                # Versión 7: Umbralización adaptativa
                gray_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                  cv2.THRESH_BINARY, 11, 2)
                img_versions.append(255 - gray_thresh)  # Invertir para que el damero sea oscuro
            
            # Configurar parámetros de detección más robustos
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | \
                    cv2.CALIB_CB_FILTER_QUADS | cv2.CALIB_CB_FAST_CHECK
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.000001)
            
            # Intentar detectar el damero en cada versión de la imagen
            ret = False
            corners = None
            
            for img_version in img_versions:
                if self.cancel_processing_flag:
                    return None
                    
                # Intentar con esta versión de la imagen
                ret_attempt, corners_attempt = cv2.findChessboardCorners(img_version, chessboard_size, flags=flags)
                
                if ret_attempt:
                    ret = True
                    corners = corners_attempt
                    break
            
            # Si no se detectó con ninguna versión, intentar con findChessboardCornersSB (más robusto pero más lento)
            if not ret:
                try:
                    # Este método es más robusto para dameros parcialmente visibles o con distorsión
                    ret, corners = cv2.findChessboardCornersSB(gray, chessboard_size, flags=flags)
                except:
                    # Si el método no está disponible (versiones antiguas de OpenCV), usar el método estándar una última vez
                    ret, corners = cv2.findChessboardCorners(gray, chessboard_size, flags=flags)
            
            if not ret:
                return None
            
            # Mejorar la precisión de las esquinas detectadas
            # Usar una ventana más grande para el refinamiento de esquinas
            # y criterios más estrictos para mayor precisión
            corners_subpix = cv2.cornerSubPix(gray, corners, (13, 13), (-1, -1), criteria)
            
            # Obtener las esquinas del tablero
            top_left = corners_subpix[0][0]
            top_right = corners_subpix[chessboard_size[0] - 1][0]
            bottom_right = corners_subpix[-1][0]
            bottom_left = corners_subpix[-chessboard_size[0]][0]
            
            # Escalar de vuelta a la resolución original
            scale_back_x = original_width / new_width
            scale_back_y = original_height / new_height
            top_left = (top_left[0] * scale_back_x, top_left[1] * scale_back_y)
            top_right = (top_right[0] * scale_back_x, top_right[1] * scale_back_y)
            bottom_right = (bottom_right[0] * scale_back_x, bottom_right[1] * scale_back_y)
            bottom_left = (bottom_left[0] * scale_back_x, bottom_left[1] * scale_back_y)
            
            # Crear polígono
            pts = np.array([top_left, top_right, bottom_right, bottom_left], np.int32).reshape((-1, 1, 2))
            
            # Calcular bounding box
            x_coords = pts[:,0,0]
            y_coords = pts[:,0,1]
            bbox = (int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords)))
            
            # Calcular centroide
            centroid = (int(np.mean(x_coords)), int(np.mean(y_coords)))
            
            # Opcionalmente guardar una imagen con el damero detectado para verificación
            if self.save_individual.get() or save_debug_images:
                # Crear una copia de la imagen original para dibujar
                img_with_corners = img_resized.copy()
                # Dibujar las esquinas y el patrón del damero
                cv2.drawChessboardCorners(img_with_corners, chessboard_size, corners_subpix, ret)
                # Dibujar el polígono que delimita el damero
                pts_draw = np.array([top_left, top_right, bottom_right, bottom_left], np.int32).reshape((-1, 1, 2))
                pts_draw = (pts_draw / np.array([scale_back_x, scale_back_y], dtype=np.float32)).astype(np.int32)
                cv2.polylines(img_with_corners, [pts_draw], True, (0, 255, 0), 2)
                # Dibujar el centroide
                centroid_draw = (int(centroid[0] / scale_back_x), int(centroid[1] / scale_back_y))
                cv2.circle(img_with_corners, centroid_draw, 5, (0, 0, 255), -1)
                
                base_filename = os.path.basename(filename)
                
                # Guardar en subcarpeta de verificación si está habilitado
                if self.save_individual.get():
                    verify_dir = os.path.join(os.path.dirname(output_path), "verificacion_damero")
                    os.makedirs(verify_dir, exist_ok=True)
                    verify_path = os.path.join(verify_dir, f"detected_{base_filename}")
                    cv2.imwrite(verify_path, img_with_corners)
                
                # Guardar en carpeta de depuración si está habilitado
                if save_debug_images and debug_folder:
                    # Añadir información adicional a la imagen
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(img_with_corners, f"Sensibilidad: {sensitivity:.1f}", (10, 30), font, 0.7, (0, 0, 255), 2)
                    
                    # Guardar versiones de preprocesamiento también
                    for i, img_version in enumerate(img_versions):
                        # Convertir a color para poder dibujar
                        if len(img_version.shape) == 2:
                            img_version_color = cv2.cvtColor(img_version, cv2.COLOR_GRAY2BGR)
                        else:
                            img_version_color = img_version.copy()
                            
                        # Añadir etiqueta de versión
                        cv2.putText(img_version_color, f"Versión {i}", (10, 30), font, 0.7, (0, 0, 255), 2)
                        
                        # Guardar
                        version_path = os.path.join(debug_folder, f"v{i}_{base_filename}")
                        cv2.imwrite(version_path, img_version_color)
                    
                    # Guardar imagen con detección
                    debug_path = os.path.join(debug_folder, f"detected_{base_filename}")
                    cv2.imwrite(debug_path, img_with_corners)
            
            # Liberar memoria de manera más agresiva
            del img, img_resized, gray, img_versions
            if 'img_with_corners' in locals():
                del img_with_corners
            if 'img_version_color' in locals():
                del img_version_color
            if 'pts_draw' in locals():
                del pts_draw
            if 'centroid_draw' in locals():
                del centroid_draw
            if self.optimize_performance.get():
                gc.collect()
                
            return filename, pts, bbox, centroid

        # Usar ThreadPoolExecutor para procesamiento concurrente
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(procesar_imagen, f): f for f in image_files}
            
            for future in concurrent.futures.as_completed(futures):
                if self.cancel_processing_flag:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                    
                result = future.result()
                if result:
                    filename, pts, bbox, centroid = result
                    polygons_info.append((filename, pts, bbox, centroid))
                    
                    # Crear máscara temporal solo para esta imagen
                    mask = np.zeros((image_resolution[1], image_resolution[0]), dtype=np.float32)
                    cv2.fillConvexPoly(mask, pts, 1.0)
                    heatmap += mask
                    
                    # Liberar memoria inmediatamente
                    del mask
                    if self.optimize_performance.get():
                        gc.collect()
                    
                    with progress_lock:
                        processed_count += 1
                        current_progress = min(100, processed_count / total_files * 100)
                        if hasattr(self, 'progress') and hasattr(self, 'root'):
                            self.root.after(0, lambda p=current_progress: self.progress.config(value=p))
                        self.log_message(f"✅ Procesada: {os.path.basename(filename)} ({processed_count}/{total_files})")

        if processed_count == 0:
            return False, None, [], 0, 0
            
        return True, heatmap, polygons_info, processed_count, total_files

    def open_heatmap_viewer(self, heatmap, polygons_info, camera_name, output_path, image_resolution):
        # Ejecutar en el hilo principal
        self.root.after(0, lambda: HeatmapViewer(
            self.root, heatmap, polygons_info, camera_name, output_path, image_resolution, self.show_plots.get()
        ))
    
    def add_to_history(self, folder):
        if folder in self.folders_history:
            self.folders_history.remove(folder)
        self.folders_history.insert(0, folder)
        self.folders_history = self.folders_history[:10]  # Mantener solo los últimos 10
        self.folder_combobox.config(values=self.folders_history)
        self.save_folder_history()
    
    def load_folder_history(self):
        try:
            history_file = Path.home() / '.heatmap_folders.txt'
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.folders_history = [line.strip() for line in f.readlines() if line.strip()]
        except:
            self.folders_history = []
    
    def save_folder_history(self):
        try:
            history_file = Path.home() / '.heatmap_folders.txt'
            with open(history_file, 'w', encoding='utf-8') as f:
                for folder in self.folders_history:
                    f.write(folder + '\n')
        except:
            pass
    
    def clear_history(self):
        if messagebox.askyesno("Confirmar", "¿Limpiar el historial de carpetas?"):
            self.folders_history = []
            self.folder_combobox.config(values=[])
            self.save_folder_history()

def main():
    root = tk.Tk()
    app = HeatmapApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
