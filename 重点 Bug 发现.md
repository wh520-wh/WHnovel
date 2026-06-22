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

## Bug #6：config_backup 导出/导入丢失 v17 之后新增的全部 ModelConfig 字段，恢复备份后 ComfyUI/自定义 API 模式静默失效

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

---

## Bug #7：撤回（recall）最后一轮 AI 消息后，archive 的状态/剧情/记忆未回滚，tail 仍读陈旧字段导致状态漂移与 memory_log 污染

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

---

## Bug #8：`redis.set(..., ex=...)` 关键字参数与 wrapper 签名不匹配，启用 Redis 时每次角色加载抛 TypeError → 聊天硬 500（含第二处 chat_models.py:399）

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

---

## Bug #9：预设开场缓存 `chat_cache` 模块级裸 dict 无锁，默认部署下 threadpool 并发可致重复 LLM 调用 + TTL 边界 KeyError 500

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

---

## 本轮驳回/降级记录（过滤器工作证据）

- **驳回**：seed_data `init_db` 升级重复插入示例故事——前提虚假。`.seed_done` 自根提交 `e190b70`（首次公开发布）起即被 git 跟踪、从未被任何提交删除；不存在"早于 seed_flag 机制的旧版本"可升级。仅当用户手动删除被跟踪的 `.seed_done` 文件才触发，非真实升级路径。判为防御性小瑕疵，非 bug。
- **降级未入选**：`story_id=0` 封面/背景图文件名用 `int(time.time())` 无 uuid，同秒并发生成会覆盖。真实 oversight（对话图路径 `image_generation.py:200` 用了 `uuid.uuid4().hex`，封面/背景路径漏），但需两个 `ai-generate` 请求的图片保存落在同一秒窗口，单用户 UI 不可达，影响是"封面图显示成别人的"（持久但视觉层面，无数据丢失/无崩溃）。判为次要硬化项，未列入三大。

