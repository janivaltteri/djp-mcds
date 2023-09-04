# djp-mcds
django-postgres-manual-chamber-data-server

## What you need in addition to these files

1. `.djpmcds.env.dev`

Contains environmental variables for the web app. These are:

```
POSTGRES_HOST=
POSTGRES_NAME=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_PORT=5432
MEDIA_ROOT="/opt/djpmcds/files/"
SECRET_KEY=
```

2. `.celery.env.dev`

```
POSTGRES_HOST=
POSTGRES_NAME=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_PORT=5432
MEDIA_ROOT="/opt/djpmcds/files/"
```

3. `.postgres.env.dev`

```
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
```

4. Change the contents of `userlist.json`

The included example list creates two users, `tester` and `autotrimmer`. The `autotrimmer` is required, and must not be removed, but you might want to change the users password.

5. Check settings for production if needed

Your host name should be listed in `djpmcds/djpmcds/settings.py` `ALLOWED_HOSTS`.

Also in `settings.py` switch `Debug=False`.

In `docker-compose.yml` remove the `python manage.py runserver 0.0.0.0:8000` line, uncomment the other command line and set arguments according to your needs.
