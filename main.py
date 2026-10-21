from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import msvcrt

from journal import (
    ExcelJournalWriter,
    JournalError,
    JournalWriter,
    TicketGenerator,
    append_record,
    generate_ticket,
)


JOURNAL_PATH = Path(__file__).resolve().with_name("journal.xlsx")


def read_name(prompt: str, getch: Callable[[], str] = msvcrt.getwch) -> Optional[str]:
    """Читает имя посимвольно и возвращает None при нажатии ESC."""
    while True:
        print(prompt, end="", flush=True)
        characters = []

        while True:
            character = getch()

            if character == "\x1b":
                print()
                return None
            if character in ("\x00", "\xe0"):
                getch()
                continue
            if character in ("\r", "\n"):
                value = "".join(characters).strip()
                print()
                if value:
                    return value
                print("Поле не может быть пустым.")
                break
            if character in ("\b", "\x7f"):
                if characters:
                    characters.pop()
                    print("\b \b", end="", flush=True)
                continue

            characters.append(character)
            print(character, end="", flush=True)


def wait_for_save_retry(getch: Callable[[], str] = msvcrt.getwch) -> bool:
    print("Закройте journal.xlsx в Excel и нажмите Enter для повтора (ESC — выход).")
    while True:
        character = getch()
        if character == "\x1b":
            print()
            return False
        if character in ("\x00", "\xe0"):
            getch()
        elif character in ("\r", "\n"):
            return True


def save_with_retry(
    last_name: str,
    first_name: str,
    ticket_number: int,
    timestamp: datetime,
    writer: JournalWriter | None = None,
) -> bool:
    """Повторяет сохранение той же записи после блокировки Excel."""
    if writer is None:
        writer = _LegacyWriter()

    while True:
        try:
            writer.append_record(
                last_name,
                first_name,
                ticket_number,
                timestamp,
            )
            return True
        except PermissionError:
            print("Не удалось сохранить журнал: файл открыт в Excel.")
            if not wait_for_save_retry():
                print("Запись не сохранена. Программа завершена.")
                return False


class _LegacyWriter:
    """Адаптер для сохранения совместимости с существующим API и тестами."""

    def append_record(
        self,
        last_name: str,
        first_name: str,
        ticket_number: int,
        timestamp: datetime,
    ) -> None:
        append_record(
            JOURNAL_PATH,
            last_name,
            first_name,
            ticket_number,
            timestamp,
        )


def main(
    writer: JournalWriter | None = None,
    ticket_generator: TicketGenerator | None = None,
) -> None:
    print("Для выхода нажмите ESC.")
    configured_writer = writer
    writer = writer or ExcelJournalWriter(JOURNAL_PATH)
    ticket_generator = ticket_generator or _LegacyTicketGenerator()

    while True:
        last_name = read_name("Last name: ")
        if last_name is None:
            return

        first_name = read_name("First name: ")
        if first_name is None:
            return

        ticket_number = ticket_generator.generate()
        timestamp = datetime.now()
        print(f"Билет № {ticket_number}")

        try:
            if configured_writer is None:
                saved = save_with_retry(
                    last_name,
                    first_name,
                    ticket_number,
                    timestamp,
                )
            else:
                saved = save_with_retry(
                    last_name,
                    first_name,
                    ticket_number,
                    timestamp,
                    writer,
                )
        except JournalError as error:
            print(f"Ошибка журнала: {error}")
            return

        if not saved:
            return


class _LegacyTicketGenerator:
    """Адаптер для сохранения совместимости с существующим API и тестами."""

    def generate(self) -> int:
        return generate_ticket()


if __name__ == "__main__":
    main()
