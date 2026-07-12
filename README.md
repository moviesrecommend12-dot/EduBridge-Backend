# Orbiet Backend

Orbiet is a Django backend for school management. The project was originally named EduBridge, so some internal folders still use the old name. Do not rename the Django apps or the `config` settings package unless there is a specific migration plan.

## Stack

- Django and Django REST Framework
- JWT authentication with Simple JWT
- Django Templates dashboard
- Django Channels WebSocket chat
- Stripe Checkout in Test Mode
- MySQL for the deployed/local database target

## Apps

- `accounts`
- `academics`
- `finance`
- `notifications`
- `chat`
- `dashboard`

## Windows PowerShell Setup

From the project directory:

```powershell
cd C:\Users\Msii9\EduBridge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If a `requirements.txt` file is added later, install from it:

```powershell
pip install -r requirements.txt
```

If there is no requirements file yet, install the current core packages:

```powershell
pip install Django djangorestframework djangorestframework-simplejwt django-cors-headers channels daphne stripe python-dotenv mysqlclient
```

If `mysqlclient` fails on Windows, install the matching Microsoft C++ Build Tools, then retry.

## Environment File

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Fill in your local MySQL and Stripe Test Mode values.

Current `config/settings.py` reads these values from `.env`:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CORS_ALLOW_ALL_ORIGINS`
- `DB_ENGINE`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `FRONTEND_SUCCESS_URL`
- `FRONTEND_CANCEL_URL`

If `DB_ENGINE` is not set, Django falls back to the local `db.sqlite3` file. To use MySQL, set `DB_ENGINE=django.db.backends.mysql` and fill in the other `DB_*` values in `.env`.

## MySQL Setup

In MySQL, create the database and user:

```sql
CREATE DATABASE orbiet_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'orbiet_user'@'localhost' IDENTIFIED BY 'replace-with-your-password';
GRANT ALL PRIVILEGES ON orbiet_db.* TO 'orbiet_user'@'localhost';
FLUSH PRIVILEGES;
```

Then put the same values in `.env`.

## Migrations And Admin User

Run:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

For existing databases, do not delete old migration files. Use `migrate` normally.

## Run The Project

HTTP dashboard and API:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/dashboard/
```

For WebSocket testing with Channels, `runserver` is enough for local development because `daphne` is installed and configured in `INSTALLED_APPS`.

## Demo Accounts

Create accounts from the dashboard or Django Admin:

- Admin: create with `createsuperuser`
- Teacher: create from `http://127.0.0.1:8000/dashboard/teachers/`
- Student: create from `http://127.0.0.1:8000/dashboard/students/create/`
- Parent: register by API using a student parent linking code

Record local demo credentials here after creating them:

```text
ADMIN username:
ADMIN password:

TEACHER username:
TEACHER password:

STUDENT username:
STUDENT password:

PARENT username:
PARENT password:
```

## Dashboard Pages

Base URL:

```text
http://127.0.0.1:8000/dashboard/
```

Main pages:

- `/dashboard/`
- `/dashboard/students/`
- `/dashboard/students/create/`
- `/dashboard/teachers/`
- `/dashboard/parents/`
- `/dashboard/classrooms/`
- `/dashboard/sections/`
- `/dashboard/subjects/`
- `/dashboard/teaching-assignments/`
- `/dashboard/schedules/`
- `/dashboard/attendance/`
- `/dashboard/grades/`
- `/dashboard/assignments/`
- `/dashboard/uploaded-files/`
- `/dashboard/announcements/`
- `/dashboard/notifications/`
- `/dashboard/invoices/`
- `/dashboard/payments/`
- `/dashboard/receipts/`
- `/admin/`

## Authentication API

All API URLs use:

```text
http://127.0.0.1:8000
```

Login:

```http
POST /api/accounts/login/
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

Use the returned access token:

```http
Authorization: Bearer <access_token>
```

Current user:

```http
GET /api/accounts/me/
Authorization: Bearer <access_token>
```

Parent registration:

```http
POST /api/accounts/parent/register/
Content-Type: application/json

