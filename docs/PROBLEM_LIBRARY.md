# 题库与分类

内置60道项目自编教学题，采用经典算法知识；不宣称算法原创。
现有三道演示题保留，当前为63题、369个用例。新题含30道简单、24道中等、6道困难。
题面、参考程序及验证脚本由AI辅助编写；预期答案与参考实现分开构造，并经过程序校验。参赛材料应据实记录这一创作过程。
每道新题有2组公开示例和4组隐藏验证，覆盖零值、单元素、重复值、负数、空串或无解等适用分支。
这些用例用于功能验证，不代表穷尽全部输入或严格证明算法正确。

| 分类ID | 分类名称 | 新增题数 |
|---|---|---|
| basics | 输入输出与基础运算 | 6 |
| control | 分支与循环 | 6 |
| arrays | 数组与哈希 | 6 |
| strings | 字符串处理 | 6 |
| search | 排序与二分查找 | 6 |
| windows | 双指针与滑动窗口 | 6 |
| stacks | 栈与队列 | 6 |
| recursion | 递归与回溯 | 6 |
| graphs | 树与图基础 | 6 |
| dp | 动态规划 | 6 |
| uncategorized | 未分类（旧题默认） | 0 |

## 运行与更新

先备份已有数据库，再升级：

```cmd
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\.venv\Scripts\python.exe -m flask --app app seed-library
```

`seed-library`只插入不存在的题号，重复执行不会覆盖管理员编辑、已有用例或提交。
公开API只返回题面、分类、标签和当前用户状态，不返回隐藏用例或参考程序。
题库页面按分类、难度、个人状态筛选，支持题号/标题搜索，每页12题。
“尝试未通过”指存在提交但尚未通过；练习状态不能证明掌握程度。
进入练习会保留筛选条件，并在当前浏览器会话保存题单；上下题沿此题单，返回时保留筛选页码。

旧库如果已经由 `create_all()` 建表、却没有迁移版本，不要直接盲目 stamp。
应先备份并核对实际数据库结构，再选择匹配的迁移版本。

## 内容维护

- `data/problem_library.json`：题面、分类、来源、公开/隐藏用例。
- `data/reference_solutions.json`：私有验证用Python参考程序，不放在static目录，也不通过题目API返回。
- `scripts/build_problem_library.py`：可复现的题目与答案生成器。小规模独立求解器生成预期答案，参考程序另行核对。
- 管理页可修改分类、标签及来源，更新JSON用例时保留输入空白字符。
- HTML导入可增加 `.category`、`.tags`、`.source` 元素。分类填固定ID，标签逗号分隔；省略元信息会保留旧值，新题默认为未分类。
- `<pre class="input">` 内输入按原样保留；不要为排版添加多余换行或缩进。空行输入用真实换行表示。

重新生成内容文件（不会修改数据库）：

```cmd
.\.venv\Scripts\python.exe scripts\build_problem_library.py
```

Docker及执行镜像就绪时，可复查全部360个用例：

```cmd
.\.venv\Scripts\python.exe scripts\verify_problem_library.py
```

验证结果以当前运行输出为准。
原用户、原题与原提交不用于创建测试记录。接口测试使用独立内存数据库。
