from typing import Any, cast

from models.catalog import (
    RECOMMENDED_QWEN_VISION_MODEL,
    is_qwen_vision_model,
    requires_qwen_reasoning,
    supports_qwen_reasoning_toggle,
)
from models.model import Model
from prompting.builder import PromptPackage


class Qwen(Model):
    def get_instructions_for_objective(
        self,
        original_user_request: str,
        step_num: int = 0,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not is_qwen_vision_model(self.model_name):
            raise ValueError(
                f'Qwen model "{self.model_name}" does not support image input. '
                f'Please choose a VL model such as "{RECOMMENDED_QWEN_VISION_MODEL}".'
            )

        return super().get_instructions_for_objective(
            original_user_request,
            step_num,
            request_context=request_context,
        )

    def format_prompt_package_for_llm(
        self,
        prompt_package: PromptPackage,
        visual_payload: dict[str, Any] | None,
        request_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if not isinstance(visual_payload, dict):
            return [
                {
                    'role': 'system',
                    'content': prompt_package.system_context,
                },
                {
                    'role': 'user',
                    'content': prompt_package.user_context,
                },
            ]

        return [
            {
                'role': 'system',
                'content': prompt_package.system_context,
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': prompt_package.user_context,
                    },
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f"data:image/png;base64,{visual_payload['annotated_image_base64']}",
                        },
                    },
                ],
            },
        ]

    def send_message_to_llm(
        self,
        message: list[dict[str, Any]],
        prompt_package: PromptPackage | None = None,
    ) -> Any:
        request_options = self.build_qwen_request_options()
        completions_client = cast(Any, self.client.chat.completions)
        response = completions_client.create(
            model=self.model_name,
            messages=message,
            max_tokens=800,
            **request_options,
        )
        self.raise_for_provider_error(response)
        return response

    def build_qwen_request_options(self) -> dict[str, Any]:
        if requires_qwen_reasoning(self.model_name):
            return {
                'extra_body': {
                    'enable_thinking': True,
                },
            }

        if supports_qwen_reasoning_toggle(self.model_name):
            return {
                'extra_body': {
                    'enable_thinking': self.enable_reasoning,
                },
            }

        return {}

    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> dict[str, Any]:
        choices = getattr(llm_response, 'choices', None) or []
        if len(choices) == 0:
            raise ValueError('Qwen 没有返回任何候选结果。')

        message = getattr(choices[0], 'message', None)
        llm_response_data = str(getattr(message, 'content', '') or '').strip()
        return self.parse_json_response_text(llm_response_data)

    def _read_grid_reference(self, visual_payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(visual_payload, dict):
            return {}

        frame_context = visual_payload.get('frame_context')
        if not isinstance(frame_context, dict):
            return {}

        grid_reference = frame_context.get('grid_reference')
        if not isinstance(grid_reference, dict):
            return {}

        return grid_reference

    def _read_logical_screen(self, visual_payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(visual_payload, dict):
            return {}

        frame_context = visual_payload.get('frame_context')
        if not isinstance(frame_context, dict):
            return {}

        logical_screen = frame_context.get('logical_screen')
        if not isinstance(logical_screen, dict):
            return {}

        return logical_screen

    def _read_captured_screen(self, visual_payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(visual_payload, dict):
            return {}

        frame_context = visual_payload.get('frame_context')
        if not isinstance(frame_context, dict):
            return {}

        captured_screen = frame_context.get('captured_screen')
        if not isinstance(captured_screen, dict):
            return {}

        return captured_screen
