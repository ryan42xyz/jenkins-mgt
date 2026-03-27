# Jenkins Management Dashboard

[English](#english) | [中文](#chinese)

---

<a name="english"></a>

## Why I Built This

Jenkins' native UI is designed for single-job interactions — you can only view one job, one build, and one set of parameters at a time. As CI/CD pipelines grow more complex, this becomes inefficient:

- **Pipelines are chained.** A single image release flows through entrypoint → pre-process → build-image → deploy, but Jenkins has no unified view — each job requires opening a separate page.
- **Parameters are scattered and hard to trace.** Finding what parameters last produced a successful build means drilling into build detail → parameters, clicking many times just to replay.
- **Multi-environment friction.** Switching between old and new Jenkins instances means juggling browser tabs with different URLs and credentials.
- **Replay is painful.** Retrying a failed build with the same parameters requires a deep navigation path.

This tool does one simple thing: **aggregate all job statuses, recent build records, and parameters onto a single page**, ordered by actual pipeline sequence, so day-to-day build management no longer requires jumping between multiple Jenkins pages.

Core use cases:
1. First thing in the morning: check overall build health at a glance
2. When something breaks: quickly pinpoint which job failed and on which parameters
3. One-click replay using the last successful build's parameters
4. Quickly compare builds across old and new Jenkins environments

---

## Screenshots

### Dashboard Overview
![Dashboard Overview](screenshot-dashboard-overview.png)

### Job Detail View
![Job Detail View](screenshot-job-detail.png)

---

## Features

### Smart Organization
- **Folder hierarchy**: Group related pipelines into ordered folder structures
- **Pipeline ordering**: Display pipelines within folders by configured execution order
- **Three-tier architecture**: Folder → Job → Latest 5 Builds (expandable)
- **Quick navigation**: Collapsible folders and jobs, expanded by default

### Multi-Environment Support
- Switch seamlessly between multiple Jenkins environments (e.g. current vs. legacy)
- Instant switching via UI dropdown
- Unified YAML config manages all environments

### Performance
- **Concurrent fetching** via `ThreadPoolExecutor`
- **~30% faster** response times (8.31s → 5.79s)
- Batch requests to reduce HTTP call count
- Smart caching to minimize redundant Jenkins API calls

### Search
- Search by job name — shows last 5 builds with parameters
- Search by Build ID — fetch a specific build's details
- Status filtering to quickly spot failures

### Modern UI
- Responsive design (desktop and mobile)
- Color-coded build status indicators
- Bootstrap 5 components

---

## Architecture

### Three-tier structure
```
📁 Folder (Build Image Pipeline)
    ├── 🔧 Job (global-entrypoint)
    │   ├── 📋 Build #12345 (SUCCESS)
    │   ├── 📋 Build #12344 (FAILURE)
    │   ├── 📋 Build #12343 (SUCCESS)
    │   ├── 📋 Build #12342 (UNSTABLE)
    │   └── 📋 Build #12341 (SUCCESS)
    └── 🔧 Job (pre-process-general-build-docker-image)
        └── [Recent 5 Builds...]
```

### Data flow
```
Config → Backend → Frontend → User
  ↓         ↓         ↓        ↓
YAML → JenkinsManager → Web UI → Interaction
  ↓         ↓         ↓        ↓
Multi-Env → Concurrent → Real-time → Management
```

---

## Quick Start

### 1. Setup
```bash
git clone https://github.com/ryan42xyz/jenkins-mgt
cd jenkins-mgt

python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Configuration
```bash
cp jobs_config.yaml.example jobs_config.yaml
# Edit jobs_config.yaml with your Jenkins URL, username, and API token
```

`jobs_config.yaml` is in `.gitignore` and will not be committed. Example config:

```yaml
environments:
  current:
    name: "My Jenkins"
    jenkins:
      url: "http://jenkins.example.com"
      username: "your_username"
      token: "your_api_token"
  # legacy:  # optional: configure a second Jenkins environment
  #   name: "Old Jenkins"
  #   jenkins:
  #     url: "http://old-jenkins.example.com"
  #     username: "your_username"
  #     token: "your_api_token"

folders:
  - name: "Build Image Pipeline"
    description: "Complete Docker image build pipeline chain"
    icon: "fas fa-docker"
    order: 1
    pipelines:
      - name: "global-entrypoint"
        description: "Global entrypoint pipeline"
        order: 1
      - name: "general-build-docker-image"
        description: "Docker image build pipeline"
        order: 2
```

### 3. Run
```bash
# Development
python app.py

# Background
nohup python app.py > nohup.out 2>&1 &
```

Open: http://localhost:5000

### 4. Tests
```bash
./run_tests.sh

# Manual API test
curl http://localhost:5000/api/jobs
```

---

## Usage Guide

### Environment Switching
1. Click the environment selector (top right)
2. Data clears automatically — click **Refresh Jobs** to reload

### Folders
- Click a folder header to collapse/expand
- Pipelines are sorted by the `order` field in config

### Job Expand
1. Click the expand button on a job row to see the last 5 builds
2. Each build shows: status, time, duration, triggered by, parameters
3. Quick actions: Console Log, Replay, Parameters

### Search
- **Job search**: type a job name → shows last 5 builds with parameters
- **Build search**: type a Build ID → shows that specific build's details

### Quick Actions
- **Jenkins Job** — open job page in Jenkins
- **Console Log** — view build output
- **Replay** — re-run the build
- **Parameters** — view/edit parameters
- **Copy Parameters** — copy params for a new build
- **Quick Build** — trigger with latest parameters

---

## Status Indicators

| Status | Color | Meaning |
|--------|-------|---------|
| SUCCESS | Green | Build passed |
| FAILURE | Red | Build failed |
| UNSTABLE | Yellow | Build unstable |
| ABORTED | Gray | Build aborted |
| RUNNING | Blue | Build in progress |
| PENDING | Orange | Build queued |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main page |
| GET | `/api/jobs` | All jobs summary (with folder structure) |
| GET | `/api/job/<job_name>` | Specific job info |
| GET | `/api/build/<job_name>/<build_id>` | Specific build info |
| GET | `/api/environments` | List available environments |
| POST | `/api/switch-environment` | Switch Jenkins environment |
| GET | `/api/job/<job_name>/recent-builds` | Recent builds for a job |
| POST | `/api/job/<job_name>/build` | Trigger a new build |

---

## File Structure

```
jenkins-mgt/
├── app.py                      # Flask application
├── jenkins_manager.py          # Jenkins API client
├── jobs_config.yaml.example    # Config template
├── get_jenkins_config.py       # Utility: fetch job config from Jenkins
├── templates/
│   └── index.html              # Frontend
├── k8s/                        # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── test_jenkins_manager.py     # Unit tests
├── run_tests.sh                # Test runner
├── Dockerfile
├── build.sh                    # Docker build script
└── requirements.txt
```

---

## Performance

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total time | 8.31s | 5.79s | 30.3% faster |
| Throughput | 1.20 jobs/s | 1.73 jobs/s | 44.2% higher |
| Concurrency | 1 | 8 | 8x |
| Timeout | 30s | 15s | 50% lower |

---

## Deployment

### Docker
```bash
docker build -t jenkins-mgt .
docker run -d -p 5000:5000 \
  -v $(pwd)/jobs_config.yaml:/app/jobs_config.yaml \
  jenkins-mgt
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

### Traditional
```bash
pip install -r requirements.txt
python app.py
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Connection failed | Check Jenkins URL and network access |
| Auth error | Verify username and API token |
| Missing data | Check Jenkins job permissions |

---

## License

MIT License

---

> **Note**: Keep your Jenkins API token secure. Never commit it to version control. Use environment variables or a secrets manager.

---

<a name="chinese"></a>

## 为什么做这个

Jenkins 原生 UI 是为单任务设计的：每次只能看一个 job、翻一个 build、找一组参数。当 CI/CD 流程变复杂之后，这套交互变得很低效：

- **pipeline 是串联的**。一次镜像发布要经过 entrypoint → pre-process → build-image → deploy 多个 job，但 Jenkins 没有统一视图，每个 job 都要单独打开页面确认状态。
- **参数分散、难以追溯**。上次用什么参数跑成功的？要进 build detail → parameters 一层层找，想复用一次要点很多下。
- **多环境切换摩擦大**。新旧两套 Jenkins 实例之间，要来回切换浏览器 tab，URL 不同、认证不同。
- **replay 麻烦**。失败了想用同一组参数重试，原生操作路径很深。

这个工具做的事情很简单：**把所有 job 的状态、最近构建记录、参数，汇聚到一个页面**，按照实际的 pipeline 顺序排列，让日常的构建管理操作不用再在多个 Jenkins 页面之间跳来跳去。

核心使用场景：
1. 每天上班第一眼看整体构建健康状态
2. 出问题时快速定位是哪个 job 挂了、挂在哪个参数上
3. 用上一次成功构建的参数一键 replay
4. 在新旧 Jenkins 环境之间快速对比

---

## 截图

### 主界面总览
![Dashboard Overview](screenshot-dashboard-overview.png)

### Job 详情视图
![Job Detail View](screenshot-job-detail.png)

---

## 核心特性

### 智能组织结构
- **Folder 层级管理**: 将相关 pipeline 组织成有序的文件夹结构
- **Pipeline 顺序**: 支持 folder 内 pipeline 的执行顺序展示
- **三层架构**: Folder → Job → Latest 5 Builds（可展开）
- **快速导航**: 可折叠的 folder 和 job 结构，默认展开状态

### 多环境支持
- 支持新旧两个 Jenkins 环境无缝切换
- 通过 UI 下拉菜单即时切换环境
- 统一的 YAML 配置文件管理多环境

### 性能优化
- 使用 `ThreadPoolExecutor` 并发获取 job 信息
- **性能提升约 30%**（从 8.31秒 优化到 5.79秒）
- 批量请求减少 HTTP 请求数量
- 智能缓存减少重复的 Jenkins API 调用

### 搜索功能
- 搜索 job 名称，显示最近 5 次构建记录和参数
- 搜索 Build ID，获取特定构建详情
- 状态过滤，快速识别成功/失败的构建

### 现代化界面
- 响应式设计，支持桌面和移动设备
- 彩色状态指示
- Bootstrap 5

---

## 架构

### 三层组织结构
```
📁 Folder (Build Image Pipeline)
    ├── 🔧 Job (global-entrypoint)
    │   ├── 📋 Build #12345 (SUCCESS)
    │   ├── 📋 Build #12344 (FAILURE)
    │   ├── 📋 Build #12343 (SUCCESS)
    │   ├── 📋 Build #12342 (UNSTABLE)
    │   └── 📋 Build #12341 (SUCCESS)
    └── 🔧 Job (pre-process-general-build-docker-image)
        └── [Recent 5 Builds...]
```

### 数据流
```
Config → Backend → Frontend → User
  ↓         ↓         ↓        ↓
YAML → JenkinsManager → Web UI → Interaction
  ↓         ↓         ↓        ↓
Multi-Env → Concurrent → Real-time → Management
```

---

## 快速开始

### 1. 环境准备
```bash
git clone https://github.com/ryan42xyz/jenkins-mgt
cd jenkins-mgt

python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. 配置设置
```bash
cp jobs_config.yaml.example jobs_config.yaml
# 编辑 jobs_config.yaml，填入真实的 URL、用户名和 API Token
```

`jobs_config.yaml` 已在 `.gitignore` 中，不会被提交。配置格式：

```yaml
environments:
  current:
    name: "My Jenkins"
    jenkins:
      url: "http://jenkins.example.com"
      username: "your_username"
      token: "your_api_token"
  # legacy:  # 可选：配置旧版 Jenkins 环境
  #   name: "Old Jenkins"
  #   jenkins:
  #     url: "http://old-jenkins.example.com"
  #     username: "your_username"
  #     token: "your_api_token"

folders:
  - name: "Build Image Pipeline"
    description: "Complete Docker image build pipeline chain"
    icon: "fas fa-docker"
    order: 1
    pipelines:
      - name: "global-entrypoint"
        description: "Global entrypoint pipeline"
        order: 1
      - name: "general-build-docker-image"
        description: "Docker image build pipeline"
        order: 2
```

### 3. 启动应用
```bash
# 开发模式
python app.py

# 后台运行
nohup python app.py > nohup.out 2>&1 &
```

访问: http://localhost:5000

### 4. 测试验证
```bash
./run_tests.sh

# 手动测试 API
curl http://localhost:5000/api/jobs
```

---

## 功能指南

### 多环境管理
1. 点击右上角环境选择器切换环境
2. 切换后自动清空数据，点击 **Refresh Jobs** 重新加载

### Folder 功能
- 点击 folder header 折叠/展开
- 按配置的 `order` 字段排序显示

### Job 展开功能
1. 点击 job 行的展开按钮查看最近 5 次构建
2. 每个 build 显示：状态、时间、持续时间、触发人、参数
3. 快速操作：Console Log、Replay、Parameters

### 搜索功能
- **Job 搜索**: 输入 job 名称 → 显示最近 5 次构建和参数
- **Build 搜索**: 输入 Build ID → 显示该构建详情

### 快速操作
- **Jenkins Job** — 跳转到 Jenkins job 页面
- **Console Log** — 查看构建日志
- **Replay** — 重放构建
- **Parameters** — 查看/编辑构建参数
- **Copy Parameters** — 复制参数用于新构建
- **Quick Build** — 使用最新参数快速构建

---

## 状态指示器

| 状态 | 颜色 | 含义 |
|------|------|------|
| SUCCESS | 绿色 | 构建成功 |
| FAILURE | 红色 | 构建失败 |
| UNSTABLE | 黄色 | 构建不稳定 |
| ABORTED | 灰色 | 构建中止 |
| RUNNING | 蓝色 | 正在构建 |
| PENDING | 橙色 | 等待构建 |

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 主页面 |
| GET | `/api/jobs` | 获取所有 jobs 汇总（含 folder 结构）|
| GET | `/api/job/<job_name>` | 获取特定 job 信息 |
| GET | `/api/build/<job_name>/<build_id>` | 获取特定构建信息 |
| GET | `/api/environments` | 获取所有可用环境 |
| POST | `/api/switch-environment` | 切换 Jenkins 环境 |
| GET | `/api/job/<job_name>/recent-builds` | 获取最近构建记录 |
| POST | `/api/job/<job_name>/build` | 触发新构建 |

---

## 文件结构

```
jenkins-mgt/
├── app.py                      # Flask 主应用
├── jenkins_manager.py          # Jenkins API 客户端
├── jobs_config.yaml.example    # 配置模板
├── get_jenkins_config.py       # 工具脚本：从 Jenkins 抓取 job 配置
├── templates/
│   └── index.html              # 前端界面
├── k8s/                        # Kubernetes 部署文件
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── test_jenkins_manager.py     # 单元测试
├── run_tests.sh                # 测试执行脚本
├── Dockerfile
├── build.sh                    # Docker 构建脚本
└── requirements.txt
```

---

## 性能指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 总耗时 | 8.31秒 | 5.79秒 | 30.3% ↓ |
| 处理速度 | 1.20 jobs/s | 1.73 jobs/s | 44.2% ↑ |
| 并发数 | 1 | 8 | 8x ↑ |
| 超时时间 | 30秒 | 15秒 | 50% ↓ |

---

## 部署方案

### Docker
```bash
docker build -t jenkins-mgt .
docker run -d -p 5000:5000 \
  -v $(pwd)/jobs_config.yaml:/app/jobs_config.yaml \
  jenkins-mgt
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

### 传统部署
```bash
pip install -r requirements.txt
python app.py
```

---

## 故障排除

| 问题 | 解决方法 |
|------|----------|
| 连接失败 | 检查 Jenkins URL 和网络连接 |
| 认证错误 | 验证用户名和 API token |
| 数据不全 | 检查 Jenkins job 权限设置 |

---

## 许可证

MIT License

---

> **注意**: 确保 Jenkins API token 的安全，不要将其提交到版本控制系统。建议使用环境变量或安全的配置管理方案。
