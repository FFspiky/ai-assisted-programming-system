PROBLEMS = {
    "number-of-2s-in-range-lcci": {
        "title": "2出现的次数",
        "content": """
            <p>编写一个方法，计算从 0 到 n (含 n) 中数字 2 出现的次数。</p>

            <p><strong>示例:</strong></p>

            <pre><strong>输入: </strong>25
            <strong>输出: </strong>9
            <strong>解释: </strong>(2, 12, 20, 21, 22, 23, 24, 25)(注意 22 应该算作两次)</pre>

            <p>提示：</p>

            <ul>
                <li><code>n &lt;= 10^9</code></li>
            </ul>
        """
    },
    "power-of-three": {
        "title": "3的幂",
        "content": """
            <p>给定一个整数，写一个函数来判断它是否是 3&nbsp;的幂次方。如果是，返回 <code>true</code> ；否则，返回 <code>false</code> 。</p>

            <p>整数 <code>n</code> 是 3 的幂次方需满足：存在整数 <code>x</code> 使得 <code>n == 3<sup>x</sup></code></p>

            <p>&nbsp;</p>

            <p><strong>示例 1：</strong></p>

            <pre>
            <strong>输入：</strong>n = 27
            <strong>输出：</strong>true
            </pre>

            <p><strong>示例 2：</strong></p>

            <pre>
            <strong>输入：</strong>n = 0
            <strong>输出：</strong>false
            </pre>

            <p><strong>示例 3：</strong></p>

            <pre>
            <strong>输入：</strong>n = 9
            <strong>输出：</strong>true
            </pre>

            <p><strong>示例 4：</strong></p>

            <pre>
            <strong>输入：</strong>n = 45
            <strong>输出：</strong>false
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>-2<sup>31</sup> &lt;= n &lt;= 2<sup>31</sup> - 1</code></li>
            </ul>

            <p>&nbsp;</p>

            <p><strong>进阶：</strong>你能不使用循环或者递归来完成本题吗？</p>
        """
    },
    "pizza-with-3n-slices": {
        "title": "3n块披萨",
        "content": """
            <p>给你一个披萨，它由 3n 块不同大小的部分组成，现在你和你的朋友们需要按照如下规则来分披萨：</p>

            <ul>
                <li>你挑选 <strong>任意</strong>&nbsp;一块披萨。</li>
                <li>Alice 将会挑选你所选择的披萨逆时针方向的下一块披萨。</li>
                <li>Bob 将会挑选你所选择的披萨顺时针方向的下一块披萨。</li>
                <li>重复上述过程直到没有披萨剩下。</li>
            </ul>

            <p>每一块披萨的大小按顺时针方向由循环数组 <code>slices</code>&nbsp;表示。</p>

            <p>请你返回你可以获得的披萨大小总和的最大值。</p>

            <p>&nbsp;</p>

            <p><strong>示例 1：</strong></p>

            <p><img alt="" src="https://assets.leetcode-cn.com/aliyun-lc-upload/uploads/2020/03/21/sample_3_1723.png" style="height: 240px; width: 475px;" /></p>

            <pre>
            <strong>输入：</strong>slices = [1,2,3,4,5,6]
            <strong>输出：</strong>10
            <strong>解释：</strong>选择大小为 4 的披萨，Alice 和 Bob 分别挑选大小为 3 和 5 的披萨。然后你选择大小为 6 的披萨，Alice 和 Bob 分别挑选大小为 2 和 1 的披萨。你获得的披萨总大小为 4 + 6 = 10 。
            </pre>

            <p><strong>示例 2：</strong></p>

            <p><strong><img alt="" src="https://assets.leetcode-cn.com/aliyun-lc-upload/uploads/2020/03/21/sample_4_1723.png" style="height: 250px; width: 475px;" /></strong></p>

            <pre>
            <strong>输入：</strong>slices = [8,9,8,6,1,1]
            <strong>输出：</strong>16
            <strong>解释：</strong>两轮都选大小为 8 的披萨。如果你选择大小为 9 的披萨，你的朋友们就会选择大小为 8 的披萨，这种情况下你的总和不是最大的。
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>1 &lt;= slices.length &lt;= 500</code></li>
                <li><code>slices.length % 3 == 0</code></li>
                <li><code>1 &lt;= slices[i] &lt;= 1000</code></li>
            </ul>
        """
    },
    "power-of-four": {
        "title": "4的幂",
        "content": """
            <p>给定一个整数，写一个函数来判断它是否是 4 的幂次方。如果是，返回 <code>true</code> ；否则，返回 <code>false</code> 。</p>

            <p>整数 <code>n</code> 是 4 的幂次方需满足：存在整数 <code>x</code> 使得 <code>n == 4<sup>x</sup></code></p>

            <p>&nbsp;</p>

            <p><strong>示例 1：</strong></p>

            <pre>
            <strong>输入：</strong>n = 16
            <strong>输出：</strong>true
            </pre>

            <p><strong>示例 2：</strong></p>

            <pre>
            <strong>输入：</strong>n = 5
            <strong>输出：</strong>false
            </pre>

            <p><strong>示例 3：</strong></p>

            <pre>
            <strong>输入：</strong>n = 1
            <strong>输出：</strong>true
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>-2<sup>31</sup> &lt;= n &lt;= 2<sup>31</sup> - 1</code></li>
            </ul>

            <p>&nbsp;</p>

            <p><strong>进阶：</strong>你能不使用循环或者递归来完成本题吗？</p>
        """
    },
    "maximum-69-number": {
        "title": "6和9组成的最大数字",
        "content": """
            <p>给你一个仅由数字 6 和 9 组成的正整数&nbsp;<code>num</code>。</p>

            <p>你最多只能翻转一位数字，将 6 变成&nbsp;9，或者把&nbsp;9 变成&nbsp;6 。</p>

            <p>请返回你可以得到的最大数字。</p>

            <p>&nbsp;</p>

            <p><strong>示例 1：</strong></p>

            <pre><strong>输入：</strong>num = 9669
            <strong>输出：</strong>9969
            <strong>解释：</strong>
            改变第一位数字可以得到 6669 。
            改变第二位数字可以得到 9969 。
            改变第三位数字可以得到 9699 。
            改变第四位数字可以得到 9666 。
            其中最大的数字是 9969 。
            </pre>

            <p><strong>示例 2：</strong></p>

            <pre><strong>输入：</strong>num = 9996
            <strong>输出：</strong>9999
            <strong>解释：</strong>将最后一位从 6 变到 9，其结果 9999 是最大的数。</pre>

            <p><strong>示例 3：</strong></p>

            <pre><strong>输入：</strong>num = 9999
            <strong>输出：</strong>9999
            <strong>解释：</strong>无需改变就已经是最大的数字了。</pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>1 &lt;= num &lt;= 10^4</code></li>
                <li><code>num</code>&nbsp;每一位上的数字都是 6 或者&nbsp;9 。</li>
            </ul>
        """
    },
    "maximum-number-of-balloons": {
        "title": "气球的最大数量",
        "content": """
            <p>给你一个字符串&nbsp;<code>text</code>，你需要使用 <code>text</code> 中的字母来拼凑尽可能多的单词&nbsp;<strong>"balloon"（气球）</strong>。</p>

            <p>字符串&nbsp;<code>text</code> 中的每个字母最多只能被使用一次。请你返回最多可以拼凑出多少个单词&nbsp;<strong>"balloon"</strong>。</p>

            <p>&nbsp;</p>

            <p><strong class="example">示例 1：</strong></p>

            <p><strong><img alt="" src="https://assets.leetcode-cn.com/aliyun-lc-upload/uploads/2019/09/14/1536_ex1_upd.jpeg" style="height: 35px; width: 154px;" /></strong></p>

            <pre>
            <strong>输入：</strong>text = "nlaebolko"
            <strong>输出：</strong>1
            </pre>

            <p><strong class="example">示例 2：</strong></p>

            <p><strong><img alt="" src="https://assets.leetcode-cn.com/aliyun-lc-upload/uploads/2019/09/14/1536_ex2_upd.jpeg" style="height: 35px; width: 233px;" /></strong></p>

            <pre>
            <strong>输入：</strong>text = "loonbalxballpoon"
            <strong>输出：</strong>2
            </pre>

            <p><strong class="example">示例 3：</strong></p>

            <pre>
            <strong>输入：</strong>text = "leetcode"
            <strong>输出：</strong>0
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>1 &lt;= text.length &lt;= 10<sup>4</sup></code></li>
                <li><code>text</code>&nbsp;全部由小写英文字母组成</li>
            </ul>

            <p>&nbsp;</p>

            <p><strong>注意：</strong>本题与&nbsp;<a href="https://leetcode.cn/problems/rearrange-characters-to-make-target-string/">2287. 重排字符形成目标字符串</a>&nbsp;相同。</p>
        """
    },
    "que-shi-de-shu-zi-lcof": {
        "title": "0～n-1中缺失的数字",
        "content": """
            <p>一个长度为n-1的递增排序数组中的所有数字都是唯一的，并且每个数字都在范围0～n-1之内。在范围0～n-1内的n个数字中有且只有一个数字不在该数组中，请找出这个数字。</p>

            <p>&nbsp;</p>

            <p><strong>示例 1:</strong></p>

            <pre><strong>输入:</strong> [0,1,3]
            <strong>输出:</strong> 2
            </pre>

            <p><strong>示例&nbsp;2:</strong></p>

            <pre><strong>输入:</strong> [0,1,2,3,4,5,6,7,9]
            <strong>输出:</strong> 8</pre>

            <p>&nbsp;</p>

            <p><strong>限制：</strong></p>

            <p><code>1 &lt;= 数组长度 &lt;= 10000</code></p>
        """
    },
    "01-matrix": {
        "title": "01矩阵",
        "content": """
            <p>给定一个由 <code>0</code> 和 <code>1</code> 组成的矩阵 <code>mat</code>&nbsp;，请输出一个大小相同的矩阵，其中每一个格子是 <code>mat</code> 中对应位置元素到最近的 <code>0</code> 的距离。</p>

            <p>两个相邻元素间的距离为 <code>1</code> 。</p>

            <p>&nbsp;</p>

            <p><b>示例 1：</b></p>

            <p><img alt="" src="https://pic.leetcode-cn.com/1626667201-NCWmuP-image.png" style="width: 150px; " /></p>

            <pre>
            <strong>输入：</strong>mat =<strong> </strong>[[0,0,0],[0,1,0],[0,0,0]]
            <strong>输出：</strong>[[0,0,0],[0,1,0],[0,0,0]]
            </pre>

            <p><b>示例 2：</b></p>

            <p><img alt="" src="https://pic.leetcode-cn.com/1626667205-xFxIeK-image.png" style="width: 150px; " /></p>

            <pre>
            <strong>输入：</strong>mat =<b> </b>[[0,0,0],[0,1,0],[1,1,1]]
            <strong>输出：</strong>[[0,0,0],[0,1,0],[1,2,1]]
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>m == mat.length</code></li>
                <li><code>n == mat[i].length</code></li>
                <li><code>1 &lt;= m, n &lt;= 10<sup>4</sup></code></li>
                <li><code>1 &lt;= m * n &lt;= 10<sup>4</sup></code></li>
                <li><code>mat[i][j] is either 0 or 1.</code></li>
                <li><code>mat</code> 中至少有一个 <code>0&nbsp;</code></li>
            </ul>

            <p>&nbsp;</p>

            <p><meta charset="UTF-8" />注意：本题与主站 542&nbsp;题相同：<a href="https://leetcode-cn.com/problems/01-matrix/">https://leetcode-cn.com/problems/01-matrix/</a></p>
        """
    },
    "1-bit-and-2-bit-characters": {
        "title": "1比特与2比特字符",
        "content": """
            <p>有两种特殊字符：</p>

            <ul>
                <li>第一种字符可以用一比特&nbsp;<code>0</code> 表示</li>
                <li>第二种字符可以用两比特（<code>10</code>&nbsp;或&nbsp;<code>11</code>）表示</li>
            </ul>

            <p>给你一个以 <code>0</code> 结尾的二进制数组&nbsp;<code>bits</code>&nbsp;，如果最后一个字符必须是一个一比特字符，则返回 <code>true</code> 。</p>

            <p>&nbsp;</p>

            <p><strong>示例&nbsp;1:</strong></p>

            <pre>
            <strong>输入:</strong> bits = [1, 0, 0]
            <strong>输出:</strong> true
            <strong>解释:</strong> 唯一的解码方式是将其解析为一个两比特字符和一个一比特字符。
            所以最后一个字符是一比特字符。
            </pre>

            <p><strong>示例&nbsp;2:</strong></p>

            <pre>
            <strong>输入：</strong>bits = [1,1,1,0]
            <strong>输出：</strong>false
            <strong>解释：</strong>唯一的解码方式是将其解析为两比特字符和两比特字符。
            所以最后一个字符不是一比特字符。
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示:</strong></p>

            <ul>
                <li><code>1 &lt;= bits.length &lt;= 1000</code></li>
                <li><code>bits[i]</code> 为 <code>0</code> 或 <code>1</code></li>
            </ul>
        """
    },
    "1nzheng-shu-zhong-1chu-xian-de-ci-shu-lcof": {
        "title": "1～n整数中1出现的次数",
        "content": """
            <p>输入一个整数 <code>n</code> ，求1～n这n个整数的十进制表示中1出现的次数。</p>

            <p>例如，输入12，1～12这些整数中包含1 的数字有1、10、11和12，1一共出现了5次。</p>

            <p>&nbsp;</p>

            <p><strong>示例 1：</strong></p>

            <pre>
            <strong>输入：</strong>n = 12
            <strong>输出：</strong>5
            </pre>

            <p><strong>示例 2：</strong></p>

            <pre>
            <strong>输入：</strong>n = 13
            <strong>输出：</strong>6</pre>

            <p>&nbsp;</p>

            <p><strong>限制：</strong></p>

            <ul>
                <li><code>1 &lt;= n &lt;&nbsp;2^31</code></li>
            </ul>

            <p>注意：本题与主站 233 题相同：<a href="https://leetcode-cn.com/problems/number-of-digit-one/">https://leetcode-cn.com/problems/number-of-digit-one/</a></p>
        """
    },
    "power-of-two": {
        "title": "2的幂",
        "content": """
            <p>给你一个整数 <code>n</code>，请你判断该整数是否是 2 的幂次方。如果是，返回 <code>true</code> ；否则，返回 <code>false</code> 。</p>

            <p>如果存在一个整数 <code>x</code> 使得&nbsp;<code>n == 2<sup>x</sup></code> ，则认为 <code>n</code> 是 2 的幂次方。</p>

            <p>&nbsp;</p>

            <p><strong>示例 1：</strong></p>

            <pre>
            <strong>输入：</strong>n = 1
            <strong>输出：</strong>true
            <strong>解释：</strong>2<sup>0</sup> = 1
            </pre>

            <p><strong>示例 2：</strong></p>

            <pre>
            <strong>输入：</strong>n = 16
            <strong>输出：</strong>true
            <strong>解释：</strong>2<sup>4</sup> = 16
            </pre>

            <p><strong>示例 3：</strong></p>

            <pre>
            <strong>输入：</strong>n = 3
            <strong>输出：</strong>false
            </pre>

            <p>&nbsp;</p>

            <p><strong>提示：</strong></p>

            <ul>
                <li><code>-2<sup>31</sup> &lt;= n &lt;= 2<sup>31</sup> - 1</code></li>
            </ul>

            <p>&nbsp;</p>

            <p><strong>进阶：</strong>你能够不使用循环/递归解决此问题吗？</p>
        """
    }
}