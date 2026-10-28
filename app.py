"""
Start JobTrack on your laptop:

    python app.py

Then open http://127.0.0.1:5001

All the real code lives in the jobtrack/ folder.
"""

from jobtrack import create_app

app = create_app()

if __name__ == "__main__":
    # debug comes from config: on in development, off in production
    app.run(port=5001)
