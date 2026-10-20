import unittest
from datetime import datetime
from unittest.mock import Mock, call, patch

import main


class MainInputTests(unittest.TestCase):
    def test_empty_input_is_rejected_and_whitespace_is_trimmed(self):
        keys = iter([" ", " ", "\r", " ", "И", "в", "а", "н", " ", "\r"])

        value = main.read_name("Name: ", getch=lambda: next(keys))

        self.assertEqual(value, "Иван")

    def test_backspace_removes_previous_character(self):
        keys = iter(["И", "в", "а", "н", "\b", "н", "\r"])

        value = main.read_name("Name: ", getch=lambda: next(keys))

        self.assertEqual(value, "Иван")

    def test_escape_returns_none_immediately(self):
        getch = Mock(return_value="\x1b")

        value = main.read_name("Name: ", getch=getch)

        self.assertIsNone(value)
        getch.assert_called_once_with()


class MainSavingTests(unittest.TestCase):
    def test_save_with_retry_reuses_same_record_without_duplicate_call_data(self):
        timestamp = datetime(2026, 10, 20, 22, 4, 0)
        append_record = Mock(side_effect=[PermissionError("locked"), None])

        with patch.object(main, "append_record", append_record), patch.object(
            main, "wait_for_save_retry", return_value=True
        ) as wait_for_retry:
            saved = main.save_with_retry("Иванов", "Иван", 7, timestamp)

        self.assertTrue(saved)
        self.assertEqual(append_record.call_count, 2)
        expected_call = call(main.JOURNAL_PATH, "Иванов", "Иван", 7, timestamp)
        self.assertEqual(append_record.call_args_list, [expected_call, expected_call])
        wait_for_retry.assert_called_once_with()

    def test_main_saves_before_prompting_for_next_student(self):
        read_name = Mock(side_effect=["Иванов", "Иван", None])
        timestamp = datetime(2026, 10, 20, 22, 5, 0)

        def save_and_confirm_order(*args):
            self.assertEqual(read_name.call_count, 2)
            self.assertEqual(args, ("Иванов", "Иван", 11, timestamp))
            return True

        with patch.object(main, "read_name", read_name), patch.object(
            main, "generate_ticket", return_value=11
        ), patch.object(main, "datetime") as datetime_type, patch.object(
            main, "save_with_retry", side_effect=save_and_confirm_order
        ):
            datetime_type.now.return_value = timestamp
            main.main()

        self.assertEqual(
            read_name.call_args_list,
            [call("Last name: "), call("First name: "), call("Last name: ")],
        )


if __name__ == "__main__":
    unittest.main()
