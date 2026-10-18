# Инициализация PostgreSQL

Compose использует `postgres:17-alpine`. На новом томе сначала выполняется `01_roles.sql`, затем `02_seed.sql`. Первый скрипт создаёт отдельную роль чтения. Второй загружает ту же учебную фикстуру, которую использует `salesbench/data.py` в тестах.

Seed можно пересоздать после изменения фикстуры, через контейнер приложения:

```bash
docker compose run --rm --no-deps --entrypoint python app -c "from salesbench.data import bootstrap_sql; print(bootstrap_sql(), end='')" > db/02_seed.sql
```

Это меняет только SQL-файл, не содержимое уже работающей базы. Не используйте эти скрипты в рабочей базе с чужими данными. Пароли здесь открытые учебные. Доступ с хоста ограничен `127.0.0.1:55432`.

Роль владельца создаёт схему и данные. Агенты используют только `salesbench_reader`. Они не получают строку подключения в промптах, а отчёт хранит только тип и версию PostgreSQL, имя схемы и количество записей.

Справка: [транзакции READ ONLY и statement_timeout PostgreSQL](https://www.postgresql.org/docs/current/runtime-config-client.html), [подключения psycopg 3](https://www.psycopg.org/psycopg3/docs/basic/usage.html).
