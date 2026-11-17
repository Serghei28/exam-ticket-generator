from collections.abc import Sequence
from datetime import datetime
from typing import Callable, Protocol

from models import PreparedAssignment, Student, Ticket


class StudentProvider(Protocol):
    def groups(self) -> tuple[str, ...]:
        ...

    def students(self, group: str) -> tuple[Student, ...]:
        ...


class TicketProvider(Protocol):
    def tickets(self) -> tuple[Ticket, ...]:
        ...

    def get_ticket(self, number: int) -> Ticket | None:
        ...


class ResultsRepository(Protocol):
    def history(self) -> tuple[PreparedAssignment, ...]:
        """Returns rows in append order; failed append leaves history unchanged."""
        ...

    def append(self, assignment: PreparedAssignment) -> None:
        """Appends one row or raises without changing persisted history."""
        ...


TicketSelector = Callable[[Sequence[Ticket]], Ticket]
Clock = Callable[[], datetime]
