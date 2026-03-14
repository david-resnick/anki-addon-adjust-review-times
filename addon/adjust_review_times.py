"""Adjust review timestamps to correct for timezone skew."""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import json
import sys

try:
    from zoneinfo import ZoneInfo
    pytz = None
except ImportError:
    # Fallback for Python < 3.9
    try:
        from backports.zoneinfo import ZoneInfo
        pytz = None
    except ImportError:
        # Fallback to pytz if available
        try:
            import pytz
            ZoneInfo = None  # Will use pytz instead
        except ImportError:
            from aqt.utils import showWarning
            showWarning("Timezone support requires Python 3.9+ with zoneinfo or pytz package")
            raise

from aqt import mw
from aqt.utils import showInfo, showWarning, qconnect
from aqt.qt import *

# Config keys
CONFIG_KEY_HOME_TZ = "review_timezone_adjuster.home_tz"
CONFIG_KEY_ADJUSTMENTS = "review_timezone_adjuster.adjustments"


def get_timezone_list():
    """Get a sorted list of common timezone names."""
    # Common timezones grouped by region
    timezones = [
        # Americas
        "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
        "America/Toronto", "America/Vancouver", "America/Mexico_City", "America/Sao_Paulo",
        "America/Buenos_Aires",
        # Europe
        "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
        "Europe/Amsterdam", "Europe/Stockholm", "Europe/Moscow", "Europe/Istanbul",
        # Asia
        "Asia/Tokyo", "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Singapore", "Asia/Bangkok",
        "Asia/Kolkata", "Asia/Dubai", "Asia/Seoul", "Asia/Jakarta", "Asia/Manila",
        "Asia/Jerusalem",
        # Oceania
        "Australia/Sydney", "Australia/Melbourne", "Pacific/Auckland",
        # UTC
        "UTC",
    ]
    return sorted(timezones)


def get_timezone(tz_name):
    """Get a timezone object from a timezone name."""
    if ZoneInfo is not None:
        return ZoneInfo(tz_name)
    else:
        # Fallback to pytz (should be imported at module level)
        return pytz.timezone(tz_name)


def get_home_timezone():
    """Retrieve home timezone from config."""
    if not mw or not mw.col:
        return None
    return mw.col.conf.get(CONFIG_KEY_HOME_TZ)


def set_home_timezone(tz_name):
    """Store home timezone in config."""
    if not mw or not mw.col:
        return False
    mw.col.conf[CONFIG_KEY_HOME_TZ] = tz_name
    mw.col.setMod()
    return True


def configure_home_timezone():
    """Show dialog to configure home timezone."""
    if not mw or not mw.col:
        showWarning("No collection open")
        return

    dialog = QDialog(mw)
    dialog.setWindowTitle("Timezone Adjuster - Configure Home Timezone")
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.resize(500, 200)

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    # Description
    desc = QLabel("Set your home timezone. This will be used for all timezone adjustments.")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    # Current timezone display
    current_tz = get_home_timezone()
    if current_tz:
        current_label = QLabel(f"Current home timezone: <b>{current_tz}</b>")
        layout.addWidget(current_label)

    # Timezone selector
    tz_layout = QHBoxLayout()
    tz_label = QLabel("Home Timezone:")
    tz_combo = QComboBox()
    tz_combo.setEditable(True)  # Allow custom timezone names
    tz_combo.addItems(get_timezone_list())

    if current_tz:
        index = tz_combo.findText(current_tz)
        if index >= 0:
            tz_combo.setCurrentIndex(index)
        else:
            tz_combo.setEditText(current_tz)

    tz_layout.addWidget(tz_label)
    tz_layout.addWidget(tz_combo)
    layout.addLayout(tz_layout)

    # Buttons
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    cancel_button = QPushButton("Cancel")
    qconnect(cancel_button.clicked, dialog.reject)
    button_layout.addWidget(cancel_button)

    save_button = QPushButton("Save")
    save_button.setDefault(True)
    qconnect(save_button.clicked, dialog.accept)
    button_layout.addWidget(save_button)

    layout.addLayout(button_layout)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        tz_name = tz_combo.currentText().strip()
        if not tz_name:
            showWarning("Please select a timezone")
            return

        # Validate timezone
        try:
            get_timezone(tz_name)
        except Exception as e:
            showWarning(f"Invalid timezone: {tz_name}\n{str(e)}")
            return

        if set_home_timezone(tz_name):
            showInfo(f"Home timezone set to: {tz_name}")


