#!/bin/bash
# Runs the website beside the bot. The website is started again if it stops;
# the container stops with the bot, so Docker starts both again.

(
    cd web || exit
    while true; do
        python main.py
        sleep 2
    done
) &

exec python fischl.py
