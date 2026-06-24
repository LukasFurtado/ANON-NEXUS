from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CommunicationEvent:
    cell: str
    stage: str
    message: str
    level: str = "info"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cell": self.cell,
            "stage": self.stage,
            "level": self.level,
            "message": self.message,
            "data": _safe_public_data(self.data),
        }


class CommunicationTrace:
    def __init__(self) -> None:
        self._events: list[CommunicationEvent] = []

    def emit(self, cell: str, stage: str, message: str, level: str = "info", **data: Any) -> None:
        self._events.append(CommunicationEvent(cell=cell, stage=stage, message=message, level=level, data=data))

    def public_events(self) -> list[dict[str, Any]]:
        return [event.to_public_dict() for event in self._events]

    def summary(self) -> dict[str, Any]:
        levels: dict[str, int] = {}
        cells: dict[str, int] = {}
        for event in self._events:
            levels[event.level] = levels.get(event.level, 0) + 1
            cells[event.cell] = cells.get(event.cell, 0) + 1
        return {
            "events": len(self._events),
            "levels": levels,
            "cells": cells,
            "last_stage": self._events[-1].stage if self._events else None,
        }


def _safe_public_data(data: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in {"text", "original_text", "anonymized_text", "content", "document_content"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [item for item in value[:12] if isinstance(item, (str, int, float, bool))]
        elif isinstance(value, dict):
            safe[key] = {
                str(nested_key): nested_value
                for nested_key, nested_value in value.items()
                if isinstance(nested_value, (str, int, float, bool)) or nested_value is None
            }
    return safe
