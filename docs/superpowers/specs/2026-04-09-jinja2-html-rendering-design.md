# Jinja2 HTML Rendering Design

**Date:** 2026-04-09

## Overview

Add HTML rendering alongside the existing JSON API using Jinja2 templates. Two new routes return HTML pages for listing and viewing items. Existing JSON endpoints are unchanged.

## Routes

| Route | Method | Description |
|---|---|---|
| `/items/html` | GET | Renders all items in an HTML table |
| `/items/<id>/html` | GET | Renders a single item detail page; 404 if not found |

## File Structure

```
templates/
  items.html   — list page
  item.html    — detail page
app.py         — two new route handlers added
```

## Templates

- `templates/items.html`: HTML page with a table of all items showing `id` and `config` (JSON-formatted). Each row links to the item's detail page.
- `templates/item.html`: Shows item `id` and pretty-printed `config`. Includes a back link to the list.
- Minimal inline styling only. No external CSS dependencies.

## Dependencies

None. Jinja2 is bundled with Flask and already installed.

## Constraints

- JSON API routes (`/items`, `/items/<id>`) are not modified.
- No new packages required.
