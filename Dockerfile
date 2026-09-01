# Imagen de la API. El `dockerfile` que había antes estaba vacío (0 bytes),
# así que cualquier build fallaba.
#
#   docker build -t tienda-api .
#   docker run --rm -p 8000:8000 --env-file .env tienda-api
#
# Las migraciones SÍ se corren en el arranque (ver el CMD del final).
#
# Antes no: la idea era correrlas aparte, porque dos instancias
# arrancando a la vez son dos `alembic upgrade head` compitiendo sobre la
# misma base. Pero en Render con runtime Docker no hay dónde ponerlas:
# el campo "Pre-Deploy Command", que es el lugar correcto, es de plan
# pago, y el "Docker Command" del panel rompe las comillas de un
# `sh -c` anidado.
#
# Con una sola instancia (plan free, WEB_CONCURRENCY=1) no hay carrera
# posible, así que va acá. Si algún día corren varias instancias, esto
# hay que sacarlo de nuevo y mover las migraciones al Pre-Deploy Command.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /code

# Se copian primero los requirements para que Docker reuse la capa de
# dependencias mientras solo cambie el código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Sin esto el proceso corre como root dentro del contenedor.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

# `sh -c` para que $PORT se expanda: Render (y varios PaaS) asignan el
# puerto por variable de entorno, no siempre es el 8000.
#
# Al ir acá y no en el panel de Render, las comillas las controla este
# archivo y no la interfaz web — que fue justo lo que falló antes con
# "sh: 1: ...: not found". El campo "Docker Command" de Render tiene que
# quedar VACÍO para que mande este CMD.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main_app:app --host 0.0.0.0 --port ${PORT}"]
