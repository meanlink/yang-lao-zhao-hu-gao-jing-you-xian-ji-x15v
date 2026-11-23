from typing import Literal

from pydantic import Field

from .schemas import Input, Note, Shift, ShortText


class StartCoverage(Input):
    unit: ShortText
    carer_id: int = Field(gt=0)
    shift: Shift
    duration_minutes: Literal[60, 120, 240, 480]
    capacity: int = Field(ge=1, le=5)


class EndCoverage(Input):
    reason: Note
