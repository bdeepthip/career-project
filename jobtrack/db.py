"""
Database connection helper.

Before: every route opened and closed its own connection
(30+ copies of the same 3 lines, easy to forget close()).

Now: call get_db() anywhere during a request. Flask opens ONE
connection per request, stores it on `g`, and closes it
automatically when the request ends, even if an error happens.
"""

import sqlite3

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row   # rows act like dicts: row["company"]
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


@click.command("init-db")
def init_db_command():
    """Create any missing tables. Safe to run on an existing database."""
    init_db()
    click.echo("Database is ready.")


@click.command("seed")
def seed_command():
    """Add sample jobs and learning resources (skips ones that exist)."""
    from .seed_data import seed
    jobs_added, resources_added = seed(get_db())
    click.echo(f"Added {jobs_added} jobs and {resources_added} learning resources.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
