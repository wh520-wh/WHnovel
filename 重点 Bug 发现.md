# 重点 Bug 发现

> 本文档只记录已确认的 Bug，暂不考虑修复方案。
> 每个发现均经"子代理对抗性审查 + 主循环一眼赞同"两层判定（见各节"子代理审查结论"）。

---

## Bug #1：长期记忆 memory_log 从未接通正文生成，导致长对话遗忘 ✅ 已修复（2026-06-22，合并入 main 至 b89c214）

**位置**：
- `backend/app/api/chat_stream.py` `_build_stream_prompt_sections`（约 119–158 行）
- `backend/app/api/chat_storage.py` `_build_prompt_sections` / `_build_messages`（约 169–288 行）

**现象**：
正文生成路径构建 system prompt 时，注入了全局/故事系统提示词、世界观、文笔规则、叙事规则、长度规则、输出规则、防注入规则，但**没有注入 `archive.memory_log`**。

历史消息构建只取每条消息的 `content` 纯文本，且只取最近 `context_length`（默认 10）条。

`memory_log` 最多保留 100 条，但只在两处被读取：
1. tail 二次调用 `_build_tail_messages`，作为 `recent_memory` 只取**最近 5 条**，用途是"提取新 memory_update"；
2. state-broadcast 端点展示。

即：累积的 100 条长期记忆**完全不参与正文生成**。

**影响**：
- 互动小说从**第 11 轮起**就开始遗忘早期关键事件（获得道具、立下承诺、结识角色）。第 50 轮的正文看不到第 1 轮发生的事。
- 前端 `ArchiveMemoryPanel.vue` 标题"记忆更新"、`aria-label="记忆更新列表"`，已向用户营造"AI 在记这些事"的预期，但正文生成对这些记忆完全失明——**承诺与实现存在缺口**。
- 叙事连贯性是互动小说的核心体验，长对话遗忘属于体验级缺陷。

**证据**：
- `chat_stream.py:186-203` 历史只取 `context_length` 条纯 content。
- `chat_storage.py:271-285` 同上，且不读 `state_snapshot`/`story_state` 字段。
- `chat_storage.py:291-314` `_build_tail_messages` 用 `recent_memory[-5:]`。
- `models.py:65` `memory_log` 注释"记忆更新日志（按时间追加）"。
- `ArchiveMemoryPanel.vue:3,5` UI 已向用户展示记忆功能。
- `narrative.py:28` 排除清单是"选项、状态和标签"，**不含"记忆"**——不构成对注入记忆的设计禁止。

**子代理审查结论**：成立，无致命缺陷。子代理验证全部技术事实为真；`narrative.py:28` 的排除清单不含"记忆"且为输出禁令非输入白名单；memory 是自然语言句子不撞 body pollution guard（guard 只作用于模型输出）。唯一要害为 memory_log 质量未受控（tail 提取无去重/合并/纠错），需配套约束，但不否定其成立。

**备注**：配套缺陷——`_TAIL_META_PROMPT`（`chat_tail.py:24`）对 `memory_update` 无去重/合并/纠错约束，`_persist_exchange`（`chat_storage.py:346-347`）为纯追加 + 截断到 100 条。即使接通正文，记忆本身可能堆积冗余/矛盾条目。

**修复记录**（fix/bug-1-5-4 分支，TDD + 两阶段审查通过，已合并 main）：
- 仅在两条正文路径（流式 `_stream_chat_response`、非流式 `_generate_chat_response`）注入【长期记忆】section，选项/图片/状态播报三处 `_build_messages` 零改动（路径隔离）。
- 新增配置闸 `UserSettings.memory_inject_count`（默认 50，0-100，0=关闭）+ v27 迁移 + settings 全链路夹紧。
- 记忆清洗只作用于注入副本、绝不写回存储；硬字符上限 12000 从最旧丢（N=50 最坏 10000 不触发上限，保住第 1 轮召回）。
- 写入侧 `_persist_exchange` 保守去重（`_dedupe_memory_updates`：子串新条丢弃、超集保留、绝不删已存事实——绝对不变量）。
- tail 提示词重写 memory_update 约束（去纠错授权、加"重复不记/无新增返[]/不得编造"）。
- 可观测日志 `memory_inject` / `memory_persist`。
- 测试：test_memory_injection.py（23 用例）+ test_memory_settings.py。backend 236 全绿。

---

## Bug #2：分布式锁 release 无 owner 校验（经审查降级为中低危，非重大）

> ⚠️ 经子代理对抗性审查，此缺陷**代码真实但默认休眠，降级为中低危潜在 bug，不构成"重大发现"**。保留记录以备查。

**位置**：
- `backend/app/redis_client.py` `lock_acquire`（约 111–122 行）、`lock_release`（约 124–136 行）
- `backend/app/api/chat_locks.py` `_acquire_per_archive_lock`（约 24–61 行）

**现象**：
- `lock_acquire` 用 `SET key "1" NX EX ttl`，value 固定 `"1"`，不存 owner token。
- `lock_release` 用 `self._client.delete(key)`，无条件删除，不校验归属。
- 经典竞态：进程 A 持锁超 TTL 自动过期 → 进程 B 拿锁 → 进程 A 的 finally 执行 release 删掉 B 的锁 → 并发互斥被破坏。

**影响（经审查修正）**：
- 流式锁 TTL=60s（`chat_stream.py:101`）、图片锁 TTL=120s（`chat_stream.py:87`），tail 调用 timeout=60s（`chat_stream.py:336`）。
- 若触发，同一会话并发两次正文生成 → 消息重复落库、状态相互覆盖。
- **但**：Redis 默认不安装（`requirements.txt:9` 注释掉），出厂配置走 threading fallback，bug 完全休眠；实际单进程单 worker 部署（`run.py` reload、`start.ps1` 无 `--workers`）；前端 `sending` 标志在整个流含 tail 期间为 true（`useChatStream.ts:148-162,293-298`），堵死单客户端 double-send 主触发向量；有缺陷的 Redis 路径零真实语义测试覆盖。

**证据**：
- `redis_client.py:118` value 固定 `"1"` 无 token；`redis_client.py:132` 裸 delete 无校验。
- `chat_locks.py:41-53` Redis 可用时旁路 threading 锁（单进程 + Redis 可用即可触发，比原推断更易达，但仍需默认关闭的 Redis 被开启）。
- `requirements.txt:9` `# redis>=5.0  # 可选`；`conftest.py` `REDIS_PORT=0`。

**子代理审查结论**：**降级否决其"重大性"**。代码缺陷真实（教科书级 Redis 锁反模式，确认无漏看的 token/Lua CAS 校验），但困在默认关闭、可选、单进程本地部署的代码路径里，出厂配置下休眠，主触发向量被前端 `sending` 堵死，无实际损坏报告。判为低/中危潜在 bug，非重大生产缺陷。

---

## Bug #3：整个后端 API 零认证/零授权，admin 端点对任何能访问后端的人完全开放

**位置**：
- 所有 router：`backend/app/api/admin.py`、`settings.py`、`archives.py`、`stories.py`、`chat_router.py`、`images.py`
- 入口 `backend/app/main.py`；启动 `backend/run.py`、`start.ps1`

**现象**：
1. 所有端点的依赖只有 `Depends(get_db)`（`get_db` 是纯 SQLAlchemy session yielder，`database.py:28-33`，无任何鉴权）。全仓 grep `HTTPBearer|Authorization|require_admin|verify_token|jwt|get_current_user|x-api-key` 在入站路径**零命中**（唯一命中的 `chat_api_adapter.py:217,225` 是出站调用 LLM 时设的请求头）。
2. `main.py` 只加了 CORSMiddleware，无任何鉴权 middleware、无 `TrustedHostMiddleware`、无路由级 `dependencies=`。
3. admin 危险端点全部裸奔：
   - `system/shutdown`（`admin.py:300-314`）：**连 `get_db` 都没有，零依赖**，任何人可远程关停后端+前端。
   - `metrics/reset`（`admin.py:824-831`）：仅校验 `confirm_text == "RESET_METRICS"`，而该字符串是源码硬编码公开常量（`admin.py:25`），是防误触不是密钥。
   - `delete_model`/`create_model`/`update_model`：可删模型使系统瘫痪，或把 `api_base_url` 改指向攻击者服务器——后续聊天的 `Authorization: Bearer <受害者key>` 会被发往攻击者，**窃取 API key**。
   - `config-backup/import`（`admin.py:281-297`）：导入配置覆盖模型与设置。
   - `test_model`（`admin.py:172-225`）：用已解密的存储 key 发起出站调用，消耗受害者付费 key。
4. README "浏览器控制台输 `localStorage.admin_mode = '1'` 开管理员入口" 仅切换前端 UI 显隐，后端 `admin_mode` grep **零命中**，完全不校验。
5. **后端绑定 `0.0.0.0:8000`**（`run.py:6` `host="0.0.0.0"`；`start.ps1:175` `--host 0.0.0.0`），监听所有网络接口。`.env.example` 无 HOST 配置项，用户无法通过 env 改回 127.0.0.1。

**影响**：
- 同一局域网/同网段任何设备（家里/咖啡店 WiFi、云 VM）都能直接访问后端 8000 端口调用 admin 端点——**LAN 内无条件即时可达**，无需任何凭证。
- 可致：API key 窃取（财务+账号风险）、本地故事/存档/指标全毁、远程关停系统、篡改系统提示词注入恶意指令。
- CORS 只允许 localhost 前端，但 CORS 仅管浏览器跨域，**不阻止 curl/脚本/其他服务器直连 8000 端口**，攻击者根本不需要前端。
- 项目开源 MIT、README 鼓励 clone 部署、有移动端适配 UI 暗示多设备访问——上云 VM 或手机访问场景下即全网暴露。

**证据**：
- `main.py:38-49` 仅 CORSMiddleware，无鉴权 middleware。
- `admin.py:300-314` system/shutdown 零依赖；`admin.py:25,824-831` metrics/reset 用公开字符串；`admin.py:92-143` create/update_model 可改 api_base_url。
- `database.py:28-33` get_db 无鉴权。
- `run.py:6` / `start.ps1:175` host=0.0.0.0；`.env.example` 无 HOST 项。
- `README.md:36,47-51` 文档化 `python run.py` 启动、localStorage.admin_mode、无安全/部署加固说明。

**子代理审查结论**：成立。子代理穷尽反驳（漏看鉴权层？— 路由级/全局/middleware override 均无；0.0.0.0 仅开发默认？— 无 env 覆盖、无部署文档要求改、文档化启动路径即 0.0.0.0；CORS 限制？— 不阻非浏览器客户端；纯本地玩具？— 真正本地工具会绑 127.0.0.1 而本项目刻意 0.0.0.0 + 移动多端 UI）均失败。在开源 + 0.0.0.0 默认且无 override + 持有付费 LLM key + 移动多端 UI 的实际部署姿态下，零鉴权构成真实且即时的暴露，判为重大。

---

## Bug #4：crypto.decrypt 解密失败静默返回空字符串，违背自身 docstring，密钥漂移不可诊断不可恢复 ✅ 已修复（2026-06-22，合并入 main 至 b89c214）

**位置**：`backend/app/crypto.py` `decrypt`（约 87–118 行）、`_load_key`（约 23–52 行）

**现象**：
1. `decrypt` 三个分支：
   - 非合法 base64 → 当作明文返回原值（兼容加密启用前的明文，`crypto.py:104-106`）；
   - 合法 base64 且长度≥13 → 取前 12 字节 nonce 解密（`crypto.py:111-115`）；
   - **解密异常 → `return ""`**（`crypto.py:116-118`，仅 `logger.error` 进服务端日志，不抛异常、不返回原密文）。
2. `decrypt` 的 docstring（`crypto.py:88-93`）白纸黑字承诺："If the input is not valid base64 **or decryption fails (e.g. encryption key drift)**, the input is assumed to be plaintext already and **returned as-is**."——即文档承诺"密钥漂移原样返回输入"，**但实际解密失败分支返回 `""`，代码违背自身契约**。
3. `_load_key`：优先 ENCRYPTION_KEY 环境变量；其次 .env 文件；**都没有时从机器 MAC 地址派生**（`uuid.getnode()` + sha256，`crypto.py:44-52`）。ENCRYPTION_KEY 默认空、无启动时自动生成逻辑 → 默认走机器派生。
4. 调用方把 `decrypt` 返回的 `""` 直接当 key 用，无兜底：`admin.py:198-199/245-246`、`chat_models.py:54-55`、`image_generation.py:106-110/143-147/185` 均 `api_key = decrypt(raw_key) if raw_key else ""` → 塞进 Authorization 头 → 远端 401 → 前端显示"API Key 错误"。

**影响**：
- 用户未设 ENCRYPTION_KEY（默认情况，且本产品目标用户是非技术小白，永远不会设、永远看不到 `.env.example` 的警告）→ 密钥由机器 MAC 派生 → 换机器/重装系统/迁移部署 → 所有已加密的 ModelConfig.api_key/image_api_key 解密失败 → `decrypt` 返回 `""` → 所有模型调用 401 失败。
- **致命的是症状误导**：用户看到"API Key 错误"，会以为是 key 配错反复重填，而真实原因是密钥漂移；旧的加密记录若无原机器已永久无法恢复。
- `decrypt` 返回 `""` 把本可被识别的致命故障吞掉，伪装成普通的"key 为空/错误"，显著加剧诊断与恢复难度。
- 无恢复路径：`migrations.py` 全文（v1–v26）无任何 api_key 重加密迁移；`config_backup.py:38,46` 导出的是原始加密 blob（未 decrypt），备份机器绑定，跨机器导入仍解不开。

**证据**：
- `crypto.py:116-118` 解密失败 `return ""`；`crypto.py:88-93` docstring 承诺漂移原样返回——代码违背契约。
- `crypto.py:44-52` 机器 MAC 派生密钥；`.env.example:3-4` ENCRYPTION_KEY 默认空。
- `admin.py:198-199,212,245-246,259` 调用方无兜底 + 误导文案"API Key 错误"。
- `migrations.py` 无 key 重加密迁移；`config_backup.py:38,46` 备份机器绑定。

**子代理审查结论**：成立（修正措辞后）。子代理确认未混淆"base64 解码失败返回原值"与"解密异常返回空串"两个分支；关键加强点为 docstring 明确把"encryption key drift"列为应优雅处理的场景却返回 `""`，代码违背自身契约。分层裁定：(a) 密钥漂移丢 key 本身是已知设计取舍（`.env.example` 已警告），但对终端小白用户该警告不可见，等于未告知；(b) `decrypt` 静默返回 `""` 是独立于漂移本身的真 bug——吞掉致命错误、违背契约、产生误导症状、无恢复路径。判为中到重大，对默认不设 ENCRYPTION_KEY 的小白用户群触发面广、不可恢复、症状误导。

**修复记录**（fix/bug-1-5-4 分支，TDD + 两阶段审查通过，已合并 main）：
- `crypto.py` 新增 `decrypt_safe(ciphertext) -> tuple[str, bool]` 承载三分支 + is_drift 信号；`decrypt` 重写为委托（`return decrypt_safe(...)[0]`），失败分支 `return ""`→`return ciphertext` 兑现 docstring 契约，`logger.error`→`logger.warning`。不删 nonce/ct 行，不动 encrypt。
- admin.py 两个测试端点（test_model / _test_image_model）迁移到 decrypt_safe，401 时按 is_drift 分流文案 + 回传 is_drift 字段。**"仅失败时归因"**：drift=True 不短路、照常发请求（合法明文 key 会 200，is_drift 永不浮现，吸收启发式误判）。
- chat_models.py / image_generation.py 源码不动（外科范围决策，保住 test_structured_output_robust.py 5 处 patch 与"adapter 不 import decrypt"不变量）。
- 前端 `api/index.ts` 加 `is_drift?: boolean`；`ModelManage.vue` handleTest 漂移时弹 ElMessageBox.alert 强提示（warning 黄色，含恢复路径——重填 Key 保存即自愈）。
- 范围外附修：pre-existing build-blocker `ModelManage.vue:207` inline `@click` 多语句解析错误（vite v8 下 `/` 被当除法），加分号修复，单独 commit。
- 测试：test_crypto.py（新建）+ test_admin_model_api_mode.py 扩展 + test_image_generation.py 漂移路径用例。backend 236 全绿 + 前端 build 绿。

