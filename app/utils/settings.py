import copy
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from models.catalog import (
    CLAUDE_PROVIDER_ID,
    DEFAULT_BASE_URL,
    DEFAULT_CLAUDE_MODEL_NAME,
    DEFAULT_MODEL_NAME,
    DEFAULT_PROVIDER_ID,
    DEFAULT_QWEN_BASE_URL,
    DEFAULT_QWEN_MODEL_NAME,
    OPENAI_PROVIDER_ID,
    QWEN_PROVIDER_ID,
    get_default_base_url_for_provider,
    get_default_model_for_provider,
    get_provider_ids,
    normalize_provider_id,
)


DEFAULT_THEME = 'superhero'
DEFAULT_LANGUAGE = 'zh-CN'
DEFAULT_REASONING_DEPTH = 'medium'
DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS = 2048
DEFAULT_REQUEST_TIMEOUT_SECONDS = 25.0
MIN_REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REQUEST_TIMEOUT_SECONDS = 300.0

SUPPORTED_THEMES = {'darkly', 'cyborg', 'journal', 'solar', 'superhero'}
SUPPORTED_LANGUAGES = {'zh-CN', 'en-US'}
SUPPORTED_REASONING_DEPTHS = {'none', 'low', 'medium', 'high', 'xhigh'}

DEFAULT_PROVIDER_SETTINGS: dict[str, dict[str, Any]] = {
    OPENAI_PROVIDER_ID: {
        'api_key': '',
        'base_url': DEFAULT_BASE_URL,
        'model': DEFAULT_MODEL_NAME,
        'reasoning': {
            'enabled': False,
            'depth': DEFAULT_REASONING_DEPTH,
        },
    },
    QWEN_PROVIDER_ID: {
        'api_key': '',
        'base_url': DEFAULT_QWEN_BASE_URL,
        'model': DEFAULT_QWEN_MODEL_NAME,
        'thinking': {
            'enabled': False,
        },
    },
    CLAUDE_PROVIDER_ID: {
        'api_key': '',
        'base_url': get_default_base_url_for_provider(CLAUDE_PROVIDER_ID),
        'model': DEFAULT_CLAUDE_MODEL_NAME,
        'thinking': {
            'enabled': False,
            'budget_tokens': DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS,
        },
    },
}

DEFAULT_RUNTIME_SETTINGS: dict[str, Any] = {
    'request_timeout_seconds': DEFAULT_REQUEST_TIMEOUT_SECONDS,
    'play_ding_on_completion': True,
    'disable_local_step_verification': False,
}

DEFAULT_APPEARANCE_SETTINGS: dict[str, Any] = {
    'theme': DEFAULT_THEME,
    'language': DEFAULT_LANGUAGE,
}

DEFAULT_ADVANCED_SETTINGS: dict[str, Any] = {
    'custom_llm_instructions': '',
    'save_model_prompt_images': False,
    'save_prompt_text_dumps': False,
}

DEFAULT_SETTINGS: dict[str, Any] = {
    'active_provider': DEFAULT_PROVIDER_ID,
    'providers': DEFAULT_PROVIDER_SETTINGS,
    'runtime': DEFAULT_RUNTIME_SETTINGS,
    'appearance': DEFAULT_APPEARANCE_SETTINGS,
    'advanced': DEFAULT_ADVANCED_SETTINGS,
}


class SettingsValidationError(ValueError):
    pass


