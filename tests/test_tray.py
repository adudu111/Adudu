"""Tests for the system tray (menu, profiles, pause state, close-to-tray)."""

from __future__ import annotations

from cyberglossary.windows.tray import TrayController, build_profile_specs


def _profile(profile_service):
    return profile_service.create_profile("Cyber Security")


# --- pure menu-spec helper -------------------------------------------------


def test_build_profile_specs_marks_active():
    from cyberglossary.database.models import Profile

    p1 = Profile(1, "Cyber Security", "", None, 0, "now", "now")
    p2 = Profile(2, "Accounting", "", None, 0, "now", "now")
    specs = build_profile_specs([p1, p2], active_id=2)
    assert [(s.profile_id, s.name, s.checked) for s in specs] == [
        (1, "Cyber Security", False),
        (2, "Accounting", True),
    ]


def test_build_profile_specs_empty():
    assert build_profile_specs([], None) == []


# --- tray object + menu ----------------------------------------------------


def test_tray_creation_builds_menu(qapp, profile_service):
    controller = TrayController(profile_service)

    assert controller.tray is not None
    assert controller.open_action.text() == "Open adudu"
    assert controller.profile_menu.title() == "Active Profile"
    assert controller.pause_action.text() == "Pause Lookup"
    assert controller.pause_action.isCheckable()
    assert controller.settings_action.text() == "Settings"
    assert controller.exit_action.text() == "Exit"


def test_active_profile_submenu_generated(qapp, profile_service):
    first = _profile(profile_service)
    second = profile_service.create_profile("Accounting")

    controller = TrayController(profile_service)
    controller.refresh_profiles()

    actions = controller.profile_menu.actions()
    assert [a.text() for a in actions] == ["Cyber Security", "Accounting"]
    assert actions[0].isChecked() is True   # first created is active
    assert actions[1].isChecked() is False
    assert actions[0].data() == first.id
    assert actions[1].data() == second.id


def test_switch_active_profile_from_tray(qapp, profile_service):
    profile_service.create_profile("Cyber Security")
    second = profile_service.create_profile("Accounting")

    controller = TrayController(profile_service)
    controller._on_profile_selected(second.id)

    assert profile_service.get_active_profile_id() == second.id
    actions = controller.profile_menu.actions()
    assert actions[1].isChecked() is True


def test_profile_switch_emits_signal(qapp, profile_service):
    profile_service.create_profile("Cyber Security")
    second = profile_service.create_profile("Accounting")

    controller = TrayController(profile_service)
    emitted = []
    controller.profile_selected.connect(emitted.append)
    controller._on_profile_selected(second.id)
    assert emitted == [second.id]


# --- pause / resume --------------------------------------------------------


def test_pause_resume_state(qapp, profile_service):
    controller = TrayController(profile_service)

    assert controller.is_paused() is False
    assert controller.pause_action.isChecked() is False

    controller.set_paused(True)
    assert controller.is_paused() is True
    assert controller.pause_action.isChecked() is True

    controller.set_paused(False)
    assert controller.is_paused() is False
    assert controller.pause_action.isChecked() is False


def test_pause_toggled_emits_signal(qapp, profile_service):
    controller = TrayController(profile_service)
    emitted = []
    controller.pause_toggled.connect(emitted.append)

    controller.set_paused(True)
    assert emitted == [True]

    controller.set_paused(False)
    assert emitted == [True, False]


def test_initial_paused_state(qapp, profile_service):
    controller = TrayController(profile_service, initial_paused=True)
    assert controller.is_paused() is True
    assert controller.pause_action.isChecked() is True


# --- exit action -----------------------------------------------------------


def test_exit_action_emits_signal(qapp, profile_service):
    controller = TrayController(profile_service)
    emitted = []
    controller.exit_requested.connect(lambda: emitted.append(True))
    controller.exit_action.trigger()
    assert emitted == [True]


# --- close-to-tray (main window) ------------------------------------------


def test_close_to_tray_hides_window(window):
    window.show()
    assert window.isVisible()

    window.close()  # closeEvent ignores and hides

    assert not window.isVisible()
    assert window.is_exiting() is False


def test_exit_application_closes_window(window):
    window.show()

    window.exit_application()

    assert window.is_exiting() is True
    assert not window.isVisible()
