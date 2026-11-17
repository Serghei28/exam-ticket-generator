from collections.abc import Sequence
from datetime import datetime
import random

from models import PreparedAssignment, Student, Ticket
from ports import Clock, ResultsRepository, StudentProvider, TicketProvider, TicketSelector


class AssignmentError(Exception):
    """The selected student cannot receive a ticket."""


def choose_random_ticket(tickets: Sequence[Ticket]) -> Ticket:
    return random.choice(tickets)


class AssignmentService:
    def __init__(
        self,
        ticket_provider: TicketProvider,
        results_repository: ResultsRepository,
        ticket_selector: TicketSelector = choose_random_ticket,
        clock: Clock = datetime.now,
    ) -> None:
        self._ticket_provider = ticket_provider
        self._results_repository = results_repository
        self._ticket_selector = ticket_selector
        self._clock = clock

    def prepare(self, student: Student) -> PreparedAssignment:
        history = self._results_repository.history()
        for previous in history:
            if previous.student == student:
                if self._ticket_provider.get_ticket(previous.ticket_number) is None:
                    raise AssignmentError(
                        f"Билет № {previous.ticket_number} больше отсутствует "
                        "в tickets.docx; назначение невозможно."
                    )
                return PreparedAssignment(
                    student,
                    previous.ticket_number,
                    self._clock(),
                    True,
                )

        tickets = self._ticket_provider.tickets()
        if not tickets:
            raise AssignmentError("Нет корректных билетов для назначения.")
        selected = self._ticket_selector(tickets)
        return PreparedAssignment(student, selected.number, self._clock(), False)

    def persist(self, assignment: PreparedAssignment) -> None:
        self._results_repository.append(assignment)


def students_for_group(provider: StudentProvider, group: str) -> tuple[Student, ...]:
    return provider.students(group)