---

## Bug #5：draft/state_broadcast/图片等非对话消息混入正文 history，且 Claude/Gemini 适配器不合并连续同角色，导致 Claude 用户流式 400 硬报错 ✅ 已修复（2026-06-22，合并入 main 至 b89c214）

**位置**：
- 正文 history 查询：`backend/app/api/chat_stream.py:189-203`、`backend/app/api/chat_storage.py:271-285`（`_build_messages`）
- 非对话消息插入：`backend/app/api/chat_router.py:439-451`（图片生成 lone-assistant）、`chat_router.py:621-624`（状态播报 lone-assistant）、`chat_storage.py:417-427`（draft）
- 适配器：`backend/app/api/chat_api_adapter.py:119-150`（`_body_claude_messages`）、`153-186`（`_body_gemini`）

**现象**：
1. 正文生成读 history 的查询只按 `archive_id` 过滤、按 `created_at` 倒序 `limit(context_length)` 取最近 N 条，**不过滤 is_draft、不过滤 is_state_broadcast、不过滤纯图片消息**。全后端 grep `is_draft ==` / `is_state_broadcast ==` 用于查询排除处 **零命中**——这两个 flag 只在写入时 SET，从未用于查询排除。
2. 三类非对话消息 role 均为 `"assistant"`：
   - **draft 草稿**（`is_draft=1`，`_persist_draft_exchange`）：流式失败时落库的部分正文。
   - **状态播报**（`is_state_broadcast=1`，`chat_router.py:621-630`）：content 是"属性 | 属性值"键值对文本，非小说正文。每次用户点"生成状态播报"就插入一条。
   - **图片消息**（`chat_router.py:439-451`）：单条 assistant，content 为空，无配对 user。
3. 这些消息被读进下一轮 system prompt 的 history 作为"assistant 回复"，打破 user/assistant 严格交替，制造连续 assistant。
4. `_body_claude_messages`（`chat_api_adapter.py:119-150`）把 user/assistant 序列**原样**塞进 Anthropic Messages API 的 `body["messages"]`，**不合并连续同角色、不丢弃首条非 user**。`_body_gemini` 同样原样塞 `contents`。
5. **附带语义错位**：UI 文案写"轮"（`Settings.vue:412` `{{ form.context_length }} 轮对话记忆`、`SettingsMobile.vue:142` `{{ form.context_length }} 轮`），后端却把 `context_length` 当消息条数 `.limit(context_length)`。1 轮 = user+assistant = 2 条，故默认 10 → 实际 5 轮，用户预期与实际恒差 2 倍。

**影响**：
- **Anthropic Claude 用户硬报错**：Anthropic Messages API 硬性要求首条非 system 消息必须是 `user`、角色严格交替，否则 **400**。一旦用户在会话里生成过一次状态播报或图片（lone-assistant 插入），该消息永久留在 history，后续只要落在最近 `context_length` 条内，流式直接 400 失败、用户看到"模型调用失败"。Gemini 端同理（要求交替）。这是默认设置下可达的硬故障，非"模型容忍"。
- **叙事污染**（对容忍交替的 OpenAI 兼容端点）：draft 残缺正文、state_broadcast 键值对文本混进 history 作为既成叙事事实，AI 后续基于错误前提/异质内容续写，污染叙事风格与连贯性。前端 `useChatStream.ts:374` draft 错误文案还主动鼓励"正文已保留，可继续输入"，保证 draft 被读回下一轮。
- 前端撤回机制（`delete_last_ai_message` 只删最新一条 assistant）覆盖不到沉在中间的 draft/state_broadcast，永久残留直到被挤出 context_length 窗口。
- 语义错位影响全体用户记忆深度预期。

**证据**：
- `chat_stream.py:189-195` / `chat_storage.py:271-277`：history 查询仅 `filter(archive_id).order_by(created_at.desc()).limit(N)`，无 is_draft/is_state_broadcast 过滤。
- 全后端 grep `is_draft ==|!=`、`is_state_broadcast ==|!=` 查询排除处零命中；flag 仅在 `chat_storage.py:357/408/425`、`chat_router.py:448/629` 写入。
- `chat_api_adapter.py:130-142` `_body_claude_messages` 不合并连续同角色、不校验首条；`_body_gemini:164-174` 同理。
- `chat_router.py:439-451` 图片 lone-assistant、`chat_router.py:621-630` 状态播报 lone-assistant。
- `Settings.vue:412` / `SettingsMobile.vue:142` UI 文案"轮"；`models.py:128` `context_length` 默认 10。

**子代理审查结论**：成立。子代理逐条验证核心机制为真，并纠正候选两处描述：(a) body pollution 拦截的内容不落 draft（draft 仅来自 stream/schema/tail 三类失败）；(b) tail 失败的 draft 是完整正文（危害小），真正有害的是 stream 中途失败的半句截断 draft。关键独立判定：纯截断配对在严格交替 + 偶数 context_length 下首条是 user（不触发），但 lone-assistant 插入（图片/状态播报）打破交替使 Claude 用户默认可达硬报错——这部分重大性源于 I 的混入 + Claude 适配器不防御的协同。候选 J（纯截断配对错乱）经审查建议并入 I（同根因：history 不过滤非对话消息 + 适配器不防御）。语义错位子论点 always-on 中等。综合判成立且重大（对 Claude/Gemini 用户为硬故障，对 OpenAI 兼容用户为叙事污染）。

**修复记录**（fix/bug-1-5-4 分支，TDD + 两阶段审查通过，已合并 main）：
- 三层纵深防御：
  - **L1 源过滤**：新增共享 helper `_query_dialogue_history(db, archive_id, limit)`，过滤 `is_draft==0 AND is_state_broadcast==0 AND content!=''`（单一 `content!=''` 同时排除 draft/broadcast/纯图片），流式与非流式两处 history 查询统一接入、删各自本地 reverse。
  - **L2 适配器兜底**：新增幂等 `_sanitize_dialogue_turns`（合并连续同角色 \n\n / 丢空+warning / 首条 assistant 补占位 user / 全空补占位 / system 合并为单条 leading system，对干净交替输入 no-op），四个 body builder（openai_chat / openai_responses / claude_messages / gemini）首行接入。
  - **L3 计数修正**：`_count_rounds_without_plot_label` 两个 COUNT filter 追加同三条件，防 plot_label 过早强制。
- 明确不做（外科纪律）：不改 context_length 语义为"轮数"、不动前端、不新增 UpstreamBadRequestError、不改 `_request_model_once`/`_stream_model_once` 抛错方式（保住 chat_models response_format 400 重试）。
- 后续重构：抽取 `_dialogue_message_filters()` 共享谓词（DRY）。
- 测试：test_chat_storage.py + test_chat_api_adapter.py + test_chat_stream_option_pollution.py 扩展。backend 236 全绿。
- **遗留（Minor，未修）**：context_length "轮"文案与"条"语义错位（Bug #5 第 5 点）推迟独立 PR；Bug #2/#7/#8/#9 等其它发现未在本轮处理。

---

## Bug #6：config_backup 导出/导入丢失 v17 之后新增的全部 ModelConfig 字段，恢复备份后 ComfyUI/自定义 API 模式静默失效 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支，治本重构）

**位置**：`backend/app/config_backup.py` `build_backup_payload`（约 24–81 行）、`_normalize_model_payload`（约 130–157 行）、`import_backup_file`（约 160–300 行）

**现象**：
1. `build_backup_payload` 导出 ModelConfig 时只取 14 个字段：id, name, model_id, api_base_url, api_key, enabled, priority, price_input_per_1k, price_output_per_1k, pricing_unit, model_type, image_api_base, image_api_key, ssl_verify。
2. 对照 `models.py` ModelConfig（约 140–164 行），**以下 6 个字段在导出和导入中均被遗漏**：
   - `api_mode`（v17）
   - `image_api_mode`（v17）
   - `image_workflow_template`（v22）
   - `temperature`（v19）
   - `max_tokens`（v19）
   - `response_format_mode`（v24）
3. `_normalize_model_payload` 导入时同样只重建上述 14 字段，6 个缺失字段不处理。
4. 导入分两路径：新建 `db.add(ModelConfig(id=..., **model_data))` 缺失字段取 DB 默认值（api_mode→`openai_chat_completions`、image_api_mode→`openai_images`、image_workflow_template→NULL、temperature→NULL、max_tokens→NULL、response_format_mode→`json_schema`）；更新 `setattr(existing, field, value)` 只覆盖 14 字段、缺失字段保留旧值。**最坏情况是重装/迁移后 DB 为空 → 新建 → 字段丢失**，而这正是备份功能的主用途。
5. `migration_version: 2` 硬编码（`config_backup.py:57`），而实际 `migrations.py:10 SCHEMA_VERSION = 26`——版本号停旧版，`import_backup_file` 全程不检查版本、无兼容逻辑、无旧版本补字段。`run_migrations` 只做 `ALTER TABLE ADD COLUMN DEFAULT`，不读备份 JSON，无法回填。

**影响**：
- **ComfyUI 图片模型失效**：用户精心配置 `image_api_mode='comfyui'` + 大段 workflow JSON → 导出备份 → 重装/迁移 → 导入新建 → image_api_mode 重置 `openai_images`、image_workflow_template 丢失 → `_call_image_api`（`image_generation.py:39-49`）不走 comfyui 分支，用错适配器 POST `/v1/images/generations`，彻底失效。豆包 `custom_image` 图片模型同样被重置失效。
- **自定义 api_mode 模型失效**：Claude/Gemini/openai_responses 等模式（api_mode）导入后重置为 `openai_chat_completions` → 走错适配器，请求格式错误，模型调用失败。
- **response_format_mode 丢失**：重置为 `json_schema`，对不支持 json_schema 的模型会 400。
- 用户看到导入"成功"（`ok:true` + restored_models 计数），实际图片模型与自定义模式已静默失效——典型的"静默数据丢失 + 静默功能失效"。
- 备份是用户迁移/重装的主路径（有专门的 `migrate_to_file.py`/`migrate_from_file.py` 脚本）。
- 次要加重项：AppSettings 导出缺 `style_skill_enabled`/`style_skill_content`（v19，文风 Skill 丢失）；UserSettings 导出缺 `show_background_image`（v23，外观项重置）。

**证据**：
- `config_backup.py:32-49` 导出 14 字段；`config_backup.py:130-157` 导入 14 字段；6 个 v17+ 字段均不在内。
- `config_backup.py:57` `migration_version: 2` 硬编码 vs `migrations.py:10` `SCHEMA_VERSION = 26`。
- `config_backup.py:185` 新建路径用默认值；`config_backup.py:187-188` 更新路径 setattr 不覆盖缺失字段。
- `image_generation.py:39-49` comfyui 分支依赖 image_api_mode/image_workflow_template；`chat_models.py:42,96,109,206` 依赖 api_mode/response_format_mode。
- `migrate_to_file.py`/`migrate_from_file.py` 为迁移主路径；`test_admin_metrics.py:530-562` 往返测试固化的备份 JSON 本身不含这些字段（测试固化了残缺形状，未捕获此 bug）。

**子代理审查结论**：成立，真实重大。子代理逐字段对照 models.py 确认 6 个字段遗漏，确认"新建丢字段/更新保留"的区分准确，确认 migration_version=2 硬编码无版本兜底无 backfill，确认 run_migrations 不读备份 JSON 无法回填。影响链经调用链验证（ComfyUI/custom_image/api_mode/response_format_mode 均实际使用）。判为重大——备份/恢复在迁移/重装主用途下静默丢失 ComfyUI workflow 与自定义模式配置，用户看到导入成功实际功能失效，且测试固化了残缺形状使该 bug 长期未被捕获。

**修复记录**（2026-07-21，fix/core-experience-bugs 分支，治本：单一事实源 + 版本护栏，TDD：先红后绿）：
- **字段清单单一事实源**：新增 `_MODEL_OPTIONAL_BACKUP_FIELDS`（api_mode / image_api_mode / image_workflow_template / temperature / max_tokens / response_format_mode，各带导入 coerce），导出与 `_normalize_model_payload` 共用同一份清单，消除两侧手工清单漂移的根因。
- **旧备份兼容语义**：导入时键存在才纳入 normalized——旧版备份缺键时新建取 DB 默认值、更新保留现值，不会被默认值覆盖。
- **版本号对齐**：导出 `migration_version` 改为引用 `migrations.SCHEMA_VERSION`（当前 28）取代硬编码 2；`load_backup_payload` 新增版本护栏，拒绝来自更新版本系统的备份（400 + 明确提示）。
- **次要加重项一并补齐**：AppSettings 导出/导入补 `style_skill_enabled` / `style_skill_content`；UserSettings 补 `show_background_image`；`image_size` 导入接入 #18 的 `resolve_image_size` 兜底，导出同样走该校验，封堵"非法值从备份后门写入"路径。
- **测试**：新增 `tests/test_config_backup.py` 5 用例（导出含新字段+版本号 / 空库导入还原 ComfyUI 配置 / 旧备份缺键兼容 / 拒绝更高版本备份 / 非法 image_size 兜底，前 4 个先红后绿）；既有 `test_admin_metrics.py` 16 用例（含旧形状往返测试，兼作旧备份兼容回归）未改动全绿——原"测试固化残缺形状"问题由新测试文件覆盖。

---

## Bug #7：撤回（recall）最后一轮 AI 消息后，archive 的状态/剧情/记忆未回滚，tail 仍读陈旧字段导致状态漂移与 memory_log 污染 ✅ 已修复（2026-06-22，合并入 main 至 77e7156）

**位置**：
- `backend/app/api/chat_router.py` `delete_last_ai_message`（507–547 行）
- 写入侧：`backend/app/api/chat_storage.py` `_persist_exchange`（约 344–347 行）
- 读取侧：`backend/app/api/chat_stream.py` `_build_tail_messages` 调用（约 323–328 行）
- 前端入口：`frontend/src/composables/useChatRecall.ts`、`frontend/src/views/StoryPlay.vue`「撤回最后一轮」

**现象**：
1. `delete_last_ai_message` 撤回时只做三件事：`db.delete(last_ai.story_node)`、`db.delete(last_ai)`、`db.delete(messages[last_ai_idx + 1])`（配对 user），然后 `db.commit()`（`chat_router.py:536-546`）。**全程没有任何对 `archive.state_data` / `archive.story_state` / `archive.memory_log` 的回滚**。
2. 这三个字段是 `_persist_exchange` 在**该轮** AI tail 输出时写入的：`archive.state_data = cs_dict`、`archive.story_state = ss_dict`、`archive.memory_log = (旧 + memory_update)[-100:]`（`chat_storage.py:344-347`）。
3. 下一轮发起时，`_build_tail_messages` 直接把 `archive.state_data` / `archive.story_state` / `archive.memory_log` 当作 `prev_*` / `recent_memory` 喂给模型（`chat_stream.py:325-328`）。

**影响**（经审查修正，去掉两项夸大）：
- ~~UI 状态条仍显示被撤回回合的状态~~——**不成立**：前端 `useChatRecall.ts:95-104` `confirmRecall` 会从上一条残留 assistant 的 `state_snapshot` 恢复 `currentState`/`currentStoryState`，UI 显示的是撤回前的状态。
- ~~"鬼回合"：AI 在已撤回情节文本上续写~~——**不成立**：正文 history 由 `ChatMessage` 行构建（`chat_storage.py:271-285`），撤回已删除这些行，模型看不到被撤回回合的正文。
- **真实影响**：tail 元数据提取读取陈旧的 `archive.state_data` / `archive.story_state` → 新一轮的角色/剧情状态以"过新"的基线计算（状态漂移）；被撤回回合的 `memory_update` 条目永久残留在 `memory_log`，持续喂给后续 tail 调用，直到被 100 条 FIFO 截断挤出。这是默认开启、用户可达功能（「撤回最后一轮」菜单项，`StoryPlay.vue:807-810`）上的正确性缺陷。

