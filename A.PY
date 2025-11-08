import sys
import bisect

def main() -> None:
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[:2]
    ptr = 2

    left = []
    right = []
    for _ in range(n):
        a = data[ptr]
        b = data[ptr + 1]
        ptr += 2
        if a <= b:
            left.append(a)
            right.append(b)
        else:
            left.append(b)
            right.append(a)

    points = data[ptr : ptr + m]

    left.sort()
    right.sort()

    out_lines = []
    for x in points:
        started = bisect.bisect_right(left, x)
        finished = bisect.bisect_left(right, x)
        out_lines.append(str(started - finished))

    sys.stdout.write(" ".join(out_lines))

if __name__ == "__main__":
    main()