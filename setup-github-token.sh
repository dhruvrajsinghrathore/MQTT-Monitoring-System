#!/bin/bash

# Script to set up GitHub token for this repository only
# Usage: ./setup-github-token.sh YOUR_GITHUB_TOKEN

if [ -z "$1" ]; then
    echo "Usage: ./setup-github-token.sh YOUR_GITHUB_TOKEN"
    exit 1
fi

TOKEN=$1

# Update remote URL with token
git remote set-url origin "https://${TOKEN}@github.com/dhruvrajsinghrathore/MQTT-Monitoring-System.git"

echo "Remote URL updated with token"
echo "You can now push using: git push -u origin main"
