import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

from models import PreparedAssignment, Student
from ports import ResultsRepository


logger = logging.getLogger(__name__)
RESULT_HEADERS = ("Группа", "Фамилия", "Имя", "Номер билета", "Дата и время", "Повтор (да/нет)")
DATE_FORMAT = "dd.mm.yyyy hh:mm:ss"


class RepositoryError(Exception):
    """The results journal cannot be read or safely written."""


class ExcelResultsRepository(ResultsRepository):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._ensure_file()

    def history(self) -> tuple[PreparedAssignment, ...]:
        workbook = self._open_validated()
        try:
            worksheet = workbook.active
            assignments = []
            for row in worksheet.iter_rows(min_row=2, max_col=6, values_only=True):
                if all(value is None for value in row):
                    continue
                if not all(isinstance(row[index], str) for index in (0, 1, 2)):
                    raise RepositoryError("В results.xlsx найдена некорректная строка.")
                if not isinstance(row[3], int) or not isinstance(row[4], datetime):
                    raise RepositoryError("В results.xlsx найдена некорректная запись.")
                assignments.append(
                    PreparedAssignment(
                        student=Student(row[0], row[1], row[2]),
                        ticket_number=row[3],
                        timestamp=row[4],
                        repeated=row[5] == "да",
                    )
                )
            return tuple(assignments)
        finally:
            workbook.close()

    def append(self, assignment: PreparedAssignment) -> None:
        workbook = self._open_validated()
        temporary_path: Path | None = None
        try:
            worksheet = workbook.active
            worksheet.append(
                (
                    assignment.student.group,
                    assignment.student.last_name,
                    assignment.student.first_name,
                    assignment.ticket_number,
                    assignment.timestamp,
                    "да" if assignment.repeated else "нет",
                )
            )
            worksheet.cell(worksheet.max_row, 5).number_format = DATE_FORMAT
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".results-",
                suffix=".xlsx",
                dir=self._path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            workbook.save(temporary_path)
            workbook.close()
            os.replace(temporary_path, self._path)
            temporary_path = None
        except PermissionError:
            raise
        except Exception as error:
            logger.error("Ошибка сохранения %s", self._path, exc_info=True)
            raise RepositoryError("Не удалось сохранить results.xlsx.") from error
        finally:
            workbook.close()
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    def _ensure_file(self) -> None:
        if self._path.exists():
            self._open_validated().close()
            return
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(RESULT_HEADERS)
        self._set_widths(worksheet)
        self._save_new(workbook)

    def _open_validated(self):
        try:
            workbook = load_workbook(self._path)
        except Exception as error:
            logger.error("Ошибка чтения %s", self._path, exc_info=True)
            raise RepositoryError("results.xlsx поврежден или недоступен.") from error
        headers = tuple(workbook.active.cell(1, column).value for column in range(1, 7))
        if headers != RESULT_HEADERS:
            workbook.close()
            raise RepositoryError("В results.xlsx неверные заголовки.")
        return workbook

    def _save_new(self, workbook) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".results-", suffix=".xlsx", dir=self._path.parent, delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            workbook.save(temporary_path)
            workbook.close()
            os.replace(temporary_path, self._path)
            temporary_path = None
        except Exception as error:
            logger.error("Ошибка создания %s", self._path, exc_info=True)
            raise RepositoryError("Не удалось создать results.xlsx.") from error
        finally:
            workbook.close()
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    @staticmethod
    def _set_widths(worksheet) -> None:
        for column, width in {"A": 22, "B": 22, "C": 22, "D": 16, "E": 24, "F": 16}.items():
            worksheet.column_dimensions[column].width = width
