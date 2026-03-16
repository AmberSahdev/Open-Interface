DEFAULT_MODEL_NAME = 'gpt-5.2'
DEFAULT_BASE_URL = 'https://api.openai.com/v1/'
DEFAULT_ANTHROPIC_BASE_URL = 'https://api.anthropic.com/'
DEFAULT_QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1/'
RECOMMENDED_QWEN_VISION_MODEL = 'qwen-vl-max-latest'
DEFAULT_QWEN_MODEL_NAME = 'qwen3.5-plus'
DEFAULT_CLAUDE_MODEL_NAME = 'claude-sonnet-4-6'

OPENAI_PROVIDER_ID = 'openai'
QWEN_PROVIDER_ID = 'qwen'
CLAUDE_PROVIDER_ID = 'claude'
GEMINI_PROVIDER_ID = 'gemini'
KIMI_PROVIDER_ID = 'kimi'
DEFAULT_PROVIDER_ID = OPENAI_PROVIDER_ID

QWEN_MODEL_PREFIXES = ('qwen', 'qvq', 'qwq')
CLAUDE_MODEL_PREFIXES = ('claude',)
QWEN_VISION_MODEL_PREFIXES = (
    'qwen3.5-plus',
    'qwen-vl',
    'qwen2.5-vl',
    'qwen3-vl',
    'qwen-vl-ocr',
    'qvq',
)

QWEN_REASONING_TOGGLE_PREFIXES = (
    'qwen3.5-plus',
    'qwen3.5-flash',
    'qwen3-vl-plus',
    'qwen3-vl-flash',
    'qwen3-max',
    'qwen-plus',
    'qwen-flash',
    'qwen-turbo',
    'qwen3-',
)

QWEN_REASONING_REQUIRED_PREFIXES = (
    'qwq',
    'qvq',
    'qwen3-vl-235b-a22b-thinking',
    'qwen3-vl-30b-a3b-thinking',
    'qwen3-vl-8b-thinking',
    'qwen3-next-80b-a3b-thinking',
)

PROVIDER_CATALOG = [
    {
        'id': OPENAI_PROVIDER_ID,
        'label': 'OpenAI',
        'default_model': DEFAULT_MODEL_NAME,
        'default_base_url': DEFAULT_BASE_URL,
    },
    {
        'id': QWEN_PROVIDER_ID,
        'label': 'Qwen',
        'default_model': DEFAULT_QWEN_MODEL_NAME,
        'default_base_url': DEFAULT_QWEN_BASE_URL,
    },
    {
        'id': CLAUDE_PROVIDER_ID,
        'label': 'Claude',
        'default_model': DEFAULT_CLAUDE_MODEL_NAME,
        'default_base_url': DEFAULT_ANTHROPIC_BASE_URL,
    },
]

