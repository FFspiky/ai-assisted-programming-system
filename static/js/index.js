// 页面加载时检查用户登录状态
    document.addEventListener('DOMContentLoaded', async function() {
try {
    const response = await fetch('/api/current_user'); // 使用了 supports_credentials
    if (response.ok) {
        const result = await response.json();
        if (result.success) {
            updateUserInfo(result.user);
        } else {
            showLoginRegister();
        }
    } else {
        showLoginRegister();
    }
} catch (error) {
    console.error('获取用户信息失败', error);
    showLoginRegister();
}
    });

    function updateUserInfo(user) {
       document.querySelector('.username').textContent = user.username;
const userStats = document.querySelector('.user-stats');

// 修改此区域，添加一个登出链接
userStats.innerHTML = `
    <span id="showRecords">刷题记录</span>
    <span>积分: ${user.points}</span>
    <a href="#" id="logoutBtn" style="color: #f72585; cursor: pointer; margin-left: 15px; text-decoration: none;">登出</a>
`;

// 由于 innerHTML 被重写，需要为“刷题记录”重新绑定事件
document.getElementById('showRecords').addEventListener('click', openRecordModal);

// 为新创建的“登出”按钮添加事件监听
document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    }

    async function handleLogout(e) {
e.preventDefault(); // 阻止链接的默认跳转行为
const response = await fetch('/api/logout', {
    method: 'POST'
});
const result = await response.json();

if (result.success) {
    alert("已成功登出");
    window.location.reload(); // 刷新页面以更新UI状态
} else {
    alert("登出失败，请稍后重试");
}
    }


    function showLoginRegister() {
const userInfo = document.querySelector('.user-info');
// 此处的class与您原有的login/register按钮样式可能不同，请根据需要调整
userInfo.innerHTML = `
    <div style="display: flex; gap: 10px;">
        <a href="/login.html" class="btn">登录</a>
        <a href="/register.html" class="btn" style="background: var(--primary);">注册</a>
    </div>
`;
    }

// 页面切换功能
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', function (e) {
        e.preventDefault();
        const targetPage = this.getAttribute('data-page');

        // 隐藏所有页面
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });

        // 显示目标页面
        document.getElementById(targetPage).classList.add('active');
    });
});

// 开始刷题按钮
document.getElementById('start-practice').addEventListener('click', function () {
    // 隐藏首页，显示刷题页面
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById('problem-page').classList.add('active');
});

// 继续刷题按钮
document.getElementById('continue-practice').addEventListener('click', function () {
    // 隐藏首页，显示刷题页面
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById('problem-page').classList.add('active');
});

// 刷题记录功能
const recordModal = document.getElementById('recordModal');
const showRecords = document.getElementById('showRecords');
const userAvatar = document.getElementById('userAvatar');
const closeModal = document.getElementById('closeModal');

// 显示刷题记录弹窗
function openRecordModal() {
    recordModal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

// 关闭刷题记录弹窗
function closeRecordModal() {
    recordModal.classList.remove('active');
    document.body.style.overflow = 'auto';
}

// 添加事件监听
showRecords.addEventListener('click', openRecordModal);
userAvatar.addEventListener('click', openRecordModal);
closeModal.addEventListener('click', closeRecordModal);

// 点击弹窗外部关闭
recordModal.addEventListener('click', function (e) {
    if (e.target === recordModal) {
        closeRecordModal();
    }
});

// 添加键盘事件监听 (ESC键关闭)
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && recordModal.classList.contains('active')) {
        closeRecordModal();
    }
});

// 语言卡片选择功能
const langCards = document.querySelectorAll('.lang-card');
const editorContainer = document.getElementById('editorContainer');

