#!/bin/bash
# Quick deployment script for SchedulrX

set -e

ENV=${1:-dev}

echo "Deploying SchedulrX in $ENV environment..."

# Load appropriate env file
if [ "$ENV" = "prod" ]; then
    cp .env.prod .env
    echo "Loaded production configuration"
elif [ "$ENV" = "dev" ]; then
    cp .env.dev .env
    echo "Loaded development configuration"
else
    echo "Using existing .env file"
fi

# Build and start containers
echo "Building Docker images..."
docker-compose build

echo "Starting services..."
docker-compose up -d

echo "Waiting for services to be healthy..."
sleep 10

# Check health
echo "Checking application health..."
curl -f http://localhost:8000/health || echo "Warning: Health check failed"

echo ""
echo "✓ Deployment complete!"
echo "  - API docs: http://localhost:8000/docs"
echo "  - Health: http://localhost:8000/health"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "View logs: docker-compose logs -f app"
echo "Stop: docker-compose down"
