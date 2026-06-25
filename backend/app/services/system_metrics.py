from __future__ import annotations

import json
import subprocess
import ctypes
import time
from pathlib import Path
from typing import Any


def collect_system_metrics() -> dict[str, Any]:
    """Collect lightweight local resource metrics for the processing dialog."""
    return {
        "cpu": _cpu_metrics(),
        "memory": _memory_metrics(),
        "gpu": _gpu_metrics(),
    }


def _cpu_metrics() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        percent = psutil.cpu_percent(interval=0.1)
        return {"available": True, "percent": round(float(percent), 1)}
    except Exception:
        return _cpu_metrics_windows_fallback()


def _memory_metrics() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        memory = psutil.virtual_memory()
        used_gb = (memory.total - memory.available) / (1024**3)
        total_gb = memory.total / (1024**3)
        return {
            "available": True,
            "percent": round(float(memory.percent), 1),
            "used_gb": round(used_gb, 1),
            "total_gb": round(total_gb, 1),
        }
    except Exception:
        return _memory_metrics_windows_fallback()


def _cpu_metrics_windows_fallback() -> dict[str, Any]:
    native = _cpu_metrics_windows_native()
    if native["available"]:
        return native
    try:
        completed = subprocess.run(
            ["wmic", "cpu", "get", "loadpercentage", "/value"],
            capture_output=True,
            check=True,
            text=True,
            timeout=1.5,
        )
        values: list[float] = []
        for line in completed.stdout.splitlines():
            if line.lower().startswith("loadpercentage="):
                values.append(float(line.split("=", 1)[1].strip()))
        if values:
            return {"available": True, "percent": round(sum(values) / len(values), 1)}
    except Exception:
        pass
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        percent = float(completed.stdout.strip().replace(",", "."))
        return {"available": True, "percent": round(percent, 1)}
    except Exception:
        pass
    return {"available": False, "percent": None}


def _memory_metrics_windows_fallback() -> dict[str, Any]:
    native = _memory_metrics_windows_native()
    if native["available"]:
        return native
    try:
        completed = subprocess.run(
            ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"],
            capture_output=True,
            check=True,
            text=True,
            timeout=1.5,
        )
        values: dict[str, float] = {}
        for line in completed.stdout.splitlines():
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            raw_value = raw_value.strip()
            if raw_value:
                values[key.strip()] = float(raw_value)
        total_kb = values.get("TotalVisibleMemorySize")
        free_kb = values.get("FreePhysicalMemory")
        if total_kb and free_kb is not None:
            used_kb = total_kb - free_kb
            return {
                "available": True,
                "percent": round((used_kb / total_kb) * 100, 1),
                "used_gb": round(used_kb / (1024**2), 1),
                "total_gb": round(total_kb / (1024**2), 1),
            }
    except Exception:
        pass
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        payload = json.loads(completed.stdout)
        total_kb = float(payload["TotalVisibleMemorySize"])
        free_kb = float(payload["FreePhysicalMemory"])
        used_kb = total_kb - free_kb
        return {
            "available": True,
            "percent": round((used_kb / total_kb) * 100, 1),
            "used_gb": round(used_kb / (1024**2), 1),
            "total_gb": round(total_kb / (1024**2), 1),
        }
    except Exception:
        pass
    return {"available": False, "percent": None, "used_gb": None, "total_gb": None}


