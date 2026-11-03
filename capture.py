import io
import time
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab

# Enable DPI Awareness for accurate pixel coordinates on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def copy_to_clipboard(image):
    """Copies a PIL Image directly to Windows Clipboard as DIB format."""
    output = io.BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # Remove standard BMP 14-byte header
    output.close()

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if user32.OpenClipboard(None):
        user32.EmptyClipboard()
        h_mem = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE = 0x0002
        p_mem = kernel32.GlobalLock(h_mem)
        ctypes.memmove(p_mem, data, len(data))
        kernel32.GlobalUnlock(h_mem)
        user32.SetClipboardData(8, h_mem)  # CF_DIB = 8
        user32.CloseClipboard()


class ScreenCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Capture Tool")
        self.root.geometry("380x350")
        self.root.resizable(False, False)

        self.last_captured_image = None

        # --- Section 1: Fixed Dimension Capture ---
        lbl_frame = tk.LabelFrame(root, text=" 1. Moveable Frame by Pixel Size ", padx=15, pady=10)
        lbl_frame.pack(fill="x", padx=15, pady=10)

        input_frame = tk.Frame(lbl_frame)
        input_frame.pack()

        tk.Label(input_frame, text="Width (px):").grid(row=0, column=0, padx=5, pady=4, sticky="e")
        self.entry_w = tk.Entry(input_frame, width=8)
        self.entry_w.insert(0, "600")
        self.entry_w.grid(row=0, column=1, padx=5, pady=4)

        tk.Label(input_frame, text="Height (px):").grid(row=0, column=2, padx=5, pady=4, sticky="e")
        self.entry_h = tk.Entry(input_frame, width=8)
        self.entry_h.insert(0, "400")
        self.entry_h.grid(row=0, column=3, padx=5, pady=4)

        self.btn_spawn_frame = tk.Button(
            lbl_frame, text="Create Moveable Frame", bg="#2563eb", fg="white",
            relief="flat", pady=4, command=self.open_moveable_frame
        )
        self.btn_spawn_frame.pack(fill="x", pady=(8, 2))

        # --- Section 2: Free Drag Capture ---
        lbl_drag = tk.LabelFrame(root, text=" 2. Drag & Select Area ", padx=15, pady=10)
        lbl_drag.pack(fill="x", padx=15, pady=5)

        self.btn_drag = tk.Button(
            lbl_drag, text="Drag to Select Area", pady=4, command=self.start_drag_capture
        )
        self.btn_drag.pack(fill="x")

        # --- Section 3: Output & Actions ---
        lbl_output = tk.LabelFrame(root, text=" Status & Save ", padx=15, pady=10)
        lbl_output.pack(fill="x", padx=15, pady=10)

        self.lbl_status = tk.Label(lbl_output, text="Status: Ready", fg="gray")
        self.lbl_status.pack(anchor="w", pady=(0, 5))

        self.btn_save = tk.Button(
            lbl_output, text="Save as PNG...", state="disabled",
            bg="#059669", fg="white", relief="flat", pady=5, command=self.save_as_png
        )
        self.btn_save.pack(fill="x")

    def open_moveable_frame(self):
        try:
            w = int(self.entry_w.get().strip())
            h = int(self.entry_h.get().strip())
            if w <= 0 or h <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid positive numbers for Width and Height.")
            return

        # Frame window
        frame_win = tk.Toplevel(self.root)
        frame_win.overrideredirect(True)
        frame_win.attributes('-topmost', True)

        toolbar_height = 36
        total_height = h + toolbar_height

        # Position near center of screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(50, (screen_w - w) // 2)
        pos_y = max(50, (screen_h - total_height) // 2)
        frame_win.geometry(f"{w}x{total_height}+{pos_x}+{pos_y}")

        # Make interior transparent using magenta color-key
        transparent_color = "#ff00ff"
        frame_win.wm_attributes("-transparentcolor", transparent_color)

        # 1. Top Draggable Toolbar
        toolbar = tk.Frame(frame_win, height=toolbar_height, bg="#1e293b")
        toolbar.pack(fill="x", side="top")

        lbl_info = tk.Label(toolbar, text=f" Drag here ({w}x{h} px)", bg="#1e293b", fg="white", font=("Arial", 9, "bold"))
        lbl_info.pack(side="left", padx=8)

        def do_capture():
            # Get exact capture area coordinates below toolbar
            cx = frame_win.winfo_rootx()
            cy = frame_win.winfo_rooty() + toolbar_height
            frame_win.destroy()
            self.root.after(150, lambda: self.process_capture(cx, cy, cx + w, cy + h))

        btn_capture = tk.Button(toolbar, text="Capture", bg="#10b981", fg="white", relief="flat", padx=8, command=do_capture)
        btn_capture.pack(side="right", padx=5, pady=4)

        btn_close = tk.Button(toolbar, text="Cancel", bg="#ef4444", fg="white", relief="flat", padx=6, command=frame_win.destroy)
        btn_close.pack(side="right", padx=(0, 4), pady=4)

        # Dragging logic for toolbar
        def start_move(event):
            frame_win.drag_start_x = event.x
            frame_win.drag_start_y = event.y

        def do_move(event):
            dx = event.x - frame_win.drag_start_x
            dy = event.y - frame_win.drag_start_y
            new_x = frame_win.winfo_x() + dx
            new_y = frame_win.winfo_y() + dy
            frame_win.geometry(f"+{new_x}+{new_y}")

        toolbar.bind("<ButtonPress-1>", start_move)
        toolbar.bind("<B1-Motion>", do_move)
        lbl_info.bind("<ButtonPress-1>", start_move)
        lbl_info.bind("<B1-Motion>", do_move)

        # 2. Transparent Hollow Area with Red Border
        canvas = tk.Canvas(frame_win, width=w, height=h, bg=transparent_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_rectangle(1, 1, w - 2, h - 2, outline="#ef4444", width=2)

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
            state["rect"] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2, fill="black")

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
                self.root.after(150, lambda: self.process_capture(x1, y1, x2, y2))
            else:
                self.root.deiconify()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

    def process_capture(self, x1, y1, x2, y2):
        self.root.withdraw()
        time.sleep(0.1)

        try:
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            self.last_captured_image = img

            # 1. Automatically copy to Windows Clipboard
            copy_to_clipboard(img)

            # 2. Update UI
            w = x2 - x1
            h = y2 - y1
            self.lbl_status.config(
                text=f"Captured ({w}x{h} px) - Copied to Clipboard!",
                fg="#16a34a"
            )
            self.btn_save.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture: {str(e)}")
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
                self.lbl_status.config(text="Saved to file successfully.", fg="#2563eb")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenCaptureApp(root)
    root.mainloop()