def create_backup():
    """Create a backup of the collection database."""
    if not mw or not mw.col:
        return None

    collection_path = Path(mw.col.path)
    if not collection_path.exists():
        return None

    # Create backup directory in addon folder
    addon_dir = Path(__file__).parent
    backup_dir = addon_dir / "backups"
    backup_dir.mkdir(exist_ok=True)

    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"collection_backup_{timestamp}.anki2"

    try:
        shutil.copy2(collection_path, backup_path)
        return str(backup_path)
    except Exception as e:
        showWarning(f"Failed to create backup: {str(e)}")
        return None


def calculate_adjusted_timestamp(old_timestamp_ms, source_tz_name, home_tz_name):
    """
    Calculate adjusted timestamp preserving wall clock time.

    Args:
        old_timestamp_ms: Original timestamp in milliseconds
        source_tz_name: Timezone where review was done
        home_tz_name: Home timezone to adjust to

    Returns:
        New timestamp in milliseconds
    """
    # Convert to seconds
    old_timestamp_sec = old_timestamp_ms / 1000.0

    # Get timezone objects
    source_tz = get_timezone(source_tz_name)
    home_tz = get_timezone(home_tz_name)

    # Step 1: Interpret old UTC timestamp in source timezone to get wall clock time
    # fromtimestamp interprets the timestamp as UTC and converts to the given timezone
    if ZoneInfo is not None:
        dt_source = datetime.fromtimestamp(old_timestamp_sec, tz=source_tz)
    else:
        # pytz handling
        dt_utc = datetime.fromtimestamp(old_timestamp_sec, tz=timezone.utc)
        dt_source = dt_utc.astimezone(source_tz)

    # Step 2: Extract wall clock time (naive datetime with same hour/minute/second)
    wall_clock_time = dt_source.replace(tzinfo=None)

    # Step 3: Create same wall clock time in home timezone
    # With zoneinfo, constructing datetime with tzinfo means "this time in that timezone"
    if ZoneInfo is not None:
        # zoneinfo: construct datetime with timezone (this means "wall_clock_time in home_tz")
        dt_home = datetime(
            wall_clock_time.year, wall_clock_time.month, wall_clock_time.day,
            wall_clock_time.hour, wall_clock_time.minute, wall_clock_time.second,
            wall_clock_time.microsecond, tzinfo=home_tz
        )
    else:
        # pytz: use localize method to attach timezone to naive datetime
        dt_home = home_tz.localize(wall_clock_time)

    # Convert to UTC and then to milliseconds
    dt_home_utc = dt_home.astimezone(timezone.utc)
    new_timestamp_sec = dt_home_utc.timestamp()
    new_timestamp_ms = int(new_timestamp_sec * 1000)

    return new_timestamp_ms


def preview_adjustments(start_date, end_date, source_tz_name, home_tz_name):
    """
    Preview what adjustments will be made.

    Returns:
        List of tuples: (old_id, new_id, cid, old_datetime, new_datetime)
    """
    if not mw or not mw.col:
        return []

    # Convert date range to timestamps in source timezone
    source_tz = get_timezone(source_tz_name)

    # Start of start_date in source timezone (beginning of day)
    start_dt = datetime.combine(start_date, datetime.min.time())
    if ZoneInfo is not None:
        start_dt = start_dt.replace(tzinfo=source_tz)
    else:
        start_dt = source_tz.localize(start_dt)
    start_ts_ms = int(start_dt.astimezone(timezone.utc).timestamp() * 1000)

    # End of end_date in source timezone (end of day)
    end_dt = datetime.combine(end_date, datetime.max.time())
    if ZoneInfo is not None:
        end_dt = end_dt.replace(tzinfo=source_tz)
    else:
        end_dt = source_tz.localize(end_dt)
    end_ts_ms = int(end_dt.astimezone(timezone.utc).timestamp() * 1000)

    # Expand range slightly to account for timezone offsets (add/subtract 1 day in ms)
    # This ensures we don't miss any reviews due to timezone conversion edge cases
    day_ms = 24 * 60 * 60 * 1000
    query_start_ms = max(0, start_ts_ms - day_ms)
    query_end_ms = end_ts_ms + day_ms

    # Query reviews in this expanded range (based on stored UTC timestamp)
    # We'll filter by actual date in source TZ below
    reviews = mw.col.db.all("""
        SELECT id, cid, ease, time, type
        FROM revlog
        WHERE id >= ? AND id <= ?
        ORDER BY id
    """, query_start_ms, query_end_ms)

    # Filter reviews that actually fall in the date range when interpreted in source TZ
    preview_data = []
    for rev_id, cid, ease, time_ms, rev_type in reviews:
        # Interpret in source timezone
        rev_ts_sec = rev_id / 1000.0
        source_tz_obj = get_timezone(source_tz_name)

        if ZoneInfo is not None:
            dt_source = datetime.fromtimestamp(rev_ts_sec, tz=source_tz_obj)
        else:
            dt_utc = datetime.fromtimestamp(rev_ts_sec, tz=timezone.utc)
            dt_source = dt_utc.astimezone(source_tz_obj)

        # Check if date falls in range
        source_date = dt_source.date()
        if start_date <= source_date <= end_date:
            # Calculate adjusted timestamp
            new_id = calculate_adjusted_timestamp(rev_id, source_tz_name, home_tz_name)

            # Get new datetime for display
            new_ts_sec = new_id / 1000.0
            home_tz_obj = get_timezone(home_tz_name)
            if ZoneInfo is not None:
                dt_home = datetime.fromtimestamp(new_ts_sec, tz=home_tz_obj)
            else:
                dt_utc = datetime.fromtimestamp(new_ts_sec, tz=timezone.utc)
                dt_home = dt_utc.astimezone(home_tz_obj)

            preview_data.append((rev_id, new_id, cid, dt_source, dt_home))

    return preview_data


