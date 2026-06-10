import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legaldocuman.app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '0').lower() in {'1', 'true', 'yes'}
    app.run(host='0.0.0.0', port=5000, debug=debug)