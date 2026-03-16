from models.catalog import (
    CLAUDE_PROVIDER_ID,
    DEFAULT_BASE_URL,
    OPENAI_PROVIDER_ID,
    QWEN_PROVIDER_ID,
    is_gemini_model,
)
from models.claude import Claude
from models.gpt4o import GPT4o
from models.gpt4v import GPT4v
from models.gpt5 import GPT5
from models.openai_computer_use import OpenAIComputerUse
from models.qwen import Qwen


class ModelFactory:
    @staticmethod
    def create_model(model_name, *args, provider_id=OPENAI_PROVIDER_ID):
        base_url, api_key, context = ModelFactory._normalize_model_args(*args)

        try:
            if provider_id == CLAUDE_PROVIDER_ID:
                return Claude(model_name, base_url, api_key, context)

            if provider_id == QWEN_PROVIDER_ID:
                return Qwen(model_name, base_url, api_key, context)

            if model_name == 'gpt-4o' or model_name == 'gpt-4o-mini':
                return GPT4o(model_name, base_url, api_key, context)

            if model_name == 'computer-use-preview':
                return OpenAIComputerUse(model_name, base_url, api_key, context)

            if model_name.startswith('gpt-5'):
                return GPT5(model_name, base_url, api_key, context)

            if model_name == 'gpt-4-vision-preview' or model_name == 'gpt-4-turbo':
                return GPT4v(model_name, base_url, api_key, context)

            if is_gemini_model(model_name):
                return GPT4v(model_name, base_url, api_key, context)

            # Llama/Llava and unknown OpenAI-compatible models use GPT4v style routing.
            return GPT4v(model_name, base_url, api_key, context)
        except Exception as e:
            raise ValueError(f'Unsupported model type {model_name}. Create entry in app/models/. Error: {e}')

    @staticmethod
    def _normalize_model_args(*args) -> tuple[str, str, str]:
        if len(args) >= 3:
            first_arg = str(args[0] or '').strip()
            second_arg = str(args[1] or '').strip()
            context = str(args[2] or '')
            if ModelFactory._is_url(first_arg):
                base_url = first_arg
                api_key = second_arg
            elif ModelFactory._is_url(second_arg):
                base_url = second_arg
                api_key = first_arg
            else:
                base_url = first_arg
                api_key = second_arg
            return ModelFactory._normalize_base_url(base_url), api_key, context

        if len(args) == 2:
            first_arg = str(args[0] or '').strip()
            second_arg = str(args[1] or '').strip()
            if first_arg.startswith('http://') or first_arg.startswith('https://'):
                return ModelFactory._normalize_base_url(first_arg), second_arg, ''
            return ModelFactory._normalize_base_url(second_arg), first_arg, ''

        if len(args) == 1:
            api_key = str(args[0] or '')
            return ModelFactory._normalize_base_url(DEFAULT_BASE_URL), api_key, ''

        return ModelFactory._normalize_base_url(DEFAULT_BASE_URL), '', ''

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = str(base_url or '').strip()
        if normalized == '':
            normalized = DEFAULT_BASE_URL
        return normalized.rstrip('/') + '/'

    @staticmethod
    def _is_url(value: str) -> bool:
        return value.startswith('http://') or value.startswith('https://')
