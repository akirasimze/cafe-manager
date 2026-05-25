# Cafe Manager

Ứng dụng quản lý bàn và order món cho quán cà phê — chạy trên trình duyệt, dữ liệu lưu SQLite. Sau **kết toán ca**, doanh thu và tồn kho được ghi lên **Google Sheets** (nếu đã cấu hình).

## Tính năng

- **Sơ đồ 40 bàn**: hai khu — **Trong nhà** (bàn 1–20), **Bên ngoài** (21–40)
- **Order món**: menu cà phê, trà, nước ép, bánh, món nóng
- **Tồn kho**: theo dõi và cập nhật số lượng; trừ kho khi thanh toán
- **Doanh thu chưa kết toán**: tích lũy sau mỗi lần thanh toán bàn
- **Kết toán ca**: chốt doanh thu + snapshot tồn kho, đồng bộ Google Sheets
- **Thanh toán & trả bàn**, hủy order, ghi chú bàn

## Cài đặt & chạy

```bash
cd cafe-manager
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Mở trình duyệt: **http://127.0.0.1:5000**

**Thời gian:** Các cột thời gian trong SQLite và Google Sheets dùng **giờ Việt Nam** (`Asia/Ho_Chi_Minh`), ví dụ `2026-05-20T13:47:05+07:00`.

## Google Sheets

### 1. Google Cloud

1. Vào [Google Cloud Console](https://console.cloud.google.com/) → tạo project (hoặc dùng project có sẵn).
2. Bật **Google Sheets API**.
3. **IAM & Admin → Service Accounts** → tạo service account → tạo key JSON → tải về.
4. Đặt file JSON vào thư mục project, ví dụ `google-credentials.json`.

### 2. Google Spreadsheet

1. Tạo một Google Spreadsheet mới (hoặc dùng sheet có sẵn).
2. Copy **Spreadsheet ID** từ URL:  
   `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`
3. **Chia sẻ** spreadsheet với email service account (dạng `xxx@xxx.iam.gserviceaccount.com`) quyền **Editor**.

### 3. File `.env`

```env
GOOGLE_SHEET_ID=<SPREADSHEET_ID>
GOOGLE_CREDENTIALS_PATH=google-credentials.json
```

Khi kết toán, app tự tạo các tab (nếu chưa có):

| Tab | Nội dung |
|-----|----------|
| `Tong_hop` | Tổng doanh thu mỗi lần kết toán |
| `Doanh_thu` | Chi tiết từng dòng bán |
| `Ton_kho` | Tồn kho tại thời điểm kết toán |
| `Huy_tom_tat` | Mỗi lần hủy order & trả bàn (tóm tắt) |
| `Huy_chi_tiet` | Chi tiết món đã hủy theo từng lần hủy |

Mỗi lần **Hủy order & trả bàn**, lịch sử được ghi vào SQLite và đẩy lên hai tab `Huy_*` khi đã cấu hình Sheets.

## Luồng nghiệp vụ

1. Phục vụ bàn → thêm món (kiểm tra tồn kho).
2. **Thanh toán & trả bàn** → ghi doanh thu ca, trừ tồn kho.
3. Cuối ca → **Kết toán** → dữ liệu ghi Sheets + đánh dấu đã chốt.

## Cấu trúc

```
cafe-manager/
  app.py              # Flask API
  database.py         # SQLite
  google_sheets.py    # Đồng bộ Google Sheets
  .env.example
  templates/
  static/
```

## API (REST)

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/tables` | Bàn + `pendingRevenue` |
| GET | `/api/inventory` | Tồn kho |
| PATCH | `/api/inventory/:id` | Cập nhật tồn |
| GET | `/api/settlement/preview` | Xem trước kết toán |
| POST | `/api/settlement` | Kết toán + sync Sheets |
| POST | `/api/tables/:id/checkout` | Thanh toán (ghi doanh thu) |
