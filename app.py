import sys
import os

# Fix import khi chạy từ thư mục logistics_tool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import subprocess

from core.extractor_factory import process_pdf
from core.excel_exporter import export_to_excel


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Phần Mềm Bóc Tách Bill Logistics v1.0")
        self.root.configure(bg="#F8FAFC") # Màu nền sáng hiện đại hơn
        
        # Style ttk
        style = ttk.Style()
        style.theme_use('clam')

        # ── Header ──────────────────────────────────────────────
        header_frame = tk.Frame(root, bg="#0F172A", pady=15)
        header_frame.pack(fill="x")
        
        tk.Label(
            header_frame, text="LOGISTICS BILL EXTRACTOR",
            font=("Segoe UI", 18, "bold"), fg="#38BDF8", bg="#0F172A"
        ).pack()

        tk.Label(
            header_frame, text="Hỗ trợ tự động nhận diện và trích xuất dữ liệu từ các file PDF Bill of Lading",
            font=("Segoe UI", 10), fg="#94A3B8", bg="#0F172A"
        ).pack(pady=(2, 0))

        # ── Hãng tàu hỗ trợ ────────────────────────────────────
        support_frame = tk.Frame(root, bg="#E2E8F0", pady=6, padx=10)
        support_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            support_frame, 
            text="Các hãng tàu đang hỗ trợ bóc tách: ONE, OOCL, ZIM, SJJ",
            font=("Segoe UI", 10, "bold"), fg="#0F172A", bg="#E2E8F0"
        ).pack()

        # ── Khu vực chọn file ─────────────────────────────────
        main_frame = tk.Frame(root, bg="#F8FAFC")
        main_frame.pack(padx=25, fill="both", expand=True)

        tk.Label(
            main_frame, text="1. Chọn đường dẫn file hoặc thư mục cần xử lý:",
            font=("Segoe UI", 10, "bold"), fg="#334155", bg="#F8FAFC"
        ).pack(anchor="w", pady=(10, 5))

        path_frame = tk.Frame(main_frame, bg="#F8FAFC")
        path_frame.pack(fill="x")

        self.path_var = tk.StringVar()
        tk.Entry(
            path_frame, textvariable=self.path_var, width=58,
            state="readonly", font=("Consolas", 10), relief="solid", bd=1,
            bg="#FFFFFF", fg="#1E293B", readonlybackground="#FFFFFF"
        ).pack(side=tk.LEFT, ipady=6, expand=True, fill="x")

        # ── Các nút chọn ──────────────────────────────────────
        btn_frame = tk.Frame(main_frame, bg="#F8FAFC")
        btn_frame.pack(fill="x", pady=10)

        tk.Button(
            btn_frame, text="Chọn Thư Mục",
            command=self.browse_folder,
            bg="#2563EB", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=15, pady=6, cursor="hand2", activebackground="#1D4ED8", activeforeground="white"
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame, text="Chọn File PDF",
            command=self.browse_file,
            bg="#F59E0B", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=15, pady=6, cursor="hand2", activebackground="#D97706", activeforeground="white"
        ).pack(side=tk.LEFT)

        # ── Log console ───────────────────────────────────────
        tk.Label(
            main_frame, text="2. Nhật ký tiến trình:",
            font=("Segoe UI", 10, "bold"), fg="#334155", bg="#F8FAFC"
        ).pack(anchor="w", pady=(15, 5))

        self.log_text = tk.Text(
            main_frame, height=13, width=82, state="disabled",
            bg="#1E293B", fg="#10B981", font=("Consolas", 10),
            relief="flat", padx=10, pady=10
        )
        self.log_text.pack(fill="both", expand=True)

        # ── Nút chạy ──────────────────────────────────────────
        action_frame = tk.Frame(root, bg="#F8FAFC", pady=20)
        action_frame.pack(fill="x")

        self.btn_run = tk.Button(
            action_frame, text="BẮT ĐẦU TRÍCH XUẤT",
            font=("Segoe UI", 13, "bold"), bg="#10B981", fg="white",
            relief="flat", padx=25, pady=10, cursor="hand2", activebackground="#059669", activeforeground="white",
            command=self.start_processing
        )
        self.btn_run.pack()

        # Biến lưu danh sách file đã chọn
        self._selected_files = []

    # ── Helpers ───────────────────────────────────────────────
    def log(self, msg, color=None):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update()

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục chứa file PDF")
        if not folder:
            return
        pdfs = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        self._selected_files = pdfs
        self._output_dir = folder
        self.path_var.set(folder)
        self.log(f"[*] Thư mục: {folder}  -  Tìm thấy {len(pdfs)} file PDF")

    def browse_file(self):
        files = filedialog.askopenfilenames(
            title="Chọn file PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not files:
            return
        self._selected_files = list(files)
        self._output_dir = os.path.dirname(files[0])
        self.path_var.set(f"{len(files)} file đã chọn  -  {self._output_dir}")
        self.log(f"[*] Đã chọn {len(files)} file từ: {self._output_dir}")

    def start_processing(self):
        if not self._selected_files:
            messagebox.showwarning("Chưa chọn file", "Vui lòng chọn Thư Mục hoặc File PDF trước!")
            return
        self.btn_run.config(state="disabled", text="ĐANG XỬ LÝ...", bg="#9E9E9E")
        self.log("\n" + "═" * 60)
        self.log("  BẮT ĐẦU QUÁ TRÌNH TRÍCH XUẤT")
        self.log("═" * 60)
        threading.Thread(target=self._process, daemon=True).start()

    def _process(self):
        all_data = []
        total = len(self._selected_files)

        for i, pdf_path in enumerate(self._selected_files):
            fname = os.path.basename(pdf_path)
            self.log(f"  [{i+1}/{total}] - {fname}")
            try:
                rows = process_pdf(pdf_path)
                if rows:
                    all_data.extend(rows)
                    self.log(f"       OK  ({len(rows)} container)")
                else:
                    self.log(f"       Không bóc được dữ liệu")
            except Exception as e:
                self.log(f"       LỖI: {e}")

        if all_data:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H%M%S") # Timestamp ngắn gọn giờ phút giây
            
            if len(self._selected_files) == 1:
                # Nếu chỉ xử lý 1 file, lấy tên file đó làm tên Excel
                base_name = os.path.splitext(os.path.basename(self._selected_files[0]))[0]
                out_name = f"{base_name}_Extracted_{timestamp}.xlsx"
            else:
                # Nếu quét cả thư mục (nhiều file), lấy tên thư mục làm tên
                folder_name = os.path.basename(os.path.normpath(self._output_dir))
                out_name = f"{folder_name}_Batch_{len(self._selected_files)}files_{timestamp}.xlsx"
                
            out_excel = os.path.join(self._output_dir, out_name)
            self.log(f"\nĐang ghi file Excel: {out_name}...")
            try:
                export_to_excel(all_data, out_excel)
                self.log(f"XONG!  {len(all_data)} dòng  -  {out_excel}")
                if os.name == "nt":
                    out_excel_win = os.path.normpath(out_excel)
                    subprocess.Popen(f'explorer /select,"{out_excel_win}"')
                messagebox.showinfo(
                    "Hoàn thành",
                    f"Đã trích xuất {len(all_data)} dòng dữ liệu!\nFile: {out_excel}"
                )
            except Exception as e:
                self.log(f"Lỗi ghi Excel: {e}")
        else:
            self.log("Không trích xuất được dữ liệu nào hợp lệ.")

        self.btn_run.config(state="normal", text="BẮT ĐẦU TRÍCH XUẤT", bg="#4CAF50")


if __name__ == "__main__":
    root = tk.Tk()
    root.resizable(False, False)

    app = App(root)
    root.geometry("750x620")

    # Căn giữa màn hình và bắt buộc hiện lên trên
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = (sw - 750) // 2
    y = (sh - 620) // 2
    root.geometry(f"750x620+{x}+{y}")
    root.lift()
    root.attributes("-topmost", True)
    root.after(600, lambda: root.attributes("-topmost", False))
    root.deiconify()
    root.mainloop()