def _cpu_metrics_windows_native() -> dict[str, Any]:
    class FileTime(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

    def to_int(value: FileTime) -> int:
        return (value.dwHighDateTime << 32) + value.dwLowDateTime

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        idle_a = FileTime()
        kernel_a = FileTime()
        user_a = FileTime()
        idle_b = FileTime()
        kernel_b = FileTime()
        user_b = FileTime()
        if not kernel32.GetSystemTimes(ctypes.byref(idle_a), ctypes.byref(kernel_a), ctypes.byref(user_a)):
            return {"available": False, "percent": None}
        time.sleep(0.1)
        if not kernel32.GetSystemTimes(ctypes.byref(idle_b), ctypes.byref(kernel_b), ctypes.byref(user_b)):
            return {"available": False, "percent": None}
        idle_delta = to_int(idle_b) - to_int(idle_a)
        total_delta = (to_int(kernel_b) - to_int(kernel_a)) + (to_int(user_b) - to_int(user_a))
        if total_delta <= 0:
            return {"available": False, "percent": None}
        percent = max(0.0, min(100.0, (1.0 - (idle_delta / total_delta)) * 100))
        return {"available": True, "percent": round(percent, 1)}
    except Exception:
        return {"available": False, "percent": None}


def _memory_metrics_windows_native() -> dict[str, Any]:
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {"available": False, "percent": None, "used_gb": None, "total_gb": None}
        used = status.ullTotalPhys - status.ullAvailPhys
        return {
            "available": True,
            "percent": round(float(status.dwMemoryLoad), 1),
            "used_gb": round(used / (1024**3), 1),
            "total_gb": round(status.ullTotalPhys / (1024**3), 1),
        }
    except Exception:
        return {"available": False, "percent": None, "used_gb": None, "total_gb": None}


def _gpu_metrics() -> dict[str, Any]:
    nvidia = _gpu_metrics_nvidia_smi()
    if nvidia["available"]:
        return nvidia

    windows = _gpu_metrics_windows_counters()
    if windows["available"]:
        return windows

    video = _gpu_video_controller_fallback()
    if video["available"]:
        return video

    return {
        "available": False,
        "label": "GPU nao detectada",
        "percent": None,
        "memory_used_gb": None,
        "memory_total_gb": None,
        "source": "unavailable",
    }


def _gpu_metrics_nvidia_smi() -> dict[str, Any]:
    nvidia_smi = _find_nvidia_smi()
    if not nvidia_smi:
        return {
            "available": False,
            "label": "NVIDIA SMI nao encontrado",
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "nvidia-smi",
        }

    try:
        completed = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=1.5,
        )
    except Exception:
        return {
            "available": False,
            "label": "NVIDIA SMI indisponivel",
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "nvidia-smi",
        }

    first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
    parts = [part.strip() for part in first_line.split(",")]
    if len(parts) < 4:
        return {
            "available": False,
            "label": "NVIDIA SMI sem leitura valida",
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "nvidia-smi",
        }

    name, percent, used_mb, total_mb = parts[:4]
    try:
        used_gb = float(used_mb) / 1024
        total_gb = float(total_mb) / 1024
        return {
            "available": True,
            "label": name,
            "percent": round(float(percent), 1),
            "memory_used_gb": round(used_gb, 1),
            "memory_total_gb": round(total_gb, 1),
            "source": "nvidia-smi",
        }
    except ValueError:
        return {
            "available": False,
            "label": "NVIDIA SMI sem leitura numerica",
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "nvidia-smi",
        }


def _find_nvidia_smi() -> str | None:
    direct = shutil_which("nvidia-smi")
    if direct:
        return direct

    candidates = [
        Path("C:/Program Files/NVIDIA Corporation/NVSMI/nvidia-smi.exe"),
        Path("C:/Windows/System32/nvidia-smi.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def shutil_which(command: str) -> str | None:
    try:
        import shutil

        return shutil.which(command)
    except Exception:
        return None


def _gpu_metrics_windows_counters() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$samples = (Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
                    "-ErrorAction Stop).CounterSamples; "
                    "$sum = ($samples | Measure-Object -Property CookedValue -Sum).Sum; "
                    "$gpu = Get-CimInstance Win32_VideoController | "
                    "Where-Object { $_.Name -and $_.Name -notmatch 'Basic Display' } | "
                    "Select-Object -First 1 Name,AdapterRAM; "
                    "[pscustomobject]@{Percent=$sum;Name=$gpu.Name;AdapterRAM=$gpu.AdapterRAM} | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=3,
        )
        payload = json.loads(completed.stdout.strip() or "{}")
        percent_raw = payload.get("Percent")
        label = str(payload.get("Name") or "GPU detectada")
        percent = 0.0 if percent_raw in (None, "") else float(str(percent_raw).replace(",", "."))
        total_gb = _adapter_ram_to_gb(payload.get("AdapterRAM"))
        return {
            "available": True,
            "label": label,
            "percent": round(max(0.0, min(100.0, percent)), 1),
            "memory_used_gb": None,
            "memory_total_gb": total_gb,
            "source": "windows-performance-counter",
        }
    except Exception:
        return {
            "available": False,
            "label": "Contador de GPU indisponivel",
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "windows-performance-counter",
        }


def _gpu_video_controller_fallback() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_VideoController | "
                    "Where-Object { $_.Name -and $_.Name -notmatch 'Basic Display' } | "
                    "Select-Object -First 1 Name,AdapterRAM | ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        payload = json.loads(completed.stdout.strip() or "{}")
        label = payload.get("Name")
        if not label:
            raise ValueError("GPU name not available")
        return {
            "available": True,
            "label": str(label),
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": _adapter_ram_to_gb(payload.get("AdapterRAM")),
            "source": "win32-video-controller",
        }
    except Exception:
        return {
            "available": False,
            "label": "GPU nao detectada",
            "percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "win32-video-controller",
        }


def _adapter_ram_to_gb(value: Any) -> float | None:
    try:
        raw = float(value)
        if raw <= 0:
            return None
        return round(raw / (1024**3), 1)
    except Exception:
        return None
