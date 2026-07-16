# Logistics Bill Extractor Architecture

Dự án áp dụng mô hình **Strategy Pattern** kết hợp **Factory Pattern** để đảm bảo khả năng mở rộng (scalable) khi cần hỗ trợ nhiều hãng tàu (Carrier) khác nhau.

## 1. Thành phần cốt lõi (Core Components)

### `base_extractor.py` (Lớp nền tảng)
- Là class cha (`BaseExtractor`) định nghĩa cấu trúc chuẩn cho mọi kết quả bóc tách.
- Chứa danh sách `COLUMNS` quy định 18 trường thông tin bắt buộc (kể cả File name và Carrier).
- Có hàm `get_empty_row()` để tạo template dữ liệu sạch.
- Có hàm `extract(self)` là hàm Template, bắt buộc các class con phải override.

### Các class con (Ví dụ: `one_extractor.py`)
- Kế thừa từ `BaseExtractor`.
- Có nhiệm vụ duy nhất là chứa thuật toán bóc tách (đọc PDF bằng `pdfplumber`, dùng Regex quét text) cho form Bill của ĐÚNG 1 hãng cụ thể (ví dụ hãng ONE).
- Gán cứng `self.carrier_name` tương ứng với hãng đó.

### `extractor_factory.py` (Bộ điều hướng tự động)
- Chịu trách nhiệm khởi tạo đúng Class Extractor dựa trên nội dung PDF.
- Nhận input là đường dẫn file PDF.
- Đọc trang đầu tiên của file, dò các từ khoá đặc trưng (vd: "Ocean Network Express", "OOCL", v.v.).
- Trả về đối tượng (Object) Extractor phù hợp (vd: `OneExtractor()`) để hệ thống tiến hành bóc tách.

## 2. Luồng xử lý (Workflow)
1. User chọn folder từ UI -> UI gọi `app.py`.
2. `app.py` duyệt từng file `.pdf` và chuyển đường dẫn cho `extractor_factory.process_pdf(pdf_path)`.
3. `extractor_factory` đọc vài dòng đầu của PDF, nhận dạng hãng tàu là "ONE", sau đó khởi tạo đối tượng `extractor = OneExtractor(pdf_path)`.
4. Gọi `extractor.extract()`: Object này sẽ dùng các logic đã định nghĩa để thu thập dữ liệu và trả về List các Dict.
5. Danh sách Dict được gom lại và đẩy cho `excel_exporter.py` để xuất ra màn hình.

## 3. Cách thêm hãng tàu mới (VD: COSCO)
1. Tạo file `cosco_extractor.py` trong thư mục `core/extractors/`.
2. Khai báo `class CoscoExtractor(BaseExtractor):` và override hàm `extract()`.
3. Mở file `core/extractor_factory.py`, import `CoscoExtractor`.
4. Bổ sung `elif "COSCO" in text: return CoscoExtractor(pdf_path)` vào bộ điều hướng.
5. Hoàn thành! Không cần đụng vào UI hay các hãng khác.
