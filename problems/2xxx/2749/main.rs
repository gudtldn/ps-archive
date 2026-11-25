// 피보나치 수 3
// https://www.acmicpc.net/problem/2749

// TODO: pisano period와 관련된 문제이므로
// https://www.acmicpc.net/problem/9471 먼저 풀기

use std::ops::{Add, Rem};

struct BigInt(Vec<u8>);

impl BigInt {
    fn zero() -> Self {
        BigInt(vec![0])
    }

    fn one() -> Self {
        BigInt(vec![1])
    }
}

impl Add<&BigInt> for &BigInt {
    type Output = BigInt;

    fn add(self, rhs: &BigInt) -> Self::Output {
        let mut result = Vec::new();
        let mut carry = 0;
        let max_len = self.0.len().max(rhs.0.len());

        for i in 0..max_len {
            let digit_a = *self.0.get(i).unwrap_or(&0);
            let digit_b = *rhs.0.get(i).unwrap_or(&0);

            let sum = digit_a + digit_b + carry;
            result.push(sum % 10);
            carry = sum / 10;
        }

        if carry > 0 {
            result.push(carry);
        }

        BigInt(result)
    }
}

impl Rem<u128> for BigInt {
    type Output = u128;

    fn rem(self, rhs: u128) -> Self::Output {
        let mut remainder = 0_u128;

        for &digit in self.0.iter().rev() {
            remainder = (remainder * 10 + digit as u128) % rhs;
        }

        remainder
    }
}

impl std::fmt::Display for BigInt {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        for &digit in self.0.iter().rev() {
            write!(f, "{}", digit)?;
        }
        Ok(())
    }
}

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

    let n = parse_line!(u128);

    let mut a = BigInt::zero();
    let mut b = BigInt::one();

    for _ in 0..n {
        let temp = &a + &b;
        a = b;
        b = temp;
    }

    println!("{}", a % 1_000_000);
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
            capture_output(|| solution("1000")),
            "228875"
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
