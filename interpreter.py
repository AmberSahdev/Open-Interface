from time import sleep

import pyautogui


class Interpreter:
    def __init__(self):
        pass

    def process_commands(self, json_commands, status_queue):
        for command in json_commands:
            success = self.process_command(command, status_queue)
            if not success:
                return False

    def process_command(self, json_command, status_queue):
        function_name = json_command["function"]
        parameters = json_command.get('parameters', {})
        print(f"Now performing - {function_name} - {json_command.get('human_readable_justification')} - {parameters}")
        status_queue.put(json_command.get('human_readable_justification'))
        try:
            self.execute_function(function_name, parameters)
            return True
        except:
            print("We are having a problem executing this")
            return False

    def execute_function(self, function_name, parameters):
        """
            We are expecting only two types of function calls below
            1. time.sleep() - to wait for web pages, applications, and other things to load.
            2. pyautogui calls to interact with system's mouse and keyboard.
        """
        # Sometimes pyautogui needs warming up - i.e. sometimes first call isnt executed. So padding a random first call here.
        pyautogui.press("command", interval=0.1)

        if function_name == "sleep" and parameters.get("secs"):
            sleep(parameters.get("secs"))
        elif hasattr(pyautogui, function_name):
            # Execute the corresponding pyautogui function i.e. Keyboard or Mouse commands.
            function_to_call = getattr(pyautogui, function_name)

            # Special handling for the 'write' function
            if function_name == 'write' and ('string' in parameters or 'text' in parameters):
                # 'write' function expects a string, not a 'text' keyword argument. LLM sometimes gets confused on what to send.
                string_to_write = parameters.get('string') or parameters.get('text')
                interval = parameters.get('interval', 0.05)
                interval = 0.05
                function_to_call(string_to_write, interval=interval)
            elif function_name == 'press' and ('keys' in parameters or 'key' in parameters):
                # 'press' can take a list of keys or a single key
                # print("function_to_call is", function_to_call)
                keys_to_press = parameters.get('keys') or parameters.get('key')
                presses = parameters.get('presses', 1)
                interval = parameters.get('interval', 0.05)
                interval = 0.05
                function_to_call(keys_to_press, presses=presses, interval=interval)
            elif function_name == 'hotkey':
                # 'hotkey' function expects multiple key arguments, not a list
                function_to_call(*parameters['keys'])
            else:
                # For other functions, pass the parameters as they are
                function_to_call(**parameters)
        else:
            print(f"No such function {function_name} in our interface's interpreter")
