# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/classifier.py
"""
ScriptClassifier v2 — Feature-driven.

Outputs a full FeatureVector (frozenset of feature strings) instead of a
single class_id.  Every feature found in the script is recorded; nothing
is discarded by priority ordering.

Pipeline matching is done by the registry using exact feature-set equality.
"""

import re

from .script_class import (
    FeatureVector, ClassifyResult,
    # BAT
    FEATURE_FOR, FEATURE_NESTED_FOR, FEATURE_GOTO, FEATURE_IF,
    FEATURE_CALL, FEATURE_SET_P,
    FEATURE_DELAYED_EXPANSION, FEATURE_DYNAMIC_VAR, FEATURE_PERCENT_VAR,
    FEATURE_INDIRECT_TOOL,
    FEATURE_CHCP, FEATURE_PAUSE, FEATURE_TIMEOUT, FEATURE_EXIT,
    FEATURE_PREFIXED_FASTBOOT, FEATURE_PLAIN_COMMANDS,
    # SH
    FEATURE_SH_FOR, FEATURE_SH_WHILE, FEATURE_SH_IF, FEATURE_SH_CASE,
    FEATURE_DOLLAR_SUB, FEATURE_BACKTICK, FEATURE_DOLLAR_BRACE,
    FEATURE_PIPE, FEATURE_REDIRECT, FEATURE_GREP,
    FEATURE_SHEBANG, FEATURE_DIRNAME, FEATURE_EXIT_CODE,
    FEATURE_SH_VENDOR, FEATURE_SH_COMMUNITY, FEATURE_SH_PLAIN,
)


# ═══════════════════════════════════════════════════════════════
# BAT feature regexes
# ═══════════════════════════════════════════════════════════════

_RE_FOR           = re.compile(r'\bfor\s+%%\w+\s+in\b', re.IGNORECASE)
_RE_NESTED_FOR    = re.compile(r'for\s+%%\w+\s+in\b.*\bfor\s+%%\w+\s+in\b', re.IGNORECASE)
_RE_GOTO          = re.compile(r'\bgoto\b', re.IGNORECASE)
_RE_LABEL         = re.compile(r'^:\w+', re.MULTILINE)
_RE_IF            = re.compile(r'\bif\s+(exist|not|errorlevel|\S+\s*==|/i)', re.IGNORECASE)
_RE_CALL          = re.compile(r'\bcall\b', re.IGNORECASE)
_RE_SET_P         = re.compile(r'\bset\s+/p\b', re.IGNORECASE)
_RE_DELAYED       = re.compile(r'\bsetlocal\s+enabledelayedexpansion\b', re.IGNORECASE)
_RE_DYNAMIC       = re.compile(r'!\w+!')
_RE_PERCENT_VAR   = re.compile(r'%[A-Z_][A-Z0-9_]*%', re.IGNORECASE)
_RE_INDIRECT_TOOL = re.compile(r'%\w*TOOL\w*%', re.IGNORECASE)
_RE_CHCP          = re.compile(r'\bchcp\b', re.IGNORECASE)
_RE_PAUSE         = re.compile(r'\bpause\b', re.IGNORECASE)
_RE_TIMEOUT       = re.compile(r'\btimeout\b', re.IGNORECASE)
_RE_EXIT          = re.compile(r'\bexit\b', re.IGNORECASE)
_RE_PREFIXED_FB   = re.compile(r'["\x27]\S*\\fastboot\.exe["\x27]', re.IGNORECASE)


def _is_plain_bat(content: str) -> bool:
    """Return True if script has no control flow / variables -- pure fastboot."""
    has_control = any(r.search(content) for r in (
        _RE_FOR, _RE_GOTO, _RE_IF, _RE_CALL, _RE_SET_P,
    ))
    has_var = any(r.search(content) for r in (
        _RE_DELAYED, _RE_DYNAMIC, _RE_PERCENT_VAR, _RE_INDIRECT_TOOL,
    ))
    return not has_control and not has_var


# ═══════════════════════════════════════════════════════════════
# SH feature regexes
# ═══════════════════════════════════════════════════════════════

_RE_SH_FOR       = re.compile(r'\bfor\s+\S+\s+in\b|\bfor\s+\(\(', re.IGNORECASE)
_RE_SH_WHILE     = re.compile(r'\bwhile\s+')
_RE_SH_IF        = re.compile(r'\bif\s+\[\[?\s')
_RE_SH_CASE      = re.compile(r'\bcase\s+\$?\S+\s+in\b')
_RE_DOLLAR_SUB   = re.compile(r'\$\([^)]+\)')
_RE_BACKTICK     = re.compile(r'`[^`]+`')
_RE_DOLLAR_BRACE = re.compile(r'\$\{[^}]+\}')
_RE_PIPE         = re.compile(r'\|')
_RE_REDIRECT     = re.compile(r'[<>]{1,2}')
_RE_GREP         = re.compile(r'\bgrep\b')
_RE_SHEBANG      = re.compile(r'^#!\s*/bin/(ba)?sh', re.MULTILINE)
_RE_DIRNAME      = re.compile(r'\b(dirname|readlink)\b')
_RE_EXIT_CODE    = re.compile(r'\$\?|\bexit\s+[1-9]')
_RE_SH_VENDOR    = re.compile(r'flashing\s+unlock|--disable-verit|fastboot\s+flash\s+partition\b', re.IGNORECASE)
_RE_SH_COMMUNITY = re.compile(r'XDA|\u9177\u5b89|forum\.xda-developers|telegra\.ph', re.IGNORECASE)


