from typing import Literal

from pydantic import Field, model_validator

from .schemas import Input, Note


class CheckPlanItem(Input):
    kind: Literal['room_round', 'call_log', 'transfer_assistance', 'task_receipt', 'handover_note']
    instruction: Note


class CheckPlan(Input):
    items: list[CheckPlanItem] = Field(min_length=1, max_length=5)

    @model_validator(mode='after')
    def unique_kinds(self):
        if len({item.kind for item in self.items}) != len(self.items):
            raise ValueError('每种核对项目只能选择一次')
        return self


class CheckRetry(Input):
    version: int = Field(gt=0)
    note: Note


class CheckResult(CheckRetry):
    outcome: Literal['verified', 'blocked']
