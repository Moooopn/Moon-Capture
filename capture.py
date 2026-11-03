import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab

class ScreenCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("화면 캡처 프로그램")
        self.root.geometry("320x220")
        self.root.resizable(False, False)

        # 픽셀 입력 UI
        tk.Label(root, text="X 좌표:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry_x = tk.Entry(root, width=15)
        self.entry_x.grid(row=0, column=1)

        tk.Label(root, text="Y 좌표:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.entry_y = tk.Entry(root, width=15)
        self.entry_y.grid(row=1, column=1)

        tk.Label(root, text="가로 크기 (Width):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.entry_w = tk.Entry(root, width=15)
        self.entry_w.grid(row=2, column=1)

        tk.Label(root, text="세로 크기 (Height):").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.entry_h = tk.Entry(root, width=15)
        self.entry_h.grid(row=3, column=1)

        # 실행 버튼
        btn_pixel = tk.Button(root, text="픽셀 수치로 캡처", command=self.capture_by_pixels)
        btn_pixel.grid(row=4, column=0, pady=20, padx=10)

        btn_drag = tk.Button(root, text="마우스 드래그 캡처", command=self.start_drag_capture)
        btn_drag.grid(row=4, column=1, pady=20)

        # 드래그 캡처용 변수
        self.overlay = None
        self.start_x = None
        self.start_y = None
        self.rect = None

    def capture_by_pixels(self):
        try:
            x = int(self.entry_x.get())
            y = int(self.entry_y.get())
            w = int(self.entry_w.get())
            h = int(self.entry_h.get())
            self.save_capture(x, y, x + w, y + h)
        except ValueError:
            messagebox.showerror("입력 오류", "모든 좌표와 크기를 정확한 숫자로 입력해주세요.")

    def start_drag_capture(self):
        # 메인 창 숨기기
        self.root.withdraw()

        # 반투명 전체화면 오버레이 생성
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.config(cursor="cross")

        self.canvas = tk.Canvas(self.overlay, cursor="cross", bg="gray")
        self.canvas.pack(fill="both", expand=True)

        # 마우스 이벤트 바인딩
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2, fill="black")

    def on_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.overlay.destroy()
        
        # 시작점과 끝점 정렬 (드래그 방향 상관없이 캡처 가능하도록)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        # 입력창 수치 업데이트
        self.entry_x.delete(0, tk.END)
        self.entry_x.insert(0, str(x1))
        self.entry_y.delete(0, tk.END)
        self.entry_y.insert(0, str(y1))
        self.entry_w.delete(0, tk.END)
        self.entry_w.insert(0, str(x2 - x1))
        self.entry_h.delete(0, tk.END)
        self.entry_h.insert(0, str(y2 - y1))

        if x2 - x1 > 0 and y2 - y1 > 0:
            # 오버레이 창이 완전히 닫힐 시간을 주기 위해 0.2초 대기 후 캡처
            self.root.after(200, lambda: self.save_capture(x1, y1, x2, y2))
        else:
            self.root.deiconify()

    def save_capture(self, x1, y1, x2, y2):
        self.root.withdraw() # 캡처 시 메인 창이 안 찍히도록 숨김
        self.root.update()

        try:
            # 설정한 영역 캡처
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            
            # 저장 경로 지정 대화상자 (PNG 기본)
            filepath = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG 이미지", "*.png")],
                title="캡처 이미지 저장"
            )
            
            if filepath:
                img.save(filepath, "PNG")
                messagebox.showinfo("저장 완료", f"이미지가 성공적으로 저장되었습니다.\n{filepath}")
        except Exception as e:
            messagebox.showerror("오류", f"캡처 실패: {str(e)}")
        finally:
            self.root.deiconify() # 메인 창 다시 표시

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenCaptureApp(root)
    root.mainloop()
