"""Sync settlement data to Google Sheets via service account."""

import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_SUMMARY = "Tong_hop"
SHEET_REVENUE = "Doanh_thu"
SHEET_INVENTORY = "Ton_kho"

HEADERS_SUMMARY = [
    "Ma ket toan",
    "Thoi gian",
    "Tong doanh thu (VND)",
    "So dong ban",
    "Ghi chu",
]
HEADERS_REVENUE = [
    "Ma ket toan",
    "Thoi gian",
    "Ban",
    "Ma mon",
    "Ten mon",
    "So luong",
    "Don gia (VND)",
    "Thanh tien (VND)",
]
HEADERS_INVENTORY = [
    "Ma ket toan",
    "Thoi gian",
    "Ma mon",
    "Ten mon",
    "Ton kho",
]

SHEET_CANCEL_SUMMARY = "Huy_tom_tat"
SHEET_CANCEL_DETAIL = "Huy_chi_tiet"

HEADERS_CANCEL_SUMMARY = [
    "Ma huy",
    "Thoi gian",
    "Ban",
    "So dong mon",
    "Gia tri uoc tinh (VND)",
    "Ghi chu ban",
]
HEADERS_CANCEL_DETAIL = [
    "Ma huy",
    "Thoi gian",
    "Ban",
    "Ma mon",
    "Ten mon",
    "So luong",
    "Don gia (VND)",
    "Thanh tien (VND)",
    "Ghi chu mon",
]


def is_configured() -> bool:
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    creds = _credentials_path()
    return bool(sheet_id and creds.is_file())


def _credentials_path() -> Path:
    raw = os.environ.get("GOOGLE_CREDENTIALS_PATH", "google-credentials.json")
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return path


def _get_spreadsheet():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("Chưa cấu hình GOOGLE_SHEET_ID trong file .env")

    creds_path = _credentials_path()
    if not creds_path.is_file():
        raise RuntimeError(
            f"Không tìm thấy file credentials: {creds_path}. "
            "Tải JSON service account từ Google Cloud và đặt đúng đường dẫn."
        )

    credentials = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id)


def _ensure_worksheet(spreadsheet, title: str, headers: list[str]):
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers, value_input_option="USER_ENTERED")
        return ws

    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws


def sync_settlement(
    settlement_id: int,
    settled_at: str,
    total_revenue: int,
    line_count: int,
    sales: list[dict],
    inventory: list[dict],
    note: str = "",
) -> None:
    spreadsheet = _get_spreadsheet()

    ws_summary = _ensure_worksheet(spreadsheet, SHEET_SUMMARY, HEADERS_SUMMARY)
    ws_revenue = _ensure_worksheet(spreadsheet, SHEET_REVENUE, HEADERS_REVENUE)
    ws_inventory = _ensure_worksheet(spreadsheet, SHEET_INVENTORY, HEADERS_INVENTORY)

    ws_summary.append_row(
        [settlement_id, settled_at, total_revenue, line_count, note],
        value_input_option="USER_ENTERED",
    )

    revenue_rows = [
        [
            settlement_id,
            settled_at,
            s["table_label"],
            s["menu_item_id"],
            s["name"],
            s["quantity"],
            s["price"],
            s["price"] * s["quantity"],
        ]
        for s in sales
    ]
    if revenue_rows:
        ws_revenue.append_rows(revenue_rows, value_input_option="USER_ENTERED")

    inventory_rows = [
        [
            settlement_id,
            settled_at,
            row["menu_item_id"],
            row["name"],
            row["quantity"],
        ]
        for row in inventory
    ]
    if inventory_rows:
        ws_inventory.append_rows(inventory_rows, value_input_option="USER_ENTERED")


def sync_order_cancellation(
    cancellation_id: int,
    cancelled_at: str,
    table_label: str,
    table_note: str,
    item_line_count: int,
    total_value: int,
    items: list[dict],
) -> None:
    spreadsheet = _get_spreadsheet()

    ws_sum = _ensure_worksheet(spreadsheet, SHEET_CANCEL_SUMMARY, HEADERS_CANCEL_SUMMARY)
    ws_det = _ensure_worksheet(spreadsheet, SHEET_CANCEL_DETAIL, HEADERS_CANCEL_DETAIL)

    ws_sum.append_row(
        [
            cancellation_id,
            cancelled_at,
            table_label,
            item_line_count,
            total_value,
            table_note,
        ],
        value_input_option="USER_ENTERED",
    )

    detail_rows = [
        [
            cancellation_id,
            cancelled_at,
            table_label,
            line["menu_item_id"],
            line["name"],
            line["quantity"],
            line["price"],
            line["price"] * line["quantity"],
            line.get("note") or "",
        ]
        for line in items
    ]
    if detail_rows:
        ws_det.append_rows(detail_rows, value_input_option="USER_ENTERED")
