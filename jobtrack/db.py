"""
Database setup and commands.

  flask --app app init-db   Create or upgrade the database to the latest
                            version (runs any migrations not yet applied).
                            Safe to run any time; it never deletes data.
  flask --app app seed      Add the sample jobs and free learning resources.
  flask --app app db ...    Flask-Migrate commands, for example
                            `flask --app app db migrate -m "add column"`
                            after you change a model in models.py.

A migration is a small versioned script that changes the tables
(add a table, add a column...). The database remembers which
migrations it already ran, so every copy of GAJ, on your laptop
or in production, can be brought to the same structure safely.
"""

import os

import click
from flask_migrate import Migrate, upgrade

from .config import PROJECT_ROOT
from .models import db

MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "migrations")

migrate = Migrate(directory=MIGRATIONS_DIR)


def init_db():
    """Bring the database to the latest migration."""
    upgrade(directory=MIGRATIONS_DIR)


@click.command("init-db")
def init_db_command():
    """Create or upgrade the database. Safe to run on an existing database."""
    init_db()
    click.echo("Database is ready.")


@click.command("seed")
def seed_command():
    """Add sample jobs and learning resources (skips ones that exist)."""
    from .seed_data import seed
    jobs_added, resources_added = seed()
    click.echo(f"Added {jobs_added} jobs and {resources_added} learning resources.")


def init_app(app):
    db.init_app(app)
    migrate.init_app(app, db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
