## One API 配置
- 地址: http://localhost:3000 (host模式)
- 管理员: admin2/admin123、root/admin123（2026-06-21重置）
- 管理员token: 3ba2c187fe7f430cb56bdc5b396b8fb2 (重启后失效，用admin2/admin123重新登录获取session)
- 有效API token(miner-v2): jHhtKnCuHVriXUaHC992D9B645D44e8a9c901625A17fCd41
- 有效API token(miner-token): GfvnDi2dJuixs7jUDb3543D894E14eA483AeA4Da73290217，无限配额永不过期，2026-06-21实测可用
- 旧token(miner-unlimited): COMPROMISED-已禁用
- DB: /home/coze/one-api-data/one-api.db

## 活跃渠道 (2026-06-12更新)
- #55 Ollama-Local: key=ollama, base=http://172.17.0.1:11434, models=qwen2.5:0.5b,1.5b,7b (✅可用但1.5b只能搬运)
- #57 GitHub-Models-Free-v2: key=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, base=https://models.inference.ai.azure.com, models=gpt-4o-mini,gpt-4o,DeepSeek-R1,Llama-3.3-70B-Instruct (✅2026-06-21换新PAT)
- #7 OpenRouter-Free: key=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 (429限速可用)

- #2 Zhipu-GLM-Free: key=c4c766faaf974bfaba30f381ccc7b066.E7VUlQfxnMXnvVRx, type=16, base_url=空(One API自动拼), models=glm-4-flash,glm-4-air,glm-4-airx (✅全部可用)
- #59 NVIDIA-NIM-Free: key=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, base_url=https://integrate.api.nvidia.com(无/v1), 40RPM/号 (✅)
- #60 NVIDIA-NIM-Free-v2: key=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 (✅)
- #61 NVIDIA-NIM-Free-v3: key=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 (✅)
- NIM模型池(8号共享): deepseek-ai/deepseek-v4-pro, deepseek-ai/deepseek-v4-flash, meta/llama-3.3-70b-instruct, nvidia/llama-3.3-nemotron-super-49b-v1.5, nvidia/nemotron-3-ultra-550b-a55b, zai/glm-5.1, moonshotai/kimi-k2.6, openai/gpt-oss-120b, meta/llama-4-maverick-17b-128e-instruct, minimaxai/minimax-m2.7, mistralai/mistral-medium-3.5-128b, stepfun-ai/step-3.7-flash, google/gemma-4-31b-it
- #62 NVIDIA-NIM-Free-v4: key=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 (✅)
- #63 NVIDIA-NIM-Free-v5: key=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 (✅)
- #64 NVIDIA-NIM-Free-v6: key=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 (✅)
- #65 NVIDIA-NIM-Free-v7: key=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 (✅)
- #66 NVIDIA-NIM-Free-v8: key=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 (✅)

## 禁用/备用渠道
- #58 Groq-Free-v2: ❌403 IP封禁,解封后启用

## 其他Key
- R1 TG Bot Token: 8384310757:AAEhfTTMaYrV_n9hXFjBUMh2LdeeWkB-Czo
- TG Bot Token #2: 8446702999:AAHw51HYX_EwZhnzmJpQFUy734SnaZpzsCI
- R1 API Base: http://127.0.0.1:8004/api/v1/chat
- R1 Local Model: huihui_ai/deepseek-r1-abliterated:8b (Ollama)
- #67 NVIDIA-NIM-Free-v9: key=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 (✅新增2026-06-13, 包含minimaxai/minimax-m3多模态模型支持)
## 云电脑SSH配置
- Host: 140.143.124.211
- Port: 22
- User: root
- Password: KuangChang2026!

## 新增NIM Key (2026-06-13 19:37)
- NIM_KEY_10 (deepseek-v4-pro专用): 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
- NIM_KEY_11 (nemotron-3-ultra-550b专用): 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
- NIM_KEY_12 (step-3.7-flash专用): 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


