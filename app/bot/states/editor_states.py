"""FSM states for interactive audio metadata editing."""

from aiogram.fsm.state import State, StatesGroup


class EditorStates(StatesGroup):
    """FSM states representing user interaction steps."""
    idle = State()
    waiting_for_field_value = State()
    waiting_for_cover = State()
    confirming_cover = State()
    waiting_for_lyrics = State()
    waiting_for_filename = State()
    waiting_for_cut_range = State()
    confirming_cut = State()
