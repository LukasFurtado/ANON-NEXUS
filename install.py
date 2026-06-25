import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    print("INSTALADOR LOCAL - NEXUS ANON\n")
    print("Este assistente prepara dependencias do backend e frontend.")
    print("O Ollama e o modelo qwen3:32b devem existir no computador antes do uso institucional.\n")

    if sys.version_info < (3, 10):
        print("Python 3.10 ou superior e necessario.")
        return 1
    if not shutil.which("npm"):
        print("Node.js/npm nao encontrado. Instale o Node.js LTS e execute novamente.")
        return 1

    backend = ROOT / "backend"
    frontend = ROOT / "frontend"
    venv = backend / ".venv"
    python_exe = venv / "Scripts" / "python.exe"

    _run([sys.executable, "-m", "venv", str(venv)], "Criando ambiente local Python")
    _run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], "Atualizando pip")
    _run([str(python_exe), "-m", "pip", "install", "-r", str(backend / "requirements.txt")], "Instalando dependencias Python")
    _run(["npm", "install"], "Instalando dependencias da interface", cwd=frontend)

    if shutil.which("ollama"):
        print("\nOllama detectado.")
        print("Modelo padrao do ANON: qwen3:32b.")
        print("A especializacao institucional e aplicada pelos prompts, perfis JSON, validador e corretor de JSON do ANON.")
    else:
        print("\nOllama nao encontrado. Instale o Ollama e baixe qwen3:32b antes do uso.")

    print("\nInstalacao local concluida. Use scripts/start-nexus-anon.ps1 ou os atalhos do pacote.")
    return 0


def _run(command: list[str], label: str, cwd: Path | None = None) -> None:
    print(f"\n> {label}")
    subprocess.run(command, cwd=str(cwd or ROOT), check=True)


if __name__ == "__main__":
    raise SystemExit(main())
