"""느슨한 읽기 — 띄어쓰기만 다른 문장을 같은 문장으로 본다 (기능 loose_read, 2026-11-11 운영자 '처음 보는 형태도 잘 읽게').

공고문 읽기 규칙(app/lh_terms·app/notice_pdf …)은 정규식이라 '입주자모집공고일'로 적은 규칙이 '입주자 모집공고일'을 못 읽는다
(2026-11-07 의정부 2026000553, 2026-11-10 제천장락1 2015122300020975 — 둘 다 띄어쓰기 하나 차이로 '공고문 확인'이 됨).

쓰는 법: 먼저 평소 규칙 그대로 읽고(엄격), 못 읽은 칸이 있을 때만 `with loose(모듈):` 안에서 한 번 더 읽어 **비어 있던 칸만** 채운다.
엄격하게 읽은 값은 절대 바꾸지 않는다 — 그래서 지금까지 맞게 읽던 공고의 값은 달라지지 않는다.

`loosen(패턴)` 이 하는 일 (패턴 쪽만 바꾼다, 원문 글은 그대로):
  - 한글이 3자 이상 붙어 있는 곳은 글자 사이에 빈칸이 있어도 맞게 한다 ('무주택세대구성원' ↔ '무주택 세대 구성원' ↔ '무 주 택 …')
  - 패턴에 적힌 빈칸 한 칸은 없어도 맞게 한다 ('소득 배제' ↔ '소득배제')
  글자 묶음([…])·뒤돌아보기((?<=…)·(?<!…))·횟수가 붙은 글자(가?·가{2})는 건드리지 않는다. 2자 한글('일반')은 너무 흔해 풀지 않는다.
"""
from __future__ import annotations

import re as _re
from contextlib import contextmanager
from functools import lru_cache

_QUANT = "?*+{"


def _is_han(c: str) -> bool:
    return "가" <= c <= "힣"


@lru_cache(maxsize=4096)
def loosen(pattern: str) -> str:
    toks: list[tuple[str, str]] = []   # ('han', 글자) · ('sp', ' ') · ('raw', 그대로)
    stack: list[bool] = []             # 괄호마다: 뒤돌아보기 안인가
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\":
            toks.append(("raw", pattern[i:i + 2]))
            i += 2
            continue
        if c == "[":                    # 글자 묶음은 통째로
            j = i + 1
            if j < n and pattern[j] == "^":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 2 if pattern[j] == "\\" else 1
            toks.append(("raw", pattern[i:j + 1]))
            i = j + 1
            continue
        if c == "(":
            lb = pattern.startswith("(?<=", i) or pattern.startswith("(?<!", i)
            stack.append(lb or (bool(stack) and stack[-1]))
            toks.append(("raw", c))
            i += 1
            continue
        if c == ")":
            if stack:
                stack.pop()
            toks.append(("raw", c))
            i += 1
            continue
        if c == "{":                    # 횟수 {a,b}
            j = pattern.find("}", i)
            if j > 0 and _re.fullmatch(r"\{\d*,?\d*\}", pattern[i:j + 1]):
                toks.append(("raw", pattern[i:j + 1]))
                i = j + 1
                continue
        quantified = i + 1 < n and pattern[i + 1] in _QUANT and not (pattern[i + 1] == "{" and not _re.match(r"\{\d*,?\d*\}", pattern[i + 1:]))
        inside_lb = bool(stack) and stack[-1]
        if _is_han(c) and not quantified and not inside_lb:
            toks.append(("han", c))
        elif c == " " and not quantified and not inside_lb:
            toks.append(("sp", c))
        else:
            toks.append(("raw", c))
        i += 1
    out: list[str] = []
    k = 0
    while k < len(toks):
        kind, s = toks[k]
        if kind == "han":
            j = k
            while j < len(toks) and toks[j][0] == "han":
                j += 1
            run = [t[1] for t in toks[k:j]]
            out.append(r"\s?".join(run) if len(run) >= 3 else "".join(run))
            k = j
            continue
        out.append(r"\s?" if kind == "sp" else s)
        k += 1
    return "".join(out)


class _LooseRe:
    """`re` 대신 끼우는 것 — 패턴을 loosen 해서 진짜 re 에 넘긴다. 풀어 쓴 패턴이 문법 오류면 원래 패턴 그대로."""

    def __getattr__(self, name):
        return getattr(_re, name)

    @staticmethod
    def _p(pattern, flags=0):
        if isinstance(pattern, _re.Pattern):
            src, flags = pattern.pattern, pattern.flags
        else:
            src = pattern
        if not isinstance(src, str) or flags & _re.VERBOSE:
            return pattern if isinstance(pattern, _re.Pattern) else _re.compile(pattern, flags)
        try:
            return _re.compile(loosen(src), flags)
        except _re.error:
            return pattern if isinstance(pattern, _re.Pattern) else _re.compile(pattern, flags)

    def compile(self, pattern, flags=0):
        return self._p(pattern, flags)

    def search(self, pattern, string, flags=0):
        return self._p(pattern, flags).search(string)

    def match(self, pattern, string, flags=0):
        return self._p(pattern, flags).match(string)

    def fullmatch(self, pattern, string, flags=0):
        return self._p(pattern, flags).fullmatch(string)

    def finditer(self, pattern, string, flags=0):
        return self._p(pattern, flags).finditer(string)

    def findall(self, pattern, string, flags=0):
        return self._p(pattern, flags).findall(string)

    def sub(self, pattern, repl, string, count=0, flags=0):
        return self._p(pattern, flags).sub(repl, string, count)

    def subn(self, pattern, repl, string, count=0, flags=0):
        return self._p(pattern, flags).subn(repl, string, count)

    def split(self, pattern, string, maxsplit=0, flags=0):
        return self._p(pattern, flags).split(string, maxsplit)


LOOSE_RE = _LooseRe()


@contextmanager
def loose(*modules):
    """이 안에서는 모듈의 `re` 와 미리 만들어 둔 패턴(모듈 변수)이 느슨한 것으로 바뀐다. 나올 때 반드시 되돌린다. (수집은 한 번에 한 공고씩 읽는다)"""
    saved = []
    try:
        for mod in modules:
            for name, val in list(vars(mod).items()):
                if val is _re:
                    saved.append((mod, name, val))
                    setattr(mod, name, LOOSE_RE)
                elif isinstance(val, _re.Pattern):
                    saved.append((mod, name, val))
                    setattr(mod, name, LOOSE_RE._p(val))
        yield
    finally:
        for mod, name, val in saved:
            setattr(mod, name, val)
