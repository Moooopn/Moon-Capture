import io
import time
import ctypes
from ctypes import wintypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageGrab, ImageFilter, ImageDraw, ImageEnhance

# Use ImageTk for direct zero-copy GPU/GUI memory rendering
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

# Enable Per-Monitor DPI Awareness for accurate physical pixel matching on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos():
    """Returns current mouse cursor position in Windows Virtual Screen coordinates."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_virtual_screen_geometry():
    """Gets bounding rectangle across ALL active monitors (Virtual Desktop)."""
    user32 = ctypes.windll.user32
    v_left = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    v_top = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
    v_width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    v_height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    if v_width <= 0:
        v_width = user32.GetSystemMetrics(0)
    if v_height <= 0:
        v_height = user32.GetSystemMetrics(1)
    return v_left, v_top, v_width, v_height


def create_moon_icon():
    """Generates a high-quality full moon icon with crater details."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse((3, 3, 61, 61), fill=(255, 235, 150, 60))
    draw.ellipse((4, 4, 60, 60), fill="#FDD835", outline="#FBC02D", width=2)

    crater_color = "#F0C419"
    draw.ellipse((14, 18, 26, 30), fill=crater_color)
    draw.ellipse((34, 14, 44, 24), fill=crater_color)
    draw.ellipse((30, 34, 46, 50), fill=crater_color)
    draw.ellipse((18, 40, 27, 49), fill=crater_color)
    draw.ellipse((44, 28, 52, 36), fill=crater_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return tk.PhotoImage(data=buf.getvalue())


def copy_to_clipboard(image):
    """Safely copies a PIL Image to Windows Clipboard (64-bit compatible DIB)."""
    try:
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []

        opened = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)

        if not opened:
            return False

        try:
            user32.EmptyClipboard()
            h_mem = kernel32.GlobalAlloc(0x0002, len(data))
            if h_mem:
                p_mem = kernel32.GlobalLock(h_mem)
                if p_mem:
                    ctypes.memmove(p_mem, data, len(data))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(8, h_mem)
                    return True
        finally:
            user32.CloseClipboard()
    except Exception as e:
        print(f"Clipboard error: {e}")
    return False


class ScreenCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Moon's Capture")
        self.root.geometry("520x550")
        self.root.minsize(480, 520)
        self.root.resizable(True, True)

        self.current_frame_win = None
        self.blur_photo = None
        self.inside_photo = None
        self.is_running = True

        try:
            self.moon_icon = create_moon_icon()
            self.root.iconphoto(True, self.moon_icon)
        except Exception as e:
            print(f"Icon setup warning: {e}")

        self.last_captured_image = None

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_background)
        self.root.bind("<Key>", self.handle_local_hotkey)

        # --- Section 1: Frame Settings ---
        lbl_frame = tk.LabelFrame(
            root, text=" 1. Moveable & Resizable Frame ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=6
        )
        lbl_frame.pack(fill="x", padx=15, pady=5)

        input_frame = tk.Frame(lbl_frame)
        input_frame.pack(pady=3)

        tk.Label(input_frame, text="Width (px):", font=("Segoe UI", 9)).grid(row=0, column=0, padx=6, pady=3, sticky="e")
        self.entry_w = tk.Entry(input_frame, width=9, font=("Segoe UI", 9))
        self.entry_w.insert(0, "600")
        self.entry_w.grid(row=0, column=1, padx=6, pady=3)

        tk.Label(input_frame, text="Height (px):", font=("Segoe UI", 9)).grid(row=0, column=2, padx=6, pady=3, sticky="e")
        self.entry_h = tk.Entry(input_frame, width=9, font=("Segoe UI", 9))
        self.entry_h.insert(0, "400")
        self.entry_h.grid(row=0, column=3, padx=6, pady=3)

        self.btn_spawn_frame = tk.Button(
            lbl_frame, text="Create Moveable/Resizable Frame  (Alt + 1)", bg="#2563eb", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=5, cursor="hand2",
            command=self.open_moveable_frame
        )
        self.btn_spawn_frame.pack(fill="x", pady=(6, 2))

        # --- Section 2: Free Drag Area ---
        lbl_drag = tk.LabelFrame(
            root, text=" 2. Drag & Select Area ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=6
        )
        lbl_drag.pack(fill="x", padx=15, pady=5)

        self.btn_drag = tk.Button(
            lbl_drag, text="Drag to Select Area  (Alt + 2)", font=("Segoe UI", 9),
            relief="groove", pady=5, cursor="hand2", command=self.start_drag_capture
        )
        self.btn_drag.pack(fill="x")

        # --- Section 3: Upscaling & Output Options ---
        lbl_output = tk.LabelFrame(
            root, text=" 3. Resolution & Save ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=6
        )
        lbl_output.pack(fill="x", padx=15, pady=5)

        self.var_upscale = tk.BooleanVar(value=True)
        chk_upscale = tk.Checkbutton(
            lbl_output, text="Upscale to 4K + Enhance Detail & Text Clarity",
            variable=self.var_upscale, font=("Segoe UI", 9, "bold"), fg="#1e40af"
        )
        chk_upscale.pack(anchor="w", pady=(1, 4))

        self.lbl_status = tk.Label(
            lbl_output,
            text="Global Hotkeys: Alt+1 (Frame), Alt+2 (Drag), Alt+3 (Save), Alt+0 (Show/Hide)",
            font=("Segoe UI", 8), fg="#4b5563"
        )
        self.lbl_status.pack(anchor="w", pady=(0, 4))

        self.btn_save = tk.Button(
            lbl_output, text="Save as PNG...  (Alt + 3)", state="disabled",
            bg="#059669", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", pady=6, cursor="hand2", command=self.save_as_png
        )
        self.btn_save.pack(fill="x", pady=(2, 2))

        # --- Section 4: Resident Controls ---
        lbl_resident = tk.Frame(root)
        lbl_resident.pack(fill="x", padx=15, pady=(8, 4))

        btn_hide = tk.Button(
            lbl_resident, text="Hide to Background", font=("Segoe UI", 8),
            relief="groove", pady=3, cursor="hand2", command=self.hide_to_background
        )
        btn_hide.pack(side="left", expand=True, fill="x", padx=(0, 4))

        btn_quit = tk.Button(
            lbl_resident, text="Quit Application", font=("Segoe UI", 8),
            fg="#dc2626", relief="groove", pady=3, cursor="hand2", command=self.quit_app
        )
        btn_quit.pack(side="right", expand=True, fill="x", padx=(4, 0))

        # Start Global Hotkey Listener Thread
        self.hotkey_thread = threading.Thread(target=self._global_hotkey_listener, daemon=True)
        self.hotkey_thread.start()

    def hide_to_background(self):
        self.root.withdraw()

    def toggle_main_window(self):
        if self.root.winfo_viewable():
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

    def quit_app(self):
        self.is_running = False
        self.root.destroy()

    def handle_local_hotkey(self, event):
        if isinstance(event.widget, tk.Entry):
            return

        if event.char == "1" or event.keysym in ("1", "KP_1"):
            self.open_moveable_frame()
        elif event.char == "2" or event.keysym in ("2", "KP_2"):
            self.start_drag_capture()
        elif event.char == "3" or event.keysym in ("3", "KP_3"):
            if self.btn_save["state"] == "normal":
                self.save_as_png()
            else:
                self.lbl_status.config(text="Status: Please capture an image first before saving!", fg="#d97706")

    def _global_hotkey_listener(self):
        user32 = ctypes.windll.user32
        MOD_ALT = 0x0001
        MOD_NOREPEAT = 0x4000

        user32.RegisterHotKey(None, 1, MOD_ALT | MOD_NOREPEAT, 0x31)  # Alt + 1
        user32.RegisterHotKey(None, 2, MOD_ALT | MOD_NOREPEAT, 0x32)  # Alt + 2
        user32.RegisterHotKey(None, 3, MOD_ALT | MOD_NOREPEAT, 0x33)  # Alt + 3
        user32.RegisterHotKey(None, 4, MOD_ALT | MOD_NOREPEAT, 0x30)  # Alt + 0

        msg = wintypes.MSG()
        while self.is_running:
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312:
                    hk_id = msg.wParam
                    if hk_id == 1:
                        self.root.after(0, self.open_moveable_frame)
                    elif hk_id == 2:
                        self.root.after(0, self.start_drag_capture)
                    elif hk_id == 3:
                        self.root.after(0, self.hotkey_save_png)
                    elif hk_id == 4:
                        self.root.after(0, self.toggle_main_window)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        for i in (1, 2, 3, 4):
            user32.UnregisterHotKey(None, i)

    def hotkey_save_png(self):
        if self.btn_save["state"] == "normal":
            self.save_as_png()
        else:
            self.root.deiconify()
            self.root.lift()
            self.lbl_status.config(text="Status: Please capture an image first before saving (Alt+3)!", fg="#d97706")

    def capture_screen_and_blur(self):
        """Captures the entire virtual desktop spanning all monitors."""
        v_left, v_top, v_width, v_height = get_virtual_screen_geometry()
        try:
            full_screen = ImageGrab.grab(all_screens=True)
        except Exception:
            full_screen = ImageGrab.grab()

        fw, fh = full_screen.size
        v_width, v_height = fw, fh

        small_w = max(1, fw // 2)
        small_h = max(1, fh // 2)
        small_img = full_screen.resize((small_w, small_h), Image.Resampling.BILINEAR)
        blurred_small = small_img.filter(ImageFilter.BoxBlur(2))
        blurred_full = blurred_small.resize((fw, fh), Image.Resampling.BILINEAR)
        blurred_full = ImageEnhance.Brightness(blurred_full).enhance(0.95)

        if ImageTk:
            photo = ImageTk.PhotoImage(blurred_full)
        else:
            buf = io.BytesIO()
            blurred_full.save(buf, format="PNG")
            photo = tk.PhotoImage(data=buf.getvalue())

        return full_screen, photo, (v_left, v_top, v_width, v_height)

    def open_moveable_frame(self):
        try:
            w = int(self.entry_w.get().strip())
            h = int(self.entry_h.get().strip())
            if w <= 40 or h <= 40:
                raise ValueError
        except ValueError:
            w, h = 600, 400

        self.root.withdraw()
        self.root.update_idletasks()

        full_screen, self.blur_photo, (v_left, v_top, v_width, v_height) = self.capture_screen_and_blur()
        fw, fh = full_screen.size

        if self.current_frame_win and self.current_frame_win.winfo_exists():
            self.current_frame_win.destroy()

        frame_win = tk.Toplevel(self.root)
        self.current_frame_win = frame_win
        frame_win.overrideredirect(True)
        # Spans the entire virtual desktop across all monitors
        frame_win.geometry(f"{v_width}x{v_height}+{v_left}+{v_top}")
        frame_win.attributes('-topmost', True)

        canvas = tk.Canvas(frame_win, highlightthickness=0, bg="black", width=v_width, height=v_height)
        canvas.pack(fill="both", expand=True)

        # 1. Base Frosted Background across ALL monitors
        canvas.create_image(0, 0, image=self.blur_photo, anchor="nw")

        # 2. Position frame centered on current mouse cursor position
        cur_mx, cur_my = get_cursor_pos()
        mouse_cx = cur_mx - v_left
        mouse_cy = cur_my - v_top

        init_x1 = mouse_cx - w // 2
        init_y1 = mouse_cy - h // 2
        init_x1 = max(10, min(v_width - w - 10, init_x1))
        init_y1 = max(45, min(v_height - h - 10, init_y1))
        init_x2 = init_x1 + w
        init_y2 = init_y1 + h

        box = {"x1": init_x1, "y1": init_y1, "x2": init_x2, "y2": init_y2}

        # 3. Crystal Clear Inside Image Item
        crop_init = full_screen.crop((init_x1, init_y1, init_x2, init_y2))
        if ImageTk:
            self.inside_photo = ImageTk.PhotoImage(crop_init)
        else:
            buf = io.BytesIO()
            crop_init.save(buf, format="PNG")
            self.inside_photo = tk.PhotoImage(data=buf.getvalue())

        canvas.create_image(init_x1, init_y1, image=self.inside_photo, anchor="nw", tags="inside_img")

        # 4. Red Border
        border_width = 4
        half_bw = border_width // 2

        canvas.create_rectangle(
            box["x1"], box["y1"], box["x2"], box["y2"],
            outline="#ef4444", width=border_width, tags="frame_box"
        )

        toolbar = tk.Frame(frame_win, bg="#1e293b")
        lbl_info = tk.Label(
            toolbar, text=f" Moon's Capture ({w} x {h} px)",
            bg="#1e293b", fg="white", font=("Segoe UI", 9, "bold")
        )
        lbl_info.pack(side="left", padx=10, pady=6)

        def exit_frame(event=None):
            frame_win.destroy()
            self.lbl_status.config(text="Status: Ready", fg="#4b5563")

        def do_capture():
            frame_win.withdraw()
            frame_win.update_idletasks()

            def capture_and_restore():
                try:
                    self.process_capture(box["x1"], box["y1"], box["x2"], box["y2"], v_left, v_top)
                finally:
                    if frame_win.winfo_exists():
                        frame_win.deiconify()
                        frame_win.lift()

            self.root.after(30, capture_and_restore)

        btn_close = tk.Button(
            toolbar, text=" X ", bg="#ef4444", fg="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=2,
            cursor="hand2", command=exit_frame
        )
        btn_close.pack(side="right", padx=6, pady=4)

        btn_capture = tk.Button(
            toolbar, text=" Capture ", bg="#10b981", fg="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=2,
            cursor="hand2", command=do_capture
        )
        btn_capture.pack(side="right", padx=4, pady=4)

        tb_height = 36

        def update_toolbar_pos():
            cur_w = box["x2"] - box["x1"]
            outer_w = cur_w + border_width
            actual_w = max(260, outer_w)
            pos_x = max(0, min(v_width - actual_w, box["x1"] - half_bw))
            pos_y = (box["y1"] - tb_height - half_bw) if (box["y1"] - tb_height - half_bw >= 0) else (box["y2"] + half_bw)
            toolbar.place(x=pos_x, y=pos_y, width=actual_w, height=tb_height)

        def update_frame_visuals():
            canvas.coords("frame_box", box["x1"], box["y1"], box["x2"], box["y2"])
            update_toolbar_pos()

            cx1 = max(0, min(fw, box["x1"]))
            cy1 = max(0, min(fh, box["y1"]))
            cx2 = max(0, min(fw, box["x2"]))
            cy2 = max(0, min(fh, box["y2"]))
            if cx2 > cx1 and cy2 > cy1:
                cropped = full_screen.crop((cx1, cy1, cx2, cy2))
                if ImageTk:
                    self.inside_photo = ImageTk.PhotoImage(cropped)
                else:
                    buf = io.BytesIO()
                    cropped.save(buf, format="PNG")
                    self.inside_photo = tk.PhotoImage(data=buf.getvalue())
                canvas.itemconfig("inside_img", image=self.inside_photo)
                canvas.coords("inside_img", cx1, cy1)

        update_toolbar_pos()

        frame_win.lift()
        frame_win.focus_force()
        canvas.focus_set()
        frame_win.bind_all("<Escape>", exit_frame)
        frame_win.bind("<Return>", lambda e: do_capture())
        frame_win.bind("<space>", lambda e: do_capture())

        drag_data = {
            "mode": None, "start_x": 0, "start_y": 0,
            "init_x1": 0, "init_y1": 0, "init_x2": 0, "init_y2": 0,
            "active_cursor": ""
        }

        margin = 22
        corner_threshold = 30

        def get_mouse_action(x, y):
            x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

            if (abs(x - x1) <= corner_threshold) and (abs(y - y1) <= corner_threshold): return "resize_nw", "size_nw_se"
            if (abs(x - x2) <= corner_threshold) and (abs(y - y1) <= corner_threshold): return "resize_ne", "size_ne_sw"
            if (abs(x - x1) <= corner_threshold) and (abs(y - y2) <= corner_threshold): return "resize_sw", "size_ne_sw"
            if (abs(x - x2) <= corner_threshold) and (abs(y - y2) <= corner_threshold): return "resize_se", "size_nw_se"

            if abs(y - y1) <= margin and (x1 - margin <= x <= x2 + margin): return "resize_n", "size_ns"
            if abs(y - y2) <= margin and (x1 - margin <= x <= x2 + margin): return "resize_s", "size_ns"
            if abs(x - x1) <= margin and (y1 - margin <= y <= y2 + margin): return "resize_w", "size_we"
            if abs(x - x2) <= margin and (y1 - margin <= y <= y2 + margin): return "resize_e", "size_we"

            if x1 < x < x2 and y1 < y < y2:
                return "move", "fleur"

            return None, ""

        def on_canvas_motion(event):
            if drag_data["mode"]:
                return
            action, cursor = get_mouse_action(event.x, event.y)
            target_cursor = cursor if cursor else ""
            if drag_data["active_cursor"] != target_cursor:
                drag_data["active_cursor"] = target_cursor
                canvas.config(cursor=target_cursor)

        def on_canvas_press(event):
            action, _ = get_mouse_action(event.x, event.y)
            if action:
                drag_data["mode"] = action
                drag_data["start_x"] = event.x_root
                drag_data["start_y"] = event.y_root
                drag_data["init_x1"] = box["x1"]
                drag_data["init_y1"] = box["y1"]
                drag_data["init_x2"] = box["x2"]
                drag_data["init_y2"] = box["y2"]

        def on_canvas_drag(event):
            mode = drag_data["mode"]
            if not mode:
                return

            dx = event.x_root - drag_data["start_x"]
            dy = event.y_root - drag_data["start_y"]

            init_x1 = drag_data["init_x1"]
            init_y1 = drag_data["init_y1"]
            init_x2 = drag_data["init_x2"]
            init_y2 = drag_data["init_y2"]

            if mode == "move":
                cur_w = init_x2 - init_x1
                cur_h = init_y2 - init_y1
                box["x1"] = init_x1 + dx
                box["y1"] = init_y1 + dy
                box["x2"] = box["x1"] + cur_w
                box["y2"] = box["y1"] + cur_h
                update_frame_visuals()
                return

            min_w, min_h = 60, 40
            new_x1, new_x2 = init_x1, init_x2
            new_y1, new_y2 = init_y1, init_y2

            if "w" in mode:
                new_x1 = min(init_x2 - min_w, init_x1 + dx)
            elif "e" in mode:
                new_x2 = max(init_x1 + min_w, init_x2 + dx)

            if "n" in mode:
                new_y1 = min(init_y2 - min_h, init_y1 + dy)
            elif "s" in mode:
                new_y2 = max(init_y1 + min_h, init_y2 + dy)

            box["x1"], box["y1"], box["x2"], box["y2"] = new_x1, new_y1, new_x2, new_y2
            update_frame_visuals()

            cur_w = new_x2 - new_x1
            cur_h = new_y2 - new_y1
            lbl_info.config(text=f" Moon's Capture ({cur_w} x {cur_h} px)")
            self.entry_w.delete(0, tk.END); self.entry_w.insert(0, str(cur_w))
            self.entry_h.delete(0, tk.END); self.entry_h.insert(0, str(cur_h))

        def on_canvas_release(event):
            drag_data["mode"] = None
            drag_data["active_cursor"] = ""
            canvas.config(cursor="")

        canvas.bind("<Motion>", on_canvas_motion)
        canvas.bind("<ButtonPress-1>", on_canvas_press)
        canvas.bind("<B1-Motion>", on_canvas_drag)
        canvas.bind("<ButtonRelease-1>", on_canvas_release)

        def start_toolbar_move(event):
            drag_data["mode"] = "move"
            drag_data["start_x"] = event.x_root
            drag_data["start_y"] = event.y_root
            drag_data["init_x1"] = box["x1"]
            drag_data["init_y1"] = box["y1"]
            drag_data["init_x2"] = box["x2"]
            drag_data["init_y2"] = box["y2"]

        toolbar.bind("<ButtonPress-1>", start_toolbar_move)
        toolbar.bind("<B1-Motion>", on_canvas_drag)
        toolbar.bind("<ButtonRelease-1>", on_canvas_release)
        lbl_info.bind("<ButtonPress-1>", start_toolbar_move)
        lbl_info.bind("<B1-Motion>", on_canvas_drag)
        lbl_info.bind("<ButtonRelease-1>", on_canvas_release)

    def start_drag_capture(self):
        self.root.withdraw()
        self.root.update_idletasks()

        full_screen, self.blur_photo, (v_left, v_top, v_width, v_height) = self.capture_screen_and_blur()
        fw, fh = full_screen.size

        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        # Spans across all monitors
        overlay.geometry(f"{v_width}x{v_height}+{v_left}+{v_top}")
        overlay.attributes('-topmost', True)

        canvas = tk.Canvas(overlay, highlightthickness=0, bg="black", cursor="cross", width=v_width, height=v_height)
        canvas.pack(fill="both", expand=True)

        canvas.create_image(0, 0, image=self.blur_photo, anchor="nw")

        state = {
            "start_x": 0, "start_y": 0,
            "rect": None, "dim_text": None, "dim_bg": None,
            "inside_img": None, "inside_photo": None,
            "is_dragging": False
        }

        def cancel_capture(event=None):
            try:
                overlay.grab_release()
            except Exception:
                pass
            overlay.destroy()
            self.lbl_status.config(text="Status: Selection cancelled.", fg="#4b5563")

        def set_focus_and_grab():
            overlay.lift()
            overlay.focus_force()
            canvas.focus_set()
            try:
                overlay.grab_set()
            except Exception:
                pass

        overlay.after(30, set_focus_and_grab)
        overlay.bind_all("<Escape>", cancel_capture)
        overlay.bind("<Button-3>", cancel_capture)
        canvas.bind("<Button-3>", cancel_capture)

        def on_press(event):
            state["start_x"] = event.x
            state["start_y"] = event.y
            state["is_dragging"] = True

            state["inside_img"] = canvas.create_image(event.x, event.y, anchor="nw")
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#ef4444", width=3, tags="drag_box"
            )
            state["dim_bg"] = canvas.create_rectangle(0, 0, 0, 0, fill="#1e293b", outline="#ef4444", width=1, tags="dim_tag")
            state["dim_text"] = canvas.create_text(0, 0, text="", fill="white", font=("Segoe UI", 9, "bold"), anchor="nw", tags="dim_tag")

        def on_drag(event):
            if not state["is_dragging"]:
                return

            cur_x, cur_y = event.x, event.y
            x1 = min(state["start_x"], cur_x)
            y1 = min(state["start_y"], cur_y)
            x2 = max(state["start_x"], cur_x)
            y2 = max(state["start_y"], cur_y)

            w = x2 - x1
            h = y2 - y1

            if w > 2 and h > 2:
                cx1 = max(0, min(fw, x1))
                cy1 = max(0, min(fh, y1))
                cx2 = max(0, min(fw, x2))
                cy2 = max(0, min(fh, y2))
                cropped = full_screen.crop((cx1, cy1, cx2, cy2))
                if ImageTk:
                    state["inside_photo"] = ImageTk.PhotoImage(cropped)
                else:
                    buf = io.BytesIO()
                    cropped.save(buf, format="PNG")
                    state["inside_photo"] = tk.PhotoImage(data=buf.getvalue())

                canvas.itemconfig(state["inside_img"], image=state["inside_photo"])
                canvas.coords(state["inside_img"], cx1, cy1)

            canvas.coords(state["rect"], x1, y1, x2, y2)

            tag_text = f"{w} x {h} px"
            tag_y = y1 - 24 if y1 >= 28 else y1 + 8
            tag_x = max(10, min(v_width - 120, x1 + 8))

            canvas.itemconfig(state["dim_text"], text=tag_text)
            canvas.coords(state["dim_text"], tag_x, tag_y)

            bbox = canvas.bbox(state["dim_text"])
            if bbox:
                pad_x = 8
                pad_y = 3
                canvas.coords(state["dim_bg"], bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y)

            canvas.tag_raise(state["rect"])
            canvas.tag_raise(state["dim_bg"])
            canvas.tag_raise(state["dim_text"])

            self.entry_w.delete(0, tk.END)
            self.entry_w.insert(0, str(w))
            self.entry_h.delete(0, tk.END)
            self.entry_h.insert(0, str(h))

        def on_release(event):
            if not state["is_dragging"]:
                return
            state["is_dragging"] = False

            end_x, end_y = event.x, event.y
            try:
                overlay.grab_release()
            except Exception:
                pass
            overlay.destroy()

            x1 = min(state["start_x"], end_x)
            y1 = min(state["start_y"], end_y)
            x2 = max(state["start_x"], end_x)
            y2 = max(state["start_y"], end_y)

            if x2 - x1 > 5 and y2 - y1 > 5:
                self.root.after(30, lambda: self.process_capture(x1, y1, x2, y2, v_left, v_top))
            else:
                pass

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind_all("<ButtonRelease-1>", on_release)

    def process_capture(self, cx1, cy1, cx2, cy2, v_left=0, v_top=0):
        self.root.withdraw()
        self.root.update_idletasks()

        try:
            cx1_i = int(round(min(cx1, cx2)))
            cy1_i = int(round(min(cy1, cy2)))
            cx2_i = int(round(max(cx1, cx2)))
            cy2_i = int(round(max(cy1, cy2)))

            if cx2_i <= cx1_i or cy2_i <= cy1_i:
                return

            sx1 = cx1_i + v_left
            sy1 = cy1_i + v_top
            sx2 = cx2_i + v_left
            sy2 = cy2_i + v_top

            time.sleep(0.04)

            try:
                img = ImageGrab.grab(bbox=(sx1, sy1, sx2, sy2), all_screens=True)
                req_w = cx2_i - cx1_i
                req_h = cy2_i - cy1_i
                if abs(img.width - req_w) > 4 or abs(img.height - req_h) > 4:
                    full = ImageGrab.grab(all_screens=True)
                    img = full.crop((cx1_i, cy1_i, cx2_i, cy2_i))
            except Exception:
                full = ImageGrab.grab(all_screens=True)
                img = full.crop((cx1_i, cy1_i, cx2_i, cy2_i))

            orig_w, orig_h = img.size

            is_upscaled = self.var_upscale.get()
            if is_upscaled:
                target_w = orig_w * 2
                target_h = orig_h * 2
                img = img.resize((target_w, target_h), Image.Resampling.BICUBIC)
                img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=1))

            self.last_captured_image = img

            clipboard_ok = copy_to_clipboard(img)

            final_w, final_h = img.size
            upscale_text = f" -> 4K Enhanced {final_w}x{final_h} px" if is_upscaled else ""
            status_msg = f"Captured ({orig_w}x{orig_h}{upscale_text}) - "
            status_msg += "Copied to Clipboard! (Press Alt+3 to Save)" if clipboard_ok else "Ready to save! (Press Alt+3)"

            self.lbl_status.config(text=status_msg, fg="#16a34a" if clipboard_ok else "#d97706")
            self.btn_save.config(state="normal")
        except Exception as e:
            messagebox.showerror("Capture Error", f"Failed to capture screen:\n{str(e)}")

    def save_as_png(self):
        if not self.last_captured_image:
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="Save Captured Image As"
        )
        if filepath:
            try:
                self.last_captured_image.save(filepath, "PNG")
                messagebox.showinfo("Saved", f"Image saved successfully!\n{filepath}")
                self.lbl_status.config(text="Saved to PNG successfully.", fg="#2563eb")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenCaptureApp(root)
    root.mainloop()
