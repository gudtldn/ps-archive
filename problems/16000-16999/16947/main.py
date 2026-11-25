# 서울 지하철 2호선
# https://www.acmicpc.net/problem/16947

from typing import Callable

def solution(it_next: Callable[[], str]):
    ...

if __name__ == "__main__":
    solution(iter(open(0).read().splitlines()).__next__)
