// 에디터
// https://www.acmicpc.net/problem/1406

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
