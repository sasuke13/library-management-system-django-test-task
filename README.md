# Library Management System

A Django REST API for library management with JWT authentication, role-based permissions, and full CRUD operations for books, loans, and user management.

## 🚀 Features

- **User Authentication & Authorization**
  - JWT-based authentication with access/refresh tokens
  - Role-based permissions (Anonymous, User, Librarian)
  - Secure user registration and profile management

- **Book Management**
  - Complete CRUD operations for books
  - Advanced search and filtering capabilities
  - Book availability tracking and ratings system
  - ISBN validation and metadata management

- **Loan System**
  - Book borrowing and returning functionality
  - Overdue tracking with automatic fine calculation
  - Loan renewal system with configurable limits
  - Comprehensive loan history and reporting

- **Security & Performance**
  - Rate limiting and API throttling
  - CSRF protection and security headers
  - Input validation and SQL injection prevention
  - Comprehensive test coverage (88.24%)

## 📋 Requirements

- Python 3.11+
- Django 5.2.2
- PostgreSQL 15+
- Redis (for caching and sessions)
- Docker & Docker Compose

## 🛠️ Installation

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd library-management-system
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Environment configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Database setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Run development server**
   ```bash
   python manage.py runserver
   ```

### Docker Development Setup

1. **Build and run with Docker Compose**
   ```bash
   cd backend
   docker-compose up --build
   ```

2. **Run migrations in container**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_NAME=library_management
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# JWT Settings
JWT_ACCESS_TOKEN_LIFETIME=60  # minutes
JWT_REFRESH_TOKEN_LIFETIME=1440  # minutes (24 hours)
```

## 📚 API Documentation

### Base URL
- Development: `http://localhost:8000/`
- API Base: `http://localhost:8000/api/v1/`

### Interactive Documentation
- Swagger UI: `http://localhost:8000/`
- ReDoc: `http://localhost:8000/redoc/`

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register/` | User registration |
| POST | `/api/v1/auth/login/` | User login |
| POST | `/api/v1/auth/logout/` | User logout |
| POST | `/api/v1/auth/refresh/` | Refresh access token |
| GET | `/api/v1/auth/profile/` | Get user profile |
| PUT | `/api/v1/auth/profile/` | Update user profile |

### Book Management Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/books/` | List all books |
| POST | `/api/v1/books/` | Create new book (Librarian only) |
| GET | `/api/v1/books/{id}/` | Get book details |
| PUT | `/api/v1/books/{id}/` | Update book (Librarian only) |
| DELETE | `/api/v1/books/{id}/` | Delete book (Librarian only) |
| GET | `/api/v1/books/search/` | Search books |
| POST | `/api/v1/books/{id}/rate/` | Rate a book |

### Loan Management Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/loans/` | List loans |
| POST | `/api/v1/loans/` | Borrow a book |
| GET | `/api/v1/loans/{id}/` | Get loan details |
| POST | `/api/v1/loans/{id}/return/` | Return a book |
| POST | `/api/v1/loans/{id}/renew/` | Renew a loan |
| GET | `/api/v1/loans/overdue/` | List overdue loans |
| GET | `/api/v1/loans/history/` | User loan history |

### Health Check Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health/` | Basic health check |
| GET | `/health/detailed/` | Detailed health check |
| GET | `/health/ready/` | Readiness probe |
| GET | `/health/live/` | Liveness probe |

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python manage.py test

# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific test file
python manage.py test apps.core.tests.test_api
```

### Test Coverage
Current test coverage: **88.24%**

## 🔒 Security Features

- **Authentication**: JWT tokens with blacklisting
- **Authorization**: Role-based access control
- **Rate Limiting**: API throttling (100/hour anonymous, 1000/hour authenticated)
- **Input Validation**: Comprehensive serializer validation
- **Security Headers**: HSTS, XSS protection, CSP
- **CSRF Protection**: Django CSRF middleware
- **SQL Injection Prevention**: Django ORM protection

## 📊 Performance & Monitoring

### Caching
- Redis-based caching for sessions and API responses
- Database query optimization with select_related/prefetch_related

### Logging
- Structured logging with rotation
- Separate log levels for different components

### Health Checks
- Database connectivity monitoring
- Cache system health checks
- Disk space monitoring

## 🚀 Basic Deployment

### Docker Production Deployment

1. **Build production image**
   ```bash
   docker build -t library-management:latest .
   ```

2. **Run with production settings**
   ```bash
   docker run -d \
     --name library-management \
     -p 8000:8000 \
     -e DJANGO_SETTINGS_MODULE=library_management.settings_production \
     library-management:latest
   ```

### Production Docker Compose Setup

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  web:
    image: library-management:latest
    environment:
      - DJANGO_SETTINGS_MODULE=library_management.settings_production
    env_file:
      - .env.production
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  redis_data:
```

Run with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 🔧 Production Environment Configuration

### Production Environment Variables

```env
# Django Settings
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com

# Database Configuration
DB_NAME=library_management
DB_USER=postgres
DB_PASSWORD=your-secure-password
DB_HOST=your-database-host
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://your-redis-host:6379/0

# Security Settings
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```