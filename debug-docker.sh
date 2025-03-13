#!/bin/bash

# Check if a container name is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <container_name>"
  echo "Example: $0 aidebate_aidebate_1"
  exit 1
fi

CONTAINER=$1

echo "=== Container Status ==="
docker ps -a | grep $CONTAINER

echo -e "\n=== Container Logs ==="
docker logs $CONTAINER

echo -e "\n=== Container Environment ==="
docker exec -it $CONTAINER env | sort

echo -e "\n=== Container File Permissions ==="
docker exec -it $CONTAINER ls -la /app

echo -e "\n=== Container Logs Directory ==="
docker exec -it $CONTAINER ls -la /app/logs

echo -e "\n=== Container User ==="
docker exec -it $CONTAINER id

echo -e "\n=== Container Process List ==="
docker exec -it $CONTAINER ps aux
