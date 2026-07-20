import sys
import os
import updater

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
        self.root.title("Logistics Bill Extractor v1.0")
        self.root.configure(bg="#F8FAFC") # Modern light background color
        
        # Style ttk
        style = ttk.Style()
        style.theme_use('clam')

        # Header
        header_frame = tk.Frame(root, bg="#0F172A", pady=15)
        header_frame.pack(fill="x")
        
        tk.Label(
            header_frame, text="LOGISTICS BILL EXTRACTOR",
            font=("Segoe UI", 18, "bold"), fg="#38BDF8", bg="#0F172A"
        ).pack()

        tk.Label(
            header_frame, text="Automatically identify and extract data from Bill of Lading PDF files",
            font=("Segoe UI", 10), fg="#94A3B8", bg="#0F172A"
        ).pack(pady=(2, 0))

        # Supported Carriers
        support_frame = tk.Frame(root, bg="#E2E8F0", pady=6, padx=10)
        support_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            support_frame, 
            text="Supported shipping lines for extraction: ONE, OOCL, ZIM, SJJ, MSC, HMM",
            font=("Segoe UI", 10, "bold"), fg="#0F172A", bg="#E2E8F0"
        ).pack()

        # File Selection Area
        main_frame = tk.Frame(root, bg="#F8FAFC")
        main_frame.pack(padx=25, fill="both", expand=True)

        tk.Label(
            main_frame, text="1. Select file or directory to process:",
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

        # Selection Buttons
        btn_frame = tk.Frame(main_frame, bg="#F8FAFC")
        btn_frame.pack(fill="x", pady=10)

        tk.Button(
            btn_frame, text="Select Folder",
            command=self.browse_folder,
            bg="#2563EB", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=15, pady=6, cursor="hand2", activebackground="#1D4ED8", activeforeground="white"
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame, text="Select PDF File",
            command=self.browse_file,
            bg="#F59E0B", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=15, pady=6, cursor="hand2", activebackground="#D97706", activeforeground="white"
        ).pack(side=tk.LEFT)

        # Log Console
        tk.Label(
            main_frame, text="2. Process Log:",
            font=("Segoe UI", 10, "bold"), fg="#334155", bg="#F8FAFC"
        ).pack(anchor="w", pady=(15, 5))

        self.log_text = tk.Text(
            main_frame, height=13, width=82, state="disabled",
            bg="#1E293B", fg="#10B981", font=("Consolas", 10),
            relief="flat", padx=10, pady=10
        )
        self.log_text.pack(fill="both", expand=True)

        # Action Button
        action_frame = tk.Frame(root, bg="#F8FAFC", pady=20)
        action_frame.pack(fill="x")

        self.btn_run = tk.Button(
            action_frame, text="START EXTRACTION",
            font=("Segoe UI", 13, "bold"), bg="#10B981", fg="white",
            relief="flat", padx=25, pady=10, cursor="hand2", activebackground="#059669", activeforeground="white",
            command=self.start_processing
        )
        self.btn_run.pack()

        # Variable to store selected files
        self._selected_files = []

    # Helpers
    def log(self, msg, color=None):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update()

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing PDF files")
        if not folder:
            return
        pdfs = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        self._selected_files = pdfs
        self._output_dir = folder
        self.path_var.set(folder)
        self.log(f"[*] Folder: {folder}  -  Found {len(pdfs)} PDF file(s)")

    def browse_file(self):
        files = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not files:
            return
        self._selected_files = list(files)
        self._output_dir = os.path.dirname(files[0])
        self.path_var.set(f"{len(files)} file(s) selected  -  {self._output_dir}")
        self.log(f"[*] Selected {len(files)} file(s) from: {self._output_dir}")

    def start_processing(self):
        if not self._selected_files:
            messagebox.showwarning("No file selected", "Please select a Folder or PDF File first!")
            return
        self.btn_run.config(state="disabled", text="PROCESSING...", bg="#9E9E9E")
        self.log("\n" + "═" * 60)
        self.log("  STARTING EXTRACTION PROCESS")
        self.log("═" * 60)
        threading.Thread(target=self._process, daemon=True).start()

    def _process(self):
        all_data = []
        total = len(self._selected_files)

        for i, pdf_path in enumerate(self._selected_files):
            fname = os.path.basename(pdf_path)
            self.log(f"  [{i+1}/{total}] - {fname}")
            try:
                rows, carrier = process_pdf(pdf_path)
                if rows:
                    all_data.extend(rows)
                    self.log(f"       OK - {carrier} ({len(rows)} containers)")
                else:
                    self.log(f"       No valid data extracted")
            except Exception as e:
                self.log(f"       ERROR: {e}")

        if all_data:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H%M%S") # Short timestamp (HHMMSS)
            
            if len(self._selected_files) == 1:
                # If processing 1 file, use its name for the Excel file
                base_name = os.path.splitext(os.path.basename(self._selected_files[0]))[0]
                out_name = f"{base_name}_Extracted_{timestamp}.xlsx"
            else:
                # If processing a folder (multiple files), use the folder name
                folder_name = os.path.basename(os.path.normpath(self._output_dir))
                out_name = f"{folder_name}_Batch_{len(self._selected_files)}files_{timestamp}.xlsx"
                
            out_excel = os.path.join(self._output_dir, out_name)
            self.log(f"\nWriting to Excel file: {out_name}...")
            try:
                export_to_excel(all_data, out_excel)
                self.log(f"DONE!  {len(all_data)} rows  -  {out_excel}")
                if os.name == "nt":
                    out_excel_win = os.path.normpath(out_excel)
                    subprocess.Popen(f'explorer /select,"{out_excel_win}"')
                messagebox.showinfo(
                    "Completed",
                    f"Successfully extracted {len(all_data)} rows of data!\nFile: {out_excel}"
                )
            except Exception as e:
                self.log(f"Excel write error: {e}")
        else:
            self.log("No valid data was extracted.")

        self.btn_run.config(state="normal", text="START EXTRACTION", bg="#4CAF50")


if __name__ == "__main__":
    
    updater.check_for_updates()
    root = tk.Tk()
    root.resizable(False, False)

    app = App(root)
    root.geometry("750x620")

    # Center the window on the screen and force it to be on top
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
