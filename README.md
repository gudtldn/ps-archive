# PS Archive

[BOJ 프로필](https://www.acmicpc.net/user/gudtldn)

[![Solved.ac profile](http://mazassumnida.wtf/api/v2/generate_badge?boj=gudtldn)](https://solved.ac/gudtldn)
![mazandi profile](http://mazandi.herokuapp.com/api?handle=gudtldn&theme=cold)

## 사용법

`.env`에 `SOLVEDAC_CLIENT_ID`, `SOLVEDAC_CLIENT_SECRET`을 넣고 `uv run --project tools/solve solve <명령>`으로 실행합니다.
(`uv tool install -e tools/solve`로 설치하면 `solve`만으로 실행)

```sh
solve new 1000            # 문제 폴더·예제·시작 코드 만들기 (언어는 목록에서 고르고, 에디터로 바로 엶. 끄려면 -E)
solve new 1000 -l py,rs   # 언어를 바로 지정 (python/py, rust/rs, cpp/c++, kotlin/kt, asm)
solve test 1000           # 폴더에 있는 모든 언어로 tests/ 실행
solve test 1000 -l rs -v  # 한 언어만, 틀리면 기대·실제 출력 표시
solve test --all          # 전체 문제 테스트, 실패만 표시
solve done 1000           # 상태를 solved로
solve sync                # solved.ac에서 티어·태그 갱신 + README 다시 만들기
solve sync --offline      # API 없이 README만 다시 만들기
solve resolve 28955       # BOJ 번호가 solved.ac에서 몇 번인지 확인
```

- 번호는 solved.ac 번호(`19917b`)와 BOJ 번호 모두 됩니다.
- 반례는 `tests/`에 `N.in`, `N.out`을 추가하면 같이 실행됩니다.
- 문제 폴더: `problems/01000-01999/1000/` (`meta.json`, `tests/`, `main.*`)

<!-- solve:start -->
<!-- 이 구역은 `solve sync`가 생성합니다. 직접 고치면 덮어써집니다. -->

## 통계

전체 132문제 · 해결 128 · 푸는 중 4

언어: py 75 · rs 62 · cpp 40 · asm 3 · kt 1

| 티어 | 문제 수 |
| --- | ---: |
| Bronze | 62 |
| Silver | 43 |
| Gold | 25 |
| Platinum | 2 |

## 푸는 중인 문제

| 번호 | 제목 | 티어 | 태그 | 풀이 | 상태 |
| ---: | --- | :---: | --- | --- | :---: |
| [1026](https://www.acmicpc.net/problem/1026) | [보물](problems/01000-01999/1026) | <img src="https://static.solved.ac/tier_small/7.svg" alt="Silver IV" height="16"> | 그리디, 수학, 정렬 | [rs](problems/01000-01999/1026/main.rs) | 🚧 |
| [1406](https://www.acmicpc.net/problem/1406) | [에디터](problems/01000-01999/1406) | <img src="https://static.solved.ac/tier_small/9.svg" alt="Silver II" height="16"> | 자료 구조, 연결 리스트, 스택 | [cpp](problems/01000-01999/1406/main.cpp) | 🚧 |
| [2749](https://www.acmicpc.net/problem/2749) | [피보나치 수 3](problems/02000-02999/2749) | <img src="https://static.solved.ac/tier_small/14.svg" alt="Gold II" height="16"> | 분할 정복을 이용한 거듭제곱, 수학, 피사노 주기 | [rs](problems/02000-02999/2749/main.rs) | 🚧 |
| [16947](https://www.acmicpc.net/problem/16947) | [서울 지하철 2호선](problems/16000-16999/16947) | <img src="https://static.solved.ac/tier_small/13.svg" alt="Gold III" height="16"> | 너비 우선 탐색, 깊이 우선 탐색, 그래프, 그래프 탐색 | [py](problems/16000-16999/16947/main.py) [rs](problems/16000-16999/16947/main.rs) | 🚧 |

[전체 문제 목록](problems/)
<!-- solve:end -->
