import pdfplumber

# 1. Thay đường dẫn này bằng đường dẫn tới file PDF OOCL thực tế của bạn
pdf_path = r"C:\Users\ADMIN\Downloads\OneDrive_2026-07-11\5. Macro check bill\SWB\OOCL\OOCL-041-TSO-S10000254611-016-DT-2170580360-OOLU2170580360-19546-ETD 07Jul ok Thao.pdf"
# 2. Thay đường dẫn này bằng tên file TXT mà bạn muốn xuất ra
txt_output_path = r"output_first_page.txt"

def export_first_page_text_to_txt(path, out_path):
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > 0:
                first_page_text = pdf.pages[0].extract_text(layout=True)
                
                # Mở file txt với chuẩn utf-8 để không bị lỗi font tiếng Việt (nếu có)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("=== BẮT ĐẦU NỘI DUNG TRANG ĐẦU TIÊN ===\n")
                    f.write(first_page_text if first_page_text else "")
                    f.write("\n=== KẾT THÚC NỘI DUNG TRANG ĐẦU TIÊN ===\n")
                
                print(f"Đã trích xuất thành công và lưu vào file: {out_path}")
            else:
                print("File PDF không có trang nào.")
    except Exception as e:
        print(f"Có lỗi xảy ra khi đọc hoặc ghi file: {e}")

if __name__ == "__main__":
    export_first_page_text_to_txt(pdf_path, txt_output_path)
