"""
deletion_detector.py

Detects text that has been REMOVED from an ORIGINAL literary text when compared
to an EDITED (shortened) version of the same text, and returns the ORIGINAL
text with the genuinely deleted passages wrapped as:

    [removed text]X

Design goals (see accompanying README.md for full rationale):

  1. Comparison is done on WORD TOKENS, ignoring whitespace/line breaks/
     punctuation for the purpose of deciding what changed -- but the final
     output is built directly from the ORIGINAL text's characters, so all
     original punctuation, spacing and line breaks are preserved untouched.

  2. A plain difflib "replace" block is NOT automatically treated as a
     deletion. Each differing region ("gap") between two stable anchor
     matches is re-analyzed with a fuzzy word-alignment step so that a
     small wording change / OCR fix / accent correction (e.g.
     "τεθλιμμέμνος" -> "τεθλιμμένος") is recognized as a MODIFICATION
     and left unmarked, while the surrounding words that truly have no
     counterpart in EDITED are marked as deleted.

  3. Before finalizing a deletion span, the tool checks whether that same
     span of words appears elsewhere (anywhere) in EDITED. If it does, the
     text was MOVED, not deleted, and is left unmarked.

  4. Words that exist only in EDITED (insertions) are ignored entirely.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

# \w in Python's `re` module is Unicode-aware by default for `str` patterns,
# so it correctly matches Greek and polytonic Greek letters (Greek/Coptic
# block U+0370-U+03FF and Greek Extended block U+1F00-U+1FFF), Latin
# letters, digits, and underscores, all as a single contiguous token class.
# Because there's no separator between a leading digit and a following
# letter (e.g. "1ῃ"), \w+ naturally captures it as one token.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class Token:
    text: str      # the raw token text, exactly as it appears in the source
    start: int     # start character offset in the source string
    end: int       # end character offset (exclusive) in the source string


def tokenize(text: str) -> List[Token]:
    """Split `text` into word tokens, recording their character offsets."""
    return [Token(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def normalize_token(tok: str) -> str:
    """Normalize a token for equality comparisons (case-insensitive)."""
    return tok.casefold()


# ---------------------------------------------------------------------------
# Fuzzy alignment inside a "gap" (the region between two stable anchors)
# ---------------------------------------------------------------------------

def _token_similarity(a: str, b: str) -> float:
    """Character-level similarity ratio between two normalized tokens."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def fuzzy_align(orig_sub: List[str], edit_sub: List[str],
                sim_threshold: float = 0.6) -> set:
    """
    Align two short token lists allowing for near-matches (typo/accent
    fixes), not just exact equality.

    Returns the set of LOCAL indices into `orig_sub` that were matched to
    *some* token in `edit_sub` (order-preserving, i.e. a weighted longest
    common subsequence where "equality" is replaced by "similarity above
    threshold"). Unmatched indices are words with no real counterpart in
    EDITED at all -- deletion candidates.
    """
    n, m = len(orig_sub), len(edit_sub)
    if n == 0 or m == 0:
        return set()

    # dp[i][j] = best cumulative similarity score aligning orig_sub[:i]
    # with edit_sub[:j]. choice[i][j] records how we got there so we can
    # backtrack the alignment.
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    choice = [[""] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = dp[i - 1][j]
            best_choice = "skip_o"
            if dp[i][j - 1] > best:
                best = dp[i][j - 1]
                best_choice = "skip_e"
            sim = _token_similarity(orig_sub[i - 1], edit_sub[j - 1])
            if sim >= sim_threshold:
                cand = dp[i - 1][j - 1] + sim
                if cand > best:
                    best = cand
                    best_choice = "match"
            dp[i][j] = best
            choice[i][j] = best_choice

    matched: set = set()
    i, j = n, m
    while i > 0 and j > 0:
        c = choice[i][j]
        if c == "match":
            matched.add(i - 1)
            i -= 1
            j -= 1
        elif c == "skip_o":
            i -= 1
        else:
            j -= 1
    return matched


# ---------------------------------------------------------------------------
# Move detection
# ---------------------------------------------------------------------------

def _contains_contiguous_subsequence(haystack: List[str], needle: List[str]) -> bool:
    """True if `needle` appears as a contiguous run somewhere in `haystack`."""
    n, m = len(haystack), len(needle)
    if m == 0 or m > n:
        return False
    first = needle[0]
    for start in range(n - m + 1):
        if haystack[start] != first:
            continue
        if haystack[start:start + m] == needle:
            return True
    return False


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------

@dataclass
class DeletionSpan:
    start: int   # character offset in ORIGINAL
    end: int     # character offset in ORIGINAL (exclusive)
    text: str    # the actual deleted text, taken from ORIGINAL


class DeletionDetector:
    def __init__(self,
                 original: str,
                 edited: str,
                 sim_threshold: float = 0.6,
                 move_min_tokens: int = 2):
        """
        original, edited : the two text versions to compare.
        sim_threshold     : minimum character-level similarity (0-1) for two
                             words to be considered "the same word, slightly
                             modified" rather than unrelated.
        move_min_tokens   : a deleted span must contain at least this many
                             words before it is eligible to be reclassified
                             as "moved" (found verbatim elsewhere in EDITED).
                             This avoids suppressing genuine single-word
                             deletions just because that common word also
                             happens to occur elsewhere in the text.
        """
        self.original = original
        self.edited = edited
        self.sim_threshold = sim_threshold
        self.move_min_tokens = move_min_tokens

        self.orig_tokens = tokenize(original)
        self.edit_tokens = tokenize(edited)
        self.orig_norm = [normalize_token(t.text) for t in self.orig_tokens]
        self.edit_norm = [normalize_token(t.text) for t in self.edit_tokens]

    # -- step 1: top level anchors -----------------------------------------
    def _opcodes(self):
        sm = difflib.SequenceMatcher(None, self.orig_norm, self.edit_norm,
                                      autojunk=False)
        return sm.get_opcodes()

    # -- step 2: resolve each gap into deletion spans -----------------------
    def find_deletions(self) -> List[DeletionSpan]:
        spans: List[DeletionSpan] = []

        for tag, i1, i2, j1, j2 in self._opcodes():
            if tag == "equal":
                continue
            if tag == "insert":
                # Nothing on the ORIGINAL side; irrelevant to deletions.
                continue

            orig_sub = self.orig_norm[i1:i2]
            edit_sub = self.edit_norm[j1:j2]

            if tag == "delete":
                matched_local = set()
            else:  # 'replace'
                matched_local = fuzzy_align(orig_sub, edit_sub, self.sim_threshold)

            unmatched_local = [k for k in range(len(orig_sub)) if k not in matched_local]

            # group consecutive unmatched local indices into spans
            for group in _consecutive_groups(unmatched_local):
                global_start = i1 + group[0]
                global_end = i1 + group[-1]  # inclusive

                span_norm_tokens = self.orig_norm[global_start:global_end + 1]

                # Move check: does this exact run of words appear anywhere
                # (contiguously) in EDITED? If so, it was moved, not deleted.
                if len(span_norm_tokens) >= self.move_min_tokens and \
                        _contains_contiguous_subsequence(self.edit_norm, span_norm_tokens):
                    continue

                start_char = self.orig_tokens[global_start].start
                end_char = self.orig_tokens[global_end].end
                spans.append(DeletionSpan(
                    start=start_char,
                    end=end_char,
                    text=self.original[start_char:end_char],
                ))

        spans.sort(key=lambda s: s.start)
        return _merge_adjacent(spans)

    # -- step 3: render the ORIGINAL text with [deleted]X markers ----------
    def annotated_text(self) -> str:
        spans = self.find_deletions()
        out = []
        last = 0
        for sp in spans:
            out.append(self.original[last:sp.start])
            out.append("[")
            out.append(sp.text)
            out.append("]X")
            last = sp.end
        out.append(self.original[last:])
        return "".join(out)


def _consecutive_groups(indices: List[int]) -> List[List[int]]:
    if not indices:
        return []
    groups = [[indices[0]]]
    for idx in indices[1:]:
        if idx == groups[-1][-1] + 1:
            groups[-1].append(idx)
        else:
            groups.append([idx])
    return groups


def _merge_adjacent(spans: List[DeletionSpan]) -> List[DeletionSpan]:
    """Merge spans that end exactly where the next one begins (or are
    separated only by whitespace with nothing else in between), so the
    output doesn't show back-to-back ']X[' brackets."""
    if not spans:
        return spans
    merged = [spans[0]]
    for sp in spans[1:]:
        prev = merged[-1]
        between = "" if sp.start <= prev.end else None
        if sp.start == prev.end:
            merged[-1] = DeletionSpan(prev.start, sp.end, prev.text + sp.text)
        else:
            merged.append(sp)
    return merged


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def find_removed_text(original: str, edited: str,
                       sim_threshold: float = 0.6,
                       move_min_tokens: int = 2) -> str:
    """Return ORIGINAL with genuinely deleted passages wrapped as [..]X."""
    detector = DeletionDetector(original, edited, sim_threshold, move_min_tokens)
    return detector.annotated_text()


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Detect deleted passages between an ORIGINAL and EDITED text."
    )

    parser.add_argument(
        "--original",
        default=r"C:\Users\AthinaKatsoula\Downloads\files\dracula\original.txt",
        help="Path to the original text file."
    )

    parser.add_argument(
        "--edited",
        default=r"C:\Users\AthinaKatsoula\Downloads\files\dracula\edited.txt",
        help="Path to the edited text file."
    )

    parser.add_argument(
        "-o",
        "--output",
        default=r"C:\Users\AthinaKatsoula\Downloads\files\dracula\result.txt",
        help="Path to the output file."
    )

    parser.add_argument(
        "--sim-threshold",
        type=float,
        default=0.6,
        help="Similarity threshold (0-1) for word modification detection (default 0.6)"
    )

    parser.add_argument(
        "--move-min-tokens",
        type=int,
        default=2,
        help="Minimum span length (in words) eligible to be reclassified as "
             "'moved' instead of 'deleted' (default 2)"
    )

    args = parser.parse_args()

    with open(args.original, "r", encoding="utf-8") as f:
        original_text = f.read()

    with open(args.edited, "r", encoding="utf-8") as f:
        edited_text = f.read()

    result = find_removed_text(
        original_text,
        edited_text,
        args.sim_threshold,
        args.move_min_tokens
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        sys.stdout.write(result)