def _is_plain_sh(content: str) -> bool:
    """Return True if script has no control flow / variables -- pure fastboot."""
    has_control = any(r.search(content) for r in (
        _RE_SH_FOR, _RE_SH_WHILE, _RE_SH_IF, _RE_SH_CASE,
    ))
    has_expand = any(r.search(content) for r in (
        _RE_DOLLAR_SUB, _RE_BACKTICK, _RE_DOLLAR_BRACE,
        _RE_PIPE, _RE_REDIRECT,
    ))
    has_env = any(r.search(content) for r in (
        _RE_DIRNAME, _RE_EXIT_CODE,
    ))
    return not has_control and not has_expand and not has_env


# ═══════════════════════════════════════════════════════════════
# Classifier
# ═══════════════════════════════════════════════════════════════

class ScriptClassifier:
    """
    V2 classifier: detect *all* features, output FeatureVector.

    No priority chain, no early-return -- every regex is checked,
    every matched feature is added to the set.
    """

    def classify(self, content: str = "", script_type: str = "") -> ClassifyResult:
        if not content:
            return ClassifyResult(success=False, error="empty content")

        if script_type == "bat":
            features = self._extract_bat_features(content)
        elif script_type == "sh":
            features = self._extract_sh_features(content)
        else:
            return ClassifyResult(
                success=False,
                error="unknown script_type: {!r}".format(script_type),
            )

        fv = FeatureVector(features=features, script_type=script_type)
        return ClassifyResult(success=True, feature_vector=fv)

    # ── BAT feature extraction ─────────────────────────────────

    def _extract_bat_features(self, content: str) -> frozenset:
        feats = set()

        # control flow
        if _RE_NESTED_FOR.search(content):
            feats.add(FEATURE_NESTED_FOR)
        elif _RE_FOR.search(content):
            feats.add(FEATURE_FOR)

        if _RE_GOTO.search(content) and _RE_LABEL.search(content):
            feats.add(FEATURE_GOTO)

        if _RE_IF.search(content):
            feats.add(FEATURE_IF)

        if _RE_CALL.search(content):
            feats.add(FEATURE_CALL)

        if _RE_SET_P.search(content):
            feats.add(FEATURE_SET_P)

        # variable / expansion
        if _RE_DELAYED.search(content):
            feats.add(FEATURE_DELAYED_EXPANSION)

        if _RE_DYNAMIC.search(content):
            feats.add(FEATURE_DYNAMIC_VAR)

        if _RE_PERCENT_VAR.search(content):
            feats.add(FEATURE_PERCENT_VAR)

        if _RE_INDIRECT_TOOL.search(content):
            feats.add(FEATURE_INDIRECT_TOOL)

        # environment
        if _RE_CHCP.search(content):
            feats.add(FEATURE_CHCP)

        if _RE_PAUSE.search(content):
            feats.add(FEATURE_PAUSE)

        if _RE_TIMEOUT.search(content):
            feats.add(FEATURE_TIMEOUT)

        if _RE_EXIT.search(content):
            feats.add(FEATURE_EXIT)

        # command structure
        if _RE_PREFIXED_FB.search(content):
            feats.add(FEATURE_PREFIXED_FASTBOOT)

        if _is_plain_bat(content):
            feats.add(FEATURE_PLAIN_COMMANDS)

        return frozenset(feats)

    # ── SH feature extraction ──────────────────────────────────

    def _extract_sh_features(self, content: str) -> frozenset:
        feats = set()

        if _RE_SH_FOR.search(content):
            feats.add(FEATURE_SH_FOR)

        if _RE_SH_WHILE.search(content):
            feats.add(FEATURE_SH_WHILE)

        if _RE_SH_IF.search(content):
            feats.add(FEATURE_SH_IF)

        if _RE_SH_CASE.search(content):
            feats.add(FEATURE_SH_CASE)

        if _RE_DOLLAR_SUB.search(content):
            feats.add(FEATURE_DOLLAR_SUB)

        if _RE_BACKTICK.search(content):
            feats.add(FEATURE_BACKTICK)

        if _RE_DOLLAR_BRACE.search(content):
            feats.add(FEATURE_DOLLAR_BRACE)

        if _RE_PIPE.search(content):
            feats.add(FEATURE_PIPE)

        if _RE_REDIRECT.search(content):
            feats.add(FEATURE_REDIRECT)

        if _RE_GREP.search(content):
            feats.add(FEATURE_GREP)

        if _RE_SHEBANG.search(content):
            feats.add(FEATURE_SHEBANG)

        if _RE_DIRNAME.search(content):
            feats.add(FEATURE_DIRNAME)

        if _RE_EXIT_CODE.search(content):
            feats.add(FEATURE_EXIT_CODE)

        if _RE_SH_VENDOR.search(content):
            feats.add(FEATURE_SH_VENDOR)

        if _RE_SH_COMMUNITY.search(content):
            feats.add(FEATURE_SH_COMMUNITY)

        if _is_plain_sh(content):
            feats.add(FEATURE_SH_PLAIN)

        return frozenset(feats)


__all__ = ["ScriptClassifier"]
