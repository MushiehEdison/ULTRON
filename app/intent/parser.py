import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

from app.intent.schema import (
    ALLOWED_COMMANDS,
    COMMAND_ARGUMENTS,
    validate_command,
)
DEFAULT_MODEL = "openai/gpt-oss-20b"
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
   
    if not api_key:
        raise ValueError("GROQ_API_KEY environment is not set.")

    return Groq(api_key=api_key)


def build_system_prompt():
    """
    Build the instructions given to the LLM.
    """

    commands = []

    for command in sorted(ALLOWED_COMMANDS):
        arguments = COMMAND_ARGUMENTS[command]
        commands.append(
            f"- {command}: arguments = {arguments}"
        )

    command_list = "\n".join(commands)

    return f"""
You are the intent parser for Project Ultron,
a voice-controlled PC automation system.

Your job is to convert the user's natural-language request
into ONE structured JSON command.

You MUST ONLY use commands from this approved list:

{command_list}

SAFETY RULES:

1. Never invent a command.

2. Never force an unsupported request into an existing command.

3. Only select a command when the user's request clearly
   matches the meaning and purpose of that command.

4. If the request does not clearly match one of the approved
   commands, return an unsupported result:

{{
    "function": null,
    "args": {{}}
}}

5. Do NOT use type_text as a fallback for unsupported requests.

6. Do NOT use web_search as a fallback for unsupported requests.

7. Do NOT use open_app as a fallback for unsupported requests.

8. Do NOT use open_file as a fallback for unsupported requests.

9. Do NOT use change_setting as a fallback for unsupported requests.

Examples:

User:
Open Chrome

Response:
{{
    "function": "open_app",
    "args": {{
        "name": "Chrome"
    }}
}}

User:
Search for cats on Chrome

Response:
{{
    "function": "web_search",
    "args": {{
        "app": "Chrome",
        "query": "cats"
    }}
}}

User:
Type hello world

Response:
{{
    "function": "type_text",
    "args": {{
        "text": "hello world"
    }}
}}

User:
Open my report PDF

Response:
{{
    "function": "open_file",
    "args": {{
        "path": "my report.pdf"
    }}
}}

User:
Change the brightness to 50 percent

Response:
{{
    "function": "change_setting",
    "args": {{
        "key": "brightness",
        "value": "50 percent"
    }}
}}

Unsupported requests:

User:
Delete Firefox

Response:
{{
    "function": null,
    "args": {{}}
}}

User:
Call John

Response:
{{
    "function": null,
    "args": {{}}
}}

User:
Send money to John

Response:
{{
    "function": null,
    "args": {{}}
}}

User:
Open my bank account balance

Response:
{{
    "function": null,
    "args": {{}}
}}

User:
Shutdown the computer

Response:
{{
    "function": null,
    "args": {{}}
}}

Return ONLY valid JSON.
"""


def parse_command(text, model=None):
    """
    Convert natural-language text into a validated
    structured Ultron command using Groq.

    Returns:
        A validated command dictionary for supported requests.

        None for unsupported requests.
    """

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input text cannot be empty.")

    client = get_groq_client()

    model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": build_system_prompt(),
            },
            {
                "role": "user",
                "content": text.strip(),
            },
        ],
        response_format={
            "type": "json_object"
        },
        temperature=0,
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Groq returned an empty response.")

    try:
        command_data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("Groq returned invalid JSON.") from error

  
    if command_data.get("function") is None:
        return None

  
    validate_command(command_data)

    return command_data