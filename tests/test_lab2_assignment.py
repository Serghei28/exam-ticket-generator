import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

import repositories
from models import PreparedAssignment, Student, Ticket
from repositories import ExcelResultsRepository, RepositoryError
from services import AssignmentError, AssignmentService


class FakeTickets:
    def __init__(self, tickets):
        self._tickets = tuple(tickets)

    def tickets(self):
        return self._tickets

    def get_ticket(self, number):
        return next((ticket for ticket in self._tickets if ticket.number == number), None)


def ticket(number):
    return Ticket(number, (f"{number}. one", f"{number}. two", f"{number}. three"))


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.student = Student("A", "Ivanov", "Ivan")
        self.other_group_student = Student("B", "Ivanov", "Ivan")
        self.timestamp = datetime(2026, 10, 21, 12, 0)

    def make_service(self, repository, tickets=(ticket(2), ticket(8)), selected=2):
        return AssignmentService(
            FakeTickets(tickets),
            repository,
            ticket_selector=lambda available: next(item for item in available if item.number == selected),
            clock=lambda: self.timestamp,
        )

    def test_first_and_repeat_assignments_persist_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            repository = ExcelResultsRepository(path)
            service = self.make_service(repository)

            first = service.prepare(self.student)
            service.persist(first)
            second = service.prepare(self.student)
            service.persist(second)

            workbook = load_workbook(path)
            rows = list(workbook.active.iter_rows(min_row=2, max_col=6, values_only=True))
            workbook.close()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][:4], ("A", "Ivanov", "Ivan", 2))
            self.assertEqual(rows[0][5], "нет")
            self.assertEqual(rows[1][:4], ("A", "Ivanov", "Ivan", 2))
            self.assertEqual(rows[1][5], "да")
            self.assertEqual(rows[0][4], self.timestamp)

    def test_restart_keeps_original_ticket_and_groups_are_identity_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            repository = ExcelResultsRepository(path)
            service = self.make_service(repository, selected=8)
            first = service.prepare(self.student)
            service.persist(first)

            restarted = self.make_service(ExcelResultsRepository(path), selected=2)
            repeated = restarted.prepare(self.student)
            different_student = restarted.prepare(self.other_group_student)

            self.assertEqual(repeated.ticket_number, 8)
            self.assertTrue(repeated.repeated)
            self.assertEqual(different_student.ticket_number, 2)
            self.assertFalse(different_student.repeated)

    def test_first_matching_history_row_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            repository = ExcelResultsRepository(path)
            repository.append(PreparedAssignment(self.student, 8, self.timestamp, False))
            repository.append(PreparedAssignment(self.student, 2, self.timestamp, False))

            assignment = self.make_service(repository, tickets=(ticket(2), ticket(8))).prepare(self.student)

            self.assertEqual(assignment.ticket_number, 8)
            self.assertTrue(assignment.repeated)

    def test_missing_original_ticket_fails_without_replacement_or_new_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            repository = ExcelResultsRepository(path)
            repository.append(PreparedAssignment(self.student, 99, self.timestamp, False))
            service = self.make_service(repository, tickets=(ticket(2),))

            with self.assertRaisesRegex(AssignmentError, "99"):
                service.prepare(self.student)

            self.assertEqual(len(repository.history()), 1)


class RepositoryTests(unittest.TestCase):
    def assignment(self, number=2, repeated=False):
        return PreparedAssignment(
            Student("A", "Ivanov", "Ivan"),
            number,
            datetime(2026, 10, 21, 12, 0),
            repeated,
        )

    def test_successful_save_is_immediately_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            repository = ExcelResultsRepository(path)
            repository.append(self.assignment())

            reopened = ExcelResultsRepository(path)

            self.assertEqual(reopened.history(), (self.assignment(),))

    def test_replace_permission_error_preserves_original_and_retry_adds_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            repository = ExcelResultsRepository(path)
            prepared = self.assignment(8, True)
            real_replace = repositories.os.replace

            with patch.object(repositories.os, "replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    repository.append(prepared)
            self.assertEqual(repository.history(), ())

            with patch.object(repositories.os, "replace", side_effect=real_replace):
                repository.append(prepared)
            self.assertEqual(repository.history(), (prepared,))

    def test_corrupt_journal_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            original = b"not an xlsx file"
            path.write_bytes(original)

            with self.assertRaises(RepositoryError):
                ExcelResultsRepository(path)

            self.assertEqual(path.read_bytes(), original)

    def test_invalid_headers_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xlsx"
            workbook = Workbook()
            workbook.active.append(("wrong",) * 6)
            workbook.save(path)
            workbook.close()
            original = path.read_bytes()

            with self.assertRaises(RepositoryError):
                ExcelResultsRepository(path)

            self.assertEqual(path.read_bytes(), original)
