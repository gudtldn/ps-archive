"""`solve new`가 만드는 언어별 시작 코드.

테스트는 tests/*.in·*.out과 `solve test`가 맡으므로, 템플릿에는 풀이 코드만 둡니다.
자리표시자는 `{{TITLE}}`과 `{{URL}}`이며 단순 치환합니다 (Rust 매크로의 `$`, `{}`와 충돌하지 않게).
"""

from solve.langs import Language

_PYTHON = """\
# {{TITLE}}
# {{URL}}

from collections.abc import Callable


def solution(it_next: Callable[[], str]) -> None: ...


if __name__ == "__main__":
    solution(iter(open(0).read().splitlines()).__next__)
"""

_RUST = """\
// {{TITLE}}
// {{URL}}

fn solution(stdin: &str) {
    let mut lines = stdin.lines();
    #[allow(unused)]
    let mut next = || lines.next().unwrap();

    // parse_line!(usize, i64) -> (usize, i64), parse_line!([i64]) -> Vec<i64>
    #[allow(unused_macros)]
    macro_rules! parse_line {
        ([$t:ty]) => {
            next().split_ascii_whitespace().map(|s| s.parse::<$t>().unwrap()).collect::<Vec<_>>()
        };
        ($($t:ty),+) => {
            {
                let mut it = next().split_ascii_whitespace();
                ($(it.next().unwrap().parse::<$t>().unwrap()),+)
            }
        };
    }

    todo!("solve here");
}

fn main() {
    use std::io::*;
    solution(&read_to_string(stdin()).unwrap());
    STDOUT.with(|refcell| std::io::Write::flush(&mut *refcell.borrow_mut()).unwrap());
}

thread_local! {
    static STDOUT: std::cell::RefCell<std::io::BufWriter<std::io::StdoutLock<'static>>> =
        std::cell::RefCell::new(std::io::BufWriter::with_capacity(1 << 17, std::io::stdout().lock()));
}

#[macro_export]
macro_rules! println {
    ($($t:tt)*) => {
        STDOUT.with(|refcell| {
            use std::io::*;
            writeln!(refcell.borrow_mut(), $($t)*).unwrap();
        })
    };
}

#[macro_export]
macro_rules! print {
    ($($t:tt)*) => {
        STDOUT.with(|refcell| {
            use std::io::*;
            write!(refcell.borrow_mut(), $($t)*).unwrap();
        })
    };
}
"""

_CPP = """\
// {{TITLE}}
// {{URL}}

#include <iostream>

void solution()
{
    using namespace std;

    // code here
}

int main()
{
    std::cin.tie(nullptr);
    std::ios::sync_with_stdio(false);

    solution();

    return 0;
}
"""

_KOTLIN = """\
// {{TITLE}}
// {{URL}}

fun main() {
    // code here
}
"""

_ASM = """\
; {{TITLE}}
; {{URL}}

section .data
    ; data here

section .bss
    ; bss here

section .text
    global main
    extern printf
    extern scanf

main:
    push rbp
    mov rbp, rsp

    ; code here

    pop rbp
    xor rax, rax
    ret
"""

_TEMPLATES = {"py": _PYTHON, "rs": _RUST, "cpp": _CPP, "kt": _KOTLIN, "asm": _ASM}


def render_template(lang: Language, title: str, url: str) -> str:
    return _TEMPLATES[lang.ext].replace("{{TITLE}}", title).replace("{{URL}}", url)
