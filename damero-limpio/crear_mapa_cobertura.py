import cv2
import numpy as np
import os
import glob
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import FLAT, RIGHT, LEFT, Y, X, BOTH, VERTICAL, UNITS  # Importar solo lo necesario
from ttkbootstrap.scrolled import ScrolledFrame
from pathlib import Path
import threading
from datetime import datetime
import gc
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk
import concurrent.futures

# --- CONFIGURACIÓN ---
CHESSBOARD_SIZE = (21, 17)  # Esquinas interiores del damero
IMAGE_RESOLUTION = (4448, 4448)
MAX_WORKERS = 8  # Número máximo de hilos para procesamiento concurrente
REDUCED_RESOLUTION = (1024, 768)  # Resolución reducida para procesamiento interno
# --- FIN CONFIGURACIÓN ---

class HeatmapViewer(ttk.Toplevel):
    def __init__(self, initial_heatmap, polygons_info, camera_name, output_path, image_resolution, show_plots=True, parent=None):
        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
        
        # Inicializar Toplevel con master
        ttk.Toplevel.__init__(self, master=parent)
        
        # Configurar ventana como independiente
        self.title(f"Mapa de Calor Interactivo - {camera_name}")
        self.geometry("1200x800")
        self.minsize(800, 600)
        
        # Quitar comportamiento modal
        self.attributes('-toolwindow', 0)  # Asegura que tenga todos los controles de ventana
        
        # Atributos de datos
        self.initial_heatmap = initial_heatmap
        self.polygons_info = polygons_info
        self.camera_name = camera_name
        self.output_path = output_path
        self.image_resolution = image_resolution
        self.show_plots = show_plots
        
        # Atributos de estado
        self.selected = [True] * len(polygons_info)
        self.current_heatmap = np.copy(initial_heatmap)
        self.current_highlight = None
        self.color_map_rgb = None
        
        # Atributos de UI
        self.tooltip_window = None
        self.hover_label = None
        
        # Configurar tema y estilos
        self._style = ttk.Style()
        if not self._style.theme_names() or 'cosmo' not in self._style.theme_names():
            print("Warning: 'cosmo' theme not available, using default theme")
        else:
            self._style.theme_use('cosmo')
        self.configure_styles()
        
        # Inicializar la UI
        self.init_matplotlib()
        self.setup_ui()
        #self.generate_heatmap() # Generar el mapa de calor
        
        # Guardar el mapa inicial
        self.save_initial_heatmap()
        
        # Mostrar el mapa inicial
        self.after(100, self.update_heatmap_display)  # Usar after para asegurar que la UI esté lista
        
        # Traer la ventana al frente
        self.lift()
        self.focus_force()
    
    def configure_styles(self):
        """Configura los estilos personalizados para los widgets"""
        # Estilos para los frames
        self._style.configure('Info.TFrame', background='#cfe2ff')
        self._style.configure('Secondary.TFrame', background='#e2e3e5')
        self._style.configure('Primary.TFrame', background='#cff4fc')
        
        # Estilos para las etiquetas
        self._style.configure('Info.TLabel', background='#cfe2ff', foreground='#084298')
        self._style.configure('Primary.TLabel', background='#cff4fc', foreground='#055160')
        self._style.configure('Secondary.TLabel', foreground='#41464b')
        
        # Estilos para los botones
        self._style.configure('Success.TButton', background='#198754', foreground='white')
        self._style.configure('Info.TButton', background='#0dcaf0', foreground='white')
        self._style.configure('Danger.Outline.TButton', background='white', foreground='#dc3545')
        self._style.configure('Info.Outline.TButton', background='white', foreground='#0dcaf0')
        
        # Estilo para los checkbuttons
        self._style.configure('Toggle.TCheckbutton', background='white')
        
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Configurar grid de la ventana principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Frame principal con padding solo horizontal
        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
        # Configurar grid para mantener proporciones
        main_frame.grid_columnconfigure(0, weight=7)  # 70% para el mapa
        main_frame.grid_columnconfigure(1, weight=3)  # 30% para la lista
        main_frame.grid_rowconfigure(0, weight=1)     # Fila única que se expande
        
        # Panel izquierdo para el mapa (70%)
        img_frame = ttk.Frame(main_frame)
        img_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10), pady=10)
            
        # Configurar grid del frame del mapa
        img_frame.grid_columnconfigure(0, weight=1)
        img_frame.grid_rowconfigure(0, weight=1)
        img_frame.grid_rowconfigure(1, weight=0)  # Fila para el hover no se expande    
        
        # Canvas de matplotlib en el centro
        self.canvas = FigureCanvasTkAgg(self.fig, master=img_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky='nsew')
        #self.canvas.draw() # CAMBIO 2 DUDA
        # Configurar eventos de ratón
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        
        # Frame para información de hover
        hover_frame = ttk.Frame(img_frame, style='Info.TFrame')
        hover_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
        
        hover_frame.grid_columnconfigure(0, weight=1)
        self.hover_label = ttk.Label(
            hover_frame, 
            text="🔍 Pase el ratón sobre el mapa para ver detalles", 
            font=("Arial", 9, "italic"),
            style='Info.TLabel',
            anchor="center"
        )
        self.hover_label.grid(row=0, column=0, sticky='ew', ipady=3)
        
        # Panel derecho para la lista (30%)
        side_frame = ttk.Frame(main_frame)
        side_frame.grid(row=0, column=1, sticky='nsew', pady=10)
        
        # Configurar grid del panel lateral
        side_frame.grid_columnconfigure(0, weight=1)
        side_frame.grid_rowconfigure(1, weight=1)  # La lista se expande
        
        # Título
        title_frame = ttk.Frame(side_frame)
        title_frame.configure(style='Primary.TFrame')
        title_frame.grid(row=0, column=0, sticky='ew')
        
        title_frame.grid_columnconfigure(0, weight=1)
        title_label = ttk.Label(
            title_frame, 
            text="Imágenes Procesadas", 
            font=('Arial', 12, 'bold'),
            style='Primary.TLabel',
            anchor="center"
        )
        title_label.grid(row=0, column=0, sticky='ew', ipady=5)
        '''
        self.fig = Figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=img_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        '''
        # ScrolledFrame para la lista
        self.list_container = ScrolledFrame(side_frame)
        self.list_container.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Frame para las checkboxes dentro del ScrolledFrame
        self.checkbox_frame = ttk.Frame(self.list_container)
        self.checkbox_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        # Configurar grid del frame de checkboxes
        self.checkbox_frame.grid_columnconfigure(0, weight=1)
        
        # Crear checkboxes numeradas
        self.create_item_list()
        
        # Configurar el scroll
        def _on_mousewheel(event):
            if self.list_container.winfo_exists():
                self.list_container.yview_scroll(int(-1 * (event.delta/120)), "units")
        
        # Bind el evento de scroll solo al contenedor de la lista
        self.list_container.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Desactivar el scroll cuando el ratón sale del área
        def _on_leave(e):
            self.list_container.unbind_all("<MouseWheel>")
        
        def _on_enter(e):
            self.list_container.bind_all("<MouseWheel>", _on_mousewheel)
        
        self.list_container.bind("<Enter>", _on_enter)
        self.list_container.bind("<Leave>", _on_leave)

    def save_initial_heatmap(self):
        """Guarda el mapa de calor inicial"""
        min_val = float(np.min(self.initial_heatmap))
        max_val = float(np.max(self.initial_heatmap))
        if max_val > min_val:
            heatmap_normalized = ((self.initial_heatmap - min_val) * 255.0 / (max_val - min_val)).astype(np.uint8)
        else:
            heatmap_normalized = np.zeros_like(self.initial_heatmap, dtype=np.uint8)
        
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        cv2.imwrite(self.output_path, color_map)

    def init_matplotlib(self):
        """Inicializa los componentes de matplotlib"""
        # Crear figura y ejes
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Configurar aspecto inicial
        self.ax.set_title(f"Mapa de Calor - {self.camera_name}")
        self.ax.axis('off')
        '''
        # Crear canvas (se empaquetará en setup_ui)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas.draw()
        CAMBIO 1
        '''

        self.canvas = None
        self.canvas_widget = None
               
    def create_item_list(self):
        """Crea la lista de items de manera optimizada"""
        self.checkboxes = []
        
        # Crear todos los widgets primero
        for i, (filename, _, _, _) in enumerate(self.polygons_info):
            var = tk.BooleanVar(value=True)
            self.checkboxes.append(var)
            
            # Crear frame para cada elemento de la lista
            item_frame = ttk.Frame(self.checkbox_frame)
            item_frame.grid(row=i, column=0, sticky='ew', padx=5, pady=3)
            item_frame.grid_columnconfigure(1, weight=1)  # La columna del contenido se expande
            
            # Número de imagen (más compacto)
            num_label = ttk.Label(
                item_frame, 
                text=f"{i+1}.", 
                width=3, 
                anchor=tk.E,
                style='Secondary.TLabel'
            )
            num_label.grid(row=0, column=0, padx=(0, 5))
            
            # Frame para el nombre del archivo y el botón
            content_frame = ttk.Frame(item_frame)
            content_frame.grid(row=0, column=1, sticky='ew')
            content_frame.grid_columnconfigure(0, weight=1)  # El checkbox se expande
            
            # Checkbox con el nombre del archivo (usando elipsis si es muy largo)
            filename_short = os.path.basename(filename)
            if len(filename_short) > 30:
                filename_short = filename_short[:27] + "..."
            
            chk = ttk.Checkbutton(
                content_frame, 
                text=filename_short, 
                variable=var,
                command=lambda idx=i: self.on_checkbox_change(idx),
                style='Toggle.TCheckbutton'
            )
            chk.grid(row=0, column=0, sticky='ew', padx=(0, 5))
            
            # Tooltip para mostrar el nombre completo
            self.create_tooltip(chk, os.path.basename(filename))
            
            # Botón para resaltar esta imagen en el mapa
            highlight_btn = ttk.Button(
                content_frame, 
                text="🔍", 
                width=3,
                command=lambda idx=i: self.highlight_image(idx),
                style='Info.Outline.TButton'
            )
            highlight_btn.grid(row=0, column=1)
            
            # Actualizar la interfaz cada 10 items
            if i % 10 == 0:
                self.update_idletasks()
            
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
        
    # Los métodos on_frame_configure y on_canvas_configure ya no son necesarios
    # con el ScrolledFrame de ttkbootstrap
            
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
        """Actualiza la visualización del mapa de calor"""
        if not hasattr(self, 'ax') or not self.ax:
            return
            
        # Normalizar el mapa de calor
        min_val = np.min(self.current_heatmap)
        max_val = np.max(self.current_heatmap)
        if max_val > min_val:
            heatmap_normalized = ((self.current_heatmap - min_val) * 255.0 / (max_val - min_val)).astype(np.uint8)
        else:
            heatmap_normalized = np.zeros_like(self.current_heatmap, dtype=np.uint8)
        
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        self.color_map_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
        
        # Limpiar y actualizar el gráfico
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
        
        # Configurar título y aspecto
        self.ax.set_title(f"Mapa de Calor - {self.camera_name}\n{np.count_nonzero(self.selected)}/{len(self.polygons_info)} imágenes seleccionadas")
        self.ax.axis('off')
        self.fig.tight_layout()
        
        # Actualizar el canvas
        self.canvas.draw()
        # CAMBIO 3 DUDA, self.canvas_widget.update_idletasks()
        
    def save_heatmap(self):
        # Normalizar el mapa de calor
        min_val = np.min(self.current_heatmap)
        max_val = np.max(self.current_heatmap)
        if max_val > min_val:
            heatmap_normalized = ((self.current_heatmap - min_val) * 255.0 / (max_val - min_val)).astype(np.uint8)
        else:
            heatmap_normalized = np.zeros_like(self.current_heatmap, dtype=np.uint8)
            
        color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
        cv2.imwrite(self.output_path, color_map)
        messagebox.showinfo("Guardado", f"Mapa de calor guardado en:\n{self.output_path}")
    
    def highlight_image(self, index):
        """Resalta una imagen específica en el mapa de calor"""
        if not hasattr(self, 'ax') or not self.ax:
            return
            
        filename, polygon, _, centroid = self.polygons_info[index]
        
        # Crear una copia del mapa de calor actual
        if self.color_map_rgb is not None:
            highlight_map = np.copy(self.color_map_rgb)
        else:
            # Si no hay mapa de calor, crear uno vacío
            highlight_map = np.zeros((*self.image_resolution[::-1], 3), dtype=np.uint8)
        
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
        if not hasattr(self, 'ax') or not self.ax or not event.inaxes == self.ax:
            return
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
            
        # Actualizar el texto del hover si existe la etiqueta
        if hasattr(self, 'hover_label') and self.hover_label:
            if covering_images:
                # Crear texto informativo
                if len(covering_images) == 1:
                    img_num, filename = covering_images[0]
                    text = f"📸 Imagen #{img_num}: {os.path.basename(filename)}"
                else:
                    nums = ", ".join([f"#{num}" for num, _ in covering_images[:3]])
                    if len(covering_images) > 3:
                        nums += f" y {len(covering_images)-3} más"
                    text = f"🔍 Superposición: {nums} ({len(covering_images)} imágenes)"
                
                self.hover_label.config(text=text)
            else:
                self.hover_label.config(text="🔍 Pase el ratón sobre un área cubierta para ver detalles")
    
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
            img_window = tk.Toplevel()
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
            
            # Título con información de la imagen
            header_frame = ttk.Frame(img_window)
            header_frame.pack(fill=tk.X)
            
            title_label = ttk.Label(
                header_frame,
                text=f"📸 Imagen #{image_num}: {os.path.basename(image_path)}",
                font=("Arial", 12, "bold"),
                anchor="center"
            )
            title_label.pack(fill=tk.X, ipady=5)
            
            # Contenedor principal
            main_frame = ttk.Frame(img_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Mostrar imagen
            label = ttk.Label(main_frame)
            label.configure(image=img_tk)
            setattr(label, '_image_keep', img_tk)  # Mantener referencia
            label.pack(padx=10, pady=10)
            
            # Información adicional
            info_frame = ttk.Frame(main_frame)
            info_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Mostrar dimensiones de la imagen
            info_label = ttk.Label(
                info_frame,
                text=f"Dimensiones: {width}x{height} píxeles",
                font=("Arial", 9)
            )
            info_label.pack(side=tk.LEFT, padx=10, pady=5)
            
            # Botón de cierre
            close_btn = ttk.Button(
                main_frame, 
                text="❌ Cerrar", 
                command=img_window.destroy,
                width=10
            )
            close_btn.pack(pady=(10, 0))
            
            # Hacer que la ventana sea modal
            img_window.transient(self)
            img_window.grab_set()
            img_window.focus_set()

    def create_tooltip(self, widget, text):
        """Crea un tooltip para mostrar el texto completo al pasar el ratón"""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 20
            
            # Destruir tooltip anterior si existe
            if self.tooltip_window is not None:
                self.tooltip_window.destroy()
            
            # Crear ventana de tooltip
            self.tooltip_window = tk.Toplevel(widget)
            self.tooltip_window.wm_overrideredirect(True)
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(
                self.tooltip_window, 
                text=text, 
                justify=tk.LEFT,
                background="#ffffe0", 
                relief=tk.SOLID, 
                borderwidth=1
            )
            label.pack()
            
        def leave(event):
            if self.tooltip_window is not None:
                self.tooltip_window.destroy()
                self.tooltip_window = None
        
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)


