from datetime import datetime
from pathlib import Path

from prompting.builder import PromptPackage


PROMPT_DUMP_DIR_NAME = 'promptdump'


def maybe_dump_prompt_package(prompt_package: PromptPackage, enabled: bool) -> str | None:
    if not enabled:
        return None

    dump_directory = _get_prompt_dump_directory()
    dump_directory.mkdir(parents=True, exist_ok=True)
    dump_path = _build_dump_path(dump_directory, prompt_package)
    dump_path.write_text(prompt_package.debug_text, encoding='utf-8')
    return str(dump_path)


def _get_prompt_dump_directory() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / PROMPT_DUMP_DIR_NAME


def _build_dump_path(dump_directory: Path, prompt_package: PromptPackage) -> Path:
    timestamp_text = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    request_id = str(prompt_package.metadata.get('request_id') or 'request').replace('/', '_')
    step_num = int(prompt_package.metadata.get('step_num') or 0)
    filename = f'{timestamp_text}_{request_id}_step{step_num}.txt'
    return dump_directory / filename
