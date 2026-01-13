"""
Application entry point.
Run with: flask run or python -m app.main
"""
from app import create_app, db

app = create_app()


@app.cli.command('init-db')
def init_db():
    """Initialize the database tables."""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully.")


@app.cli.command('drop-db')
def drop_db():
    """Drop all database tables."""
    with app.app_context():
        db.drop_all()
        print("Database tables dropped.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
