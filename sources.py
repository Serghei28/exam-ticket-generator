import logging
import re
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from models import Student, Ticket
from ports import StudentProvider, TicketProvider


logger = logging.getLogger(__name__)


class SourceError(Exception):
    """A source file is missing, unreadable, or has an invalid structure."""


class ExcelStudentProvider(StudentProvider):
    def __init__(self, path: Path) -> None:
        self._groups: dict[str, tuple[Student, ...]] = {}
        self._load(path)

    def groups(self) -> tuple[str, ...]:
        return tuple(self._groups)

    def students(self, group: str) -> tuple[Student, ...]:
        return self._groups.get(group, ())

    def _load(self, path: Path) -> None:
        try:
            workbook = load_workbook(path, data_only=True)
        except FileNotFoundError as error:
            logger.error("Не найден файл студентов: %s", path)
            raise SourceError(f"Не найден файл студентов: {path.name}") from error
        except Exception as error:
            logger.error("Не удалось открыть %s", path, exc_info=True)
            raise SourceError(f"Не удалось открыть {path.name}") from error

        try:
            for worksheet in workbook.worksheets:
                group = worksheet.title
                headers = tuple(
                    worksheet.cell(row=1, column=column).value for column in range(1, 3)
                )
                if headers != ("Фамилия", "Имя"):
                    logger.error("Неверные заголовки на листе %s: %s", group, headers)
                    raise SourceError(
                        f"На листе {group} ожидались заголовки «Фамилия» и «Имя»."
                    )
                students: list[Student] = []
                for row_number, row in enumerate(
                    worksheet.iter_rows(min_row=2, max_col=2, values_only=True),
                    start=2,
                ):
                    last_name = str(row[0]).strip() if row[0] is not None else ""
                    first_name = str(row[1]).strip() if row[1] is not None else ""
                    if not last_name and not first_name:
                        continue
                    if not last_name or not first_name:
                        logger.warning(
                            "Пропущена строка %s!%s: отсутствует фамилия или имя",
                            group,
                            row_number,
                        )
                        continue
                    students.append(Student(group, last_name, first_name))
                self._groups[group] = tuple(students)
        finally:
            workbook.close()


_HEADING_RE = re.compile(r"^\s*Билет\s+(\d+)\s*$", re.IGNORECASE)
_HEADING_PREFIX_RE = re.compile(r"^\s*Билет\b", re.IGNORECASE)
_QUESTION_RE = re.compile(r"^\s*([1-3])\.\s+(.+?)\s*$")


class DocxTicketProvider(TicketProvider):
    def __init__(self, path: Path) -> None:
        self._tickets = self._load(path)
        self._by_number = {ticket.number: ticket for ticket in self._tickets}

    def tickets(self) -> tuple[Ticket, ...]:
        return self._tickets

    def get_ticket(self, number: int) -> Ticket | None:
        return self._by_number.get(number)

    def _load(self, path: Path) -> tuple[Ticket, ...]:
        try:
            document = Document(path)
        except FileNotFoundError as error:
            logger.error("Не найден файл билетов: %s", path)
            raise SourceError(f"Не найден файл билетов: {path.name}") from error
        except Exception as error:
            logger.error("Не удалось открыть %s", path, exc_info=True)
            raise SourceError(f"Не удалось открыть {path.name}") from error

        blocks: list[tuple[int | None, list[str], int]] = []
        current: tuple[int | None, list[str], int] | None = None

        for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
            text = paragraph.text.strip()
            if _HEADING_PREFIX_RE.match(text):
                if current is not None:
                    blocks.append(current)
                match = _HEADING_RE.fullmatch(text)
                number = int(match.group(1)) if match else None
                current = (number, [], paragraph_number)
                if number is None:
                    logger.warning("Некорректный заголовок билета в абзаце %s: %s", paragraph_number, text)
                continue
            if current is not None and text:
                current[1].append(text)

        if current is not None:
            blocks.append(current)

        number_counts: dict[int, int] = {}
        for number, _, _ in blocks:
            if number is not None and number > 0:
                number_counts[number] = number_counts.get(number, 0) + 1

        valid: list[Ticket] = []
        for number, paragraphs, paragraph_number in blocks:
            if number is None or number <= 0:
                logger.warning("Пропущен invalid ticket block at paragraph %s", paragraph_number)
                continue
            if number_counts[number] > 1:
                logger.warning("Дубликат номера билета %s: блок исключен", number)
                continue
            questions: dict[int, str] = {}
            invalid = False
            for paragraph in paragraphs:
                match = _QUESTION_RE.fullmatch(paragraph)
                if not match:
                    invalid = True
                    break
                question_number = int(match.group(1))
                question = match.group(2).strip()
                if not question or question_number in questions:
                    invalid = True
                    break
                questions[question_number] = question
            if invalid or set(questions) != {1, 2, 3} or len(paragraphs) != 3:
                logger.warning("Билет %s имеет не ровно три корректных вопроса", number)
                continue
            valid.append(Ticket(number, (questions[1], questions[2], questions[3])))

        if not valid:
            logger.warning("В файле %s не осталось корректных билетов", path)
        return tuple(valid)
