import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / 'app'

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from models.model import Model
from utils.settings import SettingsValidationError, SettingsStore


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f'{message} actual={actual!r} expected={expected!r}')


def verify_reasoning_request_options() -> None:
    model = Model('gpt-5.4', 'https://api.openai.com/v1/', '', '')

    assert_equal(model.build_reasoning_request_options(), {}, '默认不应附带 reasoning 参数。')

    model.set_runtime_settings({
        'enable_reasoning': True,
        'reasoning_depth': 'xhigh',
    })
    assert_equal(
        model.build_reasoning_request_options(),
        {'reasoning': {'effort': 'xhigh'}},
        '启用 reasoning 后应输出正确 effort。',
    )

    assert_equal(
        model.build_reasoning_request_options(include_summary=True),
        {'reasoning': {'effort': 'xhigh', 'summary': 'auto'}},
        '启用 summary 时应输出 reasoning summary=auto。',
    )

    model.set_runtime_settings({
        'enable_reasoning': True,
        'reasoning_depth': 'unsupported-value',
    })
    assert_equal(
        model.build_reasoning_request_options(),
        {'reasoning': {'effort': 'low'}},
        '非法 reasoning depth 应回退到 low。',
    )


def verify_settings_accept_gpt54_reasoning_depths() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = SettingsStore(home_dir=tmp_dir)
        payload = store.save_settings({
            'provider_type': 'openai_compatible',
            'base_url': 'https://api.openai.com/v1/',
            'api_key': '',
            'model': 'gpt-5.4',
            'theme': 'superhero',
            'language': 'zh-CN',
            'custom_llm_instructions': '',
            'enable_reasoning': True,
            'reasoning_depth': 'none',
            'play_ding_on_completion': True,
        })
        assert_equal(payload['reasoning_depth'], 'none', '配置校验应接受 none。')

        payload = store.save_settings({
            'reasoning_depth': 'xhigh',
        })
        assert_equal(payload['reasoning_depth'], 'xhigh', '配置校验应接受 xhigh。')

        try:
            store.save_settings({
                'reasoning_depth': 'invalid-depth',
            })
        except SettingsValidationError:
            return

    raise AssertionError('非法 reasoning_depth 必须触发配置校验失败。')


def main() -> int:
    verify_reasoning_request_options()
    verify_settings_accept_gpt54_reasoning_depths()
    print('verify_gpt5_reasoning: success')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f'verify_gpt5_reasoning: failed: {exc}')
        raise SystemExit(1)
