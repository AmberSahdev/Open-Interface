import os
import shutil
import subprocess

def run_terminal_commands(commands):
    for command in commands:
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()


# 1. Remove previous files
directories_to_remove = ["./build", "./dist"]
for dir in directories_to_remove:
    try:
        shutil.rmtree(dir)
    except:
        pass

# 2. TODO
