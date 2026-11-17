import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from models import PreparedAssignment, Student, Ticket
from repositories import RepositoryError
from services import AssignmentError, AssignmentService
from sources import SourceError


# --- Design tokens -----------------------------------------------------------

PALETTE = {
    "bg": "#F3F4FA",
    "card": "#FFFFFF",
    "border": "#E2E5F0",
    "text": "#1C2033",
    "muted": "#6B7290",
    "accent": "#5B4BF5",
    "accent_hover": "#4A3AE0",
    "accent_pressed": "#3B2DC4",
    "accent_soft": "#EEEBFF",
    "gradient_from": "#5B4BF5",
    "gradient_to": "#A64BF5",
    "disabled_bg": "#E6E8F0",
    "disabled_fg": "#A0A6BC",
    "success": "#15803D",
    "success_soft": "#E3F6EA",
    "warning": "#B45309",
    "warning_soft": "#FFF1DB",
    "warning_from": "#F59E0B",
    "warning_to": "#F97316",
    "danger": "#B91C1C",
    "danger_soft": "#FDE7E7",
}


def _pick_font_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for family in ("Segoe UI Variable Display", "Segoe UI", "Helvetica Neue", "Arial"):
        if family in available:
            return family
    return "TkDefaultFont"


def _mix(color_a: str, color_b: str, ratio: float) -> str:
    a = tuple(int(color_a[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * ratio):02x}" for x, y in zip(a, b))


def _plural(count: int, one: str, few: str, many: str) -> str:
    tail = count % 100
    if 11 <= tail <= 14:
        return many
    tail = count % 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


class GradientHeader(tk.Canvas):
    """A horizontal gradient band with a title and subtitle drawn on top."""

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        subtitle: str,
        family: str,
        colors: tuple[str, str] = (PALETTE["gradient_from"], PALETTE["gradient_to"]),
        title_size: int = 18,
        scale: float = 1.0,
    ) -> None:
        self._title = title
        self._subtitle = subtitle
        self._colors = colors
        self._title_font = tkfont.Font(master, family=family, size=title_size, weight="bold")
        self._subtitle_font = tkfont.Font(master, family=family, size=10)
        self._pad_x = round(28 * scale)
        self._pad_y = round(22 * scale)
        self._gap = round(4 * scale)
        height = (
            self._pad_y * 2
            + self._title_font.metrics("linespace")
            + self._gap
            + self._subtitle_font.metrics("linespace")
        )
        width = self._pad_x * 2 + max(
            self._title_font.measure(title), self._subtitle_font.measure(subtitle)
        )
        super().__init__(master, width=width, height=height, highlightthickness=0, bd=0)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        steps = 96
        for step in range(steps):
            x0 = width * step / steps
            x1 = width * (step + 1) / steps + 1
            color = _mix(self._colors[0], self._colors[1], step / (steps - 1))
            self.create_rectangle(x0, 0, x1, height, fill=color, outline=color)
        # Soft decorative circles in the corner.
        light = _mix(self._colors[1], "#FFFFFF", 0.16)
        lighter = _mix(self._colors[1], "#FFFFFF", 0.28)
        self.create_oval(width - height * 1.3, -height * 0.6, width + height * 0.4, height * 1.1, fill=light, outline="")
        self.create_oval(width - height * 0.55, height * 0.55, width + height * 0.25, height * 1.35, fill=lighter, outline="")
        title_height = self._title_font.metrics("linespace")
        self.create_text(
            self._pad_x,
            self._pad_y,
            text=self._title,
            anchor="nw",
            fill="#FFFFFF",
            font=self._title_font,
        )
        self.create_text(
            self._pad_x,
            self._pad_y + title_height + self._gap,
            text=self._subtitle,
            anchor="nw",
            fill=_mix("#FFFFFF", self._colors[0], 0.2),
            font=self._subtitle_font,
        )


class Card(tk.Frame):
    """A white panel with a thin border."""

    def __init__(self, master: tk.Misc, padding: int = 20, **kwargs) -> None:
        super().__init__(
            master,
            bg=PALETTE["card"],
            highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["border"],
            highlightthickness=1,
            bd=0,
            **kwargs,
        )
        self.inner = tk.Frame(self, bg=PALETTE["card"])
        self.inner.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)


