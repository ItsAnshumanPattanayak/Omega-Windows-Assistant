"""Deterministic, non-executing command understanding for Omega."""

from omega.understanding.aliases import ApplicationAliasRegistry
from omega.understanding.entities import RuleBasedEntityExtractor
from omega.understanding.intents import RuleBasedIntentDetector
from omega.understanding.normalizer import CommandNormalizer
from omega.understanding.parser import CommandParser
from omega.understanding.result import CommandParseResult

__all__ = [
    "ApplicationAliasRegistry",
    "CommandNormalizer",
    "CommandParseResult",
    "CommandParser",
    "RuleBasedEntityExtractor",
    "RuleBasedIntentDetector",
]
