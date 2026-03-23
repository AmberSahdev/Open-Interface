"""Unit and integration tests for MiniMax model provider."""
import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

# Mock pyautogui and related GUI modules before any model imports
# These modules require X11 display which is unavailable in headless CI environments
_mock_pyautogui = MagicMock()
_mock_mouseinfo = MagicMock()
_mock_screen_module = types.ModuleType('utils.screen')
_mock_screen_module.Screen = MagicMock()

sys.modules['pyautogui'] = _mock_pyautogui
sys.modules['mouseinfo'] = _mock_mouseinfo
sys.modules['utils.screen'] = _mock_screen_module

# Mock google.genai to avoid pydantic v2 import issues in Gemini model
_mock_genai = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = _mock_genai
sys.modules['google.genai.types'] = MagicMock()

from openai import OpenAI  # noqa: E402


class TestMiniMaxModel(unittest.TestCase):
    """Unit tests for the MiniMax model class."""

    def _create_minimax(self, model_name='MiniMax-M2.7', base_url='', api_key='test-key',
                        context='test context'):
        with patch('models.model.OpenAI') as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            from models.minimax import MiniMax
            model = MiniMax(model_name, base_url, api_key, context)
            return model, mock_client, mock_openai_cls

    def test_default_base_url(self):
        """MiniMax model should use MiniMax base URL by default."""
        model, _, mock_openai_cls = self._create_minimax()
        call_args = mock_openai_cls.call_args
        self.assertEqual(call_args[1]['base_url'], 'https://api.minimax.io/v1/')

    def test_custom_base_url_preserved(self):
        """Custom non-OpenAI base URL should be preserved."""
        model, _, mock_openai_cls = self._create_minimax(
            base_url='https://custom-proxy.example.com/v1/')
        call_args = mock_openai_cls.call_args
        self.assertEqual(call_args[1]['base_url'], 'https://custom-proxy.example.com/v1/')

    def test_openai_default_url_overridden(self):
        """OpenAI default URL should be overridden to MiniMax URL."""
        model, _, mock_openai_cls = self._create_minimax(
            base_url='https://api.openai.com/v1/')
        call_args = mock_openai_cls.call_args
        self.assertEqual(call_args[1]['base_url'], 'https://api.minimax.io/v1/')

    def test_api_key_set(self):
        """API key should be passed to OpenAI client."""
        model, _, mock_openai_cls = self._create_minimax(api_key='my-minimax-key')
        call_args = mock_openai_cls.call_args
        self.assertEqual(call_args[1]['api_key'], 'my-minimax-key')

    @patch.dict(os.environ, {'MINIMAX_API_KEY': 'env-api-key'})
    def test_api_key_from_env(self):
        """API key should fall back to MINIMAX_API_KEY env var."""
        model, _, mock_openai_cls = self._create_minimax(api_key='')
        call_args = mock_openai_cls.call_args
        self.assertEqual(call_args[1]['api_key'], 'env-api-key')

    def test_model_name(self):
        """Model name should be stored correctly."""
        model, _, _ = self._create_minimax(model_name='MiniMax-M2.5-highspeed')
        self.assertEqual(model.model_name, 'MiniMax-M2.5-highspeed')

    def test_context_stored(self):
        """Context should be stored."""
        model, _, _ = self._create_minimax(context='You are a helpful assistant.')
        self.assertEqual(model.context, 'You are a helpful assistant.')

    def test_format_user_request(self):
        """format_user_request_for_llm should return text + image_url content."""
        model, _, _ = self._create_minimax()

        # Patch Screen at the module level where it's already imported
        from models import minimax as minimax_mod
        orig_screen = minimax_mod.Screen
        mock_screen_cls = MagicMock()
        mock_screen_cls.return_value.get_screenshot_in_base64.return_value = 'base64data'
        minimax_mod.Screen = mock_screen_cls

        try:
            result = model.format_user_request_for_llm('open chrome', 0)

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['type'], 'text')
            self.assertIn('open chrome', result[0]['text'])
            self.assertEqual(result[1]['type'], 'image_url')
            self.assertIn('base64data', result[1]['image_url']['url'])
        finally:
            minimax_mod.Screen = orig_screen

    def test_send_message_temperature(self):
        """send_message_to_llm should clamp temperature within (0, 1]."""
        model, mock_client, _ = self._create_minimax()
        model.send_message_to_llm([{'type': 'text', 'text': 'hello'}])

        call_args = mock_client.chat.completions.create.call_args
        temp = call_args[1]['temperature']
        self.assertGreater(temp, 0)
        self.assertLessEqual(temp, 1.0)

    def test_send_message_max_tokens(self):
        """send_message_to_llm should set max_tokens=800."""
        model, mock_client, _ = self._create_minimax()
        model.send_message_to_llm([{'type': 'text', 'text': 'test'}])

        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args[1]['max_tokens'], 800)

    def test_send_message_model_name(self):
        """send_message_to_llm should use the correct model name."""
        model, mock_client, _ = self._create_minimax(model_name='MiniMax-M2.5-highspeed')
        model.send_message_to_llm([{'type': 'text', 'text': 'test'}])

        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args[1]['model'], 'MiniMax-M2.5-highspeed')

    def test_convert_json_response(self):
        """convert_llm_response_to_json_instructions should parse JSON from response."""
        model, _, _ = self._create_minimax()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            'steps': [{'function': 'click', 'parameters': {'x': 100, 'y': 200}}],
            'done': None
        })

        result = model.convert_llm_response_to_json_instructions(mock_response)
        self.assertIn('steps', result)
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual(result['steps'][0]['function'], 'click')

    def test_convert_json_with_extra_text(self):
        """Should extract JSON even when surrounded by extra text."""
        model, _, _ = self._create_minimax()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Here is my plan:\n{"steps": [], "done": "Task complete"}\nEnd.'

        result = model.convert_llm_response_to_json_instructions(mock_response)
        self.assertEqual(result['done'], 'Task complete')
        self.assertEqual(result['steps'], [])

    def test_convert_json_strips_think_tags(self):
        """Should strip <think>...</think> tags from MiniMax thinking models."""
        model, _, _ = self._create_minimax()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '<think>Let me analyze the screenshot...</think>\n'
            '{"steps": [{"function": "press", "parameters": {"key": "enter"}}], "done": null}'
        )

        result = model.convert_llm_response_to_json_instructions(mock_response)
        self.assertIn('steps', result)
        self.assertEqual(result['steps'][0]['function'], 'press')

    def test_convert_json_handles_parse_error(self):
        """Should return empty dict on malformed JSON."""
        model, _, _ = self._create_minimax()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'No JSON here at all.'

        result = model.convert_llm_response_to_json_instructions(mock_response)
        self.assertEqual(result, {})

    def test_convert_json_nested_think_tags(self):
        """Should handle multiple or nested think tag blocks."""
        model, _, _ = self._create_minimax()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '<think>first thought</think>\n'
            '<think>second thought</think>\n'
            '{"steps": [], "done": "completed"}'
        )

        result = model.convert_llm_response_to_json_instructions(mock_response)
        self.assertEqual(result['done'], 'completed')

    def test_cleanup(self):
        """cleanup should not raise."""
        model, _, _ = self._create_minimax()
        model.cleanup()

    def test_env_var_set_on_init(self):
        """MINIMAX_API_KEY env var should be set when API key is provided."""
        model, _, _ = self._create_minimax(api_key='test-env-key')
        self.assertEqual(os.environ.get('MINIMAX_API_KEY'), 'test-env-key')


