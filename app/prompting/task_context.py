from typing import Any

from prompting.common import format_block
from prompting.common import normalize_multiline_text
from prompting.common import summarize_parameters
from prompting.constants import MAX_INSTALLED_APPS
from prompting.constants import MAX_REASON_CHARS
from prompting.constants import MAX_SESSION_SUMMARY_CHARS


def build_task_context(
    original_user_request: str,
    step_num: int,
    request_context: dict[str, Any] | None,
    machine_profile: dict[str, Any] | None,
) -> str:
    history_lines = _build_session_summary_lines(request_context)
    latest_step = _read_latest_step(request_context)
    blocker_text = _build_blocker_text(request_context, latest_step)
    phase_text = _build_phase_text(step_num, latest_step)
    request_origin = _read_request_origin(request_context)
    boundary_text = _build_request_boundary(step_num, request_context)
    constraints = _build_next_step_constraints(request_context)
    machine_lines = _build_machine_profile_lines(machine_profile)

    lines = [
        f'Task Objective: {str(original_user_request or "").strip()}',
        f'Top Level Request Origin: {request_origin}',
        f'Request Boundary: {boundary_text}',
        f'Current Iteration: {step_num}',
        f'Current Phase: {phase_text}',
        f'Last Step Result: {_build_last_step_result(latest_step)}',
        f'Current Blocker Or Risk: {blocker_text}',
        'Next Step Constraints:',
    ]

    for item in constraints:
        lines.append(f'- {item}')

    lines.append('Session Summary:')
    lines.extend(history_lines)

    if len(machine_lines) > 0:
        lines.append('Machine Profile:')
        lines.extend(machine_lines)

    return format_block('PromptTaskContext', lines)


def _build_session_summary_lines(request_context: dict[str, Any] | None) -> list[str]:
    if not isinstance(request_context, dict):
        return ['- No previous session summary.']

    history_snapshot = request_context.get('session_history_snapshot')
    if not isinstance(history_snapshot, list) or len(history_snapshot) == 0:
        return ['- No previous session summary.']

    lines: list[str] = []
    for message in history_snapshot:
        if not isinstance(message, dict):
            continue
        role = str(message.get('role') or '').strip().lower()
        content = normalize_multiline_text(message.get('content'), MAX_SESSION_SUMMARY_CHARS)
        if content == '':
            continue
        role_label = role.capitalize() if role != '' else 'Unknown'
        lines.append(f'- {role_label}: {content}')

    if len(lines) == 0:
        return ['- No previous session summary.']

    return lines