langCards.forEach(card => {
    card.addEventListener('click', () => {
        // 更新编辑器标题
        const langName = card.querySelector('span').textContent;
        document.querySelector('.editor-title span').textContent = `${langName} AI编辑器`;

        // 根据语言设置代码示例
        const codeInput = document.getElementById('codeInput');
        switch (card.dataset.lang) {
            case 'cpp':
                codeInput.value = `#include <iostream>
using namespace std;

int main() {
    cout << "Hello, C++ Developer!" << endl;

    // 计算斐波那契数列
    int n = 10, t1 = 0, t2 = 1;
    cout << "斐波那契数列前" << n << "项: ";

    for (int i = 1; i <= n; ++i) {
cout << t1 << " ";
int nextTerm = t1 + t2;
t1 = t2;
t2 = nextTerm;
    }

    return 0;
}`;
                break;
            case 'python':
                codeInput.value = `# 欢迎使用Python AI编辑器
print("Hello, Python Developer!")

# 计算斐波那契数列
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
yield a
a, b = b, a + b

n = 10
print(f"斐波那契数列前{n}项: {list(fibonacci(n))}")`;
                break;
            // Java 已下线（本机演示版本仅保留 Python / C++）
        }

        // 显示编辑器
        editorContainer.style.display = 'block';
        setTimeout(() => {
            editorContainer.classList.add('active');
        }, 50);
    });
});

// 刷题页面功能
const problemCodeInput = document.getElementById('problemCodeInput');

// 初始化代码编辑器高度
problemCodeInput.style.height = problemCodeInput.scrollHeight + 'px';

// 自动调整代码编辑器高度
problemCodeInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// 运行代码功能
document.querySelector('.btn-run').addEventListener('click', function () {
    const btn = this;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 运行中...';
    btn.disabled = true;

    // 模拟运行过程
    setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = false;

        const outputContent = document.getElementById('outputContent');
        outputContent.innerHTML = `
            <p style="color: var(--success)">✓ 编译成功！用时 0.23s</p>
            <p>测试用例 1: nums = [2,7,11,15], target = 9</p>
            <p>预期输出: [0,1] | 实际输出: [0,1] ✓</p>
            <p>测试用例 2: nums = [3,2,4], target = 6</p>
            <p>预期输出: [1,2] | 实际输出: [1,2] ✓</p>
            <p>测试用例 3: nums = [3,3], target = 6</p>
            <p>预期输出: [0,1] | 实际输出: [0,1] ✓</p>
            <p style="margin-top: 10px; color: var(--success)">✔ 所有测试用例通过</p>
        `;
    }, 1500);
});

// AI优化代码功能
document.querySelector('.btn-ai').addEventListener('click', function () {
    const btn = this;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 优化中...';
    btn.disabled = true;

    // 模拟AI优化过程
    setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = false;

        problemCodeInput.value = `class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
unordered_map<int, int> numMap;
for (int i = 0; i < nums.size(); i++) {
    int complement = target - nums[i];
    if (numMap.find(complement) != numMap.end()) {
        return {numMap[complement], i};
    }
    numMap[nums[i]] = i;
}
return {};
    }
};`;

        // 更新AI建议
        document.querySelector('.ai-response').innerHTML = `
            <h4><i class="fas fa-lightbulb"></i> 代码优化完成</h4>
            <p>已优化您的代码：</p>
            <ul style="margin-top: 5px; padding-left: 20px;">
                <li>使用哈希表将时间复杂度从 O(n²) 降低到 O(n)</li>
                <li>添加了更完善的错误处理</li>
                <li>优化了变量命名提升可读性</li>
            </ul>
        `;

        // 调整代码区域高度
        problemCodeInput.style.height = 'auto';
        problemCodeInput.style.height = (problemCodeInput.scrollHeight) + 'px';
    }, 2000);
});

// 提交解答功能
document.querySelector('.btn-submit').addEventListener('click', function () {
    const btn = this;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';
    btn.disabled = true;

    // 模拟提交过程
    setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.disabled = false;

        // 显示提交结果
        const outputContent = document.getElementById('outputContent');
        outputContent.innerHTML = `
            <p style="color: var(--success)">✓ 提交成功！</p>
            <p>执行用时: 12 ms (击败 95.67% 的用户)</p>
            <p>内存消耗: 10.8 MB (击败 87.42% 的用户)</p>
            <p style="margin-top: 15px; color: var(--success); font-weight: bold">
                <i class="fas fa-trophy"></i> 恭喜通过本题！
            </p>
            <p>积分 +10 | 当前积分: 1290</p>
        `;
    }, 1800);
});