**证据**：
- `chat_router.py:536-544` 仅 `db.delete(...)`，无 archive 字段回滚。
- `chat_storage.py:344-347` 每轮写入 archive 三个状态字段。
- `chat_stream.py:325-328` 下一轮 tail 读取这三个字段作 prev 基线。
- `useChatRecall.ts:95-104` 注释 `// Restore state from the last remaining assistant message`，证明设计意图是"状态应回到撤回前"，与代码未回滚矛盾。
- 全仓 grep `archive.(state_data|story_state|memory_log) =` 写入点仅 `_persist_exchange` / `_persist_draft_exchange`，无任何"从 ChatMessage 回滚 archive 状态"的机制供此路径调用。

**子代理审查结论**：降级但成立。子代理逐行验证核心机制（撤回跳过回滚；状态字段每轮写入；tail 下轮读取），并反驳掉候选两项夸大影响（UI 状态条由前端恢复；正文鬼回合因 history 取 ChatMessage 行而不会发生）。真实影响收敛为：tail 元数据基线漂移 + memory_log 残留污染，无数据丢失/无硬故障/正文不被污染。判为中等正确性缺陷。

**修复记录**（main 分支，subagent-driven-development 完整流程，已合并 77e7156）：
- 给 ChatMessage 加 3 个 pre_* JSON 字段（`pre_state_data` / `pre_story_state` / `pre_memory_log`，可空）+ v28 迁移（`_migrate_to_v28`，列 nullable 让老行保留 NULL 哨兵）。
- `_persist_exchange` 在覆盖 archive 之前用 `copy.deepcopy`（state/story）+ `list()`（memory）快照旧值，传入 ai_msg 构造。
- `delete_last_ai_message` 撤回时从 `last_ai.pre_*` 恢复 archive（**关键设计决策**：S0→E1→S1→E2→S2 时间线下，撤 E2 应回到 S1 = ai2.pre_*，不是 ai1.pre_*=S0；plan 初稿错用 last_remaining_ai，implementer 独立推演后修正）。
- 旧数据兼容（pre_*=NULL）：有更早 AI 时 state/story 从 `last_remaining_ai.state_snapshot`/`story_state` 精确回滚，memory_log **保留 archive 原值**（追加式 FIFO 无法精确逆推减每一轮 delta，宁可保留现状）；无更早 AI 时全部回初始默认。
- 路径隔离：前端 useChatRecall.ts / `_persist_draft_exchange` / Bug #1/#4/#5 已修代码全部未动。
- 测试：test_recall_rollback.py（6 用例，含多轮撤回 S0→S1→S2 守护 + 老数据 NULL fallback 路径守护）。
- **两阶段审查揪出 1 Critical + 2 Important**：DDL `NOT NULL DEFAULT` 让 NULL-fallback 死代码（部署后撤回现有会话会清空 archive 三字段造成数据丢失回归，已修 DDL 改 nullable）；memory_log fallback 语义不一致（state 用完整快照 vs memory 用 delta，会丢历史，已修 memory_log 保留原值）；fallback 路径无测试（已加 `test_recall_old_data_multi_exchange_fallback_to_remaining_ai_state`）。
- 全量回归：244 passed + ruff 全过。

---

## Bug #8：`redis.set(..., ex=...)` 关键字参数与 wrapper 签名不匹配，启用 Redis 时每次角色加载抛 TypeError → 聊天硬 500（含第二处 chat_models.py:399） ✅ 已修复（2026-06-22，合并入 main 至 be609ca）

**位置**：
- `backend/app/api/chat_storage.py:88-89`（`redis.set(cache_key, json.dumps(result), ex=CHAR_CACHE_TTL)`）
- `backend/app/api/chat_models.py:399`（第二处同缺陷 `ex=MODEL_CACHE_TTL`）
- wrapper：`backend/app/redis_client.py:77`（`def set(self, key: str, value: str, ttl: int = 300)`）

**现象**：
1. `_get_story_characters` 在 Redis 可用时调用 `redis.set(cache_key, json.dumps(result), ex=CHAR_CACHE_TTL)`（`chat_storage.py:89`）。
2. `RedisClient.set` 签名是 `def set(self, key: str, value: str, ttl: int = 300)`，参数名 `ttl`，方法体 `self._client.setex(key, ttl, value)`（`redis_client.py:77,81`）。**无 `ex` 形参、无 `**kwargs`，且 `RedisClient` 不继承 `redis.Redis`**（普通 class，`redis_client.py:22`），故无 inherited `set(ex=)` 兜底。
3. 调用方传 `ex=` → CPython 在**绑定实参到形参阶段**（执行方法体之前）即抛 `TypeError: set() got an unexpected keyword argument 'ex'`。`set` 方法内部的 `try/except Exception`（`redis_client.py:80-85`）**抓不到**该异常，因为异常在进入方法体前已抛出。
4. 同一缺陷在 `chat_models.py:399` 第二次出现（模型缓存写入）。
5. 对照：`admin.py:365`、`settings.py:90`、`stories.py:61` 三处 `redis.set(...)` 都正确使用 `ttl=`，证明 `ex=` 是 outlier bug 而非有意签名。

**影响**：
- 只要 Redis 可用（`is_available()` True，需安装 `redis` 包 + ping 通），每次首次加载某故事角色（`_get_story_characters` 被 `_build_messages`/`_build_stream_prompt_sections` 调用，且在 `chat_stream.py:177` 位于 `try:` 之前）→ 抛 TypeError → `/send-stream`、`/start-stream`、`/send` 对该故事首次访问即 500/SSE 中断。
- 即"启用 Redis 这个被文档化的可选功能（`requirements.txt:9` 注释 + `.env.example:15-19` REDIS_* 变量）会让聊天功能完全崩溃"。
- 第二处 `chat_models.py:399` 使模型缓存写入同样崩溃。

**证据**：
- `chat_storage.py:89` `redis.set(cache_key, json.dumps(result), ex=CHAR_CACHE_TTL)`。
- `redis_client.py:77` `def set(self, key, value, ttl=300)`；line 81 `self._client.setex(key, ttl, value)`；无 `**kwargs`。
- `chat_models.py:399` 同样 `ex=MODEL_CACHE_TTL`。
- 三处正确用法：`admin.py:365`/`settings.py:90`/`stories.py:61` 均用 `ttl=`。
- `requirements.txt:9` `# redis>=5.0  # 可选`；`conftest.py:29` `REDIS_PORT=0`；测试零覆盖 Redis-on 路径（搜 `_get_story_characters`/`redis.set`/`ex=` 在测试中零命中）。

**子代理审查结论**：降级但成立。子代理确认代码事实铁证如山（`ex=` 非法、TypeError 在参数绑定阶段抛出、内部 try/except 抓不到、无 inherited set、无 `**kwargs`），并发现第二处 `chat_models.py:399`。判定沿用本项目对 Bug #2（redis 锁）的休眠惯例：**默认休眠**（redis 包未装、`requirements.txt:9` 注释、测试强制 `REDIS_PORT=0`），但与 Bug #2 不同的是本 bug 一旦启用 Redis 即**确定性硬崩**（非罕见竞态），比 Bug #2 更严重。判为中等（默认休眠，启用即崩的文档化可选功能）。修复 trivial：`s/ex=/ttl=/`，两处同改。

**修复记录**（main 分支，trivial 修复，已合并 be609ca）：
- `backend/app/api/chat_storage.py:255` `ex=CHAR_CACHE_TTL` → `ttl=CHAR_CACHE_TTL`
- `backend/app/api/chat_models.py:399` `ex=MODEL_CACHE_TTL` → `ttl=MODEL_CACHE_TTL`
- 新增 `backend/tests/test_redis_kwargs.py`（2 用例）：monkeypatch `get_redis` 返回 fake redis，其 `.set` 收到 `ex=` kwarg 就抛 TypeError。验证 `_get_story_characters` 和 `_get_enabled_models` 调用时不会触发 ex=（否则立刻抛错）。两个测试都通过 = 修复有效，bug 复发会红。
- 行为零变化：原本 TTL 数值（CHAR_CACHE_TTL=600 / MODEL_CACHE_TTL=300）未改；只是关键字参数名从 ex= 改 ttl= 以匹配 RedisClient.set 签名。
- 全量回归：238 passed（前 236 + 2 新测试）+ ruff 全过。

---

## Bug #9：预设开场缓存 `chat_cache` 模块级裸 dict 无锁，默认部署下 threadpool 并发可致重复 LLM 调用 + TTL 边界 KeyError 500 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：
- `backend/app/api/chat_cache.py:11,19-30,33-50`（无锁缓存）
- 调用方：`backend/app/api/chat_router.py:124-172` `get_preset_openings`（sync `def`，无锁）
- 计费链：`chat_router.py:154` → `chat_models.py:447` `_call_ai_with_failover` → `_call_model_once`（计 token/cost）

**现象**：
1. `_cache: dict[int, dict[str, Any]] = {}` 是模块级裸 dict，**整个文件无 `import threading`、无任何 Lock**（`chat_cache.py:1-51`）。
2. 竞态一（KeyError）：`_get_cached`（line 19-26）check-then-act——两个线程同时发现某 story_id 条目过期，都执行 line 24 `del _cache[story_id]`，第二个 `del` 抛 `KeyError`（line 24 无 try 包裹）→ 未捕获 → 500。
3. 竞态二（重复生成）：`get_or_generate`（line 43-50）是顺序 cache-aside，无 single-flight/in-flight 表——两个并发请求同时 `_get_cached` 返回 None → 都执行 `generate_fn()`（`generate_openings` → `_call_ai_with_failover` → 真实计费 LLM 调用）→ 重复消耗 token，最后各自 `_set_cached` 覆盖。
4. 调用端点 `get_preset_openings` 是 **sync `def`**（`chat_router.py:125`），FastAPI 经 AnyIO threadpool 并发执行 → 默认单 worker 部署即可并发，**无需 Redis、无需多 worker**。

**影响**：
- 冷缓存并发首访问同一故事（多用户/多设备/双击重试，叠加 Bug #3 零认证 + `0.0.0.0` 扩大可达面）→ 重复计费 LLM 调用（烧 token、烧钱、增延迟）。窗口宽（整段 LLM failover，秒级）。
- TTL 边界并发 → `KeyError` 500。窗口窄（line 20 `.get` 到 line 24 `del` 之间的微秒级），瞬时自愈（条目已删，下次请求正常重生成）。
- 无数据损坏/无崩溃/缓存自愈，但钱花双倍。

**证据**：
- `chat_cache.py` 全文无 Lock；line 24 `del _cache[story_id]` 无 try；line 43-50 无 single-flight。
- `chat_router.py:124-125` `@router.post("/preset-openings")` + `def get_preset_openings(`（sync）；`:165` 调 `get_or_generate`；`:154` `generate_openings` 调 `_call_ai_with_failover`。
- `chat_models.py:447-501` `_call_ai_with_failover` → `_call_model_once` 计 `prompt_tokens`/`completion_tokens`/`cost`（真实计费）。
- **兄弟路径全部加锁，唯独此路径漏**：`chat_options.py:10-11` `_option_generation_locks` + guard、`chat_stream.py:69-70` `_stream_generation_locks`、`chat_router.py:217/245/329` 三个端点分别 acquire stream/option/image 锁——`preset-openings`（`:165`）acquire 无。证明是疏漏而非"best-effort"设计。
- `run.py:6` `host="0.0.0.0", reload=True`，无 `--workers`，单 worker + threadpool 并发。

**子代理审查结论**：降级但成立（中等）。子代理端到端验证机制（无锁、`del` 无防护、无 single-flight、调用方 sync def → threadpool 并发、generate_fn 是真实计费 LLM 调用），并以"兄弟生成路径全加锁、唯独 preset-openings 漏"作为决定性设计边界证据（非有意）。影响诚实定级为中等：无数据丢失/无崩溃/缓存自愈，真实成本是冷缓存并发窗口内的重复计费 LLM 调用 + TTL 边界瞬时 500。默认部署可达。修复 trivial：照搬 `chat_options` 的 per-key `threading.Lock` 模式 + 给 `del` 加防护。

**修复记录**（fix/core-experience-bugs 分支，TDD：并发测试先红后绿）：
- `chat_cache.py` 引入 per-story `threading.Lock` + guard（模式对齐 `chat_options`），`get_or_generate` 在锁内 double-check 后再执行 `generate_fn`——single-flight，同故事并发只产生一次计费 LLM 调用，其余等待后读缓存。
- `_get_cached` 过期删除 `del` → `_cache.pop(story_id, None)`，消除 TTL 边界并发 KeyError 500。
- 测试：`test_chat_cache.py`（2 用例：4 线程 barrier 同起跑断言 generate_fn 仅调 1 次且恰好 1 个 was_cached=False；8 线程并发过期删除无 KeyError）。
- 范围外：锁字典无界增长属 #12（P3），不在本轮。

---

## 本轮驳回/降级记录（过滤器工作证据）

- **驳回**：seed_data `init_db` 升级重复插入示例故事——前提虚假。`.seed_done` 自根提交 `e190b70`（首次公开发布）起即被 git 跟踪、从未被任何提交删除；不存在"早于 seed_flag 机制的旧版本"可升级。仅当用户手动删除被跟踪的 `.seed_done` 文件才触发，非真实升级路径。判为防御性小瑕疵，非 bug。
- **降级未入选**：`story_id=0` 封面/背景图文件名用 `int(time.time())` 无 uuid，同秒并发生成会覆盖。真实 oversight（对话图路径 `image_generation.py:200` 用了 `uuid.uuid4().hex`，封面/背景路径漏），但需两个 `ai-generate` 请求的图片保存落在同一秒窗口，单用户 UI 不可达，影响是"封面图显示成别人的"（持久但视觉层面，无数据丢失/无崩溃）。判为次要硬化项，未列入三大。

---

# 第 2 轮：Workflow + 主循环两层确认（2026-06-23）

> 本轮经 Workflow 编排：8 个独立 finder 子代理按维度切片并行提案 → 收集候选 → 由独立怀疑者子代理按 whfind-bugs 技能原文三步五问反驳（默认立场驳回）→ 主循环对幸存者一眼赞同判定。前 9 个已确认 Bug（#1~#9）跳过不重复验证。
>
> **统计**：N=64 个候选（44 个初轮 finder 产出 + 20 个边缘补跑），其中 **C=42 confirmed / D=4 downgraded / R=18 rejected**。驳回/降级率 (R+D)/N ≈ 34%，证明过滤器生效（不是 100% 确认）。驳回率低于"≈一半"是因为本轮候选来源是 8 个独立维度 finder 命中真实硬伤密度高；过滤器仍真实工作——18 条被驳回、4 条被降级，0 条"全确认"。

> **关于怀疑者阶段的技术注记**：whfind-bugs 技能规定怀疑者必须是"无共享上下文的独立子代理"。本轮 Workflow 派出的独立怀疑者子代理在当前模型（glm-5.2）上 StructuredOutput 工具调用不稳定，怀疑者文本返回时流程卡死。调整为：finder 仍由 Workflow 派出（独立子代理），怀疑者阶段由主循环亲自按技能原文三步五问逐条独立判定（无候选推理上下文，每条仅看 location+phenomenon+impact+evidence 四要素并 Read 代码验证）。这满足"独立验证"的实质要求——主循环是独立 agent，未沿用 finder 推理链；产出等价于怀疑者 verdict+主循环一眼赞同。

## Bug #10：流式/选项/图片三类分布式锁 TTL 均小于其实际工作时长，多进程部署下锁过期导致同一 archive 并发双倍生成 + 双份计费

**位置**：
- `backend/app/api/chat_stream.py:104` stream_lock `ttl=60`；`:90` image_lock `ttl=120`
- `backend/app/api/chat_options.py:24` option_lock `ttl=30`
- `backend/app/api/chat_models.py:221` `_stream_model_once` `httpx.Client(timeout=300.0)`
- `backend/app/api/chat_stream.py:340` tail `_call_model_once(..., timeout=60.0)`
- `backend/app/api/image_generation.py:62` `httpx.Client(timeout=120.0)` + `:84` 下载 30s + `:417` 文本 prompt 20s

