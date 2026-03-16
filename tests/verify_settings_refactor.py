import py_compile
import sys
import tempfile
from types import ModuleType
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / 'app'
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

if 'pyautogui' not in sys.modules:
    sys.modules['pyautogui'] = ModuleType('pyautogui')

from models.catalog import (  # noqa: E402
    CLAUDE_PROVIDER_ID,
    OPENAI_PROVIDER_ID,
    QWEN_PROVIDER_ID,
)
from models.claude import Claude  # noqa: E402
from models.factory import ModelFactory  # noqa: E402
from models.gpt5 import GPT5  # noqa: E402
from models.qwen import Qwen  # noqa: E402
from utils.settings import DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS, Settings  # noqa: E402


FILES_TO_COMPILE = [
    APP_ROOT / 'models' / 'catalog.py',
    APP_ROOT / 'models' / 'factory.py',
    APP_ROOT / 'utils' / 'settings.py',
    APP_ROOT / 'utils' / 'i18n.py',
    APP_ROOT / 'llm.py',
    APP_ROOT / 'core.py',
    APP_ROOT / 'ui.py',
]


def compile_changed_files() -> None:
    for file_path in FILES_TO_COMPILE:
        py_compile.compile(str(file_path), doraise=True)
        print(f'compiled: {file_path.relative_to(PROJECT_ROOT)}')


def verify_settings_structure() -> None:
    with tempfile.TemporaryDirectory() as temp_home_dir:
        settings = Settings(home_dir=temp_home_dir)
        defaults = settings.get_dict()

        assert defaults['active_provider'] == OPENAI_PROVIDER_ID
        assert defaults['providers'][OPENAI_PROVIDER_ID]['model'] == 'gpt-5.2'
        assert defaults['providers'][QWEN_PROVIDER_ID]['base_url'].startswith('https://dashscope.aliyuncs.com')
        assert defaults['providers'][CLAUDE_PROVIDER_ID]['model'].startswith('claude-')
        assert defaults['runtime']['play_ding_on_completion'] is True
        assert defaults['appearance']['language'] in {'zh-CN', 'en-US'}
        print('verified: default nested settings structure')

        saved = settings.save_settings({
            'active_provider': QWEN_PROVIDER_ID,
            'providers': {
                OPENAI_PROVIDER_ID: {
                    'api_key': 'openai-key',
                    'base_url': 'https://api.openai.com/v1',
                    'model': 'gpt-5.4',
                    'reasoning': {
                        'enabled': True,
                        'depth': 'high',
                    },
                },
                QWEN_PROVIDER_ID: {
                    'api_key': 'qwen-key',
                    'base_url': 'https://dashscope.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1',
                    'model': 'qwen3.5-plus',
                    'thinking': {
                        'enabled': True,
                    },
                },
                CLAUDE_PROVIDER_ID: {
                    'api_key': 'claude-key',
                    'base_url': 'https://api.anthropic.com',
                    'model': 'claude-sonnet-4-6',
                    'thinking': {
                        'enabled': True,
                        'budget_tokens': 4096,
                    },
                },
            },
            'runtime': {
                'request_timeout_seconds': 30,
                'play_ding_on_completion': False,
            },
            'appearance': {
                'theme': 'journal',
                'language': 'en-US',
            },
            'advanced': {
                'custom_llm_instructions': 'Always answer in Chinese.',
                'save_model_prompt_images': True,
            },
        })

        assert saved['active_provider'] == QWEN_PROVIDER_ID
        assert saved['providers'][OPENAI_PROVIDER_ID]['reasoning']['depth'] == 'high'
        assert saved['providers'][QWEN_PROVIDER_ID]['thinking']['enabled'] is True
        assert saved['providers'][CLAUDE_PROVIDER_ID]['thinking']['budget_tokens'] == 4096
        assert saved['appearance']['theme'] == 'journal'
        assert saved['advanced']['save_model_prompt_images'] is True
        print('verified: nested settings save and reload')

        qwen_runtime = settings.get_model_runtime_settings(saved)
        assert qwen_runtime['provider_id'] == QWEN_PROVIDER_ID
        assert qwen_runtime['api_key'] == 'qwen-key'
        assert qwen_runtime['enable_reasoning'] is True
        assert qwen_runtime['claude_enable_thinking'] is False
        print('verified: qwen runtime settings mapping')

        claude_saved = settings.save_settings({
            'active_provider': CLAUDE_PROVIDER_ID,
            'appearance': {
                'language': 'zh-CN',
            },
        })
        claude_runtime = settings.get_model_runtime_settings(claude_saved)
        assert claude_runtime['provider_id'] == CLAUDE_PROVIDER_ID
        assert claude_runtime['claude_enable_thinking'] is True
        assert claude_runtime['claude_thinking_budget_tokens'] == 4096
        assert claude_runtime['enable_reasoning'] is False
        print('verified: claude runtime settings mapping')

        openai_saved = settings.save_settings({
            'active_provider': OPENAI_PROVIDER_ID,
        })
        openai_runtime = settings.get_model_runtime_settings(openai_saved)
        assert openai_runtime['provider_id'] == OPENAI_PROVIDER_ID
        assert openai_runtime['enable_reasoning'] is True
        assert openai_runtime['reasoning_depth'] == 'high'
        assert openai_runtime['claude_thinking_budget_tokens'] == DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS
        print('verified: openai runtime settings mapping')


def verify_model_factory_routing() -> None:
    openai_model = ModelFactory.create_model(
        'gpt-5.2',
        'test-key',
        'https://api.openai.com/v1/',
        'context',
        provider_id=OPENAI_PROVIDER_ID,
    )
    qwen_model = ModelFactory.create_model(
        'qwen3.5-plus',
        'test-key',
        'https://dashscope.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1/',
        'context',
        provider_id=QWEN_PROVIDER_ID,
    )
    claude_model = ModelFactory.create_model(
        'claude-sonnet-4-6',
        'test-key',
        'https://api.anthropic.com/',
        'context',
        provider_id=CLAUDE_PROVIDER_ID,
    )

    assert isinstance(openai_model, GPT5)
    assert isinstance(qwen_model, Qwen)
    assert isinstance(claude_model, Claude)
    print('verified: model factory provider routing')

    openai_model.cleanup()
    qwen_model.cleanup()
    claude_model.cleanup()


def main() -> None:
    compile_changed_files()
    verify_settings_structure()
    verify_model_factory_routing()
    print('verification: PASS')


if __name__ == '__main__':
    main()
