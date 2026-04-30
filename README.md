# systema2

A small to-do REST API built with **FastAPI** and **SQLModel**, backed by SQLite.
Managed with **uv**.

## Features

- Tasks and Projects, with tasks optionally linked to a project
- Task priority (**H**igh / **M**edium / **L**ow, default Medium)
- Optional task due date (ISO `YYYY-MM-DD`); overdue tasks highlighted
- CRUD endpoints for both; deleting a project unlinks its tasks
- `/tasks?project_id=N`, `?unassigned=true`, `?priority=H`, `?due_before=YYYY-MM-DD` filters
- Automatic request validation via Pydantic/SQLModel schemas
- Auto-generated OpenAPI docs at `/docs` and `/redoc`
- SQLite database auto-created on startup via a FastAPI lifespan handler
- Typer CLI (with a `project` sub-app) and Textual TUI (projects sidebar +
  tasks pane) that share the same CRUD code
- Three runtime modes (`local` · `client` · `server`) switched via env var

## Requirements

- Python **>=3.13** (tested on 3.13 and 3.14)
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
git clone <your-remote> systema2
cd systema2
uv sync          # creates .venv and installs all deps from uv.lock
```

## Running

### CLI / TUI (local mode — default)

```bash
# Tasks
uv run systema2 create "buy milk" -d "2L, semi-skimmed"
uv run systema2 list
uv run systema2 update 1 --completed
uv run systema2 delete 1 --yes

# Projects
uv run systema2 project create "home" -d "Household chores"
uv run systema2 project list
uv run systema2 project show 1 --with-tasks

# Link a task to a project
uv run systema2 create "clean fridge" -p 1
uv run systema2 list -p 1          # filter by project
uv run systema2 list --unassigned  # tasks with no project
uv run systema2 update 2 --clear-project

# Task priority (H/M/L, default M)
uv run systema2 create "ship it" -P H
uv run systema2 update 1 -P L
uv run systema2 list -P H          # filter by priority

# Due date (YYYY-MM-DD, optional)
uv run systema2 create "review PR" -D 2030-05-15
uv run systema2 update 1 -D 2030-06-01
uv run systema2 update 1 --clear-due
uv run systema2 list --due-before 2030-12-31

# TUI
uv run systema2 tui
```

The TUI ships with the **Tokyo Night** colour theme (Textual built-in).
Press `ctrl+p` and pick another theme at runtime if you prefer a different
palette.

#### TUI keybindings (vim-style)

| Key                    | Action                                       |
|------------------------|----------------------------------------------|
| `a`                    | **a**dd task                                 |
| `i`                    | ed**i**t task (vim insert)                   |
| `x`                    | delete task (vim delete-char)                |
| `space`                | toggle task done / not done                  |
| `o`                    | **o**pen new project (vim open-line)         |
| `I`                    | edit project                                 |
| `X`                    | delete project                               |
| `j` / `k`              | move cursor down / up                        |
| `g` / `G`              | jump to first / last row                     |
| `ctrl+d` / `ctrl+u`    | half-page down / up                          |
| `ctrl+w`               | switch pane (tasks ↔ projects sidebar)       |
| `w`                    | open the whiteboard picker                   |
| `r`                    | refresh                                      |
| `q`                    | quit                                         |

Inside modal dialogs the usual text-editing keys apply; `ctrl+s` saves
and `escape` cancels.

#### Whiteboards

The TUI also ships a lightweight whiteboard editor. Press `w` from the
main task screen to open the picker, then pick a board or press `n` to
create a new one.

The board is a fixed-size character grid. Boxes are drawn with Unicode
box-drawing glyphs; connectors between two boxes are routed as
orthogonal L-shaped poly-lines with an arrowhead at the target end.
Boxes are drawn on top of connectors so outlines stay clean.

| Key                         | Action                                           |
|-----------------------------|--------------------------------------------------|
| `n`                         | create a new box                                 |
| `h` / `j` / `k` / `l`       | move the selected box by 1 cell                  |
| `H` / `J` / `K` / `L`       | move the selected box by 5 cells                 |
| `tab` / `shift+tab`         | cycle selection between boxes                    |
| `c`                         | start a connector from the selected box;         |
|                             | press `c` again on the target box to commit      |
|                             | (or on the same box again to cancel)             |
| `x`                         | delete the selected box (and its connectors)     |
| `r`                         | rename the selected box                          |
| `q` / `escape`              | leave the whiteboard                             |

Whiteboards, boxes, and connectors are persisted as separate tables
(`whiteboard`, `box`, `connector`) in the same SQLite database used by
tasks and projects.

### Server

```bash
SYSTEMA2_MODE=server uv run systema2 serve --host 127.0.0.1 --port 8000
# or equivalently:
uv run main.py
```

Interactive docs:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc:      <http://127.0.0.1:8000/redoc>
- OpenAPI:    <http://127.0.0.1:8000/openapi.json>

### Client mode (CLI/TUI over HTTP)

Point the CLI/TUI at a running server instead of the local SQLite file:

```bash
export SYSTEMA2_MODE=client
export SYSTEMA2_API_URL=http://127.0.0.1:8000
uv run systema2 list
uv run systema2 tui
```

### Modes

| `SYSTEMA2_MODE` | CRUD backend                         | Uses DB? |
|-----------------|--------------------------------------|----------|
| `local` (default) | Direct SQLModel → SQLite           | yes      |
| `server`        | Direct SQLModel → SQLite + serves API | yes      |
| `client`        | HTTP calls to `SYSTEMA2_API_URL`     | no       |

Other env vars: `SYSTEMA2_API_URL` (default `http://127.0.0.1:8000`),
`SYSTEMA2_HOST`, `SYSTEMA2_PORT`, `SYSTEMA2_API_KEY`.

