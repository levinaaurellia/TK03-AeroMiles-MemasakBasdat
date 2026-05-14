#!/bin/bash

# Instal requirements dengan bypass aturan environment
python3 -m pip install -r requirements.txt --break-system-packages

# Kumpulkan file statis
python3 manage.py collectstatic --noinput --clear

# Jalankan migrasi database
python3 manage.py migrate