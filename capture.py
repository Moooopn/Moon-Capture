import io
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageGrab, ImageFilter, ImageDraw

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
        for _ in range(10):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.05)

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
        self.root.minsize(480, 500)
        self.root.resizable(True, True)

        self.current_frame_win = None

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
            font=("Segoe UI", 9, "bold"), padx=15, pady=8
        )
        lbl_frame.pack(fill="x", padx=15, pady=6)

        input_frame = tk.Frame(lbl_frame)
        input_frame.pack(pady=4)

        tk.Label(input_frame, text="Width (px):", font=("Segoe UI", 9)).grid(row=0, column=0, padx=6, pady=4, sticky="e")
        self.entry_w = tk.Entry(input_frame, width=9, font=("Segoe UI", 9))
        self.entry_w.insert(0, "600")
        self.entry_w.grid(row=0, column=1, padx=6, pady=4)

        tk.Label(input_frame, text="Height (px):", font=("Segoe UI", 9)).grid(row=0, column=2, padx=6, pady=4, sticky="e")
        self.entry_h = tk.Entry(input_frame, width=9, font=("Segoe UI", 9))
        self.entry_h.insert(0, "400")
        self.entry_h.grid(row=0, column=3, padx=6, pady=4)

        self.btn_spawn_frame = tk.Button(
            lbl_frame, text="Create Moveable/Resizable Frame  [ 1 ]", bg="#2563eb", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=6, cursor="hand2",
            command=self.open_moveable_frame
        )
        self.btn_spawn_frame.pack(fill="x", pady=(8, 2))

        # --- Section 2: Free Drag Area ---
        lbl_drag = tk.LabelFrame(
            root, text=" 2. Drag & Select Area ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=8
        )
        lbl_drag.pack(fill="x", padx=15, pady=6)

        self.btn_drag = tk.Button(
            lbl_drag, text="Drag to Select Area  [ 2 ]", font=("Segoe UI", 9),
            relief="groove", pady=6, cursor="hand2", command=self.start_drag_capture
        )
        self.btn_drag.pack(fill="x")

        # --- Section 3: Upscaling & Output Options ---
        lbl_output = tk.LabelFrame(
            root, text=" 3. Resolution & Save ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=8
        )
        lbl_output.pack(fill="x", padx=15, pady=8)

        self.var_upscale = tk.BooleanVar(value=True)
        chk_upscale = tk.Checkbutton(
            lbl_output, text="Upscale to 4K + Enhance Detail & Text Clarity",
            variable=self.var_upscale, font=("Segoe UI", 9, "bold"), fg="#1e40af"
        )
        chk_upscale.pack(anchor="w", pady=(2, 6))

        self.lbl_status = tk.Label(lbl_output, text="Status: Ready  (Hotkeys: 1=Frame, 2=Drag, 3=Save)", font=("Segoe UI", 9), fg="#4b5563")
        self.lbl_status.pack(anchor="w", pady=(0, 6))

        self.btn_save = tk.Button(
            lbl_output, text="Save as PNG...  [ 3 ]", state="disabled",
            bg="#059669", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", pady=7, cursor="hand2", command=self.save_as_png
        )
        self.btn_save.pack(fill="x", pady=(2, 4))

    def handle_hotkey(self, event):
        # Do not intercept hotkeys if typing in Width or Height entry boxes
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
                self.lbl_status.config(text="Status: Please capture an image first before saving [3]!", fg="#d97706")

    def open_moveable_frame(self):
        try:
            w = int(self.entry_w.get().strip())
            h = int(self.entry_h.get().strip())
            if w <= 40 or h <= 40:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter positive numbers greater than 40.")
            return

        if self.current_frame_win and self.current_frame_win.winfo_exists():
            self.current_frame_win.destroy()

        frame_win = tk.Toplevel(self.root)
        self.current_frame_win = frame_win
        frame_win.overrideredirect(True)
        frame_win.attributes('-topmost', True)

        transparent_color = "#ff00ff"
        frame_win.wm_attributes("-transparentcolor", transparent_color)

        # 1. Top Draggable Toolbar
        toolbar = tk.Frame(frame_win, bg="#1e293b")
        toolbar.pack(fill="x", side="top")

        lbl_info = tk.Label(
            toolbar, text=f" Moon's Capture ({w} x {h} px) - [Enter] to Capture",
            bg="#1e293b", fg="white", font=("Segoe UI", 9, "bold")
        )
        lbl_info.pack(side="left", padx=10, pady=6)

        def do_capture():
            frame_win.update_idletasks()
            cx = canvas.winfo_rootx()
            cy = canvas.winfo_rooty()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()

            # Temporarily hide frame for 120ms to avoid capturing its own red border/toolbar
            frame_win.withdraw()

            def capture_and_restore():
                try:
                    self.process_capture(cx, cy, cx + cw, cy + ch)
                finally:
                    if frame_win.winfo_exists():
                        frame_win.deiconify()
                        frame_win.lift()

            self.root.after(120, capture_and_restore)

        btn_close = tk.Button(
            toolbar, text=" X ", bg="#ef4444", fg="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=2,
            cursor="hand2", command=frame_win.destroy
        )
        btn_close.pack(side="right", padx=6, pady=4)

        btn_capture = tk.Button(
            toolbar, text=" Capture ", bg="#10b981", fg="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=2,
            cursor="hand2", command=do_capture
        )
        btn_capture.pack(side="right", padx=4, pady=4)

        # Bind Enter and Spacebar to capture while frame is active
        frame_win.bind("<Return>", lambda e: do_capture())
        frame_win.bind("<space>", lambda e: do_capture())
        frame_win.bind("<Escape>", lambda e: frame_win.destroy())

        # Toolbar Drag Logic
        def start_move(event):
            frame_win.drag_start_x = event.x_root
            frame_win.drag_start_y = event.y_root
            frame_win.win_x = frame_win.winfo_x()
            frame_win.win_y = frame_win.winfo_y()

        def do_move(event):
            dx = event.x_root - frame_win.drag_start_x
            dy = event.y_root - frame_win.drag_start_y
            frame_win.geometry(f"+{frame_win.win_x + dx}+{frame_win.win_y + dy}")

        toolbar.bind("<ButtonPress-1>", start_move)
        toolbar.bind("<B1-Motion>", do_move)
        lbl_info.bind("<ButtonPress-1>", start_move)
        lbl_info.bind("<B1-Motion>", do_move)

        # 2. Transparent Hollow Canvas
        canvas = tk.Canvas(frame_win, width=w, height=h, bg=transparent_color, highlightthickness=0)
        canvas.pack(side="top")

        canvas.create_rectangle(1, 1, w - 2, h - 2, outline="#ef4444", width=2, tags="border")
        grip_size = 16
        canvas.create_rectangle(w - grip_size, h - grip_size, w - 1, h - 1, fill="#ef4444", outline="white", tags="grip")
        canvas.create_text(w - 8, h - 8, text="⇲", fill="white", font=("Segoe UI", 8, "bold"), tags="grip_text")

        def start_resize(event):
            frame_win.resize_start_x = event.x_root
            frame_win.resize_start_y = event.y_root
            frame_win.initial_w = canvas.winfo_width()
            frame_win.initial_h = canvas.winfo_height()

        def do_resize(event):
            dx = event.x_root - frame_win.resize_start_x
            dy = event.y_root - frame_win.resize_start_y
            new_w = max(80, frame_win.initial_w + dx)
            new_h = max(50, frame_win.initial_h + dy)

            canvas.config(width=new_w, height=new_h)
            canvas.coords("border", 1, 1, new_w - 2, new_h - 2)
            canvas.coords("grip", new_w - grip_size, new_h - grip_size, new_w - 1, new_h - 1)
            canvas.coords("grip_text", new_w - 8, new_h - 8)

            lbl_info.config(text=f" Moon's Capture ({new_w} x {new_h} px) - [Enter] to Capture")
            self.entry_w.delete(0, tk.END)
            self.entry_w.insert(0, str(new_w))
            self.entry_h.delete(0, tk.END)
            self.entry_h.insert(0, str(new_h))

        for tag in ("grip", "grip_text"):
            canvas.tag_bind(tag, "<ButtonPress-1>", start_resize)
            canvas.tag_bind(tag, "<B1-Motion>", do_resize)
            canvas.tag_bind(tag, "<Enter>", lambda e: canvas.config(cursor="size_nw_se"))
            canvas.tag_bind(tag, "<Leave>", lambda e: canvas.config(cursor=""))

        # Center frame on screen
        frame_win.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(20, (screen_w - frame_win.winfo_reqwidth()) // 2)
        pos_y = max(20, (screen_h - frame_win.winfo_reqheight()) // 2)
        frame_win.geometry(f"+{pos_x}+{pos_y}")

    def start_drag_capture(self):
        self.root.withdraw()

        overlay = tk.Toplevel(self.root)
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-alpha', 0.3)
        overlay.attributes('-topmost', True)

        canvas = tk.Canvas(overlay, cursor="cross", bg="gray")
        canvas.pack(fill="both", expand=True)

        state = {"start_x": 0, "start_y": 0, "rect": None}

        def on_press(event):
            state["start_x"] = event.x
            state["start_y"] = event.y
            state["rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#ef4444", width=2, fill="black"
            )

        def on_drag(event):
            canvas.coords(state["rect"], state["start_x"], state["start_y"], event.x, event.y)

        def on_release(event):
            end_x, end_y = event.x, event.y
            overlay.destroy()

            x1 = min(state["start_x"], end_x)
            y1 = min(state["start_y"], end_y)
            x2 = max(state["start_x"], end_x)
            y2 = max(state["start_y"], end_y)

            self.entry_w.delete(0, tk.END)
            self.entry_w.insert(0, str(x2 - x1))
            self.entry_h.delete(0, tk.END)
            self.entry_h.insert(0, str(y2 - y1))

            if x2 - x1 > 5 and y2 - y1 > 5:
                self.root.after(120, lambda: self.process_capture(x1, y1, x2, y2))
            else:
                self.root.deiconify()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", lambda e: (overlay.destroy(), self.root.deiconify()))

    def process_capture(self, x1, y1, x2, y2):
        self.root.withdraw()
        time.sleep(0.05)

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

            # 4K Upscaling + Edge Clarification
            is_upscaled = self.var_upscale.get()
            if is_upscaled:
                target_w = orig_w * 2
                target_h = orig_h * 2
                resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                img = img.resize((target_w, target_h), resample_filter)
                img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=2))

            self.last_captured_image = img

            # 1. Copy to Clipboard
            clipboard_ok = copy_to_clipboard(img)

            # 2. Update Status
            final_w, final_h = img.size
            upscale_text = f" -> 4K Enhanced {final_w}x{final_h} px" if is_upscaled else ""
            status_msg = f"Captured ({orig_w}x{orig_h}{upscale_text}) - "
            status_msg += "Copied to Clipboard! (Press [3] to Save)" if clipboard_ok else "Ready to save! (Press [3])"

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
