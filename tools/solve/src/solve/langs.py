"""언어별 파일 확장자와 빌드·실행 명령.

명령 안의 자리표시자:
    {src}  풀이 파일 경로 (main.<ext>)
    {out}  빌드 결과물 디렉터리 (.build/<문제 키>/)
    {bin}  루트 Cargo.toml에 등록된 Rust 바이너리 이름
    {root} 저장소 루트
    {exe}  실행 파일 확장자 (Windows에서는 .exe)
"""

import os
import sys
from dataclasses import dataclass

EXE_SUFFIX = ".exe" if os.name == "nt" else ""


@dataclass(frozen=True)
class Language:
    name: str
    aliases: tuple[str, ...]
    ext: str
    build: tuple[str, ...] | None
    run: tuple[str, ...] | None
    unsupported_reason: str = ""

    @property
    def source_name(self) -> str:
        return f"main.{self.ext}"

    def command(self, template: tuple[str, ...], **values: str) -> list[str]:
        values = {"exe": EXE_SUFFIX, **values}
        return [part.format(**values) for part in template]


LANGUAGES: tuple[Language, ...] = (
    Language("python", ("py",), "py", None, (sys.executable, "{src}")),
    Language(
        "rust",
        ("rs",),
        "rs",
        ("cargo", "build", "--quiet", "--release", "--manifest-path", "{root}/Cargo.toml", "--bin", "{bin}"),
        ("{root}/target/release/{bin}{exe}",),
    ),
    Language(
        "cpp",
        ("c++", "cc"),
        "cpp",
        # BOJ와 같은 -static·매크로를 씁니다. -lstdc++exp는 GCC 14+의 std::print/println 구현입니다.
        (
            "g++",
            "-std=c++23",
            "-O2",
            "-static",
            "-DONLINE_JUDGE",
            "-DBOJ",
            "-o",
            "{out}/main{exe}",
            "{src}",
            "-lstdc++exp",
        ),
        ("{out}/main{exe}",),
    ),
    Language(
        "kotlin",
        ("kt",),
        "kt",
        ("kotlinc", "{src}", "-include-runtime", "-d", "{out}/main.jar"),
        ("java", "-jar", "{out}/main.jar"),
    ),
    Language(
        "asm",
        ("x86_64_assembly", "asm64"),
        "asm",
        None,
        None,
        unsupported_reason="BOJ 어셈블리는 Linux ABI 기준이라 Windows에서 로컬 실행을 지원하지 않습니다",
    ),
)

_BY_KEY = {key: lang for lang in LANGUAGES for key in (lang.name, lang.ext, *lang.aliases)}


class UnknownLanguageError(ValueError):
    pass


def get_language(key: str) -> Language:
    try:
        return _BY_KEY[key.strip().lower()]
    except KeyError:
        names = ", ".join(lang.ext for lang in LANGUAGES)
        raise UnknownLanguageError(f"알 수 없는 언어: {key!r} (사용 가능: {names})") from None


def parse_languages(spec: str) -> tuple[Language, ...]:
    """`py,rs` 같은 쉼표 구분 목록을 순서와 중복 제거를 지켜 변환합니다."""
    seen: dict[str, Language] = {}
    for part in spec.split(","):
        if part.strip():
            lang = get_language(part)
            seen.setdefault(lang.name, lang)
    return tuple(seen.values())


def language_for_file(filename: str) -> Language | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return next((lang for lang in LANGUAGES if lang.ext == ext), None)
