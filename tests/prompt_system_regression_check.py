import os
import sys
import tempfile
import types
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / 'app'

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def install_pyautogui_stub_if_needed() -> None:
    if 'pyautogui' in sys.modules:
        return

    module = types.ModuleType('pyautogui')
    setattr(module, 'PAUSE', 0)
    setattr(module, 'FAILSAFE', False)
    setattr(module, 'size', lambda: (1920, 1080))
    setattr(module, 'position', lambda: (0, 0))
    setattr(module, 'screenshot', lambda *args, **kwargs: None)

    def _noop(*args, **kwargs):
        return None

    for attribute_name in (
        'moveTo',
        'click',
        'doubleClick',
        'rightClick',
        'dragTo',
        'scroll',
        'hotkey',
        'press',
        'write',
        'keyDown',
        'keyUp',
        'mouseDown',
        'mouseUp',
    ):
        setattr(module, attribute_name, _noop)

    sys.modules['pyautogui'] = module


install_pyautogui_stub_if_needed()


from prompting.builder import build_prompt_package
from prompting.constants import PROMPT_SCHEMA_VERSION
from prompting.debug import maybe_dump_prompt_package
from prompting.tool_schema import ToolDefinition
from prompting.tool_schema import ToolParameterDefinition
from prompting.tool_schema import ToolRegistry
from prompting.tool_schema import build_tool_schema_text
import prompting.debug as prompt_debug
from models.claude import Claude
from models.gpt5 import GPT5
from models.qwen import Qwen


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_request_context() -> dict:
    step_history = []
    for step_index in range(1, 9):
        verification_status = 'passed'
        verification_reason = 'screen_changed'
        execution_status = 'succeeded'
        error_message = None
        if step_index == 7:
            verification_status = 'failed'
            verification_reason = 'no_visible_change'
        if step_index == 8:
            verification_status = 'not_run'
            verification_reason = 'execution_failed'
            execution_status = 'failed'
            error_message = 'button target no longer exists'

        step_history.append({
            'step_index': step_index,
            'function': 'click' if step_index % 2 == 0 else 'write',
            'parameters': {
                'target_anchor_id': step_index,
                'x_percent': round(10.0 + (step_index * 5.0), 4),
                'y_percent': round(20.0 + (step_index * 4.0), 4),
            },
            'human_readable_justification': f'第 {step_index} 步：推进当前界面状态。',
            'expected_outcome': f'第 {step_index} 步后界面应出现新的可见变化。',
            'execution_status': execution_status,
            'verification_status': verification_status,
            'verification_reason': verification_reason,
            'error_message': error_message,
        })

    return {
        'request_id': 'req-prompt-regression',
        'request_origin': 'new_request',
        'session_history_snapshot': [
            {'role': 'user', 'content': '先打开 CRM 并定位到客户详情页。'},
            {'role': 'assistant', 'content': '已经进入 CRM，当前停留在客户列表页。'},
        ],
        'agent_memory': {
            'recent_actions': [
                {
                    'function': 'click',
                    'parameters': {'target_anchor_id': 7},
                    'verification_status': 'failed',
                    'verification_reason': 'no_visible_change',
                }
            ],
            'recent_failures': [
                {
                    'function': 'click',
                    'reason': 'no_visible_change',
                    'parameters': {'target_anchor_id': 7},
                }
            ],
            'unreliable_anchor_ids': [7, 8],
            'consecutive_verification_failures': 1,
        },
        'step_history': step_history,
    }


def build_frame_context() -> dict:
    return {
        'logical_screen': {'width': 1920, 'height': 1080},
        'captured_screen': {'width': 1920, 'height': 1080},
        'grid_reference': {
            'coordinate_system': 'percent',
            'axes': ['top', 'left'],
            'x_range': [0, 100],
            'y_range': [0, 100],
        },
        'screen_state': {
            'prompt_mode': 'pure_grid',
            'coordinate_system': 'percent',
        },
    }


def build_machine_profile() -> dict:
    return {
        'operating_system': 'macOS-14.0-arm64',
        'installed_apps': ['Safari.app', 'Google Chrome.app', 'Notes.app'],
    }


