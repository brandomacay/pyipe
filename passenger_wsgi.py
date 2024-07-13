import importlib.util
import os
import sys

# Asegúrate de que el directorio actual sea el correcto
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

# Especifica la ruta completa hacia test.py si es necesario
wsgi_spec = importlib.util.spec_from_file_location('wsgi', os.path.join(current_dir, 'app.py'))
wsgi = importlib.util.module_from_spec(wsgi_spec)
wsgi_spec.loader.exec_module(wsgi)

application = wsgi.app