class TestMiniMaxFactory(unittest.TestCase):
    """Test that ModelFactory correctly routes MiniMax models."""

    @patch('models.model.OpenAI')
    def test_factory_creates_minimax_m27(self, mock_openai_cls):
        """ModelFactory should create MiniMax instance for MiniMax-M2.7."""
        mock_openai_cls.return_value = MagicMock()
        from models.factory import ModelFactory
        from models.minimax import MiniMax
        model = ModelFactory.create_model('MiniMax-M2.7', '', 'key', 'ctx')
        self.assertIsInstance(model, MiniMax)

    @patch('models.model.OpenAI')
    def test_factory_creates_minimax_m25_highspeed(self, mock_openai_cls):
        """ModelFactory should create MiniMax instance for MiniMax-M2.5-highspeed."""
        mock_openai_cls.return_value = MagicMock()
        from models.factory import ModelFactory
        from models.minimax import MiniMax
        model = ModelFactory.create_model('MiniMax-M2.5-highspeed', '', 'key', 'ctx')
        self.assertIsInstance(model, MiniMax)

    @patch('models.model.OpenAI')
    def test_factory_creates_minimax_m25(self, mock_openai_cls):
        """ModelFactory should create MiniMax instance for MiniMax-M2.5."""
        mock_openai_cls.return_value = MagicMock()
        from models.factory import ModelFactory
        from models.minimax import MiniMax
        model = ModelFactory.create_model('MiniMax-M2.5', '', 'key', 'ctx')
        self.assertIsInstance(model, MiniMax)

    @patch('models.model.OpenAI')
    def test_factory_non_minimax_not_minimax(self, mock_openai_cls):
        """ModelFactory should not create MiniMax for non-MiniMax model names."""
        mock_openai_cls.return_value = MagicMock()
        from models.factory import ModelFactory
        from models.minimax import MiniMax
        model = ModelFactory.create_model('gpt-4-vision-preview', '', 'key', 'ctx')
        self.assertNotIsInstance(model, MiniMax)