## OpenRouter Free Tier (2026-06-13 20:00)
- Key: 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
- Base: https://openrouter.ai/api/v1
- 额度: 免费层，无限额但免费模型429限速严重
- 账号: is_free_tier=true, usage=0
- 26个免费模型: llama-3.3-70b, hermes-405b, nemotron-ultra-550b, qwen3-coder, gemma-4-31b等
- 问题: 1) 免费模型高峰期429限速 2) 部分模型404(guardrails/privacy设置需在Web UI调整)
- One API渠道: #72 OpenRouter-Free, priority=8
- 定位: 补充矿工，不依赖为主力；429时自动fallback到其他渠道
## ModelScope魔搭社区 (2026-06-14)
- Key: ms-7ab1f34e-efae-4a0b-a26d-5ed25eef9d07
- Base: https://api-inference.modelscope.cn/v1
- 已测试可用模型: Qwen/Qwen3-235B-A22B, deepseek-ai/DeepSeek-V3, ZhipuAI/GLM-4.5
- 免费额度: Qwen3-235B 500次/天, DeepSeek-V3 500次/天, GLM-4.5 500次/天, Qwen3-Coder 500次/天, DeepSeek-R1 200次/天, 总额度约1700次/天
- 定位: 矿场第四军团，新增免费Worker池
## 新增NIM Key (2026-06-14 19:10 老板提供)
- NIM_KEY_13 (minimaxai/minimax-m3专用): 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
- NIM_KEY_14 (stepfun-ai/step-3.7-flash专用): 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

## 新增NIM Key (2026-06-15 18:55 老板提供)
- NIM_KEY_K2.6 (moonshotai/kimi-k2.6专用): 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
- NIM_KEY_M2.7 (minimaxai/minimax-m2.7专用): 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
- 测试结果(2026-06-15): K2.6 canonical_v2✅ slice✅ 6-8s快准 → 进主力池; M2.7 canonical❌ slice✅ 45-120s慢 → 淘汰
## 已废弃
- AiHubMix Key: 401不可用，已移除

## Google Gemini (2026-06-16 老板提供)
- Key #1: AQ.Ab8RN6IhjKRabd7VkRFh1IBod3S_ade2QkJwDSrifNoTgmOXGg
- Key #2: AQ.Ab8RN6IFCwwdAZ7aUP4uBF_9QgzEN6k4cbOkIjVTqtuABjO0Hw (2026-06-19 新增)
- Endpoint: https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent
- 模型: gemini-flash-latest
- 定位: 待测试，Google免费层新矿工

## OpenRouter Key #3 (2026-06-16 老板提供)
- Key: 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
- Base: https://openrouter.ai/api/v1

## OpenRouter Key #4 (2026-06-20 老板提供)
- Key: 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
- Base: https://openrouter.ai/api/v1
- 新增免费模型: qwen/qwen-3.6-plus, google/gemini-flash-1.5:free, meta-llama/llama-3-8b-instruct:free, mistralai/mistral-7b-instruct:free
- 定位: 待测试，补充OpenRouter矿工池

- TG API: api_id=38398440, api_hash=3460f304c16a186c2300debc673b2ed0 (App:树莓派)
- TG用户手机号: +85592538691
- TG两步验证密码: Qq364828
- TG Session文件(桌面端): C:\Users\USER\tg_collector\sessions\tg_saved_v2.session

## InStreet (实例街)
- Agent ID: 2de5947b-390a-4672-9820-9da406221752
- Username: fengzi
- API Key: sk_inst_7fb8e8cb16c1d46e4752d73e3279757c
- BASE_URL: https://instreet.coze.site
- 注册时间: 2026-06-19

## Replicate (2026-06-19)
- API Token: r8_XNr05HkdruoM2TpKcjtZF3Sj3R416xE4eXuTS
- Base: https://api.replicate.com/v1
- 可用模型: black-forest-labs/flux-2-pro (图片生成)
- 定位: 图片生成专用，免费额度

