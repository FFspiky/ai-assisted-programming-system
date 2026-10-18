"""Shared taxonomy and validation for public browsing, editing and imports."""

CATEGORIES = {
    "basics": "输入输出与基础运算",
    "control": "分支与循环",
    "arrays": "数组与哈希",
    "strings": "字符串处理",
    "search": "排序与二分查找",
    "windows": "双指针与滑动窗口",
    "stacks": "栈与队列",
    "recursion": "递归与回溯",
    "graphs": "树与图基础",
    "dp": "动态规划",
    "uncategorized": "未分类",
}


def validate_metadata(category, tags, source):
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError("请选择有效的题目分类")
    if (
        not isinstance(tags, list)
        or len(tags) > 8
        or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 24 for t in tags)
    ):
        raise ValueError("知识点标签须为列表，最多8个，每个1至24字")
    if not isinstance(source, str) or len(source) > 200:
        raise ValueError("来源说明须为不超过200字的文本")
    return category, list(dict.fromkeys(t.strip() for t in tags)), source.strip()
