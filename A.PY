n, target = map(int, input().split())
arr = list(map(int, input().split()))

INF = 10 ** 9
best = [INF] * (target + 1)
best[0] = 0
ans = INF

for value in arr:
    new = [INF] * (target + 1)
    new[0] = 0
    for s in range(1, target + 1):
        prev = best[s]
        if prev < INF:
            length = prev + 1
            if length < new[s]:
                new[s] = length
        if s >= value:
            prev = best[s - value]
            if prev < INF:
                length = prev + 1
                if length < new[s]:
                    new[s] = length
    if value <= target and new[value] > 1:
        new[value] = 1
    best = new
    if best[target] < ans:
        ans = best[target]

print(ans if ans < INF else -1)