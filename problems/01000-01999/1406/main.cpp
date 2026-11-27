// 에디터
// https://www.acmicpc.net/problem/1406

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <string>
#include <list>
#include <print>

using i8 = std::int8_t;
using u8 = std::uint8_t;
using i16 = std::int16_t;
using u16 = std::uint16_t;
using i32 = std::int32_t;
using u32 = std::uint32_t;
using i64 = std::int64_t;
using u64 = std::uint64_t;

using f32 = float;
using f64 = double;

using isize = std::ptrdiff_t;
using usize = std::size_t;

void solution()
{
    using namespace std;

    string line;
    getline (cin, line);

    list<char> edit_str{ line.begin(), line.end() };

    u32 m;
    cin >> m;

    list<char>::iterator cursor = edit_str.end();
    for (u32 i = 0; i < m; ++i)
    {
        char cmd;
        cin >> cmd;

        switch (cmd)
        {
        case 'L': // 커서를 왼쪽으로 한 칸 옮김 (커서가 문장의 맨 앞이면 무시됨)
        {
            if (cursor != edit_str.begin())
            {
                --cursor;
            }
            break;
        }
        case 'D': // 커서를 오른쪽으로 한 칸 옮김 (커서가 문장의 맨 뒤이면 무시됨)
        {
            if (cursor != edit_str.end())
            {
                ++cursor;
            }
            break;
        }
        case 'B': // 커서 왼쪽에 있는 문자를 삭제함 (커서가 문장의 맨 앞이면 무시됨)
        {
            if (cursor != edit_str.begin())
            {
                cursor = edit_str.erase(--cursor);
            }
            break;
        }
        case 'P': // "P $" $라는 문자를 커서 왼쪽에 추가함
        {
            char c;
            cin >> c;
            edit_str.insert(cursor, c);
            break;
        }
        }
    }

    for (char c : edit_str)
    {
        std::print("{}", c);
    }
}

int main()
{
    std::cin.tie(nullptr);
    std::ios::sync_with_stdio(false);

    solution();

    return 0;
}
