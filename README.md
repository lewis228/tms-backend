# FastAPI Boilerplate

Production-ready FastAPI boilerplate with authentication, RBAC, team management, and file upload infrastructure.

## Features

- **Auth** — JWT (access + refresh), OAuth (Google/Kakao/Apple), email OTP (signup/password reset)
- **RBAC** — Group-based permissions with Redis caching
- **Team** — Multi-tenant team management with member roles
- **File Upload** — MinIO/S3 presigned URL workflow
- **Database** — Async MySQL with read/write split (single dev, Primary/Replica prod)
- **Cache** — Redis with read/write split
- **Logging** — structlog with request tracing (dev: console, prod: JSON)
- **Pagination** — Cursor-based with delta sync

## Tech Stack

| Category | Stack |
|---|---|
| Framework | FastAPI 0.116, Python 3.11 |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Database | MySQL 8.0 (dev: Docker, prod: AWS RDS) |
| Cache | Redis 7.2 (dev: Docker, prod: AWS ElastiCache) |
| File Storage | MinIO (dev: Docker, prod: AWS S3) |
| Auth | PyJWT + bcrypt + OAuth 2.0 |
| Logging | structlog |

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/your-repo/boilerplate.git
cd boilerplate
cp .env.example .env  # edit values

# 2. Infrastructure
docker-compose up -d

# 3. Python environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# 4. Database migration
set PYTHONPATH=src          # Windows
# export PYTHONPATH=src     # Mac/Linux
alembic revision --autogenerate -m "initial"
alembic upgrade head

# 5. Run
uvicorn main:app --host 0.0.0.0 --port 8080 --app-dir src --reload
```

Open `http://localhost:8080/docs` for Swagger UI.

## Project Structure

```
src/
├── main.py              # FastAPI app entry
├── common/              # Shared infrastructure
│   ├── const/           # Settings, filter mapper, constants
│   ├── exceptions/      # AppException + global handlers
│   ├── middleware/       # CORS, auth, access log, request context
│   ├── lifecycle/       # Startup/shutdown hooks
│   ├── logging/         # structlog configuration
│   ├── model/           # Base model, team-scoped mixin
│   ├── pagination/      # Cursor-based pagination service
│   └── schemas/         # Base request/response schemas
├── database/            # MySQL connection, R/W split, dependencies
├── cache/               # Redis connection, R/W split, dependencies
├── auth/                # JWT, OAuth, OTP, session management
├── user/                # User CRUD, profile, soft-delete
├── team/                # Team creation, membership
├── rbac/                # Permission groups, guards, cache
└── file/                # MinIO/S3 presigned URLs, file assets
```

## Adding a New Module

1. Create `src/your_module/` with `model.py`, `repository.py`, `service.py`, `router.py`, `schemas/`
2. Register model in `src/common/model/models_registry.py`
3. Add router in `src/main.py`
4. Generate migration: `alembic revision --autogenerate -m "add your_module"`

## Environment Switching (Dev → Prod)

Switch by changing `.env` only:

```bash
ENV=production
DB_WRITE_HOST=your-rds-primary.rds.amazonaws.com
DB_READ_HOST=your-rds-read.rds.amazonaws.com
REDIS_WRITE_HOST=master.your-redis.cache.amazonaws.com
REDIS_READ_HOST=replica.your-redis.cache.amazonaws.com
MINIO_ENDPOINT=https://s3.ap-northeast-2.amazonaws.com
```

Cookie security, CORS policy, and log format auto-adjust based on `ENV`.

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/email/request` | - | Signup OTP send |
| POST | `/auth/register/email/verify` | - | Signup OTP verify |
| POST | `/auth/register` | - | Complete signup |
| POST | `/auth/login` | Basic | Email/password login |
| POST | `/auth/logout` | - | Logout |
| POST | `/auth/token/access` | Cookie | Refresh access token |
| GET | `/auth/oauth/{provider}` | - | OAuth login start |
| POST | `/auth/password/reset/*` | - | Password reset (3-step) |
| GET | `/user` | Bearer | User list (paginated) |
| GET | `/user/me` | Bearer | My profile |
| PATCH | `/user/me` | Bearer | Update profile |
| DELETE | `/user/{id}` | Bearer | Delete user (soft) |
| POST | `/team` | Bearer | Create team |
| GET | `/team/{id}` | Bearer | Get team |
| POST | `/file/upload-urls` | Bearer | Get presigned upload URLs |

## License

MIT
