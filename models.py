from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Student:
    group: str
    last_name: str
    first_name: str

    @property
    def display_name(self) -> str:
        return f"{self.last_name} {self.first_name}"


@dataclass(frozen=True)
class Ticket:
    number: int
    questions: tuple[str, str, str]


@dataclass(frozen=True)
class PreparedAssignment:
    student: Student
    ticket_number: int
    timestamp: datetime
    repeated: bool
