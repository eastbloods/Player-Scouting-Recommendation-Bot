#!/bin/bash
set -e

echo "🚀 Deploying GoatScout..."

cd ~/Player_Scouting_Recommendation_Bot

# Pull latest code
git pull

# Copy frontend to nginx serving directory
sudo cp index.html /var/www/goatscout/index.html
echo "✅ Frontend updated → /var/www/goatscout/index.html"

# Rebuild and restart API
docker compose up -d --build api
echo "✅ API restarted"

echo "🎉 Deploy complete! https://goatscout.space"
