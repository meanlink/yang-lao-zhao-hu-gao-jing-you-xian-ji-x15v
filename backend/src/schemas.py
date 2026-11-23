from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictBool


class Role(StrEnum):
    CARER = 'carer'
    LEAD = 'lead'
    RECEIVER = 'receiver'


class AlertStatus(StrEnum):
    EVALUATING = 'evaluating'
    INCOMPLETE = 'incomplete'
    REVIEW = 'review'
    CONFIRMED = 'confirmed'
    HANDOVER = 'handover'
    CLOSED = 'closed'


class Priority(IntEnum):
    ROUTINE = 1
    PROMPT = 2
    FIRST = 3


class Shift(StrEnum):
    DAY = 'day'
    SWING = 'swing'
    NIGHT = 'night'


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=600)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(Input):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=128)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class Resident(Input):
    code: Annotated[str, StringConstraints(pattern=r'^ZH-[0-9]{3}$')]
    name: ShortText
    room: ShortText
    unit: ShortText
    care_plan: Note


class Signals(Input):
    missed_round: StrictBool | None = None
    repeated_call: StrictBool | None = None
    transfer_support: StrictBool | None = None
    unfinished_task: StrictBool | None = None


FEATURES = tuple(Signals.model_fields)


class NewObservation(Signals):
    ref: Annotated[str, StringConstraints(pattern=r'^[A-Z0-9][A-Z0-9-]{4,39}$')]
    resident_id: int = Field(gt=0)
    author_note: Note


class Revision(Input):
    revision: int = Field(ge=1)


class Review(Revision):
    priority: Priority
    note: Note


class Handover(Revision):
    target_shift: Shift
    next_action: Note


class Receipt(Input):
    receipt_note: Note
