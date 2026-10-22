# Python 与 C++17

当前版本统一语言标识为 `python`、`cpp`。刷题与共创使用标准输入输出：Python 文件为 `solution.py`，C++ 文件为 `main.cpp`，入口为 `int main()`。
任务室沿用函数合同：Python `solve(data)`、C++ `Json solve(const Json& data)`，系统提供 JSON 包装；导出包含源文件与运行说明。

```sh
 docker build -t codelab-runner:local sandbox
```

配置 `SUPPORTED_LANGUAGES=python,cpp`、`CODE_SANDBOX_IMAGE=codelab-runner:local` 后重启服务。若仅启用 Python，任务室目录、创建与执行也会限制为 Python。
界面、问卷、AI 提示、草稿、导出及执行器均支持这两种语言，其他语言请求会被拒绝。数据库升级保留已有记录，不改变记录所属语言。

代码在无网络、只读根文件系统、非特权 Docker 容器中执行，不回退到宿主执行。默认资源限制见 `.env.example`；编译错误、运行异常、超时和输出超限分别返回真实状态。每个应用进程同时最多执行两个任务，繁忙时需重试，未实现分布式任务队列。

验证：

```sh
python -m unittest discover -s tests
python -m modules.task_room.verify_languages --languages python cpp
python scripts/verify_co_create_learning.py
```

后两项使用真实 Docker，隔离验证库，不调用真实 AI。它们证明样本程序与流程可执行，不代表模型生成质量或学习效果。
