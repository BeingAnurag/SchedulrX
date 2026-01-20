#!/bin/bash
# Test database and cache connectivity

echo "Starting Docker containers..."
docker-compose up -d

echo "Waiting for services to be ready..."
sleep 5

echo "Testing PostgreSQL..."
python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://user:password@localhost:5432/schedulrx')
with engine.connect() as conn:
    print('✓ PostgreSQL connected')
"

echo "Testing Redis..."
python -c "
import redis
r = redis.from_url('redis://localhost:6379/0')
r.ping()
print('✓ Redis connected')
"

echo "Creating database tables..."
python -c "from app.storage.database import init_db; init_db(); print('✓ Tables created')"

echo "All tests passed!"