### Authentication (client ↔ server)

When `SYSTEMA2_API_KEY` is set **on the server**, every request to
`/tasks` and `/projects` must present the shared secret. The `/`
health endpoint stays open so probes and reverse proxies still work.

Generate a strong shared secret (uses `secrets.token_urlsafe`, 256
bits of entropy by default):

```bash
uv run systema2 gen-api-key                # prints the key on stdout
uv run systema2 gen-api-key --export       # prints `export SYSTEMA2_API_KEY=...`
uv run systema2 gen-api-key --bytes 64     # more entropy

# Typical wiring:
export SYSTEMA2_API_KEY="$(uv run systema2 gen-api-key)"
```

Server:

```bash
export SYSTEMA2_MODE=server
export SYSTEMA2_API_KEY='s3cret'
uv run systema2 serve
```

Client (CLI / TUI): set the same value and the `HttpTaskRepository`
will forward it as `X-API-Key` on every call.

```bash
export SYSTEMA2_MODE=client
export SYSTEMA2_API_URL=http://127.0.0.1:8000
export SYSTEMA2_API_KEY='s3cret'
uv run systema2 list
```

Raw `curl` can use either header style:

```bash
curl -H 'X-API-Key: s3cret'       http://127.0.0.1:8000/tasks
curl -H 'Authorization: Bearer s3cret' http://127.0.0.1:8000/tasks
```

Responses:

- `401 Missing API key` — header absent (server also returns
  `WWW-Authenticate: X-API-Key`).
- `403 Invalid API key` — header present but value does not match.

If `SYSTEMA2_API_KEY` is **unset (or blank) on the server**, the
endpoints are unauthenticated — convenient for local dev. The client
similarly sends no header when the variable is unset, so the default
experience is unchanged.

## Project layout

```
systema2/
├── main.py                  # uvicorn entrypoint
├── pyproject.toml           # project metadata & dependencies
├── uv.lock                  # pinned dependency lockfile
├── systema2/
│   ├── __init__.py
│   ├── app.py               # FastAPI app, routes, lifespan
│   ├── database.py          # engine, session dependency, init_db
│   └── models.py            # Task + TaskCreate / TaskUpdate / TaskRead
└── systema2.db              # SQLite database (auto-created, gitignored)
```

## Data model

### `Project` (table)

| Field         | Type            | Notes                              |
|---------------|-----------------|------------------------------------|
| `id`          | `int`           | Primary key, auto-assigned         |
| `name`        | `str`           | Required, 1–200 chars, indexed     |
| `description` | `str \| None`   | Optional, up to 2000 chars         |
| `created_at`  | `datetime` (UTC)| Set on creation                    |
| `updated_at`  | `datetime` (UTC)| Updated on every successful PATCH  |

### `Task` (table)

| Field         | Type            | Notes                              |
|---------------|-----------------|------------------------------------|
| `id`          | `int`           | Primary key, auto-assigned         |
| `title`       | `str`           | Required, 1–200 chars, indexed     |
| `description` | `str \| None`   | Optional, up to 2000 chars         |
| `completed`   | `bool`          | Defaults to `false`                |
| `priority`    | `"H"`/`"M"`/`"L"` | High / Medium / Low, default `"M"` |
| `due_date`    | `date \| None`  | ISO `YYYY-MM-DD`; overdue tasks are rendered in red |
| `project_id`  | `int \| None`   | FK to `project.id`; `None` = no project |
| `created_at`  | `datetime` (UTC)| Set on creation                    |
| `updated_at`  | `datetime` (UTC)| Updated on every successful PATCH  |

