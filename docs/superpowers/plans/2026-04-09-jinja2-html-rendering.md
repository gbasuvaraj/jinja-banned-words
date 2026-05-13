# Jinja2 HTML Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two HTML routes (`/items/html` and `/items/<id>/html`) that render Jinja2 templates alongside the existing JSON API.

**Architecture:** Two new route handlers are added to `app.py`. Flask's built-in Jinja2 support is used via `render_template`. Templates live in `templates/` (Flask's default lookup path).

**Tech Stack:** Flask 3.1.0, Jinja2 (bundled with Flask), SQLite via Flask-SQLAlchemy

---

### Task 1: Create the items list template

**Files:**
- Create: `templates/items.html`

- [ ] **Step 1: Create the templates directory and items list template**

Create `templates/items.html` with this content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Items</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 16px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
    th { background: #f4f4f4; }
    a { color: #0066cc; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <h1>Items</h1>
  {% if items %}
  <table>
    <thead>
      <tr><th>ID</th><th>Config</th></tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr>
        <td><a href="/items/{{ item.id }}/html">{{ item.id }}</a></td>
        <td><pre>{{ item.config | tojson(indent=2) }}</pre></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No items found.</p>
  {% endif %}
</body>
</html>
```

---

### Task 2: Create the item detail template

**Files:**
- Create: `templates/item.html`

- [ ] **Step 1: Create the item detail template**

Create `templates/item.html` with this content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Item {{ item.id }}</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 16px; }
    pre { background: #f4f4f4; padding: 16px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; }
    a { color: #0066cc; }
  </style>
</head>
<body>
  <p><a href="/items/html">&larr; Back to list</a></p>
  <h1>Item {{ item.id }}</h1>
  <h2>Config</h2>
  <pre>{{ item.config | tojson(indent=2) }}</pre>
</body>
</html>
```

---

### Task 3: Add HTML routes to app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `render_template` to the Flask import**

Change line 1 of `app.py` from:

```python
from flask import Flask, request, jsonify
```

to:

```python
from flask import Flask, request, jsonify, render_template
```

- [ ] **Step 2: Add the two HTML route handlers**

Add these two functions to `app.py` after the existing `get_item` route (after line 45):

```python
@app.route("/items/html", methods=["GET"])
def list_items_html():
    items = Item.query.all()
    return render_template("items.jinja2", items=items)


@app.route("/items/<int:item_id>/html", methods=["GET"])
def get_item_html(item_id):
    item = db.get_or_404(Item, item_id)
    return render_template("item.jinja2", item=item)
```

- [ ] **Step 3: Verify the app starts without errors**

Run:
```bash
flask --app app.py run
```

Expected output includes:
```
 * Running on http://127.0.0.1:5000
```

No import errors or template errors on startup.

- [ ] **Step 4: Smoke test the list page**

With the app running, open `http://localhost:5000/items/html` in a browser or run:

```bash
curl -s http://localhost:5000/items/html
```

Expected: valid HTML response with an `<h1>Items</h1>` heading. If no items exist, the page shows "No items found."

- [ ] **Step 5: Smoke test the detail page**

First create an item via the JSON API:

```bash
curl -s -X POST http://localhost:5000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "value": 42}'
```

Note the returned `id` (e.g. `1`), then:

```bash
curl -s http://localhost:5000/items/1/html
```

Expected: HTML page with `<h1>Item 1</h1>` and a `<pre>` block showing the config JSON.

- [ ] **Step 6: Verify 404 on unknown item**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/items/9999/html
```

Expected output: `404`

- [ ] **Step 7: Commit**

```bash
git add app.py templates/items.jinja2 templates/item.jinja2
git commit -m "feat: add Jinja2 HTML rendering for items list and detail pages"
```