def write_log_entry(adjustment_data):
    """Write adjustment details to log file."""
    addon_dir = Path(__file__).parent
    log_file = addon_dir / "adjust_review_times.log"

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "adjustment": adjustment_data
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Failed to write log: {e}", file=sys.stderr)


def view_adjustment_history():
    """Show dialog with history of past adjustments."""
    if not mw or not mw.col:
        showWarning("No collection open")
        return

    adjustments = mw.col.conf.get(CONFIG_KEY_ADJUSTMENTS, [])

    if not adjustments:
        showInfo("No adjustments have been made yet.")
        return

    dialog = QDialog(mw)
    dialog.setWindowTitle("Adjustment History")
    dialog.resize(900, 600)

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    # Description
    desc = QLabel(f"History of {len(adjustments)} adjustment(s) made using this addon:")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    # Table to display adjustments
    table = QTableWidget()
    table.setColumnCount(6)
    table.setHorizontalHeaderLabels([
        "Date Range",
        "Source Timezone",
        "Home Timezone",
        "Reviews Adjusted",
        "Adjustment Date",
        "Backup Path"
    ])
    table.horizontalHeader().setStretchLastSection(True)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    # Populate table (reverse order to show most recent first)
    table.setRowCount(len(adjustments))
    for row, adj in enumerate(reversed(adjustments)):
        # Date range
        date_range = adj.get("date_range", {})
        start_date = date_range.get("start", "N/A")
        end_date = date_range.get("end", "N/A")
        try:
            # Parse and format dates nicely
            start_dt = datetime.fromisoformat(start_date.split("T")[0])
            end_dt = datetime.fromisoformat(end_date.split("T")[0])
            date_str = f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"
        except Exception:
            date_str = f"{start_date} to {end_date}"

        table.setItem(row, 0, QTableWidgetItem(date_str))

        # Source timezone
        table.setItem(row, 1, QTableWidgetItem(adj.get("source_timezone", "N/A")))

        # Home timezone
        table.setItem(row, 2, QTableWidgetItem(adj.get("home_timezone", "N/A")))

        # Reviews adjusted
        table.setItem(row, 3, QTableWidgetItem(str(adj.get("reviews_adjusted", 0))))

        # Adjustment timestamp
        adj_timestamp = adj.get("timestamp", "N/A")
        try:
            # Handle various ISO format variations
            timestamp_clean = adj_timestamp.replace("Z", "+00:00")
            if "T" in timestamp_clean:
                adj_dt = datetime.fromisoformat(timestamp_clean.split(".")[0])  # Remove microseconds if present
            else:
                adj_dt = datetime.fromisoformat(timestamp_clean)
            timestamp_str = adj_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback to original if parsing fails
            timestamp_str = str(adj_timestamp)
        table.setItem(row, 4, QTableWidgetItem(timestamp_str))

        # Backup path
        backup_path = adj.get("backup_path", "N/A")
        if backup_path != "N/A":
            # Show just the filename
            backup_file = Path(backup_path).name
            table.setItem(row, 5, QTableWidgetItem(backup_file))
            # Store full path in tooltip
            table.item(row, 5).setToolTip(backup_path)
        else:
            table.setItem(row, 5, QTableWidgetItem(backup_path))

    # Resize columns to content
    table.resizeColumnsToContents()
    layout.addWidget(table)

    # Buttons
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    # Export button (optional - could export to CSV or JSON)
    export_button = QPushButton("Export to JSON...")
    def export_history():
        from aqt.utils import getFile
        filename = getFile(mw, "Export adjustment history", "export", key="adjustment_history", ext=".json")
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(adjustments, f, indent=2)
                showInfo(f"History exported to {filename}")
            except Exception as e:
                showWarning(f"Failed to export: {str(e)}")

    qconnect(export_button.clicked, export_history)
    button_layout.addWidget(export_button)

    close_button = QPushButton("Close")
    close_button.setDefault(True)
    qconnect(close_button.clicked, dialog.accept)
    button_layout.addWidget(close_button)

    layout.addLayout(button_layout)

    dialog.exec()