{
  "username": "parent1",
  "password": "password123",
  "first_name": "Parent",
  "last_name": "One",
  "email": "parent@example.com",
  "phone": "0999999999",
  "national_id": "123456",
  "address": "Address",
  "linking_code": "STUDENT_CODE",
  "relationship": "Father"
}
```

## Accounts API

- `GET /api/accounts/parent/children/`
- `GET /api/accounts/parent/children/<student_id>/`
- `GET /api/accounts/student/profile/`

## Academics API

Teacher:

- `GET /api/academics/teacher/assignments/`
- `GET /api/academics/teacher/students/`
- `POST /api/academics/teacher/attendance/create/`
- `POST /api/academics/teacher/grades/create/`
- `POST /api/academics/teacher/assignments/create/`
- `POST /api/academics/teacher/announcements/create/`
- `POST /api/academics/teacher/files/upload/`

Student:

- `GET /api/academics/student/schedule/`
- `GET /api/academics/student/attendance/`
- `GET /api/academics/student/grades/`
- `GET /api/academics/student/assignments/`
- `GET /api/academics/student/files/`
- `GET /api/academics/student/announcements/`

Parent:

- `GET /api/academics/parent/children/<student_id>/schedule/`
- `GET /api/academics/parent/children/<student_id>/attendance/`
- `GET /api/academics/parent/children/<student_id>/grades/`
- `GET /api/academics/parent/children/<student_id>/assignments/`
- `GET /api/academics/parent/children/<student_id>/files/`
- `GET /api/academics/parent/children/<student_id>/announcements/`

## Finance API

Parent:

- `GET /api/finance/parent/invoices/`
- `GET /api/finance/parent/children/<student_id>/invoices/`
- `POST /api/finance/parent/invoices/<invoice_id>/create-checkout-session/`
- `POST /api/finance/parent/payments/confirm/`
- `GET /api/finance/parent/payments/`
- `GET /api/finance/parent/receipts/`
- `GET /api/finance/parent/receipts/<receipt_id>/`

Stripe webhook:

- `POST /api/finance/stripe/webhook/`

Payment result pages:

- `/payment/success/`
- `/payment/cancel/`

## Notifications API

- `GET /api/notifications/`
- `GET /api/notifications/unread-count/`
- `PATCH /api/notifications/<notification_id>/read/`
- `PATCH /api/notifications/read-all/`

## Chat API

- `GET /api/chat/rooms/`
- `POST /api/chat/rooms/create/`
- `GET /api/chat/rooms/<room_id>/messages/`
- `POST /api/chat/rooms/<room_id>/messages/send/`
- `POST /api/chat/rooms/<room_id>/read/`

## WebSocket Chat

WebSocket URL:

```text
ws://127.0.0.1:8000/ws/chat/<room_id>/?token=<access_token>
```

Send chat message:

```json
{
  "type": "chat_message",
  "content": "Hello"
}
```

Mark room messages as read:

```json
{
  "type": "mark_read"
}
```

Expected connection message:

```json
{
  "type": "connection_established",
  "room_id": 1,
  "user_id": 1,
  "message": "WebSocket connected successfully."
}
```

The WebSocket accepts authenticated parent and teacher users who are allowed to access the chat room.

## Stripe Test Mode

Use Stripe test keys in `.env`:

```text
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

For local webhook testing, forward Stripe events to:

```text
http://127.0.0.1:8000/api/finance/stripe/webhook/
```

## Useful Checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py runserver
```

## Postman Collection

Import this file into Postman:

```text
postman/Orbiet.postman_collection.json
```

Set collection variables such as `username`, `password`, `student_id`, `teacher_id`, `classroom_id`, `section_id`, `subject_id`, and `room_id`.

Run `Accounts / Login` first. The collection test script saves `access_token` and `refresh_token` automatically for the protected requests.

## Notes

- Keep the Django settings package named `config`.
- Keep existing apps and migrations.
- Do not delete migration files.
- Dashboard branding should show Orbiet.
- Some old internal references may still say EduBridge because that was the original project name.
