#!/bin/bash

echo "Stopping GeoServer services..."
echo ""

# Stop GeoServer
if docker ps --format '{{.Names}}' | grep -q "^geoserver$"; then
    echo "Stopping GeoServer container..."
    docker stop geoserver
    echo "GeoServer stopped"
else
    echo "GeoServer container is not running"
fi

# Stop PostGIS
if docker ps --format '{{.Names}}' | grep -q "^geoserver_db$"; then
    echo "Stopping PostGIS container..."
    docker stop geoserver_db
    echo "PostGIS stopped"
else
    echo "PostGIS container is not running"
fi

echo ""
echo "All GeoServer services stopped"