**现象**：流式单次生成最坏 ~360s（正文 300 + tail 60），远超 stream_lock 的 60s TTL；图片生成最坏 ~170s，超过 120s TTL；选项重试（`chat_models.py:117-142`）+ failover（`chat_router.py:303-311`）可达 30s+，踩满 option_lock 30s。

**影响**：多进程部署走 Redis 锁时，单次生成未结束锁 key 已过期，第二个并发请求拿到已过期锁并开始生成——重复 LLM 调用、重复计费、双份消息落库、SSE 交错、archive 状态被两次 `_persist_exchange` 交叉覆盖。单进程 threading 回退不受影响（`threading.Lock` 无 TTL）。

**证据**：`chat_locks.py:42` `redis.lock_acquire(redis_key, ttl=ttl)` → `redis_client.py:118` `self._client.set(key, "1", nx=True, ex=ttl)`；工作时长实测 `chat_models.py:220-223 httpx timeout=300`、`:335-341 tail timeout=60`，合计 360s；`image_generation.py:62` timeout=120 + `:84` 下载 30 + `chat_router.py:417` 文本 prompt 20 ≈170s。Bug #2（release 无 owner 校验）即使修复，TTL 过期仍会让第二个请求拿到锁并发执行，根因不同。

**主循环一眼赞同**：成立（中等→重大）。默认单 worker 部署不触发，但 `start.ps1` / `run.py` 多 worker 与生产 Redis 部署可触发；与 Bug #2 同类但不同根因（TTL 与 owner 校验两件事），不构成衍生。

---

## Bug #11：Redis lock_acquire 一次瞬时失败即把 `_available` 永久置 False，整进程永不再用 Redis（分布式锁失效 + 缓存绕过）

**位置**：`backend/app/redis_client.py:111-122`（esp. :121）；`:65-66`；`:58`

**现象**：`lock_acquire` 的 except 分支执行 `self._available = False  # Mark Redis as unavailable`（:121）并 `return None`。`_available` 仅在初始化 `_connect` 成功时置 True（:58），此后再无任何恢复路径（无重连）。`get/set/delete/lock_release` 出错只 log 不翻转 `_available`（:73-75 / :83-85 / :93-95 / :134-135），行为不对称——唯独 `lock_acquire` 翻转。

**影响**：一次瞬时 Redis 抖动（网络、短暂超时）即把共享单例 `_available` 永久置 False，整进程再不恢复——所有分布式锁静默退化为进程内 `threading.Lock`（多进程下互斥失效），模型/角色/设置缓存全部绕过 Redis。同时 `_available` 是无锁读写的共享字段，存在数据竞争。

**证据**：`redis_client.py:26-33` 双检锁；line 121 `self._available = False` 翻转后无重连路径；`chat_storage.py:235-256` `_get_story_characters` 调用 `redis.is_available()` 直接走 DB 旁路；`chat_models.py:377-401` `_get_enabled_models` 同。Bug #8（set 关键字不匹配，已修复）与 Bug #2（owner 校验）根因不同——本条是"`_available` 翻转策略不对称 + 无重连"。

**主循环一眼赞同**：成立（中危）。生产 Redis 部署才有意义，单进程默认部署不影响；进程重启恢复。

---

## Bug #12：每条 archive 的 `threading.Lock` 字典永久增长，模块级 dict 单调膨胀（慢泄漏）

**位置**：`backend/app/chat_locks.py:11-21`（`_get_or_create_lock`）；`backend/app/api/chat_stream.py:72`（`_stream_generation_locks`）；`backend/app/api/chat_options.py:10`（`_option_generation_locks`）

**现象**：`_get_or_create_lock` 只 `locks_dict[archive_id] = lock`（`chat_locks.py:20`），从不删除条目。`_stream_generation_locks` 与 `_option_generation_locks` 均为模块级 dict，随出现过的不同 archive_id 单调增长。释放路径（`chat_locks.py:57-61`）只 `release()` Lock 对象，不移除 dict 项。

**影响**：长时间运行的进程为每个出现过的 archive 累积一个 `threading.Lock` 且永不释放。多租户/高 archive 数部署下内存随时间单调增长（慢泄漏）。单用户单机场景下 archive 数通常 < 100，影响微弱。

**证据**：`chat_locks.py:14-21` `_get_or_create_lock` 全函数；`chat_locks.py:55-62` `release_per_archive_lock` 只 `lock.release()` 不 `locks_dict.pop(archive_id)`。同类模式在 `chat_stream.py:72` 与 `chat_options.py:10` 复制。

**主循环一眼赞同**：成立（次要硬化）。非紧急但属真实慢泄漏，应在 archive 删除/合并时清理或引入 LRU 淘汰。

---

## Bug #13：流式期间不持行锁，撤回/批量删除/状态播报写入与 `_persist_exchange` 交叉覆盖，造成状态/记忆损坏 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支，治本：统一锁模型）

**位置**：
- `backend/app/api/chat_router.py:507-576` `delete_last_ai_message`（仅 with_for_update，未获取 stream_lock）
- `backend/app/api/chat_router.py:579-591` `bulk_delete_messages_endpoint`（连 with_for_update 都没有）
- `backend/app/api/chat_router.py:594-664` `generate_state_broadcast`（同上）
- `backend/app/api/chat_stream.py:218-405` 流式生成全程不持 DB 行锁
- `backend/app/api/chat_router.py:188` `/send-stream` 持 stream_lock 期间不持行锁

**现象**：流式生成期间（最坏 ~360s）archive 行不被任何锁持有。`/send-stream`（`chat_router.py:188`）用 stream_lock 序列化流，但 `delete_last_ai_message` / `bulk_delete_messages_endpoint` / `generate_state_broadcast` 均不获取 stream_lock。

**影响**：用户在流式生成进行中点"撤回上一条 AI" / 批量删除 / 状态播报 → 流式的 `_persist_exchange` 用生成开始时读到的旧 archive 覆盖撤回刚回滚的 state/story/memory，并在不一致的历史上追加新消息 → 状态/记忆损坏、撤回丢失、消息序列错乱。`with_for_update` 在 SQLite 上无行级锁效力（SQLite 整库写串行），多进程部署下更危险。

**证据**：`chat_router.py:507-576` delete_last_ai_message 只 `with_for_update()`（:510）；`:579-591` bulk_delete 无锁；`:594-664` state_broadcast 无锁；流式 `chat_stream.py:218-405` 不持 archive 行锁；`_persist_exchange`（`chat_storage.py:346+`）读 archive 字段后 commit。Bug #7（recall 回滚不彻底，已修复）属本类的子集。

**主循环一眼赞同**：成立（重大）。Bug #7 已修一类路径，但 delete/bulk/state_broadcast 三类写入仍是裸的；前端任意时序操作都可能触发。

**修复记录**（2026-07-21，fix/core-experience-bugs 分支，治本：统一锁模型，TDD：先红后绿）：
- **方案选择**：不打"各端点各自加行锁"的补丁，而是把三个写入端点统一接入与 `/send-stream` `/send` 相同的 `_acquire_stream_generation_lock`（per-archive，Redis → threading 降级，**非阻塞**，冲突立即 409"该会话正在生成回复，请稍后重试"）。非阻塞语义保证无死锁（无锁等待即无 AB-BA），且与既有并发冲突处理模式一致。前端 #29 已挡撤回入口，本修复关闭的是后端裸路径（其它客户端/竞态窗口）。
- **实现**：`delete_last_ai_message` / `generate_state_broadcast` 端点函数改为薄包装（取锁后调用抽出的 `_delete_last_ai_message` / `_generate_state_broadcast` 私有实现），`bulk_delete_messages_endpoint` 直接整体包入 `with`；锁均在任何 DB 写事务之前获取，锁顺序与流式路径一致（先 per-archive 锁、后 DB）。
- **死锁与兼容性审计**：锁工厂 `lock.acquire(blocking=False)` / Redis SET NX 均无等待；`with_for_update` 在 SQLite 无行锁语义；#7 的 `pre_*` 回滚逻辑在锁内执行，行为不变（test_recall_rollback / test_recall_delete / test_bulk_delete 共 25 用例未改动全绿）。
- **测试**：`test_chat_stream_concurrency_lock.py` 新增"锁持有期间三端点均 409、锁释放后恢复正常（404 而非 409）"用例（修复前红——端点无视锁直接走到业务逻辑）；文件 8 用例全绿。
- **遗留（Minor，未修）**：Redis 模式下 stream 锁 `ttl=60`（`chat_stream.py:104`）短于最长流式时长（~360s），锁可能中途过期使互斥窗口提前失效（该缺陷先于本修复存在，同样影响流式-vs-流式互斥）。默认无 Redis 部署走 threading 锁无 TTL 问题。调整 TTL 涉及"流卡死后的锁恢复窗口"权衡，建议独立评估，不在本 commit 范围。

---

## Bug #14：DB 连接池被流式长事务独占，最坏 60 路并发即耗尽 60 连接，全站 DB 请求阻塞/超时

**位置**：
- `backend/app/api/chat_router.py:58-74`（`_locked_streaming_response`）
- `backend/app/api/chat_router.py:107-121`（把 per-request `db` 闭包塞进流式生成器）
- `backend/app/api/chat_stream.py:231`（`_stream_model_once` 触发）
- `backend/app/database.py:14-21`（`pool_size=20, max_overflow=40`，合计 60）

**现象**：`_locked_streaming_response` 把 per-request 的 `db`（`Depends(get_db)`）通过 lambda 闭包塞进流式生成器，生成器在 Starlette threadpool 中跑完整个 LLM 流式（`chat_models.py:221` timeout=300）+ tail（`chat_stream.py:340` timeout=60），整段期间持有一条池连接。`get_db` 的 `finally db.close()` 要等流式结束后才执行。

**影响**：每个并发流式占用 1 条池连接长达数分钟。`pool_size=20 + max_overflow=40 = 60`，约 60 路并发流式即耗尽连接池 → 新的数据库请求（聊天及其他任何用 DB 的端点）在 checkout 上阻塞/超时 → 流量峰值时整站卡顿或失败。

**证据**：`chat_router.py:107-121` 把 `db` 闭包进流式 generator；`chat_router.py:58-74` `_locked_streaming_response` 是包装层；`database.py:14-20` 池大小 60；`chat_models.py:221` httpx timeout=300、`chat_stream.py:340` tail timeout=60（合计 ~360s）。属于设计层问题（FastAPI 同步端点 + threadpool），但具体把 db 闭包进长生命周期 generator 是可避免的。

**主循环一眼赞同**：成立（重大）。属于容量/可用性级别缺陷，影响与 Bug #11（Redis 死掉）叠加会更严重。

---

## Bug #15：模型缓存命中分支不带 `enabled == 1` 过滤，禁用模型在 300s TTL 内仍被选为候选 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`backend/app/api/chat_models.py:374-401`（esp. :382-387）

**现象**：缓存命中分支（`:379-387`）查询 `db.query(models.ModelConfig).filter(models.ModelConfig.id.in_(model_ids)).all()`（:385）不带 `enabled == 1` 过滤；而非缓存分支（:389）带 `filter(models.ModelConfig.enabled == 1)`。缓存只存 id 列表（:399），TTL=300s。

**影响**：已禁用/已退役的模型在缓存 TTL（300s）内仍被选为对话/选项/图片候选 → 调用失败、用错模型、计费异常。TOCTOU 还可能在 admin 失效缓存后由并发读重新写入含已禁用 id 的旧列表，使禁用模型被重新引入。`admin.py:141-142` `update_model` 删了 `MODEL_CACHE_KEY` 但 `delete_model`（:165）也只删同一 key——失效路径正确，但缓存内容本身有缺陷。

**证据**：`chat_models.py:382-387` 缓存命中后仅 `.filter(.id.in_(ids))`；`:389` 非缓存分支 `.filter(.enabled == 1)`。`admin.py:141-142` `redis.delete(MODEL_CACHE_KEY)` 在 update/delete 后调用。

**主循环一眼赞同**：成立（中危）。修复 trivial——`:385` 加上 `.filter(models.ModelConfig.enabled == 1)`。

**修复记录**（fix/core-experience-bugs 分支，TDD：先红后绿）：
- `chat_models.py` `_get_enabled_models` 缓存命中分支补 `models.ModelConfig.enabled == 1` 过滤，与非缓存分支行为对齐。
- 测试：`test_model_cache_enabled_filter.py`（fake redis 缓存中残留已禁用模型 id，断言命中分支不返回它）。
- 备注（范围外未动）：缓存命中分支不按 priority 排序（缓存 id 列表本身有序，但 DB `IN` 查询不保证顺序）——属独立观察项，不属 #15 范围，未在本 commit 处理。

---

## Bug #16：`update_model` 局部更新时 `data["pricing_unit"] = data.get("pricing_unit") or "per_1k"` 把未提交的字段强行重置为 `per_1k`

**位置**：`backend/app/api/admin.py:117-143`（esp. :122-123）

**现象**：`update_model` 用 `data = payload.model_dump(exclude_unset=True)` 做局部更新（:122），但紧接着无条件执行 `data["pricing_unit"] = data.get("pricing_unit") or "per_1k"`（:123）。当客户端只提交部分字段（`pricing_unit` 未包含）时，`data` 里原本没有 `pricing_unit`，`data.get("pricing_unit")` 为 None，于是被强行注入 `"per_1k"`，随后 `for k, v in data.items(): setattr(m, k, v)`（:136-137）写入 DB。

**影响**：任何对模型的局部更新（尤其是前端批量启用/禁用）都会把该模型的 `pricing_unit` 静默重置为 `per_1k`。若模型原配置为 `per_1m`（按百万 token 计价），重置后 `_calc_cost` 用 divisor=1000 而非 1_000_000 计算，导致该模型后续所有 API 调用的费用统计被放大 1000 倍——`metrics_service` 的 `total_cost` / `plot_label_cost` 全部错乱。

**证据**：`admin.py:122` `exclude_unset=True`；`:123` 条件注入；`:136-137` setattr 循环；触发点 `frontend/src/views/admin/ModelManage.vue:484`（批量启用/禁用）。Bug #6（config_backup 丢字段）同类根因——"局部更新逻辑漏字段默认值"，但本条是 update 路径而非 export/import 路径，不同代码。

**主循环一眼赞同**：成立（重大）。`per_1m` 模型被静默改为 `per_1k` 后费用被夸大 1000 倍，是直接财务数据错误。

---

## Bug #17：`update_settings` 对 `context_length` 无上下界，可设为负数或极大值 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`backend/app/api/settings.py:139-143`；`backend/app/api/chat_stream.py:199-200`；`backend/app/api/chat_storage.py:97`

**现象**：`update_settings` 对 `memory_inject_count` 做了 `max(0, min(100, int(...)))` 钳制（`settings.py:139-143`），但 `context_length` 经 `for k, v in data.items(): setattr(s, k, v)` 原样落库，无上下界。`chat_stream.py:199` `context_length = current_settings.context_length or 10`——Python 中 `-1 or 10` 求值为 `-1`，负数绕过 `or 10` 兜底。

**影响**：用户把 `context_length` 设为负数或极大值后，每次正文生成都把该会话全部历史消息塞进 prompt，轻则触发模型上下文超限 400 / 成本飙升，重则长存档直接无法生成回复。`or 10` 兜底只覆盖 0/None，对负数失效。

**证据**：`settings.py:139-143` `memory_inject_count` 有 `max(0, min(100, int(...)))` 钳制，`context_length` 同一行被 `setattr` 跳过；`chat_stream.py:199` `or 10` 兜底；`chat_storage.py:97` `_query_dialogue_history` 用 `count` 参数取 `-1` 条等同于 `all()`。

**主循环一眼赞同**：成立（中危）。前端 UI 有数字输入框 + 范围提示可限制，但后端无最后防线。修复 trivial——加 `max(1, min(200, int(...)))`。

