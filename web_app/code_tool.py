import glob
import os
import shutil
import subprocess  # noqa: S404
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from config import SANDBOX_IMAGE
from langchain_core.tools import Tool
from pydantic import BaseModel, Field


def run_code_in_docker_with_cleanup(
    code: str, df: pd.DataFrame | None = None
) -> dict[str, Any]:
    """
    Запускает Python-код в изолированном Docker sandbox.

    Returns:
        dict[str, Any]

    """
    base_tmp = tempfile.mkdtemp(prefix="ai_analyst_", dir="/tmp")
    input_dir = Path(base_tmp) / "input"
    output_dir = Path(base_tmp) / "output"

    Path(input_dir).mkdir(exist_ok=True, parents=True)
    Path(output_dir).mkdir(exist_ok=True, parents=True)

    # DataFrame
    if df is not None:
        df.to_pickle(Path(input_dir) / "df.pkl")
        df_setup = "import pandas as pd\ndf = pd.read_pickle('/sandbox/input/df.pkl')\n"
    else:
        df_setup = ""

    img_code_settings = """import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import uuid as _uuid
import warnings
warnings.filterwarnings('ignore')

def _auto_save(*args, **kw):
    _path = '/sandbox/output/plot_' + _uuid.uuid4().hex[:8] + '.png'
    plt.savefig(_path, bbox_inches='tight', dpi=150)
    plt.close('all')

plt.show = _auto_save
"""

    script_path = Path(input_dir) / "script.py"
    full_script = df_setup + img_code_settings + "\n" + code

    Path(script_path).write_text(full_script, encoding="utf-8")

    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--memory=512m",
                "--cpus=0.5",
                "--security-opt=no-new-privileges",
                "--cap-drop=ALL",
                "-v",
                f"{input_dir}:/sandbox/input:ro",
                "-v",
                f"{output_dir}:/sandbox/output:rw",
                SANDBOX_IMAGE,
                "python",
                "/sandbox/input/script.py",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )  # type: ignore  # noqa: PGH003
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(base_tmp, ignore_errors=True)
        return {
            "stdout": "",
            "stderr": f"Ошибка Docker: {e}",
            "returncode": -1,
            "images": {},
        }

    images: dict[str, bytes] = {}
    for img_file in sorted(glob.glob(os.path.join(output_dir, "*.png"))):  # noqa: PTH118, PTH207
        try:  # noqa: SIM105
            images[Path(img_file).name] = Path(img_file).read_bytes()
        except Exception:  # noqa: BLE001, S110
            pass

    shutil.rmtree(base_tmp, ignore_errors=True)

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "images": images,
    }


class PythonReplInput(BaseModel):
    """Схема аргументов для tool."""

    code: str = Field(description="Python-код для выполнения в sandbox")


class DockerReplTool:
    """Tool для выполнения python кода в Docker."""

    def __init__(self) -> None:
        """Инициализация класса."""
        self.all_images: list[bytes] = []
        self.all_tool_outputs: list[str] = []
        self.df: pd.DataFrame | None = None

    def run(self, code: str) -> str:
        """
        Запуск код в Docker.

        Returns:
            str

        """
        if self.df is None:
            return "ОШИБКА: DataFrame не загружен. Загрузите файл CSV или Excel."

        res = run_code_in_docker_with_cleanup(code, self.df)

        for img_bytes in res["images"].values():
            self.all_images.append(img_bytes)

        output = res["stdout"].strip()
        if res["stderr"].strip():
            output += f"\nSTDERR:\n{res['stderr'].strip()}"
        if res["returncode"] != 0 and not output:
            output = f"Код завершился с кодом {res['returncode']}"  # noqa: RUF001
        if res["images"]:
            output += f"\n[Сгенерировано графиков: {len(res['images'])}]"

        result_str = output or "(нет вывода)"
        self.all_tool_outputs.append(result_str)
        return result_str

    def reset_for_new_query(self) -> None:
        """Сброс данных старого запроса."""  # noqa: RUF002
        self.all_images.clear()
        self.all_tool_outputs.clear()


def make_repl_tool() -> DockerReplTool:
    """
    Функция для создания tool.

    Returns:
        DockerReplTool

    """
    tool_instance = DockerReplTool()

    tool_instance.tool = Tool(  # type: ignore  # noqa: PGH003
        name="python_repl",
        description=(
            "Выполняет Python-код в изолированном Docker-контейнере. "
            "DataFrame с данными уже доступен как переменная df. "  # noqa: RUF001
            "Для графиков используй plt.show(), файл сохранится автоматически. "
            "НЕ вызывай plt.savefig() самостоятельно."  # noqa: RUF001
        ),
        func=tool_instance.run,
        args_schema=PythonReplInput,
    )
    return tool_instance
