"""Single typed view of Omega application and installer metadata."""

from __future__ import annotations

from dataclasses import dataclass

from omega.utils.constants import APP_VERSION, DISTRIBUTION_NAME


@dataclass(frozen=True, slots=True)
class ApplicationMetadata:
    name: str
    package_name: str
    version: str
    publisher: str
    developer: str
    description: str
    repository_url: str
    developer_url: str
    support_url: str
    updates_url: str
    copyright: str
    license_name: str
    gui_executable: str
    cli_executable: str


APPLICATION_METADATA = ApplicationMetadata(
    name="Omega Windows Assistant",
    package_name=DISTRIBUTION_NAME,
    version=APP_VERSION,
    publisher="Anshuman Pattanayak",
    developer="Anshuman Pattanayak",
    description=(
        "A safety-first, local-first Windows desktop assistant developed by "
        "Anshuman Pattanayak."
    ),
    repository_url=("https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant"),
    developer_url="https://github.com/ItsAnshumanPattanayak",
    support_url=(
        "https://github.com/ItsAnshumanPattanayak/" "Omega-Windows-Assistant/issues"
    ),
    updates_url=(
        "https://github.com/ItsAnshumanPattanayak/" "Omega-Windows-Assistant/releases"
    ),
    copyright="Copyright (c) 2026 Anshuman Pattanayak",
    license_name="MIT",
    gui_executable="Omega.exe",
    cli_executable="OmegaCLI.exe",
)
