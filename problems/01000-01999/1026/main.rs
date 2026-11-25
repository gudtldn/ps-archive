// 보물
// https://www.acmicpc.net/problem/1026

fn solution(stdin: &str) {
    let mut lines = stdin.lines();
    let mut next = || lines.next().unwrap();

    #[allow(unused_macros)]
    macro_rules! parse_line {
        ($($to_type:ty),*) => {
            {
                let mut iter = next().split_whitespace();
                ($(iter.next().unwrap().parse::<$to_type>().unwrap()),*)
            }
        };
    }

    next();
    let mut a = next()
        .split_ascii_whitespace()
        .map(|s| s.parse::<i32>().unwrap())
        .collect::<Vec<_>>();
    a.sort_unstable_by(|x, y| y.cmp(x));

    let mut b = next()
        .split_ascii_whitespace()
        .map(|s| s.parse::<i32>().unwrap())
        .collect::<Vec<_>>();
    b.sort_unstable();

    let ret: i32 = a.into_iter().zip(b).map(|(x, y)| x * y).sum();
    println!("{}", ret);
}

#[cfg(test)]
mod tests {
    use super::*;
    fn capture_output(f: impl FnOnce()) -> String {
        STDOUT.with(|stdout| {
            stdout.borrow_mut().clear();
        });
        f();
        STDOUT.with(|stdout| {
            String::from_utf8(stdout.borrow().to_vec())
                .unwrap()
                .trim_end()
                .to_string()
        })
    }

    #[test]
    fn test_solution1() {
        assert_eq!(capture_output(|| solution("5\n1 1 1 6 0\n2 7 8 3 1")), "18");
    }

    #[test]
    fn test_solution2() {
        assert_eq!(capture_output(|| solution("3\n1 1 3\n10 30 20")), "80");
    }

    #[test]
    fn test_solution3() {
        assert_eq!(
            capture_output(|| solution("9\n5 15 100 31 39 0 0 3 26\n11 12 13 2 3 4 5 9 1")),
            "528"
        );
    }
}

fn main() {
    use std::io::*;
    solution(&read_to_string(stdin()).unwrap());
    STDOUT.with(|refcell| std::io::Write::flush(&mut *refcell.borrow_mut()).unwrap());
}

thread_local! {
    #[cfg(test)]
    static STDOUT: std::cell::RefCell<Vec<u8>> = std::cell::RefCell::new(Vec::new());

    #[cfg(not(test))]
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
