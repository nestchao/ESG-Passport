"""Validated API inputs. Source and calculated quantities never use binary floats."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

Period = Annotated[str, Field(pattern=r'^([0-9]{3}[1-9]|[0-9]{2}[1-9][0-9]|[0-9][1-9][0-9]{2}|[1-9][0-9]{3})-(0[1-9]|1[0-2])$')]
Code = Literal['E1.1', 'E1.2', 'E2.1', 'E3.1', 'E4.1', 'S1.1', 'S4.1', 'G1.1', 'G2.1', 'G3.1', 'G4.1']
Category = Literal['electricity', 'diesel', 'petrol', 'water', 'waste_generated', 'waste_diverted', 'waste_disposed']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ActivityInput(Input):
    category: Category
    quantity: Decimal = Field(ge=0, max_digits=30, decimal_places=12, allow_inf_nan=False)
    unit: Literal['kWh', 'L', 'm3', 'kg', 't']
    period_start: date
    period_end: date
    estimated: StrictBool = False
    allocated_period: Period | None = None
    assumptions: str = Field(default='', max_length=4000)
    source_reference: str = Field(default='', max_length=1000)
    # Displayed attribution is accepted for round trips, but never trusted when saving.
    confirmed_by: str | None = None
    confirmed_at: str | None = None
    revision: int | None = None
    id: str | None = None

    @field_validator('quantity', mode='before')
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError('Enter a numeric quantity, not a boolean.')
        return value


class ActivitiesInput(Input):
    expected_version: int | None = Field(default=None, ge=1)
    confirmed: StrictBool
    activities: list[ActivityInput] = Field(min_length=1, max_length=20)


class DeclarationInput(Input):
    period: Period = '2026-09'
    answer: dict
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class QuestionnaireInput(Input):
    customer: str = Field(min_length=1, max_length=255)
    period: Period = '2026-09'
    due_date: date | None = None
    questions: list[Annotated[str, Field(min_length=1, max_length=4000)]] = Field(min_length=1, max_length=100)


class ReviewInput(Input):
    codes: list[Code] = Field(max_length=11)
    reviewed: StrictBool
    manual_answer: str | None = Field(default=None, max_length=10000)


class HandoffInput(Input):
    status: Literal['ready_for_owner']


class ApprovalInput(Input):
    version: int = Field(ge=1)
    recipient: str = Field(min_length=1, max_length=255)
    selected_evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class RecalculateInput(Input):
    period: Period = '2026-09'


class DocumentUpdateInput(Input):
    type: Literal['electricity', 'diesel', 'petrol', 'water', 'waste'] | None = None
    name: str = Field(min_length=1, max_length=255)
    period: Period
    activities: list[ActivityInput] = Field(max_length=20)
    expected_version: int = Field(ge=1)


class DocumentVersionInput(Input):
    expected_version: int = Field(ge=1)
