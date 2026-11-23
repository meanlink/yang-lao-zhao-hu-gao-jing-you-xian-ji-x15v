from typing import Annotated

from pydantic import StringConstraints

from .schemas import Input, Note, ShortText


class NewModelVersion(Input):
    label: ShortText
    corpus: Annotated[str, StringConstraints(min_length=10, max_length=100_000)]


class NewTrialRun(Input):
    note: Note | None = None
