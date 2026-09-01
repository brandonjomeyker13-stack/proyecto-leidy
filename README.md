# Tienda API

API del e-commerce de la tienda de bolsos: catálogo, carrito, pedidos,
pagos con Wompi y reportes de ventas. FastAPI + SQLAlchemy + PostgreSQL.

## ⚠️ Esto todavía está en montaje

El código salió de OlivoSport y se le quitó la marca vieja. **`Tienda` /
`tienda` es un placeholder**, no el nombre definitivo. Cuando se decida
el nombre real, se cambia todo de una con:

```bash
git ls-files -z | xargs -0 sed -i 's/OlivoSport/NombreReal/g; s/tienda/nombrereal/g'
```

Ojo con la segunda sustitución: `tienda` es una palabra común en español
y el `sed` de arriba también la pisa donde se usa como sustantivo normal.
Conviene revisar el `git diff` antes de commitear.

Lo que falta para que esto salga a producción:

- [ ] **Base de datos**: crear el proyecto nuevo en supabase.com y pegar
      el `DATABASE_URL` en el `.env` (y en Render). Ver `.env` para el
      formato exacto.
- [ ] **Bucket de imágenes**: en ese mismo Supabase, crear un bucket
      público llamado `product-images` y poner `SUPABASE_URL` +
      `SUPABASE_KEY` (la `service_role`, no la `anon`).
- [ ] **Repositorio**: crearlo en GitHub y conectarlo. El remote de
      OlivoSport ya se quitó, así que ahora mismo no hay ninguno:
      `git remote add origin <url>` y `git push -u origin main`.
- [ ] **Render**: desplegar con el `render.yaml` de la raíz
      (New → Blueprint) y llenar las variables marcadas `sync: false`.
- [ ] **Wompi**: cuenta propia de esta tienda. Las llaves de OlivoSport
      se borraron a propósito — si se reusan, los pagos caen en el
      dashboard de la otra tienda.
- [x] **Frontend**: en Lovable, con dominio propio `sohee.org`. Ese
      dominio ya está en `ALLOWED_ORIGINS` (`app/core/cors.py`).
      El comodín `*.lovable.app` solo funciona en local; para usar el
      preview contra la API de producción hay que prender
      `ALLOW_LOVABLE_PREVIEW=true` en Render, y apagarlo al terminar.
- [ ] **Nombre definitivo**: correr el `sed` de arriba.

## Arrancar en local

Necesitas Python 3.10+ y una base PostgreSQL.

```bash
git clone https://github.com/TU-USUARIO/TU-REPO.git
cd tienda-online

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env             # y llena DATABASE_URL y SECRET_KEY
```

Una base local rápida, si no quieres usar la de Supabase:

```bash
docker run -d --name tienda-db \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tienda \
  -p 5432:5432 postgres:16-alpine
```

Crear el esquema y levantar la API:

```bash
alembic upgrade head
uvicorn app.main_app:app --reload
```

Documentación interactiva: <http://localhost:8000/docs>.

> El `main.py` de la raíz **no** levanta la API: solo crea las tablas con
> `create_all` en una base vacía. Para el día a día usa Alembic.

## Variables de entorno

Todas se leen en `app/core/config.py` y están explicadas en
[`.env.example`](.env.example). Las únicas obligatorias son
`DATABASE_URL` y `SECRET_KEY`; sin las de Google, Supabase o Wompi la API
levanta igual, pero esos flujos quedan apagados.

En Render se cargan en Environment (no hay archivo `.env` allá).

## Migraciones (Alembic)

El esquema se versiona en `alembic/versions/`. **Nunca** se cambia la base
a mano ni con `create_all`.

```bash
alembic upgrade head                              # aplicar lo pendiente
alembic revision --autogenerate -m "que cambió"   # tras tocar un modelo
alembic downgrade -1                              # deshacer la última
alembic current                                   # en qué versión está
```

Alembic lee `DATABASE_URL` del entorno (no hay credenciales en
`alembic.ini`), así que apunta a la misma base que la app.

**Base que ya existía antes de Alembic** (la de producción, o cualquiera
donde se corrió `python main.py`): las tablas ya están, así que
`alembic upgrade head` fallaría con *table already exists*. Se marca la
migración inicial como aplicada, una sola vez:

```bash
alembic stamp f627c998be66
```

De ahí en adelante `alembic upgrade head` funciona normal.

## Tests

```bash
pytest
```

Corren contra SQLite en memoria, así que no necesitan base ni Docker.
Para correrlos contra Postgres de verdad:

```bash
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/tienda_test pytest
```

Linter (la misma versión que corre en CI):

```bash
ruff check .        # revisar
ruff check --fix .  # arreglar lo automático
```

CI (`.github/workflows/ci.yml`) corre en cada PR: `ruff`, `pytest` en
Python 3.10 y 3.12, y las migraciones contra un Postgres real.

## Crear un administrador

No hay endpoint para volverse admin (sería un agujero de seguridad). Se
hace por consola; si el email ya existe, lo promueve en vez de duplicarlo:

```bash
python -m app.scripts.create_admin admin@tienda.com "Nombre Admin" "contraseña-segura"
```

En Render: Dashboard → el servicio → pestaña **Shell** → el mismo comando.

## Cómo está organizado

