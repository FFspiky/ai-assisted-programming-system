    const questions = [
{ type: 'radio', question: '1. 您的编程经验时长：', options: ['0-6个月', '6-12个月', '1-3年', '3年以上'] },
{ type: 'radio', question: '2. 您最熟悉的编程语言：', options: ['Python', 'C/C++', 'Go', 'Rust'] },
{ type: 'radio', question: '3. 您使用哪种编程编辑器最频繁？', options: ['VS Code', 'IntelliJ IDEA', 'PyCharm', 'Vim/Neovim', 'Sublime Text', '其他'] },
{ type: 'radio', question: '4. 您是否使用过版本控制系统（如Git）？', options: ['从未用过', '了解基本命令', '熟练使用分支管理', '有团队协作经验'] },
{ type: 'radio', question: '5. 您对数组(Array)的掌握程度：', options: ['不了解', '了解基本概念', '能实现基本操作', '能解决实际问题'] },
{ type: 'radio', question: '6. 您对哈希表(HashMap/Dictionary)的掌握程度：', options: ['不了解', '了解基本概念', '能实现基本操作', '能解决实际问题'] },
{ type: 'radio', question: '7. 您对树(Tree)结构的掌握程度：', options: ['不了解', '了解基本概念', '能实现基本操作', '能解决实际问题'] },
{ type: 'radio', question: '8. 您对图(Graph)结构的掌握程度：', options: ['不了解', '了解基本概念', '能实现基本操作', '能解决实际问题'] },
{ type: 'radio', question: '9. 您对排序算法的掌握程度：', options: ['不了解', '了解基本概念', '能实现基础算法', '能应用解决实际问题'] },
{ type: 'radio', question: '10. 您对搜索算法的掌握程度：', options: ['不了解', '了解基本概念', '能实现基础算法', '能应用解决实际问题'] },
{ type: 'radio', question: '11. 您对动态规划(DP)的掌握程度：', options: ['不了解', '了解基本概念', '能实现简单DP', '能解决较复杂问题'] },
{ type: 'radio', question: '12. 您对递归算法的掌握程度：', options: ['不了解', '了解基本概念', '能实现简单递归', '能解决复杂递归问题'] },
{ type: 'radio', question: '13. 您解决过最复杂的LeetCode问题是哪个难度级别？', options: ['未尝试过', '简单级别', '中等难度', '困难级别'] },
{ type: 'checkbox', question: '14. 您熟悉哪些编程范型？（多选）', options: ['面向对象', '函数式编程', '响应式编程', '面向切面', '并发编程'] },
{ type: 'checkbox', question: '15. 您最想提升哪些方面的技能？（多选）', options: ['算法能力', '系统设计', '项目架构', '数据库设计', 'API开发', '前端框架', '后端框架', '云服务部署'] },
{ type: 'radio', question: '16. 您参与开发的项目规模：', options: ['无项目经验', '小项目（<1000行代码）', '中型项目（1000-5000行）', '大型项目（5000+行）'] },
{ type: 'radio', question: '17. 您在团队中通常是：', options: ['独立开发者', '功能模块实现者', '架构设计者', '技术负责人'] },
{ type: 'radio', question: '18. 您使用测试框架的经验：', options: ['未编写过测试', '写过简单单元测试', '能进行TDD开发', '具有集成测试经验'] },
{ type: 'radio', question: '19. 您每天能够投入编程学习的时间：', options: ['<1小时', '1-2小时', '2-3小时', '>3小时'] },
{ type: 'checkbox', question: '20. 您的学习目标是：（多选）', options: ['提升求职竞争力', '从事专业开发', '参与开源项目', '开发个人项目', '解决工作问题'] }
    ];

    let currentQuestion = 0;
    const userAnswers = Array(questions.length).fill(null);

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text || '').replace(/[&<>"']/g, function (m) { return map[m]; });
}

function sanitizeRenderedHtml(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    template.content.querySelectorAll('script, iframe, object, embed, style').forEach(node => node.remove());
    template.content.querySelectorAll('*').forEach(node => {
        [...node.attributes].forEach(attr => {
            const attrName = attr.name.toLowerCase();
            const attrValue = attr.value.trim().toLowerCase();
            if (attrName.startsWith('on') || attrValue.startsWith('javascript:')) {
                node.removeAttribute(attr.name);
            }
        });
    });
    return template.innerHTML;
}

function renderMarkdownSafe(markdown) {
    return sanitizeRenderedHtml(marked.parse(markdown || ''));
}

    function initAssessment() {
renderQuestion(currentQuestion);
document.getElementById('prevBtn').addEventListener('click', goToPrevious);
document.getElementById('nextBtn').addEventListener('click', goToNext);
document.getElementById('submitBtn').addEventListener('click', submitAssessment);
// 修正：直接传递 event 对象
document.getElementById('questionContainer').addEventListener('click', handleOptionSelect);
    }

    function renderQuestion(index) {
const question = questions[index];
const container = document.getElementById('questionContainer');
let optionsHTML = question.options.map(option => {
    let isSelected = (question.type === 'radio')
        ? (userAnswers[index] === option)
        : (userAnswers[index] && userAnswers[index].includes(option));
    return `<button type="button" class="option-btn ${isSelected ? 'selected' : ''}" data-value="${option}">${option}</button>`;
}).join('');

container.innerHTML = `<div class="question-content"><h4>${question.question}</h4><div class="options">${optionsHTML}</div></div>`;
document.getElementById('questionCount').textContent = `${index + 1}/${questions.length}`;
const progressBar = document.getElementById('progressBar');
if (progressBar) {
    progressBar.style.width = `${((index + 1) / questions.length) * 100}%`;
}
document.getElementById('prevBtn').disabled = index === 0;
document.getElementById('nextBtn').style.display = index < questions.length - 1 ? 'inline-flex' : 'none';
document.getElementById('submitBtn').style.display = index === questions.length - 1 ? 'inline-flex' : 'none';
    }

    // 修正：使用 event.target.closest()
    function handleOptionSelect(event) {
const optionElement = event.target.closest('.option-btn');
if (!optionElement) return;

const question = questions[currentQuestion];
const optionValue = optionElement.dataset.value;

if (question.type === 'radio') {
    document.querySelectorAll(`#questionContainer .option-btn`).forEach(btn => btn.classList.remove('selected'));
    optionElement.classList.add('selected');
    userAnswers[currentQuestion] = optionValue;
    if (currentQuestion < questions.length - 1) setTimeout(goToNext, 300);
} else {
    optionElement.classList.toggle('selected');
    if (!userAnswers[currentQuestion]) userAnswers[currentQuestion] = [];
    const idx = userAnswers[currentQuestion].indexOf(optionValue);
    if (idx > -1) {
        userAnswers[currentQuestion].splice(idx, 1);
    } else {
        userAnswers[currentQuestion].push(optionValue);
    }
}
    }

    function validateCurrentAnswer() {
const answer = userAnswers[currentQuestion];
return answer !== null && (Array.isArray(answer) ? answer.length > 0 : true);
    }

    function goToPrevious() {
if (currentQuestion > 0) renderQuestion(--currentQuestion);
    }

    function goToNext() {
if (validateCurrentAnswer()) {
    if (currentQuestion < questions.length - 1) renderQuestion(++currentQuestion);
} else alert('请完成当前题目');
    }


    // learn-analytics.html

async function submitAssessment() {
    if (!validateCurrentAnswer()) {
alert('请在提交前完成当前题目'); // 使用 alert 或更美观的提示
return;
    }

    const loadingElement = document.getElementById('assessmentLoading');
    const preview = document.getElementById('pathPreview');
    const pathContent = document.getElementById('pathContent');

    // 准备UI
    document.getElementById('assessmentForm').style.display = 'none'; // 隐藏问卷
    preview.style.display = 'block';
    loadingElement.style.display = 'block'; // 先显示加载动画
    pathContent.style.display = 'none';  // 隐藏旧内容
    pathContent.innerHTML = ''; // 清空之前的内容

    // --- 修改开始：替换整个 try...catch 块 ---
    try {
const response = await fetch('/api/assess-learning-path', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ answers: userAnswers })
});

