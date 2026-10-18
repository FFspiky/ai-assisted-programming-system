# 三语言执行与 AI 帮助

统一语言标识为 `python`、`cpp`、`java`。所有用户代码继续在无网络、只读根文件系统、非特权 Docker 容器中执行，不回退到宿主机执行。

| 语言 | 运行约定 | 标准入口 |
| --- | --- | --- |
| Python 3.11 | UTF-8 Python 脚本 | 脚本顶层，或 `main()` |
| C++17 | `g++ -std=c++17` | `int main()` |
| Java 17 | `javac --release 17 -encoding UTF-8 -proc:none` | `Main.java` / `public class Main` / `public static void main(String[] args)` |

刷题程序读取标准输入、写出标准输出。Java 程序不声明 `package`；多个辅助类可放在同一个源文件中，公开入口类使用 `Main`。编译环境只提供标准语言库。题目判定仍使用题目自身的输入、预期输出及判题模式。

共创和实战任务室如使用函数合同，由相应模块提供该语言的输入输出包装。标准刷题入口模板不能直接替代模块要求的函数签名。

## 配置与构建

`.env` 与 `.env.example` 的语言配置：

```dotenv
SUPPORTED_LANGUAGES=python,cpp,java
CODE_SANDBOX_IMAGE=codelab-runner:local
```

在项目根目录构建镜像：

```text
docker build -t codelab-runner:local sandbox
```

本次升级前的镜像保留为 `codelab-runner:pre-java-20261016`。如 Docker Hub 暂不可达，可复用该本地 Python/C++ 镜像，仅下载缺少的 Debian JDK 软件包：

```text
docker build --build-arg PYTHON_IMAGE=codelab-runner:pre-java-20261016 -t codelab-runner:local sandbox
```

已额外保留兼容新版源码传输协议的 Python/C++ 镜像 `codelab-runner:python-cpp-20261016`。只回退 Java 功能时，使用 `docker tag codelab-runner:python-cpp-20261016 codelab-runner:local`，同时从语言配置中关闭 Java 并重启网站；原有提交数据不受影响。最初的 `pre-java` 镜像使用旧命令行协议，仅适合与相应旧版运行器一起整体回退，不能直接交给新版运行器。

## 资源与结果

默认容器仍限制 256 MB 内存、32 个进程/线程、1 个 CPU、10 秒总等待及有界输出。Java 的编译器 JVM 和运行 JVM 都使用 96 MB 最大堆、64 MB 元空间上限、串行 GC 与单 CPU 参数，为 JVM 本身的线程和本地内存预留空间。256 MB 是容器总上限，不能视为 Java 可分配的堆容量。

源码与标准输入通过 Docker 的输入管道传送，容器入口恢复原始标准输入后执行。源码不再编码到 Windows 命令行参数中，避免长代码或多字节字符超过 Windows 命令行长度；源码和输入仍仅进入当前容器。

编译阶段允许至多 16 MB 的单个中间文件，仍受有界临时文件系统限制，避免正常 C++ 模板编译被默认 1 MB 用户文件限额中断。用户程序开始前会将文件写入软限制和硬限制同时降回 `CODE_RUN_FILE_SIZE_MB` 配置值，默认 1 MB；程序不能自行提高该硬限制。回归实际确认了 2 MB 写入被拒绝。

Java 编译失败返回 `Compile Error`；运行异常返回 `Runtime Error`；堆耗尽或容器资源终止返回 `Resource Limit Exceeded`；超过总等待返回 `Time Limit Exceeded`。沙箱中的异常输出仍有长度限制。

通用补全、优化、问答、分级学习帮助及提交诊断均使用统一语言版本和入口约定。AI 返回内容是候选建议，真实通过与否依照 Docker 执行和判题证据；提示适配测试使用 mock，不调用付费模型。

## 复用接口

`services/language_support.py` 提供：

- `LANGUAGE_IDS`：有序的三语言标识。
- `normalize_language(value)`：统一 `C++`、`python3`、`java17` 等别名。
- `language_spec(language)`：返回 `id/label/version/filename/entrypoint/starter_code` 元数据副本。
- `language_options(enabled=None)`：按支持列表返回语言元数据。
- `language_label(language)`、`starter_code(language)`、`language_prompt(language)`：供界面、模块与 AI 提示复用。

真实隔离执行回归：

```text
.\.venv\Scripts\python.exe -m unittest tests.test_execute_runner
```

语言契约与无网络 AI 提示回归：

```text
.\.venv\Scripts\python.exe -m unittest tests.test_language_support tests.test_ai_prompts tests.test_autocomplete
```

Windows 上测试进程必须具有访问 Docker Desktop 引擎的权限；沙箱工具会话的 Docker 管道拒绝访问属于测试进程权限问题，不能据此判断某种编程语言错误。

## 参数依据

JDK 包采用 [Debian bookworm 的 openjdk-17-jdk-headless](https://packages.debian.org/bookworm/openjdk-17-jdk-headless)。入口及 `-Xmx`、`-Xss`、`UseSerialGC`、`ActiveProcessorCount`、元空间参数以 [Java 17 java 官方手册](https://docs.oracle.com/en/java/javase/17/docs/specs/man/java.html)为依据；编译编码、`--release`、`-proc:none` 和 `-J` 参数见 [Java 17 javac 官方手册](https://docs.oracle.com/en/java/javase/17/docs/specs/man/javac.html)。具体资源预算以本机真实 Docker 回归为准。
