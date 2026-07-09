# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/script_class.py
"""
Script classification data types v2.
Feature-driven: classifier outputs full feature set, not a single class_id.
"""

from dataclasses import dataclass
from typing import FrozenSet


# ── BAT features ──
FEATURE_FOR = 'FOR'
FEATURE_NESTED_FOR = 'NESTED_FOR'
FEATURE_GOTO = 'GOTO'
FEATURE_IF = 'IF'
FEATURE_CALL = 'CALL'
FEATURE_SET_P = 'SET_P'
FEATURE_DELAYED_EXPANSION = 'DELAYED_EXPANSION'
FEATURE_DYNAMIC_VAR = 'DYNAMIC_VAR'
FEATURE_PERCENT_VAR = 'PERCENT_VAR'
FEATURE_INDIRECT_TOOL = 'INDIRECT_TOOL'
FEATURE_CHCP = 'CHCP'
FEATURE_PAUSE = 'PAUSE'
FEATURE_TIMEOUT = 'TIMEOUT'
FEATURE_EXIT = 'EXIT'
FEATURE_PREFIXED_FASTBOOT = 'PREFIXED_FASTBOOT'
FEATURE_PLAIN_COMMANDS = 'PLAIN_COMMANDS'

BAT_FEATURES_ALL = frozenset({
    FEATURE_FOR, FEATURE_NESTED_FOR, FEATURE_GOTO, FEATURE_IF,
    FEATURE_CALL, FEATURE_SET_P, FEATURE_DELAYED_EXPANSION,
    FEATURE_DYNAMIC_VAR, FEATURE_PERCENT_VAR, FEATURE_INDIRECT_TOOL,
    FEATURE_CHCP, FEATURE_PAUSE, FEATURE_TIMEOUT, FEATURE_EXIT,
    FEATURE_PREFIXED_FASTBOOT, FEATURE_PLAIN_COMMANDS,
})

# ── SH features ──
FEATURE_SH_FOR = 'SH_FOR'
FEATURE_SH_WHILE = 'SH_WHILE'
FEATURE_SH_IF = 'SH_IF'
FEATURE_SH_CASE = 'SH_CASE'
FEATURE_DOLLAR_SUB = 'DOLLAR_SUB'
FEATURE_BACKTICK = 'BACKTICK'
FEATURE_DOLLAR_BRACE = 'DOLLAR_BRACE'
FEATURE_PIPE = 'PIPE'
FEATURE_REDIRECT = 'REDIRECT'
FEATURE_GREP = 'GREP'
FEATURE_SHEBANG = 'SHEBANG'
FEATURE_DIRNAME = 'DIRNAME'
FEATURE_EXIT_CODE = 'EXIT_CODE'
FEATURE_SH_VENDOR = 'SH_VENDOR'
FEATURE_SH_COMMUNITY = 'SH_COMMUNITY'
FEATURE_SH_PLAIN = 'SH_PLAIN'

SH_FEATURES_ALL = frozenset({
    FEATURE_SH_FOR, FEATURE_SH_WHILE, FEATURE_SH_IF, FEATURE_SH_CASE,
    FEATURE_DOLLAR_SUB, FEATURE_BACKTICK, FEATURE_DOLLAR_BRACE,
    FEATURE_PIPE, FEATURE_REDIRECT, FEATURE_GREP,
    FEATURE_SHEBANG, FEATURE_DIRNAME, FEATURE_EXIT_CODE,
    FEATURE_SH_VENDOR, FEATURE_SH_COMMUNITY, FEATURE_SH_PLAIN,
})


@dataclass(frozen=True)
class FeatureVector:
    features: FrozenSet[str]
    script_type: str

    def to_key(self) -> str:
        return self.script_type + ':' + ','.join(sorted(self.features))

    @classmethod
    def from_set(cls, features: frozenset, script_type: str):
        return cls(features=features, script_type=script_type)


@dataclass
class ClassifyResult:
    success: bool = True
    feature_vector: FeatureVector | None = None
    error: str = ''

    @property
    def features(self):
        return self.feature_vector.features if self.feature_vector else None

    @property
    def script_type(self):
        return self.feature_vector.script_type if self.feature_vector else ''


@dataclass
class ClassMatchResult:
    matched: bool = False
    class_id: str = 'generic'
    class_name: str = 'generic'


__all__ = [
    'FeatureVector', 'ClassifyResult', 'ClassMatchResult',
    'BAT_FEATURES_ALL', 'SH_FEATURES_ALL',
    'FEATURE_FOR', 'FEATURE_NESTED_FOR', 'FEATURE_GOTO', 'FEATURE_IF',
    'FEATURE_CALL', 'FEATURE_SET_P',
    'FEATURE_DELAYED_EXPANSION', 'FEATURE_DYNAMIC_VAR', 'FEATURE_PERCENT_VAR',
    'FEATURE_INDIRECT_TOOL',
    'FEATURE_CHCP', 'FEATURE_PAUSE', 'FEATURE_TIMEOUT', 'FEATURE_EXIT',
    'FEATURE_PREFIXED_FASTBOOT', 'FEATURE_PLAIN_COMMANDS',
    'FEATURE_SH_FOR', 'FEATURE_SH_WHILE', 'FEATURE_SH_IF', 'FEATURE_SH_CASE',
    'FEATURE_DOLLAR_SUB', 'FEATURE_BACKTICK', 'FEATURE_DOLLAR_BRACE',
    'FEATURE_PIPE', 'FEATURE_REDIRECT', 'FEATURE_GREP',
    'FEATURE_SHEBANG', 'FEATURE_DIRNAME', 'FEATURE_EXIT_CODE',
    'FEATURE_SH_VENDOR', 'FEATURE_SH_COMMUNITY', 'FEATURE_SH_PLAIN',
]
