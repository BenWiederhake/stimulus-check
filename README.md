# stimulus-check

> Here's your stimulating checkmark, or "stimulus check" for short.

All this talk about a "stimulus check" gave me an idea: Create a checkmark that "stimulates" your senses.

![A visually-loud image displaying prominently a checkmark, along with the text "stimulus check". The colors, sizes, positions, fonts, and everything change back and forth.](example.gif)

Epilepsy warning! This program intentionally produces harsh videos that are difficult to look at.

## Table of Contents

- [Install](#install)
- [Usage](#usage)
- [Performance](#performance)
- [TODOs](#todos)
- [NOTDOs](#notdos)
- [Contribute](#contribute)

## Install

### Prerequisites

You'll need:
- The image library PIL: `pip3 install PIL`
- ffmpeg: `sudo apt-get install ffmpeg`

### Configuration

I don't know how to scan for system fonts, and a lot of fonts don't work well with PIL, so the font
list is manually assembled. Your mileage may vary, so feel free to add/remove files to your heart's
content. The listed ttf are all available in the Debian repo, one way or the other. Check out
[the search function](https://packages.debian.org/search?suite=testing&arch=any&mode=filename&searchon=contents&keywords=foobar.ttf)
if you really want a particular TTF but don't have it.

## Usage

```console
$ EMIT_MUSIC_FILE='/path/to/for/example/Hybrid - Choke-gkexA9cYAds.m4a' ./emit.py
Writing 1140 images ........................................................... done.
Concatenating into stimulating_1616090488.mp4 ... done.
Cleaning up ........................................................... done.
Output is at stimulating_1616090488.mp4
```

## How it works

- `WORDS` defines what you'd like to have displayed.
- `sample_image` is then used 1200 times to create 1200 images.
- These images are written to disk.
- ffmpeg is used to create a video from that.

## TODOs

* Make it work
* Watch it on a beamer

## NOTDOs

Here are some things this project will definitely not support:
* Automatic beat detection
* Calling an ambulance when the user inevitably suffers an epileptic seizure
* Command-line arguments (Use the source, Luke!)

## Contribute

Feel free to dive in! [Open an issue](https://github.com/BenWiederhake/stimulus-check/issues/new) or submit PRs.