Three schemas wrap each table at the API boundary
(`TaskCreate`/`TaskUpdate`/`TaskRead` and the analogous `Project*`).
Deleting a project **does not delete its tasks**; they are unlinked
(`project_id` set to `NULL`).

## API reference

Base URL: `http://127.0.0.1:8000`

| Method | Path                          | Description                         | Success              |
|--------|-------------------------------|-------------------------------------|----------------------|
| GET    | `/`                           | Health / info                       | 200                  |
| GET    | `/tasks`                      | List tasks (`?project_id=N`, `?unassigned=true`) | 200     |
| GET    | `/tasks/{id}`                 | Get one task                        | 200 / 404            |
| POST   | `/tasks`                      | Create a task                       | 201 / 400 / 422      |
| PATCH  | `/tasks/{id}`                 | Partially update a task             | 200 / 400 / 404 / 422|
| DELETE | `/tasks/{id}`                 | Delete a task                       | 204 / 404            |
| GET    | `/projects`                   | List all projects                   | 200                  |
| GET    | `/projects/{id}`              | Get one project                     | 200 / 404            |
| GET    | `/projects/{id}/tasks`        | List tasks in a project             | 200 / 404            |
| POST   | `/projects`                   | Create a project                    | 201 / 422            |
| PATCH  | `/projects/{id}`              | Partially update a project          | 200 / 404 / 422      |
| DELETE | `/projects/{id}`              | Delete a project (unlinks its tasks)| 204 / 404            |

`POST`/`PATCH` on `/tasks` with a non-existent `project_id` return **400**
with `{"detail": {"error_code": "project_not_found", "project_id": N}}`.

### Create a task

```bash
curl -X POST http://127.0.0.1:8000/tasks \
     -H 'Content-Type: application/json' \
     -d '{"title": "buy milk", "description": "2L, semi-skimmed"}'
```

```json
{
  "id": 1,
  "title": "buy milk",
  "description": "2L, semi-skimmed",
  "completed": false,
  "created_at": "2026-04-25T23:28:06.279831",
  "updated_at": "2026-04-25T23:28:06.279843"
}
```

### List tasks

```bash
curl http://127.0.0.1:8000/tasks
```

### Get one task

```bash
curl http://127.0.0.1:8000/tasks/1
```

Returns `404` with `{"detail": "Task not found"}` if the id does not exist.

### Update a task (partial)

Any subset of fields may be provided; omitted fields are untouched.

```bash
curl -X PATCH http://127.0.0.1:8000/tasks/1 \
     -H 'Content-Type: application/json' \
     -d '{"completed": true}'
```

### Delete a task

```bash
curl -X DELETE http://127.0.0.1:8000/tasks/1
```

Responds with `204 No Content` on success.

## Development

Install dev dependencies (already in the lockfile, pulled in by `uv sync`):

- `httpx` — used for `fastapi.testclient.TestClient`

### Smoke-testing the API without a running server

```python
from fastapi.testclient import TestClient
from systema2.app import app

with TestClient(app) as c:   # context manager triggers startup/shutdown
    r = c.post("/tasks", json={"title": "write docs"})
    print(r.status_code, r.json())
```

### Adding dependencies

```bash
uv add <package>             # runtime dep
uv add --dev <package>       # dev-only dep
```

### Resetting the database

The SQLite file is created automatically on next startup:

```bash
rm -f systema2.db
```

## Releases

Cutting a release is tag-driven. The `release` GitHub Actions workflow
runs the full test suite, builds sdist + wheel with `uv build`, and
publishes to PyPI using [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC — no API tokens). It also attaches the built artifacts to a
GitHub Release.

To cut a new release:

```bash
# 1. Bump the version in pyproject.toml (must match the tag below).
# 2. Commit and push to master.
# 3. Tag and push:
git tag v0.2.0
git push origin v0.2.0
```

The workflow refuses to publish if the tag doesn't match
`project.version` in `pyproject.toml`.

One-time PyPI setup (per project, done via the PyPI UI):

1. Register the project name on PyPI.
2. In the project's "Publishing" settings, add a **Trusted Publisher**
   with:
   - Owner: `rodrigokimura`
   - Repository: `systema2`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. Create a matching GitHub environment named `pypi` (Settings →
   Environments) with any required protection rules.

## License

MIT — see [LICENSE](./LICENSE).
