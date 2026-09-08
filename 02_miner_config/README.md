# 矿场环境变量

## miner_env.sh 核心配置
- 文件位置: /home/coze/miner_env.sh
- NIM API Keys: 文件内 NIM_API_KEYS 数组，共9个Key
- GitHub Token: inject via the local credential helper or `GITHUB_TOKEN`; never store it in this repository
- 工作模式: 减法/稳定模式(v5)
- 调度频率: 每4小时一班

## 约束系统
- 约束文件: /home/coze/routing_constraints.json
- 版本: v5，21条ACTIVE
- 核心保护: nim_mistral_675b(94%胜率标杆)、拦截低效worker

## 矿工存活(2026-06-29)
- 总存活: 21个 (GLM 3 / NIM 15 / GitHub 3)
- 离线: 11个 (含P3 AutoPromote淘汰的10个低胜率)
- 标杆: nim_mistral_675b (94%/52场)
- 分类标杆: gh_4omini (100%/提速55%至7.5s)

## 常用命令
- 手动跑矿场: source /home/coze/miner_env.sh && python3 /home/coze/miner_24h.py
- 手动信号: source /home/coze/miner_env.sh && bash /home/coze/signal_cron.sh
- 种子归档: bash /home/coze/seed_archive.sh
- 查看日志: cat /home/coze/mine_output/cron.log | tail -20
