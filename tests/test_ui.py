import tkinter as tk
import unittest
from datetime import datetime

from models import PreparedAssignment, Student, Ticket
from ui import ExamTicketApp, _plural


class FakeStudents:
    def __init__(self):
        self._groups = {
            "Группа А": (Student("Группа А", "Волков", "Илья"), Student("Группа А", "Соколова", "Мария")),
            "Пустая группа": (),
        }

    def groups(self):
        return tuple(self._groups)

    def students(self, group):
        return self._groups.get(group, ())


class FakeTickets:
    def __init__(self):
        self._ticket = Ticket(3, ("Что такое SQL?", "Что такое транзакция?", "Зачем нужны индексы?"))

    def tickets(self):
        return (self._ticket,)

    def get_ticket(self, number):
        return self._ticket if number == self._ticket.number else None


class FakeService:
    def __init__(self, repeated=False):
        self.persisted = []
        self.repeated = repeated

    def prepare(self, student):
        return PreparedAssignment(student, 3, datetime(2026, 11, 17, 9, 30), self.repeated)

    def persist(self, assignment):
        self.persisted.append(assignment)


class PluralTests(unittest.TestCase):
    def test_russian_plural_forms(self):
        forms = ("билет", "билета", "билетов")
        self.assertEqual(_plural(1, *forms), "билет")
        self.assertEqual(_plural(3, *forms), "билета")
        self.assertEqual(_plural(5, *forms), "билетов")
        self.assertEqual(_plural(11, *forms), "билетов")
        self.assertEqual(_plural(21, *forms), "билет")


class ExamTicketAppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk недоступен: {error}")
        self.root.withdraw()
        self.service = FakeService()
        self.app = ExamTicketApp(self.root, FakeStudents(), FakeTickets(), self.service)

    def tearDown(self):
        self.root.destroy()

    def select(self, combo, value):
        combo.set(value)
        combo.event_generate("<<ComboboxSelected>>")
        self.root.update_idletasks()

    def test_nothing_selected_on_start(self):
        self.assertEqual(self.app.group_combo.get(), "")
        self.assertEqual(str(self.app.student_combo["state"]), "disabled")
        self.assertEqual(str(self.app.generate_button["state"]), "disabled")

    def test_empty_group_keeps_generation_disabled(self):
        self.select(self.app.group_combo, "Пустая группа")
        self.app._on_group_changed()
        self.assertEqual(str(self.app.student_combo["state"]), "disabled")
        self.assertEqual(str(self.app.generate_button["state"]), "disabled")

    def test_generate_persists_and_shows_result_then_resets(self):
        self.select(self.app.group_combo, "Группа А")
        self.app._on_group_changed()
        self.app.student_combo.current(1)
        self.app._on_student_changed()
        self.assertEqual(str(self.app.generate_button["state"]), "normal")

        self.app._generate()

        self.assertEqual(len(self.service.persisted), 1)
        self.assertEqual(self.service.persisted[0].student.last_name, "Соколова")
        window = self.app.result_window
        self.assertTrue(window.winfo_exists())
        self.assertEqual(window.title(), "Билет № 3")
        self.assertEqual(str(self.app.generate_button["state"]), "disabled")

        self.app._close_result(window)

        self.assertFalse(window.winfo_exists())
        self.assertEqual(self.app.student_combo.get(), "")
        self.assertEqual(str(self.app.generate_button["state"]), "disabled")


if __name__ == "__main__":
    unittest.main()
