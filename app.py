from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from database import init_db, get_connection

load_dotenv()

app = Flask(__name__)
init_db()


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def vn_now():
    """Current local time in Vietnam (for DB, API, Google Sheets)."""
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def table_row_to_dict(row, conn):
    items = conn.execute(
        """
        SELECT id, menu_item_id, name, price, quantity, note, created_at
        FROM order_items WHERE table_id = ? ORDER BY created_at
        """,
        (row["id"],),
    ).fetchall()
    total = sum(i["price"] * i["quantity"] for i in items)
    return {
        "id": row["id"],
        "label": row["label"],
        "status": row["status"],
        "openedAt": row["opened_at"],
        "note": row["note"] or "",
        "items": [dict(i) for i in items],
        "total": total,
        "itemCount": sum(i["quantity"] for i in items),
    }


def pending_revenue(conn):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(price * quantity), 0) AS total,
               COUNT(*) AS line_count
        FROM sale_lines WHERE settlement_id IS NULL
        """
    ).fetchone()
    return int(row["total"]), int(row["line_count"])


def fetch_inventory(conn):
    rows = conn.execute(
        """
        SELECT i.menu_item_id, m.name, i.quantity
        FROM inventory i
        JOIN menu_items m ON m.id = i.menu_item_id
        ORDER BY m.name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_pending_sales(conn):
    rows = conn.execute(
        """
        SELECT table_label, menu_item_id, name, price, quantity, sold_at
        FROM sale_lines WHERE settlement_id IS NULL
        ORDER BY sold_at
        """
    ).fetchall()
    return [dict(r) for r in rows]


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/tables")
def list_tables():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM tables ORDER BY id").fetchall()
    result = [table_row_to_dict(r, conn) for r in rows]
    pending_total, _ = pending_revenue(conn)
    conn.close()
    return jsonify({"tables": result, "pendingRevenue": pending_total})


@app.get("/api/menu")
def list_menu():
    conn = get_connection()
    categories = conn.execute(
        "SELECT id, name FROM categories ORDER BY sort_order"
    ).fetchall()
    result = []
    for cat in categories:
        items = conn.execute(
            "SELECT id, name, price FROM menu_items WHERE category_id = ? ORDER BY name",
            (cat["id"],),
        ).fetchall()
        result.append(
            {
                "id": cat["id"],
                "name": cat["name"],
                "items": [dict(i) for i in items],
            }
        )
    conn.close()
    return jsonify(result)


@app.get("/api/inventory")
def list_inventory():
    conn = get_connection()
    result = fetch_inventory(conn)
    conn.close()
    return jsonify(result)