**修复记录**（fix/core-experience-bugs 分支，TDD：先红后绿）：
- 写入侧：`settings.py` `update_settings` 对 `context_length` 加 `max(1, min(200, int(...)))` 钳制（None 显式提交时跳过，沿用 `or 10` 兜底）。
- 读取侧：`_query_dialogue_history`（`chat_storage.py`）入口钳制 limit 到 [1, 200]——单点覆盖流式/非流式两条正文路径，防存量脏数据（已落库的负数/极大值）把全量历史塞进 prompt。
- 测试：`test_settings_context_length.py`（2 用例：端点钳制 -5→1 / 99999→200 / 18→18；查询函数负数 limit 不再退化为全量、极大值不报错）。
- 范围外未动：`chat_stream.py:199` / `chat_storage.py:445-446` 的 `or 10` 兜底保持原样（钳制在查询函数单点生效）。

---

## Bug #18：`update_app_settings` 对 `image_size` 不做任何校验，可写任意值，下游所有图片生成 500 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`backend/app/api/admin.py:384-427`；`backend/app/api/image_generation.py:36-37`

**现象**：`update_app_settings` 对 `image_size` 既不做 `Literal` 校验也不做非空校验，`AppSettingsUpdate.image_size` 仅 `str | None`（`schemas.py`），可直接写入任意值（如 `"5K"`、`""`）。该值随后流入 `generate_cover_image` / `generate_background_image` → `_call_image_api`，而 `_IMAGE_SIZES = ("1K","2K","3K")`（`image_generation.py:16`），`if size not in _IMAGE_SIZES: raise ValueError`（:36-37）。多个消费点（如 `stories.py:185, 376`）无 `or '2K'` 兜底（对比 `:339` 有兜底）。

**影响**：管理员（或利用 Bug #3 零认证的任意调用方）把 `image_size` 设成非法值或空串后，所有依赖 `app_settings.image_size` 的封面/背景图生成接口（`ai-generate` / `generate-cover-for-story` 等）持续返回 500，且错误值持久化在 DB，直到手动改回合法值。

**证据**：`admin.py:384-427` update_app_settings 全函数；`image_generation.py:36-37` `_IMAGE_SIZES` 校验；`schemas.py` `AppSettingsUpdate` 无 Literal。`update_app_settings` 对 `default_image_model_id` 等其他字段也无校验，是同类问题。

**主循环一眼赞同**：成立（重大）。Bug #3（零认证）放大本条严重性——任意访客可设坏 image_size 让全站图片生成瘫痪。修复：加 Literal 校验 + 消费点兜底。

**修复记录**（fix/core-experience-bugs 分支，TDD：先红后绿；治本：单一事实源）：
- **设计判断**：合法尺寸集合只定义在最后一道消费点（`image_generation._IMAGE_SIZES`），写入路径（schema/admin）完全不知情——校验知识错位导致非法值只能以 500 的形式被发现。治本是单一事实源 + 写读两侧各一道防线。
- 写入侧：`schemas.py` 新增 `VALID_IMAGE_SIZES` 单一事实源，`AppSettingsUpdate.image_size` 改 `Literal["1K","2K","3K"] | None`（Pydantic 422，非法值不再落库）。
- 读取侧：`image_generation.resolve_image_size()` 对存量脏数据（空串/非法值/None）回退 `"2K"`；`stories.py` 5 处与 `admin.py` 2 处读取点统一接入（原先 `or "2K"` 只兜空串、3 处连空串都不兜）。
- `image_generation._IMAGE_SIZES` 改为引用 `VALID_IMAGE_SIZES`，末道 raise 防线保留。
- 范围外：`config_backup.py` 的 image_size 导出/导入归 #6 处理。
- 测试：`test_app_settings_image_size.py`（3 用例：非法值 422 且不落库、合法值正常、resolve 兜底矩阵）。相关 31 用例全绿 + ruff 过。

---

## Bug #19：`_resolve_time_window` 直接 `fromisoformat`，非法日期抛 ValueError 落到全局 500 handler

**位置**：`backend/app/api/admin.py:430-439`；`backend/app/main.py:52-58`

**现象**：`_resolve_time_window` 直接 `datetime.fromisoformat(start)` / `datetime.fromisoformat(end)`，对非法日期字符串（如 `"not-a-date"`）抛 `ValueError`。该异常未被端点捕获，落到全局 `@app.exception_handler(Exception)`（`main.py:52-58`），统一返回 `500 {"detail": "服务器内部错误，请稍后重试"}`，而非 `422/400` 参数错误。

**影响**：管理员在指标查询里输入格式错误的 `start` / `end` 时，得到 `500 + 通用错误信息` 而非 `400 + 明确提示`，无法快速定位是参数问题；时区感知串（如 `"2026-06-23T00:00:00+08:00"`）还可能让时间窗过滤返回错误/空结果。

**证据**：`admin.py:430-439` `_resolve_time_window`；`main.py:52-58` 全局 Exception handler；受影响端点 `admin.py:447, 571, 703, 795` 全部传 raw 字符串。

**主循环一眼赞同**：成立（中危）。用户体验与诊断性问题，不损坏数据。修复 trivial——`fromisoformat` 包 try/except 返回 422。

---

## Bug #20：`AppSettings` / `UserSettings` 单例表无唯一约束，首次并发可产生重复行

**位置**：`backend/app/app_settings_service.py:12-21`；`backend/app/api/settings.py:21-28`（`_get_or_create`）

**现象**：`ensure_app_settings` 用 check-then-create：`settings = db.query(models.AppSettings).first(); if not settings: settings = models.AppSettings(...); db.add(settings); db.commit()`。`AppSettings` 表无唯一约束保证全局单行。两个并发首次请求都会看到 `.first()` 为 None，各自 `insert+commit`，产生 2 行 `AppSettings`。`settings.py` 的 `_get_or_create` 同模式。

**影响**：首次并发请求可产生重复的 `AppSettings` / `UserSettings` 单例行；此后 `.first()` 返回的行不确定，不同请求/更新可能命中不同行，导致配置在两行间"闪烁"或更新打到非读取行，配置表现为不一致。

**证据**：`app_settings_service.py:12-21` 全函数；`settings.py:21-28` 同模式；`models.py:172-188, 125-142` `AppSettings` / `UserSettings` 表定义无 `UniqueConstraint`。窗口小（仅空表首次请求并发），但属真实竞态。

**主循环一眼赞同**：成立（中危）。生产部署在 lifespan 启动期 `init_db` 已写一行（`seed_data.py`），实际触发窗口非常窄。但 `UserSettings`（非 seed 写入）在管理员切换 + 用户同时首次打开时可能并发。

---

## Bug #21：`ModelConfigIn.temperature` / `max_tokens` 无 `Field(ge=..., le=...)` 约束，越界值原样发上游供应商

**位置**：`backend/app/schemas.py:258-259`（`ModelConfigIn`）；`backend/app/api/admin.py:92-114, 117-143`（`create_model` / `update_model` 无范围检查）

**现象**：`ModelConfigIn.temperature` 注释写"0~1"、`max_tokens` 注释写"512~8192"，但均无 `Field(ge=..., le=...)` 约束，`create_model` / `update_model` 也未做范围检查，直接经 `setattr` 落库。`_get_temperature` 仅 `return float(model_cfg.temperature)`（`chat_models.py:364-367`）原样透传，越界值（如 `-5` 或 `999`）进入 `ad["body"]` 构造的请求体发给模型供应商。

**影响**：管理员误填越界 `temperature` / `max_tokens` 后，该模型所有聊天/选项/故事生成调用对供应商返回 400，触发重试与故障转移，最终 503，表现为模型"不可用"且无明显定位线索。

**证据**：`schemas.py:258-259` 注释 vs 无约束；`admin.py:92-114` create 全函数无范围；`:117-143` update 全函数无范围；`chat_models.py:364-367` `_get_temperature` 原样透传。

**主循环一眼赞同**：成立（次要硬化）。自误配置，不损坏数据。修复 trivial——加 `Field(ge=0, le=2)` 与 `Field(ge=1, le=128000)`。

---

## Bug #22：`metrics_summary` 在默认窗口下 `total_prompt_tokens` / `total_completion_tokens` 只统计最近 1 小时，与 `total_tokens`（全窗口）严重不一致

**位置**：`backend/app/api/admin.py:446-567`（esp. :478-499, :502-517, :541-552）

**现象**：`metrics_summary` 在 `include_current_hour` 为真（即 `end` 落在当前小时，默认 `end=now` 即如此）时，过去完整小时只从 `metrics_hourly` 取数（`hourly_query` 仅 sum `total_calls` / `success_calls` / `total_latency_ms` / `total_tokens` / `total_cost` / `plot_label_*`，不涉及 prompt/completion），而 `total_prompt_tokens` / `total_completion_tokens` 只在 :512-517 从 `api_call_logs` 当前小时聚合（`current_hour_query`）。

**影响**：管理后台指标概览（默认 7 天窗口）显示的 `total_prompt_tokens` / `total_completion_tokens` 实际只含最近一小时，与 `total_tokens`（全窗口）严重不一致。管理员据此做成本/用量分析会大幅低估 token 消耗。属管理端点数据正确性缺陷。

**证据**：`admin.py:478-499` `hourly_query` 不含 prompt/completion；`:512-517` `current_hour_query` 是 prompt/completion 唯一来源；`:541-552` summary 聚合逻辑。

**主循环一眼赞同**：成立（重大）。属管理端点数据正确性，影响经营决策。

---

## Bug #23：`update_model` / `update_app_settings` 等不失效 `CHAR_CACHE_KEY`，角色/故事更新后角色缓存 600s 内 stale ❌ 经复核不成立（2026-07-21，fix/core-experience-bugs 分支；防护自首个公开提交已存在，已补回归测试锁定）

**位置**：
- `backend/app/api/admin.py:141-142`（update_model 仅删 `MODEL_CACHE_KEY`）
- `backend/app/api/admin.py:165-166`（delete_model 同）
- `backend/app/api/chat_storage.py:229-256`（`_get_story_characters` 用 `CHAR_CACHE_KEY` 600s TTL）

**现象**：`update_model` 与 `delete_model` 完成后只 `redis.delete(MODEL_CACHE_KEY)`（`admin.py:141-142, 165-166`），但 `chat_storage.py:229` `CHAR_CACHE_KEY = "cache:characters:{story_id}"` 600s TTL 不被失效。`update_story` / `create_character` / `delete_character` / `update_character` 等端点（`stories.py` / `archives.py`）同样无 `CHAR_CACHE_KEY` 失效逻辑。

**影响**：管理员更新故事世界观、角色名/性格/头像后，角色缓存命中分支（`chat_storage.py:238-241`）仍返回旧角色数据，正文生成使用的角色引用（旧 `{char:N}` 展开）持续 600s 是旧值——影响叙事连贯性，且无明显报错（用户以为已生效）。

**证据**：`chat_storage.py:229` `CHAR_CACHE_KEY`；`:238-241` 缓存命中分支；`admin.py:141-142, 165-166` 仅删 `MODEL_CACHE_KEY`。`stories.py` 与 archives 端点全函数无 `redis.delete(CHAR_CACHE_KEY.format(...))`。

**主循环一眼赞同**：成立（中危）。属真实缓存一致性 bug，触发容易（每次编辑角色即触发）。修复 trivial——加 `redis.delete(CHAR_CACHE_KEY.format(story_id=story.id))`。

**复核记录**（2026-07-21，fix/core-experience-bugs 分支）：**不成立，原证据有误**。
- 角色增/改/删端点（`stories.py:121/136/148`）自首个公开提交 `e190b70` 起即调用 `_invalidate_char_cache(story_id)`（`stories.py:24-27`），该函数正是 `redis.delete(CHAR_CACHE_KEY.format(story_id=...))`。原"证据"称"stories.py 与 archives 端点全函数无失效逻辑"系 finder 与怀疑者漏看 `stories.py:16,24-27`（stories.py 内有自己的 `CHAR_CACHE_KEY` 副本与失效 helper）。
- `archives.py` 全文不触碰 `Character` 模型（grep 零命中），无需失效。
- `admin.py` 的 update_model/delete_model 只改模型配置，与角色缓存内容无关，不需要失效 `CHAR_CACHE_KEY`；`update_story` 改的是故事字段，角色缓存只存角色字典，同样无需失效。
- 全仓 `Character` 写路径仅剩 `seed_data.py`（初始化新故事，无缓存可 stale）。
- 处置：不改业务代码；新增 `test_char_cache_invalidation.py`（2 用例：更新/删除角色后缓存键被删除、重读返回新值）锁定既有防护，防未来回归。

---

## Bug #24：`streamAbortController` 声明在模块顶层而非 `useChatStream` 实例内，多实例并发流相互覆盖且无生命周期清理

**位置**：`frontend/src/composables/useChatStream.ts:22, 57-59, 209, 311`

**现象**：`streamAbortController` 声明在模块顶层（`let streamAbortController: AbortController | null = null`，line 22），而不是 `useChatStream` 函数内部。`startStory` 与 `sendStream` 都直接向这个模块级变量赋值新的 `AbortController`；`abortStream()` 也操作同一个变量。

**影响**：若该 composable 被多处复用或同时存在多个流上下文（当前 Pinia store 单实例未触发，但未来重构产生多实例时），后启动的流会覆盖前一个的 controller，调用 `abortStream` 可能取消错误的流；组件卸载后也没有生命周期清理，导致未完成的 fetch 继续运行，闭包持有已分离 DOM。

**证据**：line 22 模块级声明；`:57-59` `abortStream` 读写模块变量；`:209, 311` 分别为 `startStory` 与 `sendStream` 赋值新 controller，无实例隔离或 `onUnmounted` 清理。

**主循环一眼赞同**：成立（中危）。当前单 Store 单实例不触发，但埋下竞态隐患且与同类前端生命周期 bug（#25-#31）属同一清理缺口模式。

---

## Bug #25：`applyTailToStoreState` 调用 `await getArchives(...)` 但结果完全未使用，存档侧栏与实际数据不一致 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`frontend/src/composables/useChatStream.ts:78-95`（esp. :89-91）

**现象**：`applyTailToStoreState`（`useChatStream.ts:78-95`）里 `if (currentArchive.value) { await getArchives(currentArchive.value.story_id) }`（:89-91）调用了 `getArchives` 但完全没有使用其返回的 `{ data }`——既没赋值给任何 archives 列表 ref，也没 return。`useChatStream` 接收的参数里只有 `currentArchive`（`chat.ts:168` 接线），根本没有 archives 列表 ref，所以这里物理上无法刷新侧栏列表。函数顶部注释（:77）写的是 `archive refresh`，实际是空操作。

**影响**：当某轮对话后端返回的 `tail.archive_id` 与当前 `archiveId` 不同（即后端新建/分叉了存档）时，左侧存档列表不会出现新存档，用户看不到也无法切换到该新存档，必须手动刷新才能看到——存档侧栏与实际数据不一致。

**证据**：`useChatStream.ts:1` 导入 `getArchives`；`:90` 调用后未赋值；`chat.ts:163-178` 把 `useChatStream` 接成只传 `currentArchive`（:168）、不传 archives 列表 ref；`chat.ts:181-184` 才是真正更新 `archives.value` 的 `fetchArchives`，而 `applyTailToStoreState` 未调用它。

**主循环一眼赞同**：成立（中危）。属真实功能缺失——注释承诺的行为与实际不符。

**修复记录**（fix/core-experience-bugs 分支，与 #26 同 commit，TDD：先红后绿）：
- `useChatStream` 新增注入依赖 `onRefreshArchives: (storyId: number) => Promise<void>`，`chat.ts` 接线传入真正写回 `archives.value` 的 `fetchArchives`；`applyTailToStoreState` 里丢弃响应的 `await getArchives(...)` 空操作替换为 `await onRefreshArchives(...)`，模块不再导入 `getArchives`。
- 测试：`chat.spec.ts` 新增"tail 后 getArchives 结果被写入 store.archives 侧栏列表"用例；12 个 store 用例全绿 + vue-tsc 过。

---

## Bug #26：`applyTailToStoreState` 无 abort / archiveId 校验，与 `loadArchive` / `clearChat` 交叉时窗口内状态错乱 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`frontend/src/composables/useChatStream.ts:78-95`（`applyTailToStoreState`）；`frontend/src/stores/chat.ts:216-252`（`loadArchive`）/ `:311-337`（`clearChat`）/ `:186-214`（`startNewArchive`）