MODEL_CATALOG = [
    {
        'id': 'gpt-5.4',
        'label_key': 'advanced.model.gpt54_default',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'gpt-5.2',
        'label_key': 'advanced.model.gpt52_default',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'qwen3.5-plus',
        'label_key': 'advanced.model.qwen35_plus',
        'provider': QWEN_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'qwen-vl-max-latest',
        'label_key': 'advanced.model.qwen_vl_max_latest',
        'provider': QWEN_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'qwen3-vl-plus',
        'label_key': 'advanced.model.qwen3_vl_plus',
        'provider': QWEN_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'qwen-plus-latest',
        'label_key': 'advanced.model.qwen_plus_latest',
        'provider': QWEN_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'qwen3-32b',
        'label_key': 'advanced.model.qwen3_32b',
        'provider': QWEN_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'claude-sonnet-4-6',
        'label_key': 'advanced.model.claude_sonnet_46',
        'provider': CLAUDE_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'claude-opus-4-6',
        'label_key': 'advanced.model.claude_opus_46',
        'provider': CLAUDE_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'computer-use-preview',
        'label_key': 'advanced.model.computer_use_preview',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'gemini-3-pro-preview',
        'label_key': 'advanced.model.gemini_3_pro_preview',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'gemini-3-flash-preview',
        'label_key': 'advanced.model.gemini_3_flash_preview',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': False,
    },
    {
        'id': 'gpt-4o',
        'label_key': 'advanced.model.gpt4o',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gpt-4o-mini',
        'label_key': 'advanced.model.gpt4o_mini',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gpt-4-vision-preview',
        'label_key': 'advanced.model.gpt4v',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gpt-4-turbo',
        'label_key': 'advanced.model.gpt4_turbo',
        'provider': OPENAI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.5-pro',
        'label_key': 'advanced.model.gemini_25_pro',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.5-flash',
        'label_key': 'advanced.model.gemini_25_flash',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.5-flash-lite',
        'label_key': 'advanced.model.gemini_25_flash_lite',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.0-flash',
        'label_key': 'advanced.model.gemini_20_flash',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.0-flash-lite',
        'label_key': 'advanced.model.gemini_20_flash_lite',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.0-flash-thinking-exp',
        'label_key': 'advanced.model.gemini_20_flash_thinking',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
    {
        'id': 'gemini-2.0-pro-exp-02-05',
        'label_key': 'advanced.model.gemini_20_pro_exp',
        'provider': GEMINI_PROVIDER_ID,
        'deprecated': True,
    },
]


def get_provider_catalog() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for provider in PROVIDER_CATALOG:
        items.append(dict(provider))
    return items


def get_provider_ids() -> list[str]:
    provider_ids: list[str] = []
    for provider in PROVIDER_CATALOG:
        provider_ids.append(str(provider['id']))
    return provider_ids


def normalize_provider_id(provider_id: str | None) -> str:
    normalized = str(provider_id or '').strip().lower()
    if normalized in get_provider_ids():
        return normalized
    return DEFAULT_PROVIDER_ID


def get_provider_label(provider_id: str) -> str:
    normalized_provider_id = normalize_provider_id(provider_id)
    for provider in PROVIDER_CATALOG:
        if provider['id'] == normalized_provider_id:
            return str(provider['label'])
    return str(PROVIDER_CATALOG[0]['label'])


def get_default_model_for_provider(provider_id: str) -> str:
    normalized_provider_id = normalize_provider_id(provider_id)
    for provider in PROVIDER_CATALOG:
        if provider['id'] == normalized_provider_id:
            return str(provider['default_model'])
    return DEFAULT_MODEL_NAME


def get_default_base_url_for_provider(provider_id: str) -> str:
    normalized_provider_id = normalize_provider_id(provider_id)
    for provider in PROVIDER_CATALOG:
        if provider['id'] == normalized_provider_id:
            return str(provider['default_base_url'])
    return DEFAULT_BASE_URL


def get_model_ids(include_deprecated: bool = True) -> list[str]:
    model_ids: list[str] = []
    for item in MODEL_CATALOG:
        if not include_deprecated and item['deprecated']:
            continue
        model_ids.append(str(item['id']))
    return model_ids


def get_model_catalog(include_deprecated: bool = True) -> list[dict[str, str | bool]]:
    items: list[dict[str, str | bool]] = []
    for item in MODEL_CATALOG:
        if not include_deprecated and item['deprecated']:
            continue
        items.append(dict(item))
    return items


def get_model_catalog_for_provider(provider_id: str, include_deprecated: bool = True) -> list[dict[str, str | bool]]:
    normalized_provider_id = normalize_provider_id(provider_id)
    filtered_items: list[dict[str, str | bool]] = []

    for item in get_model_catalog(include_deprecated=include_deprecated):
        item_provider_id = str(item.get('provider') or '').strip().lower()
        if item_provider_id == normalized_provider_id:
            filtered_items.append(item)

    return filtered_items


def is_gemini_model(model_name: str) -> bool:
    normalized = str(model_name or '').strip().lower()
    return normalized.startswith('gemini')


def is_qwen_model(model_name: str) -> bool:
    normalized = str(model_name or '').strip().lower()
    for prefix in QWEN_MODEL_PREFIXES:
        if normalized.startswith(prefix):
            return True
    return False


def is_claude_model(model_name: str) -> bool:
    normalized = str(model_name or '').strip().lower()
    for prefix in CLAUDE_MODEL_PREFIXES:
        if normalized.startswith(prefix):
            return True
    return False


def is_qwen_vision_model(model_name: str) -> bool:
    normalized = str(model_name or '').strip().lower()
    for prefix in QWEN_VISION_MODEL_PREFIXES:
        if normalized.startswith(prefix):
            return True
    return False


def supports_qwen_reasoning_toggle(model_name: str) -> bool:
    normalized = str(model_name or '').strip().lower()
    for prefix in QWEN_REASONING_TOGGLE_PREFIXES:
        if normalized.startswith(prefix):
            return True
    return False


def requires_qwen_reasoning(model_name: str) -> bool:
    normalized = str(model_name or '').strip().lower()
    for prefix in QWEN_REASONING_REQUIRED_PREFIXES:
        if normalized.startswith(prefix):
            return True
    return False
