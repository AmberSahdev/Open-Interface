from typing import Any

from prompting.common import format_block
from prompting.common import normalize_multiline_text
from prompting.common import summarize_parameters
from prompting.constants import MAX_REASON_CHARS


def build_execution_timeline(request_context: dict[str, Any] | None) -> str:
    lines = ['Full Step Timeline:']

    step_history = _read_step_history(request_context)
    if len(step_history) == 0:
        lines.append('- No steps executed yet.')
        return format_block('PromptExecutionTimeline', lines)

    for step in step_history:
        lines.append(_build_timeline_line(step))

    return format_block('PromptExecutionTimeline', lines)


def _read_step_history(request_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(request_context, dict):
        return []

    step_history = request_context.get('step_history')
    if not isinstance(step_history, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in step_history:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def _build_timeline_line(step: dict[str, Any]) -> str:
    step_index = int(step.get('step_index') or 0)
    function_name = str(step.get('function') or 'unknown').strip()
    parameters = summarize_parameters(step.get('parameters'))
    execution_status = str(step.get('execution_status') or 'unknown').strip()
    verification_status = str(step.get('verification_status') or 'unknown').strip()
    reason = _build_timeline_reason(step)

    return (
        f'- Step {step_index}: {function_name} {parameters} | '
        f'execution={execution_status} | verification={verification_status} | reason={reason}'
    )


def _build_timeline_reason(step: dict[str, Any]) -> str:
    if str(step.get('execution_status') or '').strip() == 'failed':
        error_message = normalize_multiline_text(step.get('error_message'), MAX_REASON_CHARS)
        if error_message != '':
            return error_message

    verification_reason = normalize_multiline_text(step.get('verification_reason'), MAX_REASON_CHARS)
    if verification_reason != '':
        return verification_reason

    justification = normalize_multiline_text(step.get('human_readable_justification'), MAX_REASON_CHARS)
    if justification != '':
        return justification

    expected_outcome = normalize_multiline_text(step.get('expected_outcome'), MAX_REASON_CHARS)
    if expected_outcome != '':
        return expected_outcome

    return 'none'
