# AnkiWeb Submission Fields

## Title
Adjust Review Times (Timezone)

## Tags
statistics timezone review

## Support Page
https://github.com/david-resnick/anki-addon-adjust-review-times

## Description
Corrects review timestamps when you study in a different timezone from home — fixing streaks, heatmaps, and daily counts that get attributed to the wrong date while traveling.

## Features

- Preview all changes before applying
- Automatic collection backup before any modifications
- Full adjustment history with export to JSON
- Forces a full sync after applying (direct revlog changes can't be incrementally synced)
- Supports any IANA timezone name

## Usage

1. **Tools → Adjust Review Times (Timezone)** — set your home timezone on first run, then select the date range you were traveling and the timezone you were in. Click *Update Preview* to see what will change, then *Apply*.
2. **Tools → View Adjustment History** — review a log of all past adjustments.

After applying, Anki will require a full one-way upload on the next sync — choose **Upload to AnkiWeb** to push the corrected timestamps.

## Source

https://github.com/david-resnick/anki-addon-adjust-review-times
