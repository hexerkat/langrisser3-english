# Langrisser III : English Patch (Sega Saturn)

An English translation patch for *Langrisser III* (Sega Saturn, Japan), built from your own Japanese disc image.

**[Download the patcher](https://github.com/hexerkat/langrisser3-english/releases/latest)** · **[Strategy guide](https://hexerkat.github.io/langrisser3-strategy-guide/)** · [How to install](#installing-the-patch) · [Changelog](CHANGELOG.md)

## About this patch

*Langrisser III* is a 1996 tactical RPG that never received an official English release. This patch translates the story, dialogue, menus, and interface so the game can be played end to end without knowing Japanese. Character and place names broadly follow the spellings used in *Langrisser Mobile*, the modern English release of the series.

**Version 0.7 made the patch 100% this project's own work.** Every change on the disc is generated from this repository against the original Japanese game: no third-party binaries in the pipeline, nothing carried over from CyberWarriorX's earlier v0.2 patch (credited below as groundwork, not as shipped code or data). The English script was reworked line by line against the Japanese, correcting mistranslations and trimming a few additions that weren't in the original, so each character's voice and the tone of every line follow the source.

## Status : v0.8.1 (playable start to finish)

**Working**

- The whole story plays start to finish in English, with every dialogue and narration line translated.
- The interface is translated: menus, the save/load screen, the name-entry keyboard, and item / class / spell names with their descriptions.
- Text uses a mix of wide and narrow letters, so words sit naturally in dialogue, menus and battle windows.
- Your name can be up to 16 letters, with Ä, Ö, Ü and a hyphen on the keyboard.
- The staff roll after the ending, the credits in the scenario 3 opening, the title screen credit and the hidden sound test are in English.
- The opening movie can play with English subtitles (see [The opening movie](#the-opening-movie)).
- A ready-to-run patcher for Windows and Linux builds the game from your disc in a few seconds.

**Still to do toward v1.0**

- The digits of the magic resistances on the status screen are still wide.
- The hidden debug menu still shows Japanese text.
- A full validation playthrough, including the secret stages and both endings, on Ymir, Beetle Saturn and real hardware (Saroo).

## Strategy guide

A complete English strategy guide goes with the patch:
**https://hexerkat.github.io/langrisser3-strategy-guide/**

It covers character creation, classes, the heroine love-index system, every item, all 36 scenarios and the five secret stages with their battle maps, the endings and the best-ending route, and the secrets and cheats. Every line of game text it quotes comes from this patch's scripts, so it uses the same words as your game. Its source lives in [langrisser3-strategy-guide](https://github.com/hexerkat/langrisser3-strategy-guide).

## Installing the patch

You need **your own Japanese *Langrisser III* disc image**: a folder with a `.cue` file, the Track 01 data `.bin`, and the audio track `.bin` files. This patch requires the original disc. No game data is distributed here.

### Source ISO

The patch needs the Redump "3M" dump of the Japanese disc (the "1M" dump has the same data). Check your Track 01 (the data track, where all game files live) with `sha256sum`:

```
SHA-256: 557bfaaa37dc11b6190c46dca8841bc252dfe9f1b3ba8b77ff242843b2bff4c8
File:    Langrisser III (Japan) (3M) (Track 01).bin
Size:    77,098,560 bytes (32,780 sectors × 2,352 bytes)
```

The patcher and `build.py` refuse any other Track 01. The "7M" dump is Rev A, a later revision with different program files: the patch does not support it.

### Easiest: the patcher (Windows and Linux)

Nothing to install, no Python, no terminal.

> **The patcher is not signed.** It is a free fan project, so it has no paid code signing certificate, and your system will ask you to allow it the first time:
> - **Windows**: a blue window says "Windows protected your PC". Click **More info**, then **Run anyway**. Some antivirus programs may also ask before letting it run.
> - **Linux**: if it does not open with a double click, allow it to run as a program (file properties, or `chmod +x Langrisser3-Patcher` in a terminal).
>
> Only download the patcher from this repository's releases.

1. **Download the patcher** for your system from the [latest release](https://github.com/hexerkat/langrisser3-english/releases/latest):
   - **Windows**: `Langrisser3-Patcher-windows.exe`
   - **Linux**: `Langrisser3-Patcher-linux.tar.gz` (extract it first)
2. **Open it.** Allow it to run if your system asks (see the note above).
3. **Choose your Japanese disc folder** with **Browse…**. The patcher checks that it really is the Langrisser III disc. When it is, a character from the disc's own art gallery shows up behind the window.
4. **Press Build patched game.** It takes a few seconds, or about five minutes with the English opening movie. When it finishes, **Open folder** shows the patched game, in a `build/` folder next to the patcher.
5. **Load the `.cue`** from that folder in your emulator and play. On real hardware, burn the `.cue` image or copy it to your optical drive emulator (tested on Saroo).

The English opening movie option needs [ffmpeg](https://ffmpeg.org/download.html) installed. Without it the game keeps the Japanese opening.

### From source (Python)

For developers, or if the patcher does not run on your system. You need **Python 3.10+** (check with `python3 --version`). The build uses only the standard library, so there is nothing to `pip install`.

1. **Download the source** from [GitHub Releases](https://github.com/hexerkat/langrisser3-english/releases) (Source code ZIP) and extract it.

2. **Run the build:**

```bash
python3 build.py --jp-iso "/path/to/Langrisser III (Japan)"
```

This produces a self-contained folder under `build/` named after the `.cue` (e.g. `build/Langrisser III (English v0.8.1)/`) holding the `.cue` and all track `.bin` files, ready to play.

3. **Load in your emulator**: open the `.cue` inside that folder and play.

The same window as the patcher runs with `python3 launcher.py` (needs Tkinter: on Debian/Ubuntu, `sudo apt install python3-tk`).

### The opening movie

The opening FMV is game data, so no video ships here : only its English subtitle track (`assets/movie/opening_en.srt`). Add `--encode-movie` and the patcher builds the subtitled opening from the movie on *your* disc, keeping the Japanese voice track:

```bash
python3 build.py --jp-iso "/path/to/Langrisser III (Japan)" --encode-movie
```

Requires ffmpeg, and can take a while. Without the flag your disc keeps the Japanese opening.

> **Note**: the movie step has only been tested on Linux. It should work anywhere ffmpeg does, but Windows and macOS are unverified : reports welcome.

The encoder lives in [`tools/movie_tools.py`](tools/movie_tools.py) and is developed as a standalone, game-agnostic tool in [**saturn-cinepak-muxer**](https://github.com/ralfguth/saturn-cinepak-muxer), where the write-up on making Cinepak FMV play on real Saturn hardware also lives.

### Compatibility

|                                          | Music | Text | Character voices |
| -----------------------------------------| :---: | :--: | :--------------: |
| **Real Saturn hardware (via Saroo 0.9)** |  ✅   |  ✅  |        ✅        |
| **Ymir** (standalone emulator)           |  ✅   |  ✅  |        ✅        |
| **RetroArch + Beetle Saturn**            |  ✅   |  ✅  |        ✅        |

## Credits

* **hexerkat**: project maintainer and current patch author, handling releases and ongoing maintenance.
* **ralfguth**: original author of this patch, including the modular Python build pipeline, the JP-aligned translation revision, font work, and engine fixes.

## Acknowledgements

* **CyberWarriorX (Theo Berkau)**: Saturn reverse engineering, the original v0.2 patch, bigram font system, and menu translations.
* **Akari Dawn, ElfShadow, Oogami**: original English translation scripts, used as a draft baseline and revised against the Japanese source.
* **VermillionDesserts**: independent translation build and D00.DAT research.

### Special thanks

D (Langrisser.info), Privateye, [langrisser.wiki](https://www.langrisser.wiki/), Langrisser Fandom, and everyone who reported a bug: Starman99x, bqio, nE0sIghT, therion23, pickled-jonaye.

## License

The code in this repository is licensed under the **GNU General Public License, version 3 or later** (`GPL-3.0-or-later`). See [`LICENSE`](LICENSE). This covers the build pipeline, the tools (`tools/`), the tests, the schemas and authored glossaries, and the English translation scripts (`scripts/`) : the project's own contributions, to the extent of the rights held. It cannot grant rights over the original game or over the prior third-party work this project builds on.

### Third-party assets

* **`data/fonts/Mx437_CL_EagleIII_8x16.ttf`** and the in-game glyphs derived from it are from VileR's *Ultimate Oldschool PC Font Pack*, under **CC BY-SA 4.0**. Attribution: VileR / int10h.org. Details in [`data/fonts/SOURCES.md`](data/fonts/SOURCES.md).
* The English script began from a draft translation baseline by **Akari Dawn, ElfShadow and Oogami**, and from **CyberWarriorX's** v0.2 patch (bigram font, menu translations). Those contributions remain the work of their respective authors.

## Legal

This is an unofficial fan translation for educational and preservation purposes, not affiliated with, sponsored by, or endorsed by NCS / Masaya or any rights holder. *Langrisser III* and all related assets are © their respective owners. You must own a legitimate copy of *Langrisser III (Japan)* for Sega Saturn to use this patch.
