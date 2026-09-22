import os
from django.core.wsgi import get_wsgi_application

# Replace 'your_project_name' with the actual name of your settings folder
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = get_wsgi_application()