class TestMiniMaxGetInstructions(unittest.TestCase):
    """Test the full get_instructions_for_objective flow."""

    def test_get_instructions_full_flow(self):
        """get_instructions_for_objective should return parsed JSON from LLM response."""
        mock_screen = MagicMock()
        mock_screen.return_value.get_screenshot_in_base64.return_value = 'fakebase64'
        _mock_screen_module.Screen = mock_screen

        with patch('models.model.OpenAI') as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            expected = {
                'steps': [
                    {
                        'function': 'click',
                        'parameters': {'x': 500, 'y': 300},
                        'human_readable_justification': 'Click on Chrome icon'
                    }
                ],
                'done': None
            }
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(expected)
            mock_client.chat.completions.create.return_value = mock_response

            from models.minimax import MiniMax
            model = MiniMax('MiniMax-M2.7', '', 'test-key', 'You are a helpful assistant.')
            result = model.get_instructions_for_objective('Open Chrome', 0)

            self.assertEqual(result['steps'][0]['function'], 'click')
            self.assertIsNone(result['done'])

        _mock_screen_module.Screen = MagicMock()

    def test_get_instructions_done_state(self):
        """Should correctly handle done state responses."""
        mock_screen = MagicMock()
        mock_screen.return_value.get_screenshot_in_base64.return_value = 'fakebase64'
        _mock_screen_module.Screen = mock_screen

        with patch('models.model.OpenAI') as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            expected = {'steps': [], 'done': 'Chrome is already open.'}
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(expected)
            mock_client.chat.completions.create.return_value = mock_response

            from models.minimax import MiniMax
            model = MiniMax('MiniMax-M2.7', '', 'test-key', 'ctx')
            result = model.get_instructions_for_objective('Open Chrome', 1)

            self.assertEqual(result['steps'], [])
            self.assertEqual(result['done'], 'Chrome is already open.')

        _mock_screen_module.Screen = MagicMock()

    def test_get_instructions_with_think_tags(self):
        """Should strip think tags in full flow."""
        mock_screen = MagicMock()
        mock_screen.return_value.get_screenshot_in_base64.return_value = 'fakebase64'
        _mock_screen_module.Screen = mock_screen

        with patch('models.model.OpenAI') as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = (
                '<think>reasoning here</think>\n'
                '{"steps": [{"function": "write", "parameters": {"string": "hello"}}], "done": null}'
            )
            mock_client.chat.completions.create.return_value = mock_response

            from models.minimax import MiniMax
            model = MiniMax('MiniMax-M2.5-highspeed', '', 'test-key', 'ctx')
            result = model.get_instructions_for_objective('Type hello', 0)

            self.assertEqual(result['steps'][0]['function'], 'write')

        _mock_screen_module.Screen = MagicMock()


class TestMiniMaxIntegration(unittest.TestCase):
    """Integration tests for MiniMax provider (require MINIMAX_API_KEY)."""

    def setUp(self):
        self.api_key = os.environ.get('MINIMAX_API_KEY', '')
        if not self.api_key:
            self.skipTest('MINIMAX_API_KEY not set')

    def test_real_api_connection(self):
        """Test that MiniMax API accepts a basic chat completion request."""
        client = OpenAI(api_key=self.api_key, base_url='https://api.minimax.io/v1/')
        response = client.chat.completions.create(
            model='MiniMax-M2.7',
            messages=[{'role': 'user', 'content': 'Say hello in one word.'}],
            max_tokens=10,
        )
        self.assertTrue(len(response.choices) > 0)
        self.assertTrue(len(response.choices[0].message.content) > 0)

    def test_real_api_m25_highspeed(self):
        """Test MiniMax-M2.5-highspeed model connectivity."""
        client = OpenAI(api_key=self.api_key, base_url='https://api.minimax.io/v1/')
        response = client.chat.completions.create(
            model='MiniMax-M2.5-highspeed',
            messages=[{'role': 'user', 'content': 'Reply OK.'}],
            max_tokens=5,
        )
        self.assertTrue(len(response.choices) > 0)

    def test_real_api_json_response(self):
        """Test that MiniMax returns a response containing valid JSON."""
        client = OpenAI(api_key=self.api_key, base_url='https://api.minimax.io/v1/')
        response = client.chat.completions.create(
            model='MiniMax-M2.7',
            messages=[{
                'role': 'user',
                'content': 'Respond with exactly this JSON and nothing else: {"steps": [], "done": "ok"}'
            }],
            max_tokens=50,
        )
        content = response.choices[0].message.content.strip()
        start = content.find('{')
        if start >= 0:
            # Use raw_decode to parse just the first JSON object
            parsed, _ = json.JSONDecoder().raw_decode(content[start:])
            self.assertIn('done', parsed)


if __name__ == '__main__':
    unittest.main()
