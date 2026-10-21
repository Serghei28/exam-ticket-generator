import tkinter as tk
from tkinter import messagebox, ttk

from models import PreparedAssignment, Student
from repositories import RepositoryError
from services import AssignmentError, AssignmentService
from sources import SourceError


class ExamTicketApp:
    def __init__(self, root: tk.Tk, student_provider, ticket_provider, service: AssignmentService) -> None:
        self.root = root
        self.student_provider = student_provider
        self.ticket_provider = ticket_provider
        self.service = service
        self._students: tuple[Student, ...] = ()
        self._prepared: PreparedAssignment | None = None
        self._busy = False
        self._build()

    def _build(self) -> None:
        self.root.title("Генератор экзаменационных билетов")
        self.root.minsize(560, 260)
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Группа:").grid(row=0, column=0, sticky="w", pady=6)
        self.group_combo = ttk.Combobox(frame, state="readonly")
        self.group_combo.grid(row=0, column=1, sticky="ew", pady=6)
        self.group_combo.bind("<<ComboboxSelected>>", self._on_group_changed)

        ttk.Label(frame, text="Студент:").grid(row=1, column=0, sticky="w", pady=6)
        self.student_combo = ttk.Combobox(frame, state="disabled")
        self.student_combo.grid(row=1, column=1, sticky="ew", pady=6)
        self.student_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_button())

        self.generate_button = ttk.Button(
            frame, text="Сгенерировать билет", command=self._generate, state="disabled"
        )
        self.generate_button.grid(row=2, column=0, columnspan=2, pady=(18, 4))

        groups = self.student_provider.groups()
        self.group_combo["values"] = groups
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._update_button()
        if not self.ticket_provider.tickets():
            messagebox.showwarning(
                "Нет билетов",
                "В tickets.docx не найдено ни одного корректного билета. "
                "Генерация отключена.",
                parent=self.root,
            )

    def _on_group_changed(self, _event=None) -> None:
        group = self.group_combo.get()
        self.student_combo.set("")
        self._students = self.student_provider.students(group)
        self.student_combo["values"] = tuple(student.display_name for student in self._students)
        self.student_combo.configure(state="readonly" if self._students else "disabled")
        self._update_button()

    def _update_button(self) -> None:
        enabled = bool(
            self.group_combo.get()
            and self.student_combo.get()
            and self._students
            and self.ticket_provider.tickets()
            and not self._busy
        )
        self.generate_button.configure(state="normal" if enabled else "disabled")

    def _generate(self) -> None:
        if self._busy or not self._students:
            return
        index = self.student_combo.current()
        if index < 0:
            return
        self._busy = True
        self._update_button()
        student = self._students[index]
        try:
            self._prepared = self.service.prepare(student)
            self._persist_with_retry()
        except (AssignmentError, RepositoryError, SourceError) as error:
            self._busy = False
            self._prepared = None
            self._update_button()
            messagebox.showerror("Ошибка", str(error), parent=self.root)

    def _persist_with_retry(self) -> None:
        assert self._prepared is not None
        try:
            self.service.persist(self._prepared)
        except PermissionError:
            retry = messagebox.askretrycancel(
                "Файл занят",
                "Не удалось сохранить results.xlsx.\nЗакройте файл и повторите попытку.",
                parent=self.root,
            )
            if retry:
                self._persist_with_retry()
            else:
                self._busy = False
                self._prepared = None
                self._update_button()
            return
        except RepositoryError as error:
            self._busy = False
            self._prepared = None
            self._update_button()
            messagebox.showerror("Ошибка сохранения", str(error), parent=self.root)
            return
        self._show_result(self._prepared)

    def _show_result(self, assignment: PreparedAssignment) -> None:
        ticket = self.ticket_provider.get_ticket(assignment.ticket_number)
        if ticket is None:
            self._busy = False
            self._prepared = None
            self._update_button()
            messagebox.showerror("Ошибка", "Назначенный билет отсутствует в источнике.", parent=self.root)
            return
        window = tk.Toplevel(self.root)
        window.title("Экзаменационный билет")
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_result(window))
        window.bind("<Escape>", lambda _event: self._close_result(window))
        content = ttk.Frame(window, padding=18)
        content.pack(fill=tk.BOTH, expand=True)
        ttk.Label(content, text=f"Ваш билет № {ticket.number}", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        for number, question in enumerate(ticket.questions, start=1):
            ttk.Label(content, text=f"{number}. {question}", wraplength=520, justify="left").pack(anchor="w", pady=(12, 0))
        window.grab_set()
        window.focus_set()

    def _close_result(self, window: tk.Toplevel) -> None:
        if window.winfo_exists():
            window.grab_release()
            window.destroy()
        self._prepared = None
        self._busy = False
        self.student_combo.set("")
        self._update_button()
        self.root.focus_set()
