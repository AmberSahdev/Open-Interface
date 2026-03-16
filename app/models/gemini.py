from models.gpt4v import GPT4v


class Gemini(GPT4v):
    """
    Backward-compatible alias.
    Gemini is now routed through the OpenAI-compatible SDK path.
    """
