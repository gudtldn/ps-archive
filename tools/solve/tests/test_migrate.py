import subprocess
from pathlib import Path

from solve.api import JudgeId, Problem
from solve.layout import STATUS_SOLVED, STATUS_SOLVING, meta_from_problem, read_meta, read_tests
from solve.migrate import extract_cases, migrate
from solve.scrape import ProblemPage, Sample

PY_RUN_SOLUTION = """
class Test(TestCase):
    @staticmethod
    def run_solution(input_str: str) -> str:
        with StringIO(input_str) as capture_input:
            return ""

    def test_solution1(self) -> None:
        self.assertEqual(
            Test.run_solution("1 2"),
            "3"
        )

    def test_solution2(self) -> None:
        self.assertEqual(
            Test.run_solution("4\\n5 6"),
            "11"
        )

if __name__ == "__main__":
    main()
"""

PY_STRINGIO = """
class Test(TestCase):
    def test_solution1(self) -> None:
        buffer = StringIO("1\\n99 999999")
        self.assertEqual(solution(buffer), "9")
"""

RUST_MAIN = """
fn solution(stdin: &str) { todo!("solve here"); }

#[cfg(test)]
mod tests {
    use super::*;
    fn capture_output(f: impl FnOnce()) -> String { String::new() }

    #[test]
    fn test_solution1() {
        assert_eq!(
            capture_output(|| solution("1 2\\n")),
            "3"
        );
    }
}

fn main() { println!("{}", "x"); }
"""


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def boj_meta(boj_id: int):
    problem = Problem(boj_id, "", f"P{boj_id}", 3, (), (JudgeId("boj", str(boj_id), ""),))
    return meta_from_problem(problem, {"boj": "https://www.acmicpc.net/problem/{problemId}"})


class TestExtractCases:
    def test_run_solution_style(self) -> None:
        assert extract_cases(PY_RUN_SOLUTION, "py") == ([("1 2", "3"), ("4\n5 6", "11")], True)

    def test_stringio_style(self) -> None:
        assert extract_cases(PY_STRINGIO, "py") == ([("1\n99 999999", "9")], True)

    def test_rust_capture_style_ignores_code_outside_tests(self) -> None:
        assert extract_cases(RUST_MAIN, "rs") == ([("1 2\n", "3")], True)

    def test_unrecognized_block_marks_incomplete(self) -> None:
        text = PY_STRINGIO + '\n    def test_x(self):\n        self.assertTrue(check("a", "b", "c"))\n'
        cases, complete = extract_cases(text, "py")
        assert cases == [("1\n99 999999", "9")]
        assert complete is False


class TestMigrate:
    def test_moves_files_extracts_tests_and_cleans_up(self, tmp_path: Path) -> None:
        git(tmp_path, "init", "-q")
        write(tmp_path / "1000/python/boj_1000.py", "print(3)\n")
        write(tmp_path / "1000/python/boj_1000_test.py", PY_RUN_SOLUTION)
        write(tmp_path / "1000/rust/boj_1000/src/main.rs", RUST_MAIN)
        write(tmp_path / "1000/rust/boj_1000/Cargo.toml", '[package]\nname = "boj_1000"\nedition = "2021"\n')
        write(tmp_path / "1000/Cargo.toml", "[workspace]\n")
        write(tmp_path / "1000/cpp/boj_1000_test.cpp", "int main(){}\n")
        git(tmp_path, "add", ".")
        git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init")
        write(tmp_path / "1000/rust/boj_1000/target/debug/junk", "x")
        write(tmp_path / "2749/python/2749.py", "print(1)\n")  # 미추적 = 푸는 중

        page = ProblemPage(2.0, 128, (Sample("1 2", "3"),))
        logs: list[str] = []
        migrate(tmp_path, {1000: boj_meta(1000), 2749: boj_meta(2749)}, lambda _: page, logs.append)

        solved = tmp_path / "problems/01000-01999/1000"
        assert sorted(p.name for p in solved.iterdir()) == [
            "boj_1000_test.cpp",
            "main.py",
            "main.rs",
            "meta.json",
            "tests",
        ]
        assert [(i, o) for _, i, o in read_tests(solved)] == [("1 2\n", "3\n"), ("4\n5 6\n", "11\n")]
        assert read_meta(solved).status == STATUS_SOLVED
        assert read_meta(solved).time_limit_sec == 2.0
        assert read_meta(tmp_path / "problems/02000-02999/2749").status == STATUS_SOLVING
        assert not (tmp_path / "1000").exists()
        assert not (tmp_path / "2749").exists()
        manifest = (tmp_path / "Cargo.toml").read_text(encoding="utf-8")
        assert 'path = "problems/01000-01999/1000/main.rs"\nedition = "2021"' in manifest
        assert read_meta(solved).extra == {"rustEdition": "2021"}

        status = subprocess.run(
            ["git", "-C", str(tmp_path), "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout
        assert "R  1000/python/boj_1000.py -> problems/01000-01999/1000/main.py" in status
        assert "D  1000/python/boj_1000_test.py" in status

    def test_skips_folder_without_sources(self, tmp_path: Path) -> None:
        git(tmp_path, "init", "-q")
        write(tmp_path / "15595/cpp/output/boj_15595.exe", "MZ")
        plans = migrate(tmp_path, {15595: boj_meta(15595)}, lambda _: ProblemPage(1, 1, ()), lambda _: None)
        assert plans == []
        assert (tmp_path / "15595/cpp/output/boj_15595.exe").exists()
        assert not (tmp_path / "problems/15000-15999/15595").exists()

    def test_dry_run_changes_nothing(self, tmp_path: Path) -> None:
        git(tmp_path, "init", "-q")
        write(tmp_path / "1000/python/boj_1000.py", "print(3)\n")
        migrate(tmp_path, {1000: boj_meta(1000)}, lambda _: ProblemPage(1, 1, ()), lambda _: None, dry_run=True)
        assert (tmp_path / "1000/python/boj_1000.py").exists()
        assert not (tmp_path / "problems").exists()
