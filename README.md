# X Information Collector

X (Twitter) 信息收集智能体 - 自动采集订阅用户动态，AI 识别与总结。

## 功能特性

- � 订阅管理：配置 YAML 文件管理监控用户列表
- 🤖 多模态 AI：支持 DashScope/OpenAI/Anthropic/Google 多供应商切换
- 📸 智能采集：Playwright 浏览器自动化截图 + AI 识别
- 📊 内容总结：每日热点汇总，AI 智能提炼
- 📧 通知推送：本地报告 + 邮件通知
- ⏰ 定时/手动：每日自动采集，支持手动触发

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 配置

1. 复制配置模板并填写 API Key：
```bash
cp config/config.example.yaml config/config.yaml
```

2. 编辑订阅用户列表：
```bash
vim config/subscriptions.yaml
```

### 使用

```bash
# 手动触发采集
python main.py collect

# 采集指定用户
python main.py collect --user elonmusk

# 生成今日报告
python main.py report

# 启动守护进程 (每日定时)
python main.py daemon

# 查看订阅列表
python main.py list
```

## 配置说明

详见 `config/config.example.yaml`

## License

MIT