- API易 Key #1: sk-xQrs9IDbjK2LJpFh1d947b41A1B449A4Be0dD8Bf3a7cDc8b (base: https://api.apiyi.com, 310模型代理，含GPT-4.1/DeepSeek/Gemini/Qwen/Claude等，2026-06-20新增)
## 新的GitHub Fine-Grained PAT (2026-06-21新增)
- Token: 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
- 权限：All repositories, Administration: Write, Contents: Write, Metadata: Read-only
- 用途：mine-seed私有仓库操作，已成功完成首次提交和多次推送
## Cloudflare (2026-06-22 21:37)
- Account ID: 0259e0fefdceeaddc87a4e5ed675487f
- Tunnel Token: odd-sun-94e8
- API Token: cfat_IQRtQQyGuybl8nTLgafyRz4opSiNj0GMawMGNFBe1385e2cd
- R2 Access Key ID: 5ac7027e078590ba17dd33366c5c1381
- R2 Secret Access Key: 8f3ef0ff541abc995dfc5f1f79c6f5d2236553d4dde8b2593f74508e02e4caf8
- R2 S3 Endpoint: https://0259e0fefdceeaddc87a4e5ed675487f.r2.cloudflarestorage.com
## 公网桥 R1 Bridge Key (2026-06-23)
- Key: e8a43023a7873cb5a67db8d6e92b483c
- 请求头字段: X-R1-Bridge-Key
- 白名单路径: https://api.zhangningjing.com/v1/ (OpenAI兼容)
## Agent World
- username: fengzi-l0
- api_key: agent-world-cb6106df243ee933526d6548c84ce75a928a091556feef86
- agent_id: 349a37d8-930c-4aca-b2ad-10a0c2b51887
- 注册时间: 2026-06-24 13:16 CST
- 验证方式: Header `agent-auth-api-key: <key>` 或 `Authorization: Bearer <key>`
## R1考古及其他分析任务 — API Key 使用规则 (2026-06-25 分配)

### 优先级规则（由高到低 fallback）
1. **API易（主力推荐）**：优先使用，模型多、稳定，覆盖310+模型
   - Key: sk-xQrs9IDbjK2LJpFh1d947b41A1B449A4Be0dD8Bf3a7cDc8b
   - Base: https://api.apiyi.com
   - 覆盖模型：GPT-4.1、DeepSeek-V3、Gemini、Qwen、Claude 等
   - 定位：主力分析模型，适合代码分析/文档生成/源码解读

2. **OpenRouter #4（备用）**：API易429限速或挂了时 fallback
   - Key: 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
   - Base: https://openrouter.ai/api/v1
   - 免费模型：qwen/qwen-3.6-plus, google/gemini-flash-1.5:free, meta-llama/llama-3-8b-instruct:free 等

3. **Google Gemini #2（备用免费）**：前两者都不可用时兜底
   - Key: AQ.Ab8RN6IFCwwdAZ7aUP4uBF_9QgzEN6k4cbOkIjVTqtuABjO0Hw
   - Endpoint: https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent

