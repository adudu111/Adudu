"""Profile business logic.

Owns the "active profile" concept (persisted in the DB ``settings`` table) and delegates
all persistence to repositories. Contains no UI or SQL.
"""

from __future__ import annotations

from cyberglossary.database.models import Profile
from cyberglossary.database.repositories import (
    ProfileNotFoundError,
    ProfileRepository,
    SettingsRepository,
)

# DB settings key storing the id of the active profile (as a decimal string).
ACTIVE_PROFILE_KEY = "active_profile_id"


class ProfileService:
    def __init__(self, profiles: ProfileRepository, settings: SettingsRepository) -> None:
        self._profiles = profiles
        self._settings = settings

    def create_profile(
        self, name: str, description: str = "", color: str | None = None
    ) -> Profile:
        name = name.strip()
        if not name:
            raise ValueError("Profile name must not be empty.")
        profile = self._profiles.create(name=name, description=description, color=color)
        if self.get_active_profile_id() is None:
            self._settings.set(ACTIVE_PROFILE_KEY, str(profile.id))
        return profile

    def get_profile(self, profile_id: int) -> Profile | None:
        return self._profiles.get(profile_id)

    def list_profiles(self) -> list[Profile]:
        return self._profiles.list_all()

    def rename_profile(self, profile_id: int, name: str) -> Profile:
        name = name.strip()
        if not name:
            raise ValueError("Profile name must not be empty.")
        return self._profiles.rename(profile_id, name)

    def set_description(self, profile_id: int, description: str) -> Profile:
        return self._profiles.set_description(profile_id, description)

    def set_color(self, profile_id: int, color: str | None) -> Profile:
        return self._profiles.set_color(profile_id, color)

    def reorder_profiles(self, ordered_ids: list[int]) -> None:
        self._profiles.reorder(ordered_ids)

    def delete_profile(self, profile_id: int) -> None:
        self._profiles.delete(profile_id)
        if self.get_active_profile_id() != profile_id:
            return
        remaining = self._profiles.list_all()
        if remaining:
            # Keep an active profile: fall back to the first remaining profile.
            self._settings.set(ACTIVE_PROFILE_KEY, str(remaining[0].id))
        else:
            self._settings.delete(ACTIVE_PROFILE_KEY)

    def get_active_profile_id(self) -> int | None:
        raw = self._settings.get(ACTIVE_PROFILE_KEY)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def get_active_profile(self) -> Profile | None:
        profile_id = self.get_active_profile_id()
        if profile_id is None:
            return None
        return self._profiles.get(profile_id)

    def set_active_profile(self, profile_id: int) -> Profile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)
        self._settings.set(ACTIVE_PROFILE_KEY, str(profile_id))
        return profile
