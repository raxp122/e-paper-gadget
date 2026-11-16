#!/bin/bash
# OPZIONALE e SPERIMENTALE: installa Nexmon (modalita' monitor) per il chip
# bcm43430a1 del Pi Zero W, seguendo le istruzioni ufficiali di seemoo-lab/nexmon.
# Serve SOLO se "etere.py --probe" dice che rssi NON funziona.
#
# - La compilazione sul Pi Zero dura ore.
# - Nexmon supporta i kernel fino al 6.6: se il tuo e' piu' recente lo script
#   si ferma (in quel caso serve un'immagine Raspberry Pi OS piu' vecchia).
# - Sostituisce il firmware Wi-Fi (viene fatta una copia di backup).
# - Blocca gli aggiornamenti del kernel, altrimenti un apt upgrade lo romperebbe.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"

KVER="$(uname -r | sed 's/\([0-9]\+\.[0-9]\+\)\..*/\1/')"
SUPPORTED="4.9 4.14 4.19 5.4 5.10 5.15 6.1 6.2 6.6"
echo "Kernel: $(uname -r)  (serie $KVER)"
if ! echo " $SUPPORTED " | grep -q " $KVER "; then
    echo "!! Nexmon non ha il driver per il kernel $KVER (supportati: $SUPPORTED)."
    echo "!! Non procedo. Etere funziona comunque con la sorgente 'scan'."
    exit 1
fi

if dpkg -s linux-headers-rpi-v6 >/dev/null 2>&1 || apt-cache show linux-headers-rpi-v6 >/dev/null 2>&1; then
    HEADERS=linux-headers-rpi-v6; KPKGS="linux-image-rpi-v6 linux-headers-rpi-v6"
else
    HEADERS=raspberrypi-kernel-headers; KPKGS="raspberrypi-kernel raspberrypi-kernel-headers"
fi

apt-get update
apt-get install -y "$HEADERS" git libgmp3-dev gawk qpdf bison flex make autoconf \
    automake libtool texinfo xxd
apt-mark hold $KPKGS raspberrypi-bootloader 2>/dev/null || apt-mark hold $KPKGS

cd /opt
[ -d nexmon ] || git clone --depth 1 https://github.com/seemoo-lab/nexmon.git
cd nexmon
ARCHLIB=/usr/lib/arm-linux-gnueabihf
if [ ! -e "$ARCHLIB/libisl.so.10" ]; then
    (cd buildtools/isl-0.10 && ./configure && make && make install)
    ln -sf /usr/local/lib/libisl.so "$ARCHLIB/libisl.so.10"
fi
if [ ! -e "$ARCHLIB/libmpfr.so.4" ]; then
    (cd buildtools/mpfr-3.1.4 && autoreconf -f -i && ./configure && make && make install)
    ln -sf /usr/local/lib/libmpfr.so "$ARCHLIB/libmpfr.so.4"
fi

# setup_env.sh va "sourced" in bash
set +u
source setup_env.sh
set -u
make
cd patches/bcm43430a1/7_45_41_46/nexmon/
make
make backup-firmware
make install-firmware
cd /opt/nexmon/utilities/nexutil && make && make install

# carica il driver modificato anche ai riavvii successivi
DRV="$(modinfo -n brcmfmac)"
NEW="/opt/nexmon/patches/driver/brcmfmac_${KVER}.y-nexmon/brcmfmac.ko"
if [ -f "$NEW" ]; then
    [ -f "$DRV.orig" ] || cp "$DRV" "$DRV.orig"
    cp "$NEW" "$DRV"
    depmod -a
fi

echo "Nexmon installato. Riavvia e poi prova: sudo python3 /opt/etere/etere.py --probe"
