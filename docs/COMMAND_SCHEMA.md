# Command Schema

Every command the system is allowed to execute. The LLM can only pick from
this list — nothing else is valid.

| Command | Args | Description |
|---|---|---|
| open_app | name | Launch an application |
| web_search | app, query | Open a browser and search |
| type_text | text | Type text at the current cursor position |
| open_file | path | Open a file with its default application |
| change_setting | key, value | Change a system setting (requires confirmation) |

Add new commands here first, then implement them in `app/intent/schema.py`
and in every platform adapter.
