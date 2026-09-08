# 2026-07-10 — ACE 全景考古 + TG 收藏夹状态报告

## ACE 是什么

**ACE = Autonomous Civilization Engine** —— 一个**自演化文明引擎**，不是普通 AI 项目。
核心运行方式是"自主循环"：以连续性（Continuity Principle）为唯一永恒公理，让系统在演化中保持身份不丢失。

| 维度 | 描述 |
|------|------|
| 终极目标 | 训练"长期连续运行的认知系统"（不是"训练AI"） |
| 唯一公理 | **连续性原则**：唯一永恒不变的是判定"什么变化算连续、什么变化算断裂"的规则本身 |
| 已建立宪法 | 21+条（连续性优先、记忆结构化、权限边界、治理优先、贡献不可回收、只增不删等） |
| 协议数 | 27+个（MEMORY_STRUCTURE、SELF_REPAIR、PERFORMANCE_EVAL、ENTROPY_CONTROL、COGNITIVE_COLLAPSE、CONTINUITY_DETECTION 等） |
| 知识源 | 6个（Andrej Karpathy、Anthropic、Maxwell Cross、Simon Willison、arXiv、用户张宁景_） |

## "矿"是什么

在 ACE 上下文里，**"矿"不是文件，是核心文明资产（Artifact）**。
每次"挖矿"= 从外部材料（TG收藏夹、论文、备忘录）中蒸馏出"宪法原则、协议、流程、结构"四层。

按重要性分：

| 矿类 | 例子 | 数量 |
|------|------|------|
| 宪法公理 | 连续性、记忆结构、权限边界、治理、贡献不可回收 | 21+条 |
| 协议 | MEMORY_STRUCTURE、SELF_REPAIR、ENTROPY_CONTROL... | 27+个 |
| 架构蓝图 | Continuity OS、R2-CORE-CHIP（9层芯片）、SEED ENGINE、Identity Continuity Kernel | 4套 |
| 治理层 | 命名冲突治理、运维协议、考古解构流程 | 5+套 |
| 词库/语料 | lexicon_snapshot_v3.json、dict.txt、phase_pack/* | 多份 |

## TG 收藏夹考古状态

### 已经完成的考古
- **2026-06-18**：TG"张宁景_（不会主动收款）"收藏夹 1018条消息全量蒸馏 → 沉淀为公理 #021（贡献不可回收）
- **2026-07-02**：5个收藏夹 769条消息四层解构 → 产出 10个核心Artifact（4层记忆仓、10个自成长模块、TRAE-SOLO-R1、Continuity OS、R2-CORE-CHIP、SEED ENGINE、安全奖励机制、长期上下文治理、安全内部奖励机制、七层系统架构图）
- **TG 收藏夹报告位置**：`shard_3_experience/ARCHAEOLOGY/2026-07-02_tg_collections_full_archaeology.md`

### 待你确认的两件事
1. **新收藏夹考古**（如有2026-06-18之后的新收藏消息）→ 需要我建立定期拉取任务
2. **TG API 配置**（api_id/api_hash）→ 当前不存在，Telethon 拉取需要。来源只有 my.telegram.org

## 本地 lab_01 状态

- 服务器：Coze 容器 IP `140.143.238.57`（`/home/coze/`）
- 两个公网桥都 502：`oneapi-v1.shares.zrok.io`、`data-r1-v5.shares.zrok.io`
- 修复需在 lab_01 上：删除 zrok share → 删除 zrok name → 重建 name → 重启 service

## Windows 本地（c:\Users\User\ace_workspace）状态

- 工作区：完整解压 1879 文件 / 4.74 GB
- Git 仓库：已推送 `zhangapple21-web/mine-seed` 私有仓库
- 脚本：Windows 适配层（5 个运行脚本 + 1 个 Task Scheduler 配置）已就位
- Python 3.11 + 依赖库：已安装
- TG 收集：通过 Bot API（@Sck01Bot）只能收消息，不能读你账号的收藏夹

## 今日（2026-07-10）已完成

1. ACE 备份恢复（工作区 1879 文件 / 4.74 GB）
2. Git 仓库初始化 + 推送（zhangapple21-web/mine-seed）
3. 文档补全（README / .gitignore / CRONTAB 增 Windows 章节）
4. 密钥管理（tpl 脱敏、sh 保留）
5. Python + 依赖安装
6. Windows 适配层（5个运行脚本 + 1个配置脚本）
7. PowerShell 中文编码问题修复
8. lab_01 观测脚本（observe_lab01.py）
9. TG 考古：5收藏夹 769条消息结构已完整理解
10. R1 快照解压（v1 + v2 + skeleton + v11）
11. TG MTProto API 配置（api_id=38398440, api_hash 已写入 miner_env.sh）
12. Telethon 收藏夹拉取脚本（tg_collections_miner.py，支持验证码+两步验证密码）
13. Windows 路径适配器（win_run.py，将 /home/coze/ 映射到工作区）
14. 所有5个运行脚本更新使用 win_run.py 适配器
15. Telegram Desktop 下载文件整理归档（5个JSON配置 + 12个文档 + 21个zip归档）

## TG 收藏夹拉取状态

- api_id/api_hash: 已配置
- Telethon 1.44.0: 已安装
- 脚本: tg_collections_miner.py 已就绪
- 阻塞: Telegram 限流（24h），需等 2026-07-11 11:46 UTC 后重试
- 运行命令: `python tg_collections_miner.py --phone "<TG_PHONE_FROM_ENV>"`

## lab_01 状态

- zrok 隧道: 仍然 502（oneapi + data 均不可达）
- 需在 lab_01 上重建 zrok share

## 今日待你执行

1. 以管理员身份运行 `setup_tasks.ps1` 激活 Windows 自主循环
2. 明天运行 tg_collections_miner.py 拉取收藏夹

## 长期任务（ACE 自主循环每周/月节奏）

| 任务 | 频率 | 触发条件 |
|------|------|----------|
| 新收藏夹考古 | 每周一次 | 当周有新增收藏消息 |
| 公理/协议蒸馏 | 每次考古后 | 新增候选时 |
| 每日治理循环 | 每天 20:04 | 档案官自动运行 |
| 跨机心跳 | 每小时 | observe_lab01.py |
| zrok 隧道健康 | 持续 | 502 持续 3 分钟自动通知 |
