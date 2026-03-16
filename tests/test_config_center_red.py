import importlib
import inspect
import json
import sys
import types
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / 'app') not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / 'app'))


REQUIRED_CONFIG_KEYS = {
    'provider_type',
    'base_url',
    'api_key',
    'model',
    'theme',
    'language',
    'custom_llm_instructions',
    'play_ding_on_completion',
}


def _load_settings_module():
    return importlib.import_module('utils.settings')


def _create_settings_store(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    settings_module = _load_settings_module()

    for class_name in ('SettingsStore', 'ConfigStore', 'Settings'):
        if hasattr(settings_module, class_name):
            store_class = getattr(settings_module, class_name)
            break
    else:
        raise AssertionError(
            '未找到 SettingsStore/ConfigStore。配置中心重构后应提供统一配置存储类。'
        )

    try:
        return store_class()
    except TypeError:
        return store_class(home_dir=str(tmp_path))


def _call_reader(store):
    for method_name in ('get_settings', 'load_settings', 'read_settings', 'get_dict'):
        if hasattr(store, method_name):
            return getattr(store, method_name)()
    raise AssertionError('配置中心缺少读取方法：期望 get_settings()/load_settings()/read_settings()。')


def _call_saver(store, payload):
    for method_name in ('save_settings', 'save', 'save_settings_to_file'):
        if hasattr(store, method_name):
            return getattr(store, method_name)(payload)
    raise AssertionError('配置中心缺少保存方法：期望 save_settings()/save()。')


def _call_migration(store):
    for method_name in ('migrate_from_legacy_json_if_needed', 'migrate_legacy_settings'):
        if hasattr(store, method_name):
            return getattr(store, method_name)()
    raise AssertionError('缺少旧 settings.json 到 SQLite 的迁移入口方法。')


def _has_migration_marker(store):
    for method_name in ('has_migration_marker', 'is_migration_completed'):
        if hasattr(store, method_name):
            return bool(getattr(store, method_name)())
    raise AssertionError('缺少迁移标记查询方法：期望 has_migration_marker()/is_migration_completed()。')


def _call_factory_create(model_name, api_key, base_url):
    factory_module = importlib.import_module('models.factory')
    assert hasattr(factory_module, 'ModelFactory'), '缺少 ModelFactory，无法统一维护模型路由。'

    factory_class = getattr(factory_module, 'ModelFactory')
    instance = factory_class()

    create_method = None
    for candidate in ('create_model', 'create', 'build_model'):
        if hasattr(instance, candidate):
            create_method = getattr(instance, candidate)
            break
    assert create_method is not None, 'ModelFactory 缺少统一模型创建入口。'

    signature = inspect.signature(create_method)
    param_names = tuple(signature.parameters.keys())

    try:
        return create_method(model_name, api_key, base_url)
    except TypeError as exc:
        raise AssertionError(
            f'ModelFactory 创建入口参数不兼容（当前签名: {param_names}），无法验证 Gemini 统一路由。'
        ) from exc


def _install_pyautogui_stub(monkeypatch):
    if 'pyautogui' in sys.modules:
        return

    module = types.ModuleType('pyautogui')
    setattr(module, 'PAUSE', 0)
    setattr(module, 'FAILSAFE', False)

    def _noop(*args, **kwargs):
        return None

    setattr(module, 'size', lambda: (1920, 1080))
    setattr(module, 'position', lambda: (0, 0))
    for attribute_name in (
        'screenshot',
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

    monkeypatch.setitem(sys.modules, 'pyautogui', module)


def _install_google_genai_stub(monkeypatch):
    google_module = sys.modules.get('google')
    if google_module is None:
        google_module = types.ModuleType('google')

    genai_module = types.ModuleType('google.genai')
    genai_types_module = types.ModuleType('google.genai.types')

    class _Client:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    setattr(genai_module, 'Client', _Client)
    setattr(genai_module, 'types', genai_types_module)
    setattr(google_module, 'genai', genai_module)

    monkeypatch.setitem(sys.modules, 'google', google_module)
    monkeypatch.setitem(sys.modules, 'google.genai', genai_module)
    monkeypatch.setitem(sys.modules, 'google.genai.types', genai_types_module)


def test_normal_migrate_legacy_settings_json_to_sqlite_and_write_marker(tmp_path, monkeypatch):
    config_dir = tmp_path / '.open-interface'
    config_dir.mkdir(parents=True, exist_ok=True)

    legacy_payload = {
        'provider_type': 'openai_compatible',
        'base_url': 'https://example.com/v1',
        'api_key': 'bGVnYWN5LWtleQ==',
        'model': 'gpt-5.2',
        'theme': 'darkly',
        'language': 'zh-CN',
        'custom_llm_instructions': 'legacy instructions',
        'play_ding_on_completion': True,
    }
    legacy_file = config_dir / 'settings.json'
    legacy_file.write_text(json.dumps(legacy_payload, ensure_ascii=True), encoding='utf-8')

    store = _create_settings_store(tmp_path, monkeypatch)
    migrate_result = _call_migration(store)
    assert migrate_result is True, '检测到旧配置后应完成迁移并返回成功标记。'

    loaded = _call_reader(store)
    assert loaded['model'] == 'gpt-5.2', '迁移后应保留旧 model 字段。'
    assert _has_migration_marker(store) is True, '迁移完成后应持久化迁移标记。'


def test_boundary_read_without_legacy_returns_complete_defaults(tmp_path, monkeypatch):
    store = _create_settings_store(tmp_path, monkeypatch)
    loaded = _call_reader(store)

    assert isinstance(loaded, dict), '读取配置应返回 dict。'
    missing = REQUIRED_CONFIG_KEYS - set(loaded.keys())
    assert not missing, f'无旧配置时必须回填完整默认值，缺失字段: {sorted(missing)}'

    assert loaded['provider_type'], 'provider_type 不能为空。'
    assert loaded['base_url'], 'base_url 不能为空。'
    assert loaded['model'], 'model 不能为空。'
    assert isinstance(loaded['play_ding_on_completion'], bool), '提示音默认值必须是布尔类型。'


def test_negative_invalid_config_save_must_fail_validation(tmp_path, monkeypatch):
    store = _create_settings_store(tmp_path, monkeypatch)
    invalid_payload = {
        'provider_type': 'openai_compatible',
        'base_url': 'not-a-url',
        'api_key': '',
        'model': '',
        'theme': 'unknown-theme',
        'language': 'invalid-language',
        'custom_llm_instructions': 'x',
        'play_ding_on_completion': 'true',
    }

    with pytest.raises(Exception) as exc_info:
        _call_saver(store, invalid_payload)

    error_text = str(exc_info.value).lower()
    assert (
        'invalid' in error_text
        or 'validation' in error_text
        or 'base_url' in error_text
        or 'model' in error_text
    ), '保存非法配置时应返回可识别的校验错误。'


def test_normal_core_exposes_reload_runtime_settings_for_hot_update(monkeypatch):
    _install_pyautogui_stub(monkeypatch)
    _install_google_genai_stub(monkeypatch)
    core_module = importlib.import_module('core')
    assert hasattr(core_module.Core, 'reload_runtime_settings'), (
        'Core 必须提供 reload_runtime_settings()，用于保存配置后即时热更新。'
    )


def test_negative_reload_runtime_settings_failure_keeps_old_llm_instance(monkeypatch):
    _install_pyautogui_stub(monkeypatch)
    _install_google_genai_stub(monkeypatch)
    core_module = importlib.import_module('core')
    assert hasattr(core_module.Core, 'reload_runtime_settings'), (
        '缺少 reload_runtime_settings()：无法验证热更新失败回退。'
    )

    class ExplodingLLM:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('forced failure for rollback test')

    old_llm = object()
    core = core_module.Core.__new__(core_module.Core)
    core.llm = old_llm

    monkeypatch.setattr(core_module, 'LLM', ExplodingLLM)

    result = core.reload_runtime_settings()
    assert core.llm is old_llm, '热更新失败时必须保留旧 LLM 实例。'
    assert result is False or (isinstance(result, dict) and result.get('ok') is False), (
        '热更新失败时应返回失败状态，避免 UI 误判为成功。'
    )


def test_negative_openai_compatible_gemini_uses_same_openai_sdk_route(monkeypatch):
    _install_pyautogui_stub(monkeypatch)
    _install_google_genai_stub(monkeypatch)
    created_model = None
    try:
        created_model = _call_factory_create(
            model_name='gemini-2.0-flash',
            api_key='test-api-key',
            base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
        )
    except Exception as exc:
        pytest.fail(
            f'Gemini 作为 OpenAI-compatible 路由不应依赖专属参数或独立 SDK，当前异常: {exc}'
        )

    base_model_module = importlib.import_module('models.model')
    assert created_model is not None, '统一路由应成功返回模型实例。'
    assert isinstance(created_model, base_model_module.Model), (
        'OpenAI-compatible 模型（含 Gemini）应复用 Model(OpenAI SDK) 路径。'
    )
    assert created_model.__class__.__module__ != 'models.gemini', (
        'Gemini 不应再走 models.gemini / google.genai 分支。'
    )
