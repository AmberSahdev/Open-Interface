from models.gpt4o import GPT4o
from models.gpt4v import GPT4v


class ModelFactory:
    @staticmethod
    def create_model(model_name, *args):
        try:
            if model_name == 'gpt-4o' or model_name == 'gpt-4o-mini':
                return GPT4o(model_name, *args)
            elif model_name == 'gpt-4-vision-preview' or model_name == 'gpt-4-turbo':
                return GPT4v(model_name, *args)
            else:
                # Llama/Llava models will work with the standard code I wrote for GPT4V without the assitant mode features of gpt4o
                return GPT4v(model_name, *args)
        except Exception as e:
            raise ValueError(f'Unsupported model type {model_name}. Create entry in app/models/. Error: {e}')
