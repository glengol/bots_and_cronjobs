#!/bin/bash
set -e  # Exit script on error

echo "🚀 Running main.py..."
python get_jira_tickets.py

echo "⏳ Waiting for 30 seconds before running push_to_hubspot_new.py..."
sleep 30

echo "✅ Running push_to_hubspot_new.py..."
python push_to_hubspot.py

echo "🎉 Script execution completed!"