class HeatmapGallery(ttk.Toplevel):
    """Clase para mostrar una galería de miniaturas de mapas de calor"""
    def __init__(self, parent, gallery_items, image_resolution, show_plots):
        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
        
        # Inicializar Toplevel con master
        ttk.Toplevel.__init__(self, master=parent)
        
        # Configurar ventana como independiente
        self.title("Galería de Mapas de Calor")
        self.geometry("1200x800")
        self.attributes('-toolwindow', 0)  # Asegura que tenga todos los controles de ventana
        
        # Guardar referencia al padre
        self.parent = parent
        
        # Atributos
        self.gallery_items = gallery_items
        self.image_resolution = image_resolution
        # Convertir show_plots a bool si es un BooleanVar
        if isinstance(show_plots, tk.BooleanVar):
            self.show_plots = show_plots.get()
        else:
            self.show_plots = bool(show_plots)
        
        # Configurar tema y estilos
        self._style = ttk.Style()
        if not self._style.theme_names() or 'cosmo' not in self._style.theme_names():
            print("Warning: 'cosmo' theme not available, using default theme")
        else:
            self._style.theme_use('cosmo')
        
        # Configurar UI
        self.setup_ui()
        
        # Traer la ventana al frente
        self.lift()
        self.focus_force()

    def setup_ui(self):
        # Título principal
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 20))
        
        title_label = ttk.Label(
            header_frame, 
            text="Galería de Mapas de Calor", 
            font=("Arial", 16, "bold"),
            anchor="center"
        )
        title_label.pack(fill=tk.X, ipady=10)
        
        # Contenedor con scroll
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Canvas y scrollbar
        self.canvas = tk.Canvas(main_container, width=1000, height=600)  # Tamaño fijo inicial
        self.scrollbar = ttk.Scrollbar(main_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configurar scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Crear ventana en el canvas
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Empaquetar elementos
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configurar scroll con rueda del ratón
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Desactivar el scroll cuando el ratón sale del área
        def _on_leave(e):
            self.canvas.unbind_all("<MouseWheel>")
        
        def _on_enter(e):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        self.canvas.bind("<Enter>", _on_enter)
        self.canvas.bind("<Leave>", _on_leave)
        
        # Contenedor para las tarjetas
        self.gallery_frame = ttk.Frame(self.scrollable_frame)
        self.gallery_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Lista para mantener referencias a las imágenes
        self.image_refs = []
        
        # Crear una cuadrícula de 3 columnas
        cols = 3
        for i, item in enumerate(self.gallery_items):
            row = i // cols
            col = i % cols
            
            # Crear tarjeta
            frame = ttk.Frame(self.gallery_frame)
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Configurar peso de columnas
            self.gallery_frame.grid_columnconfigure(col, weight=1)
            
            # Contenedor interno
            card = ttk.Frame(frame, relief="solid", borderwidth=1)
            card.pack(fill=tk.BOTH, expand=True)
            
            # Encabezado de la tarjeta
            header = ttk.Frame(card)
            header.pack(fill=tk.X)
            
            # Título con número de cámara
            label = ttk.Label(
                header, 
                text=f"Cámara #{i+1}: {item['camera_name']}", 
                font=('Arial', 10, 'bold'),
                anchor="center",
                padding=5
            )
            label.pack(fill=tk.X)
            
            # Contenido de la tarjeta
            content = ttk.Frame(card, padding=10)
            content.pack(fill=tk.BOTH, expand=True)
            
            try:
                # Generar miniatura
                min_val = float(np.min(item['heatmap']))
                max_val = float(np.max(item['heatmap']))
                if max_val > min_val:
                    heatmap_normalized = ((item['heatmap'] - min_val) * 255.0 / (max_val - min_val)).astype(np.uint8)
                else:
                    heatmap_normalized = np.zeros_like(item['heatmap'], dtype=np.uint8)
                color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
                img_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
                # Reducir tamaño para miniatura manteniendo proporción
                height, width = img_rgb.shape[:2]
                target_width = 300
                target_height = int(height * target_width / width)
                preview = cv2.resize(img_rgb, (target_width, target_height))
                # Convertir a formato Tkinter
                img_tk = ImageTk.PhotoImage(Image.fromarray(preview))
                # Guardar referencia a la imagen
                self.image_refs.append(img_tk)
                # Mostrar miniatura
                img_label = ttk.Label(content, cursor="hand2")
                img_label.configure(image=img_tk)
                setattr(img_label, '_image_keep', img_tk)  # Mantener referencia de manera segura
                img_label.pack(pady=5)
                # Hacer clic sobre la miniatura para abrir visor
                img_label.bind("<Button-1>", lambda e, item=item: self.open_heatmap_viewer(item))
                # Texto informativo
                info_frame = ttk.Frame(content)
                info_frame.pack(fill=tk.X, pady=(5, 0))
                info_label = ttk.Label(
                    info_frame, 
                    text=f"{item['processed_count']}/{item['total_files']} imágenes"
                )
                info_label.pack(side=tk.LEFT)
                # Botón para abrir
                open_btn = ttk.Button(
                    info_frame, 
                    text="Abrir", 
                    command=lambda item=item: self.open_heatmap_viewer(item),
                    width=8
                )
                open_btn.pack(side=tk.RIGHT)
            except Exception as e:
                error_label = ttk.Label(
                    content,
                    text=f"Error al cargar la imagen:\n{str(e)}",
                    foreground="red"
                )
                error_label.pack(pady=10)
                print(f"Error al procesar mapa de calor {i+1}: {str(e)}")
        
        # Ajustar tamaño del canvas después de cargar todo
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Configurar redimensionamiento
        self.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event):
        """Maneja el redimensionamiento de la ventana"""
        # Actualizar el tamaño del canvas
        width = event.width - 40  # Margen para scrollbar y padding
        self.canvas.configure(width=width)
        
        # Recalcular el área de scroll
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def open_heatmap_viewer(self, item):
        """Abre el visor interactivo para el mapa seleccionado"""
        try:
            viewer = HeatmapViewer(
                item['heatmap'].copy(),
                item['polygons_info'].copy(),
                item['camera_name'],
                item['output_path'],
                self.image_resolution,
                self.show_plots,
                parent=self
            )
            viewer.focus_force()
        except Exception as e:
            print(f"Error al abrir el visor: {str(e)}")
            messagebox.showerror("Error", f"Error al abrir el visor:\n{str(e)}")

class HeatmapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Mapa de Calor - Calibración Multi-Cámara")
        
        # Variables
        self.selected_folder = tk.StringVar()
        self.folders_history = []
        self.processing_mode = tk.StringVar(value="single")
        self.camera_folders = []
        self.image_resolution = IMAGE_RESOLUTION  # Añadir atributo image_resolution
        
        # Cargar historial de carpetas
        self.load_folder_history()
        
        # Crear contenedor principal
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Crear frame principal con scroll
        self.scrolled_frame = ScrolledFrame(self.main_container)
        self.scrolled_frame.pack(fill=tk.BOTH, expand=True)
        
        self.setup_ui()
    
    def update_sensitivity_label(self, value):
        """Actualiza la etiqueta con el valor actual del control deslizante"""
        if hasattr(self, 'sensitivity_value_label'):
            self.sensitivity_value_label.config(text=f"{float(value):.1f}")
    
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.scrolled_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título con estilo mejorado
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(
            title_frame, 
            text="Generador de Mapa de Calor Multi-Cámara", 
            font=("Arial", 18, "bold"),
            anchor="center"
        )
        title_label.pack(fill=tk.X, ipady=10)
        
        # Modo de procesamiento con estilo mejorado
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Procesamiento", padding="15")
        mode_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Contenedor para los radiobuttons
        radio_container = ttk.Frame(mode_frame)
        radio_container.pack(fill=tk.X, padx=10, pady=10)
        
        # Radiobuttons con estilo mejorado
        single_radio = ttk.Radiobutton(
            radio_container, 
            text="Carpeta única (una cámara)", 
            variable=self.processing_mode, 
            value="single",
            command=self.on_mode_change
        )
        single_radio.pack(side=tk.LEFT, padx=(0, 20))
        
        multi_radio = ttk.Radiobutton(
            radio_container, 
            text="Carpeta con subcarpetas (múltiples cámaras)", 
            variable=self.processing_mode, 
            value="multi",
            command=self.on_mode_change
        )
        multi_radio.pack(side=tk.LEFT, padx=(10, 20))
        
        # Selección de carpeta
        folder_frame = ttk.LabelFrame(main_frame, text="Seleccionar Carpeta", padding="15")
        folder_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Panel superior con etiqueta y botones
        folder_header = ttk.Frame(folder_frame)
        folder_header.pack(fill=tk.X, pady=(0, 10))
        
        # Etiqueta con ícono
        ttk.Label(folder_header, text="📁 Carpeta de imágenes:", 
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        # Botones en el lado derecho del encabezado
        btn_frame = ttk.Frame(folder_header)
        btn_frame.pack(side=tk.RIGHT)
        
        # Botón examinar
        browse_btn = ttk.Button(
            btn_frame, 
            text="Examinar...", 
            command=self.browse_folder,
            width=12
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Botón actualizar lista
        refresh_btn = ttk.Button(
            btn_frame, 
            text="↻ Actualizar", 
            command=self.refresh_folder_info,
            width=12
        )
        refresh_btn.pack(side=tk.LEFT)
        
        # Panel para el combobox
        combo_frame = ttk.Frame(folder_frame)
        combo_frame.pack(fill=tk.X, padx=5)
        
        # Combobox para carpetas recientes
        self.folder_combobox = ttk.Combobox(
            combo_frame, 
            textvariable=self.selected_folder, 
            values=self.folders_history, 
            width=70
        )
        self.folder_combobox.pack(fill=tk.X, expand=True, pady=(0, 5))
        
        # Información de la carpeta
        info_label = ttk.Label(
            folder_frame, 
            text="Información de la carpeta", 
            font=("Arial", 10, "bold")
        )
        info_label.pack(anchor=tk.W, padx=5, pady=(10, 5))
        
        # Frame para el texto de información
        info_frame = ttk.Frame(folder_frame)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Texto con estilo mejorado
        self.info_text = tk.Text(
            info_frame, 
            height=6, 
            width=80, 
            wrap=tk.WORD,
            font=("Consolas", 9),
            background="#f0f0f0",
            borderwidth=1,
            relief="solid"
        )
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar para el texto
        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.config(yscrollcommand=scrollbar.set)
        
        # Configuración
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding="15")
        config_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Crear dos columnas para organizar mejor los controles
        left_config = ttk.Frame(config_frame)
        left_config.pack(side=tk.LEFT, padx=(5, 15), pady=10)
        
        right_config = ttk.Frame(config_frame)
        right_config.pack(side=tk.LEFT, padx=(15, 5), pady=10)
        
        # === COLUMNA IZQUIERDA ===
        # Tamaño del damero
        chess_label_frame = ttk.LabelFrame(left_config, text="Tamaño del damero")
        chess_label_frame.pack(fill=tk.X, pady=(0, 10), ipady=5)
        
        chess_frame = ttk.Frame(chess_label_frame)
        chess_frame.pack(padx=10, pady=10)
        
        self.chess_width = tk.StringVar(value=str(CHESSBOARD_SIZE[0]))
        self.chess_height = tk.StringVar(value=str(CHESSBOARD_SIZE[1]))
        
        ttk.Label(chess_frame, text="Ancho:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(chess_frame, textvariable=self.chess_width, width=5).grid(row=0, column=1)
        
        ttk.Label(chess_frame, text="Alto:").grid(row=0, column=2, sticky=tk.W, padx=(15, 5))
        ttk.Entry(chess_frame, textvariable=self.chess_height, width=5).grid(row=0, column=3)
        
        # Resolución de imagen
        res_label_frame = ttk.LabelFrame(left_config, text="Resolución de imagen")
        res_label_frame.pack(fill=tk.X, ipady=5)
        
        res_frame = ttk.Frame(res_label_frame)
        res_frame.pack(padx=10, pady=10)
        
        self.img_width = tk.StringVar(value=str(IMAGE_RESOLUTION[0]))
        self.img_height = tk.StringVar(value=str(IMAGE_RESOLUTION[1]))
        
        ttk.Label(res_frame, text="Ancho:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(res_frame, textvariable=self.img_width, width=6).grid(row=0, column=1)
        
        ttk.Label(res_frame, text="Alto:").grid(row=0, column=2, sticky=tk.W, padx=(15, 5))
        ttk.Entry(res_frame, textvariable=self.img_height, width=6).grid(row=0, column=3)
        
        # Opciones adicionales (en columna derecha)
        options_label_frame = ttk.LabelFrame(right_config, text="Opciones adicionales")
        options_label_frame.pack(fill=tk.X, expand=True)
        
        # Checkbuttons
        self.save_individual = tk.BooleanVar(value=True)
        save_check = ttk.Checkbutton(
            options_label_frame, 
            text="Guardar mapas individuales", 
            variable=self.save_individual
        )
        save_check.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.show_plots = tk.BooleanVar(value=True)
        plots_check = ttk.Checkbutton(
            options_label_frame, 
            text="Mostrar gráficos", 
            variable=self.show_plots
        )
        plots_check.pack(anchor=tk.W, padx=10, pady=5)
        
        self.optimize_performance = tk.BooleanVar(value=True)
        perf_check = ttk.Checkbutton(
            options_label_frame, 
            text="Optimizar rendimiento", 
            variable=self.optimize_performance
        )
        perf_check.pack(anchor=tk.W, padx=10, pady=5)
        
        self.save_debug_images = tk.BooleanVar(value=False)
        debug_check = ttk.Checkbutton(
            options_label_frame, 
            text="Guardar imágenes de depuración", 
            variable=self.save_debug_images
        )
        debug_check.pack(anchor=tk.W, padx=10, pady=(5, 10))
        
        # Control de sensibilidad de detección
        sensitivity_frame = ttk.LabelFrame(config_frame, text="Sensibilidad de detección")
        sensitivity_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Valor actual
        value_frame = ttk.Frame(sensitivity_frame)
        value_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        self.detection_sensitivity = tk.DoubleVar(value=3.0)
        
        # Mostrar valor actual
        self.sensitivity_value_label = ttk.Label(
            value_frame, 
            text=f"{self.detection_sensitivity.get():.1f}", 
            font=("Arial", 10, "bold")
        )
        self.sensitivity_value_label.pack(side=tk.RIGHT)
        
        ttk.Label(value_frame, text="Valor actual:").pack(side=tk.RIGHT, padx=(0, 5))
        
        # Control deslizante
        scale_frame = ttk.Frame(sensitivity_frame)
        scale_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        sensitivity_scale = ttk.Scale(
            scale_frame, 
            from_=1.0, 
            to=5.0, 
            variable=self.detection_sensitivity, 
            orient=tk.HORIZONTAL, 
            length=250,
            command=self.update_sensitivity_label
        )
        sensitivity_scale.pack(fill=tk.X, expand=True)
        
        # Etiquetas para la escala
        label_frame = ttk.Frame(sensitivity_frame)
        label_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(label_frame, text="Baja").pack(side=tk.LEFT)
        ttk.Label(label_frame, text="Alta").pack(side=tk.RIGHT)
        
        # Botones de acción
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.generate_btn = ttk.Button(
            action_frame, 
            text="Generar Mapa(s) de Calor", 
            command=self.generate_heatmap_threaded
        )
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Botón Limpiar Historial
        clear_btn = ttk.Button(
            action_frame, 
            text="Limpiar Historial", 
            command=self.clear_history,
            width=15
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Botón Cancelar
        self.cancel_btn = ttk.Button(
            action_frame, 
            text="Cancelar", 
            command=self.cancel_processing, 
            width=15,
            state='disabled'
        )
        self.cancel_btn.pack(side=tk.LEFT)

        # Barra de progreso
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.progress_label = ttk.Label(progress_frame, text="")
        self.progress_label.pack(side=tk.LEFT)
        
        # Log de procesamiento
        log_frame = ttk.LabelFrame(main_frame, text="Log de Procesamiento", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Frame contenedor para el texto y scrollbar
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        # Texto con estilo mejorado
        self.log_text = tk.Text(
            log_container, 
            height=6, 
            width=80, 
            wrap=tk.WORD,
            font=("Consolas", 9),
            background="#f0f0f0",
            borderwidth=1,
            relief="solid"
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar para el texto
        log_scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
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
        
        if success and heatmap is not None:
             # Programar la apertura del visor en el hilo principal
            self.root.after(0, lambda: self.open_heatmap_viewer(
                heatmap.copy(),
                polygons_info.copy(),
                "Cámara única",
                output_path,
                img_resolution,
                processed_count,
                total_files
            ))
            
            self.log_message(f"✅ Mapa de calor generado: {output_path}")
        else:
            self.root.after(0, lambda: messagebox.showwarning(
                "Advertencia", 
                "No se pudo procesar ninguna imagen válida"
            ))
            self.log_message("❌ No se pudo procesar ninguna imagen válida")
            # Abrir visor interactivo
            '''item = {
                'heatmap': heatmap,
                'polygons_info': polygons_info,
                'camera_name': "Cámara única",
                'output_path': output_path,
                'processed_count': processed_count,
                'total_files': total_files
            }
            try:
                viewer = HeatmapViewer(
                    item['heatmap'].copy(),
                    item['polygons_info'].copy(),
                    item['camera_name'],
                    item['output_path'],
                    img_resolution,
                    self.show_plots.get(),  # Convertir BooleanVar a bool
                    parent=self.root
                )
                viewer.focus_force()
            except Exception as e:
                self.log_message(f"❌ Error al abrir el visor: {str(e)}")
                messagebox.showerror("Error", f"Error al abrir el visor:\n{str(e)}")
            
            self.log_message(f"✅ Mapa de calor generado: {output_path}")
        else:
            self.log_message("❌ No se pudo procesar ninguna imagen válida")
            messagebox.showwarning("Advertencia", "No se pudo procesar ninguna imagen válida")'''
    
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
            
            if success and heatmap is not None:
                # Normalizar el mapa de calor
                min_val = float(np.min(heatmap))
                max_val = float(np.max(heatmap))
                if max_val > min_val:
                    heatmap_normalized = ((heatmap - min_val) * 255.0 / (max_val - min_val)).astype(np.uint8)
                else:
                    heatmap_normalized = np.zeros_like(heatmap, dtype=np.uint8)
                
                # Guardar el mapa inicial
                color_map = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
                cv2.imwrite(output_path, color_map)
                
                # Guardar datos para la galería
                gallery_items.append({
                    'camera_name': camera_name,
                    'heatmap': heatmap.copy(),  # Hacer una copia para evitar problemas de referencia
                    'polygons_info': polygons_info.copy(),  # Hacer una copia para evitar problemas de referencia
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
            # Asegurarse de que la galería se cree en el hilo principal
            self.root.after(100, lambda: self.show_gallery(gallery_items, img_resolution))
            
            self.log_message(f"🎉 Procesamiento completado: {successful_cameras}/{total_cameras} cámaras")
            messagebox.showinfo("Éxito", 
                f"Procesamiento completado exitosamente:\n"
                f"• {successful_cameras} de {total_cameras} cámaras procesadas\n"
                f"• Mapas guardados en: {folder}")
        else:
            self.log_message("❌ No se pudo procesar ninguna cámara")
            messagebox.showwarning("Advertencia", "No se pudo procesar ninguna cámara")
    
    def show_gallery(self, gallery_items, img_resolution):
        """Muestra la galería de mapas de calor en el hilo principal"""
        try:
            gallery = HeatmapGallery(
                self.root,
                gallery_items,
                img_resolution,
                self.show_plots.get()  # Convertir a bool antes de pasar
            )
            gallery.focus_force()  # Asegurar que la ventana tenga el foco
        except Exception as e:
            self.log_message(f"❌ Error al mostrar la galería: {str(e)}")
            messagebox.showerror("Error", f"Error al mostrar la galería:\n{str(e)}")
    
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
            if blur_size % 2 == 0:
                blur_size += 1
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
            if corners is not None:
                corners_subpix = cv2.cornerSubPix(gray, corners, (13, 13), (-1, -1), criteria)
            else:
                return None
            
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

    def open_heatmap_viewer(self, heatmap, polygons_info, camera_name, output_path, img_resolution, processed_count, total_files):
        try:
            viewer = HeatmapViewer(
                heatmap,
                polygons_info,
                camera_name,
                output_path,
                img_resolution,
                self.show_plots.get(),
                parent=self.root
            )
            viewer.focus_force()
        except Exception as e:
            self.log_message(f"❌ Error al abrir el visor: {str(e)}")
            messagebox.showerror("Error", f"Error al abrir el visor:\n{str(e)}")

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
    # Usar ttkbootstrap en lugar de tkinter estándar
    root = ttk.Window(
        title="Generador de Mapa de Calor - Calibración Multi-Cámara",
        themename="cosmo",  # Tema moderno y limpio
        resizable=(True, True),
        size=(1000, 800),
        position=(100, 50),
        minsize=(800, 600)
    )
    app = HeatmapApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