class ExamTicketApp:
    def __init__(self, root: tk.Tk, student_provider, ticket_provider, service: AssignmentService) -> None:
        self.root = root
        self.student_provider = student_provider
        self.ticket_provider = ticket_provider
        self.service = service
        self._students: tuple[Student, ...] = ()
        self._prepared: PreparedAssignment | None = None
        self._busy = False
        self._family = _pick_font_family(root)
        self._scale = max(root.winfo_fpixels("1i") / 96.0, 1.0)
        self._configure_styles()
        self._build()

    def _px(self, value: float) -> int:
        """Converts a 96-DPI design size into real screen pixels."""
        return round(value * self._scale)

    # --- Styling --------------------------------------------------------------

    def _configure_styles(self) -> None:
        family = self._family
        self.root.configure(bg=PALETTE["bg"])
        self.root.option_add("*TCombobox*Listbox.font", (family, 11))
        self.root.option_add("*TCombobox*Listbox.background", PALETTE["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", PALETTE["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", PALETTE["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.root.option_add("*TCombobox*Listbox.borderWidth", 0)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=(family, 10), background=PALETTE["bg"], foreground=PALETTE["text"])

        style.configure(
            "Modern.TCombobox",
            padding=(self._px(12), self._px(9)),
            fieldbackground=PALETTE["card"],
            background=PALETTE["card"],
            foreground=PALETTE["text"],
            bordercolor=PALETTE["border"],
            lightcolor=PALETTE["card"],
            darkcolor=PALETTE["card"],
            arrowcolor=PALETTE["accent"],
            arrowsize=self._px(15),
            selectbackground=PALETTE["card"],
            selectforeground=PALETTE["text"],
            font=(family, 11),
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("disabled", PALETTE["bg"]), ("readonly", PALETTE["card"])],
            foreground=[("disabled", PALETTE["disabled_fg"])],
            bordercolor=[
                ("disabled", PALETTE["border"]),
                ("focus", PALETTE["accent"]),
                ("hover", _mix(PALETTE["border"], PALETTE["accent"], 0.45)),
            ],
            arrowcolor=[("disabled", PALETTE["disabled_fg"])],
            background=[("disabled", PALETTE["bg"])],
            selectbackground=[("readonly", PALETTE["card"])],
            selectforeground=[("readonly", PALETTE["text"])],
        )

        style.configure(
            "Accent.TButton",
            font=(family, 12, "bold"),
            padding=(self._px(22), self._px(13)),
            background=PALETTE["accent"],
            foreground="#FFFFFF",
            bordercolor=PALETTE["accent"],
            lightcolor=PALETTE["accent"],
            darkcolor=PALETTE["accent"],
            focuscolor=PALETTE["accent"],
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Accent.TButton",
            background=[
                ("disabled", PALETTE["disabled_bg"]),
                ("pressed", PALETTE["accent_pressed"]),
                ("active", PALETTE["accent_hover"]),
            ],
            foreground=[("disabled", PALETTE["disabled_fg"])],
            bordercolor=[("disabled", PALETTE["disabled_bg"]), ("active", PALETTE["accent_hover"])],
            lightcolor=[("disabled", PALETTE["disabled_bg"]), ("active", PALETTE["accent_hover"])],
            darkcolor=[("disabled", PALETTE["disabled_bg"]), ("active", PALETTE["accent_hover"])],
        )

        style.configure(
            "Ghost.TButton",
            font=(family, 10, "bold"),
            padding=(self._px(18), self._px(9)),
            background=PALETTE["accent_soft"],
            foreground=PALETTE["accent"],
            bordercolor=PALETTE["accent_soft"],
            lightcolor=PALETTE["accent_soft"],
            darkcolor=PALETTE["accent_soft"],
            focuscolor=PALETTE["accent_soft"],
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Ghost.TButton",
            background=[("pressed", "#DCD6FF"), ("active", "#E4DFFF")],
            bordercolor=[("active", "#E4DFFF")],
            lightcolor=[("active", "#E4DFFF")],
            darkcolor=[("active", "#E4DFFF")],
        )

    def _label(self, master, text="", size=10, weight="normal", color="text", bg="card", **kwargs) -> tk.Label:
        return tk.Label(
            master,
            text=text,
            bg=PALETTE[bg],
            fg=PALETTE[color],
            font=(self._family, size, weight),
            **kwargs,
        )

    def _chip(self, master, title: str, value: str) -> tk.Frame:
        chip = tk.Frame(
            master,
            bg=PALETTE["card"],
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
        )
        body = tk.Frame(chip, bg=PALETTE["card"])
        body.pack(padx=self._px(16), pady=self._px(10), fill=tk.X)
        value_label = self._label(body, value, size=17, weight="bold", color="accent")
        value_label.pack(anchor="w")
        self._label(body, title, size=9, color="muted").pack(anchor="w")
        chip.value_label = value_label
        return chip

    # --- Layout ---------------------------------------------------------------

    def _build(self) -> None:
        self.root.title("Генератор экзаменационных билетов")
        header = GradientHeader(
            self.root,
            "Генератор экзаменационных билетов",
            "Выберите группу и студента — билет будет выдан и сохранён в журнал",
            self._family,
            scale=self._scale,
        )
        header.pack(fill=tk.X)

        body = tk.Frame(self.root, bg=PALETTE["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=self._px(24), pady=(self._px(20), self._px(12)))

        groups = self.student_provider.groups()
        tickets = self.ticket_provider.tickets()
        student_total = sum(len(self.student_provider.students(group)) for group in groups)

        stats = tk.Frame(body, bg=PALETTE["bg"])
        stats.pack(fill=tk.X)
        for column, (title, value) in enumerate(
            (
                (_plural(len(groups), "группа", "группы", "групп"), len(groups)),
                (_plural(student_total, "студент", "студента", "студентов"), student_total),
                (_plural(len(tickets), "билет", "билета", "билетов"), len(tickets)),
            )
        ):
            stats.columnconfigure(column, weight=1, uniform="stats")
            chip = self._chip(stats, title, str(value))
            chip.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else self._px(6), 0 if column == 2 else self._px(6)))

        card = Card(body, padding=self._px(22))
        card.pack(fill=tk.BOTH, expand=True, pady=(self._px(16), 0))
        form = card.inner
        form.columnconfigure(0, weight=1)

        self._step_label(form, "1", "Группа").grid(row=0, column=0, sticky="w")
        self.group_combo = ttk.Combobox(form, state="readonly", style="Modern.TCombobox", font=(self._family, 11))
        self.group_combo.grid(row=1, column=0, sticky="ew", pady=(self._px(8), self._px(16)))
        self.group_combo.bind("<<ComboboxSelected>>", self._on_group_changed)

        self._step_label(form, "2", "Студент").grid(row=2, column=0, sticky="w")
        self.student_combo = ttk.Combobox(form, state="disabled", style="Modern.TCombobox", font=(self._family, 11))
        self.student_combo.grid(row=3, column=0, sticky="ew", pady=(self._px(8), self._px(6)))
        self.student_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_student_changed())

        self.hint_label = self._label(form, "", size=9, color="muted", anchor="w", justify="left")
        self.hint_label.grid(row=4, column=0, sticky="ew")

        self.generate_button = ttk.Button(
            form,
            text="Сгенерировать билет  →",
            command=self._generate,
            state="disabled",
            style="Accent.TButton",
            cursor="hand2",
        )
        self.generate_button.grid(row=5, column=0, sticky="ew", pady=(self._px(20), 0))

        footer = tk.Frame(self.root, bg=PALETTE["bg"])
        footer.pack(fill=tk.X, padx=self._px(24), pady=(0, self._px(16)))
        dot = self._px(10)
        self.status_dot = tk.Canvas(footer, width=dot, height=dot, bg=PALETTE["bg"], highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, pady=(2, 0))
        self.status_label = self._label(footer, "", size=9, color="muted", bg="bg")
        self.status_label.pack(side=tk.LEFT, padx=(self._px(8), 0))

        self.group_combo["values"] = groups
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.bind("<Return>", self._on_return)
        self._set_hint("Начните с выбора группы.")
        if tickets:
            self._set_status("Результаты сохраняются в results.xlsx", PALETTE["success"])
        else:
            self._set_status("Нет корректных билетов в tickets.docx — генерация отключена", PALETTE["danger"])
        self._update_button()
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())
        if not tickets:
            messagebox.showwarning(
                "Нет билетов",
                "В tickets.docx не найдено ни одного корректного билета. "
                "Генерация отключена.",
                parent=self.root,
            )

    def _step_label(self, master, number: str, text: str) -> tk.Frame:
        row = tk.Frame(master, bg=PALETTE["card"])
        size = self._px(24)
        badge = tk.Canvas(row, width=size, height=size, bg=PALETTE["card"], highlightthickness=0)
        badge.create_oval(1, 1, size - 1, size - 1, fill=PALETTE["accent_soft"], outline="")
        badge.create_text(size / 2, size / 2, text=number, fill=PALETTE["accent"], font=(self._family, 9, "bold"))
        badge.pack(side=tk.LEFT)
        self._label(row, text, size=11, weight="bold").pack(side=tk.LEFT, padx=(self._px(10), 0))
        return row

    def _set_hint(self, text: str, color: str = "muted") -> None:
        self.hint_label.configure(text=text, fg=PALETTE[color])

    def _set_status(self, text: str, color: str) -> None:
        self.status_dot.delete("all")
        dot = self._px(10)
        self.status_dot.create_oval(1, 1, dot - 1, dot - 1, fill=color, outline="")
        self.status_label.configure(text=text)

    # --- Behaviour ------------------------------------------------------------

    def _on_return(self, _event=None) -> None:
        if str(self.generate_button["state"]) == "normal":
            self._generate()

    def _on_group_changed(self, _event=None) -> None:
        group = self.group_combo.get()
        self.student_combo.set("")
        self._students = self.student_provider.students(group)
        self.student_combo["values"] = tuple(student.display_name for student in self._students)
        self.student_combo.configure(state="readonly" if self._students else "disabled")
        if self._students:
            count = len(self._students)
            self._set_hint(f"В группе {count} {_plural(count, 'студент', 'студента', 'студентов')}. Выберите студента.")
        else:
            self._set_hint("В этой группе пока нет студентов.", "warning")
        self._update_button()

    def _on_student_changed(self) -> None:
        if self.student_combo.get():
            self._set_hint("Всё готово — нажмите кнопку или Enter.", "success")
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

    # --- Result window --------------------------------------------------------

    def _show_result(self, assignment: PreparedAssignment) -> None:
        ticket = self.ticket_provider.get_ticket(assignment.ticket_number)
        if ticket is None:
            self._busy = False
            self._prepared = None
            self._update_button()
            messagebox.showerror("Ошибка", "Назначенный билет отсутствует в источнике.", parent=self.root)
            return
        window = tk.Toplevel(self.root)
        window.title(f"Билет № {ticket.number}")
        window.configure(bg=PALETTE["bg"])
        window.transient(self.root)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_result(window))
        window.bind("<Escape>", lambda _event: self._close_result(window))
        window.bind("<Return>", lambda _event: self._close_result(window))
        self.result_window = window
        self._build_result(window, assignment, ticket)
        self._center_over_root(window)
        window.grab_set()
        window.focus_set()

    def _build_result(self, window: tk.Toplevel, assignment: PreparedAssignment, ticket: Ticket) -> None:
        student = assignment.student
        if assignment.repeated:
            colors = (PALETTE["warning_from"], PALETTE["warning_to"])
            badge_text, badge_fg, badge_bg = "Повторная выдача", PALETTE["warning"], PALETTE["warning_soft"]
        else:
            colors = (PALETTE["gradient_from"], PALETTE["gradient_to"])
            badge_text, badge_fg, badge_bg = "Новая выдача", PALETTE["success"], PALETTE["success_soft"]

        header = GradientHeader(
            window,
            f"Билет № {ticket.number}",
            f"{student.display_name}  ·  {student.group}",
            self._family,
            colors=colors,
            title_size=26,
            scale=self._scale,
        )
        header.pack(fill=tk.X)

        body = tk.Frame(window, bg=PALETTE["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=self._px(24), pady=self._px(20))

        meta = tk.Frame(body, bg=PALETTE["bg"])
        meta.pack(fill=tk.X, pady=(0, self._px(14)))
        tk.Label(
            meta,
            text=f"  {badge_text}  ",
            bg=badge_bg,
            fg=badge_fg,
            font=(self._family, 9, "bold"),
            pady=self._px(4),
        ).pack(side=tk.LEFT)
        self._label(
            meta,
            assignment.timestamp.strftime("%d.%m.%Y  %H:%M:%S"),
            size=9,
            color="muted",
            bg="bg",
        ).pack(side=tk.RIGHT)

        for number, question in enumerate(ticket.questions, start=1):
            card = Card(body, padding=self._px(14))
            card.pack(fill=tk.X, pady=(0, self._px(10)))
            row = card.inner
            size = self._px(32)
            badge = tk.Canvas(row, width=size, height=size, bg=PALETTE["card"], highlightthickness=0)
            badge.create_oval(1, 1, size - 1, size - 1, fill=colors[0], outline="")
            badge.create_text(size / 2, size / 2, text=str(number), fill="#FFFFFF", font=(self._family, 11, "bold"))
            badge.pack(side=tk.LEFT, anchor="n")
            self._label(
                row,
                question,
                size=11,
                anchor="w",
                justify="left",
                wraplength=self._px(430),
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(self._px(14), 0), pady=(self._px(5), 0))

        footer = tk.Frame(body, bg=PALETTE["bg"])
        footer.pack(fill=tk.X, pady=(self._px(8), 0))
        self._label(footer, "Esc или Enter — закрыть", size=9, color="muted", bg="bg").pack(side=tk.LEFT)
        ttk.Button(
            footer,
            text="Готово",
            style="Ghost.TButton",
            cursor="hand2",
            command=lambda: self._close_result(window),
        ).pack(side=tk.RIGHT)

    def _center_over_root(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        width = max(window.winfo_reqwidth(), self._px(560))
        height = window.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        window.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    def _close_result(self, window: tk.Toplevel) -> None:
        if window.winfo_exists():
            window.grab_release()
            window.destroy()
        self._prepared = None
        self._busy = False
        self.student_combo.set("")
        if self._students:
            self._set_hint("Билет выдан. Выберите следующего студента.", "muted")
        self._update_button()
        self.root.focus_set()
