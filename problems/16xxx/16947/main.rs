// 서울 지하철 2호선
// https://www.acmicpc.net/problem/16947

fn solution(stdin: &str) {
    let mut tokens = stdin.split('\n');
    let mut next = || tokens.next().unwrap();

    #[allow(unused_macros)]
    macro_rules! parse_line {
        ($($to_type:ty),*) => {
            {
                let mut iter = next().split_whitespace();
                ($(iter.next().unwrap().parse::<$to_type>().unwrap()),*)
            }
        };
    }

    todo!("solve here");
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
        assert_eq!(
            capture_output(|| solution("4\n1 3\n4 3\n4 2\n1 2")),
            "0 0 0 0"
        );
    }

    #[test]
    fn test_solution2() {
        assert_eq!(
            capture_output(|| solution("6\n1 2\n3 4\n6 4\n2 3\n1 3\n3 5")),
            "0 0 0 1 1 2"
        );
    }

    #[test]
    fn test_solution3() {
        assert_eq!(
            capture_output(|| solution("51\n1 2\n2 3\n3 4\n4 5\n5 6\n6 7\n7 8\n8 9\n9 10\n10 11\n11 12\n12 13\n13 14\n14 15\n15 16\n16 17\n17 18\n18 19\n19 20\n20 21\n21 22\n22 23\n23 24\n24 25\n25 26\n26 27\n27 28\n28 29\n29 30\n30 31\n31 32\n32 33\n33 34\n34 35\n35 36\n36 37\n37 38\n38 39\n39 40\n40 41\n41 42\n42 43\n43 1\n11 44\n44 45\n45 46\n46 47\n34 48\n48 49\n49 50\n50 51")),
            "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 2 3 4 1 2 3 4"
        );
    }

    #[test]
    fn test_solution4() {
        assert_eq!(
            capture_output(|| solution("38\n1 2\n2 3\n3 4\n4 5\n5 6\n6 1\n1 7\n7 8\n8 9\n9 10\n10 11\n11 12\n12 13\n13 14\n14 15\n15 16\n16 17\n17 18\n18 19\n19 20\n20 21\n21 22\n22 23\n23 24\n24 25\n25 26\n26 27\n27 28\n28 29\n29 30\n30 31\n31 32\n32 33\n33 34\n34 35\n35 36\n36 37\n37 38")),
            "0 0 0 0 0 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32"
        );
    }

    #[test]
    fn test_solution5() {
        assert_eq!(
            capture_output(|| solution("12\n1 3\n3 4\n4 5\n5 6\n6 7\n7 8\n8 4\n2 3\n7 9\n9 12\n7 10\n10 11")),
            "2 2 1 0 0 0 0 0 1 1 2 2"
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
        });
    };
}

#[macro_export]
macro_rules! print {
    ($($t:tt)*) => {
        STDOUT.with(|refcell| {
            use std::io::*;
            write!(refcell.borrow_mut(), $($t)*).unwrap();
        });
    };
}
