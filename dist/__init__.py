"""
Anki Add-on: Adjust Review Times (Timezone)

Adjust review timestamps to correct for timezone skew.
"""

from aqt import mw
from aqt.utils import qconnect
from aqt.qt import *
from .adjust_review_times import configure_home_timezone, adjust_review_times, view_adjustment_history

# Register addon config dialog
try:
    addon_id = mw.addonManager.addonFromModule(__name__)
    if addon_id:
        mw.addonManager.setConfigAction(addon_id, configure_home_timezone)
except Exception:
    pass

# Timezone adjustment tools
mw.form.menuTools.addSeparator()
action_adjust_times = QAction("Adjust Review Times (Timezone)", mw)
qconnect(action_adjust_times.triggered, adjust_review_times)
mw.form.menuTools.addAction(action_adjust_times)

action_view_history = QAction("View Adjustment History", mw)
qconnect(action_view_history.triggered, view_adjustment_history)
mw.form.menuTools.addAction(action_view_history)
