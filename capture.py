import io
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageGrab

# Enable DPI Awareness for accurate pixel matching on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def copy_to_clipboard(image):
    """Safely copies a PIL Image to Windows Clipboard (64-bit compatible DIB)."""
    try:
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Remove standard BMP header
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
        self.root.title("Screen Capture Tool (4K Upscale)")
        self.root.geometry("500x440")
        self.root.minsize(460, 400)
        self.root.resizable(True, True)

        self.last_captured_image = None

        # --- Section 1: Frame Settings ---
        lbl_frame = tk.LabelFrame(
            root, text=" 1. Moveable & Resizable Frame ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=10
        )
        lbl_frame.pack(fill="x", padx=15, pady=8)

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
            lbl_frame, text="Create Moveable/Resizable Frame", bg="#2563eb", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=6, cursor="hand2",
            command=self.open_moveable_frame
        )
        self.btn_spawn_frame.pack(fill="x", pady=(8, 2))

        # --- Section 2: Free Drag Area ---
        lbl_drag = tk.LabelFrame(
            root, text=" 2. Drag & Select Area ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=10
        )
        lbl_drag.pack(fill="x", padx=15, pady=5)

        self.btn_drag = tk.Button(
            lbl_drag, text="Drag to Select Area", font=("Segoe UI", 9),
            relief="groove", pady=6, cursor="hand2", command=self.start_drag_capture
        )
        self.btn_drag.pack(fill="x")

        # --- Section 3: Upscaling & Output Options ---
        lbl_output = tk.LabelFrame(
            root, text=" 3. Resolution & Save ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=10
        )
        lbl_output.pack(fill="x", padx=15, pady=8)

        # 4K Upscale Toggle (Enabled by default)
        self.var_upscale = tk.BooleanVar(value=True)
        chk_upscale = tk.Checkbutton(
            lbl_output, text="Upscale to 4K Quality (2x Resolution, Lanczos Filter)",
            variable=self.var_upscale, font=("Segoe UI", 9, "bold"), fg="#1e40af"
        )
        chk_upscale.pack(anchor="w", pady=(0, 6))

        self.lbl_status = tk.Label(lbl_output, text="Status: Ready", font=("Segoe UI", 9), fg="#4b5563")
        self.lbl_status.pack(anchor="w", pady=(0, 6))

        self.btn_save = tk.Button(
            lbl_output, text="Save as PNG...", state="disabled",
            bg="#059669", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", pady=6, cursor="hand2", command=self.save_as_png
        )
        self.btn_save.pack(fill="x")

    def open_moveable_frame(self):
        try:
            w = int(self.entry_w.get().strip())
            h = int(self.entry_h.get().strip())
            if w <= 40 or h <= 40:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter positive numbers greater than 40.")
            return

        frame_win = tk.Toplevel(self.root)
        frame_win.overrideredirect(True)
        frame_win.attributes('-topmost', True)

        transparent_color = "#ff00ff"
        frame_win.wm_attributes("-transparentcolor", transparent_color)

        # 1. Top Draggable Toolbar
        toolbar = tk.Frame(frame_win, bg="#1e293b")
        toolbar.pack(fill="x", side="top")

        lbl_info = tk.Label(
            toolbar, text=f" Move Toolbar ({w} x {h} px)",
            bg="#1e293b", fg="white", font=("Segoe UI", 9, "bold")
        )
        lbl_info.pack(side="left", padx=10, pady=6)

        def do_capture():
            frame_win.update_idletasks()
            cx = canvas.winfo_rootx()
            cy = canvas.winfo_rooty()
            cw = canvas.