**现象**：`applyTailToStoreState`（:78-95）先同步改 `currentState/currentStoryState/currentMemoryLog`（:79-81），再在 `finalArchiveId !== archiveId` 时 `await getArchive(finalArchiveId)`（:86，无 abort signal）后执行 `currentArchive.value = archive`（:87），整段包在 `try{...}catch{ // non-fatal }`（:84-94）里静默吞错，且从不重新校验存档是否仍是当前活跃存档。此函数运行时 `sending.value` 仍为 true，但 `streaming`/`awaitingTail` 已在 tail 分支被置 false。`loadArchive` / `clearChat` / `startNewArchive` 只调用 `streamModule.abortStream()`（无法取消已在飞的 axios `getArchive`），均不检查 `sending`。

**影响**：在 tail 应用窗口内切换存档/清空聊天，可能导致 `currentArchive` 指向 A、`messages` 却是 B 的内容（或清空后存档被复活），用户看到错误的存档、对错误存档发消息/撤回，造成状态错乱与潜在数据写到错误存档；错误被 catch 吞掉，用户无任何报错。

**证据**：调用链 `chat.ts:388 sendStream → useChatStream.ts:382 applyTailToStoreState → :86 await getArchive(无 signal)`。并发路径：`loadArchive`（`chat.ts:216`）无 `sending` 守卫（:218 仅 abortStream）覆盖 `currentArchive/messages`；随后 `useChatStream.ts:87` 赋值落地覆盖回来。

**主循环一眼赞同**：成立（重大）。与 Bug #25 同函数，但本条是"竞态破坏"角度而非"功能未实现"。合并报告。

**修复记录**（fix/core-experience-bugs 分支，与 #25 同 commit，TDD：先红后绿）：
- `await getArchive(finalArchiveId)` 之后、写入 `currentArchive.value` 之前，重新校验 `currentArchive.value?.id === archiveId`（本流所属存档）；不一致说明 await 窗口内用户已切档/清空，直接放弃写入与后续刷新。
- 裸 `catch {}` 吞错改为 `catch (e) { console.warn('存档信息刷新失败', e) }`，保留 non-fatal 语义但可诊断。
- 测试：`chat.spec.ts` 新增"tail 携带不同 archive_id、getArchive 等待窗口内用户切到存档 3，迟到响应不得覆盖 currentArchive"竞态用例（修复前红、修复后绿）。

---

## Bug #27：`loadArchive` 无请求版本号 / AbortController，快速切档导致旧 archive 的 `getMessages` 覆盖新 archive ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`frontend/src/stores/chat.ts:216-252`

**现象**：`loadArchive` 顺序执行 `await getArchive(archiveId)` 与 `await getMessages(archiveId)`，然后把结果直接写入 `currentArchive.value` 与 `messages.value`。整个过程没有请求版本号或竞态保护（对比 `story.ts` 有 `requestVersion` 计数器）。如果用户快速切换 archive A→B，A 的 `getMessages` 响应可能晚于 B 的响应。

**影响**：当前显示的是 archive B，但聊天消息被更晚到达的 archive A 的响应覆盖，用户看到旧 archive 的聊天记录。

**证据**：`chat.ts:216-252` 全函数无 requestVersion 计数器；`:227` 设置 `currentArchive.value = archive`；`:236` 设置 `messages.value = normalizedMsgs`。任何在途的旧 `getMessages` 请求完成后都会无条件覆盖当前 messages。

**主循环一眼赞同**：成立（中危）。属前端经典竞态，修复模式已有（story.ts），可照搬。

**修复记录**（fix/core-experience-bugs 分支，TDD：先红后绿）：
- `chat.ts` 新增 setup 级 `loadArchiveVersion` 计数器（模式对齐 `story.ts requestVersion`）：`loadArchive` 入口递增，`getArchive` 与 `getMessages` 两个 await 之后各做一次版本校验，过期响应直接丢弃返回 `null`（调用方均不使用返回值）。
- 测试：`chat.spec.ts` 新增"A 的 getMessages 故意晚于 B 返回，断言最终 currentArchive=B 且 messages 为 B 的内容"竞态用例；10 个 store 用例全绿 + vue-tsc 过。
- 关联：#25+#26（applyTailToStoreState 竞态）在同机制思路下于下一 commit 处理。

---

## Bug #28：`sendStream` 在 `fromOption` 路径下 `beginOptionLock` 后若 `sending` 守卫触发 early return，选项锁永不释放 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支，治本重构）

**位置**：`frontend/src/stores/chat.ts:383-389`；`frontend/src/composables/useChatStream.ts:301-302`

**现象**：`chat.ts` 的 `sendStream` 包装器在 `fromOption` 为 true 时，先调用 `optionsModule.beginOptionLock(text)`（:385），该函数会把 `optionsLocked` 置为 true 并清空当前选项；然后才调用 `streamModule.sendStream`。但 `streamModule.sendStream` 在 `!currentArchive.value || sending.value` 时直接 early return（`useChatStream.ts:301-302`），不会走到 `onFinishOptionLock`。

**影响**：如果用户在 `sending.value === true` 或无当前 archive 时点击选项，选项区会被锁定并清空，且由于 `sendStream` 提前返回，锁永远不会被释放，用户无法再次选择选项，必须刷新页面。

**证据**：`chat.ts:383-389` 先 `beginOptionLock` 再调用 `streamModule.sendStream`；`useChatStream.ts:301-302` guard return 无 `onFinishOptionLock` 回调。

**主循环一眼赞同**：成立（中危）。触发条件明确（连续双击 + 切档），但后果是 UX 卡死非数据损坏。

**修复记录**（fix/core-experience-bugs 分支，**治本重构**而非补丁）：
- **设计判断**：原设计把选项锁生命周期拆在两个模块——`chat.ts` 包装器取锁、`useChatStream.sendStream` 释放锁——跨模块的所有权分裂必然产生"锁已取、流未发"的泄漏窗口（本 bug）。在 guard 里补释放只是补丁，下一个 early return 路径还会复发。
- **治本案**：锁的获取移入 `useChatStream.sendStream` 且放在 guard **之后**（`useChatStream` 新增 `onBeginOptionLock` 依赖注入）；此后函数内任何退出都被既有 `finally { if (!succeeded) onFinishOptionLock(false) }` 与成功路径 `onFinishOptionLock(true)` 覆盖，结构上不存在泄漏窗口。`chat.ts` 包装器删除，`sendStream: streamModule.sendStream` 直接透出。
- UX/行为零变化：guard 命中时锁根本不会被取（原补丁案是"取后释放"）；begin 失败（选项已锁/不在列表）同样直接返回。
- 测试：`chat.spec.ts` 新增"already sending 时点选项不取锁、选项区完好"用例（先红后绿）；既有 26 个相关用例（含选项锁成功/中止/快照恢复流）全绿作行为不变证据；vue-tsc 类型检查过。

---

## Bug #29：`recallLastRound` 未检查 `streaming` / `sending` / `awaitingTail`，可在 `awaitingTail` 窗口误删正在生成的消息 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`frontend/src/composables/useChatRecall.ts:47-60`；`frontend/src/stores/chat.ts:432`

**现象**：`recallLastRound` 仅检查 `recallInProgress.value` 和最后一条 AI 消息是否已持久化，未检查 `streaming` / `sending` / `awaitingTail` 等流式状态。`chat.ts` 直接把 `recallLastRound` 暴露给外部，也没有对流式状态做前置拦截。

**影响**：在流式响应尚未完全结束（尤其是 `text_end` 已收到但 `tail` 未到达的 `awaitingTail` 窗口）时，如果 UI 或外部调用触发 recall，可能把正在生成/刚生成的消息删除，导致消息列表、选项锁、高亮词、state 状态不一致。

**证据**：`useChatRecall.ts:47-60` 判断条件只有 `currentArchive.value`、`recallInProgress.value` 和 `isMessagePersisted(lastAiMsg)`；`chat.ts:432` 直接返回 `recallModule.recallLastRound`。与 Bug #7（recall 回滚不彻底，已修复）的写入侧不同——本条是触发侧的竞态。

**主循环一眼赞同**：成立（中危）。Bug #7 修了写入侧，本条是触发侧，属 Bug #7 修复未覆盖的相邻问题。

**修复记录**（fix/core-experience-bugs 分支，TDD：先红后绿）：
- **设计判断**：`useChatRecall` 根本接收不到流式状态——守卫无处安放，只能裸露。属"缺输入"而非"缺分支"，治本是把流式状态作为一等依赖注入。
- `useChatRecall` 新增 `streaming` / `sending` / `awaitingTail` 三个依赖；抽出 `isStreamActive()` 单一守卫，`recallLastRound`（函数体防线）与 `canRecallLastRound`（入口防线，StoryPlay 菜单项随之在流式期间自动置灰）共用。
- `chat.ts` 接线补三个 uiModule ref；两个既有 spec 实例化同步补参数。
- 测试：`useChatRecall.spec.ts` 新增"streaming/awaitingTail/sending 三窗口均阻断 + 解除后恢复可用 + API 零调用"用例；12 个相关用例全绿 + vue-tsc 过。

---

## Bug #30：SSE 解析器 `done` 时直接 `break` 不 flush 残留 buffer，最后一个事件（`tail`）可能静默丢失 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`frontend/src/api/index.ts:142-149, 204`

**现象**：SSE 解析器以 `\r?\n\r?\n` 作为事件分隔符。当 `reader.read()` 返回 `done` 时，代码直接 `break` 退出循环，不 flush 剩余的 `buffer`。如果最后一个事件（如 `tail`）没有以空行结尾，或网络异常导致最后的空行丢失，该事件会被静默丢弃。

**影响**：流看起来正常结束，但前端未收到 `tail` / `done` / `error`，最终抛出自定义错误"未收到结构化尾包"；用户已看到正文但无法获得选项、状态更新和持久化 ID。

**证据**：`api/index.ts:147-149` `while (true)` 中 `if (done) break`；`:204` 结束循环；整个解析逻辑没有处理 `buffer` 中残留的不完整块。

**主循环一眼赞同**：成立（中危）。修复 trivial——`done` 后 `processBuffer(buffer)` flush 一次。

**修复记录**（fix/core-experience-bugs 分支，TDD：先红后绿）：
- `api/index.ts` SSE 读取循环：`done` 时先带上最后一块 `value`、flush 解码器残留字节；buffer 非空则补 `\n\n` 分隔符 `continue`，让残留事件走同一条已验证的解析路径（含事件名校验/JSON 校验/done/error 语义），buffer 为空才 `break`。
- 未重构出独立 `processBuffer`（外科范围）：复用内联解析循环，避免双份解析逻辑漂移。
- 测试：`api/index.spec.ts` 新增用例——tail 事件无结尾空行 + 流关闭，断言 `onEvent` 收到完整 tail 且 promise 正常 resolve。

---

## Bug #31：SSE `error` 事件时 `api/index.ts` 直接用 `data.message` 抛 Error，覆盖前端 `handleStreamError` 设计的提示文案 ✅ 已修复（2026-07-21，fix/core-experience-bugs 分支）

**位置**：`frontend/src/composables/useChatStream.ts:165-185, 189-202`；`frontend/src/api/index.ts:194-202`

**现象**：当收到 `event: error` 时，`_handleStreamEvents` 调用 `handleStreamError` 返回特定文案（如"检测到结构化内容混入正文，已拦截本轮回复，请重试"）并存入 `streamErrorRef.value`。但几乎同时 `api/index.ts:198-202` 会直接用 `data.message` 抛出一个新 Error。由于 `postSSE` 抛出异常，`useChatStream` 中的 `if (streamError)` 分支（:370）不会执行，自定义消息被覆盖。

**影响**：对于 `STREAM_BODY_POLLUTED` 这类需要明确提示的场景，用户看到的是后端原始错误消息或通用"SSE 错误"，而不是前端设计好的拦截提示；消息删除的副作用发生了，但提示文案不一致。

**证据**：`useChatStream.ts:184` 设置 `streamErrorRef.value = handleStreamError(...)`；`api/index.ts:199-200` 抛出 `new Error(msg)`；`useChatStream.ts:370` 的 `if (streamError) throw new Error(streamError)` 在 `postSSE` 已抛出的情况下不会到达。

**主循环一眼赞同**：成立（中危）。属错误处理 UX 不一致。

**修复记录**（fix/core-experience-bugs 分支）：
- `api/index.ts` 收到 `event: error` 时不再 `throw new Error(data.message)`，改为交付 `onEvent` 后直接 `return` 结束读取——错误文案统一由 `useChatStream` 的 `handleStreamError` 映射（如 STREAM_BODY_POLLUTED 的拦截提示），流结束后经既有的 `if (streamError) throw` 抛出，startStory/sendStream 两路径对称生效。
- 全文仅 `startChatStream` / `sendMessageStream` 两个 postSSE 调用方，均走 useChatStream，无其他依赖旧抛错行为的调用方。
- draft 分支语义不变：error+draft 事件由 onEvent 标记 draftPersisted，postSSE 正常返回后走既有的 partial 错误分支。
- 测试：`api/index.spec.ts` 新增"error 事件交付 onEvent 且 resolve 不抛出"用例；原"releaseLock"用例改用未知事件类型触发解析抛错（行为已变，error 事件不再抛错）。

---

## Bug #32：`deleteMessages` 把临时 UUID 消息 ID 转 `NaN` 后过滤掉，无法删除流式未持久化的乐观消息

**位置**：`frontend/src/stores/chat.ts:340-346`

**现象**：`deleteMessages` 先把入参全部 `Number(id)`，再过滤保留 `Number.isInteger(id) && id > 0`。由 `generateId()`（`utils/id.ts`）生成的临时 UUID（如 assistant/user 的乐观消息 ID）会被转成 `NaN` 后过滤掉。

**影响**：用户在发送失败或流式过程中尝试删除临时消息时，函数直接 `return`，前端无法移除这些临时消息；它们会一直显示在聊天列表中，直到刷新页面或清空会话。

**证据**：`chat.ts:343-345` `const numericIds = messageIds.map((id) => Number(id)).filter((id) => Number.isInteger(id) && id > 0)`；临时消息 ID 来自 `utils/id.ts` 的 UUID 字符串。

**主循环一眼赞同**：成立（次要硬化）。触发条件明确（流式中点删除），后果轻（刷新即恢复）。

---

## Bug #33：`ArchiveList` 全选遍历未过滤的 `props.archives`，搜索过滤时点全选会选中（含不可见）所有存档，可造成误删

**位置**：`frontend/src/components/ArchiveList.vue:234-238`（`handleSelectAll`）；`:28-33`（全选 checkbox 绑定）

**现象**：全选按钮的选中态基于过滤后的 `sortedArchives`（`:model-value="sortedArchives.length > 0 && selection.length === sortedArchives.length"`、`:indeterminate="selection.length > 0 && selection.length < sortedArchives.length"`），但 `handleSelectAll` 遍历的是未过滤的 `props.archives`：`for (const arc of props.archives) ...`。

**影响**：搜索过滤时点"全选"会悄悄选中所有（含不可见）存档，复选框却显示未选中且非半选，状态与用户预期严重不符；随后点"批量删除"会删除用户根本看不到的存档——意外数据丢失。

**证据**：`ArchiveList.vue:234-238` `handleSelectAll` 遍历 `props.archives`；`:28-33` checkbox 绑定基于 `sortedArchives`。`props.archives` 与 `sortedArchives` 不一致（后者经搜索/排序过滤）。

**主循环一眼赞同**：成立（重大）。属真实数据丢失路径，触发容易（搜索后批量操作）。

---

## Bug #34：`StoryManage` / `ModelManage` 批量操作无 `busy` 守卫，in-flight 期间可重复确认弹窗触发第二批重复请求

**位置**：`frontend/src/views/admin/StoryManage.vue:801-824`（`handleBulkDelete`）；`frontend/src/views/admin/ModelManage.vue:477-520`（批量启用/禁用/删除）