### 使用约束
- 绝不在 commit/gist/public 中暴露这些 Key
- 共享额度，别一次性打满日调用
- R1 考古分析优先用这些 Key 调模型做源码解读，不再依赖矿场资源
## GitHub Models 下苦力专用 PAT (2026-07-02 老板提供)
- Token: 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
- 用途：调用GitHub Models免费API，矿场下苦力专用
- 特征：无期限，不限量
- 定位：替换旧GitHub渠道PAT，或作为新GitHub渠道接入
## GitHub Models 双账号轮询（2026-07-02）
- **渠道#1 "GitHub-Models-v1-web账号"**：旧PAT (zhangapple21-web), weight=1 ✅启用
- **渠道#57 "GitHub-Models-v2-新账号"**：新PAT (zhangapple21), weight=1 ✅启用
- **轮替策略**：One API weight=1 自动轮询，两个账号独立免费额度 → 日调用量翻倍
## Groq API（2026-07-02 备份记录）
- **Key**: `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`
- **Base URL**: https://api.groq.com/openai
- **One API渠道**: #58 Groq-Free-v2（当前状态=2 禁用，原因：国内IP 403封禁）
- **可用模型**: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768, gemma2-9b-it
- **定位**: 海外环境部署后启用，国内IP被Groq封禁
- **提示**: 若迁移到海外环境，启用渠道#58，改status=1、weight设1即可
## Sixfinger API (2026-07-02)
- **Key**: sixfinger_jv5ts2elbbsgxb87f32g
- **Base URL**: https://api.sixfinger.live/v1 (OpenAI兼容)
- **One API渠道**: #97 Sixfinger-Free (status=1 ✅启用, weight=1)
- **Free计划**: 1000请求/月, 10万token/月, 10 RPM
- **可用Claude模型**: claude-sonnet-4-6, claude-haiku-4-5, claude-sonnet-4-5, claude-sonnet-4
- **其他免费模型**: gpt-5, gpt-5.4, gpt-5.5, glm-5, kimi-k2.7-code, deepseek-v3.2, deepseek-v4-flash 等20个
- **注册邮箱**: mine-ops@coze.email (被拒，老板用自己的邮箱注册)
- **定位**: 补充矿场Claude系算力，用于canonical_v2验证或约束系统评审
## SerpAPI (2026-07-02)
- **Key**: e11b42995b047b7ffb5538bc56a5885128eb352f731d65fb6c6682c9b927a07a
- **Base URL**: https://serpapi.com/search
- **Free计划**: 250次搜索/月, 50次/小时吞吐量
- **定位**: Google搜索API备选，需要真实Google搜索结果时使用
- **来源**: 老板给的免费Key

## 神稳AI (SWA) — 2026-07-16 老板提供
- **Key #1**: sk-or-v1-sUwZwRuo0c6-5FSz_mIjWWcbiMuB4Qa7z2bZaTJF9Hs
- **Key #2**: (留空，备用)
- **Base URL**: https://api.shenwenai.com/v1/chat/completions
- **模型**: gpt-5.4-mini
- **定位**: 新增矿工，补充国内AI渠道

## Perplexity API — 2026-07-16 老板提供
- **Key #1**: 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
- **Key #2**: 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
- **Base URL**: https://api.perplexity.ai/chat/completions
- **模型**: sonar
- **定位**: 海外AI渠道，补充知识库能力
## Kimi (Moonshot AI) API — 2026-07-02

### 海外账号（platform.kimi.ai）
- **URL**: https://api.moonshot.ai/v1
- **旧Key**: sk-9F1YJJQYAZoBiZzQFE75IDeuIcP7oWzdfmvUY6NBACwj0Sj4
- **新Key**: sk-1jBWEWW4GxskxaIXZGREiauTRjmCAbNtgX8c0THi5fsxd1oW
- **状态**: 认证通过，余额不足("insufficient balance")

### 国内账号（platform.moonshot.cn）
- **URL**: https://api.moonshot.cn/v1（国内IP直连✅）
- **Key**: sk-c1qODqN3Gv2j27X8xTfraJv32LEkLARMfZdTNiP6PYjASpC6
- **状态**: 认证通过，余额0（available_balance=0，需充值）
- **账户ID**: org-0bcddd8419e04dbd91efa755c97d3458

### 可用模型（通用）
kimi-k2.7-code, kimi-k2.7-code-highspeed, kimi-k2.6, kimi-k2.5, moonshot-v1系列(8k/32k/128k), moonshot-v1-vision系列

### 定位
三个Key都有效但均无余额，需充值后才能用。国内账号延迟更低，优先考虑。不急着配One API。
## 新增NIM Key (15)
- NIM_KEY_15: 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
## 新增NIM Key (16)
- NIM_KEY_16: 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

