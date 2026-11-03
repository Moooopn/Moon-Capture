import io
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab

# Enable Per-Monitor DPI Awareness for accurate physical pixel alignment on Windows
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
        data = output.getvalue()[14:]  # Remove standard BMP 14-byte header
        output.close()

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Explicitly configure 64-bit ctypes signatures to prevent memory access violations
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

        # Retry opening clipboard up to 10 times in case it is held by another process
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
            # GMEM_MOVEABLE = 0x0002
            h_mem = kernel32.GlobalAlloc(0x0002, len(data))
            if h_mem:
                p_mem = kernel32.GlobalLock(h_mem)
                if p_mem:
                    ctypes.memmove(p_mem, data, len(data))
                    kernel32.GlobalUnlock(h_mem)
                    # CF_DIB = 8
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
        self.root.title("Screen Capture Tool")
        self.root.geometry("480x400")
        self.root.minsize(440, 360)
        self.root.resizable(True, True)

        self.last_captured_image = None

        # --- Section 1: Fixed Dimension Capture ---
        lbl_frame = tk.LabelFrame(
            root, text=" 1. Moveable Frame by Pixel Size ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=12
        )
        lbl_frame.pack(fill="x", padx=15, pady=10)

        input_frame = tk.Frame(lbl_frame)
        input_frame.pack(pady=4)

        tk.Label(input_frame, text="Width (px):", font=("Segoe UI", 9)).grid(row=0, column=0, padx=6, pady=4, sticky="e")
        self.entry_w = tk.Entry(input_frame, width=10, font=("Segoe UI", 9))
        self.entry_w.insert(0, "600")
        self.entry_w.grid(row=0, column=1, padx=6, pady=4)

        tk.Label(input_frame, text="Height (px):", font=("Segoe UI", 9)).grid(row=0, column=2, padx=6, pady=4, sticky="e")
        self.entry_h = tk.Entry(input_frame, width=10, font=("Segoe UI", 9))
        self.entry_h.insert(0, "400")
        self.entry_h.grid(row=0, column=3, padx=6, pady=4)

        self.btn_spawn_frame = tk.Button(
            lbl_frame, text="Create Moveable Frame", bg="#2563eb", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=6, cursor="hand2",
            command=self.open_moveable_frame
        )
        self.btn_spawn_frame.pack(fill="x", pady=(10, 2))

        # --- Section 2: Free Drag Capture ---
        lbl_drag = tk.LabelFrame(
            root, text=" 2. Drag & Select Area ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=12
        )
        lbl_drag.pack(fill="x", padx=15, pady=5)

        self.btn_drag = tk.Button(
            lbl_drag, text="Drag to Select Area", font=("Segoe UI", 9),
            relief="groove", pady=6, cursor="hand2", command=self.start_drag_capture
        )
        self.btn_drag.pack(fill="x")

        # --- Section 3: Status & Output ---
        lbl_output = tk.LabelFrame(
            root, text=" Status & Save ",
            font=("Segoe UI", 9, "bold"), padx=15, pady=12
        )
        lbl_output.pack(fill="x", padx=15, pady=10)

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
            if w <= 10 or h <= 10:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter positive numbers greater than 10.")
            return

        # Frame window setup
        frame_win = tk.Toplevel(self.root)
        frame_win.overrideredirect(True)
        frame_win.attributes('-topmost', True)

        transparent_color = "#ff00ff"
        frame_win.wm_attributes("-transparentcolor", transparent_color)

        # 1. Top Draggable Toolbar
        toolbar = tk.Frame(frame_win, bg="#1e293b")
        toolbar.pack(fill="x", side="top")

        lbl_info = tk.Label(
            toolbar, text=f" Drag Toolbar ({w} x {h} px)",
            bg="#1e293b", fg="white", font=("Segoe UI", 9, "bold")
        )
        lbl_info.pack(side="left", padx=10, pady=6)

        def do_capture():
            frame_win.update_idletasks()
            cx = canvas.winfo_rootx()
            cy = canvas.winfo_rooty()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            frame_win.destroy()
            # 180ms delay to allow screen refresh before taking screenshot
            self.root.after(180, lambda: self.process_capture(cx, cy, cx + cw, cy + ch))

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

        # Smooth window drag logic using root screen coordinates
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

        # 2. Transparent Hollow Canvas with Visible 4-side Red Border
        canvas = tk.Canvas(frame_win, width=w, height=h, bg=transparent_color, highlightthickness=0)
        canvas.pack(side="top")
        canvas.create_rectangle(1, 1, w - 2, h - 2, outline="#ef4444", width=2)

        # Auto position frame near screen center
        frame_win.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        req_w = frame_win.winfo_reqwidth()
        req_h = frame_win.winfo_reqheight()
        pos_x = max(20, (screen_w - req_w) // 2)
        pos_y = max(20, (screen_h - req_h) // 2)
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

            if x2 - x1 > 5 and y2 - y1 > 5:
                self.root.after(180, lambda: self.process_capture(x1, y1, x2, y2))
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

            # Capture screen area (supports multi-monitor setups)
            try:
                img = ImageGrab.grab(bbox=(x1_i, y1_i, x2_i, y2_i), all_screens=True)
            except Exception:
                img = ImageGrab.grab(bbox=(x1_i, y1_i, x2_i, y2_i))

            self.last_captured_image = img

            # 1. Copy image to Windows Clipboard
            clipboard_ok = copy_to_clipboard(img)

            # 2. Update status and enable Save button
            w = x2_i - x1_i
            h = y2_i - y1_i
            if clipboard_ok:
                self.lbl_status.config(
                    text=f"Captured ({w}x{h} px) - Copied to Clipboard!",
                    fg="#16a34a"
                )
            else:
                self.lbl_status.config(
                    text=f"Captured ({w}x{h} px) - Clipboard busy, ready to save!",
                    fg="#d97706"
                )

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
