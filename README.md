# pm5190-ctrl

Terminal UI for controlling the Philips PM5190 LF synthesizer over GPIB.

Connects via an [AR488](https://github.com/Twilight-Logic/AR488) Arduino-based USB-to-GPIB adapter.

## Requirements

- Arduino Nano with AR488 firmware on `/dev/ttyUSB0`
- PM5190 GPIB address set to 4 (DIP switches on the bottom of the unit)

## Usage

```bash
uv run python pm5190.py
```

| Key | Action |
|-----|--------|
| `Ctrl+T` | Transmit settings to instrument |
| `F2` | Preferences (port, baud rate, GPIB address) |
| `Ctrl+Q` | Quit |

## Frequency input

The frequency field accepts SI suffixes: `1k` = 1000 Hz, `1M` = 1 MHz, `500m` = 0.5 Hz.
