import os
from typing import Any

from openai import OpenAI


class Model:
    def __init__(self, model_name, base_url, api_key, context):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.context = context
        self.client = OpenAI(api_key=api_key, base_url=base_url)

        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key

    def get_instructions_for_objective(self, *args) -> dict[str, Any]:
        pass

    def format_user_request_for_llm(self, *args):
        pass

    def convert_llm_response_to_json_instructions(self, *args) -> dict[str, Any]:
        pass

    def cleanup(self, *args):
        pass
