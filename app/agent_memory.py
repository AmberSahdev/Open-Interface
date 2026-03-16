from typing import Any, Optional

MAX_RECENT_ACTIONS = 6
MAX_RECENT_FAILURES = 6
MAX_UNRELIABLE_ANCHORS = 12


def create_agent_memory() -> dict[str, Any]:
    return {
        'recent_actions': [],
        'recent_failures': [],
        'unreliable_anchor_ids': [],
        'consecutive_verification_failures': 0,
    }


def build_agent_memory_payload(agent_memory: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(agent_memory, dict):
        return create_agent_memory()

    payload = create_agent_memory()
    payload['recent_actions'] = _copy_list(agent_memory.get('recent_actions'), MAX_RECENT_ACTIONS)
    payload['recent_failures'] = _copy_list(agent_memory.get('recent_failures'), MAX_RECENT_FAILURES)
    payload['unreliable_anchor_ids'] = _copy_anchor_ids(agent_memory.get('unreliable_anchor_ids'))
    payload['consecutive_verification_failures'] = _read_non_negative_int(
        agent_memory.get('consecutive_verification_failures'),
    )
    return payload


def record_action(
    agent_memory: dict[str, Any],
    *,
    function_name: str,
    parameters: Optional[dict[str, Any]],
    verification_status: str,
    verification_reason: str,
) -> None:
    recent_actions = _ensure_list(agent_memory, 'recent_actions')
    recent_actions.append({
        'function': str(function_name or '').strip(),
        'parameters': _summarize_parameters(parameters),
        'verification_status': str(verification_status or '').strip(),
        'verification_reason': str(verification_reason or '').strip(),
    })
    _trim_list(recent_actions, MAX_RECENT_ACTIONS)

    if verification_status == 'failed':
        agent_memory['consecutive_verification_failures'] = _read_non_negative_int(
            agent_memory.get('consecutive_verification_failures'),
        ) + 1
    else:
        agent_memory['consecutive_verification_failures'] = 0


def record_failure(
    agent_memory: dict[str, Any],
    *,
    function_name: str,
    reason: str,
    parameters: Optional[dict[str, Any]] = None,
) -> None:
    recent_failures = _ensure_list(agent_memory, 'recent_failures')
    recent_failures.append({
        'function': str(function_name or '').strip(),
        'reason': str(reason or '').strip(),
        'parameters': _summarize_parameters(parameters),
    })
    _trim_list(recent_failures, MAX_RECENT_FAILURES)


def mark_anchor_unreliable(agent_memory: dict[str, Any], anchor_id: Any) -> None:
    try:
        normalized_anchor_id = int(anchor_id)
    except Exception:
        return

    unreliable_anchor_ids = _ensure_list(agent_memory, 'unreliable_anchor_ids')
    if normalized_anchor_id in unreliable_anchor_ids:
        return

    unreliable_anchor_ids.append(normalized_anchor_id)
    _trim_list(unreliable_anchor_ids, MAX_UNRELIABLE_ANCHORS)


def _copy_list(value: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    copied: list[dict[str, Any]] = []
    for item in value[-limit:]:
        if isinstance(item, dict):
            copied.append(dict(item))
    return copied


def _copy_anchor_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    normalized: list[int] = []
    for item in value[-MAX_UNRELIABLE_ANCHORS:]:
        try:
            normalized.append(int(item))
        except Exception:
            continue
    return normalized


def _ensure_list(agent_memory: dict[str, Any], key: str) -> list[Any]:
    current_value = agent_memory.get(key)
    if isinstance(current_value, list):
        return current_value

    agent_memory[key] = []
    return agent_memory[key]


def _trim_list(items: list[Any], limit: int) -> None:
    while len(items) > limit:
        items.pop(0)


def _read_non_negative_int(value: Any) -> int:
    try:
        normalized = int(value)
    except Exception:
        return 0

    if normalized < 0:
        return 0
    return normalized


def _summarize_parameters(parameters: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        return {}

    allowed_keys = {
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
    }
    summary: dict[str, Any] = {}
    for key, value in parameters.items():
        if key not in allowed_keys:
            continue
        summary[key] = value
    return summary
