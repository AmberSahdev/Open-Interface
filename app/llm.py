from pathlib import Path
from typing import Any

from models.catalog import DEFAULT_MODEL_NAME, OPENAI_PROVIDER_ID
from models.factory import ModelFactory
from prompting.constants import PROMPT_SCHEMA_VERSION
from prompting.system_context import build_system_context
from utils import local_info
from utils.settings import Settings

MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARACTERS = 6000

HISTORY_ROLE_LABELS = {
    'assistant': 'Assistant',
    'system': 'System',
    'user': 'User',
}


def build_user_request_with_history(
    original_user_request: str,
    session_messages: list[dict[str, Any]],
) -> str:
    history_messages = build_session_history_snapshot(session_messages)
    if len(history_messages) == 0:
        return original_user_request

    history_lines = ['Recent conversation history:']
    for message in history_messages:
        history_lines.append(
            f"{HISTORY_ROLE_LABELS[message['role']]}: {message['content']}"
        )

    history_lines.append('')
    history_lines.append('Current user request:')
    history_lines.append(original_user_request)

    return '\n'.join(history_lines)


def build_session_history_snapshot(
    session_messages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return _get_bounded_history_messages(session_messages)


def _get_bounded_history_messages(
    session_messages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    relevant_messages: list[dict[str, str]] = []

    for message in session_messages:
        role = str(message.get('role') or '').lower()
        content = str(message.get('content') or '').strip()

        if role not in HISTORY_ROLE_LABELS or content == '':
            continue

        relevant_messages.append({
            'role': role,
            'content': content,
        })

    relevant_messages = relevant_messages[-MAX_HISTORY_MESSAGES:]

    bounded_messages: list[dict[str, str]] = []
    total_characters = 0

    for message in reversed(relevant_messages):
        message_size = len(message['content']) + len(message['role']) + 2

        if len(bounded_messages) > 0 and total_characters + message_size > MAX_HISTORY_CHARACTERS:
            break

        if message_size > MAX_HISTORY_CHARACTERS:
            truncated_message = dict(message)
            truncated_message['content'] = truncated_message['content'][-MAX_HISTORY_CHARACTERS:]
            bounded_messages.append(truncated_message)
            break

        bounded_messages.append(message)
        total_characters += message_size

    bounded_messages.reverse()
    return bounded_messages


class LLM:
    """
    LLM Request
    {
    	"original_user_request": ...,
    	"step_num": ...,
    	"screenshot": ...
    }

    step_num is the count of times we've interacted with the LLM for this user request.
        If it's 0, we know it's a fresh user request.
    	If it's greater than 0, then we know we are already in the middle of a request.
    	Therefore, if the number is positive and from the screenshot it looks like request is complete, then return an
    	    empty list in steps and a string in done. Don't keep looping the same request.

    Expected LLM Response
    {
    	"steps": [
    		{
    			"function": "...",
    			"parameters": {
    				"key1": "value1",
    				...
    			},
    			"human_readable_justification": "..."
    		},
    		{...},
    		...
    	],
    	"done": ...
    }

    function is the function name to call in the executer.
    parameters are the parameters of the above function.
    human_readable_justification is what we can use to debug in case program fails somewhere or to explain to user why we're doing what we're doing.
    done is null if user request is not complete, and it's a string when it's complete that either contains the
        information that the user asked for, or just acknowledges completion of the user requested task. This is going
        to be communicated to the user if it's present.
    """

    def __init__(self):
        self.settings_store = Settings()
        self.settings_dict: dict[str, Any] = self.settings_store.get_dict()
        self.model_settings_dict = self.settings_store.get_model_runtime_settings(self.settings_dict)
        provider_id, model_name, base_url, api_key = self.get_settings_values()

        self.provider_id = provider_id
        self.model_name = model_name
        self.base_system_rules = self.read_context_txt_file()
        context = self.build_system_context_text()

        self.model = ModelFactory.create_model(
            self.model_name,
            api_key,
            base_url,
            context,
            provider_id=self.provider_id,
        )
        self.sync_model_runtime_settings()
        self.sync_prompt_runtime_data()

    def sync_model_runtime_settings(self) -> None:
        set_runtime_settings = getattr(self.model, 'set_runtime_settings', None)
        if callable(set_runtime_settings):
            set_runtime_settings(self.model_settings_dict)

    def sync_prompt_runtime_data(self) -> None:
        set_prompt_runtime_data = getattr(self.model, 'set_prompt_runtime_data', None)
        if not callable(set_prompt_runtime_data):
            return

        prompt_runtime_data = {
            'base_system_rules': self.base_system_rules,
            'custom_instructions': str(self.model_settings_dict.get('custom_llm_instructions') or ''),
            'machine_profile': self.build_machine_profile(),
            'prompt_schema_version': PROMPT_SCHEMA_VERSION,
            'save_prompt_text_dumps': bool(self.model_settings_dict.get('save_prompt_text_dumps', False)),
        }
        set_prompt_runtime_data(prompt_runtime_data)

    def get_settings_values(self) -> tuple[str, str, str, str]:
        provider_id = str(self.model_settings_dict.get('provider_id') or OPENAI_PROVIDER_ID).strip()
        model_name = str(self.model_settings_dict.get('model') or DEFAULT_MODEL_NAME).strip()
        base_url = str(self.model_settings_dict.get('base_url') or '').rstrip('/') + '/'
        api_key = str(self.model_settings_dict.get('api_key') or '')
        return provider_id, model_name, base_url, api_key

    def read_context_txt_file(self) -> str:
        path_to_context_file = Path(__file__).resolve().parent.joinpath('resources', 'context.txt')
        return path_to_context_file.read_text(encoding='utf-8')

    def build_system_context_text(self) -> str:
        self.settings_dict = self.settings_store.get_dict()
        self.model_settings_dict = self.settings_store.get_model_runtime_settings(self.settings_dict)
        return build_system_context(
            base_rules_text=self.base_system_rules,
            schema_version=PROMPT_SCHEMA_VERSION,
            custom_instructions=str(self.model_settings_dict.get('custom_llm_instructions') or ''),
        )

    def build_machine_profile(self) -> dict[str, Any]:
        return {
            'operating_system': str(local_info.operating_system or '').strip(),
            'installed_apps': list(local_info.locally_installed_apps),
        }

    def get_instructions_for_objective(
        self,
        original_user_request: str,
        step_num: int = 0,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.model.context = self.build_system_context_text()
        self.sync_model_runtime_settings()
        self.sync_prompt_runtime_data()
        return self.model.get_instructions_for_objective(
            original_user_request,
            step_num,
            request_context=request_context,
        )

    def begin_request(self) -> None:
        reset_method = getattr(self.model, 'reset_for_new_request', None)
        if callable(reset_method):
            reset_method()

    def build_user_request_with_history(
        self,
        original_user_request: str,
        session_messages: list[dict[str, Any]],
    ) -> str:
        return build_user_request_with_history(original_user_request, session_messages)

    def _get_bounded_history_messages(
        self,
        session_messages: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        return build_session_history_snapshot(session_messages)

    def cleanup(self):
        self.model.cleanup()