if (!response.ok) {
    throw new Error(`服务器响应错误: ${response.status} ${response.statusText}`);
}

// 收到响应后，隐藏加载动画，显示内容容器
loadingElement.style.display = 'none';
pathContent.style.display = 'block';

const reader = response.body.getReader();
const decoder = new TextDecoder('utf-8');
let buffer = '';
let fullText = '';

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // 将接收到的数据块解码并添加到缓冲区
    buffer += decoder.decode(value, { stream: true });
    // 按换行符分割，处理完整的行
    const lines = buffer.split('\n');
    buffer = lines.pop(); // 最后一行可能不完整，放回缓冲区等待下次处理

    for (const line of lines) {
        // 检查是否是有效的 SSE 数据行
        if (line.startsWith('data: ')) {
            const jsonStr = line.substring(6).trim();
            if (jsonStr) {
                try {
                    const data = JSON.parse(jsonStr);
                    // 处理内容数据
                    if (data.content) {
                        fullText += data.content;
                        // 使用 marked.parse (这依然是必要的)
                        pathContent.innerHTML = renderMarkdownSafe(fullText);
                        pathContent.scrollTop = pathContent.scrollHeight; // 自动滚到底部
                    }
                    // 处理错误数据
                    if (data.error) {
                        pathContent.innerHTML = `<div class="error-message">生成学习路径时出错: ${escapeHtml(data.error)}</div>`;
                        console.error("Stream Error:", data.error);
                        return; // 收到错误后停止处理
                    }
                } catch (e) {
                    console.error('解析JSON数据流时出错:', e, '收到的数据:', jsonStr);
                }
            }
        }
    }
}
    } catch (error) {
console.error('获取学习路径失败:', error);
loadingElement.style.display = 'none'; // 隐藏加载
pathContent.style.display = 'block'; // 显示内容区
pathContent.innerHTML = `<div class="error-message">请求失败: ${escapeHtml(error.message)}。请检查网络连接或联系管理员。</div>`;
    }
    // --- 修改结束 ---
}
    // --- 页面加载的完整逻辑 (已修正) ---
    document.addEventListener('DOMContentLoaded', function() {
initAssessment();
UserSession.init({
    showRecords: true,
    onRecordsClick: function () {
        window.location.href = '/practice.html';
    },
    onAuthenticated: function () {
        fetchLearningOverview();
        fetchAiAnalysisStream();
    },
    onGuest: showGuestAnalysisState
});
fetchLeaderboard();
    });

    function showGuestAnalysisState() {
document.getElementById('totalSolved').textContent = '-';
document.getElementById('accuracyRate').textContent = '-';
document.getElementById('learningHours').textContent = '-';
document.getElementById('aiAnalysisContainer').innerHTML = `
    <div class="card-body" style="text-align:center;">
        <p>请<a href="/login.html" style="color:var(--primary)">登录</a>后查看您的学习数据和AI分析。</p>
    </div>`;
    }

    async function fetchLearningOverview() {
try {
    const response = await fetch('/api/learning_overview');
    const result = await response.json();
    if (result.success) {
        document.getElementById('totalSolved').textContent = result.data.total_solved;
        document.getElementById('learningHours').textContent = result.data.learning_hours + 'h';
        document.getElementById('accuracyRate').textContent = result.data.accuracy + '%';
    }
} catch (error) {
    console.error('获取学习概览失败:', error);
}
    }

    async function fetchLeaderboard() {
const container = document.getElementById('leaderboardContainer');
try {
    const response = await fetch('/api/leaderboard');
    const result = await response.json();
    if (result.success && result.data.length > 0) {
        let tableHTML = '<table class="leaderboard-table"><thead><tr><th>排名</th><th>用户</th><th>解题数</th><th>学习时长 (h)</th></tr></thead><tbody>';
        result.data.forEach(user => {
            tableHTML += `
                <tr>
                    <td class="rank">${escapeHtml(user.rank)}</td>
                    <td class="username">${escapeHtml(user.username)}</td>
                    <td>${escapeHtml(user.solved_count)}</td>
                    <td>${escapeHtml(user.learning_hours)}</td>
                </tr>
            `;
        });
        tableHTML += '</tbody></table>';
        container.innerHTML = tableHTML;
    } else {
        container.innerHTML = '<p style="text-align:center; color:var(--gray);">英雄榜正在等待第一位英雄的诞生！</p>';
    }
} catch (error) {
    container.innerHTML = `<p class="error-message">网络错误: ${escapeHtml(error.message)}</p>`;
}
    }

    async function fetchAiAnalysisStream() {
const container = document.getElementById('aiAnalysisContainer');
container.innerHTML = `<div class="card-body path-content" id="ai-stream-content"></div>`;
const contentDiv = document.getElementById('ai-stream-content');

try {
    const response = await fetch('/api/ai_learning_analysis_stream');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const jsonStr = line.substring(6);
                if (!jsonStr) continue;

                try {
                    const data = JSON.parse(jsonStr);
                    if(data.content) {
                        fullContent += data.content;
                        contentDiv.innerHTML = renderMarkdownSafe(fullContent);
                        contentDiv.scrollTop = contentDiv.scrollHeight;
                    }
                    if(data.error) {
                        contentDiv.innerHTML = `<p class="error-message">${escapeHtml(data.error)}</p>`;
                        return;
                    }
                } catch(e) {
                    // 忽略JSON解析错误
                }
            }
        }
    }
} catch (error) {
    contentDiv.innerHTML = `<p class="error-message">请求AI分析时发生错误: ${escapeHtml(error.message)}</p>`;
}
    }
