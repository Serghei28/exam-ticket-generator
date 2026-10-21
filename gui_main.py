import logging
from pathlib import Path
import tkinter as tk

from repositories import ExcelResultsRepository
from services import AssignmentService
from sources import DocxTicketProvider, ExcelStudentProvider
from ui import ExamTicketApp


PROJECT_DIR = Path(__file__).resolve().parent


def main() -> None:
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