def apply_adjustments(start_date, end_date, source_tz_name, home_tz_name):
    """Apply timezone adjustments to reviews."""
    if not mw or not mw.col:
        return False, "No collection open"

    # Get preview data
    preview_data = preview_adjustments(start_date, end_date, source_tz_name, home_tz_name)

    if not preview_data:
        return False, "No reviews found in the specified date range"

    # Create backup
    backup_path = create_backup()
    if not backup_path:
        return False, "Failed to create backup. Aborting."

    # Track adjustments for logging
    adjustments_made = []

    # Update each review
    try:
        for old_id, new_id, cid, old_dt, new_dt in preview_data:
            # Check for duplicate timestamps
            existing = mw.col.db.scalar("SELECT COUNT(*) FROM revlog WHERE id = ?", new_id)
            if existing > 0:
                showWarning(f"Warning: Adjustment would create duplicate timestamp {new_id}. Skipping review {old_id}.")
                continue

            # Update the review timestamp
            mw.col.db.execute("""
                UPDATE revlog
                SET id = ?
                WHERE id = ?
            """, new_id, old_id)

            adjustments_made.append({
                "old_id": old_id,
                "new_id": new_id,
                "cid": cid,
                "old_datetime": old_dt.isoformat(),
                "new_datetime": new_dt.isoformat()
            })

        # Record adjustment in config
        if CONFIG_KEY_ADJUSTMENTS not in mw.col.conf:
            mw.col.conf[CONFIG_KEY_ADJUSTMENTS] = []

        adjustment_record = {
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "source_timezone": source_tz_name,
            "home_timezone": home_tz_name,
            "reviews_adjusted": len(adjustments_made),
            "timestamp": datetime.now().isoformat(),
            "backup_path": backup_path
        }

        mw.col.conf[CONFIG_KEY_ADJUSTMENTS].append(adjustment_record)
        mw.col.setMod()

        # Force a full sync on next sync. Direct revlog ID changes can't be
        # handled by incremental sync (the old IDs still exist on the server),
        # so we mark the schema as modified to trigger a one-way upload.
        try:
            mw.col.modSchema(check=False)
        except AttributeError:
            mw.col.mod_schema(check=False)

        # Write to log file
        write_log_entry({
            "adjustment_record": adjustment_record,
            "details": adjustments_made
        })

        return True, f"Successfully adjusted {len(adjustments_made)} reviews. Backup saved to: {backup_path}"

    except Exception as e:
        return False, f"Error during adjustment: {str(e)}"


