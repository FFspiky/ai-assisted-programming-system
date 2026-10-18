"""Build 60 authored teaching problems and private reference solutions deterministically.

Expected answers use small independent oracles; optimized reference programs are
verified separately. No model calls or external problem statements are used.
"""

import html
import itertools as it
import json
import math
from collections import Counter, deque
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBLEMS, REFERENCES = [], {}
CATEGORY, DIFFICULTIES, NUMBER = "", [], 0


def group(category, difficulties):
    global CATEGORY, DIFFICULTIES, NUMBER
    CATEGORY, DIFFICULTIES, NUMBER = category, difficulties.split(), 0


def nums(s):
    return list(map(int, s.split()))


def arr(s):
    return nums(s)[1:]


def pack(a):
    return str(len(a)) + "\n" + " ".join(map(str, a)) + "\n"


def text(value):
    if isinstance(value, (list, tuple)):
        return " ".join(map(str, value)) or "EMPTY"
    return str(value)


def add(title, statement, input_format, output_format, limits, inputs, oracle, code, tags):
    global NUMBER
    NUMBER += 1
    # Keep worst-case required output within the executor's 20 KB output budget.
    if title in {"排序去重", "右侧首个更大值的位置", "等待升温", "无向图的度数"}:
        limits = limits.replace("100000，", "1000，").replace("10000，", "1000，")
    elif title == "区间和查询":
        limits = limits.replace("n,q ≤ 10000", "n ≤ 10000，1 ≤ q ≤ 1000")
    elif title == "合并有序数组":
        limits = limits.replace("n,m ≤ 10000", "n,m ≤ 1000，n+m ≤ 1000")
    elif title == "连续字符压缩":
        limits = "长度1至1000。"
    elif title == "队列操作日志":
        limits = limits.replace("q ≤ 10000", "q ≤ 1000")
    pid = f"CL-{CATEGORY.upper()}-{NUMBER:02d}"
    assert len(inputs) == len(set(inputs)) == 6, title
    cases = [{"input": s, "output": text(oracle(s)), "public": i < 2} for i, s in enumerate(inputs)]
    esc = html.escape
    description = f"<p>{esc(statement)}</p><h3>输入格式</h3><p>{esc(input_format)}</p><h3>输出格式</h3><p>{esc(output_format)}</p><h3>数据范围</h3><p>{esc(limits)}</p>"
    for i, case in enumerate(cases[:2], 1):
        description += f"<h3>示例 {i}</h3><pre>输入：\n{esc(case['input'].rstrip())}\n输出：\n{esc(case['output'])}</pre>"
    PROBLEMS.append(
        dict(
            id=pid,
            title=title,
            description=description,
            category=CATEGORY,
            tags=tags.split(),
            difficulty=DIFFICULTIES[NUMBER - 1],
            judge_mode="text",
            source="智练 CodeLab 自编教学题；采用经典算法知识，题面与用例由项目编写",
            cases=cases,
        )
    )
    REFERENCES[pid] = code.strip() + "\n"


