#!/bin/bash
# Installa Etere sul Raspberry Pi. Uso:  sudo ./install/install.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/opt/etere
BOOT=/boot/firmware; [ -d "$BOOT" ] || BOOT=/boot

echo "==> Pacchetti"
# IPv4 forzato e piu' tentativi: sugli hotspot del telefono IPv6 spesso non va
# e la connessione puo' cadere a meta' download
APT="apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5"
$APT update
$APT install -y python3-numpy python3-pil python3-spidev python3-gpiozero \
    iw rfkill git fonts-dejavu-core
# gpiozero ha bisogno di un "pin factory": lgpio (Bookworm e successivi) o RPi.GPIO
$APT install -y python3-lgpio || $APT install -y python3-rpi.gpio || true

echo "==> SPI (serve al display)"
raspi-config nonint do_spi 0

echo "==> Programma in $DEST"
mkdir -p "$DEST"
cp "$HERE"/etere/*.py "$DEST"/

if [ ! -d "$DEST/lib/waveshare_epd" ]; then
    echo "==> Driver Waveshare (solo la cartella che serve)"
    tmp="$(mktemp -d)"
    git clone --depth 1 --filter=blob:none --sparse https://github.com/waveshare/e-Paper "$tmp/ws"
    git -C "$tmp/ws" sparse-checkout set RaspberryPi_JetsonNano/python/lib/waveshare_epd
    mkdir -p "$DEST/lib"
    cp -r "$tmp/ws/RaspberryPi_JetsonNano/python/lib/waveshare_epd" "$DEST/lib/"
    rm -rf "$tmp"
fi

if [ ! -f "$BOOT/etere.conf" ]; then
    echo "==> Configurazione in $BOOT/etere.conf"
    cp "$HERE/install/etere.conf" "$BOOT/etere.conf"
fi

echo "==> Avvio automatico"
cp "$HERE/install/etere.service" /etc/systemd/system/etere.service
systemctl daemon-reload
systemctl enable etere.service

cat <<EOF

Fatto. Prossimi passi:
  1) prova il display:     sudo python3 $DEST/etere.py --test-display
  2) prova le radio:       sudo python3 $DEST/etere.py --probe
  3) avvia subito:         sudo systemctl start etere
     (oppure riavvia: parte da solo a ogni accensione)
  Log:                     journalctl -u etere -f
EOF
