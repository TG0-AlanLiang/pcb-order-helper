import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from config import ORDERS_HEADERS
from utils import message_store, orders_store
from utils.sheet_records import read_records


class OrderIdentityTests(unittest.TestCase):
    def setUp(self):
        self.ws = Mock()

    def records(self):
        self.ws.get_all_values.return_value = [
            ["OrderID", "PCBName", "Status", "CreatedAt"],
            [96368545, "Board A", "shipped", "2026-10-23 16:35"],
            [96415879, "Board B", "ordered", "2026-08-03 10:36"],
            ["", "", "", ""],
        ]
        return orders_store._parse_rows(self.ws)

    def test_raw_ids_remain_distinct_and_dates_remain_text(self):
        records = self.records()
        self.assertEqual([r["OrderID"] for r in records], ["96368545", "96415879"])
        self.assertEqual(records[0]["CreatedAt"], "2026-10-23 16:35")
        self.ws.get_all_values.assert_called_once_with(
            value_render_option="UNFORMATTED_VALUE",
            date_time_render_option="FORMATTED_STRING",
        )

    def test_text_ids_are_never_numericised(self):
        self.ws.get_all_values.return_value = [
            ["OrderID"], ["00123456"], ["18799e25"], [1.8799e29],
        ]
        self.assertEqual([r["OrderID"] for r in read_records(self.ws)],
                         ["00123456", "18799e25", "187990000000000000000000000000"])

    def test_fetch_rejects_real_duplicates_and_missing_ids(self):
        for records in [[{"OrderID": "same"}, {"OrderID": "same"}],
                        [{"PCBName": "No ID"}]]:
            with self.subTest(records=records), patch.object(
                orders_store.data_cache, "get", return_value=records
            ):
                with self.assertRaises(orders_store.OrderIdentityError):
                    orders_store.fetch_all_orders()

    def test_updates_target_full_raw_id_and_patch_only_that_order(self):
        self.ws.batch_get.return_value = [
            [["OrderID"], [96368545], [96415879]], [["OrderID", "Status"]],
        ]
        with patch.object(orders_store, "_on_orders_ws", side_effect=lambda fn: fn(self.ws)), \
                patch.object(orders_store.data_cache, "patch_rows") as cached:
            orders_store.update_order(None, "96415879", {"Status": "shipped"})
        self.ws.batch_get.assert_called_once_with(
            ["A:A", "1:1"], value_render_option="UNFORMATTED_VALUE",
            date_time_render_option="FORMATTED_STRING",
        )
        self.ws.batch_update.assert_called_once_with(
            [{"range": "B3", "values": [["shipped"]]}], value_input_option="USER_ENTERED",
        )
        predicate = cached.call_args.args[1]
        self.assertTrue(predicate({"OrderID": "96415879"}))
        self.assertFalse(predicate({"OrderID": "96368545"}))

    def test_ambiguous_missing_and_old_display_ids_never_write(self):
        for ids, target in [([96368545, 96368545], "96368545"),
                            ([96368545, 96415879], "9.64E+07"),
                            ([96368545], "missing")]:
            with self.subTest(target=target):
                self.ws.reset_mock()
                self.ws.batch_get.return_value = [
                    [["OrderID"], *[[value] for value in ids]], [["OrderID", "Status"]],
                ]
                with patch.object(orders_store, "_on_orders_ws", side_effect=lambda fn: fn(self.ws)), \
                        patch.object(orders_store.data_cache, "patch_rows") as cached:
                    with self.assertRaises(orders_store.OrderIdentityError):
                        orders_store.update_order(None, target, {"Status": "cancelled"})
                self.ws.batch_update.assert_not_called()
                cached.assert_not_called()

    def test_order_id_is_immutable(self):
        with self.assertRaises(orders_store.OrderIdentityError):
            orders_store.update_order(None, "96368545", {"OrderID": "other"})

    def test_new_orders_use_raw_text_and_full_prefixed_uuid(self):
        with patch.object(orders_store, "_on_orders_ws", side_effect=lambda fn: fn(self.ws)), \
                patch.object(orders_store.data_cache, "insert_row"):
            oid = orders_store.create_order(None, {"pcb_name": "Board"})
        self.assertRegex(oid, r"^ord_[0-9a-f]{32}$")
        self.assertEqual(self.ws.insert_row.call_args.args[0][0], oid)
        self.assertEqual(self.ws.insert_row.call_args.kwargs["value_input_option"], "RAW")

    def test_messages_preserve_links_without_guessing_rounded_id(self):
        self.ws.get_all_values.return_value = [
            ["MessageID", "OrderID", "Content"],
            ["m1", 96368545, "First"], ["m2", 96415879, "Second"],
            ["m3", 96400000, "Ambiguous historical message"],
        ]
        with patch.object(message_store, "_on_messages_ws", side_effect=lambda fn: fn(self.ws)):
            records = message_store._load_messages()
        with patch.object(message_store, "fetch_all_messages", return_value=records):
            self.assertEqual([m["MessageID"] for m in message_store.fetch_messages_for_order("96368545")], ["m1"])
            self.assertEqual([m["MessageID"] for m in message_store.fetch_messages_for_order("96415879")], ["m2"])
        self.assertEqual(records[2]["OrderID"], "96400000")

    def test_new_messages_store_exact_id_and_literal_content(self):
        with patch.object(orders_store, "fetch_order_by_id", return_value={"OrderID": "96368545"}), \
                patch.object(message_store, "_on_messages_ws", side_effect=lambda fn: fn(self.ws)), \
                patch.object(message_store.data_cache, "insert_row"):
            message_store.send_message(None, "96368545", "Engineer", "=literal text")
        row = self.ws.append_row.call_args.args[0]
        self.assertRegex(row[0], r"^msg_[0-9a-f]{32}$")
        self.assertEqual(row[1], "96368545")
        self.assertEqual(row[4], "=literal text")
        self.assertEqual(self.ws.append_row.call_args.kwargs["value_input_option"], "RAW")

    def test_stale_message_target_never_writes(self):
        with patch.object(orders_store, "fetch_order_by_id", return_value=None), \
                patch.object(message_store, "_on_messages_ws") as worksheet:
            with self.assertRaises(orders_store.OrderIdentityError):
                message_store.send_message(None, "9.64E+07", "Engineer", "Note")
        worksheet.assert_not_called()

    def test_process_order_page_has_distinct_open_buttons(self):
        records = self.records()
        page = Path(__file__).resolve().parents[1] / "pages" / "admin_process_order.py"
        with patch("utils.auth.require_role", return_value={"name": "Admin"}), \
                patch.object(orders_store, "fetch_all_orders", return_value=records), \
                patch("utils.google_client.get_gspread_client", return_value=None), \
                patch.object(message_store, "fetch_messages_for_order", return_value=[]):
            app = AppTest.from_file(str(page)).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual([b.key for b in app.button], ["open_96368545", "open_96415879"])
            app.button(key="open_96415879").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.session_state["process_order_id"], "96415879")

    def test_process_order_page_reports_real_duplicates(self):
        page = Path(__file__).resolve().parents[1] / "pages" / "admin_process_order.py"
        with patch("utils.auth.require_role", return_value={"name": "Admin"}), \
                patch.object(orders_store, "fetch_all_orders", side_effect=orders_store.OrderIdentityError("Duplicate OrderID")):
            app = AppTest.from_file(str(page)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.error[0].value, "Duplicate OrderID")
        self.assertEqual(len(app.button), 0)


if __name__ == "__main__":
    unittest.main()
