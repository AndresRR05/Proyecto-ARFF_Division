# ARFF Visualizer (minimal)

Proyecto Django mínimo para subir archivos `.arff`, generar splits (train/val/test) y mostrar gráficas de `protocol_type`.

Pasos rápidos:

1. Crear y activar un virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecutar migraciones y servidor:

```bash
python manage.py migrate
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ y subir un archivo `.arff` o pegar una URL de GitHub (raw/blob).

Despliegue en Render (rápido)
1. Añade el repositorio a Render como Web Service.
2. En Environment, configura estas variables:
	- DJANGO_SECRET_KEY = <tu secret>
	- DJANGO_DEBUG = False
	- DJANGO_ALLOWED_HOSTS = <tu-dominio-de-render.com>
3. Build Command: pip install -r requirements.txt
4. Start Command: gunicorn arff_project.wsgi --log-file -
5. Asegúrate de que `Procfile` está en el repo y que `requirements.txt` contiene `gunicorn` y `whitenoise`.

Notas:
- Por limitaciones de los planes gratuitos, evita subir archivos ARFF enormes; usa la versión 20% para pruebas.
- Considera implementar sampling o procesamiento asíncrono si necesitas manejar archivos grandes.
