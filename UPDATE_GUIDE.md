# Hướng dẫn Cập nhật Phiên bản (Release Guide)

Tài liệu này ghi chú lại các bước cần thiết mỗi khi bạn muốn phát hành một bản cập nhật mới cho phần mềm **Logistics Bill Extractor** để người dùng có thể nhận được bản update tự động.

## ⚠️ TRƯỚC KHI BUILD FILE .EXE

Mỗi lần cập nhật phiên bản mới (ví dụ từ `1.0.1` lên `1.0.2`), bạn **BẮT BUỘC** phải đổi số version ở 3 file sau cho đồng bộ:

1. **`updater.py`**
   Tìm dòng `CURRENT_VERSION` và sửa lại:
   ```python
   CURRENT_VERSION = "1.0.2"
   ```

2. **`installer.iss`** (Nếu bạn dùng Inno Setup để tạo file cài đặt)
   Sửa 2 dòng sau cho khớp version mới:
   ```ini
   AppVersion=1.0.2
   OutputBaseFilename=Setup_LogisticsBillExtractor_v1.0.2
   ```

3. **`version.json`**
   Cập nhật version, link tải file, và ghi chú sửa đổi:
   ```json
   {
     "version": "1.0.2",
     "download_url": "https://github.com/Thu-sunrise/Logistics-Bill-Extractor/releases/download/v1.0.2/LogisticsBillExtractor.exe",
     "changelog": "- Tính năng A\n- Sửa lỗi B"
   }
   ```

---

## 🚀 QUY TRÌNH PHÁT HÀNH

Sau khi đã đổi số version ở 3 file trên, thực hiện theo thứ tự sau:

**Bước 1: Build (đóng gói) ứng dụng**
- Chạy lệnh PyInstaller hoặc Nuitka (công cụ bạn đang dùng) để đóng gói mã nguồn thành file `.exe` mới.
- Nếu dùng Inno Setup, chạy file `installer.iss` để tạo file cài đặt `.exe` hoàn chỉnh.

**Bước 2: Push code lên GitHub**
- Commit tất cả thay đổi (bao gồm code mới và file `version.json` đã cập nhật).
- Push lên nhánh `main`.
*(Lúc này, app của người dùng sẽ quét file `version.json` trên Git và biết là có bản mới).*

**Bước 3: Tạo Release trên GitHub**
1. Truy cập repo GitHub, vào phần **Releases** > **Draft a new release**.
2. Tạo một thẻ tag khớp với link tải, ví dụ: `v1.0.2`.
3. Đặt **Release title** (Ví dụ: *Logistics Bill Extractor v1.0.2*).
4. Nhập mô tả tính năng mới (copy từ changelog).
5. **Kéo thả file `.exe` mới (ở Bước 1) vào ô đính kèm (Assets).** Đảm bảo tên file trùng với tên trong `download_url` của bạn.
6. Bấm **Publish release**.

Hoàn thành! Bây giờ người dùng mở app lên sẽ nhận được thông báo cập nhật mới.
