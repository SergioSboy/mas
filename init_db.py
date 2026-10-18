"""Optional setup for an existing dedicated PostgreSQL database.

Docker Compose initializes the fixture automatically. This script never drops
existing schemas. Database and reader role must already exist.
"""
import os
from salesbench.data import create_database
from salesbench.database import DEFAULT_ADMIN_URL

if __name__=='__main__':
    created=create_database(os.getenv('DATABASE_ADMIN_URL',DEFAULT_ADMIN_URL))
    print('Учебная схема создана.' if created else 'Схема salesbench уже существует. Данные оставлены без изменений.')
