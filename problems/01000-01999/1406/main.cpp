// 에디터
// https://www.acmicpc.net/problem/1406

#include <cstdint>
#include <iostream>
#include <list>
#include <print>

void solution()
{
    using namespace std;

    list<char> edit_str;

    uint32_t m;
    cin >> m;

    for (uint32_t i = 0; i < m; ++i)
    {
        char cmd;
        cin >> cmd;

        switch (cmd)
        {
        case 'L': // 커서를 왼쪽으로 한 칸 옮김 (커서가 문장의 맨 앞이면 무시됨)
        {

        }
        case 'D': // 커서를 오른쪽으로 한 칸 옮김 (커서가 문장의 맨 뒤이면 무시됨)
        {

        }
        case 'B': // 커서 왼쪽에 있는 문자를 삭제함 (커서가 문장의 맨 앞이면 무시됨)
        {

        }
        case 'P': // "P $" $라는 문자를 커서 왼쪽에 추가함
        {

        }
        }
    }
}

int main()
{
    std::cin.tie(nullptr);
    std::ios::sync_with_stdio(false);

    solution();

    return 0;
}
