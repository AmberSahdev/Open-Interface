import json
from typing import Any

from google import genai
from google.genai import types
from utils.screen import Screen


class Gemini:
    def __init__(self, model_name, api_key, context):
        self.model_name = model_name
        self.api_key = api_key
        self.context = context
        self.client = genai.Client(api_key=api_key)

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        safety_settings = [
            types.SafetySetting(category=category.value, threshold="BLOCK_NONE")
            for category in types.HarmCategory
            if category.value != 'HARM_CATEGORY_UNSPECIFIED'
        ]
        message_content = self.format_user_request_for_llm(original_user_request, step_num)

        llm_response = self.client.models.generate_content(
            model=self.model_name,
            contents=message_content,
            config=types.GenerateContentConfig(safety_settings=safety_settings),
        )
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)
        return json_instructions

    def format_user_request_for_llm(self, original_user_request, step_num) -> list[Any]:
        base64_img: str = Screen().get_screenshot_in_base64()

        request_data: str = json.dumps({
            "original_user_request": original_user_request,
            "step_num": step_num,
        })

        message_content = [
            {"text": self.context + request_data + "\n\nHere is a screenshot of the user's screen:"},
            {"inline_data": {
                "mime_type": "image/jpeg",
                "data": base64_img,
            }},
        ]
        return message_content

    def convert_llm_response_to_json_instructions(self, llm_response) -> dict[str, Any]:

        llm_response_data = llm_response.text.strip()

        start_index = llm_response_data.find("{")
        end_index = llm_response_data.rfind("}")

        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f"Error while parsing JSON response - {e}")
            json_response = {}

        return json_response

    def cleanup(self):
        pass