@app.patch("/api/inventory/<menu_item_id>")
def update_inventory(menu_item_id):
    data = request.get_json(silent=True) or {}
    quantity = data.get("quantity")
    if quantity is None:
        return jsonify({"error": "Thiếu quantity"}), 400
    qty = int(quantity)
    if qty < 0:
        return jsonify({"error": "Số lượng không hợp lệ"}), 400

    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM menu_items WHERE id = ?", (menu_item_id,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Món không tồn tại"}), 404

    conn.execute(
        """
        INSERT INTO inventory (menu_item_id, quantity) VALUES (?, ?)
        ON CONFLICT(menu_item_id) DO UPDATE SET quantity = excluded.quantity
        """,
        (menu_item_id, qty),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.get("/api/settlement/preview")
def settlement_preview():
    conn = get_connection()
    total, line_count = pending_revenue(conn)
    sales = fetch_pending_sales(conn)
    inventory = fetch_inventory(conn)
    conn.close()
    return jsonify(
        {
            "totalRevenue": total,
            "lineCount": line_count,
            "sales": sales,
            "inventory": inventory,
            "sheetsConfigured": _sheets_configured(),
        }
    )


def _sheets_configured():
    try:
        from google_sheets import is_configured

        return is_configured()
    except ImportError:
        return False


@app.post("/api/settlement")
def run_settlement():
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()

    conn = get_connection()
    total, line_count = pending_revenue(conn)
    if line_count == 0:
        conn.close()
        return jsonify({"error": "Không có doanh thu nào để kết toán"}), 400

    sales = fetch_pending_sales(conn)
    inventory = fetch_inventory(conn)
    settled_at = vn_now()

    cur = conn.execute(
        """
        INSERT INTO settlements (settled_at, total_revenue, line_count, synced_to_sheets, note)
        VALUES (?, ?, ?, 0, ?)
        """,
        (settled_at, total, line_count, note),
    )
    settlement_id = cur.lastrowid

    conn.execute(
        """
        UPDATE sale_lines SET settlement_id = ?
        WHERE settlement_id IS NULL
        """,
        (settlement_id,),
    )
    conn.commit()

    synced = False
    sheets_error = None
    if _sheets_configured():
        try:
            from google_sheets import sync_settlement

            sync_settlement(
                settlement_id,
                settled_at,
                total,
                line_count,
                sales,
                inventory,
                note,
            )
            conn.execute(
                "UPDATE settlements SET synced_to_sheets = 1 WHERE id = ?",
                (settlement_id,),
            )
            conn.commit()
            synced = True
        except Exception as exc:
            sheets_error = str(exc)

    conn.close()
    return jsonify(
        {
            "ok": True,
            "settlementId": settlement_id,
            "totalRevenue": total,
            "lineCount": line_count,
            "syncedToSheets": synced,
            "sheetsError": sheets_error,
        }
    )


@app.post("/api/tables/<int:table_id>/open")
def open_table(table_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Bàn không tồn tại"}), 404
    if row["status"] == "available":
        has_items = conn.execute(
            "SELECT 1 FROM order_items WHERE table_id = ? LIMIT 1", (table_id,)
        ).fetchone()
        if not has_items:
            conn.close()
            return jsonify({"error": "Chưa có món, không thể chuyển sang đang phục vụ"}), 400
        conn.execute(
            "UPDATE tables SET status = 'occupied', opened_at = ? WHERE id = ?",
            (vn_now(), table_id),
        )
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.patch("/api/tables/<int:table_id>")
def update_table(table_id):
    data = request.get_json(silent=True) or {}
    conn = get_connection()
    row = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Bàn không tồn tại"}), 404
    if "note" in data:
        conn.execute("UPDATE tables SET note = ? WHERE id = ?", (data["note"], table_id))
    if data.get("status") == "billing":
        has_items = conn.execute(
            "SELECT 1 FROM order_items WHERE table_id = ? LIMIT 1", (table_id,)
        ).fetchone()
        if not has_items:
            conn.close()
            return jsonify({"error": "Chưa có món, không thể yêu cầu thanh toán"}), 400
        conn.execute("UPDATE tables SET status = 'billing' WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.post("/api/tables/<int:table_id>/items")
def add_item(table_id):
    data = request.get_json(silent=True) or {}
    menu_item_id = data.get("menuItemId")
    quantity = max(1, int(data.get("quantity", 1)))
    note = (data.get("note") or "").strip()

    conn = get_connection()
    table = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not table:
        conn.close()
        return jsonify({"error": "Bàn không tồn tại"}), 404

    if table["status"] == "available":
        conn.execute(
            "UPDATE tables SET status = 'occupied', opened_at = ? WHERE id = ?",
            (vn_now(), table_id),
        )

    menu = conn.execute(
        "SELECT id, name, price FROM menu_items WHERE id = ?", (menu_item_id,)
    ).fetchone()
    if not menu:
        conn.close()
        return jsonify({"error": "Món không tồn tại"}), 404

    stock = conn.execute(
        "SELECT quantity FROM inventory WHERE menu_item_id = ?", (menu_item_id,)
    ).fetchone()
    if stock and stock["quantity"] < quantity:
        conn.close()
        return jsonify({"error": f"Tồn kho không đủ ({stock['quantity']} còn lại)"}), 400

    existing = conn.execute(
        """
        SELECT id, quantity FROM order_items
        WHERE table_id = ? AND menu_item_id = ? AND note = ?
        """,
        (table_id, menu_item_id, note),
    ).fetchone()

    if existing and not note:
        new_qty = existing["quantity"] + quantity
        if stock and stock["quantity"] < new_qty:
            conn.close()
            return jsonify({"error": f"Tồn kho không đủ ({stock['quantity']} còn lại)"}), 400
        conn.execute(
            "UPDATE order_items SET quantity = quantity + ? WHERE id = ?",
            (quantity, existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO order_items (table_id, menu_item_id, name, price, quantity, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (table_id, menu["id"], menu["name"], menu["price"], quantity, note, vn_now()),
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.patch("/api/order-items/<int:item_id>")
def update_item(item_id):
    data = request.get_json(silent=True) or {}
    conn = get_connection()
    row = conn.execute("SELECT * FROM order_items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Món không tồn tại"}), 404

    quantity = data.get("quantity")
    if quantity is not None:
        qty = int(quantity)
        if qty <= 0:
            conn.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
        else:
            stock = conn.execute(
                "SELECT quantity FROM inventory WHERE menu_item_id = ?",
                (row["menu_item_id"],),
            ).fetchone()
            if stock and stock["quantity"] < qty:
                conn.close()
                return jsonify(
                    {"error": f"Tồn kho không đủ ({stock['quantity']} còn lại)"}
                ), 400
            conn.execute(
                "UPDATE order_items SET quantity = ? WHERE id = ?", (qty, item_id)
            )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.delete("/api/order-items/<int:item_id>")
def delete_item(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.post("/api/tables/<int:table_id>/checkout")
def checkout(table_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Bàn không tồn tại"}), 404

    items = conn.execute(
        """
        SELECT menu_item_id, name, price, quantity
        FROM order_items WHERE table_id = ?
        """,
        (table_id,),
    ).fetchall()
    total = sum(i["price"] * i["quantity"] for i in items)
    sold_at = vn_now()

    for item in items:
        stock = conn.execute(
            "SELECT quantity FROM inventory WHERE menu_item_id = ?",
            (item["menu_item_id"],),
        ).fetchone()
        if stock and stock["quantity"] < item["quantity"]:
            conn.close()
            return jsonify(
                {"error": f"Tồn kho không đủ cho {item['name']}"}
            ), 400

        conn.execute(
            """
            INSERT INTO sale_lines
            (table_id, table_label, menu_item_id, name, price, quantity, sold_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                table_id,
                row["label"],
                item["menu_item_id"],
                item["name"],
                item["price"],
                item["quantity"],
                sold_at,
            ),
        )
        conn.execute(
            """
            UPDATE inventory SET quantity = quantity - ?
            WHERE menu_item_id = ?
            """,
            (item["quantity"], item["menu_item_id"]),
        )

    conn.execute("DELETE FROM order_items WHERE table_id = ?", (table_id,))
    conn.execute(
        """
        UPDATE tables SET status = 'available', opened_at = NULL, note = ''
        WHERE id = ?
        """,
        (table_id,),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "total": total})


@app.post("/api/tables/<int:table_id>/cancel")
def cancel_table(table_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Bàn không tồn tại"}), 404

    items = conn.execute(
        """
        SELECT menu_item_id, name, price, quantity, note
        FROM order_items WHERE table_id = ?
        ORDER BY created_at
        """,
        (table_id,),
    ).fetchall()
    item_dicts = [dict(i) for i in items]
    line_count = len(item_dicts)
    total_value = sum(i["price"] * i["quantity"] for i in item_dicts)
    cancelled_at = vn_now()

    cur = conn.execute(
        """
        INSERT INTO order_cancellations (
            cancelled_at, table_id, table_label, opened_at, table_note,
            item_line_count, total_value, synced_to_sheets
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            cancelled_at,
            table_id,
            row["label"],
            row["opened_at"],
            row["note"] or "",
            line_count,
            total_value,
        ),
    )
    cancellation_id = cur.lastrowid

    for item in item_dicts:
        conn.execute(
            """
            INSERT INTO order_cancellation_lines
            (cancellation_id, menu_item_id, name, price, quantity, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cancellation_id,
                item["menu_item_id"],
                item["name"],
                item["price"],
                item["quantity"],
                item["note"] or "",
            ),
        )

    conn.execute("DELETE FROM order_items WHERE table_id = ?", (table_id,))
    conn.execute(
        """
        UPDATE tables SET status = 'available', opened_at = NULL, note = ''
        WHERE id = ?
        """,
        (table_id,),
    )
    conn.commit()

    synced = False
    sheets_error = None
    if _sheets_configured():
        try:
            from google_sheets import sync_order_cancellation

            sync_order_cancellation(
                cancellation_id,
                cancelled_at,
                row["label"],
                row["note"] or "",
                line_count,
                total_value,
                item_dicts,
            )
            conn.execute(
                "UPDATE order_cancellations SET synced_to_sheets = 1 WHERE id = ?",
                (cancellation_id,),
            )
            conn.commit()
            synced = True
        except Exception as exc:
            sheets_error = str(exc)

    conn.close()
    return jsonify(
        {
            "ok": True,
            "cancellationId": cancellation_id,
            "syncedToSheets": synced,
            "sheetsError": sheets_error,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
