"""Session end (logoff/shutdown) handling: prompt, cancel, flush."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from pcc.core.projects import load_project
from pcc.gui import app as app_mod
from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState

SB = QMessageBox.StandardButton


class FakeManager:
    def __init__(self, interact):
        self.interact = interact
        self.calls = []

    def allowsInteraction(self):
        self.calls.append("allows")
        return self.interact

    def release(self):
        self.calls.append("release")

    def cancel(self):
        self.calls.append("cancel")


def _window(qtbot, monkeypatch, dirty=True, choice=SB.Cancel):
    state = AppState(legacy_paths=[])
    w = MainWindow(state)
    qtbot.addWidget(w)
    path = state.new_project("Sess")
    if dirty:
        state.add_plate()
    asked, flushed = [], []
    monkeypatch.setattr(MainWindow, "_ask_save",
                        lambda self, name: asked.append(name) or choice)
    real_flush = state.flush
    monkeypatch.setattr(state, "flush", lambda: flushed.append(1) or real_flush())
    return state, w, path, asked, flushed


@pytest.mark.parametrize("choice,cancelled,saved", [
    (SB.Cancel, True, False), (SB.Save, False, True), (SB.Discard, False, False)])
def test_dirty_session_end_prompts(qtbot, cfg_dir, data_dir, monkeypatch, choice, cancelled, saved):
    state, w, path, asked, flushed = _window(qtbot, monkeypatch, choice=choice)
    m = FakeManager(True)
    w.commit_session(m)
    assert asked == ["Sess"]
    assert ("cancel" in m.calls) == cancelled
    assert "release" in m.calls
    assert flushed == [1]
    assert (len(load_project(path).job.plates) == 1) == saved


def test_session_end_without_interaction_just_flushes(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, path, asked, flushed = _window(qtbot, monkeypatch)
    m = FakeManager(False)
    w.commit_session(m)
    assert asked == [] and "cancel" not in m.calls and flushed == [1]


def test_clean_session_end_does_not_prompt(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, path, asked, flushed = _window(qtbot, monkeypatch, dirty=False)
    m = FakeManager(True)
    w.commit_session(m)
    assert asked == [] and m.calls == [] and flushed == [1]


def test_session_end_flushes_debounced_settings(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, path, asked, flushed = _window(qtbot, monkeypatch, dirty=False)
    state.update_settings(margin_pct=77.0)  # debounced: not on disk yet
    w.commit_session(FakeManager(False))
    assert AppState(legacy_paths=[]).settings.margin_pct == 77.0


class _Sig:
    def __init__(self):
        self.slots = []

    def connect(self, slot, type=None):
        self.slots.append((slot, type))


class _FakeApp:
    def __init__(self):
        self.commitDataRequest = _Sig()
        self.aboutToQuit = _Sig()


def test_app_wires_session_signals(qtbot, cfg_dir, data_dir):
    state = AppState(legacy_paths=[])
    w = MainWindow(state)
    qtbot.addWidget(w)
    fake = _FakeApp()
    app_mod.wire_session(fake, w, state)
    assert fake.commitDataRequest.slots == [
        (w.commit_session, Qt.ConnectionType.DirectConnection)]
    assert fake.aboutToQuit.slots == [(state.flush, None)]
