#!/bin/bash
# Rende il sistema "effimero": tutto in sola lettura, le scritture vivono in RAM
# e spariscono allo spegnimento. Cosi' staccare la corrente non rovina la SD.
#
# Per tornare indietro (per aggiornare il programma):
#   sudo raspi-config nonint disable_overlayfs && sudo reboot
#   sudo raspi-config nonint disable_bootro   && sudo reboot
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"

raspi-config nonint enable_bootro      # partizione di boot in sola lettura
raspi-config nonint enable_overlayfs   # radice in sola lettura (overlay in RAM)
echo "Sistema in sola lettura dal prossimo avvio. Riavvio..."
sleep 2
reboot