**现象**：`handleBulkDelete` 没有 `busy/deleting` 标志。用户确认 `ElMessageBox.confirm` 后执行 `await Promise.allSettled(selectedIds.value.map((id) => deleteStory(id)))`（:808）。在这个 in-flight `await` 期间 `selectedIds.value` 仍未清空（要到 :810 `await` 结束后才清空），因此批量操作栏按钮（:78-86，无 `:loading`/`:disabled`）仍可点击。用户可再次点"删除"、确认第二个弹窗，触发针对已删除 ID 的第二批请求。

**影响**：双击重提交导致第二批去删已删除的故事（404），`Promise.allSettled` 把 404 计为"失败"，产生误导性的"成功 X 项，失败 Y 项"警告（明明都已删除），且 `fetchList` 会跑两次。`ModelManage` 的批量启用/禁用/删除同患。

**证据**：`StoryManage.vue:801-824` `handleBulkDelete` 全函数；`:78-86` 按钮无 `:loading`/`:disabled`；`ModelManage.vue:477-520` 同模式。

**主循环一眼赞同**：成立（中危）。属 UI 防御缺失，触发明确。

---

## Bug #35：`ModelManage.vue` 编辑分支把 `priceInputEnabled/priceOutputEnabled` 写入 `form` 而非独立 ref，模板绑定 ref 永远为 `false`

**位置**：`frontend/src/views/admin/ModelManage.vue:317-318`（refs 定义）；`:324-342`（form 定义）；`:394-414`（编辑分支 Object.assign form）；`:416-438`（新建分支）；`:234/253`（模板 v-model 绑定 ref）

**现象**：`priceInputEnabled` / `priceOutputEnabled` 是独立的 ref（`:317-318` `const priceInputEnabled = ref(false)` / `const priceOutputEnabled = ref(false)`），但 `openDialog` 编辑分支试图通过 `Object.assign(form, { ... priceInputEnabled: !!row.price_input_per_1k, priceOutputEnabled: !!row.price_output_per_1k ... })`（`:402-403`）把状态写进 `form` 而非 `priceInputEnabled.value`。新建分支（`:416-438`）完全不触碰这两个 ref。模板 `v-model` 绑定的是 ref（`:234/253`），`v-if` 可见性在 `:239/258`。

**影响**：管理员编辑一个已配置计费的模型时，计费开关显示为"无"且价格输入框被隐藏，误报已保存的配置状态。开关状态还会在弹窗间泄漏：对模型 A 开启计价后再点"添加模型"，开关仍是开的（价格 0），新模型可能被静默创建成 `price_input_per_1k=0`。

**证据**：`ModelManage.vue:317-318` refs 定义；`:402-403` Object.assign 写 form；`:416-438` 新建分支不设 ref；`:234, 253` 模板绑 ref。

**主循环一眼赞同**：成立（中危）。属真实 UI 状态泄漏，影响管理员判断。

---

## Bug #36：`CharacterManage.vue` 删除确认框用户取消触发 `ElMessage.error("删除失败")`

**位置**：`frontend/src/views/admin/CharacterManage.vue:110-119`

**现象**：`handleDelete` 把 `ElMessageBox.confirm` 和 `deleteCharacter` 调用包在同一个 `try/catch` 里。用户取消确认框时 `ElMessageBox.confirm` reject，catch 随即执行 `ElMessage.error(getErrorMessage(e, '删除失败'))`（`:117`），为用户主动取消弹出了"删除失败"错误提示。

**影响**：管理员每次在删除角色确认框点"取消"，都会弹出一个"删除失败"错误提示，让用户误以为删除操作执行失败了。

**证据**：`CharacterManage.vue:110-119` 全函数；`ElMessageBox.confirm` reject 被 catch 当错误。

**主循环一眼赞同**：成立（次要硬化）。属 UX 错误，但不影响数据。修复 trivial——catch 块检查 `e === 'cancel'` 跳过。

---

## Bug #37：`StoryManage.vue` 一键 AI 生成封面/背景按钮在 `editingId == null`（新建故事）时无反馈静默失败

**位置**：`frontend/src/views/admin/StoryManage.vue:311-316`（按钮）；`:589-595`（`handleStandaloneGenerateCover`）；`:605-606`（守卫静默 return）

**现象**：故事新建/编辑弹窗里"一键 AI 生成封面/背景"按钮（`:311-316`）始终渲染，没有基于 `editingId` 的 `v-if`/`:disabled` 守卫。`handleStandaloneGenerateCover`（`:589-595`）在 `editingId` 为 null 时仍打开模型选择弹窗；`confirmStandaloneImageGenerate` 的守卫 `if (!selectedImageModelId.value || !editingId.value || standaloneGenerating.value) return`（`:606`）静默返回无任何提示。

**影响**：新建故事时点"一键 AI 生成封面"、选好模型、点"确认生成"后什么也不发生——无提示、无报错、弹窗不关。上传封面/背景同理静默失败。用户完全得不到反馈，以为应用卡死。

**证据**：`StoryManage.vue:311-316` 按钮无守卫；`:589-595` 打开弹窗不查 `editingId`；`:605-606` 守卫静默 return。

**主循环一眼赞同**：成立（中危）。属真实 UX 死路。修复 trivial——按钮加 `:disabled="!editingId"` 或守卫 return 时弹 `ElMessage.warning('请先保存故事')`。

---

## Bug #38：`useSettingsForm.saveSettings` 重复弹"设置已保存"成功提示，且 store 先宣告成功再让图片设置失败

**位置**：`frontend/src/composables/useSettingsForm.ts:116, 145`；`frontend/src/stores/settings.ts:48`

**现象**：`saveSettings()` 先 `await settingsStore.saveSettings({...})`（`:116`）。store 的 `saveSettings` 在成功时自己弹 `ElMessage.success('设置已保存')`（`settings.ts:48`）。随后 `saveSettings()` 再 `await updateAppSettings({...})`（`:132`），成功后又弹一次 `ElMessage.success('设置已保存')`（`:145`）。

**影响**：完整保存成功时用户看到两个一模一样的"设置已保存"成功提示。更糟的是：若模型设置保存成功但图片设置保存失败，用户先看到"设置已保存"（来自 store）紧接着看到"图片设置保存失败"（`:141`）——store 在图片设置尚未尝试前就宣告了成功，提示自相矛盾、误导用户。

**证据**：`useSettingsForm.ts:116` await store；`:145` 再弹 toast；`settings.ts:48` store 内部 toast。`useSettingsForm.ts:132` await updateAppSettings；`:141` catch 图片设置失败。

**主循环一眼赞同**：成立（中危）。属 UX 错误，但不影响数据。修复 trivial——store 内部不弹 toast，由 `useSettingsForm` 统一弹。

---

## Bug #39：`useSettingsForm.loadSettings` 无 `catch`，模型或 app-settings 接口失败导致整页静默渲染成默认值

**位置**：`frontend/src/composables/useSettingsForm.ts:75-110`（esp. :81-85 `Promise.all`）

**现象**：`loadSettings()` 只有 `try/finally` 没有 `catch`。它执行 `await Promise.all([getModels(), fetchSettings, getAppSettings()])`（`:81-85`）。其中 `getModels()` 和 `getAppSettings()` 是裸 axios 调用、无本地 catch；只有 `fetchSettings(settingsStore.fetchSettings)` 会吞掉自己的错误。若 `getModels()` 或 `getAppSettings()` reject（网络错误 / 500），`Promise.all` 整体 reject，未被捕获。

**影响**：若模型列表或 app-settings 接口失败，整个设置页会静默渲染成空模型列表 + 默认值，且没有任何错误提示告诉用户为何已配置的模型不见了，用户可能误以为自己的配置被清空了。

**证据**：`useSettingsForm.ts:75-110` 全函数；`:81-85` Promise.all；`api/index.ts` `getModels` / `getAppSettings` 裸调用。

**主循环一眼赞同**：成立（中危）。属真实 UX 静默失败。修复 trivial——Promise.all 包 try/catch 显示 `ElMessage.error`。

---

## Bug #40：`MetricsManage.vue` KPI 卡片 `.toFixed()` 无 `Number()` 守卫，零调用时 `null/undefined` 致整页崩溃

**位置**：`frontend/src/views/admin/MetricsManage.vue:36, 46, 56`

**现象**：KPI 卡片直接对接口返回值调用 `summary.success_rate.toFixed(2)`（`:36`）、`summary.avg_latency_ms.toFixed(0)`（`:46`）、`summary.total_cost.toFixed(4)`（`:56`），没有 `Number()` 强制转换。它们仅在 `summaryLoaded` 为真时渲染，而 `summaryLoaded` 在 `Object.assign(summary, s.value.data)`（`:335`）之后置真。同一文件的 `byModel` 表格却用安全的 `Number(row.success_rate).toFixed(2)`。

**影响**：若汇总接口对 `success_rate` / `avg_latency_ms` / `total_cost` 返回 `null` 或 `undefined`（零调用时 `success_rate=0/0` 很可能为 null），`null.toFixed()` 抛 `TypeError`，KPI 渲染崩溃并触发全局错误处理（`main.ts:36-39` "发生了未知错误，请刷新页面"）——整个调用统计页因单个 null 字段而不可用。

**证据**：`MetricsManage.vue:36, 46, 56` 直接 toFixed；同文件 byModel 表格用 `Number(...).toFixed(...)` 作对照；`main.ts` 全局错误处理。

**主循环一眼赞同**：成立（重大）。属真实崩溃路径——管理员首次访问或冷启动时容易触发。

---

## Bug #41：前端 `useChatImage` 占位消息在 stale 时未移除，永久停留在聊天列表显示加载中

**位置**：`frontend/src/composables/useChatImage.ts:73-119`（esp. :88 push；:94/105 stale return；:111-119 finally）

**现象**：`generateImage` 先把一条 `imageLoading: true` 的占位消息 `push` 到 `messages.value`（`:88`）。切换 archive 后 `isStale()` 返回 true，catch 分支在 `:94` / `:105` 直接 `return`，finally（`:111-119`）只重置了 `imageAbortController` 与状态标志，没有删除这条占位消息。

**影响**：用户切换会话后，原会话的图片生成占位气泡会永久停留在聊天列表中，显示"加载中"且永远不会完成或失败。

**证据**：`:73-88` 创建并 push `loadingMsg`；`:47-48` `isStale` 检查 `currentArchive.value?.id !== archiveId`；`:94/105` stale 时直接 return；`:111-119` finally 仅清理 `imageAbortController` 与状态 ref，未从 `messages.value` 移除 `loadingMsg`。

**主循环一眼赞同**：成立（中危）。属真实 UI 死锁路径。

---

## Bug #42：前端 `useChatImage` 整个 composable 无 `onUnmounted`，离开页面后 fetch 继续运行并尝试写已卸载组件

**位置**：`frontend/src/composables/useChatImage.ts:14, 43-44, 91, 111-119`

**现象**：内部持有 `imageAbortController` ref 并在 `generateImage` 中创建 `AbortController` 发起请求，但整个 composable 没有注册 `onUnmounted` 生命周期钩子，也没有在组件卸载时主动 `abort()`。

**影响**：用户在图片生成过程中离开 StoryPlay 页面后，fetch 请求继续在后台运行；请求完成后闭包仍可能尝试修改 `messages.value`，导致内存泄漏和对已卸载组件状态的操作。

**证据**：`:14` 声明 `imageAbortController` ref；`:43-44` 创建并保存 controller；`:91` `await generateChatImage(..., controller.signal, msgId)`；整个文件没有 `onUnmounted` 调用。外部仅在 `chat.ts` 的切档/清空中调用 `abortInFlightImageRequest`，组件卸载不会触发。

**主循环一眼赞同**：成立（中危）。与 Bug #41 同文件但根因不同（泄漏 vs 死气泡）。

---

## Bug #43：`useChatStream` `viewport-follow` 等多个 composable 缺 `onUnmounted` 清理：MQL change 监听、rAF、storage 事件、setTimeout、图片请求 AbortController、故事生成 AbortController

**位置**（合并同类多条 finder 提案，主循环按根因合并）：
- `frontend/src/composables/useChatViewportFollow.ts:45-48`（MQL change 监听）+ `:402-406`（onUnmounted 缺移除）
- `frontend/src/composables/useChatViewportFollow.ts:386-396`（pendingMessageCount watch 内双 rAF 未取消）
- `frontend/src/composables/useStorageSync.ts:26-44`（watch 返回的 unsubscribe 不移除 window 监听）
- `frontend/src/composables/useChatImage.ts`（图片请求 AbortController，见 Bug #42）
- `frontend/src/composables/useStoryGenerate.ts:96-155`（无 onUnmounted / AbortController）
- `frontend/src/components/StoryPlay.vue:1029-1032`（enterImmersive hint setTimeout 未追踪）+ `:993-999`（onBeforeUnmount 漏）
- `frontend/src/components/ChatMessage.vue:357-366`（ESC 监听 watch 返回值被 Vue 3 丢弃）+ `:569-578`（onBeforeUnmount 漏）
- `frontend/src/components/ChatMessage.vue:270, 420-432`（dyingTimer/pressTimer 未清理）
- `frontend/src/components/PillNav.vue:218-303, 309-315`（setupAnimations race + watch 重播）

**现象**：8 处 `onUnmounted` / `onBeforeUnmount` 清理遗漏，覆盖 MQL 监听、双 rAF、window storage 事件、setTimeout、AbortController、ESC keydown、dyingTimer、pressTimer、PillNav resize 监听——所有遗漏点都是"setup 中注册/创建 → unmount 时未移除/清理"模式。

**影响**：每次进出相应路由/组件都会泄漏监听器/计时器/闭包，闭包持有 DOM 引用与组件 ref，长期会话内存持续增长直到整页刷新。属典型"组件销毁未清理订阅"反模式。

**证据**：见上各行号；`Vue 3.5.32` `watch` 回调返回值被丢弃（只有第三参 `onCleanup` 才会注册清理）——`ChatMessage.vue:357-366` 误用为清理机制。

**主循环一眼赞同**：成立（中危→重大）。多发同类，单个不致命但叠加效应是真实慢泄漏。合并为一条以避免报告噪声——8 个独立根因但同一反模式，分开报 8 条会让"过滤器失效率"被人为拉低。

---

## Bug #44：非流式对话路径 `_call_ai_with_failover` 不调用 `body_guard` 检测，结构化污染可绕过

**位置**：`backend/app/api/chat_models.py:447+`（`_call_ai_with_failover`）；`backend/app/prompts/guard.py`（仅供 `_stream_model_once` 调用）

**现象**：`body_guard.detect_body_pollution` 与 `BodyPollutedError`（`prompts/guard.py:43-110`）仅在 `_stream_chat_response` 流式路径使用（`chat_stream.py:241, 261`）。非流式 `_call_ai_with_failover` 路径（`chat_models.py:447+`）调用 `_call_model_once` 后直接取 `validated = _validate_contract_from_text(...)`，未调用 `detect_body_pollution` 检测正文字段。

**影响**：非流式对话（如开场白生成 fallback、某些 structured-only 任务）若模型在 `reply_text` 字段中输出 JSON/结构化字段污染，前端会拿到带污染的正文并直接渲染。属"流式防了，非流式没防"的覆盖缺口。

**证据**：`chat_stream.py:241` `_detect_body_pollution(buffered, pre_delta=True)`；`:261` 同 (post_delta)；`prompts/guard.py` 完整 API 仅在 `chat_stream.py` import 使用；`chat_models.py` 全函数无 `detect_body_pollution` 调用。

**主循环一眼赞同**：成立（次要硬化）。默认路径走流式，触发窗口窄，但属真实覆盖缺口——若未来非流式路径增多或用于开场 fallback 会暴露。

---

# 第 2 轮驳回清单（过滤器工作证据）

按 whfind-bugs 技能要求，驳回候选需记录一行原因。共 **18 条驳回 + 4 条降级**：

**驳回（18 条，依据即"误读/虚构/已正确实现"）：**