class SettingsStore:
    APP_DATA_DIRECTORY_NAME = '.open-interface'
    SETTINGS_FILE_NAME = 'settings.json'
    SESSION_HISTORY_DB_FILE_NAME = 'session_history.db'
    CONFIG_TABLE_NAME = 'app_config'

    def __init__(self, home_dir: str | None = None):
        if home_dir is None:
            self.home_dir = Path.home()
        else:
            self.home_dir = Path(home_dir).expanduser()

        self.app_data_directory = self.home_dir / self.APP_DATA_DIRECTORY_NAME
        self.settings_file_path = str(self.app_data_directory / self.SETTINGS_FILE_NAME)
        self.session_history_db_path = str(self.app_data_directory / self.SESSION_HISTORY_DB_FILE_NAME)
        self.app_data_directory.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
        self.settings: dict[str, Any] = {}

    @classmethod
    def get_app_data_directory(cls) -> Path:
        return Path.home() / cls.APP_DATA_DIRECTORY_NAME

    def get_settings_directory_path(self) -> str:
        return str(self.app_data_directory)

    def get_app_data_directory_path(self) -> str:
        return str(self.app_data_directory)

    def get_settings_file_path(self) -> str:
        return self.settings_file_path

    def get_session_history_db_path(self) -> str:
        return self.session_history_db_path

    def get_storage_paths(self) -> dict[str, str]:
        return {
            'app_data_dir': self.get_app_data_directory_path(),
            'settings_file': self.get_settings_file_path(),
            'session_history_db': self.get_session_history_db_path(),
            'config_db': self.get_session_history_db_path(),
        }

    def get_dict(self) -> dict[str, Any]:
        return self.get_settings()

    def get_settings(self) -> dict[str, Any]:
        self._initialize_schema()
        db_settings = self._read_settings_from_db()

        if len(db_settings) == 0:
            settings = self._build_default_settings()
            self._write_settings_to_db(settings)
        else:
            try:
                merged_settings = self._deep_merge(self._build_default_settings(), db_settings)
                settings = self._normalize_for_read(merged_settings)
                if db_settings != settings:
                    self._write_settings_to_db(settings)
            except SettingsValidationError:
                settings = self._build_default_settings()
                self._write_settings_to_db(settings)

        self.settings = settings
        self._sync_provider_api_key_env(settings)
        return copy.deepcopy(settings)

    def load_settings(self) -> dict[str, Any]:
        return self.get_settings()

    def read_settings(self) -> dict[str, Any]:
        return self.get_settings()

    def save_settings(self, settings_dict: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(settings_dict, dict):
            raise SettingsValidationError('Invalid settings payload: expected dict.')

        current_settings = self.get_settings()
        merged_settings = self._deep_merge(current_settings, settings_dict)
        normalized_settings = self._validate_and_normalize(merged_settings)

        self._write_settings_to_db(normalized_settings)
        self.settings = normalized_settings
        self._sync_provider_api_key_env(normalized_settings)

        return copy.deepcopy(normalized_settings)

    def save(self, settings_dict: dict[str, Any]) -> dict[str, Any]:
        return self.save_settings(settings_dict)

    def save_settings_to_file(self, settings_dict: dict[str, Any]) -> None:
        self.save_settings(settings_dict)

    def get_active_provider_id(self, settings_dict: dict[str, Any] | None = None) -> str:
        normalized_settings = self._normalize_input_settings(settings_dict)
        return str(normalized_settings['active_provider'])

    def get_provider_settings(self, provider_id: str, settings_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_settings = self._normalize_input_settings(settings_dict)
        normalized_provider_id = normalize_provider_id(provider_id)
        providers = normalized_settings.get('providers')
        if not isinstance(providers, dict):
            return copy.deepcopy(DEFAULT_PROVIDER_SETTINGS[normalized_provider_id])
        provider_settings = providers.get(normalized_provider_id)
        if not isinstance(provider_settings, dict):
            return copy.deepcopy(DEFAULT_PROVIDER_SETTINGS[normalized_provider_id])
        return copy.deepcopy(provider_settings)

    def get_active_provider_settings(self, settings_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_settings = self._normalize_input_settings(settings_dict)
        active_provider = self.get_active_provider_id(normalized_settings)
        return self.get_provider_settings(active_provider, normalized_settings)

    def get_model_runtime_settings(self, settings_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_settings = self._normalize_input_settings(settings_dict)
        active_provider = self.get_active_provider_id(normalized_settings)
        active_provider_settings = self.get_provider_settings(active_provider, normalized_settings)
        runtime_settings = normalized_settings.get('runtime') or {}
        appearance_settings = normalized_settings.get('appearance') or {}
        advanced_settings = normalized_settings.get('advanced') or {}

        model_runtime_settings = {
            'provider_id': active_provider,
            'base_url': str(active_provider_settings.get('base_url') or ''),
            'api_key': str(active_provider_settings.get('api_key') or ''),
            'model': str(active_provider_settings.get('model') or get_default_model_for_provider(active_provider)),
            'request_timeout_seconds': runtime_settings.get('request_timeout_seconds', DEFAULT_REQUEST_TIMEOUT_SECONDS),
            'play_ding_on_completion': bool(runtime_settings.get('play_ding_on_completion', True)),
            'theme': str(appearance_settings.get('theme') or DEFAULT_THEME),
            'language': str(appearance_settings.get('language') or DEFAULT_LANGUAGE),
            'custom_llm_instructions': str(advanced_settings.get('custom_llm_instructions') or ''),
            'save_model_prompt_images': bool(advanced_settings.get('save_model_prompt_images', False)),
            'save_prompt_text_dumps': bool(advanced_settings.get('save_prompt_text_dumps', False)),
            'enable_reasoning': False,
            'reasoning_depth': DEFAULT_REASONING_DEPTH,
            'claude_enable_thinking': False,
            'claude_thinking_budget_tokens': DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS,
        }

        if active_provider == OPENAI_PROVIDER_ID:
            reasoning_settings = active_provider_settings.get('reasoning') or {}
            model_runtime_settings['enable_reasoning'] = bool(reasoning_settings.get('enabled', False))
            model_runtime_settings['reasoning_depth'] = str(reasoning_settings.get('depth') or DEFAULT_REASONING_DEPTH)
        elif active_provider == QWEN_PROVIDER_ID:
            thinking_settings = active_provider_settings.get('thinking') or {}
            model_runtime_settings['enable_reasoning'] = bool(thinking_settings.get('enabled', False))
            model_runtime_settings['reasoning_depth'] = DEFAULT_REASONING_DEPTH
        elif active_provider == CLAUDE_PROVIDER_ID:
            thinking_settings = active_provider_settings.get('thinking') or {}
            model_runtime_settings['claude_enable_thinking'] = bool(thinking_settings.get('enabled', False))
            model_runtime_settings['claude_thinking_budget_tokens'] = int(
                thinking_settings.get('budget_tokens', DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS)
            )

        return model_runtime_settings

    def _build_default_settings(self) -> dict[str, Any]:
        return copy.deepcopy(DEFAULT_SETTINGS)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.session_history_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                f'''
                CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE_NAME} (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            connection.commit()
        finally:
            connection.close()

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read_settings_from_db(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(f'SELECT key, value FROM {self.CONFIG_TABLE_NAME}')
            rows = cursor.fetchall()
        finally:
            connection.close()

        settings: dict[str, Any] = {}
        for row in rows:
            key = str(row['key'])
            value = row['value']
            settings[key] = self._deserialize_value(value)
        return settings

    def _write_settings_to_db(self, settings_dict: dict[str, Any]) -> None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(f'DELETE FROM {self.CONFIG_TABLE_NAME}')
            now = self._timestamp()
            for key, value in settings_dict.items():
                cursor.execute(
                    f'''
                    INSERT INTO {self.CONFIG_TABLE_NAME} (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ''',
                    (str(key), self._serialize_value(value), now),
                )
            connection.commit()
        finally:
            connection.close()

    def _serialize_value(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=True)

    def _deserialize_value(self, value: str) -> Any:
        try:
            return json.loads(value)
        except Exception:
            return value

    def _deep_merge(self, base_value: Any, update_value: Any) -> Any:
        if not isinstance(base_value, dict) or not isinstance(update_value, dict):
            return copy.deepcopy(update_value)

        merged: dict[str, Any] = copy.deepcopy(base_value)
        for key, value in update_value.items():
            if key in merged:
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def _normalize_input_settings(self, settings_dict: dict[str, Any] | None) -> dict[str, Any]:
        if settings_dict is None:
            return self.get_settings()

        if not isinstance(settings_dict, dict):
            raise SettingsValidationError('Invalid settings payload: expected dict.')

        merged_settings = self._deep_merge(self._build_default_settings(), settings_dict)
        return self._normalize_for_read(merged_settings)

    def _normalize_for_read(self, settings_dict: dict[str, Any]) -> dict[str, Any]:
        normalized_input = self._deep_merge(self._build_default_settings(), settings_dict)
        return self._validate_and_normalize(normalized_input)

    def _sync_provider_api_key_env(self, settings_dict: dict[str, Any]) -> None:
        try:
            normalized_settings = self._normalize_input_settings(settings_dict)
        except SettingsValidationError:
            normalized_settings = self._build_default_settings()

        providers = normalized_settings.get('providers') or {}
        active_provider = str(normalized_settings.get('active_provider') or DEFAULT_PROVIDER_ID)

        openai_api_key = ''
        if active_provider in {OPENAI_PROVIDER_ID, QWEN_PROVIDER_ID}:
            active_provider_settings = providers.get(active_provider) or {}
            openai_api_key = str(active_provider_settings.get('api_key') or '').strip()

        if openai_api_key == '':
            openai_provider_settings = providers.get(OPENAI_PROVIDER_ID) or {}
            openai_api_key = str(openai_provider_settings.get('api_key') or '').strip()

        if openai_api_key == '':
            qwen_provider_settings = providers.get(QWEN_PROVIDER_ID) or {}
            openai_api_key = str(qwen_provider_settings.get('api_key') or '').strip()

        if openai_api_key == '':
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = openai_api_key

        claude_provider_settings = providers.get(CLAUDE_PROVIDER_ID) or {}
        anthropic_api_key = str(claude_provider_settings.get('api_key') or '').strip()
        if anthropic_api_key == '':
            os.environ.pop('ANTHROPIC_API_KEY', None)
        else:
            os.environ['ANTHROPIC_API_KEY'] = anthropic_api_key

    def _validate_and_normalize(self, settings_dict: dict[str, Any]) -> dict[str, Any]:
        active_provider = normalize_provider_id(settings_dict.get('active_provider'))
        if active_provider not in get_provider_ids():
            raise SettingsValidationError('Invalid active_provider value.')

        providers_raw = settings_dict.get('providers')
        if not isinstance(providers_raw, dict):
            raise SettingsValidationError('Invalid providers payload: expected dict.')

        providers: dict[str, dict[str, Any]] = {}
        for provider_id in get_provider_ids():
            providers[provider_id] = self._validate_provider_settings(provider_id, providers_raw.get(provider_id))

        runtime_settings = self._validate_runtime_settings(settings_dict.get('runtime'))
        appearance_settings = self._validate_appearance_settings(settings_dict.get('appearance'))
        advanced_settings = self._validate_advanced_settings(settings_dict.get('advanced'))

        return {
            'active_provider': active_provider,
            'providers': providers,
            'runtime': runtime_settings,
            'appearance': appearance_settings,
            'advanced': advanced_settings,
        }

    def _validate_provider_settings(self, provider_id: str, provider_settings: Any) -> dict[str, Any]:
        normalized_provider_id = normalize_provider_id(provider_id)
        default_provider_settings = copy.deepcopy(DEFAULT_PROVIDER_SETTINGS[normalized_provider_id])

        if provider_settings is None:
            provider_settings = {}
        if not isinstance(provider_settings, dict):
            raise SettingsValidationError(f'Invalid provider settings for {normalized_provider_id}: expected dict.')

        merged_provider_settings = self._deep_merge(default_provider_settings, provider_settings)
        api_key = str(merged_provider_settings.get('api_key') or '').strip()
        base_url = self._validate_url(
            merged_provider_settings.get('base_url'),
            fallback_value=get_default_base_url_for_provider(normalized_provider_id),
            field_name=f'{normalized_provider_id}.base_url',
        )
        model_name = str(merged_provider_settings.get('model') or '').strip()
        if model_name == '':
            raise SettingsValidationError(f'Invalid {normalized_provider_id}.model: empty value.')

        normalized_provider_settings: dict[str, Any] = {
            'api_key': api_key,
            'base_url': base_url,
            'model': model_name,
        }

        if normalized_provider_id == OPENAI_PROVIDER_ID:
            reasoning_settings = merged_provider_settings.get('reasoning')
            if not isinstance(reasoning_settings, dict):
                raise SettingsValidationError('Invalid openai.reasoning payload: expected dict.')

            enabled = reasoning_settings.get('enabled', False)
            if not isinstance(enabled, bool):
                raise SettingsValidationError('Invalid openai.reasoning.enabled: expected bool.')

            depth = str(reasoning_settings.get('depth') or DEFAULT_REASONING_DEPTH).strip().lower()
            if depth not in SUPPORTED_REASONING_DEPTHS:
                raise SettingsValidationError('Invalid openai.reasoning.depth value.')

            normalized_provider_settings['reasoning'] = {
                'enabled': enabled,
                'depth': depth,
            }
            return normalized_provider_settings

        if normalized_provider_id == QWEN_PROVIDER_ID:
            thinking_settings = merged_provider_settings.get('thinking')
            if not isinstance(thinking_settings, dict):
                raise SettingsValidationError('Invalid qwen.thinking payload: expected dict.')

            enabled = thinking_settings.get('enabled', False)
            if not isinstance(enabled, bool):
                raise SettingsValidationError('Invalid qwen.thinking.enabled: expected bool.')

            normalized_provider_settings['thinking'] = {
                'enabled': enabled,
            }
            return normalized_provider_settings

        if normalized_provider_id == CLAUDE_PROVIDER_ID:
            thinking_settings = merged_provider_settings.get('thinking')
            if not isinstance(thinking_settings, dict):
                raise SettingsValidationError('Invalid claude.thinking payload: expected dict.')

            enabled = thinking_settings.get('enabled', False)
            if not isinstance(enabled, bool):
                raise SettingsValidationError('Invalid claude.thinking.enabled: expected bool.')

            budget_raw = thinking_settings.get('budget_tokens', DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS)
            try:
                budget_tokens = int(budget_raw)
            except Exception as exc:
                raise SettingsValidationError('Invalid claude.thinking.budget_tokens: expected integer.') from exc
            if budget_tokens <= 0:
                raise SettingsValidationError('Invalid claude.thinking.budget_tokens: must be greater than 0.')

            normalized_provider_settings['thinking'] = {
                'enabled': enabled,
                'budget_tokens': budget_tokens,
            }
            return normalized_provider_settings

        return normalized_provider_settings

    def _validate_runtime_settings(self, runtime_settings: Any) -> dict[str, Any]:
        if runtime_settings is None:
            runtime_settings = {}
        if not isinstance(runtime_settings, dict):
            raise SettingsValidationError('Invalid runtime payload: expected dict.')

        merged_runtime_settings = self._deep_merge(DEFAULT_RUNTIME_SETTINGS, runtime_settings)

        request_timeout_raw = merged_runtime_settings.get('request_timeout_seconds', DEFAULT_REQUEST_TIMEOUT_SECONDS)
        try:
            request_timeout_seconds = float(request_timeout_raw)
        except Exception as exc:
            raise SettingsValidationError('Invalid runtime.request_timeout_seconds: expected number.') from exc

        if request_timeout_seconds < MIN_REQUEST_TIMEOUT_SECONDS or request_timeout_seconds > MAX_REQUEST_TIMEOUT_SECONDS:
            raise SettingsValidationError(
                f'Invalid runtime.request_timeout_seconds: must be between '
                f'{MIN_REQUEST_TIMEOUT_SECONDS} and {MAX_REQUEST_TIMEOUT_SECONDS} seconds.'
            )

        play_ding_on_completion = merged_runtime_settings.get('play_ding_on_completion', True)
        if not isinstance(play_ding_on_completion, bool):
            raise SettingsValidationError('Invalid runtime.play_ding_on_completion: expected bool.')

        disable_local_step_verification = merged_runtime_settings.get('disable_local_step_verification', False)
        if not isinstance(disable_local_step_verification, bool):
            raise SettingsValidationError('Invalid runtime.disable_local_step_verification: expected bool.')

        return {
            'request_timeout_seconds': request_timeout_seconds,
            'play_ding_on_completion': play_ding_on_completion,
            'disable_local_step_verification': disable_local_step_verification,
        }

    def _validate_appearance_settings(self, appearance_settings: Any) -> dict[str, Any]:
        if appearance_settings is None:
            appearance_settings = {}
        if not isinstance(appearance_settings, dict):
            raise SettingsValidationError('Invalid appearance payload: expected dict.')

        merged_appearance_settings = self._deep_merge(DEFAULT_APPEARANCE_SETTINGS, appearance_settings)

        theme = str(merged_appearance_settings.get('theme') or '').strip()
        if theme not in SUPPORTED_THEMES:
            raise SettingsValidationError('Invalid appearance.theme value.')

        language = str(merged_appearance_settings.get('language') or '').strip()
        if language not in SUPPORTED_LANGUAGES:
            raise SettingsValidationError('Invalid appearance.language value.')

        return {
            'theme': theme,
            'language': language,
        }

    def _validate_advanced_settings(self, advanced_settings: Any) -> dict[str, Any]:
        if advanced_settings is None:
            advanced_settings = {}
        if not isinstance(advanced_settings, dict):
            raise SettingsValidationError('Invalid advanced payload: expected dict.')

        merged_advanced_settings = self._deep_merge(DEFAULT_ADVANCED_SETTINGS, advanced_settings)

        custom_llm_instructions = str(merged_advanced_settings.get('custom_llm_instructions') or '').strip()
        save_model_prompt_images = merged_advanced_settings.get('save_model_prompt_images', False)
        if not isinstance(save_model_prompt_images, bool):
            raise SettingsValidationError('Invalid advanced.save_model_prompt_images: expected bool.')

        save_prompt_text_dumps = merged_advanced_settings.get('save_prompt_text_dumps', False)
        if not isinstance(save_prompt_text_dumps, bool):
            raise SettingsValidationError('Invalid advanced.save_prompt_text_dumps: expected bool.')

        return {
            'custom_llm_instructions': custom_llm_instructions,
            'save_model_prompt_images': save_model_prompt_images,
            'save_prompt_text_dumps': save_prompt_text_dumps,
        }

    def _validate_url(self, raw_value: Any, fallback_value: str, field_name: str) -> str:
        value = str(raw_value or fallback_value).strip()
        if value == '':
            raise SettingsValidationError(f'Invalid {field_name}: empty value.')

        parsed_url = urlparse(value)
        if parsed_url.scheme not in ('http', 'https') or parsed_url.netloc == '':
            raise SettingsValidationError(f'Invalid {field_name}: must be a valid http(s) URL.')

        return value.rstrip('/') + '/'


class ConfigStore(SettingsStore):
    pass


class Settings(SettingsStore):
    pass
