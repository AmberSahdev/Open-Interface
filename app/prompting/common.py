import json
from typing import Any

from prompting.constants import MAX_PARAMETER_CHARS


ALLOWED_PARAMETER_KEYS = {
    'target_anchor_id',
    'x_percent',
    'y_percent',
    'x',
    'y',
    'button',
    'clicks',
    'key',
    'keys',
    'string',
    'text',
    'secs',
    'duration',
    'interval',
    'presses',
}


def truncate_text(value: Any, max_length: int) -> str:
    text = str(value or '').strip()
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return text[:max_length - 3] + '...'


def normalize_multiline_text(value: Any, max_length: int) -> str:
    text = str(value or '').replace('\n', ' ').strip()
    return truncate_text(text, max_length)


def summarize_parameters(parameters: Any, max_length: int = MAX_PARAMETER_CHARS) -> str:
    if not isinstance(parameters, dict) or len(parameters) == 0:
        return '{}'

    summary: dict[str, Any] = {}
    for key, value in parameters.items():
        if key not in ALLOWED_PARAMETER_KEYS:
            continue
        summary[key] = value

    if len(summary) == 0:
        return '{}'

    serialized = json.dumps(summary, ensure_ascii=False, separators=(', ', ': '))
    return truncate_text(serialized, max_length)


def format_block(title: str, lines: list[str]) -> str:
    content = '\n'.join(line for line in lines if line != '')
    return f'[{title}]\n{content}'.strip()