def test_prompt_package_structure() -> None:
    package = build_prompt_package(
        base_system_rules='Role:\nYou are a single-step agent.\n\nOutput Contract:\nReturn strict JSON only.',
        custom_instructions='Prefer concise justifications.',
        original_user_request='请继续导出该客户的最新处理记录。',
        step_num=8,
        request_context=build_request_context(),
        frame_context=build_frame_context(),
        machine_profile=build_machine_profile(),
    )

    assert_true(package.schema_version == PROMPT_SCHEMA_VERSION, 'prompt schema version 应固定为 v1。')
    assert_true('[PromptSystemContext]' in package.system_context, 'system context 分层块缺失。')
    assert_true('[PromptToolSchema]' in package.system_context, 'tool schema 分层块缺失。')
    assert_true('[PromptTaskContext]' in package.user_context, 'task context 分层块缺失。')
    assert_true('[PromptExecutionTimeline]' in package.user_context, 'execution timeline 分层块缺失。')
    assert_true('[PromptRecentDetails]' in package.user_context, 'recent details 分层块缺失。')
    assert_true('[PromptVisualContext]' in package.user_context, 'visual context 分层块缺失。')
    assert_true('[PromptOutputContract]' in package.user_context, 'output contract 分层块缺失。')

    assert_true('Current Iteration:' not in package.system_context, 'system context 不应混入动态轮次信息。')
    assert_true('Logical Screen Size:' not in package.system_context, 'system context 不应混入动态视觉尺寸信息。')
    assert_true('pyautogui' not in package.system_context.lower(), 'system context 不应暴露底层 pyautogui 实现。')
    assert_true('Tool: write' in package.system_context, 'tool schema 应暴露 write 工具。')
    assert_true('Tool: hotkey' not in package.system_context, 'tool schema 不应再暴露 hotkey 工具。')
    assert_true('Do not use string, message, or typewrite.' in package.system_context, 'write 参数规范缺失。')
    assert_true('[0, 100]' in package.system_context, 'tool schema 应明确坐标采用 0-100 标尺。')
    assert_true('0-100 ruler scale' in package.user_context, 'visual context 应明确返回 0-100 标尺值。')
    assert_true('Current Iteration: 8' in package.user_context, '动态 task context 必须包含当前轮次。')
    assert_true('Logical Screen Size: 1920x1080' in package.user_context, 'visual context 必须包含逻辑屏幕尺寸。')
    assert_true('Top Level Request Origin: new_request' in package.user_context, 'task context 必须包含顶层请求来源。')
    assert_true('Request Boundary: continuation' in package.user_context, 'task context 必须包含当前请求边界。')
    assert_true('Current Blocker Or Risk: button target no longer exists' in package.user_context, 'authoritative blocker 缺失。')


def test_full_timeline_and_recent_details() -> None:
    package = build_prompt_package(
        base_system_rules='Role:\nYou are a single-step agent.',
        custom_instructions='',
        original_user_request='测试完整 timeline。',
        step_num=8,
        request_context=build_request_context(),
        frame_context=build_frame_context(),
        machine_profile=build_machine_profile(),
    )

    for step_index in range(1, 9):
        assert_true(
            f'Step {step_index}:' in package.execution_timeline,
            f'完整 timeline 必须保留 Step {step_index}。',
        )

    assert_true('Step 5:' not in package.recent_details, 'recent details 不应保留过多旧步骤。')
    assert_true('Step 6:' in package.recent_details, 'recent details 应保留最近少量步骤。')
    assert_true('Step 7:' in package.recent_details, 'recent details 应包含最近失败步骤。')
    assert_true('Step 8:' in package.recent_details, 'recent details 应包含最新步骤。')
    assert_true('button target no longer exists' in package.execution_timeline, 'timeline 应包含失败原因摘要。')
    assert_true('execution=failed' in package.execution_timeline, 'timeline 应包含执行状态。')


