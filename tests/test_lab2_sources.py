import logging
import tempfile
import unittest
from pathlib import Path

from docx import Document
from openpyxl import Workbook

from models import Ticket
from sources import DocxTicketProvider, ExcelStudentProvider


def write_document(path: Path, paragraphs: list[str]) -> None:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)


class TicketSourceTests(unittest.TestCase):
    def test_valid_ticket_preserves_number_and_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.docx"
            write_document(path, ["Билет 42", "1. First question", "2. Second question", "3. Third question"])

            tickets = DocxTicketProvider(path).tickets()

            self.assertEqual(
                tickets,
                (Ticket(42, ("First question", "Second question", "Third question")),),
            )

    def test_ticket_with_fewer_questions_is_skipped_and_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.docx"
            write_document(path, ["Билет 7", "1. Only question", "2. Another question"])

            with self.assertLogs("sources", level=logging.WARNING) as logs:
                tickets = DocxTicketProvider(path).tickets()

            self.assertEqual(tickets, ())
            self.assertTrue(any("Билет 7" in message for message in logs.output))

    def test_malformed_heading_ends_previous_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.docx"
            write_document(
                path,
                [
                    "Билет 10", "1. A", "2. B",
                    "Билет without a number", "3. Must not attach",
                    "Билет 20", "1. C", "2. D", "3. E",
                ],
            )

            tickets = DocxTicketProvider(path).tickets()

            self.assertEqual([ticket.number for ticket in tickets], [20])
            self.assertNotIn("Must not attach", tickets[0].questions)

    def test_duplicate_ticket_numbers_are_all_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.docx"
            write_document(
                path,
                [
                    "Билет 3", "1. First", "2. Second", "3. Third",
                    "Билет 3", "1. Other", "2. Other", "3. Other",
                    "Билет 9", "1. Nine", "2. Nine", "3. Nine",
                ],
            )

            tickets = DocxTicketProvider(path).tickets()

            self.assertEqual([ticket.number for ticket in tickets], [9])

    def test_gaps_do_not_create_nonexistent_tickets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.docx"
            write_document(path, ["Билет 2", "1. A", "2. B", "3. C", "Билет 8", "1. D", "2. E", "3. F"])

            provider = DocxTicketProvider(path)

            self.assertEqual([ticket.number for ticket in provider.tickets()], [2, 8])
            self.assertIsNone(provider.get_ticket(1))
            self.assertIsNone(provider.get_ticket(7))


class StudentSourceTests(unittest.TestCase):
    def test_groups_students_and_whitespace_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "students.xlsx"
            workbook = Workbook()
            first = workbook.active
            first.title = "Group A"
            first.append(("Фамилия", "Имя"))
            first.append(("  Ivanov  ", " Ivan "))
            first.append(("OnlyLast", None))
            first.append((None, "OnlyFirst"))
            second = workbook.create_sheet("Empty")
            second.append(("Фамилия", "Имя"))
            workbook.create_sheet("Group B").append(("Фамилия", "Имя"))
            workbook["Group B"].append(("Petrov", "Petr"))
            workbook.save(path)
            workbook.close()

            provider = ExcelStudentProvider(path)

            self.assertEqual(provider.groups(), ("Group A", "Empty", "Group B"))
            self.assertEqual([(s.last_name, s.first_name) for s in provider.students("Group A")], [("Ivanov", "Ivan")])
            self.assertEqual(provider.students("Empty"), ())
            self.assertEqual([(s.last_name, s.first_name) for s in provider.students("Group B")], [("Petrov", "Petr")])