def _read_latest_step(request_context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(request_context, dict):
        return None

    step_history = request_context.get('step_history')
    if not isinstance(step_history, list) or len(step_history) == 0:
        return None

    latest_step = step_history[-1]
    if not isinstance(latest_step, dict):
        return None
    return latest_step


def _build_request_boundary(step_num: int, request_context: dict[str, Any] | None) -> str:
    if step_num > 0:
        return 'continuation'

    request_origin = _read_request_origin(request_context)
    if request_origin == '':
        return 'new_request'
    return request_origin


def _read_request_origin(request_context: dict[str, Any] | None) -> str:
    if not isinstance(request_context, dict):
        return 'new_request'

    request_origin = str(request_context.get('request_origin') or 'new_request').strip()
    if request_origin == '':
        return 'new_request'
    return request_origin


def _build_phase_text(step_num: int, latest_step: dict[str, Any] | None) -> str:
    if latest_step is None:
        return 'initial_observation'

    execution_status = str(latest_step.get('execution_status') or '').strip()
    verification_status = str(latest_step.get('verification_status') or '').strip()

    if execution_status == 'failed':
        return 'recover_from_execution_failure'

    if verification_status == 'failed':
        return 'recover_from_verification_failure'

    if step_num <= 0:
        return 'initial_action_selection'

    return 'continue_from_latest_confirmed_state'


def _build_last_step_result(latest_step: dict[str, Any] | None) -> str:
    if latest_step is None:
        return 'none yet'

    function_name = str(latest_step.get('function') or 'unknown').strip()
    execution_status = str(latest_step.get('execution_status') or 'unknown').strip()
    verification_status = str(latest_step.get('verification_status') or 'unknown').strip()
    return f'{function_name} | execution={execution_status} | verification={verification_status}'


def _build_blocker_text(
    request_context: dict[str, Any] | None,
    latest_step: dict[str, Any] | None,
) -> str:
    if latest_step is not None:
        if str(latest_step.get('execution_status') or '').strip() == 'failed':
            error_message = normalize_multiline_text(latest_step.get('error_message'), MAX_REASON_CHARS)
            if error_message != '':
                return error_message
            return 'latest execution step failed'

        if str(latest_step.get('verification_status') or '').strip() == 'failed':
            reason = normalize_multiline_text(latest_step.get('verification_reason'), MAX_REASON_CHARS)
            if reason != '':
                return reason
            return 'latest step did not produce a visible UI change'

    if not isinstance(request_context, dict):
        return 'none'

    agent_memory = request_context.get('agent_memory')
    if not isinstance(agent_memory, dict):
        return 'none'

    failures = agent_memory.get('recent_failures')
    if not isinstance(failures, list) or len(failures) == 0:
        return 'none'

    latest_failure = failures[-1]
    if not isinstance(latest_failure, dict):
        return 'none'

    reason = normalize_multiline_text(latest_failure.get('reason'), MAX_REASON_CHARS)
    if reason == '':
        return 'none'
    return reason


def _build_next_step_constraints(request_context: dict[str, Any] | None) -> list[str]:
    constraints = [
        'Return exactly one next step, or return no steps with done when the task is complete or unsafe.',
        'Prefer a short, reversible action that improves certainty about the current UI state.',
        'Do not repeat the exact same failed action if the recent result shows no progress.',
        'Stop with done if login, captcha, 2FA, or any manual confirmation is required.',
    ]

    if not isinstance(request_context, dict):
        return constraints

    agent_memory = request_context.get('agent_memory')
    if not isinstance(agent_memory, dict):
        return constraints

    unreliable_anchor_ids = agent_memory.get('unreliable_anchor_ids')
    if isinstance(unreliable_anchor_ids, list) and len(unreliable_anchor_ids) > 0:
        normalized_ids = ', '.join(str(anchor_id) for anchor_id in unreliable_anchor_ids)
        constraints.append(f'Avoid unreliable anchors unless there is strong new evidence: [{normalized_ids}]')

    recent_failures = agent_memory.get('recent_failures')
    if isinstance(recent_failures, list) and len(recent_failures) > 0:
        latest_failure = recent_failures[-1]
        if isinstance(latest_failure, dict):
            function_name = str(latest_failure.get('function') or '').strip()
            parameters = summarize_parameters(latest_failure.get('parameters'))
            if function_name != '':
                constraints.append(
                    f'Latest relevant failure to avoid repeating blindly: {function_name} {parameters}'
                )

    return constraints


def _build_machine_profile_lines(machine_profile: dict[str, Any] | None) -> list[str]:
    if not isinstance(machine_profile, dict):
        return []

    lines: list[str] = []
    operating_system = str(machine_profile.get('operating_system') or '').strip()
    if operating_system != '':
        lines.append(f'- Operating System: {operating_system}')

    installed_apps = machine_profile.get('installed_apps')
    if isinstance(installed_apps, list) and len(installed_apps) > 0:
        limited_apps = installed_apps[:MAX_INSTALLED_APPS]
        apps_text = ', '.join(str(app_name) for app_name in limited_apps if str(app_name).strip() != '')
        if apps_text != '':
            lines.append(f'- Installed Apps Sample: {apps_text}')

    return lines
