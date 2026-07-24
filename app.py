import sys
import os
import updater
import datetime
import threading
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.extractor_factory import process_pdf
from core.excel_exporter import export_to_excel

# Cấu hình giao diện chung
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Logistics Bill Extractor v1.0")
        self.geometry("800x600")
        self.minsize(700, 500)
        self.configure(fg_color="#F3F4F6") # Xám nhạt nền
        
        # --- HEADER ---
        self.header_frame = ctk.CTkFrame(self, fg_color="#1E3A8A", corner_radius=0)
        self.header_frame.pack(fill="x")
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.header_frame, text="LOGISTICS BILL EXTRACTOR",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="white"
        )
        self.title_label.pack(pady=(6, 2))
        
        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame, text="Tự động nhận diện và trích xuất dữ liệu từ các file PDF vận đơn (Bill of Lading)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#93C5FD"
        )
        self.subtitle_label.pack(pady=(0, 6))

        # Supported line
        self.support_frame = ctk.CTkFrame(self.header_frame, fg_color="white", corner_radius=8)
        self.support_frame.pack(pady=(0, 6), padx=20)
        
        supported_lines = "Supported shipping lines: ONE, OOCL, ZIM, SJJ, MSC, HMM, CMA CGM, COSCO, MAERSK, K&N, Hapag-Lloyd, Schenker"
        self.support_label = ctk.CTkLabel(
            self.support_frame, text=supported_lines,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#1E3A8A"
        )
        self.support_label.pack(padx=15, pady=3)
        
        # --- MAIN BODY ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=40, pady=10)
        
        # Grid config
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1) # file list
        self.main_frame.rowconfigure(4, weight=1) # log text
        
        # Tiêu đề danh sách file
        self.list_header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.list_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.list_title = ctk.CTkLabel(
            self.list_header_frame, text="1. Chọn File hoặc Thư Mục để xử lý:",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#1F2937"
        )
        self.list_title.pack(side="left")
        
        # Các nút thao tác
        self.btn_clear = ctk.CTkButton(
            self.list_header_frame, text="🗑 Xóa Tất Cả",
            fg_color="#6B7280", hover_color="#4B5563",
            width=100, corner_radius=6,
            command=self.clear_all
        )
        self.btn_clear.pack(side="right")

        self.btn_remove = ctk.CTkButton(
            self.list_header_frame, text="🗑 Xóa Đã Chọn",
            fg_color="#EF4444", hover_color="#DC2626",
            width=100, corner_radius=6,
            command=self.remove_selected
        )
        self.btn_remove.pack(side="right", padx=(5, 5))

        self.btn_add_file = ctk.CTkButton(
            self.list_header_frame, text="📄 Thêm PDF(s)",
            fg_color="#2563EB", hover_color="#1D4ED8",
            width=100, corner_radius=6,
            command=self.browse_file
        )
        self.btn_add_file.pack(side="right", padx=(5, 0))

        self.btn_add_folder = ctk.CTkButton(
            self.list_header_frame, text="📁 Thêm Folder",
            fg_color="#2563EB", hover_color="#1D4ED8",
            width=100, corner_radius=6,
            command=self.browse_folder
        )
        self.btn_add_folder.pack(side="right", padx=(0, 0))
        
        # Vùng chọn file
        self.file_list_frame = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="white", 
            border_width=1, border_color="#D1D5DB", corner_radius=8,
            height=150
        )
        self.file_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Nút Bắt đầu
        self.btn_run = ctk.CTkButton(
            self.main_frame, text="BẮT ĐẦU TRÍCH XUẤT",
            fg_color="#2563EB", hover_color="#1D4ED8",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            height=45, corner_radius=8,
            command=self.start_processing
        )
        self.btn_run.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        # Vùng Log
        self.log_title = ctk.CTkLabel(
            self.main_frame, text="2. Nhật Ký Xử Lý:",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#1F2937"
        )
        self.log_title.grid(row=3, column=0, sticky="w", pady=(0, 5))
        
        self.log_text = ctk.CTkTextbox(
            self.main_frame, fg_color="#1E1E1E", text_color="#A3BE8C",
            font=ctk.CTkFont(family="Consolas", size=13),
            corner_radius=8, height=120
        )
        self.log_text.grid(row=4, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")
        
        # Data
        self._selected_files = [] # Danh sách chứa đường dẫn
        self._checkbox_vars = {} # Mapping từ đường dẫn -> biến BooleanVar của Checkbox
        self._checkbox_widgets = {} # Mapping từ đường dẫn -> Checkbox widget

    def log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update()

    def _add_files_to_list(self, files):
        added = 0
        for f in files:
            f = os.path.normpath(f)
            if f not in self._selected_files:
                self._selected_files.append(f)
                
                # Tạo checkbox cho mỗi file
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(
                    self.file_list_frame, text=os.path.basename(f),
                    variable=var, font=ctk.CTkFont(family="Segoe UI", size=14),
                    text_color="#374151"
                )
                cb.pack(anchor="w", pady=6, padx=10)
                
                self._checkbox_vars[f] = var
                self._checkbox_widgets[f] = cb
                added += 1
        return added

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing PDF files")
        if not folder:
            return
        pdfs = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        added = self._add_files_to_list(pdfs)
        self.log(f"[*] Folder: {folder}  -  Added {added} new PDF file(s)")

    def browse_file(self):
        files = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not files:
            return
        added = self._add_files_to_list(files)
        self.log(f"[*] Added {added} new PDF file(s)")

    def remove_selected(self):
        to_remove = []
        for f in self._selected_files:
            if self._checkbox_vars[f].get():
                to_remove.append(f)
                
        for f in to_remove:
            self._selected_files.remove(f)
            self._checkbox_widgets[f].destroy()
            del self._checkbox_widgets[f]
            del self._checkbox_vars[f]
            
        if to_remove:
            self.log(f"[-] Removed {len(to_remove)} file(s) from queue")

    def clear_all(self):
        for f in self._selected_files:
            self._checkbox_widgets[f].destroy()
        self._selected_files.clear()
        self._checkbox_widgets.clear()
        self._checkbox_vars.clear()
        self.log("[-] Cleared all files from queue")

    def start_processing(self):
        if not self._selected_files:
            messagebox.showwarning("No file selected", "Vui lòng thêm ít nhất một file PDF để xử lý!")
            return
            
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        if len(self._selected_files) == 1:
            base_name = os.path.splitext(os.path.basename(self._selected_files[0]))[0]
            default_name = f"{base_name}_Extracted_{timestamp}.xlsx"
        else:
            default_name = f"Batch_{len(self._selected_files)}files_{timestamp}.xlsx"
            
        initial_dir = os.path.dirname(self._selected_files[0])
        
        save_path = filedialog.asksaveasfilename(
            title="Save Extracted Data As...",
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if not save_path:
            self.log("[!] Extraction cancelled by user.")
            return
            
        self.btn_run.configure(state="disabled", text="ĐANG XỬ LÝ...", fg_color="#9CA3AF")
        self.log("\n" + "=" * 50)
        self.log("BẮT ĐẦU QUÁ TRÌNH TRÍCH XUẤT")
        self.log("=" * 50)
        threading.Thread(target=self._process, args=(save_path,), daemon=True).start()

    def _process(self, save_path):
        all_data = []
        total = len(self._selected_files)

        for i, pdf_path in enumerate(self._selected_files):
            fname = os.path.basename(pdf_path)
            self.log(f"[{i+1}/{total}] Đang xử lý: {fname}")
            try:
                rows, carrier = process_pdf(pdf_path)
                if rows:
                    all_data.extend(rows)
                    self.log(f"   -> THÀNH CÔNG: {carrier} ({len(rows)} containers)")
                else:
                    self.log(f"   -> LỖI: Không có dữ liệu hợp lệ")
            except Exception as e:
                self.log(f"   -> LỖI ỨNG DỤNG: {e}")

        if all_data:
            self.log(f"\nĐang ghi vào file Excel: {os.path.basename(save_path)}...")
            try:
                export_to_excel(all_data, save_path)
                self.log(f"HOÀN TẤT! Đã lưu {len(all_data)} dòng dữ liệu.")
                if os.name == "nt":
                    out_excel_win = os.path.normpath(save_path)
                    subprocess.Popen(f'explorer /select,"{out_excel_win}"')
                messagebox.showinfo("Thành công", f"Đã trích xuất {len(all_data)} dòng dữ liệu!\nFile: {save_path}")
            except Exception as e:
                self.log(f"Lỗi ghi file Excel: {e}")
        else:
            self.log("Không có dữ liệu hợp lệ nào được trích xuất.")

        self.btn_run.configure(state="normal", text="BẮT ĐẦU TRÍCH XUẤT", fg_color="#2563EB")


if __name__ == "__main__":
    updater.check_for_updates()
    app = App()
    
    # Center screen
    app.update_idletasks()
    sw, sh = app.winfo_screenwidth(), app.winfo_screenheight()
    x = (sw - 800) // 2
    y = (sh - 600) // 2
    app.geometry(f"800x600+{x}+{y}")
    
    app.mainloop()
