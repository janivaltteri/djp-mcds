#!/bin/sh

echo "starting djpmcds entrypoint script"

python manage.py migrate --noinput
python manage.py makemigrations mcds --noinput
python manage.py migrate --noinput

python manage.py shell --command="exec(open('create-users.py').read())"

exec "$@"
