import requests
import re
from config import API_KEY, API_URL, MODEL_NAME

def check_code(code: str, language: str):
    if not API_KEY:
        return {
            "success": False,
            "error": "未配置 SILICONFLOW_API_KEY（可在 .env 或环境变量中设置）",
        }

    full_prompt = f"""
你是一位经验丰富的编程助教，请帮助我分析并优化以下 {language} 代码：

{code}

请严格按照以下结构和格式自然语言回答：

1. **代码错误检查**：
   - 如果代码中存在语法或逻辑错误，请逐条指出，并解释每个错误的原因和给出相应的修正建议。
   - 如果代码中没有语法或逻辑错误，则简单用一句话略过。

2. **代码优化建议 (多版本)**：
    **重要提示：即使代码存在错误，也请你独立考虑并提供多版本代码优化建议。**
   - 请提供**至少 3 个不同版本**的优化代码，每个版本都应解决代码可读性、性能、风格或结构上的改进点。
   - 对于每个优化版本，请先用简短的中文描述其主要优化点或适用场景（**严格按照：#### 版本1：优化点概述...**），然后紧接着提供对应的完整代码片段。
   - 每个代码片段请务必使用 Markdown 格式（**严格使用三反引号，并确保开始和结束反引号在新的一行：\n```python\n# 你的优化代码\n```\n**）。

3. **整体评价**：
   - 对原始代码的整体结构、风格、效率进行总结评价。

请使用自然、清晰的中文输出，并合理自然分段，让初学者容易理解。
"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"你是一名擅长教学和编程指导的助理"},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.5, # 可以根据需要调整
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=10000
        )
        response.raise_for_status()
        ai_response_content = response.json()["choices"][0]["message"]["content"]
        
        ##print("--- 原始AI响应内容开始 ---")
        #print(ai_response_content)
        #print("--- 原始AI响应内容结束 ---")

        overall_feedback = ""
        optimized_versions = []

        # 定义更灵活的模式，匹配AI可能返回的各种标题格式：无Markdown、**加粗**、### 标题等
        # 匹配 `X.` 或 `### X. **Title**` 或 `X. Title`
        pattern_section1 = r"^(?:###\s*)?\s*1\.\s*(?:\*\*代码错误检查\*\*|代码错误检查)\s*[:：.]*\s*$"
        pattern_section2 = r"^(?:###\s*)?\s*2\.\s*(?:\*\*代码优化建议 \(多版本\)\*\*|代码优化建议 \(多版本\))\s*[:：.]*\s*$"
        pattern_section3 = r"^(?:###\s*)?\s*3\.\s*(?:\*\*整体评价\*\*|整体评价)\s*[:：.]*\s*$"
        
        # 查找所有主要部分的起始点
        match1 = re.search(pattern_section1, ai_response_content, re.MULTILINE | re.IGNORECASE)
        match2 = re.search(pattern_section2, ai_response_content, re.MULTILINE | re.IGNORECASE)
        match3 = re.search(pattern_section3, ai_response_content, re.MULTILINE | re.IGNORECASE)

        # 存储每个部分的起始和结束索引，以及内容
        section_data = {
            "1": {"start_match": match1, "content": ""},
            "2": {"start_match": match2, "content": ""},
            "3": {"start_match": match3, "content": ""},
        }

        # 构建一个有序的起始索引列表
        sorted_start_indices = []
        for key, data in section_data.items():
            if data["start_match"]:
                sorted_start_indices.append((data["start_match"].start(), key, data["start_match"].end()))
        
        sorted_start_indices.sort() # 按起始位置排序

        # 提取每个部分的内容
        for i, (start_full_idx, key, content_start_idx) in enumerate(sorted_start_indices):
            end_idx = len(ai_response_content) # 默认到字符串末尾

            if i + 1 < len(sorted_start_indices):
                # 如果不是最后一个部分，则结束位置是下一个部分的完整起始位置
                end_idx = sorted_start_indices[i+1][0]
            
            # 提取内容，从标题的实际内容开始处到结束位置
            section_content_raw = ai_response_content[content_start_idx:end_idx].strip()
            section_data[key]["content"] = section_content_raw

        # 构建 overall_feedback (代码错误检查 + 整体评价)，并移除序号
        overall_feedback_parts = []
        if section_data["1"]["content"]:
            # 重新加上 H3 标题格式，以便前端正确渲染，移除序号，但保留加粗
            overall_feedback_parts.append("### **代码错误检查**\n" + section_data["1"]["content"])
        if section_data["3"]["content"]:
            overall_feedback_parts.append("### **整体评价**\n" + section_data["3"]["content"])
        overall_feedback = "\n\n".join(overall_feedback_parts).strip()


        # 提取优化版本 (从代码优化建议部分)
        optimization_section_text = section_data["2"]["content"]
        
        if optimization_section_text:
            # 改进 version_pattern，使其能够匹配 '#### 版本X：' 这样的前缀，或者只是 '版本X：'
            # 同时对代码块的开始和结束反引号以及中间的空白字符做最大程度的容忍
            version_pattern = re.compile(
                r'(^####\s*版本\d+[:：].*?)\s*' # Version title: e.g., "#### 版本1："
                r'(?:优化点概述[:：].*?)?\s*'   # Optional "优化点概述："
                r'(?:代码实现[:：].*?)?\s*'     # Optional "代码实现："
                r'(`{1,3}[a-zA-Z]*[\s\S]*?)'   # Captures opening backticks and anything until the code
                r'([\s\S]*?)'                 # Captures the actual code content (non-greedy)
                r'([\r\n]*`{1,3})',            # Captures closing backticks with optional preceding newlines
                re.MULTILINE | re.DOTALL
            )
            
            matches = version_pattern.findall(optimization_section_text)

            if matches:
                for match_tuple in matches:
                    description_with_markdown = match_tuple[0].strip() # This will contain "#### 版本X: ..."
                    # The parts of the match_tuple are now:
                    # 0: version_title (e.g., "#### 版本1：...")
                    # 1: opening_backticks_and_stuff (e.g., "```python\n")
                    # 2: code_content
                    # 3: closing_backticks_and_stuff (e.g., "\n```")

                    code_content = match_tuple[2].strip()

                    # 移除描述中的 '#### ' Markdown 标题前缀
                    description = re.sub(r'^#+\s*', '', description_with_markdown).strip()

                    optimized_versions.append({
                        "description": description,
                        "code": code_content
                    })
            else:
                # Fallback if no specific versions are parsed but the section exists
                optimized_versions.append({
                    "description": "AI已提供优化建议，但未能解析到具体优化代码版本，请检查AI返回格式。",
                    "code": ""
                })
        elif section_data["2"]["start_match"]: # 如果找到了 Section 2 的标题，但内容为空
             optimized_versions.append({
                "description": "AI已提供优化建议，但未能解析到具体优化代码版本。",
                "code": ""
            })

        # 最终回退：如果没有任何内容被解析到，将整个原始AI响应作为feedback
        if not overall_feedback and not optimized_versions and ai_response_content.strip():
             overall_feedback = "AI返回内容格式不符或未能解析。原始AI响应：\n" + ai_response_content.strip()
             optimized_versions.append({
                "description": "未能解析到任何优化版本。",
                "code": ""
            })
        elif not optimized_versions and overall_feedback:
            # 如果有反馈（section 1或3），但没有优化版本（section 2），也添加一个提示
            optimized_versions.append({
                "description": "AI已提供反馈，但未能解析到具体优化代码版本。",
                "code": ""
            })


        return {
            "success": True,
            "feedback": overall_feedback,
            "optimizedVersions": optimized_versions
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "AI服务响应超时"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"AI服务请求失败: {str(e)}"}
    except Exception as e:
        print(f"AI响应解析过程中发生错误: {e}") # 打印详细的解析错误到后端日志
        return {"success": False, "error": f"AI响应解析失败: {str(e)}"}
