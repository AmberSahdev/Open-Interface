from typing import Any

from prompting.common import format_block
from prompting.common import normalize_multiline_text
from prompting.common import summarize_parameters
from prompting.constants import MAX_REASON_CHARS
from prompting.constants import MAX_RECENT_DETAIL_COUNT


def build_recent_details(request_context: dict[str, Any] | None) -> str:
    lines = []
    step_history = _read_recent_step_history(request_context)

    if len(step_history) == 0:
        lines.append('No recent detailed steps yet.')
        return format_block('PromptRecentDetails', lines)

    for step in step_history:
        step_index = int(step.get('step_index') or 0)
        lines.append(f'Step {step_index}:')
        lines.append(f'- function: {str(step.get("function") or "unknown").strip()}')
        lines.append(f'- parameters: {summarize_parameters(step.get("parameters"), max_length=140)}')
        lines.append(
            f'- justification: {normalize_multiline_text(step.get("human_readable_justification"), MAX_REASON_CHARS)}'
        )
        lines.append(
            f'- expected_outcome: {normalize_multiline_text(step.get("expected_outcome"), MAX_REASON_CHARS)}'
        )
        lines.append(f'- execution_status: {str(step.get("execution_status") or "unknown").strip()}')
        lines.append(f'- verification_status: {str(step.get("verification_status") or "unknown").strip()}')
        verification_reason = normalize_multiline_text(step.get('verification_reason'), MAX_REASON_CHARS)
        if verification_reason != '':
            lines.append(f'- verification_reason: {verification_reason}')
        error_message = normalize_multiline_text(step.get('error_message'), MAX_REASON_CHARS)
        if error_message != '':
            lines.append(f'- error_message: {error_message}')

    return format_block('PromptRecentDetails', lines)


def _read_recent_step_history(request_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(request_context, dict):
        return []

    step_history = request_context.get('step_history')
    if not isinstance(step_history, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in step_history[-MAX_RECENT_DETAIL_COUNT:]:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized
