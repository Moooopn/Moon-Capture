import io
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageGrab, ImageFilter, ImageDraw, ImageEnhance

# Use ImageTk for direct zero-copy GPU/GUI memory rendering
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

# Enable Per-Monitor DPI Awareness for accurate pixel matching on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def create_moon_icon():
    """Generates a high-quality full moon icon with crater details."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Subtle Outer Glow
    draw.ellipse((3, 3, 61, 61), fill=(255, 235, 150, 60))

    # 2. Main Full Moon Body
    draw.ellipse((4, 4, 60, 60), fill="#FDD835", outline="#FBC02D", width=2)

    # 3. Soft Moon Craters & Surface Details
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
        data = output.getvalue()[14:]  # Remove standard BMP 14-byte header
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
            h_mem = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
            if h_mem:
                p_mem = kernel32.GlobalLock(h_mem)
                if p_mem:
                    ctypes.memmove(p_mem, data, len(data))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(8, h_mem)  # CF_DIB
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
        self.root.geometry("520x500")
        self.root.minsize(480, 480)
        self.root.resizable(True, True)

        self.current_frame_win = None
        self.blur_photo = None
        self.inside_photo = None

        # Set Moon Icon
        try:
            self.moon_icon = create_moon_icon()
            self.root.iconphoto(True, self.moon_icon)
        except Exception as e:
            print(f"Icon setup warning: {e}")

        self.last_captured_image = None

        # Bind Global Hotkeys (1, 2, 3)
        self.root.bind("<Key>", self.handle_hotkey)

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
            lbl_frame, text="Create Moveable/Resizable Frame", bg="#2563eb", fg="white",
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
            lbl_drag, text="Drag to Select Area", font=("Segoe UI", 9),
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

        self.lbl_status = tk.Label(lbl_output, text="Status: Ready", font=("Segoe UI", 9), fg="#4b5563")
        self.lbl_status.pack(anchor="w", pady=(0, 4))

        self.btn_save = tk.Button(
            lbl_output, text="Save as PNG...", state="disabled",
            bg="#059669", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", pady=6, cursor="hand2", command=self.save_as_png
        )
        self.btn_save.pack(fill="x", pady=(2, 2))

    def handle_hotkey(self, event):
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

    def capture_screen_and_blur(self):
        """Captures full screen and prepares frosted background."""
        try:
            full_screen = ImageGrab.grab(all_screens=True)
        except Exception:
            full_screen = ImageGrab.grab()

        fw, fh = full_screen.size
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

        return full_screen, photo

    def open_moveable_frame(self):
        try:
            w = int(self.entry_w.get().strip())
            h = int(self.entry_h.get().strip())
            if w <= 40 or h <= 40:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter positive numbers greater than 40.")
            return

        self.root.withdraw()
        self.root.update_idletasks()

        full_screen, self.blur_photo = self.capture_screen_and_blur()
        fw, fh = full_screen.size

        if self.current_frame_win and self.current_frame_win.winfo_exists():
            self.current_frame_win.destroy()

        frame_win = tk.Toplevel(self.root)
        self.current_frame_win = frame_win
        frame_win.attributes('-fullscreen', True)
        frame_win.attributes('-topmost', True)

        canvas = tk.Canvas(frame_win, highlightthickness=0, bg="black")
        canvas.pack(fill="both", expand=True)

        # 1. Base Frosted Background Image
        canvas.create_image(0, 0, image=self.blur_photo, anchor="nw")

        # Initial coordinates
        screen_w = frame_win.winfo_screenwidth()
        screen_h = frame_win.winfo_screenheight()
        init_x1 = max(40, (screen_w - w) // 2)
        init_y1 = max(50, (screen_h - h) // 2)
        init_x2 = init_x1 + w
        init_y2 = init_y1 + h

        box = {"x1": init_x1, "y1": init_y1, "x2": init_x2, "y2": init_y2}

        # 2. Crystal Clear Inside Image Item
        crop_init = full_screen.crop((init_x1, init_y1, init_x2, init_y2))
        if ImageTk:
            self.inside_photo = ImageTk.PhotoImage(crop_init)
        else:
            buf = io.BytesIO()
            crop_init.save(buf, format="PNG")
            self.inside_photo = tk.PhotoImage(data=buf.getvalue())

        canvas.create_image(init_x1, init_y1, image=self.inside_photo, anchor="nw", tags="inside_img")

        # 3. Red Border (Width: 4px)
        canvas.create_rectangle(
            box["x1"], box["y1"], box["x2"], box["y2"],
            outline="#ef4444", width=4, tags="frame_box"
        )

        toolbar = tk.Frame(frame_win, bg="#1e293b")
        lbl_info = tk.Label(
            toolbar, text=f" Moon's Capture ({w} x {h} px)",
            bg="#1e293b", fg="white", font=("Segoe UI", 9, "bold")
        )
        lbl_info.pack(side="left", padx=10, pady=6)

        def exit_frame(event=None):
            frame_win.destroy()
            self.root.deiconify()
            self.lbl_status.config(text="Status: Ready", fg="#4b5563")

        def do_capture():
            frame_win.withdraw()
            frame_win.update_idletasks()

            def capture_and_restore():
                try:
                    self.process_capture(box["x1"], box["y1"], box["x2"], box["y2"])
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
            pos_y = box["y1"] - tb_height if (box["y1"] - tb_height >= 0) else box["y2"]
            toolbar.place(x=box["x1"], y=pos_y, width=max(260, cur_w), height=tb_height)

        def update_frame_visuals():
            canvas.coords("frame_box", box["x1"], box["y1"], box["x2"], box["y2"])
            update_toolbar_pos()

            # Refresh clear inside view
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

        # Keyboard shortcuts
        frame_win.focus_force()
        canvas.focus_set()
        frame_win.bind_all("<Escape>", exit_frame)
        frame_win.bind("<Return>", lambda e: do_capture())
        frame_win.bind("<space>", lambda e: do_capture())

        # Move/Resize unified engine
        drag_data = {
            "mode": None, "start_x": 0, "start_y": 0,
            "init_x1": 0, "init_y1": 0, "init_x2": 0, "init_y2": 0,
            "active_cursor": ""
        }

        margin = 22
        corner_threshold = 30

        def get_mouse_action(x, y):
            x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

            # 1. Check Corners (Resize)
            if (abs(x - x1) <= corner_threshold) and (abs(y - y1) <= corner_threshold): return "resize_nw", "size_nw_se"
            if (abs(x - x2) <= corner_threshold) and (abs(y - y1) <= corner_threshold): return "resize_ne", "size_ne_sw"
            if (abs(x - x1) <= corner_threshold) and (abs(y - y2) <= corner_threshold): return "resize_sw", "size_ne_sw"
            if (abs(x - x2) <= corner_threshold) and (abs(y - y2) <= corner_threshold): return "resize_se", "size_nw_se"

            # 2. Check Edges (Resize)
            if abs(y - y1) <= margin and (x1 - margin <= x <= x2 + margin): return "resize_n", "size_ns"
            if abs(y - y2) <= margin and (x1 - margin <= x <= x2 + margin): return "resize_s", "size_ns"
            if abs(x - x1) <= margin and (y1 - margin <= y <= y2 + margin): return "resize_w", "size_we"
            if abs(x - x2) <= margin and (y1 - margin <= y <= y2 + margin): return "resize_e", "size_we"

            # 3. Inside Frame Body (Move!)
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

            # A. Inside Frame Drag -> Move Frame
            if mode == "move":
                cur_w = init_x2 - init_x1
                cur_h = init_y2 - init_y1
                box["x1"] = init_x1 + dx
                box["y1"] = init_y1 + dy
                box["x2"] = box["x1"] + cur_w
                box["y2"] = box["y1"] + cur_h
                update_frame_visuals()
                return

            # B. Edge/Corner Drag -> Resize Frame
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

        # Toolbar Drag Logic (Also moves the frame)
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

        full_screen, self.blur_photo = self.capture_screen_and_blur()
        fw, fh = full_screen.size

        overlay = tk.Toplevel(self.root)
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-topmost', True)

        canvas = tk.Canvas(overlay, highlightthickness=0, bg="black", cursor="cross")
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
            self.root.deiconify()
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
            # Dimension badge (dark background + white text)
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

            # Auto-fitting Dimension Badge (dynamically calculates text bounds)
            tag_text = f"{w} x {h} px"
            tag_y = y1 - 24 if y1 >= 28 else y1 + 8
            tag_x = max(10, x1 + 8)

            canvas.itemconfig(state["dim_text"], text=tag_text)
            canvas.coords(state["dim_text"], tag_x, tag_y)

            # Calculate actual text bounding box and resize background rectangle with padding
            bbox = canvas.bbox(state["dim_text"])
            if bbox:
                pad_x = 8
                pad_y = 3
                canvas.coords(state["dim_bg"], bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y)

            # Ensure tags always float above selection area
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
                self.root.after(30, lambda: self.process_capture(x1, y1, x2, y2))
            else:
                self.root.deiconify()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind_all("<ButtonRelease-1>", on_release)

    def process_capture(self, x1, y1, x2, y2):
        self.root.withdraw()
        self.root.update_idletasks()

        try:
            x1_i = int(round(min(x1, x2)))
            y1_i = int(round(min(y1, y2)))
            x2_i = int(round(max(x1, x2)))
            y2_i = int(round(max(y1, y2)))

            if x2_i <= x1_i or y2_i <= y1_i:
                return

            try:
                img = ImageGrab.grab(bbox=(x1_i, y1_i, x2_i, y2_i), all_screens=True)
            except Exception:
                img = ImageGrab.grab(bbox=(x1_i, y1_i, x2_i, y2_i))

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
            status_msg += "Copied to Clipboard!" if clipboard_ok else "Ready to save!"

            self.lbl_status.config(text=status_msg, fg="#16a34a" if clipboard_ok else "#d97706")
            self.btn_save.config(state="normal")
        except Exception as e:
            messagebox.showerror("Capture Error", f"Failed to capture screen:\n{str(e)}")
        finally:
            self.root.deiconify()

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
