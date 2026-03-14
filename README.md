# Adjust Review Times (Timezone)

An Anki add-on that corrects review timestamps when you study in a different timezone from your home timezone.

## The Problem

Anki stores review timestamps in UTC. When Anki computes your daily review counts and streaks, it converts UTC timestamps to your local timezone to determine which "day" a review belongs to. If you travel and do reviews in a different timezone, those reviews get attributed to the wrong local date — throwing off your statistics, streaks, and heatmaps.

This add-on lets you retroactively fix those timestamps so that a review done at 9pm Tokyo time is recorded as 9pm New York time (or whatever your home timezone is), as if you'd never left.

## Features

- **Preview before applying** — see exactly which reviews will be changed and how, before committing
- **Automatic backup** — creates a copy of your collection database before any changes are made
- **Adjustment history** — log of all past adjustments with date ranges, timezones, and review counts
- **Exportable history** — export adjustment history to JSON
- **Safe duplicate detection** — skips any adjustment that would create a duplicate timestamp
- **Configurable home timezone** — set once, reuse across all adjustments
- **Custom timezone support** — type any IANA timezone name, not just the built-in list

## Usage

### 1. Set your home timezone

Go to **Tools → Adjust Review Times (Timezone)** the first time and you'll be prompted to set your home timezone (e.g. `America/New_York`). You can also change it later via the add-on's config action or the "Change..." button in the dialog.

### 2. Adjust review times

**Tools → Adjust Review Times (Timezone)**

- Set the **date range** covering when you were traveling
- Select the **source timezone** (where you actually were when reviewing)
- Click **Update Preview** to see what will change
- Click **Apply Adjustments** to commit — a backup is created automatically before any changes

### 3. View history

**Tools → View Adjustment History**

Shows a table of all past adjustments. Click **Export to JSON** to save a full record.

## Installation

### From AnkiWeb

Search for "Adjust Review Times" on [AnkiWeb](https://ankiweb.net/shared/addons) or install by add-on code.

### Manual

1. Download the latest release zip
2. In Anki: **Tools → Add-ons → Install from file...**
3. Select the zip and restart Anki

## Compatibility

- Anki 2.1.x (Qt6 and Qt5)
- Python 3.9+ (uses `zoneinfo`; falls back to `backports.zoneinfo` or `pytz` on older versions)

## Notes

- This add-on modifies `revlog` entries directly. Always keep the automatic backup or make your own before running.
- Only the timestamp (`id`) of each review log entry is changed — ease, interval, and all other fields are untouched.
- The adjustment preserves **wall clock time**: a review at 21:00 in Tokyo becomes 21:00 in New York, not the same UTC instant.
