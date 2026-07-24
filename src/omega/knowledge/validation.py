"""Approved-root, signature, and size validation for explicit document imports."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSourceType
from omega.knowledge.exceptions import (
    DocumentValidationError,
    UnsupportedDocumentError,
)
from omega.utils.paths import project_root

_EXECUTABLE = frozenset(
    {
        ".bat",
        ".cmd",
        ".com",
        ".cpl",
        ".dll",
        ".exe",
        ".hta",
        ".js",
        ".jse",
        ".lnk",
        ".msi",
        ".ps1",
        ".py",
        ".scr",
        ".vbs",
        ".wsf",
    }
)
_PEM_MARKER = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?(?:PRIVATE KEY|CERTIFICATE)-----"
)
_SENSITIVE_NAME = re.compile(
    r"(?:credential|password|private[-_ ]?key|secret|token)", re.IGNORECASE
)


@dataclass(frozen=True)
class ValidatedKnowledgeFile:
    path: Path
    source_type: KnowledgeSourceType
    size_bytes: int
    fingerprint: str


class KnowledgeFileValidator:
    """Validate one explicitly selected regular file under approved roots."""

    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        approved_roots: tuple[Path, ...],
        protected_roots: tuple[Path, ...] | None = None,
    ) -> None:
        self.configuration = configuration
        self.approved_roots = tuple(
            root.resolve(strict=False) for root in approved_roots
        )
        if not self.approved_roots:
            raise DocumentValidationError(
                "At least one approved document root is required."
            )
        project = project_root()
        selected_protected = (
            protected_roots
            if protected_roots is not None
            else (
                project / ".git",
                project / "config",
                project / "data" / "database",
                project / "data" / "logs",
            )
        )
        self.protected_roots = tuple(
            root.resolve(strict=False) for root in selected_protected
        )

    def validate(self, path: Path) -> ValidatedKnowledgeFile:
        if not isinstance(path, Path):
            raise DocumentValidationError("A document path is required.")
        raw = str(path)
        windows = PureWindowsPath(raw)
        if raw.startswith("\\\\") or windows.drive.casefold().startswith("\\\\"):
            raise DocumentValidationError("Network document paths are not approved.")
        if raw.startswith("\\\\.\\") or raw.startswith("\\\\?\\"):
            raise DocumentValidationError("Windows device paths are not approved.")
        try:
            candidate = path.resolve(strict=True)
        except OSError as error:
            raise DocumentValidationError(
                "The selected document does not exist or is unavailable."
            ) from error
        if not any(self._contained(candidate, root) for root in self.approved_roots):
            raise DocumentValidationError(
                "The document is outside Omega's approved local locations."
            )
        if any(self._contained(candidate, root) for root in self.protected_roots):
            raise DocumentValidationError(
                "Omega runtime, configuration, and repository metadata are protected."
            )
        if _SENSITIVE_NAME.search(candidate.name):
            raise DocumentValidationError(
                "Files identified as credentials, secrets, tokens, or private keys "
                "are not approved for indexing."
            )
        if path.is_symlink() or not candidate.is_file():
            raise DocumentValidationError(
                "The selected document must be a regular non-symbolic-link file."
            )
        if any(part.startswith(".") for part in candidate.parts[1:]):
            raise DocumentValidationError("Hidden document paths are not approved.")
        suffix = candidate.suffix.casefold()
        if (
            suffix in _EXECUTABLE
            or suffix not in self.configuration.supported_extensions
        ):
            raise UnsupportedDocumentError("That document type is not supported.")
        stat = candidate.stat()
        if stat.st_size <= 0 or stat.st_size > self.configuration.maximum_file_bytes:
            raise DocumentValidationError(
                "The document is empty or exceeds the size limit."
            )
        if not os.path.isfile(candidate):
            raise DocumentValidationError("The selected path is not a regular file.")
        with candidate.open("rb") as stream:
            head = stream.read(min(stat.st_size, 8_192))
            digest = hashlib.sha256()
            digest.update(head)
            while block := stream.read(1024 * 1024):
                digest.update(block)
        if _PEM_MARKER.search(head):
            raise DocumentValidationError(
                "Credential and private-key documents are not approved for indexing."
            )
        source_type = self._source_type(suffix)
        self._signature(source_type, head)
        return ValidatedKnowledgeFile(
            candidate, source_type, stat.st_size, digest.hexdigest()
        )

    @staticmethod
    def _contained(candidate: Path, root: Path) -> bool:
        try:
            return os.path.commonpath(
                (os.path.normcase(candidate), os.path.normcase(root))
            ) == os.path.normcase(root)
        except ValueError:
            return False

    @staticmethod
    def _source_type(suffix: str) -> KnowledgeSourceType:
        return {
            ".pdf": KnowledgeSourceType.PDF,
            ".docx": KnowledgeSourceType.DOCX,
            ".txt": KnowledgeSourceType.TEXT,
            ".md": KnowledgeSourceType.MARKDOWN,
            ".markdown": KnowledgeSourceType.MARKDOWN,
        }[suffix]

    @staticmethod
    def _signature(source_type: KnowledgeSourceType, head: bytes) -> None:
        if source_type is KnowledgeSourceType.PDF and not head.startswith(b"%PDF-"):
            raise DocumentValidationError("The selected PDF has an invalid signature.")
        if source_type is KnowledgeSourceType.DOCX and not head.startswith(b"PK"):
            raise DocumentValidationError("The selected DOCX has an invalid signature.")
        if source_type in {KnowledgeSourceType.TEXT, KnowledgeSourceType.MARKDOWN}:
            if b"\x00" in head:
                raise DocumentValidationError(
                    "The selected text document appears to be binary."
                )
