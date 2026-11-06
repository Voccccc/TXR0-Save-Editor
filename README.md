# Tokyo Xtreme Racer Zero Save Editor

A Python/Tkinter editor for the North American PS2 release (SLUS-20189).

## Run

Install Python 3 with Tcl/Tk support, then run:

```sh
python txr_zero_editor.py
```

Open a memory card, select a car, choose part levels, and save an edited copy.
The editor supports cash, days, performance parts, and aero parts. Changes to
multiple cars are retained until the editor is closed.

## Supported formats and limits

- 64 MiB SD2PSX `.mcd` images without ECC.
- Corresponding PCSX2 `.ps2` images with 528-byte pages and ECC.
- Up to 50 garage records, including duplicate models.
- The game-data file must occupy the currently supported directory and card
  locations. This is not a general PS2 memory-card filesystem parser.
- Known car classes are labels from the development reference. Other models
  appear under Other cars.
- No car creation, mileage editing, or active-car selection.

Exports refresh the game-data additive checksum and generate page ECC for
PCSX2. An earlier edited reference save was confirmed to load by its owner;
compatibility with all saves and hardware configurations is not established.
Keep a backup and close the emulator or game before changing card files.
The editor writes to a separate file and protects the opened input path.

No saves, BIOS, game assets, or personal development notes are included.

## Research acknowledgments

- [tofuman0's TXR0 Rival Data research](https://github.com/tofuman0/TXR0-Rival-Data): corroboration of part order.
- [PCSX2 memory card implementation](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/SIO/Memcard/MemoryCardFile.cpp): card page format and corroboration of the public-domain mymc ECC algorithm.
- Ross Ridge's public-domain mymc research: PS2 memory-card format and ECC.

The game-data checksum and reference offsets were established by inspecting
reference saves. This project is unofficial and is not affiliated with Genki,
Sony, SD2PSX, or PCSX2.
