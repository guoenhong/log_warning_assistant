# Log Warning Assistant

日志预警助手 - 基于 MiniMax M2.7 的智能日志分析工具

## 功能特性

- 🤖 **LLM 驱动** - MiniMax M2.7 自动选择合适工具
- 📊 **日志解析** - 支持 IIS、Nginx、Apache、JSON 等格式
- 🔍 **智能分析** - 自动统计、错误分析、关键词搜索
- 📝 **结构化报告** - 结论 + 数据 + 建议

---

## 一、前置条件

### 1. 环境要求

- Python 3.8+
- MiniMax API Key

### 2. 获取 API Key

1. 访问 [MiniMax 开放平台](https://platform.minimaxi.com)
2. 注册/登录账号
3. 创建 API Key：[接口密钥](https://platform.minimaxi.com/user-center/basic-information/interface-key)
4. 充值账户（按量付费）

### 3. 配置环境变量

创建 `.env` 文件：

```
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_API_KEY=你的API_Key
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

---

## 二、基本用法

### 命令行（推荐）

```bash
python -m src.log_assistant "分析日志错误" logs/u_ex170704.log
```

### Python API

```python
from src.log_assistant import analyze

result = analyze(
    question="分析日志中的主要错误",
    log_path="logs/u_ex170704.log"
)

print(result['structured_output']['markdown'])
```

---

## 三、完整用法

### 命令行参数

```bash
python -m src.log_assistant "问题" 日志路径 [选项]
```

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `question` | - | 分析问题（必需） | - |
| `log_path` | - | 日志文件路径（必需） | - |
| `--top-n` | - | 返回条数 | 10 |
| `--keywords` | - | 关键词（逗号分隔） | - |
| `--time-start` | - | 开始时间 ISO 格式 | - |
| `--time-end` | - | 结束时间 ISO 格式 | - |
| `--knowledge` | - | 知识文本文件路径 | - |
| `--output` | `-o` | 输出 Markdown 文件 | - |

### 完整示例

```bash
# 基本分析
python -m src.log_assistant "分析主要错误" logs/u_ex170704.log

# 指定返回条数
python -m src.log_assistant "有哪些5xx错误" logs/u_ex170704.log --top-n 20

# 关键词搜索
python -m src.log_assistant "搜索timeout相关错误" logs/u_ex170704.log --keywords timeout,database

# 时间范围 + 输出文件
python -m src.log_assistant "分析上午的错误" logs/u_ex170704.log \
    --time-start 2017-07-04T08:00:00 \
    --time-end 2017-07-04T12:00:00 \
    --output result.md

# 使用知识文本
python -m src.log_assistant "分析错误原因" logs/u_ex170704.log \
    --knowledge faq.txt
```

### Python API 完整参数

```python
from src.log_assistant import analyze

result = analyze(
    question="分析日志中的主要错误",
    log_path="logs/u_ex170704.log",
    time_range={
        "start": "2017-07-04T10:00:00",
        "end": "2017-07-04T12:00:00"
    },
    keywords=["error", "timeout"],
    top_n=20,
    knowledge_text="历史故障：上次是Redis连接池耗尽"
)

# 获取 Markdown 报告
print(result['structured_output']['markdown'])

# 获取原始 LLM 回答
print(result['llm_raw_response'])

# 获取使用的工具列表
print(result['tools_used'])
```

---

## 四、可分析的日志类型

- ✅ IIS 日志 (W3C Extended Format)
- ✅ Nginx/Apache 访问日志
- ✅ JSON 格式日志
- ✅ 自定义文本日志

---

## 五、示例问题

你可以问：

- "分析日志中的主要错误"
- "有哪些5xx服务器错误？"
- "404错误主要出现在哪些URL？"
- "响应时间最慢的请求有哪些？"
- "帮我排查系统性能问题"
- "最近一小时的异常请求有哪些？"

---

## 六、项目结构

```
log_warning_assistant/
├── .env                     # API 配置（需自行创建）
├── config/
│   └── config.yaml          # 配置文件
├── src/log_assistant/
│   ├── __main__.py          # CLI 入口
│   ├── log_parser.py        # 日志解析
│   ├── orchestrator.py     # 主协调器
│   ├── llm_client.py        # LLM 集成
│   ├── function_calling.py  # 工具定义
│   └── output_generator.py  # 输出生成
├── tools/
│   └── log_tools.py         # 工具函数
├── logs/                    # 示例日志
│   └── u_ex170704.log      # IIS 日志样例
└── requirements.txt         # 依赖
```

---

## 七、输出格式

```
# 日志分析报告

**问题**: 分析日志中的主要错误
**日志文件**: logs/u_ex170704.log

**状态**: ✅ 信息充分

## 1. 结论
[发生了什么]

## 2. 关键数据
- 总日志条目: 191243
- 5xx错误总数: 0
- 404错误: 10999
- 日志时间范围: 2017-07-04 00:00 ~ 23:59

## 3. 建议
- 排查 404 请求的来源
- 检查异常 IP
```

---

## 八、运行测试

```bash
pytest
```

---

## 依赖

- anthropic>=0.18.0      # MiniMax SDK
- python-dateutil>=2.8.0 # 日期解析
- pyyaml>=6.0            # 配置文件
- pytest>=7.0.0          # 测试框架
- python-dotenv>=1.0.0   # 环境变量

---

## License

MIT
