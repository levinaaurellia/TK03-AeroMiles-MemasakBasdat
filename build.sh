# Instal requirements
pip install -r requirements.txt

# Kumpulkan file statis
python manage.py collectstatic --noinput --clear

# Jalankan migrasi database
python manage.py migrate