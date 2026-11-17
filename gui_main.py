import logging
from pathlib import Path
import tkinter as tk

from repositories import ExcelResultsRepository
from services import AssignmentService
from sources import DocxTicketProvider, ExcelStudentProvider
from ui import ExamTicketApp


PROJECT_DIR = Path(__file__).resolve().parent


def _enable_high_dpi() -> None:
    """Keeps text sharp on scaled Windows displays instead of bitmap-stretched."""
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main() -> None:
    _enable_high_dpi()
    logging.basicConfig(
        filename=PROJECT_DIR / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        students = ExcelStudentProvider(PROJECT_DIR / "students.xlsx")
        tickets = DocxTicketProvider(PROJECT_DIR / "tickets.docx")
        results = ExcelResultsRepository(PROJECT_DIR / "results.xlsx")
    except Exception as error:
        logging.getLogger(__name__).error("Не удалось запустить GUI", exc_info=True)
        root = tk.Tk()
        root.withdraw()
        from tkinter import messagebox

        messagebox.showerror("Ошибка запуска", str(error), parent=root)
        root.destroy()
        return

    root = tk.Tk()
    service = AssignmentService(tickets, results)
    ExamTicketApp(root, students, tickets, service)
    root.mainloop()


if __name__ == "__main__":
    main()
