release: python manage.py collectstatic --noinput
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT