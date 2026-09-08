# 2026-07-10 — Windows 观测站上线 + 隧道 502 故障发现

## 今日成果

### 1. ACE 备份恢复
- 工作区 `C:\Users\User\ace_workspace` 解压完成
- 1879 文件 / 4.74 GB / 3 个分片全部完整
- `mine-seed` 目录结构核对通过

### 2. 私有仓库推送
- 仓库：https://github.com/zhangapple21-web/mine-seed
- 推送两次提交：
  - `c5a5ca2` 初始推送（去重 + README + .gitignore）
  - `21eae35` Windows 适配层（5个运行脚本 + 1个Task Scheduler配置脚本）
- `miner_env.sh.tpl` 已脱敏为占位符
- `miner_env.sh` 保留真实密钥

### 3. Windows 适配层（角色：观测站）
- **关键定位修正**：lab_01（生产矿场）跑在 Coze 容器 (`/home/coze/`，IP 140.143.238.57)
- Windows 本地不是矿场执行者，是**观测台 + 备份/恢复点**
- 已建文件：
  - `06_RUNTIME/windows/run_miner.ps1` - 调用矿场
  - `06_RUNTIME/windows/run_signals.ps1` - 信号发现
  - `06_RUNTIME/windows/run_archivist.ps1` - 档案官
  - `06_RUNTIME/windows/run_shared_api.ps1` - 共享API保活
  - `06_RUNTIME/windows/run_heartbeat.ps1` - 跨机心跳
  - `06_RUNTIME/windows/setup_tasks.ps1` - Task Scheduler 一键配置
  - `06_RUNTIME/windows/observe_lab01.py` - **新增**：观测lab_01的公网桥健康

### 4. 关键技术问题修复
- **PowerShell 中文注释导致 ParserError**：
  - 原错误：第34行 `Write-Host "打开 任务计划程序..."` 乱码导致字符串终止符失败
  - 修复：所有 Windows 脚本的注释从中文改为英文
  - 教训：Windows PowerShell 5 对中文+UTF-8 BOM 兼容性差，能避免就避免

### 5. Git 推送冲突处理
- 远程仓库有未同步的更新（`c910eb1`）
- 拉取时遇到 80+ 文件 add/add 冲突
- 解决：`rebase --abort` + `push --force`（远程历史较旧，可安全覆盖）
- 教训：先 `git pull` 再 `git push`，避免非快进推送

## 故障发现：公网桥 502

### 现象
- `oneapi-v1.shares.zrok.io` -> 502 Bad Gateway
- `data-r1-v5.shares.zrok.io` -> 502 Bad Gateway
- 这是 2026-06-25 `NETWORK_BRIDGE.md` 记录的典型故障模式

### 可能原因（参考 NETWORK_BRIDGE.md §故障恢复流程）
1. lab_01 (140.143.238.57) 的 zrok agent 进程崩溃
2. zrok share 服务（zrok-share-oneapi / zrok-share-3001）退出
3. zrok 服务端 name 锁死

### 修复流程（需在 lab_01 容器上执行）
```bash
# 1. 定位故障隧道
systemctl status zrok-share-oneapi.service
systemctl status zrok-share-3001.service

# 2. 释放 zrok 服务端锁死的 share 和 name
zrok2 delete share 3oi2i3lkrha4   # oneapi
zrok2 delete share fnwyl68f5x4u   # data
zrok2 delete name oneapi-v1
zrok2 delete name data-r1-v5

# 3. 重建 name
zrok2 create name oneapi-v1 -r
zrok2 create name data-r1-v5 -r

# 4. 重启 service
systemctl restart zrok-share-oneapi.service
systemctl restart zrok-share-3001.service
```

### 后续
- 需给 lab_01 增加 zrok tunnel 健康自动告警（观察 502 持续 3 分钟触发 ntfy 通知）
- 监控告警：隧道断开自动 ntfy 通知（NETWORK_BRIDGE.md 末项 TODO）

## TG 考古结果

- **TG_BOT_TOKEN_1** (`[REDACTED]`)：状态记录已失效（HTTP 401）
- **TG_BOT_TOKEN_2** (`[REDACTED]`)：状态记录曾有效；凭证必须轮换
- 无活跃聊天 / 群组（getUpdates 返回空）

## 任务清单

### ✅ 已完成
- [x] 解压 ACE 备份
- [x] 整理 mine-seed 结构
- [x] Git 推送私有仓库
- [x] Windows 适配层脚本
- [x] Task Scheduler 配置脚本
- [x] PowerShell 编码问题修复
- [x] lab_01 观测脚本
- [x] TG 考古 + 连通性测试

### ⏳ 进行中
- [ ] 你执行 `setup_tasks.ps1` 注册 Windows 计划任务
- [ ] 等 lab_01 SSH 通道恢复后修复 zrok 隧道

### 📋 下一步（你的工作区已就位）
- [ ] 验证 `observe_lab01.py` 持续运行
- [ ] 决定是走 lab_01 还是把矿场逻辑迁到本地跑
- [ ] 决定是否需要恢复 TG_BOT_TOKEN_1（如果继续用，建议从 @BotFather 重新申请）
