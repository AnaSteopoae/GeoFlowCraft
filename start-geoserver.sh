#!/bin/bash

set -e

echo "🌍 Starting GeoServer and PostGIS..."
echo ""

# Verifică dacă containerul PostGIS rulează
if docker ps --format '{{.Names}}' | grep -q "^geoserver_db$"; then
    echo "✅ PostGIS container is already running"
else
    if docker ps -a --format '{{.Names}}' | grep -q "^geoserver_db$"; then
        echo "🔄 Starting existing PostGIS container..."
        docker start geoserver_db
    else
        echo "🚀 Creating and starting PostGIS container..."
        docker run --name geoserver_db \
            -p 5434:5432 \
            -e POSTGRES_PASSWORD=postgres \
            -d postgis/postgis
    fi
    sleep 3
fi

# Verifică dacă containerul GeoServer rulează
if docker ps --format '{{.Names}}' | grep -q "^geoserver$"; then
    echo "✅ GeoServer container is already running"
    echo ""
    echo "📊 Container info:"
    docker ps --filter "name=geoserver" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "🌐 GeoServer Web UI: http://localhost:5433/geoserver"
    echo "   Username: admin"
    echo "   Password: admin"
else
    # Șterge containerul vechi dacă există dar nu rulează
    if docker ps -a --format '{{.Names}}' | grep -q "^geoserver$"; then
        echo "🗑️  Removing old GeoServer container..."
        docker rm -f geoserver
    fi
    
    echo "🚀 Creating and starting GeoServer container..."
    docker run -d \
        -p 5433:8080 \
        -v "$(pwd)/backend/data_geoserver:/opt/geoserver/data_dir" \
        --name geoserver \
        --link geoserver_db:geoserver_db \
        -e DB_BACKEND=POSTGRES \
        -e HOST=geoserver_db \
        -e POSTGRES_PORT=5432 \
        -e POSTGRES_DB=gis \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASS=postgres \
        -e GEOSERVER_ADMIN_USER=admin \
        -e GEOSERVER_ADMIN_PASSWORD=admin \
        -e TOMCAT_USER=admin \
        -e TOMCAT_PASS=admin \
        -e CSRF_WHITELIST="localhost:5173" \
        kartoza/geoserver
    
    echo ""
    echo "⏳ Waiting for GeoServer to start (this may take 30-60 seconds)..."
    sleep 10
fi

echo ""
echo "✅ GeoServer services started successfully!"
echo ""
echo "📝 Service URLs:"
echo "  - GeoServer Web UI: http://localhost:5433/geoserver"
echo "  - PostGIS Database: localhost:5434 (mapped to 5432 in container)"
echo ""
echo "🔑 Default Credentials:"
echo "  - GeoServer: admin / admin"
echo "  - PostGIS: postgres / postgres"
echo ""
echo "📊 Useful commands:"
echo "  - View GeoServer logs: docker logs -f geoserver"
echo "  - View PostGIS logs: docker logs -f geoserver_db"
echo "  - Stop services: ./stop-geoserver.sh"
echo "  - Restart GeoServer: docker restart geoserver"
