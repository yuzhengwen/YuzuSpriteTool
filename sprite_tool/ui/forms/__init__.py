"""Settings panels. Each one emits `changed` and builds a core settings object."""
from .pack_form import PackLayoutForm
from .slice_form import SliceSettingsForm

__all__ = ["PackLayoutForm", "SliceSettingsForm"]
