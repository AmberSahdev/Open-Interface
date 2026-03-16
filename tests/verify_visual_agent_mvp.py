import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from agent_memory import build_agent_memory_payload
from agent_memory import create_agent_memory
from agent_memory import mark_anchor_unreliable
from agent_memory import record_action
from agent_memory import record_failure
from verifier import StepVerifier


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_test_images() -> tuple[Image.Image, Image.Image]:
    before = Image.new('RGB', (240, 180), color='white')
    draw_before = ImageDraw.Draw(before)
    draw_before.rectangle((40, 50, 120, 110), outline='black', width=2)

    after = before.copy()
    draw_after = ImageDraw.Draw(after)
    draw_after.rectangle((40, 50, 120, 110), fill='blue', outline='black', width=2)
    return before, after


def test_agent_memory() -> None:
    memory = create_agent_memory()
    record_action(
        memory,
        function_name='click',
        parameters={'target_anchor_id': 3, 'x_percent': 0.3, 'y_percent': 0.4},
        verification_status='passed',
        verification_reason='screen_changed',
    )
    record_failure(
        memory,
        function_name='click',
        reason='no_visible_change',
        parameters={'target_anchor_id': 3},
    )
    mark_anchor_unreliable(memory, 3)
    payload = build_agent_memory_payload(memory)

    assert_true(len(payload['recent_actions']) == 1, 'recent_actions should contain one item')
    assert_true(len(payload['recent_failures']) == 1, 'recent_failures should contain one item')
    assert_true(payload['unreliable_anchor_ids'] == [3], 'anchor 3 should be marked unreliable')
    assert_true(
        payload['consecutive_verification_failures'] == 0,
        'successful action should reset consecutive verification failures',
    )


def test_verifier_passes_on_local_change() -> None:
    before, after = build_test_images()
    verifier = StepVerifier()
    result = verifier.verify_step(
        {
            'function': 'click',
            'expected_outcome': 'A dialog or visual state should change.',
        },
        {'x': 80, 'y': 80},
        before,
        after,
    )
    assert_true(result['status'] == 'passed', 'click with local visual change should pass verification')


def test_verifier_fails_when_nothing_changes() -> None:
    before = Image.new('RGB', (240, 180), color='white')
    after = before.copy()
    verifier = StepVerifier()
    result = verifier.verify_step(
        {
            'function': 'click',
            'expected_outcome': 'The UI should visibly change.',
        },
        {'x': 80, 'y': 80},
        before,
        after,
    )
    assert_true(result['status'] == 'failed', 'unchanged click should fail verification')


def main() -> None:
    test_agent_memory()
    test_verifier_passes_on_local_change()
    test_verifier_fails_when_nothing_changes()
    print('visual agent MVP verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'visual agent MVP verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