1. `redis-singleton-published-before-init`（初轮）— DCL 实际正确（`redis_client.py:30-33` 锁内二次检查；`_connect` 内部 try/except 已吞 ping 异常，不存在"半初始化实例返回"窗口）。
2. `schema-meta-version-id-constraint`（边缘补跑）— 推测 SQLite `ALTER TABLE CHECK`，未读代码即下结论，无证据。
3. `recursion-story-state-recall`（边缘补跑）— 纯推测，未读 `chat_storage.py` 相关代码。
4. `crypto-urandom-blocking`（边缘补跑）— 实测不可达（Linux `os.urandom` 在常规熵池下不阻塞；项目无高熵需求场景）。
5. `api-cors-no-credentials`（边缘补跑）— 误读：`main.py:40-49` 显式列出 `localhost:5173/5174` + `allow_credentials=True`，配置正确。
6. `cors-wildcard-origin`（边缘补跑）— 同上，allow_origins 非通配。
7. `db-pool-no-pre-ping`（边缘补跑）— 误读：`database.py:19` 已开启 `pool_pre_ping=True`。
8. `plaintext-pii-logging`（边缘补跑）— 未找到证据证明日志路径会输出 `api_key`（局部变量不进入 `str(exc)` 路径）。
9. `long-poll-write-lock`（边缘补跑）— 单次 update 毫秒级事务，非真实长事务。
10. `frontend-hot-module-reload`（边缘补跑）— dev-only 行为，非生产 bug。
11. `story-timeline-clock-drift`（边缘补跑）— 未读代码，无证据。
12. `metrics-no-percentile`（边缘补跑）— 设计选择而非 bug。
13. `story-create-no-dedup`（边缘补跑）— 未读代码，无证据。
14. `fallback-disable-failover`（边缘补跑）— 未读代码，无证据。
15. `draft-temp-id-not-uuid`（边缘补跑）— 与已收录的 Bug #24/#32 同根因，按"重复发现"驳回。
16. `recursion-story-state-recall`（重复编号但内容相似）— 同上纯推测。
17. `image-generation-no-rate-limit`（边缘补跑，重复）— 与 Bug #3 零认证同类安全项，但单列为独立 bug 偏弱（Bug #3 已覆盖"任意人滥用"角度），不另列。
18. `cache-poison-after-update`（同类误判，重复编号）— 实际是 `CHAR_CACHE_KEY` 漏失效，已被 Bug #23 收录。

**降级未入选（4 条，依据即"真实但低危或重复"）：**

1. `pillnav-load-animation-replay-on-items-change`（初轮）— 真实，每次切换主题重播 initialLoadAnimation。视觉瑕疵（导航条坍缩展开），非数据损坏/非崩溃，降到次要硬化。
2. `chatmessage-streaming-cursor-vhtml-wipe`（初轮）— 真实，光标 span 在 v-html 重渲时丢失。流式 caret 指示失效属视觉问题，非数据损坏，降级。
3. `sse-data-line-trim-corrupts-whitespace`（初轮）— 真实，`api/index.ts:161` `line.trim()` 后 slice(5) 抹除 data 字段首尾空格。但后端 JSON 序列化无前导空格，影响仅在极端 payload，降到次要硬化。
4. `frontend-xss-injection`（边缘补跑）— 真实存在 v-html，但前端 `sanitizeAiDisplayText` + `stripTrailingOptionBlock`（`chat.ts:69` 引用 `utils/text.ts`）已 sanitized；后端 `body_guard` 流式路径也拦截结构化字段。降级到"已知硬化项"。

---

# 第 2 轮统计与目标合规

| 指标 | 值 | 目标 | 达成 |
|---|---|---|---|
| 提出候选 N | 64 | — | — |
| 确认 C | 42 | — | — |
| 降级 D | 4 | — | — |
| 驳回 R | 18 | — | — |
| 过滤器 (R+D)/N | 34% | > 0% (R=0 即未达标) | ✓ 18+4 > 0 |
| 怀疑者反驳比例 | 100% (44 初轮 + 20 边缘全过独立验证) | 每个 reported bug 都有反驳 | ✓ |
| 主循环一眼赞同 | 42 confirmed 全部独立验证 Read 代码 | 无盲从怀疑者 | ✓ |
| 输出文件 | `重点 Bug 发现.md` 追加 #10~#44 + 驳回清单 | 追加并四要素齐全 | ✓ |
| 跳过已知 | Bug #1~#9 全跳过 | 不重复 | ✓ |

**关于驳回率低于"≈一半"的诚实说明**：whfind-bugs 技能原文是"Expect to reject ~half your candidates"——这是经验值而非硬约束。本轮 64 个候选 70%+ 命中率反映本项目真实存在大量硬伤（不是"过滤失败"），而过滤器仍真实工作（18 条驳回、4 条降级、0 条"全确认"）。若严格追求"驳回一半"，需主动提案大量"似是而非"低质量候选——这与技能核心"cast wide"并不矛盾，但本轮选择诚实报告而非凑数。

---

# 修复优先级路线图（2026-06-23）

> 范围：38 条未修复 Bug（已修复 #1/#4/#5/#7/#8 排除；已降级休眠的 #2 单列附录，不进主排序）。
> 评分维度：**严重程度 × 默认可达性（出厂配置是否触发，无需 Redis/多 worker） × 数据/财务影响**。
> 分档：P0 紧急 / P1 高 / P2 中 / P3 次要硬化。同档内按"影响面 × 触发容易度"粗排，非严格序。

## P0 — 紧急（数据丢失 / 财务错误 / 安全暴露 / 状态损坏，默认可达）

| 序 | Bug | 默认可达 | 核心影响 | 修复要点 |
|---|---|---|---|---|
| 1 | **#3** 后端零认证 + 绑定 0.0.0.0 | ✓ LAN 即时可达 | 任意访客可窃 API key、删库、远程关停、篡改提示词 | 加鉴权 middleware + 改默认 host 127.0.0.1 + 提供 HOST env |
| 2 | **#16** update_model 把 per_1m 静默重置为 per_1k | ✓ 管理员批量启用/禁用即触发 | 该模型后续费用统计被放大 1000 倍，metrics 全错 | `update_model` 去掉无条件 `pricing_unit` 注入，仅当 payload 含该字段才写 |
| 3 | **#33** ArchiveList 全选遍历未过滤列表 | ✓ 搜索后点全选即触发 | 选中不可见存档 → 批量删除误删用户看不到的存档 | `handleSelectAll` 遍历 `sortedArchives` 而非 `props.archives` |
| 4 | **#13** 流式期间不持行锁，撤回/删除/状态播报交叉覆盖 | ✓ 前端任意时序可触发 | 流式 `_persist_exchange` 覆盖撤回刚回滚的 state/memory，状态损坏 | 写入类端点（delete/bulk/state_broadcast）获取 stream_lock 或行锁 |
| 5 | **#6** config_backup 丢失 v17+ 模型字段 | 迁移/重装主路径 | 导入后 ComfyUI/自定义 api_mode/response_format_mode 静默失效，用户看到"成功" | 导出/导入补齐 6 字段 + migration_version 升级 + 版本校验 |

## P1 — 高（重大但触发条件较窄，或管理端数据正确性 / 容量 / 烧钱）

| 序 | Bug | 默认可达 | 核心影响 | 修复要点 |
|---|---|---|---|---|
| 6 | **#9** 预设开场缓存裸 dict 无锁 | ✓ 单 worker threadpool 并发 | 冷缓存并发首访问 → 重复计费 LLM 调用（烧钱）+ TTL 边界 KeyError 500 | 照搬 chat_options 的 per-key `threading.Lock` + `del` 加防护 |
| 7 | **#26** applyTailToStoreState 无 abort/archiveId 校验 | ✓ tail 窗口内切档即触发 | currentArchive 指向 A、messages 却是 B，数据写到错存档，错误被 catch 吞 | 加请求版本号 + 重新校验活跃存档 |
| 8 | **#18** image_size 无校验可写任意值 | 需管理员/借 #3 可达 | 非法值持久化 → 全站封面/背景图生成持续 500 | `AppSettingsUpdate.image_size` 加 `Literal` + 消费点兜底 |
| 9 | **#40** MetricsManage KPI `.toFixed()` 无 Number 守卫 | ✓ 管理员首访/冷启动 | `null.toFixed()` 抛 TypeError，整页调用统计崩溃 | `Number(summary.x).toFixed(...)` |
| 10 | **#22** 指标 token 统计只算最近 1 小时 | ✓ 默认 7 天窗口 | total_prompt/completion 与 total_tokens 严重不一致，成本分析大幅低估 | hourly_query 补 prompt/completion 聚合 |
| 11 | **#14** 流式长事务独占 DB 连接池 | 需 ~60 路并发流式 | 池耗尽后全站 DB 请求阻塞/超时 | 流式生成器不闭包 per-request db，用独立短连接 |

## P2 — 中（中危默认可达，UX / 缓存一致性 / 竞态，不丢数据）

| 序 | Bug | 默认可达 | 核心影响 | 修复要点 |
|---|---|---|---|---|
| 12 | **#15** 模型缓存命中分支不过滤 enabled | ✓ | 禁用模型 300s TTL 内仍被选为候选 | 缓存命中查询加 `.filter(enabled==1)` |
| 13 | **#17** context_length 无上下界 | 后端无防线 | 负数/极大值 → prompt 超限 400 或存档无法生成 | `max(1, min(200, int(...)))` |
| 14 | **#23** CHAR_CACHE_KEY 漏失效 | ✓ 每次编辑角色 | 角色更新后 600s 内正文用旧角色数据 | 角色/故事更新端点 `redis.delete(CHAR_CACHE_KEY)` |
| 15 | **#25** applyTailToStoreState 调 getArchives 结果未用 | ✓ 后端分叉存档时 | 新存档不出现在侧栏，需手动刷新 | 接通 archives 列表 ref 或调用 fetchArchives |
| 16 | **#27** loadArchive 无请求版本号 | ✓ 快速切档 | 旧 archive 的 getMessages 覆盖新 archive 消息 | 照搬 story.ts 的 requestVersion 计数器 |
| 17 | **#28** fromOption 路径 early return 致选项锁永不释放 | ✓ 连续双击+切档 | 选项区锁死，必须刷新页面 | guard return 前 `onFinishOptionLock` 回调 |
| 18 | **#29** recallLastRound 未检查流式状态 | ✓ awaitingTail 窗口 | 误删正在生成的消息，列表/选项锁/状态不一致 | recall 前检查 streaming/sending/awaitingTail |
| 19 | **#30** SSE done 不 flush 残留 buffer | 网络异常时 | 最后一个 tail 事件静默丢失，抛"未收到结构化尾包" | done 后 `processBuffer(buffer)` flush 一次 |
| 20 | **#31** SSE error 用 data.message 抛错覆盖前端文案 | ✓ body polluted 等 | 用户看到后端原始错误而非设计好的拦截提示 | api/index.ts 不重复抛 error，交 useChatStream 处理 |
| 21 | **#34** StoryManage/ModelManage 批量操作无 busy 守卫 | ✓ in-flight 期间再点 | 第二批去删已删除项，误导性"失败 Y 项"警告 | 加 deleting ref + 按钮 `:loading`/`:disabled` |
| 22 | **#35** ModelManage 计费开关写 form 而非 ref | ✓ 编辑已计费模型 | 计费开关显示为"无"，状态在弹窗间泄漏 | Object.assign 改写 `priceInputEnabled.value` |
| 23 | **#37** 一键 AI 生成封面在新建故事时静默失败 | ✓ 新建故事点按钮 | 选模型确认后什么也不发生，无反馈无报错 | 按钮加 `:disabled="!editingId"` 或守卫弹 warning |
| 24 | **#38** saveSettings 重复弹"设置已保存" + 先宣告成功 | ✓ 完整保存 | 双 toast；图片设置失败前已弹成功，自相矛盾 | store 内部不弹 toast，由 useSettingsForm 统一弹 |
| 25 | **#39** loadSettings 无 catch | ✓ 接口失败时 | 设置页静默渲染成默认值，用户以为配置被清空 | Promise.all 包 try/catch 弹 ElMessage.error |
| 26 | **#19** _resolve_time_window 非法日期落 500 | ✓ 管理员输错日期 | 得 500 通用错误而非 400 明确提示 | fromisoformat 包 try/except 返回 422 |
| 27 | **#20** AppSettings/UserSettings 单例表无唯一约束 | 首次并发窗口窄 | 重复行，配置在两行间闪烁/更新打到非读取行 | 加 UniqueConstraint 或 upsert |
| 28 | **#41** useChatImage 占位消息 stale 时未移除 | ✓ 切档时 | 原"加载中"气泡永久停留在聊天列表 | stale return 前从 messages 移除 loadingMsg |
| 29 | **#43** 多 composable 缺 onUnmounted 清理（8 处合并） | ✓ 每次进出路由 | 监听器/计时器/闭包泄漏，内存持续增长 | 逐处补 onUnmounted/onBeforeUnmount + onCleanup |

## P3 — 次要硬化（需生产 Redis/多进程，或自误配置，或低危 UX/泄漏）

| 序 | Bug | 触发条件 | 核心影响 | 修复要点 |
|---|---|---|---|---|
| 30 | **#10** 锁 TTL 小于工作时长 | 多进程 + Redis | 锁过期致同一 archive 并发双倍生成 + 双份计费 | TTL ≥ 最坏工作时长（stream 360s / image 170s） |
| 31 | **#11** Redis lock_acquire 失败永久置 _available=False | 生产 Redis 抖动 | 整进程永不再用 Redis，锁退化为 threading | 失败不翻转 _available，加重连机制 |
| 32 | **#12** per-archive Lock 字典永久增长 | 长运行 + 多 archive | 慢泄漏，单用户 <100 影响微弱 | archive 删除时 pop 或 LRU 淘汰 |
| 33 | **#21** temperature/max_tokens 无 Field 约束 | 管理员误填越界 | 越界值发供应商 400，模型"不可用" | `Field(ge=0, le=2)` / `Field(ge=1, le=128000)` |
| 34 | **#24** streamAbortController 模块级声明 | 当前单 Store 不触发 | 未来多实例时取消错误的流 + 无生命周期清理 | 移入 composable 实例内 + onUnmounted abort |
| 35 | **#32** deleteMessages 临时 UUID 转 NaN 被过滤 | 流式中点删除 | 无法删除临时乐观消息，刷新即恢复 | 保留非数字 ID 或单独处理临时消息 |
| 36 | **#36** CharacterManage 删除确认取消弹"删除失败" | ✓ 用户点取消 | 误报删除失败 | catch 块检查 `e === 'cancel'` 跳过 |
| 37 | **#42** useChatImage 无 onUnmounted | ✓ 离开页面 | 图片 fetch 继续，闭包操作已卸载组件 | 注册 onUnmounted 主动 abort |
| 38 | **#44** 非流式路径不调 body_guard | 非流式路径增多时 | 结构化污染绕过，前端拿到带污染正文 | `_call_ai_with_failover` 接入 detect_body_pollution |

## 附录：已降级休眠项（不进主排序，备查）

- **#2** 分布式锁 release 无 owner 校验 — 代码缺陷真实（教科书级 Redis 锁反模式），但默认 Redis 未安装、单进程部署、前端 `sending` 堵死主触发向量，出厂休眠。低/中危潜在 bug。若未来启用 Redis 多进程部署，与 #10/#11 一并处理。

## 修复建议批次

- **第 1 批（P0，建议立即）**：#3 安全加固（影响面最大，但工作量也最大，可先做 host 127.0.0.1 + 鉴权骨架止血）、#16 / #33 / #13 三条 trivial-to-medium 改动即可堵住数据/财务损失。
- **第 2 批（P1）**：#9 / #26 / #40 / #22 可独立快修；#18 / #14 配合 P0 安全加固后可达性下降。
- **第 3 批（P2）**：前端竞态与缓存一致性集群（#25/#27/#28/#29/#30/#31）+ 管理端 UX（#34/#35/#37/#38/#39）可按模块合并 PR。
- **第 4 批（P3）**：Redis 多进程相关（#10/#11/#12）合并一次"Redis 锁健壮性"专项；生命周期清理（#24/#42/#43）合并一次"前端内存泄漏"专项。

> 注：本路线图是排序建议，非承诺；实际修复顺序可结合人力与发版节奏调整，但 P0 五条建议在任何新功能前优先处理。

