an experiment on banning words in Jinja2 templates and Python source files.
## Jinja2

Configure banned words in `app.py`:
```python
app.jinja_env.banned_words = {"secret", "password", "admin"}
```


in jinja template (denied word is "admin")
```jinja
<p>admin is the username</p>
```

in jinja template ('secret' is allowed as an argument to call a function)
```jinja
{{ helper_function("secret") }}
```
Banned words in template text raise an error; words inside function call arguments are allowed.

## Python AST (`ast_utils.py`)

Print the structural flow of a `.py` file:
```bash
python ast_utils.py app.py
```

Check for banned words — raises `BannedWordError` listing every violation before printing:
```bash
python ast_utils.py app.py --ban secret password admin
```

Programmatic use:
```python
from ast_utils import print_flow, BannedWordError

print_flow("app.py", banned_words={"secret", "password"})
```