def build():
    group("basics", "简单 简单 简单 简单 简单 简单")
    add(
        "秒数换算",
        "将一段持续时间换算为小时、分钟和秒。小时数可以超过24。",
        "一个非负整数 t。",
        "依次输出小时、分钟、秒，用空格分隔。",
        "0 ≤ t ≤ 10^9。",
        ["3661\n", "59\n", "0\n", "3600\n", "86400\n", "1000000000\n"],
        lambda s: (int(s) // 3600, int(s) // 60 % 60, int(s) % 60),
        "t=int(input()); print(t//3600,t//60%60,t%60)",
        "整除 取余",
    )
    add(
        "数位之和",
        "计算整数绝对值的所有十进制数位之和。",
        "一个整数 n。",
        "输出数位之和。",
        "-10^18 ≤ n ≤ 10^18。",
        ["203\n", "-91\n", "0\n", "1000000000000000000\n", "999999999999999999\n", "7\n"],
        lambda s: sum(map(int, str(abs(int(s))))),
        "n=abs(int(input())); total=0\nwhile n: total+=n%10; n//=10\nprint(total)",
        "数位 取余",
    )
    add(
        "平均分取整",
        "三次测评的权重分别为2、3、5，计算加权平均分并向下取整。",
        "一行三个整数 a b c。",
        "输出一个整数分数。",
        "0 ≤ a,b,c ≤ 100。",
        ["80 90 100\n", "0 0 0\n", "100 100 100\n", "1 0 0\n", "0 1 1\n", "99 1 50\n"],
        lambda s: sum(x * w for x, w in zip(nums(s), [2, 3, 5], strict=False)) // 10,
        "a,b,c=map(int,input().split());print((a*2+b*3+c*5)//10)",
        "算术表达式 整除",
    )
    add(
        "矩形围栏",
        "已知矩形的长和宽，计算周长与面积。",
        "一行两个正整数 a b。",
        "输出周长和面积，以空格分隔。",
        "1 ≤ a,b ≤ 10^9，使用可容纳结果的整数类型。",
        ["3 4\n", "1 1\n", "1000000000 1000000000\n", "2 9\n", "17 11\n", "1 1000000000\n"],
        lambda s: (2 * sum(nums(s)), math.prod(nums(s))),
        "a,b=map(int,input().split());print(2*(a+b),a*b)",
        "整数运算 数据范围",
    )
    add(
        "公约数与公倍数",
        "求两个正整数的最大公约数和最小公倍数。",
        "一行两个正整数 a b。",
        "输出最大公约数、最小公倍数。",
        "1 ≤ a,b ≤ 10^9。",
        ["12 18\n", "7 13\n", "1 1\n", "1000000000 1000000000\n", "24 8\n", "35 49\n"],
        lambda s: (math.gcd(*nums(s)), math.lcm(*nums(s))),
        "a,b=map(int,input().split());x,y=a,b\nwhile y:x,y=y,x%y\nprint(x,a//x*b)",
        "欧几里得算法 整数运算",
    )
    add(
        "分数加法",
        "将两个分数相加，结果约分为最简分数；分母始终为正，零写为0/1。",
        "一行四个整数 a b c d，表示 a/b 和 c/d。",
        "输出分子和分母，以空格分隔。",
        "-10^6 ≤ a,c ≤ 10^6，1 ≤ b,d ≤ 10^6。",
        [
            "1 2 1 3\n",
            "-1 2 1 2\n",
            "0 7 0 9\n",
            "-3 4 -1 4\n",
            "5 6 7 6\n",
            "1000000 1 1 1000000\n",
        ],
        lambda s: (lambda f: (f.numerator, f.denominator))(
            Fraction(*nums(s)[:2]) + Fraction(*nums(s)[2:])
        ),
        "from math import gcd\na,b,c,d=map(int,input().split());p=a*d+c*b;q=b*d;g=gcd(abs(p),q);print(p//g,q//g)",
        "分数 约分",
    )

    group("control", "简单 简单 简单 简单 中等 中等")
    add(
        "区间奇数计数",
        "统计闭区间内奇数的数量。",
        "一行两个整数 l r。",
        "输出数量。",
        "0 ≤ l ≤ r ≤ 10^9。",
        ["1 9\n", "2 2\n", "0 0\n", "0 1000000000\n", "7 7\n", "10 20\n"],
        lambda s: (nums(s)[1] + 1) // 2 - nums(s)[0] // 2,
        "l,r=map(int,input().split());print((r+1)//2-l//2)",
        "分支 边界条件",
    )
    add(
        "闰年判断",
        "按公历规则判断年份是否为闰年。",
        "一个年份 y。",
        "闰年输出 YES，否则输出 NO。",
        "1 ≤ y ≤ 9999。",
        ["2000\n", "1900\n", "2024\n", "2023\n", "1\n", "2400\n"],
        lambda s: "YES" if int(s) % 400 == 0 or int(s) % 4 == 0 and int(s) % 100 != 0 else "NO",
        'y=int(input());print("YES" if y%400==0 or (y%4==0 and y%100!=0) else "NO")',
        "条件判断 逻辑运算",
    )
    add(
        "整数因子计数",
        "统计正整数有多少个正因子。",
        "一个正整数 n。",
        "输出因子数量。",
        "1 ≤ n ≤ 10^6。",
        ["12\n", "1\n", "49\n", "97\n", "1000000\n", "36\n"],
        lambda s: sum(int(s) % d == 0 for d in range(1, int(s) + 1)),
        "from math import isqrt\nn=int(input());ans=0\nfor d in range(1,isqrt(n)+1):\n if n%d==0:ans+=1 if d*d==n else 2\nprint(ans)",
        "循环 因子枚举",
    )
    add(
        "数字反转",
        "反转整数的十进制数位，去除结果的前导零并保留负号。",
        "一个整数 n。",
        "输出反转后的整数。",
        "-10^9 ≤ n ≤ 10^9。",
        ["120\n", "-305\n", "0\n", "7\n", "1000000000\n", "999999999\n"],
        lambda s: (-1 if int(s) < 0 else 1) * int(str(abs(int(s)))[::-1]),
        "n=int(input());sign=-1 if n<0 else 1;n=abs(n);r=0\nwhile n:r=r*10+n%10;n//=10\nprint(sign*r)",
        "循环 数位",
    )
    add(
        "区间素数",
        "统计闭区间内素数数量，1不是素数。",
        "一行两个整数 l r。",
        "输出数量。",
        "1 ≤ l ≤ r ≤ 10000。",
        ["1 10\n", "1 1\n", "2 2\n", "90 110\n", "100 200\n", "1 10000\n"],
        lambda s: sum(
            n >= 2 and all(n % d for d in range(2, math.isqrt(n) + 1))
            for n in range(nums(s)[0], nums(s)[1] + 1)
        ),
        "l,r=map(int,input().split());prime=[True]*(r+1);prime[0]=False\nif r>=1:prime[1]=False\nfor p in range(2,int(r**0.5)+1):\n if prime[p]:\n  for j in range(p*p,r+1,p):prime[j]=False\nprint(sum(prime[l:r+1]))",
        "筛法 循环",
    )
    add(
        "最小达标天数",
        "第一天存入 a 元，以后每天比前一天多存 d 元，求累计金额至少为 t 的最少天数。",
        "一行三个整数 a d t。",
        "输出最少天数。",
        "1 ≤ a,t ≤ 10^6，0 ≤ d ≤ 1000。",
        ["2 1 9\n", "5 0 20\n", "1 0 1\n", "1 0 1000000\n", "3 7 100\n", "100 0 1\n"],
        lambda s: next(
            n
            for n in range(1, 1000001)
            if n * nums(s)[0] + n * (n - 1) // 2 * nums(s)[1] >= nums(s)[2]
        ),
        "a,d,t=map(int,input().split());lo,hi=1,t\nwhile lo<hi:\n m=(lo+hi)//2\n if m*a+m*(m-1)//2*d>=t:hi=m\n else:lo=m+1\nprint(lo)",
        "模拟 二分答案",
    )

    arrays = [[2, 5, 1], [0], [-5, -2, -3], [3, 3, 1, 2], [1, 2, 3, 4, 5], [1000000, -1000000, 7]]
    group("arrays", "简单 简单 简单 中等 中等 中等")
    add(
        "数组总和",
        "计算数组中所有整数之和。",
        "第一行 n，第二行 n 个整数。",
        "输出总和。",
        "1 ≤ n ≤ 10000，元素绝对值不超过10^6。",
        list(map(pack, arrays)),
        lambda s: sum(arr(s)),
        "n=int(input());a=list(map(int,input().split()));print(sum(a))",
        "数组 遍历",
    )
    add(
        "第二大不同值",
        "找出数组中第二大的不同整数；不足两个不同值时输出 NONE。",
        "第一行 n，第二行 n 个整数。",
        "输出第二大不同值或 NONE。",
        "1 ≤ n ≤ 10000，元素绝对值不超过10^9。",
        list(map(pack, arrays)),
        lambda s: sorted(set(arr(s)))[-2] if len(set(arr(s))) > 1 else "NONE",
        'n=int(input());a=sorted(set(map(int,input().split())));print(a[-2] if len(a)>1 else "NONE")',
        "数组 去重",
    )
    add(
        "频次冠军",
        "输出出现次数最多的整数；次数相同选数值最小的。",
        "第一行 n，第二行 n 个整数。",
        "输出该整数及其出现次数。",
        "1 ≤ n ≤ 10000，元素绝对值不超过10^6。",
        list(map(pack, arrays)),
        lambda s: (lambda c: (min(c, key=lambda x: (-c[x], x)), max(c.values())))(Counter(arr(s))),
        "from collections import Counter\nn=int(input());c=Counter(map(int,input().split()));v=min(c,key=lambda x:(-c[x],x));print(v,c[v])",
        "哈希表 频次统计",
    )

    def range_oracle(s):
        lines = s.splitlines()
        a = nums(lines[1])
        return "\n".join(str(sum(a[left - 1 : right])) for left, right in map(nums, lines[2:]))

    add(
        "区间和查询",
        "多次查询数组闭区间的元素之和，下标从1开始。",
        "首行 n q，次行 n 个整数，随后 q 行 l r。",
        "每个查询输出一行区间和。",
        "1 ≤ n,q ≤ 10000，1 ≤ l ≤ r ≤ n，元素绝对值≤10^6。",
        [
            "3 2\n1 2 3\n1 3\n2 2\n",
            "1 1\n-9\n1 1\n",
            "4 2\n0 0 0 0\n1 4\n3 4\n",
            "3 2\n-1 2 -3\n1 2\n2 3\n",
            "5 1\n5 4 3 2 1\n2 5\n",
            "2 2\n1000000 1000000\n1 2\n1 1\n",
        ],
        range_oracle,
        "n,q=map(int,input().split());a=list(map(int,input().split()));p=[0]\nfor x in a:p.append(p[-1]+x)\nfor _ in range(q):\n l,r=map(int,input().split());print(p[r]-p[l-1])",
        "前缀和 区间查询",
    )
    add(
        "和为目标的连续段",
        "统计和恰好为 k 的非空连续子数组数量。",
        "首行 n k，次行 n 个整数。",
        "输出数量。",
        "1 ≤ n ≤ 10000，|k|、元素绝对值≤10^6。",
        [
            "3 2\n1 1 1\n",
            "1 0\n0\n",
            "4 0\n0 0 0 0\n",
            "4 0\n1 -1 1 -1\n",
            "3 99\n1 2 3\n",
            "5 3\n1 2 0 3 -3\n",
        ],
        lambda s: sum(
            sum(nums(s)[2:][i:j]) == nums(s)[1]
            for i in range(nums(s)[0])
            for j in range(i + 1, nums(s)[0] + 1)
        ),
        "from collections import defaultdict\nn,k=map(int,input().split());a=list(map(int,input().split()));c=defaultdict(int);c[0]=1;p=ans=0\nfor x in a:p+=x;ans+=c[p-k];c[p]+=1\nprint(ans)",
        "前缀和 哈希表",
    )
    add(
        "最长连续整数链",
        "数组次序可以忽略，求其中由不同整数构成的最长连续序列长度。",
        "第一行 n，第二行 n 个整数。",
        "输出长度。",
        "1 ≤ n ≤ 10000，元素绝对值≤10^9。",
        list(map(pack, arrays)),
        lambda s: max(
            sum(1 for _ in g)
            for _, g in it.groupby(enumerate(sorted(set(arr(s)))), lambda p: p[1] - p[0])
        ),
        "n=int(input());a=set(map(int,input().split()));best=0\nfor x in a:\n if x-1 not in a:\n  y=x\n  while y in a:y+=1\n  best=max(best,y-x)\nprint(best)",
        "集合 连续序列",
    )

    group("strings", "简单 简单 简单 简单 中等 中等")
    strings = [
        "code lab\n",
        "a\n",
        "  blue   sea  \n",
        "a a a\n",
        "hello world again\n",
        "123 xyz\n",
    ]
    add(
        "单词倒序",
        "反转一行文本的单词顺序，单词间输出一个空格。",
        "一行由英文、数字和空格组成的文本，至少含一个单词。",
        "输出倒序后的单词。",
        "文本长度1至1000。",
        strings,
        lambda s: " ".join(s.split()[::-1]),
        'print(" ".join(input().split()[::-1]))',
        "字符串 分词",
    )
    add(
        "清洗后回文",
        "忽略大小写与非英文字母数字字符，判断剩余文本是否回文；空串视为回文。",
        "一行ASCII文本。",
        "输出 YES 或 NO。",
        "文本长度0至1000。",
        ["A man, a plan, a canal: Panama\n", "race a car\n", "\n", "!!!\n", "0P\n", "Abba\n"],
        lambda s: (
            "YES"
            if (lambda t: t == t[::-1])("".join(c.lower() for c in s.rstrip("\n") if c.isalnum()))
            else "NO"
        ),
        's="".join(c.lower() for c in input() if c.isalnum());print("YES" if s==s[::-1] else "NO")',
        "字符串 回文",
    )
    add(
        "连续字符压缩",
        "将每段连续相同字母写为字母和次数，包括次数为1的段。",
        "一行非空小写英文字母串。",
        "输出压缩结果，例如 aaabb 输出 a3b2。",
        "长度1至10000。",
        ["aaabb\n", "a\n", "abc\n", "aaaaaa\n", "aabbaa\n", "zzxyyy\n"],
        lambda s: "".join(c + str(len(list(g))) for c, g in it.groupby(s.strip())),
        's=input();out=[];i=0\nwhile i<len(s):\n j=i+1\n while j<len(s) and s[j]==s[i]:j+=1\n out.append(s[i]+str(j-i));i=j\nprint("".join(out))',
        "字符串 游程编码",
    )
    add(
        "最长单词长度",
        "计算文本中最长单词的长度，单词以空格分隔。",
        "一行英文单词和空格，至少含一个单词。",
        "输出最大长度。",
        "文本长度1至1000。",
        strings,
        lambda s: max(map(len, s.split())),
        "print(max(map(len,input().split())))",
        "字符串 遍历",
    )
    add(
        "版本号比较",
        "比较由非负整数段组成的版本号，缺失的末尾段按0处理，允许段内前导零。",
        "两行版本号，每段用英文句点分隔。",
        "第一版本较小输出 -1，相等输出 0，较大输出 1。",
        "每个版本1至20段，每段数值≤10^9。",
        ["1.2\n1.10\n", "1.0\n1\n", "01.002\n1.2.0\n", "2\n1.999\n", "0\n0.0\n", "1.0.1\n1\n"],
        lambda s: (lambda a, b: (a > b) - (a < b))(
            *[
                tuple(nums(x.replace(".", " ")) + [0] * (20 - len(x.split("."))))
                for x in s.splitlines()
            ]
        ),
        'a=list(map(int,input().split(".")));b=list(map(int,input().split(".")));n=max(len(a),len(b));a+=[0]*(n-len(a));b+=[0]*(n-len(b));print((a>b)-(a<b))',
        "字符串 分段比较",
    )
    add(
        "超长非负整数相加",
        "计算两个非负十进制整数之和，输出中去除前导零。",
        "两行数字串。",
        "输出和。",
        "每串1至1000位，可有前导零；用逐位计算方法完成。",
        ["999\n1\n", "0\n0\n", "0012\n0008\n", "12345\n98765\n", "9" * 100 + "\n1\n", "123\n7\n"],
        lambda s: sum(map(int, s.split())),
        'a=input()[::-1];b=input()[::-1];out=[];carry=0\nfor i in range(max(len(a),len(b))):\n t=carry+(int(a[i]) if i<len(a) else 0)+(int(b[i]) if i<len(b) else 0);out.append(str(t%10));carry=t//10\nif carry:out.append(str(carry))\nprint("".join(out[::-1]).lstrip("0") or "0")',
        "字符串 模拟加法",
    )

    group("search", "简单 简单 中等 中等 中等 困难")
    add(
        "排序去重",
        "将数组去重后按升序输出。",
        "第一行 n，第二行 n 个整数。",
        "输出不同整数，空格分隔。",
        "1 ≤ n ≤ 10000，元素绝对值≤10^9。",
        list(map(pack, arrays)),
        lambda s: sorted(set(arr(s))),
        "n=int(input());print(*sorted(set(map(int,input().split()))))",
        "排序 去重",
    )
    add(
        "有序插入位置",
        "在非递减数组中找到第一个大于或等于 x 的位置；不存在时返回 n。下标从0开始。",
        "首行 n x，次行 n 个有序整数。",
        "输出位置。",
        "1 ≤ n ≤ 10000，整数绝对值≤10^9。",
        [
            "4 3\n1 3 3 5\n",
            "1 0\n2\n",
            "1 9\n2\n",
            "3 2\n2 2 2\n",
            "3 -4\n-3 0 7\n",
            "4 4\n1 2 3 5\n",
        ],
        lambda s: sum(x < nums(s)[1] for x in nums(s)[2:]),
        "n,x=map(int,input().split());a=list(map(int,input().split()));l,r=0,n\nwhile l<r:\n m=(l+r)//2\n if a[m]<x:l=m+1\n else:r=m\nprint(l)",
        "二分查找 边界条件",
    )
    add(
        "第k大元素",
        "按包含重复值的降序次序找出第 k 个元素。",
        "首行 n k，次行 n 个整数。",
        "输出第 k 大的元素。",
        "1 ≤ k ≤ n ≤ 10000，整数绝对值≤10^9。",
        [
            "5 2\n3 1 5 5 2\n",
            "1 1\n-7\n",
            "3 3\n1 2 3\n",
            "4 1\n0 0 0 0\n",
            "5 4\n-2 -9 -1 0 7\n",
            "6 3\n8 7 6 5 4 3\n",
        ],
        lambda s: sorted(nums(s)[2:], reverse=True)[nums(s)[1] - 1],
        "import heapq\nn,k=map(int,input().split());a=list(map(int,input().split()));print(heapq.nlargest(k,a)[-1])",
        "排序 堆",
    )
    add(
        "旋转有序数组定位",
        "一个严格递增数组经过循环旋转，求 x 的下标，不存在则输出 -1。",
        "首行 n x，次行 n 个整数。",
        "输出从0开始的下标或 -1。",
        "1 ≤ n ≤ 10000，数组元素互不相同且绝对值≤10^9。",
        [
            "5 1\n4 5 1 2 3\n",
            "1 2\n2\n",
            "1 3\n2\n",
            "4 4\n1 2 3 4\n",
            "5 9\n4 5 1 2 3\n",
            "5 -2\n0 1 2 -3 -2\n",
        ],
        lambda s: nums(s)[2:].index(nums(s)[1]) if nums(s)[1] in nums(s)[2:] else -1,
        "n,x=map(int,input().split());a=list(map(int,input().split()));l,r=0,n-1;ans=-1\nwhile l<=r:\n m=(l+r)//2\n if a[m]==x:ans=m;break\n if a[l]<=a[m]:\n  if a[l]<=x<a[m]:r=m-1\n  else:l=m+1\n else:\n  if a[m]<x<=a[r]:l=m+1\n  else:r=m-1\nprint(ans)",
        "二分查找 旋转数组",
    )

    def shipping(s):
        n, d, *a = nums(s)
        for cap in range(max(a), sum(a) + 1):
            days, load = 1, 0
            for x in a:
                if load + x > cap:
                    days += 1
                    load = 0
                load += x
            if days <= d:
                return cap

    add(
        "按序运输的最小容量",
        "货物按给定顺序装运，每天装一个连续段且不可拆分单件，求 d 天内运完的最小日容量。",
        "首行 n d，次行 n 个正重量。",
        "输出最小容量。",
        "1 ≤ d ≤ n ≤ 10000，每件重量1至1000。",
        [
            "5 3\n1 2 3 4 5\n",
            "1 1\n7\n",
            "4 4\n9 2 3 1\n",
            "4 1\n9 2 3 1\n",
            "5 2\n3 2 2 4 1\n",
            "3 2\n1000 1000 1000\n",
        ],
        shipping,
        "n,d=map(int,input().split());a=list(map(int,input().split()));l,r=max(a),sum(a)\nwhile l<r:\n m=(l+r)//2;days=1;load=0\n for x in a:\n  if load+x>m:days+=1;load=0\n  load+=x\n if days<=d:r=m\n else:l=m+1\nprint(l)",
        "二分答案 贪心",
    )
    add(
        "逆序对计数",
        "统计满足 i < j 且 a[i] > a[j] 的下标对数量，相等元素不计入。",
        "第一行 n，第二行 n 个整数。",
        "输出数量。",
        "1 ≤ n ≤ 100000，元素绝对值≤10^9。",
        list(map(pack, arrays)),
        lambda s: sum(x > y for i, x in enumerate(arr(s)) for y in arr(s)[i + 1 :]),
        "n=int(input());a=list(map(int,input().split()))\ndef solve(a):\n if len(a)<2:return a,0\n m=len(a)//2;l,x=solve(a[:m]);r,y=solve(a[m:]);out=[];i=j=0;ans=x+y\n while i<len(l) and j<len(r):\n  if l[i]<=r[j]:out.append(l[i]);i+=1\n  else:out.append(r[j]);j+=1;ans+=len(l)-i\n return out+l[i:]+r[j:],ans\nprint(solve(a)[1])",
        "归并排序 分治",
    )

    build_advanced()
    assert len(PROBLEMS) == 60 and Counter(p["difficulty"] for p in PROBLEMS) == {
        "简单": 30,
        "中等": 24,
        "困难": 6,
    }
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data/problem_library.json").write_text(
        json.dumps(PROBLEMS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "data/reference_solutions.json").write_text(
        json.dumps(REFERENCES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Built", len(PROBLEMS), "problems and", sum(len(p["cases"]) for p in PROBLEMS), "cases.")


def build_advanced():
    group("windows", "简单 简单 中等 中等 中等 困难")
    merges = [
        "3 2\n1 3 5\n2 4\n",
        "0 1\n\n7\n",
        "1 0\n-2\n\n",
        "2 2\n1 1\n1 1\n",
        "2 3\n-5 0\n-4 0 8\n",
        "0 0\n\n\n",
    ]
    add(
        "合并有序数组",
        "将两个非递减数组合并为一个非递减数组。",
        "首行 n m，第二、三行分别为两个数组；长度为0时该行为空。",
        "输出合并结果，空格分隔；空数组输出 EMPTY。",
        "0 ≤ n,m ≤ 10000，元素绝对值≤10^9。",
        merges,
        lambda s: sorted(nums(s)[2:]),
        'n,m=map(int,input().split());a=list(map(int,input().split()));b=list(map(int,input().split()));out=[];i=j=0\nwhile i<n and j<m:\n if a[i]<=b[j]:out.append(a[i]);i+=1\n else:out.append(b[j]);j+=1\nout+=a[i:]+b[j:];print(" ".join(map(str,out)) or "EMPTY")',
        "双指针 有序合并",
    )
    add(
        "配对和计数",
        "统计数组中满足 i < j 且 a[i]+a[j]=k 的下标对数量。",
        "首行 n k，次行 n 个整数。",
        "输出数量；重复值在不同下标时分别计数。",
        "1 ≤ n ≤ 10000，元素和k的绝对值≤10^9。",
        [
            "4 5\n1 4 2 3\n",
            "1 2\n1\n",
            "4 2\n1 1 1 1\n",
            "4 0\n-1 1 -1 1\n",
            "3 99\n1 2 3\n",
            "5 4\n2 2 1 3 0\n",
        ],
        lambda s: sum(x + y == nums(s)[1] for x, y in it.combinations(nums(s)[2:], 2)),
        "from collections import Counter\nn,k=map(int,input().split());a=list(map(int,input().split()));seen=Counter();ans=0\nfor x in a:ans+=seen[k-x];seen[x]+=1\nprint(ans)",
        "配对 哈希表",
    )
    add(
        "最长不重复片段",
        "求字符串中不含重复字符的最长连续片段长度。",
        "一行小写字母串，允许为空。",
        "输出长度。",
        "长度0至100000。",
        ["abcabcbb\n", "\n", "aaaa\n", "abba\n", "pwwkew\n", "abcdef\n"],
        lambda s: max(
            [0]
            + [
                j - i
                for i in range(len(s.rstrip("\n")))
                for j in range(i + 1, len(s.rstrip("\n")) + 1)
                if len(set(s[i:j])) == j - i
            ]
        ),
        "s=input();last={};l=ans=0\nfor r,c in enumerate(s):\n l=max(l,last.get(c,-1)+1);last[c]=r;ans=max(ans,r-l+1)\nprint(ans)",
        "滑动窗口 字符串",
    )
    add(
        "最短达标连续段",
        "在正整数数组中找出和至少为 t 的最短非空连续段。",
        "首行 n t，次行 n 个正整数。",
        "输出最短长度，不存在则输出0。",
        "1 ≤ n ≤ 100000，1 ≤ t ≤ 10^9，元素1至10000。",
        [
            "6 7\n2 3 1 2 4 3\n",
            "1 5\n5\n",
            "3 99\n1 2 3\n",
            "4 4\n1 1 1 1\n",
            "5 10\n10 1 1 1 1\n",
            "3 3\n1 1 1\n",
        ],
        lambda s: min(
            [
                j - i
                for i in range(nums(s)[0])
                for j in range(i + 1, nums(s)[0] + 1)
                if sum(nums(s)[2:][i:j]) >= nums(s)[1]
            ]
            or [0]
        ),
        "n,t=map(int,input().split());a=list(map(int,input().split()));l=total=0;ans=n+1\nfor r,x in enumerate(a):\n total+=x\n while total>=t:ans=min(ans,r-l+1);total-=a[l];l+=1\nprint(ans if ans<=n else 0)",
        "滑动窗口 正数数组",
    )
    add(
        "翻转后的连续1",
        "最多将 k 个0变成1，求可得到的最长全1连续段长度。",
        "首行 n k，次行 n 个0或1。",
        "输出最大长度。",
        "1 ≤ n ≤ 100000，0 ≤ k ≤ n。",
        [
            "6 1\n1 0 1 1 0 1\n",
            "1 0\n0\n",
            "3 3\n0 0 0\n",
            "4 0\n1 1 1 1\n",
            "5 0\n1 0 1 0 1\n",
            "5 2\n0 1 0 1 0\n",
        ],
        lambda s: max(
            [0]
            + [
                j - i
                for i in range(nums(s)[0])
                for j in range(i + 1, nums(s)[0] + 1)
                if nums(s)[2:][i:j].count(0) <= nums(s)[1]
            ]
        ),
        "n,k=map(int,input().split());a=list(map(int,input().split()));l=z=ans=0\nfor r,x in enumerate(a):\n z+=x==0\n while z>k:z-=a[l]==0;l+=1\n ans=max(ans,r-l+1)\nprint(ans)",
        "滑动窗口 双指针",
    )

    def cover(s):
        a, b = s.splitlines()
        need = Counter(b)
        return min(
            [
                j - i
                for i in range(len(a))
                for j in range(i + 1, len(a) + 1)
                if not need - Counter(a[i:j])
            ]
            or [0]
        )

    add(
        "最短覆盖片段",
        "在 s 中寻找包含 t 所有字母及其重复次数的最短连续片段。",
        "两行非空英文字母串 s 和 t，区分大小写。",
        "输出最短长度；不存在则输出0。",
        "1 ≤ |s|,|t| ≤ 100000。",
        ["ADOBECODEBANC\nABC\n", "a\na\n", "a\naa\n", "aaab\naab\n", "xyz\nA\n", "abbbcaa\naa\n"],
        cover,
        "from collections import Counter\ns=input();t=input();need=Counter(t);missing=len(t);l=0;ans=len(s)+1\nfor r,c in enumerate(s):\n if need[c]>0:missing-=1\n need[c]-=1\n while missing==0:\n  ans=min(ans,r-l+1);need[s[l]]+=1\n  if need[s[l]]>0:missing+=1\n  l+=1\nprint(ans if ans<=len(s) else 0)",
        "滑动窗口 频次统计",
    )

    group("stacks", "简单 简单 中等 中等 中等 困难")
    brackets = ["([])\n", "([)]\n", "\n", "((\n", "]\n", "{}[()]\n"]

    def balanced(s):
        old = s.strip()
        while True:
            new = old.replace("()", "").replace("[]", "").replace("{}", "")
            if new == old:
                return "YES" if not new else "NO"
            old = new

    add(
        "括号匹配",
        "检查三种括号是否正确嵌套和配对。空串合法。",
        "一行仅含 ()[]{} 的字符串。",
        "输出 YES 或 NO。",
        "长度0至100000。",
        brackets,
        balanced,
        's=input();stack=[];ok=True;p={")":"(","]":"[","}":"{"}\nfor c in s:\n if c in "([{":stack.append(c)\n elif not stack or stack.pop()!=p[c]:ok=False;break\nprint("YES" if ok and not stack else "NO")',
        "栈 括号",
    )
    queue_inputs = [
        "5\nPUSH 2\nPUSH 3\nFRONT\nPOP\nFRONT\n",
        "1\nFRONT\n",
        "2\nPUSH -1\nPOP\n",
        "3\nPOP\nPUSH 9\nFRONT\n",
        "4\nPUSH 0\nPUSH 1\nPOP\nPOP\n",
        "6\nPUSH 2\nPOP\nPOP\nPUSH 4\nFRONT\nPOP\n",
    ]
    add(
        "队列操作日志",
        "模拟初始为空的队列。PUSH入队；POP出队并输出该值；FRONT只查看队首。空队列的POP/FRONT输出EMPTY。",
        "首行 q，随后 q 行 PUSH x、POP 或 FRONT；至少有一次POP或FRONT。",
        "每次POP或FRONT各输出一行。",
        "1 ≤ q ≤ 10000，|x|≤10^9。",
        queue_inputs,
        dict(
            zip(
                queue_inputs,
                ["2\n2\n3", "EMPTY", "-1", "EMPTY\n9", "0\n1", "2\nEMPTY\n4\n4"],
                strict=False,
            )
        ).__getitem__,
        'from collections import deque\nq=deque()\nfor _ in range(int(input())):\n a=input().split()\n if a[0]=="PUSH":q.append(int(a[1]))\n elif not q:print("EMPTY")\n elif a[0]=="FRONT":print(q[0])\n else:print(q.popleft())',
        "队列 模拟",
    )
    arrays = [[2, 1, 3], [7], [3, 3, 3], [5, 4, 3, 2, 1], [1, 2, 3, 4, 5], [-2, 0, -1, 8]]
    add(
        "右侧首个更大值的位置",
        "对每个元素，找右侧第一个严格更大元素的下标。",
        "第一行 n，第二行 n 个整数。",
        "输出 n 个位置，下标从1开始；不存在输出0。",
        "1 ≤ n ≤ 100000，元素绝对值≤10^9。",
        list(map(pack, arrays)),
        lambda s: [
            next((j + 1 for j in range(i + 1, len(arr(s))) if arr(s)[j] > x), 0)
            for i, x in enumerate(arr(s))
        ],
        "n=int(input());a=list(map(int,input().split()));stack=[];ans=[0]*n\nfor i,x in enumerate(a):\n while stack and a[stack[-1]]<x:ans[stack.pop()]=i+1\n stack.append(i)\nprint(*ans)",
        "单调栈 数组",
    )
    rpn = ["2 3 +\n", "4 2 /\n", "-7 3 /\n", "3 4 + 2 *\n", "9 2 - 3 /\n", "5 1 2 + 4 * + 3 -\n"]
    add(
        "后缀表达式计算",
        "计算合法后缀表达式。除法向零截断，保证除数不为0。",
        "一行用空格分隔的整数或 + - * /。",
        "输出结果。",
        "1至1000个记号，中间整数绝对值≤10^9。",
        rpn,
        dict(zip(rpn, [5, 2, -2, 14, 2, 14], strict=False)).__getitem__,
        'st=[]\nfor t in input().split():\n if t not in {"+","-","*","/"}:st.append(int(t));continue\n b=st.pop();a=st.pop()\n if t=="+":v=a+b\n elif t=="-":v=a-b\n elif t=="*":v=a*b\n else:v=(abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1)\n st.append(v)\nprint(st[0])',
        "栈 表达式",
    )
    add(
        "等待升温",
        "每天的温度已知，计算从当天起还需等待几天才出现更高温度。",
        "第一行 n，第二行 n 个温度。",
        "输出 n 个等待天数；以后没有更高温度则为0。",
        "1 ≤ n ≤ 100000，-100 ≤ 温度 ≤ 100。",
        list(map(pack, arrays)),
        lambda s: [
            next((j - i for j in range(i + 1, len(arr(s))) if arr(s)[j] > x), 0)
            for i, x in enumerate(arr(s))
        ],
        "n=int(input());a=list(map(int,input().split()));st=[];ans=[0]*n\nfor i,t in enumerate(a):\n while st and a[st[-1]]<t:j=st.pop();ans[j]=i-j\n st.append(i)\nprint(*ans)",
        "单调栈 距离计算",
    )
    hist = [[2, 1, 5, 6, 2, 3], [0], [5], [3, 3, 3], [1, 2, 3, 4], [4, 3, 2, 1]]
    add(
        "柱状图最大矩形",
        "每个柱子宽为1，求柱状图内能容纳的最大矩形面积。",
        "第一行 n，第二行 n 个非负高度。",
        "输出最大面积。",
        "1 ≤ n ≤ 100000，0 ≤ 高度 ≤ 10^6。",
        list(map(pack, hist)),
        lambda s: max(
            min(arr(s)[i:j]) * (j - i)
            for i in range(len(arr(s)))
            for j in range(i + 1, len(arr(s)) + 1)
        ),
        "n=int(input());a=list(map(int,input().split()))+[0];st=[];ans=0\nfor i,h in enumerate(a):\n while st and a[st[-1]]>h:\n  height=a[st.pop()];left=st[-1]+1 if st else 0;ans=max(ans,height*(i-left))\n st.append(i)\nprint(ans)",
        "单调栈 最大矩形",
    )

    group("recursion", "简单 简单 中等 中等 中等 困难")
    add(
        "递归求平方和",
        "计算从1到n的平方和，n为0时结果为0。尝试用递归表达子问题。",
        "一个整数 n。",
        "输出平方和。",
        "0 ≤ n ≤ 200。",
        ["0\n", "1\n", "2\n", "5\n", "20\n", "200\n"],
        lambda s: sum(x * x for x in range(1, int(s) + 1)),
        "def f(n):return 0 if n==0 else n*n+f(n-1)\nprint(f(int(input())))",
        "递归 终止条件",
    )
    add(
        "二进制串枚举",
        "按字典序输出所有长度为n的二进制串。n为0时只输出EMPTY。",
        "一个整数 n。",
        "每个二进制串一行，保留前导零。",
        "0 ≤ n ≤ 10。",
        ["0\n", "1\n", "2\n", "3\n", "4\n", "5\n"],
        lambda s: (
            "\n".join("".join(p) for p in it.product("01", repeat=int(s))) if int(s) else "EMPTY"
        ),
        'n=int(input())\ndef dfs(s):\n if len(s)==n:print(s or "EMPTY");return\n dfs(s+"0");dfs(s+"1")\ndfs("")',
        "递归 字典序",
    )
    subset = [
        "3 3\n1 2 3\n",
        "1 0\n0\n",
        "4 0\n0 0 0 0\n",
        "3 0\n-1 0 1\n",
        "3 9\n1 2 3\n",
        "5 5\n1 1 2 3 4\n",
    ]
    add(
        "目标和子集数",
        "每个下标的元素可选或不选，统计所选元素之和为t的方案数；空集也计入。",
        "首行 n t，次行 n 个整数。",
        "输出方案数，数值相同的不同下标视为不同选择。",
        "1 ≤ n ≤ 20，元素与t绝对值≤100。",
        subset,
        lambda s: sum(
            sum(a) == nums(s)[1]
            for k in range(nums(s)[0] + 1)
            for a in it.combinations(nums(s)[2:], k)
        ),
        "n,t=map(int,input().split());a=list(map(int,input().split()))\ndef dfs(i,s):\n if i==n:return int(s==t)\n return dfs(i+1,s)+dfs(i+1,s+a[i])\nprint(dfs(0,0))",
        "回溯 子集",
    )
    queens = ["1\n", "2\n", "3\n", "4\n", "5\n", "6\n"]
    add(
        "皇后摆放计数",
        "在n×n棋盘放n个皇后，每行每列各一个，且不能位于同一条对角线。",
        "一个整数 n。",
        "输出不同合法摆放数量，旋转或镜像视为不同。",
        "1 ≤ n ≤ 9。",
        queens,
        dict(zip(queens, [1, 0, 0, 2, 10, 4], strict=False)).__getitem__,
        "n=int(input());mask=(1<<n)-1\ndef dfs(cols,left,right):\n if cols==mask:return 1\n free=mask&~(cols|left|right);ans=0\n while free:\n  bit=free&-free;free-=bit;ans+=dfs(cols|bit,(left|bit)<<1,(right|bit)>>1)\n return ans\nprint(dfs(0,0,0))",
        "回溯 约束剪枝",
    )
    add(
        "选人组合数",
        "从编号1至n的人中选k人，不考虑选择顺序。",
        "一行两个整数 n k。",
        "输出组合数。",
        "0 ≤ k ≤ n ≤ 20。",
        ["5 2\n", "0 0\n", "6 0\n", "6 6\n", "10 3\n", "20 10\n"],
        lambda s: math.comb(*nums(s)),
        "from functools import lru_cache\n@lru_cache(None)\ndef f(n,k):\n if k==0 or k==n:return 1\n return f(n-1,k-1)+f(n-1,k)\nn,k=map(int,input().split());print(f(n,k))",
        "组合 递归记忆化",
    )
    paths = [
        "3 3\n1 2\n2 3\n1 3\n",
        "1 0\n",
        "3 1\n1 3\n",
        "4 5\n1 2\n2 3\n3 4\n1 3\n2 4\n",
        "4 6\n1 2\n1 3\n2 3\n3 2\n2 4\n3 4\n",
        "2 1\n1 2\n",
    ]

    def all_nodes(s):
        n, m, *es = nums(s)
        edges = set(zip(es[::2], es[1::2], strict=False))
        if n == 1:
            return 1
        return sum(
            all((a, b) in edges for a, b in zip((1,) + p + (n,), p + (n,), strict=False))
            for p in it.permutations(range(2, n))
        )

    add(
        "经过所有点的路径数",
        "在有向图中统计从1到n、每个顶点恰好经过一次的路径数。",
        "首行 n m，随后m行 u v 表示有向边；无自环和重边。",
        "输出路径数，n为1时空路径计1。",
        "1 ≤ n ≤ 15，0 ≤ m ≤ n(n-1)。",
        paths,
        all_nodes,
        "n,m=map(int,input().split());g=[[] for _ in range(n)]\nfor _ in range(m):\n u,v=map(int,input().split());g[u-1].append(v-1)\ndp={(1,0):1}\nfor mask in range(1,1<<n):\n for u in range(n):\n  ways=dp.get((mask,u),0)\n  if not ways:continue\n  for v in g[u]:\n   if not mask>>v&1:dp[(mask|1<<v,v)]=dp.get((mask|1<<v,v),0)+ways\nprint(dp.get(((1<<n)-1,n-1),0))",
        "状态压缩 路径计数",
    )

    group("graphs", "简单 简单 中等 中等 中等 困难")
    edges = [
        "4 3\n1 2\n2 3\n2 4\n",
        "1 0\n",
        "3 0\n",
        "4 2\n1 2\n3 4\n",
        "3 3\n1 2\n2 3\n1 3\n",
        "5 4\n1 2\n2 3\n3 4\n4 5\n",
    ]
    add(
        "无向图的度数",
        "统计无向图中每个顶点连接的边数。",
        "首行 n m，随后m行 u v；无自环和重边。",
        "按顶点1至n输出度数，空格分隔。",
        "1 ≤ n ≤ 10000，0 ≤ m ≤ 100000。",
        edges,
        lambda s: [nums(s)[2:].count(i) for i in range(1, nums(s)[0] + 1)],
        "n,m=map(int,input().split());d=[0]*n\nfor _ in range(m):\n u,v=map(int,input().split());d[u-1]+=1;d[v-1]+=1\nprint(*d)",
        "图 邻接关系",
    )
    trees = ["4\n1 1 2\n", "1\n\n", "5\n1 2 3 4\n", "5\n1 1 1 1\n", "6\n1 1 2 2 3\n", "3\n1 2\n"]
    add(
        "有根树的叶子数",
        "根为1，每个其他顶点给出父节点，统计没有子节点的叶子。单节点树的根也算叶子。",
        "第一行 n，第二行依次为顶点2至n的父节点；n为1时该行为空。",
        "输出叶子数量。",
        "1 ≤ n ≤ 100000，父节点编号小于当前顶点编号。",
        trees,
        lambda s: sum(i not in nums(s)[1:] for i in range(1, nums(s)[0] + 1)),
        "n=int(input());parents=list(map(int,input().split()));has=set(parents);print(n-len(has))",
        "树 叶子节点",
    )

    def components(s):
        n, m, *es = nums(s)
        p = list(range(n + 1))

        def root(x):
            while p[x] != x:
                x = p[x]
            return x

        for a, b in zip(es[::2], es[1::2], strict=False):
            p[root(a)] = root(b)
        return len({root(i) for i in range(1, n + 1)})

    add(
        "连通块数量",
        "统计无向图的连通块，孤立顶点各算一个。",
        "首行 n m，随后m行 u v；无自环和重边。",
        "输出连通块数量。",
        "1 ≤ n ≤ 10000，0 ≤ m ≤ 100000。",
        edges,
        components,
        "n,m=map(int,input().split());g=[[] for _ in range(n)]\nfor _ in range(m):\n u,v=map(int,input().split());g[u-1].append(v-1);g[v-1].append(u-1)\nseen=set();ans=0\nfor start in range(n):\n if start in seen:continue\n ans+=1;st=[start];seen.add(start)\n while st:\n  for v in g[st.pop()]:\n   if v not in seen:seen.add(v);st.append(v)\nprint(ans)",
        "图遍历 连通性",
    )
    grids = [
        "3 4\n1100\n0101\n0011\n",
        "1 1\n0\n",
        "1 1\n1\n",
        "2 2\n10\n01\n",
        "3 3\n111\n111\n111\n",
        "1 5\n10101\n",
    ]

    def islands(s):
        lines = s.splitlines()
        h, w = nums(lines[0])
        p = list(range(h * w))

        def root(x):
            while p[x] != x:
                x = p[x]
            return x

        for r in range(h):
            for c in range(w):
                if lines[r + 1][c] == "0":
                    continue
                for rr, cc in [(r + 1, c), (r, c + 1)]:
                    if rr < h and cc < w and lines[rr + 1][cc] == "1":
                        p[root(r * w + c)] = root(rr * w + cc)
        return len({root(r * w + c) for r in range(h) for c in range(w) if lines[r + 1][c] == "1"})

    add(
        "网格岛屿数量",
        "1表示陆地、0表示水，上下左右相连的陆地组成岛屿；对角相接不连通。",
        "首行 h w，随后h行各w个0/1字符，不含空格。",
        "输出岛屿数量。",
        "1 ≤ h,w ≤ 100。",
        grids,
        islands,
        'h,w=map(int,input().split());g=[list(input()) for _ in range(h)];ans=0\nfor r in range(h):\n for c in range(w):\n  if g[r][c]!="1":continue\n  ans+=1;st=[(r,c)];g[r][c]="0"\n  while st:\n   x,y=st.pop()\n   for a,b in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:\n    if 0<=a<h and 0<=b<w and g[a][b]=="1":g[a][b]="0";st.append((a,b))\nprint(ans)',
        "网格 DFS",
    )

    def shortest(s, weighted=False):
        n, m, *es = nums(s)
        inf = 10**30
        d = [[inf] * n for _ in range(n)]
        for i in range(n):
            d[i][i] = 0
        step = 3 if weighted else 2
        for i in range(0, len(es), step):
            u, v = es[i] - 1, es[i + 1] - 1
            d[u][v] = min(d[u][v], es[i + 2] if weighted else 1)
            if not weighted:
                d[v][u] = 1
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    d[i][j] = min(d[i][j], d[i][k] + d[k][j])
        return -1 if d[0][n - 1] == inf else d[0][n - 1]

    add(
        "最少经过几条边",
        "求无向图中从顶点1到顶点n的最短路径边数。",
        "首行 n m，随后m行 u v；无自环和重边。",
        "输出最少边数，不可达输出 -1。",
        "1 ≤ n ≤ 10000，0 ≤ m ≤ 100000。",
        edges,
        shortest,
        "from collections import deque\nn,m=map(int,input().split());g=[[] for _ in range(n)]\nfor _ in range(m):\n u,v=map(int,input().split());g[u-1].append(v-1);g[v-1].append(u-1)\nd=[-1]*n;d[0]=0;q=deque([0])\nwhile q:\n u=q.popleft()\n for v in g[u]:\n  if d[v]<0:d[v]=d[u]+1;q.append(v)\nprint(d[-1])",
        "BFS 最短路",
    )
    weighted = [
        "3 3\n1 2 2\n2 3 3\n1 3 9\n",
        "1 0\n",
        "3 1\n1 2 1\n",
        "3 3\n1 2 0\n2 3 0\n1 3 2\n",
        "4 4\n1 2 5\n1 3 1\n3 2 1\n2 4 2\n",
        "2 1\n2 1 3\n",
    ]
    add(
        "带权路线最短距离",
        "有向图的边具有非负长度，求从1到n的最短距离。",
        "首行 n m，随后m行 u v w；无自环和重边。",
        "输出最短距离，不可达输出 -1。",
        "1 ≤ n ≤ 10000，0 ≤ m ≤ 100000，0 ≤ w ≤ 10^6。",
        weighted,
        lambda s: shortest(s, True),
        "import heapq\nn,m=map(int,input().split());g=[[] for _ in range(n)]\nfor _ in range(m):\n u,v,w=map(int,input().split());g[u-1].append((v-1,w))\nd=[10**30]*n;d[0]=0;q=[(0,0)]\nwhile q:\n cost,u=heapq.heappop(q)\n if cost!=d[u]:continue\n for v,w in g[u]:\n  if cost+w<d[v]:d[v]=cost+w;heapq.heappush(q,(d[v],v))\nprint(-1 if d[-1]==10**30 else d[-1])",
        "Dijkstra 优先队列",
    )

    group("dp", "简单 简单 简单 中等 中等 困难")
    add(
        "台阶走法",
        "每次走1或2级台阶，求走到第n级的方案数；n为0时空走法算1种。",
        "一个整数 n。",
        "输出方案数对1000000007取模后的值。",
        "0 ≤ n ≤ 100000。",
        ["0\n", "1\n", "2\n", "5\n", "10\n", "30\n"],
        lambda s: sum(math.comb(int(s) - k, k) for k in range(int(s) // 2 + 1)) % 1000000007,
        "n=int(input());a=b=1\nfor _ in range(n):a,b=b,(a+b)%1000000007\nprint(a)",
        "动态规划 状态转移",
    )
    houses = [[2, 7, 9, 3, 1], [0], [5], [1, 1, 1, 1], [9, 1, 1, 9], [0, 0, 0]]
    add(
        "不相邻奖励",
        "从一列非负奖励中挑选若干项，相邻项不可同时选择，求最大总奖励。允许全部不选。",
        "第一行 n，第二行 n 个非负整数。",
        "输出最大总奖励。",
        "1 ≤ n ≤ 100000，单项≤10^6。",
        list(map(pack, houses)),
        lambda s: max(
            sum(arr(s)[i] for i in range(len(arr(s))) if mask >> i & 1)
            for mask in range(1 << len(arr(s)))
            if not mask & (mask << 1)
        ),
        "n=int(input());a=list(map(int,input().split()));skip=take=0\nfor x in a:skip,take=max(skip,take),skip+x\nprint(max(skip,take))",
        "动态规划 相邻约束",
    )
    arrays = [[2, -3, 4, 5, -1], [-5], [-3, -2, -7], [0, 0, 0], [1, 2, 3], [5, -9, 6]]
    add(
        "最大连续段和",
        "求非空连续子数组的最大元素和。",
        "第一行 n，第二行 n 个整数。",
        "输出最大和；全负数组也必须选至少一个元素。",
        "1 ≤ n ≤ 100000，元素绝对值≤10^6。",
        list(map(pack, arrays)),
        lambda s: max(
            sum(arr(s)[i:j]) for i in range(len(arr(s))) for j in range(i + 1, len(arr(s)) + 1)
        ),
        "n=int(input());a=list(map(int,input().split()));end=ans=a[0]\nfor x in a[1:]:end=max(x,end+x);ans=max(ans,end)\nprint(ans)",
        "动态规划 连续子数组",
    )

    def coins(s):
        n, target, *a = nums(s)
        q = deque([(0, 0)])
        seen = {0}
        while q:
            value, steps = q.popleft()
            if value == target:
                return steps
            for c in a:
                if value + c <= target and value + c not in seen:
                    seen.add(value + c)
                    q.append((value + c, steps + 1))
        return -1

    add(
        "最少硬币数",
        "每种面额硬币可无限使用，求凑出目标金额的最少硬币数量。",
        "首行 n t，次行 n 个互不相同的正面额。",
        "输出最少数量，不可凑出输出 -1，目标0输出0。",
        "1 ≤ n ≤ 20，0 ≤ t ≤ 10000，面额1至1000。",
        ["3 11\n1 2 5\n", "1 3\n2\n", "2 0\n2 7\n", "2 6\n1 3\n", "3 7\n2 3 5\n", "1 20\n4\n"],
        coins,
        "n,t=map(int,input().split());a=list(map(int,input().split()));d=[0]+[t+1]*t\nfor v in range(1,t+1):\n for c in a:\n  if c<=v:d[v]=min(d[v],d[v-c]+1)\nprint(-1 if d[t]>t else d[t])",
        "动态规划 完全背包",
    )

    def grid_paths(s):
        lines = s.splitlines()
        h, w = nums(lines[0])
        ans = 0
        for down in it.combinations(range(h + w - 2), h - 1):
            r = c = 0
            ok = lines[1][0] == "0"
            for i in range(h + w - 2):
                if i in down:
                    r += 1
                else:
                    c += 1
                ok = ok and lines[r + 1][c] == "0"
            ans += ok
        return ans % 1000000007

    paths = [
        "3 3\n000\n010\n000\n",
        "1 1\n0\n",
        "1 1\n1\n",
        "2 2\n00\n01\n",
        "2 3\n000\n000\n",
        "3 2\n00\n11\n00\n",
    ]
    add(
        "避障网格路径",
        "从左上到右下，每步只能向右或向下。0可通行，1为障碍，起点或终点受阻时无路径。",
        "首行 h w，随后h行各w个0/1字符。",
        "输出路径数对1000000007取模后的值。",
        "1 ≤ h,w ≤ 100。",
        paths,
        grid_paths,
        'h,w=map(int,input().split());g=[input() for _ in range(h)];d=[0]*w;d[0]=1\nfor r in range(h):\n for c in range(w):\n  if g[r][c]=="1":d[c]=0\n  elif c:d[c]=(d[c]+d[c-1])%1000000007\nprint(d[-1])',
        "动态规划 网格路径",
    )

    def edit_distance(s):
        from functools import lru_cache

        a, b = s.splitlines()

        @lru_cache(None)
        def f(i, j):
            if i == len(a):
                return len(b) - j
            if j == len(b):
                return len(a) - i
            if a[i] == b[j]:
                return f(i + 1, j + 1)
            return 1 + min(f(i + 1, j), f(i, j + 1), f(i + 1, j + 1))

        return f(0, 0)

    add(
        "文本编辑距离",
        "每次可插入、删除或替换一个字符，求将a变为b的最少操作数。",
        "两行小写字母串 a b，两行都保留，允许为空。",
        "输出最少操作数。",
        "0 ≤ |a|,|b| ≤ 500。",
        ["kitten\nsitting\n", "\n\n", "a\n\n", "\nabc\n", "abc\nabc\n", "abc\nxyz\n"],
        edit_distance,
        "a=input();b=input();d=list(range(len(b)+1))\nfor i,x in enumerate(a,1):\n row=[i]\n for j,y in enumerate(b,1):row.append(min(row[-1]+1,d[j]+1,d[j-1]+(x!=y)))\n d=row\nprint(d[-1])",
        "动态规划 编辑距离",
    )


if __name__ == "__main__":
    build()
