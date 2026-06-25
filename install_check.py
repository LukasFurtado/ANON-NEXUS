import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    checks = [
        ("Python", _python_ok()),
        ("Node.js", _command_ok(["node", "--version"])),
        ("npm", _command_ok(["npm", "--version"])),
        ("Ollama", _command_ok(["ollama", "--version"])),
        ("Backend", (ROOT / "backend" / "requirements.txt").exists()),
        ("Frontend", (ROOT / "frontend" / "package.json").exists()),
    ]
    print("VERIFICACAO DO AMBIENTE NEXUS ANON\n")
    failed = False
    for label, ok in checks:
        status = "OK" if ok else "PENDENTE"
        print(f"[{status}] {label}")
        failed = failed or not ok

    models = _ollama_models()
    if models:
        print("\nModelos Ollama detectados:")
        for model in models:
            print(f"- {model}")
        if "qwen3:32b" not in models:
            print("\nPENDENTE: qwen3:32b nao foi encontrado. Execute: ollama pull qwen3:32b")
            failed = True
    else:
        print("\nNenhum modelo Ollama foi detectado. Abra o Ollama antes de iniciar o ANON.")
        failed = True

    if failed:
        print("\nHa pendencias. Consulte o tutorial HTML de instalacao antes de executar o programa.")
        return 1
    print("\nAmbiente basico pronto para executar o ANON.")
    return 0


def _python_ok() -> bool:
    return sys.version_info >= (3, 10)


def _command_ok(command: list[str]) -> bool:
    if not shutil.which(command[0]):
        return False
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=10)
        return True
    except Exception:
        return False


def _ollama_models() -> list[str]:
    if not shutil.which("ollama"):
        return []
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True, timeout=15)
    except Exception:
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) <= 1:
        return []
    return [line.split()[0] for line in lines[1:] if line.split()]


if __name__ == "__main__":
    raise SystemExit(main())
