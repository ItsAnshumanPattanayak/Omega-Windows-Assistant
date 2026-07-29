"""Single typed view of Omega application and installer metadata."""

from __future__ import annotations

from dataclasses import dataclass

from omega.utils.constants import APP_NAME, APP_VERSION, DISTRIBUTION_NAME


@dataclass(frozen=True, slots=True)
class ApplicationMetadata:
    name: str
    package_name: str
    version: str
    publisher: str
    description: str
    repository_url: str
    license_name: str
    gui_executable: str
    cli_executable: str


APPLICATION_METADATA = ApplicationMetadata(
    name=APP_NAME,
    package_name=DISTRIBUTION_NAME,
    version=APP_VERSION,
    publisher="Omega contributors",
    description="A safety-first Windows desktop assistant.",
    repository_url=("https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant"),
    license_name="MIT",
    gui_executable="Omega.exe",
    cli_executable="OmegaCLI.exe",
)
