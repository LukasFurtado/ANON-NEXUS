import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


STATE_DIR = Path("data") / "states"
StageStatus = Literal["running", "ok", "warn", "fail"]


@dataclass
class _StageRecord:
    name: str
    status: StageStatus
    started_at: float
    duration_ms: int = 0
    note: str = ""


class PipelineStateEmitter:
    def __init__(self, pipeline_id: str) -> None:
        self.pipeline_id = pipeline_id
        self.started_at = datetime.now(timezone.utc)
        self._start_perf = time.perf_counter()
        self._stages: list[_StageRecord] = []
        self._active: dict[str, _StageRecord] = {}
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._persist(self._snapshot(finished=False))

    def stage_start(self, stage: str, input_summary: str = "") -> None:
        record = _StageRecord(name=stage, status="running", started_at=time.perf_counter(), note=input_summary)
        self._active[stage] = record
        self._upsert(record)

    def stage_ok(self, stage: str, output_summary: str = "") -> None:
        self._finish(stage, "ok", output_summary)

    def stage_warn(self, stage: str, message: str) -> None:
        self._finish(stage, "warn", message)

    def stage_fail(self, stage: str, error: str) -> None:
        self._finish(stage, "fail", error)

    def finalize(self) -> dict:
        for stage in list(self._active):
            self.stage_warn(stage, "Etapa encerrada sem confirmação explícita.")
        payload = self._snapshot(finished=True)
        self._persist(payload)
        return payload

    def _finish(self, stage: str, status: StageStatus, note: str) -> None:
        record = self._active.pop(stage, _StageRecord(stage, "running", time.perf_counter()))
        record.status = status
        record.duration_ms = int((time.perf_counter() - record.started_at) * 1000)
        record.note = note
        self._upsert(record)
        self._persist(self._snapshot(finished=False))

    def _upsert(self, record: _StageRecord) -> None:
        self._stages = [item for item in self._stages if item.name != record.name]
        self._stages.append(record)

    def _snapshot(self, finished: bool) -> dict:
        statuses = [stage.status for stage in self._stages]
        overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses or "running" in statuses else "ok"
        return {
            "pipeline_id": self.pipeline_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat() if finished else None,
            "stages": [
                {"name": stage.name, "status": stage.status, "duration_ms": stage.duration_ms, "note": stage.note}
                for stage in self._stages
            ],
            "overall_status": overall,
            "total_duration_ms": int((time.perf_counter() - self._start_perf) * 1000),
        }

    def _persist(self, payload: dict) -> None:
        path = STATE_DIR / f"{self.pipeline_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_pipeline_state(pipeline_id: str) -> dict | None:
    path = STATE_DIR / f"{pipeline_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
