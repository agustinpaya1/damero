import cv2
import numpy as np
import os
import glob
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading
from datetime import datetime
import gc
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --- CONFIGURACIÓN ---
CHESSBOARD_SIZE = (10, 7)  # Esquinas interiores del damero
IMAGE_RESOLUTION = (4096, 3000)
# --- FIN CONFIGURACIÓN ---

class HeatmapViewer(tk.Toplevel):
    def __init__(self, parent, initial_heatmap, masks, camera_name, output_path, image_resolution, show_plots=True):
        super().__init__(parent)
        self.title(f"Mapa de Calor Interactivo - {camera_name}")
        self.geometry("1200x800")
        
        self.initial_heatmap = initial_heatmap
        self.masks = masks
        self.camera_name = camera_name
        self.output_path = output_path
        self.image_resolution = image_resolution
        self.show_plots = show_plots
        
        # Estado de selección
        self.selected = [True] * len(masks)
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
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
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
        
        close_btn = ttk.Button(btn_frame, text="Cerrar", command=self.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        # Configurar eventos
        self.checkbox_frame.bind("<Configure>", self.on_frame_configure)
        self.checkbox_canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Crear checkboxes
        self.checkboxes = []
        for i, (filename, _) in enumerate(self.masks):
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(
                self.checkbox_frame, 
                text=os.path.basename(filename), 
                variable=var,
                command=lambda idx=i: self.on_checkbox_change(idx)
            )
            chk.pack(anchor=tk.W, padx=5, pady=2)
            self.checkboxes.append(var)
            
    def on_frame_configure(self, event):
        self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))
        
    def on_canvas_configure(self, event):
        canvas_width = event.width
        self.checkbox_canvas.itemconfig(self.checkbox_canvas_window, width=canvas_width)
            
    def on_checkbox_change(self, index):
        self.selected[index] = self.checkboxes[index].get()
        self.update_heatmap()
        
    def update_heatmap(self):
        self.current_heatmap = np.zeros(self.initial_heatmap.shape, dtype=np.float32)
        for i, selected in enumerate(self.selected):
            if selected:
                _, mask = self.masks[i]
                self.current_heatmap += mask
        self.update_heatmap_display()
        
    def update_heatmap_display(self):
        heatmap_normalized = cv2.normalize(self.current_heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        img_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
        
        self.ax.clear()
        self.ax.imshow(img_rgb)
        self.ax.set_title(f"Mapa de Calor - {self.camera_name}\n{np.count_nonzero(self.selected)}/{len(self.masks)} imágenes seleccionadas")
        self.ax.axis('off')
        self.fig.tight_layout()
        self.canvas.draw()
        
    def save_heatmap(self):
        heatmap_normalized = cv2.normalize(self.current_heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        cv2.imwrite(self.output_path, color_map)
        messagebox.showinfo("Guardado", f"Mapa de calor guardado en:\n{self.output_path}")

class HeatmapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Mapa de Calor - Calibración Multi-Cámara")
        self.root.geometry("800x600")
        
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
        return image_files
    
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
        
        try:
            mode = self.processing_mode.get()
            
            if mode == "single":
                self.process_single_camera(folder, chess_size, img_resolution)
            else:
                self.process_multiple_cameras(folder, chess_size, img_resolution)
                
        except Exception as e:
            self.log_message(f"❌ Error: {str(e)}")
            messagebox.showerror("Error", f"Error al generar el mapa de calor:\n{str(e)}")
        
        finally:
            self.generate_btn.config(state='normal')
            self.cancel_btn.config(state='disabled')
            self.progress.config(value=0)
            self.progress_label.config(text="")
    
    def process_single_camera(self, folder, chess_size, img_resolution):
        self.log_message("🎯 Procesando cámara única...")
        
        output_path = os.path.join(os.path.dirname(folder), f"mapa_calor_{os.path.basename(folder)}.png")
        
        success, heatmap, masks, processed_count, total_files = self.crear_mapa_de_cobertura(
            folder, chess_size, img_resolution, output_path, "Cámara única"
        )
        
        if success:
            # Guardar el mapa inicial
            heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
            cv2.imwrite(output_path, color_map)
            
            # Abrir visor interactivo
            self.open_heatmap_viewer(heatmap, masks, "Cámara única", output_path, img_resolution)
            
            self.log_message(f"✅ Mapa de calor generado: {output_path}")
        else:
            self.log_message("❌ No se pudo procesar ninguna imagen válida")
            messagebox.showwarning("Advertencia", "No se pudo procesar ninguna imagen válida")
    
    def process_multiple_cameras(self, folder, chess_size, img_resolution):
        if not self.camera_folders:
            self.log_message("❌ No hay carpetas de cámaras para procesar")
            return
        
        self.log_message(f"🎯 Procesando {len(self.camera_folders)} cámaras...")
        
        total_cameras = len(self.camera_folders)
        successful_cameras = 0
        
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
            
            success, heatmap, masks, processed_count, total_files = self.crear_mapa_de_cobertura(
                camera_path, chess_size, img_resolution, output_path, camera_name
            )
            
            if success:
                # Guardar el mapa inicial
                heatmap_normalized = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
                cv2.imwrite(output_path, color_map)
                
                # Abrir visor interactivo
                self.open_heatmap_viewer(heatmap, masks, camera_name, output_path, img_resolution)
                
                successful_cameras += 1
                self.log_message(f"✅ {camera_name}: Completado")
            else:
                self.log_message(f"❌ {camera_name}: Sin imágenes válidas")
        
        # Progreso final
        self.progress.config(value=100)
        self.progress_label.config(text="Completado")
        
        if successful_cameras > 0:
            self.log_message(f"🎉 Procesamiento completado: {successful_cameras}/{total_cameras} cámaras")
            messagebox.showinfo("Éxito", 
                f"Procesamiento completado exitosamente:\n"
                f"• {successful_cameras} de {total_cameras} cámaras procesadas\n"
                f"• Mapas guardados en: {folder}")
        else:
            self.log_message("❌ No se pudo procesar ninguna cámara")
            messagebox.showwarning("Advertencia", "No se pudo procesar ninguna cámara")
    
    def crear_mapa_de_cobertura(self, images_path, chessboard_size, image_resolution, output_path, camera_name):
        heatmap = np.zeros((image_resolution[1], image_resolution[0]), dtype=np.float32)
        masks = []  # Lista para guardar tuplas (filename, mask)
        
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        
        image_files = self.find_images_in_folder(images_path)
        
        if not image_files:
            return False, None, [], 0, 0
        
        processed_count = 0
        total_files = len(image_files)
        
        # Optimización: procesar en lotes para mejor rendimiento
        batch_size = 10
        
        for i in range(0, len(image_files), batch_size):
            if self.cancel_processing_flag:
                break
                
            # Procesar lote
            batch_files = image_files[i:i + batch_size]
            
            for filename in batch_files:
                if self.cancel_processing_flag:
                    break
                    
                img = cv2.imread(filename)
                if img is None:
                    continue
                
                # Redimensionar imagen si es muy grande para mejorar rendimiento
                height, width = img.shape[:2]
                if width > 2048 or height > 2048:
                    scale = min(2048/width, 2048/height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    img = cv2.resize(img, (new_width, new_height))
                
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK
                ret, corners = cv2.findChessboardCorners(gray, chessboard_size, flags=flags)
                
                if ret:
                    corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                    
                    # Escalar coordenadas de vuelta si redimensionamos
                    if width > 2048 or height > 2048:
                        scale_back = max(width/2048, height/2048)
                        corners_subpix = corners_subpix * scale_back
                    
                    top_left = corners_subpix[0][0]
                    top_right = corners_subpix[chessboard_size[0] - 1][0]
                    bottom_right = corners_subpix[-1][0]
                    bottom_left = corners_subpix[-chessboard_size[0]][0]
                    
                    pts = np.array([top_left, top_right, bottom_right, bottom_left], np.int32).reshape((-1, 1, 2))
                    
                    # Crear máscara individual
                    mask = np.zeros((image_resolution[1], image_resolution[0]), dtype=np.float32)
                    cv2.fillConvexPoly(mask, pts, 1.0)
                    
                    # Acumular en el heatmap total
                    heatmap += mask
                    masks.append((filename, mask))
                    processed_count += 1
                
                # Liberar memoria
                del img, gray
                if self.optimize_performance.get():
                    gc.collect()  # Forzar garbage collection periódicamente
            
            # Actualizar progreso cada lote
            if hasattr(self, 'progress') and total_files > 0:
                current_progress = min(100, (i + batch_size) / total_files * 100)
                self.root.after(0, lambda p=current_progress: self.progress.config(value=p))
        
        if processed_count == 0:
            return False, None, [], 0, 0
        
        return True, heatmap, masks, processed_count, total_files
    
    def open_heatmap_viewer(self, heatmap, masks, camera_name, output_path, image_resolution):
        # Ejecutar en el hilo principal
        self.root.after(0, lambda: HeatmapViewer(
            self.root, heatmap, masks, camera_name, output_path, image_resolution, self.show_plots.get()
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