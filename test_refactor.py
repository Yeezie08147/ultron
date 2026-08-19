import re

with open(r'C:\Ultron\Ultron\server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find the section starting with:
#                     elif action:
#                         if action["action"] == "open_terminal":

# And the section starting with:
#                     else:
#                         embedded_action = None

block_regex = re.compile(
    r'(?P<elif_action>                    elif action:\n                        if action\["action"\] == "open_terminal":.*?)(?P<else_llm>                    else:\n                        embedded_action = None.*?(?:                                        response_text = "Right away, sir\."\n))',
    re.DOTALL
)

match = block_regex.search(content)
if match:
    elif_action_block = match.group('elif_action')
    else_llm_block = match.group('else_llm')
    
    # We will swap their order and adjust indentation/logic
    # 1. The LLM block currently starts with                     else:\n
    # We want it to be:
    #                     if not action:
    #                         (LLM logic)
    #                         if embedded_action: action = embedded_action
    # 2. The execution block currently starts with                     elif action:\n
    # We want it to be:
    #                     if action:
    #                         (Execution logic)
    
    print("Match found!")
else:
    print("No match!")
