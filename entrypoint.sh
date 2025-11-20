#!/bin/bash
set -e

# Create data.json with initial structure if it doesn't exist or is empty
if [ ! -f "/app/data.json" ]; then
    echo "Initializing data.json..."
    echo '{"groups": {}}' > /app/data.json
elif [ ! -s "/app/data.json" ]; then
    # File exists but is empty
    echo "Initializing empty data.json..."
    echo '{"groups": {}}' > /app/data.json
fi

echo "Starting Santa Bot..."
exec python bot.py