## === 密钥自动同步区 (Auto-Synced) ===
### 智谱 GLM
- GLM_KEY: c4c766faaf974bfaba30f381ccc7b066.E7VUlQfxnMXnvVRx
- GLM_BASE: https://open.bigmodel.cn/api/paas/v4/chat/completions
- GLM_MODEL: glm-4-flash

### NVIDIA NIM
- NIM_KEY_1: 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
- NIM_KEY_2: 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
- NIM_KEY_3: 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
- NIM_KEY_4: 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
- NIM_KEY_5: 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
- NIM_KEY_6: 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
- NIM_KEY_7: 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
- NIM_KEY_8: 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
- NIM_KEY_9: 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
- NIM_KEY_10: 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
- NIM_KEY_11: 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
- NIM_KEY_12: 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
- NIM_KEY_13: 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
- NIM_KEY_14: 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
- NIM_KEY_15: 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
- NIM_KEY_16: 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
- NIM_BASE: https://integrate.api.nvidia.com/v1/chat/completions
- NIM_MODEL: meta/llama-3.1-8b-instruct

### GitHub Models
- GH_MODELS_KEY: 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
- GH_MODELS_BASE: https://models.inference.ai.azure.com/chat/completions
- GH_MODELS_MODEL: gpt-4o-mini

### OpenRouter
- OPENROUTER_KEY: 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
- OPENROUTER_BASE: https://openrouter.ai/api/v1

### SambaNova
- SAMBANOVA_KEY: 820feeb9-0201-4312-8c0e-900206a4d2b9
- SAMBANOVA_BASE: https://api.sambanova.ai/v1

### HuggingFace
- HF_KEY: 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

### Perplexity
- PPLX_KEY_1: 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
- PPLX_KEY_2: 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
- PPLX_BASE: https://api.perplexity.ai/chat/completions
- PPLX_MODEL: sonar

### 神稳AI (SWA)
- SWA_KEY_1: sk-or-v1-sUwZwRuo0c6-5FSz_mIjWWcbiMuB4Qa7z2bZaTJF9Hs
- SWA_BASE: https://api.shenwenai.com/v1/chat/completions
- SWA_MODEL: gpt-5.4-mini

### Telegram
- TG_API_ID: 38398440
- TG_API_HASH: 3460f304c16a186c2300debc673b2ed0
- TG_BOT_TOKEN_1: 8384310757:AAEhfTTMaYrV_n9hXFjBUMh2LdeeWkB-Czo
- TG_BOT_TOKEN_2: 8446702999:AAG71qiArYsF7p8VFXQKEs1EGpC0mX7QJ8Y
- TG_CHAT_ID: 5016609451

### One API
- ONEAPI_ADMIN_TOKEN: 3ba2c187fe7f430cb56bdc5b396b8fb2
- MINER_API_BASE: http://localhost:3000/v1/chat/completions

### 其他API
- APIYI_KEY: sk-xQrs9IDbjK2LJpFh1d947b41A1B449A4Be0dD8Bf3a7cDc8b
- SIXFINGER_KEY: sixfinger_jv5ts2elbbsgxb87f32g
- SERPAPI_KEY: e11b42995b047b7ffb5538bc56a5885128eb352f731d65fb6c6682c9b927a07a

### Felo搜索
- FELO_API_KEY: fk-4ssg3QfyEoZQqugpxk3v8pAe4y0mhlk3Jlpwpys7z39gMq3C
- FELO_BASE_URL: https://api.felo.ai/v1

### 变量名别名
- ZHIPU_KEY: c4c766faaf974bfaba30f381ccc7b066.E7VUlQfxnMXnvVRx
- ZHIPU_BASE: https://open.bigmodel.cn/api/paas/v4/chat/completions
- GITHUB_PAT: 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
- GITHUB_BASE: https://models.inference.ai.azure.com
- GH_PAT: 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
- GITHUB_TOKEN: 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

## === 密钥自动同步区结束 ===