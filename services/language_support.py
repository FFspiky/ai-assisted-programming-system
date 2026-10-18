"""Shared language identities and the standard-input contract used by all editors."""

LANGUAGE_IDS = ("python", "cpp", "java")

_SPECS = {
    "python": {
        "id": "python",
        "label": "Python",
        "version": "Python 3.11",
        "filename": "solution.py",
        "entrypoint": "脚本顶层；使用 input() 或 sys.stdin 读取标准输入",
        "starter_code": "import sys\n\n\ndef main():\n    data = sys.stdin.read()\n    # 按题面解析 data，并将答案写到标准输出。\n    print(data.strip())\n\n\nif __name__ == '__main__':\n    main()\n",
    },
    "cpp": {
        "id": "cpp",
        "label": "C++",
        "version": "C++17",
        "filename": "main.cpp",
        "entrypoint": "int main()；使用 std::cin/std::cout 读写标准输入输出",
        "starter_code": "#include <iostream>\n#include <string>\n\nint main() {\n    std::ios::sync_with_stdio(false);\n    std::cin.tie(nullptr);\n    std::string line;\n    // 按题面解析输入，并将答案写到标准输出。\n    while (std::getline(std::cin, line)) {\n        std::cout << line << '\\n';\n    }\n    return 0;\n}\n",
    },
    "java": {
        "id": "java",
        "label": "Java",
        "version": "Java 17",
        "filename": "Main.java",
        "entrypoint": "public class Main；public static void main(String[] args)，不声明 package",
        "starter_code": "import java.io.BufferedReader;\nimport java.io.InputStreamReader;\nimport java.nio.charset.StandardCharsets;\n\npublic class Main {\n    public static void main(String[] args) throws Exception {\n        BufferedReader reader = new BufferedReader(\n            new InputStreamReader(System.in, StandardCharsets.UTF_8));\n        StringBuilder output = new StringBuilder();\n        String line;\n        // 按题面解析输入，并将答案写到标准输出。\n        while ((line = reader.readLine()) != null) {\n            output.append(line).append('\\n');\n        }\n        System.out.print(output);\n    }\n}\n",
    },
}


def normalize_language(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().lower()
    return {
        "c++": "cpp",
        "py": "python",
        "python3": "python",
        "java17": "java",
        "jdk17": "java",
    }.get(value, value)


def language_spec(language):
    """Return a copy so a caller cannot accidentally alter global metadata."""
    normalized = normalize_language(language)
    if normalized not in _SPECS:
        raise ValueError("不支持的编程语言")
    return dict(_SPECS[normalized])


def language_label(language):
    return language_spec(language)["label"]


def starter_code(language):
    return language_spec(language)["starter_code"]


def language_options(enabled=None):
    allowed = set(LANGUAGE_IDS if enabled is None else map(normalize_language, enabled))
    return [language_spec(language) for language in LANGUAGE_IDS if language in allowed]


def language_prompt(language):
    spec = language_spec(language)
    return (
        f"\n本次代码语言为 {spec['version']}，不得擅自改成其他语言。"
        f"源文件约定：{spec['filename']}；标准程序入口：{spec['entrypoint']}。"
        "完整刷题程序使用标准输入/标准输出，不输出交互提示，不依赖网络、图形界面或第三方库。"
        "题面或模块若明确给出函数合同，优先遵守该函数签名及输入输出约定。"
        "局部补全或局部修改仅输出请求的片段，不补写无关入口；完整参考才提供可运行入口。"
    )
