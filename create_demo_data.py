from pathlib import Path

from docx import Document
from openpyxl import Workbook


PROJECT_DIR = Path(__file__).resolve().parent


def create_students(path: Path) -> None:
    if path.exists():
        print(f"Пропуск: {path.name} уже существует.")
        return
    workbook = Workbook()
    first = workbook.active
    first.title = "Группа А"
    first.append(("Фамилия", "Имя"))
    first.append(("Волков", "Илья"))
    first.append(("Соколова", "Мария"))
    second = workbook.create_sheet("Группа Б")
    second.append(("Фамилия", "Имя"))
    second.append(("Орлов", "Денис"))
    workbook.create_sheet("Пустая группа").append(("Фамилия", "Имя"))
    workbook.save(path)
    workbook.close()


def create_tickets(path: Path) -> None:
    if path.exists():
        print(f"Пропуск: {path.name} уже существует.")
        return
    document = Document()
    questions = (
        ("Что такое алгоритм?", "Назовите свойства хорошего API.", "Объясните роль тестов."),
        ("Что такое класс?", "Сравните список и кортеж.", "Для чего нужна обработка исключений?"),
        ("Что делает SQL-запрос?", "Что такое транзакция?", "Назовите преимущества индексов."),
        ("Что такое HTTP?", "Сравните GET и POST.", "Зачем нужен статус ответа?"),
        ("Что такое Git?", "Для чего нужна ветка?", "Что делает merge?"),
    )
    for number, ticket_questions in enumerate(questions, start=1):
        document.add_paragraph(f"Билет {number}")
        for question_number, question in enumerate(ticket_questions, start=1):
            document.add_paragraph(f"{question_number}. {question}")
    document.save(path)


if __name__ == "__main__":
    create_students(PROJECT_DIR / "students.xlsx")
    create_tickets(PROJECT_DIR / "tickets.docx")