```
app/
├── api/v1/        endpoints (HTTP: validar entrada, códigos de estado)
├── services/      reglas de negocio (stock, pedidos, auth, ventas)
├── repositories/  acceso a datos (queries, sin reglas de negocio)
├── models/        tablas SQLAlchemy
├── schemas/       entrada/salida Pydantic
├── core/          config, seguridad, headers, rate limit, storage, Wompi
└── db/            engine, sesión y Base declarativa
alembic/           migraciones
tests/             pytest
```

La dependencia va siempre en un sentido: `api → services → repositories →
models`. Un repositorio nunca llama a un service.

### Endpoints

| Grupo | Ruta base | Qué hace |
|---|---|---|
| auth | `/api/v1/auth` | registro, login, Google, refresh, logout, perfil |
| products | `/api/v1/products` | catálogo público; crear/editar/imágenes es solo-admin |
| categories | `/api/v1/categories` | listar (público) y crear (admin) |
| cart | `/api/v1/cart` | carrito del usuario autenticado |
| orders | `/api/v1/orders` | checkout, pagar, cancelar, entregas |
| webhooks | `/api/v1/webhooks/wompi` | eventos de Wompi (público, firmado) |
| sales | `/api/v1/sales` | reportes de ventas (solo-admin) |

### Imágenes de producto

Cada producto puede tener **de 0 a 4** imágenes (ninguna es obligatoria).
Viven en la tabla `product_images` y se suben a Supabase Storage; solo el
admin puede tocarlas.

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/products/{id}/images` | agrega imágenes (campo `files`, se puede repetir); 409 si pasa de 4 |
| DELETE | `/products/{id}/images/{image_id}` | quita una y corre las demás; también borra el archivo del bucket |
| POST | `/products/{id}/image` | *(obsoleto)* deja el producto con esa única imagen |

En la respuesta, `images` viene ordenada por `position` y `image_url` es
la primera de la lista (la principal). `image_url` ya no es una columna:
sale de la galería, así que no hay dos copias de la misma URL que se
puedan desincronizar.

## Cómo funciona la autenticación

- El **access token** (JWT, 15 min) va en `Authorization: Bearer ...`.
- El **refresh token** (30 días) va en una cookie `httpOnly`, con
  `Path=/api/v1/auth`; nunca se devuelve en el body. En la base solo se
  guarda su SHA-256.
- `POST /auth/refresh` **rota** el token: revoca el anterior y entrega uno
  nuevo. Si alguien reusa un token ya rotado, se asume robo y se revocan
  **todas** las sesiones de ese usuario.
- Admin es simplemente `is_admin` en la tabla `users`.
- `/auth/refresh` y `/auth/logout` exigen que el `Origin` sea uno de los
  dominios conocidos: como la cookie es `SameSite=None`, si no, cualquier
  página podría dispararle esas llamadas al visitante (CSRF).
- Las contraseñas van de 8 a 72 **bytes**: bcrypt ignora lo que pase de
  72 sin avisar, y ahí dos contraseñas distintas servían la una por la
  otra.

El frontend tiene que llamar con `credentials: "include"` para que la
cookie viaje; los orígenes permitidos están en `app/core/cors.py`.

### Rate limit

100 requests/minuto por IP en general, y más estricto en login, registro
y checkout. Dos cosas que hay que configurar bien al desplegar:

- `TRUSTED_PROXY_HOPS=1` en Render. Sin esto la app ve la IP del proxy y
  **todos los usuarios comparten el mismo cupo**.
- `RATE_LIMIT_STORAGE_URI` apuntando a un Redis si corres más de una
  instancia; en memoria cada una cuenta por su lado.

## Pagos con Wompi

1. `POST /orders/checkout` congela el carrito en un pedido `PENDING`,
   **reserva el stock** (con `SELECT ... FOR UPDATE`) y devuelve el
   payload firmado para abrir el Widget.
2. El cliente paga en Wompi.
3. Wompi llama a `POST /api/v1/webhooks/wompi`. Ese endpoint es público:
   lo único que lo protege es la firma con `WOMPI_EVENTS_SECRET`, más la
   validación de que el monto, la moneda y la transacción correspondan al
   pedido (la firma de Wompi **no** cubre la `reference`).
4. `APPROVED` confirma el pedido y limpia el carrito.
   `DECLINED`/`VOIDED`/`ERROR` liberan el stock reservado.

Un pedido `PENDING` que nadie pagó expira a las 2 horas y libera su stock.
Los precios y costos se congelan en cada `OrderItem`, así que cambiar el
precio de un producto no altera las ventas ya hechas.

Configurar la URL del webhook en el dashboard de Wompi:
`https://TU-DOMINIO/api/v1/webhooks/wompi`.

## Despliegue

Va en Render, con el `render.yaml` de la raíz: en Render se entra por
New → Blueprint, se conecta el repo y de ahí lee el archivo. Las
variables marcadas `sync: false` **no** viajan en el archivo (son
secretas): quedan vacías y se llenan a mano en Environment.

El blueprint arranca con:

```bash
alembic upgrade head && uvicorn app.main_app:app --host 0.0.0.0 --port $PORT
```

Las migraciones van en el `startCommand` y no en el `buildCommand`
porque el build de Render se cachea y puede no volver a correr en un
redeploy.

También hay un `Dockerfile`:

```bash
docker build -t tienda-api .
docker run --rm -p 8000:8000 --env-file .env tienda-api
```

Si desplegás por fuera del blueprint (Docker, otra plataforma), acordate
de correr `alembic upgrade head` vos mismo antes de levantar la app.
