#!/bin/bash

# Auto-Restart Watchdog for BBDC Bot
# This script runs the bot and automatically restarts it after a 5-minute cool-down 
# if it shuts down (e.g., due to Max Login Retries to prevent suspension).

while true
do
    echo "[Watchdog] Starting the BBDC Booking Bot..."
    ./env/bin/python main.py

    echo "[Watchdog] Bot crashed or exited safely."
    echo "[Watchdog] Cooling down for 5 minutes before resurrecting to prevent BBDC IP bans..."
    sleep 300
done
