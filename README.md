an experiment on banning words in Jinja2 templates

configuration is in app.py:
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
