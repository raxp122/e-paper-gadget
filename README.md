# Etere: una Polaroid dell'etere radio

Un Raspberry Pi Zero W con display e-paper Waveshare 2.13" che "fotografa" le
onde radio intorno a sé. Gli dai corrente e lui ascolta, disegna e aggiorna lo
schermo ogni ~15 secondi. Quando uno scatto ti piace, stacchi la corrente e
l'immagine resta sull'e-paper finché non lo riaccendi.

Non salva nulla. Ogni scatto esiste solo sul display.

```
corrente -> ascolto (esposizione ~10 s, schermo fermo) -> immagine
         -> refresh completo (~2 s, lo schermo lampeggia) -> pannello in sleep
         -> di nuovo ascolto ...
```

Puoi staccare in qualsiasi momento **tranne mentre lo schermo lampeggia**.

## Da dove arriva l'immagine (sorgenti)

| Sorgente | Cosa misura | Sul Pi Zero W |
|---|---|---|
| `csi` | Channel State Information: come ogni sottoportante Wi-Fi viene deformata dall'ambiente | **Non supportata ufficialmente.** Nexmon CSI non ha la patch per il chip bcm43430a1. Il codice è pronto nel caso un giorno lo sia. |
| `rssi` | Modalità monitor su **un solo canale**: la potenza di ogni frame nel tempo. Righe = livello di segnale (dBm), colonne = tempo | Funziona se il chip accetta la modalità monitor (firmware di serie oppure Nexmon) |
| `scan` | Ripiego: scansioni Wi-Fi normali. Righe = frequenza 2400–2490 MHz, colonne = scansioni | Funziona sempre, ma l'immagine è più statica |

Con `SOURCE=auto` il programma prova `csi`, poi `rssi` e infine `scan`, e usa la
prima che funziona.

**Privacy:** nessuna sorgente legge o conserva indirizzi MAC, nomi di rete o
contenuti. Si usa solo la potenza dei segnali.

Anteprima sul PC (dati simulati, stesso codice del Pi):

```bash
python3 tools/preview.py anteprima.png
```

## Installazione

### 1. Scrivi la SD

Con **Raspberry Pi Imager**: dispositivo *Raspberry Pi Zero*, sistema
**Raspberry Pi OS Lite (32-bit)**. Nelle impostazioni (l'ingranaggio):

- hostname: `etere`
- abilita SSH
- utente e password
- Wi-Fi: nome e password della rete (o dell'hotspot), paese `IT`

> Il Pi Zero W usa solo i **2,4 GHz**. Con l'hotspot di un iPhone attiva
> *Impostazioni → Hotspot personale → Massimizza compatibilità*.

### 2. Entra via SSH

```bash
ssh <utente>@etere.local
```

### 3. Installa

```bash
sudo apt-get install -y git
git clone https://github.com/raxp122/e-paper-gadget.git
cd e-paper-gadget
sudo ./install/install.sh
```

Lo script installa le dipendenze, attiva lo SPI, scarica il driver Waveshare,
copia il programma in `/opt/etere`, mette la configurazione in
`/boot/firmware/etere.conf` e abilita l'avvio automatico.

### 4. Prova

```bash
sudo python3 /opt/etere/etere.py --test-display
```

Deve comparire "etere – display OK". Se lo schermo resta bianco o è sporco,
cambia `EPD=` in `/boot/firmware/etere.conf` (V2, V3 o V4, come sull'etichetta
dietro il display) e riprova.

```bash
sudo python3 /opt/etere/etere.py --probe
```

Ti dice quali sorgenti funzionano sul tuo Pi.

### 5. Avvia

```bash
sudo systemctl start etere
```

Da qui in poi parte da solo a ogni accensione. Per vedere i log:

```bash
journalctl -u etere -f
```

### 6. (Opzionale) Modalità monitor con Nexmon

Solo se `--probe` dice che `rssi` **non** funziona. È sperimentale, la
compilazione dura ore e funziona solo con kernel fino al 6.6:

```bash
sudo ./install/install-nexmon.sh
```

### 7. Rendilo effimero (sola lettura)

Quando tutto funziona, metti il sistema in sola lettura: le scritture finiscono
in RAM e staccare la corrente non può rovinare la SD.

```bash
sudo ./install/readonly.sh
```

Per tornare indietro (per esempio per aggiornare):

```bash
sudo raspi-config nonint disable_overlayfs && sudo reboot
```

poi, dopo il riavvio:

```bash
sudo raspi-config nonint disable_bootro && sudo reboot
```

## Configurazione

Il file `etere.conf` sta nella partizione di boot: lo modifichi anche dal PC con
un lettore di SD.

| Chiave | Default | Significato |
|---|---|---|
| `SOURCE` | `auto` | `auto`, `csi`, `rssi`, `scan` |
| `CHANNEL` | `auto` | canale 1–13 oppure `auto` (il più trafficato) |
| `EXPOSURE_SECONDS` | `10` | secondi di ascolto tra uno scatto e l'altro |
| `FIRST_EXPOSURE_SECONDS` | `5` | esposizione del primo scatto |
| `CLEAN` | `0.6` | 0 = immagine grezza, 1 = molto pulita |
| `VIEW` | `intensita` | `spettro` = il segnale così com'è; `variazioni` = solo i cambiamenti nel tempo (più forte = bianco, più debole = nero); `intensita` = quanto cambia (fermo = nero, evento = bianco); `mix` = metà spettro e metà intensità |
| `DITHER` | `bayer` | `floyd` = morbido; `bayer` = a reticolo, tipo incisione |
| `EPD` | `V3` | versione del pannello: V2, V3, V4 |
| `INVERT` | `0` | 1 = inverte bianco e nero |
| `ROTATE` | `0` | 180 se il display è montato capovolto |
| `KEEP_WIFI` | `1` | 1 = il Wi-Fi normale resta acceso e SSH funziona. 0 = il gadget si prende la radio: canale fisso, cattura più pura, niente SSH |

**Modalità manutenzione:** crea un file vuoto chiamato `etere-off` nella
partizione di boot (anche dal PC). Il gadget non parte e il Wi-Fi resta
normale. Cancellalo per tornare all'arte.

## Sviluppo sul PC

```bash
python3 -m unittest discover tests
python3 etere/etere.py --source sim --once --out scatto.png
```

## Crediti

- Display: libreria [Waveshare e-Paper](https://github.com/waveshare/e-Paper)
- Modalità monitor / CSI: [Nexmon](https://nexmon.org) e
  [Nexmon CSI](https://github.com/seemoo-lab/nexmon_csi) di SEEMOO Lab, TU Darmstadt
