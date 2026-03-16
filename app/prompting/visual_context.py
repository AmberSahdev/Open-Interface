from typing import Any

from prompting.common import format_block


def build_visual_context(frame_context: dict[str, Any] | None) -> str:
    lines = [
        'Latest Screenshot: the annotated screenshot image is attached separately to this request.',
    ]

    if not isinstance(frame_context, dict):
        lines.append('No frame context is available.')
        return format_block('PromptVisualContext', lines)

    logical_screen = frame_context.get('logical_screen')
    captured_screen = frame_context.get('captured_screen')
    grid_reference = frame_context.get('grid_reference')
    screen_state = frame_context.get('screen_state')

    lines.append(f'Logical Screen Size: {_format_size(logical_screen)}')
    lines.append(f'Capture Size: {_format_size(captured_screen)}')
    lines.append(f'Grid Reference: {_format_grid_reference(grid_reference)}')
    lines.append(f'Screen State: {_format_screen_state(screen_state)}')
    lines.append(
        'Grid Usage Rule: use the visible top ruler for X and left ruler for Y, then return x_percent/y_percent on the same 0-100 ruler scale.'
    )

    return format_block('PromptVisualContext', lines)


def _format_size(size_payload: Any) -> str:
    if not isinstance(size_payload, dict):
        return 'unknown'

    width = size_payload.get('width')
    height = size_payload.get('height')
    if width is None or height is None:
        return 'unknown'
    return f'{width}x{height}'


def _format_grid_reference(grid_reference: Any) -> str:
    if not isinstance(grid_reference, dict):
        return 'unknown'

    coordinate_system = str(grid_reference.get('coordinate_system') or 'unknown').strip()
    axes = ', '.join(str(axis) for axis in grid_reference.get('axes') or [])
    x_range = grid_reference.get('x_range') or []
    y_range = grid_reference.get('y_range') or []
    return (
        f'coordinate_system={coordinate_system}, axes=[{axes}], '
        f'x_range={x_range}, y_range={y_range}'
    )


def _format_screen_state(screen_state: Any) -> str:
    if not isinstance(screen_state, dict):
        return 'unknown'

    prompt_mode = str(screen_state.get('prompt_mode') or 'unknown').strip()
    coordinate_system = str(screen_state.get('coordinate_system') or 'unknown').strip()
    return f'prompt_mode={prompt_mode}, coordinate_system={coordinate_system}'