def test_provider_prompt_source_consistency() -> None:
    package = build_prompt_package(
        base_system_rules='Role:\nYou are a single-step agent.',
        custom_instructions='Prefer safe clicks.',
        original_user_request='统一 provider prompt 来源。',
        step_num=1,
        request_context=build_request_context(),
        frame_context=build_frame_context(),
        machine_profile=build_machine_profile(),
    )
    visual_payload = {
        'annotated_image_base64': 'ZmFrZQ==',
        'frame_context': build_frame_context(),
    }

    gpt5_model = GPT5('gpt-5', 'https://example.invalid/v1/', 'test-key', package.system_context)
    qwen_model = Qwen('qwen-vl-max-latest', 'https://example.invalid/v1/', 'test-key', package.system_context)
    claude_model = Claude('claude-sonnet-4-6', 'https://example.invalid', 'test-key', package.system_context)

    gpt5_message = gpt5_model.format_prompt_package_for_llm(package, visual_payload, build_request_context())
    qwen_message = qwen_model.format_prompt_package_for_llm(package, visual_payload, build_request_context())
    claude_message = claude_model.format_prompt_package_for_llm(package, visual_payload, build_request_context())
    claude_payload = claude_model.build_request_payload(claude_message, package)

    assert_true(gpt5_message[0]['content'][0]['text'] == package.system_context, 'GPT5 system prompt 来源不一致。')
    assert_true(gpt5_message[1]['content'][0]['text'] == package.user_context, 'GPT5 user prompt 来源不一致。')
    assert_true(qwen_message[0]['content'] == package.system_context, 'Qwen system prompt 来源不一致。')
    assert_true(qwen_message[1]['content'][0]['text'] == package.user_context, 'Qwen user prompt 来源不一致。')
    assert_true(claude_payload['system'] == package.system_context, 'Claude system prompt 来源不一致。')
    assert_true(claude_message[0]['content'][0]['text'] == package.user_context, 'Claude user prompt 来源不一致。')
    assert_true('[PromptToolSchema]' in package.system_context, 'provider 共享的 system context 中应包含 tool schema。')

    gpt5_model.cleanup()
    qwen_model.cleanup()
    claude_model.cleanup()


def test_tool_registry_extension() -> None:
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name='capture_note',
        description='Capture a short note from the current screen state.',
        parameters=(
            ToolParameterDefinition('summary', 'Short note content.', required=True),
        ),
        usage_rules=(
            'Use this only when the runtime explicitly supports note capture.',
        ),
    ))

    schema_text = build_tool_schema_text(registry)
    assert_true('Tool: capture_note' in schema_text, '注册的新工具应自动进入 tool schema。')
    assert_true('summary (required)' in schema_text, '新工具的参数定义应自动进入 tool schema。')


def test_prompt_dump_debug_output() -> None:
    package = build_prompt_package(
        base_system_rules='Role:\nYou are a single-step agent.',
        custom_instructions='',
        original_user_request='测试 prompt dump。',
        step_num=2,
        request_context=build_request_context(),
        frame_context=build_frame_context(),
        machine_profile=build_machine_profile(),
    )

    original_get_prompt_dump_directory = prompt_debug._get_prompt_dump_directory

    with tempfile.TemporaryDirectory() as temp_dir:
        prompt_debug._get_prompt_dump_directory = lambda: Path(temp_dir)
        try:
            dump_path = maybe_dump_prompt_package(package, enabled=True)
        finally:
            prompt_debug._get_prompt_dump_directory = original_get_prompt_dump_directory

        assert_true(dump_path is not None, '启用 prompt dump 后应返回落盘路径。')
        assert_true(Path(dump_path).exists(), 'prompt dump 文件应成功创建。')
        dump_text = Path(dump_path).read_text(encoding='utf-8')
        assert_true('[PromptSystemContext]' in dump_text, 'dump 文件应包含 system context。')
        assert_true('[PromptOutputContract]' in dump_text, 'dump 文件应包含 output contract。')


def main() -> int:
    test_prompt_package_structure()
    test_full_timeline_and_recent_details()
    test_provider_prompt_source_consistency()
    test_tool_registry_extension()
    test_prompt_dump_debug_output()
    print('prompt_system_regression_check: success')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f'prompt_system_regression_check: failed: {exc}')
        raise SystemExit(1)