def adjust_review_times():
    """Main entry point - show adjustment dialog."""
    if not mw or not mw.col:
        showWarning("No collection open")
        return

    # Check if home timezone is configured
    home_tz = get_home_timezone()
    if not home_tz:
        reply = QMessageBox.question(
            mw,
            "Home Timezone Not Set",
            "Home timezone is not configured. Would you like to configure it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            configure_home_timezone()
            home_tz = get_home_timezone()
            if not home_tz:
                return
        else:
            return

    dialog = QDialog(mw)
    dialog.setWindowTitle("Adjust Review Times (Timezone)")
    dialog.resize(600, 400)

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    # Description
    desc = QLabel(
        "Adjust review timestamps to correct for timezone skew. "
        "Reviews done in the source timezone will be adjusted to appear "
        "as if done at the same wall clock time in your home timezone."
    )
    desc.setWordWrap(True)
    layout.addWidget(desc)

    # Home timezone display
    home_tz_layout = QHBoxLayout()
    home_tz_label = QLabel("Home Timezone:")
    home_tz_display = QLabel(f"<b>{home_tz}</b>")
    home_tz_button = QPushButton("Change...")

    def change_home_tz():
        dialog.reject()
        configure_home_timezone()
        # Reopen dialog if home TZ is still set
        new_home_tz = get_home_timezone()
        if new_home_tz:
            adjust_review_times()

    qconnect(home_tz_button.clicked, change_home_tz)
    home_tz_layout.addWidget(home_tz_label)
    home_tz_layout.addWidget(home_tz_display)
    home_tz_layout.addWidget(home_tz_button)
    home_tz_layout.addStretch()
    layout.addLayout(home_tz_layout)

    # Date range
    date_layout = QHBoxLayout()
    date_layout.addWidget(QLabel("Start Date:"))
    start_date = QDateEdit()
    start_date.setCalendarPopup(True)
    start_date.setDate(QDate.currentDate().addDays(-30))
    date_layout.addWidget(start_date)

    date_layout.addWidget(QLabel("End Date:"))
    end_date = QDateEdit()
    end_date.setCalendarPopup(True)
    end_date.setDate(QDate.currentDate())
    date_layout.addWidget(end_date)
    layout.addLayout(date_layout)

    # Source timezone
    source_tz_layout = QHBoxLayout()
    source_tz_label = QLabel("Source Timezone (where reviews were done):")
    source_tz_combo = QComboBox()
    source_tz_combo.setEditable(True)
    source_tz_combo.addItems(get_timezone_list())
    source_tz_layout.addWidget(source_tz_label)
    source_tz_layout.addWidget(source_tz_combo)
    layout.addLayout(source_tz_layout)

    # Timezone offset display
    offset_label = QLabel("Timezone Offset: <b>--</b> hours")
    offset_label.setStyleSheet("color: #666; font-size: 11pt;")
    layout.addWidget(offset_label)

    def adjust_column_widths():
        """Adjust column widths to fit content."""
        preview_table.resizeColumnsToContents()
        # Set minimum column widths to ensure headers are visible
        for col in range(preview_table.columnCount()):
            header_item = preview_table.horizontalHeaderItem(col)
            if header_item:
                min_width = preview_table.fontMetrics().boundingRect(
                    header_item.text()
                ).width() + 20
                current_width = preview_table.columnWidth(col)
                preview_table.setColumnWidth(col, max(current_width, min_width))

    def calculate_offset():
        """Calculate and display timezone offset in hours."""
        source_tz_name = source_tz_combo.currentText().strip()
        if not source_tz_name:
            offset_label.setText("Timezone Offset: <b>--</b> hours")
            adjust_column_widths()  # Adjust columns even when timezone is cleared
            return

        try:
            source_tz = get_timezone(source_tz_name)
            home_tz_obj = get_timezone(home_tz)

            # Get current time in both timezones to calculate offset
            now = datetime.now(timezone.utc)
            if ZoneInfo is not None:
                now_source = now.astimezone(source_tz)
                now_home = now.astimezone(home_tz_obj)
            else:
                now_source = now.astimezone(source_tz)
                now_home = now.astimezone(home_tz_obj)

            # Calculate offset: difference between source and home timezone
            # Positive means source is ahead of home
            offset_seconds = (now_source.utcoffset() - now_home.utcoffset()).total_seconds()
            offset_hours = offset_seconds / 3600.0

            if offset_hours > 0:
                offset_text = f"<b>+{offset_hours:.1f}</b> hours (source is ahead)"
            elif offset_hours < 0:
                offset_text = f"<b>{offset_hours:.1f}</b> hours (source is behind)"
            else:
                offset_text = "<b>0</b> hours (same timezone)"

            offset_label.setText(f"Timezone Offset: {offset_text}")
            adjust_column_widths()  # Adjust columns when timezone changes
        except Exception:
            offset_label.setText("Timezone Offset: <b>--</b> hours")
            adjust_column_widths()

    # Update offset when timezone changes
    qconnect(source_tz_combo.currentTextChanged, calculate_offset)

    # Preview area
    preview_label = QLabel("Preview:")
    layout.addWidget(preview_label)

    preview_table = QTableWidget()
    preview_table.setColumnCount(7)
    preview_table.setHorizontalHeaderLabels([
        "Old Time (Source TZ)", "New Time (Home TZ)", "Old UTC", "New UTC",
        "Card ID", "Old Date", "New Date"
    ])
    preview_table.horizontalHeader().setStretchLastSection(False)
    layout.addWidget(preview_table)

    def update_preview():
        """Update preview table."""
        qstart = start_date.date()
        qend = end_date.date()
        # Convert QDate to Python date
        start = datetime(qstart.year(), qstart.month(), qstart.day()).date()
        end = datetime(qend.year(), qend.month(), qend.day()).date()
        source_tz = source_tz_combo.currentText().strip()

        if not source_tz:
            preview_table.setRowCount(0)
            return

        try:
            get_timezone(source_tz)
        except Exception:
            preview_table.setRowCount(0)
            return

        preview_data = preview_adjustments(start, end, source_tz, home_tz)
        preview_table.setRowCount(len(preview_data))

        for row, (old_id, new_id, cid, old_dt, new_dt) in enumerate(preview_data):
            # Old time in source timezone (with timezone indicator)
            old_tz_name = source_tz.split('/')[-1] if '/' in source_tz else source_tz
            preview_table.setItem(row, 0, QTableWidgetItem(
                f"{old_dt.strftime('%Y-%m-%d %H:%M:%S')} ({old_tz_name})"
            ))

            # New time in home timezone (with timezone indicator)
            home_tz_name = home_tz.split('/')[-1] if '/' in home_tz else home_tz
            preview_table.setItem(row, 1, QTableWidgetItem(
                f"{new_dt.strftime('%Y-%m-%d %H:%M:%S')} ({home_tz_name})"
            ))

            # UTC times to show the actual difference
            old_utc = datetime.fromtimestamp(old_id / 1000.0, tz=timezone.utc)
            new_utc = datetime.fromtimestamp(new_id / 1000.0, tz=timezone.utc)

            # Calculate and show the difference
            diff_seconds = (new_id - old_id) / 1000.0
            diff_hours = diff_seconds / 3600.0
            diff_str = f" ({diff_hours:+.1f}h)" if abs(diff_hours) > 0.01 else ""

            preview_table.setItem(row, 2, QTableWidgetItem(
                f"{old_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            ))
            preview_table.setItem(row, 3, QTableWidgetItem(
                f"{new_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC{diff_str}"
            ))

            preview_table.setItem(row, 4, QTableWidgetItem(str(cid)))
            preview_table.setItem(row, 5, QTableWidgetItem(old_dt.date().isoformat()))
            preview_table.setItem(row, 6, QTableWidgetItem(new_dt.date().isoformat()))

        # Adjust column widths after populating data
        adjust_column_widths()

    # Update preview function (only called when button is clicked)
    def update_preview_and_offset():
        calculate_offset()  # This will also call adjust_column_widths()
        update_preview()

    # Only update offset when timezone changes (not preview table)
    def update_offset_only():
        calculate_offset()

    qconnect(source_tz_combo.currentTextChanged, update_offset_only)

    # Initial offset calculation and column width adjustment
    calculate_offset()
    adjust_column_widths()

    # Buttons
    button_layout = QHBoxLayout()

    update_preview_button = QPushButton("Update Preview")
    qconnect(update_preview_button.clicked, update_preview_and_offset)
    button_layout.addWidget(update_preview_button)

    button_layout.addStretch()

    cancel_button = QPushButton("Cancel")
    qconnect(cancel_button.clicked, dialog.reject)
    button_layout.addWidget(cancel_button)

    apply_button = QPushButton("Apply Adjustments")
    apply_button.setDefault(True)
    qconnect(apply_button.clicked, dialog.accept)
    button_layout.addWidget(apply_button)

    layout.addLayout(button_layout)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        qstart = start_date.date()
        qend = end_date.date()
        # Convert QDate to Python date
        start = datetime(qstart.year(), qstart.month(), qstart.day()).date()
        end = datetime(qend.year(), qend.month(), qend.day()).date()
        source_tz = source_tz_combo.currentText().strip()

        if not source_tz:
            showWarning("Please select a source timezone")
            return

        # Validate timezone
        try:
            get_timezone(source_tz)
        except Exception as e:
            showWarning(f"Invalid timezone: {source_tz}\n{str(e)}")
            return

        # Confirm
        preview_count = preview_table.rowCount()
        reply = QMessageBox.question(
            mw,
            "Confirm Adjustment",
            f"This will adjust {preview_count} reviews. A backup will be created first.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = apply_adjustments(start, end, source_tz, home_tz)
            if success:
                showInfo(message)
            else:
                showWarning(message)

