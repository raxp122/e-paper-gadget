#!/bin/bash
# Installa Etere sul Raspberry Pi. Uso:  sudo ./install/install.sh
# Si puo' rilanciare quando si vuole (per esempio dopo un git pull).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/opt/etere
BOOT=/boot/firmware; [ -d "$BOOT" ] || BOOT=/boot
CONF="$BOOT/etere.conf"

echo "==> Pacchetti"
# IPv4 forzato e piu' tentativi: sugli hotspot del telefono IPv6 spesso non va
# e la connessione puo' cadere a meta' download
APT="apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5"
$APT update
$APT install -y python3-numpy python3-pil python3-spidev python3-gpiozero \
    iw rfkill git fonts-dejavu-core dnsmasq-base
# gpiozero ha bisogno di un "pin factory": lgpio (Bookworm e successivi) o RPi.GPIO
$APT install -y python3-lgpio || $APT install -y python3-rpi.gpio || true

echo "==> SPI (serve al display)"
raspi-config nonint do_spi 0

echo "==> Programma in $DEST"
mkdir -p "$DEST/apps" "$DEST/data"
rm -rf "$DEST/__pycache__" "$DEST/apps/__pycache__"
cp "$HERE"/etere/*.py "$DEST"/
cp "$HERE"/etere/apps/*.py "$DEST/apps/"
cp "$HERE"/etere/data/*.json "$DEST/data/"

if [ ! -d "$DEST/lib/waveshare_epd" ]; then
    echo "==> Driver Waveshare (solo la cartella che serve)"
    tmp="$(mktemp -d)"
    git clone --depth 1 --filter=blob:none --sparse https://github.com/waveshare/e-Paper "$tmp/ws"
    git -C "$tmp/ws" sparse-checkout set RaspberryPi_JetsonNano/python/lib/waveshare_epd
    mkdir -p "$DEST/lib"
    cp -r "$tmp/ws/RaspberryPi_JetsonNano/python/lib/waveshare_epd" "$DEST/lib/"
    rm -rf "$tmp"
fi

CARDS="$DEST/data/tarocchi/cards"
if [ "$(ls "$CARDS" 2>/dev/null | wc -l)" -lt 78 ]; then
    echo "==> Carte dei tarocchi (Rider-Waite-Smith, pubblico dominio)"
    tmp="$(mktemp -d)"
    git clone --depth 1 --filter=blob:none --sparse https://github.com/metabismuth/tarot-json "$tmp/t"
    git -C "$tmp/t" sparse-checkout set cards
    mkdir -p "$CARDS"
    cp "$tmp"/t/cards/*.jpg "$CARDS/"
    rm -rf "$tmp"
fi

if [ ! -f "$CONF" ]; then
    echo "==> Configurazione in $CONF"
    cp "$HERE/install/etere.conf" "$CONF"
fi

# legge una chiave da etere.conf (o il valore di default)
conf() { local v; v="$(grep -E "^$1=" "$CONF" 2>/dev/null | tail -n1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//; s/^[[:space:]]*//; s/[[:space:]]*$//')"; echo "${v:-$2}"; }
SSID="$(conf AP_SSID raspberry)"
PSK="$(conf AP_PASSWORD raspberrypi)"

echo "==> Rete del gadget: \"$SSID\""
if [ "${#PSK}" -lt 8 ] || [ "${#PSK}" -gt 63 ]; then
    echo "!! AP_PASSWORD deve avere da 8 a 63 caratteri (regola del Wi-Fi WPA2). Rete non configurata."
else
    # Il gadget crea la sua rete solo se all'accensione non trova una rete
    # conosciuta (per esempio l'hotspot del telefono): priorita' piu' bassa.
    nmcli connection delete etere-ap >/dev/null 2>&1 || true
    nmcli connection add type wifi ifname wlan0 con-name etere-ap ssid "$SSID" \
        connection.autoconnect yes connection.autoconnect-priority -100 \
        802-11-wireless.mode ap 802-11-wireless.band bg \
        ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
        wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp >/dev/null
    # "Captive portal": ogni nome risponde con l'indirizzo del gadget, cosi'
    # il telefono apre da solo la pagina di controllo
    mkdir -p /etc/NetworkManager/dnsmasq-shared.d
    echo "address=/#/10.42.0.1" > /etc/NetworkManager/dnsmasq-shared.d/etere-captive.conf
fi

echo "==> Avvio automatico"
cp "$HERE/install/etere.service" /etc/systemd/system/etere.service
systemctl daemon-reload
systemctl enable etere.service

cat <<EOF

Fatto. Prossimi passi:
  1) riavvia il servizio:  sudo systemctl restart etere
  2) prova il display:     sudo python3 $DEST/etere.py --test-display
  Log:                     journalctl -u etere -f

Rete del gadget: se all'accensione non trova l'hotspot del telefono, crea la
rete "$SSID". Collegati dal telefono: la pagina di controllo si apre da sola
(altrimenti apri http://10.42.0.1). SSH su quella rete: ssh <utente>@10.42.0.1
EOF
