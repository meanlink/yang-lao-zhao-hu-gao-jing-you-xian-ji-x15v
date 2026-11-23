# 养老照护告警优先级

朝晖长者照护中心的班组用这个工作台登记巡视观察、维护待补与告警队列，并将复核后的接续事项交给下一班。

## 场景与边界

虚构客户朝晖长者照护中心有东、西两翼，约 60 张床位，分早、中、晚三班。过去每班用纸质巡房单和共享表传递照护事项。待核对项常被当作已确认的否定项，值班长要逐本核对告警依据，临近交班还会出现口头交代与表内版本不同的情况。

巡房单、呼叫记录和照护任务回执进入本应用。应用维护观察与优先级、值班长复核和接班签收，下一班以已签交班记录为接续依据。模型与种子均使用合成数据，等级表示跟进顺序，本项目面向流程演示。

| 角色 | 演示账号 | 可执行操作 |
|---|---|---|
| 照护员 | `carer@zhaohui.local` | 看住户档案、录入及补录观察、查看告警与交班 |
| 值班长 | `lead@zhaohui.local` | 登记住户、录入或补录、复核及上调告警、提交交班、查看审计 |
| 接班员 | `receiver@zhaohui.local` | 查阅观察、告警及交班，签收当前版本 |

演示账号密码均为 `zhaohui-demo`。

## 一班的工作剧本

1. 17:05，照护员按东翼二层筛选，打开 218-A 许文兰的住户卡。值班员核对 `OBS-DEMO-2181` 的四项已确认信号。
2. 17:10，告警队列保留「优先处理」。新的走廊巡查单 `OBS-DEMO-2182` 有一项协助移位待确认，该住户整轮告警处于「待补观察」。
3. 17:15，照护员补上同事核对的移位状态。后台 worker 领取完整观察并重新分级，已有「优先处理」保留。
4. 17:21，值班长检查候选与次选之间的特征贡献、关联观察及报告版本，填写复核说明。
5. 17:25，值班长选择晚班并提交「核对 218-A 移位协助回执」。交班单锁定此时的告警版本与观察编号。
6. 17:30，晚班接班员核对接续事项、签收，告警进入已交接。交班归档保留对应快照。
7. 17:35，晚班接班员检查 312-B 梁开明的种子交班记录「核对 312-B 例行巡视回执并登记」，按相同流程处理待签单。

如果提交后又收到同一住户的新观察，原待签单作废。页面会保留旧快照，提醒双方再次核对当前告警版本。

## 快速启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

| 入口 | 地址或端口 |
|---|---|
| 原生前端 | `http://localhost:18248` |
| FastAPI Swagger | `http://localhost:19248/docs` |
| PostgreSQL | `localhost:17748`，数据库和用户均为 `care` |

`docker compose down` 保留数据。`docker compose down -v --remove-orphans` 同时清理具名卷，供干净验收使用。五个服务分别是 Nginx 前端、FastAPI、Python worker、PostgreSQL、Redis。容器启动时自动初始化表。Redis 支持 worker 心跳和登录节流，PostgreSQL 保存待评分观察。共享 `model_files` 卷供 API 读取 worker 写入的模型签名。

`.env` 控制 `FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT`、`POSTGRES_PASSWORD`、`JWT_SECRET` 和 `SEED_DEMO`。演示配置默认绑定本机回环地址。关闭 `SEED_DEMO` 可启动空库，`python -m scripts.seed_demo` 可另行创建演示账号和样例。

### 本地开发

推荐以 Compose 运行依赖。需要在主机调试 API 时，可启动 `db`、`redis` 并在另一个本地端口提供 Redis；在 `backend/` 中使用 Python 3.11 的虚拟环境安装 `requirements.txt`，运行 `uvicorn src.main:app --reload --port 19248`。给进程提供 `PGHOST`、`PGPORT`、`PGDATABASE`、`PGUSER`、`PGPASSWORD`、`REDIS_URL`、`JWT_SECRET` 和可写的 `MODEL_DIR`，然后用相同环境启动 `python -m src.worker`。前端 ES modules 无需编译，集成调试时由 Nginx 同源代理 `/api/`。

## 分级与解释

`backend/scripts/synthetic_shift_labels.csv` 含三类各八条合成记录，四个输入为已确认的是或否。`backend/src/priority_model.py` 估计伯努利朴素贝叶斯先验与条件概率。设类别 $k$ 有 $N_k$ 条，$x_j$ 是第 $j$ 项信号，$n_{jk}$ 是信号为真的计数。先验为 $(N_k+1)/(N+3)$，条件概率 $p_{jk}=(n_{jk}+1)/(N_k+2)$。分类时将先验对数与各信号对数似然相加。归一化后验用于展示三个候选的相对得分。完全同分时取优先级较高的类别。

候选与次选之间的对数分数差，等于先验对数赔率与四项特征贡献之和。界面展示观测取值和贡献的正负。模型输出同时保留语料 SHA-256，便于重现分级结果。空白字段存在时，观察留在待补表行中，worker 只领取完整观察。每个住户同时至多有一条在办告警，本轮实际等级取历史最高确认或候选等级，直到接班员签收。

## 代码结构

| 路径 | 职责 |
|---|---|
| `backend/migrations/001_care.sql` | 领域表、外键、部分唯一索引及状态约束 |
| `backend/src/schemas.py`、`workflow.py`、`main.py` | 校验、状态转换及 FastAPI 路由 |
| `backend/src/auth.py` | PBKDF2 密码、JWT 和角色依赖 |
| `backend/src/priority_model.py`、`worker.py` | 拟合、计算解释、持久化评分与心跳 |
| `frontend/src/{residents,observations,alerts,handovers}.js` | 四个业务模块 |
| `frontend/src/{app,store,shared}.js` | 路由、请求、会话、显示与表单工具 |

角色、等级、告警状态和班次分别在 Python `schemas.py` 的 `Role`、`Priority`、`AlertStatus`、`Shift`，SQL 迁移的约束，以及前端 `shared.js` 的 `ROLES`、`PRIORITIES`、`ALERTS`、`SHIFTS`。观察及交班的状态值贯穿迁移、`workflow.py` 与前端 `OBSERVATIONS`、`HANDOVERS`。观察信号在 Python `Signals`、SQL 表列、训练语料与前端 `FEATURES` 中对应。

代码以 [MIT 许可证](LICENSE) 提供。

## 告警处置与接续模块

| 模块 | 操作与业务规则 |
|---|---|
| 照护响应派单 | 值班长从已复核告警指定照护员。按派单时优先级生成 15／30／60 分钟的内部演示时限。指定照护员接单并回填处置记录，值班长可留原因撤销。在办任务会阻止交班，处置或撤销后恢复交班。 |
| 家属联络留痕 | 值班长从已复核的告警登记第一或备用联系人，照护员和值班长可记录电话或当面联系结果。未接通和约定回拨分别生成 30／60 分钟的后续时间，确认接通则结清。 |
| 交班后复查 | 接班员从已签收交班单安排复查，可确认接续正常或将异常转成新的待补观察。四项信号由照护员后续逐项确认，当前交班签收和原告警归档保留。 |

以上记录保存在 PostgreSQL。旧卷启动时自动执行 `backend/migrations/002_care_operations.sql`。枚举和表单参数见 `backend/src/operations_schemas.py`、`backend/src/operations.py`、迁移约束和 `frontend/src/careOperations.js`。联络记录供班组留痕，实际联络由值班人员执行。

## 值班覆盖与逐项核对

1. 值班长在「值班覆盖」为有在住住户的区域登记照护员、班次、覆盖时长和同时在办上限。首次登记后，该区启用按覆盖派单。照护员同一时间只能登记一个区域的生效班次。
2. 复核告警后打开「照护响应派单」。候选人员需覆盖完整的 15／30／60 分钟处置时限并保有容量。在办任务按照护员汇总，包括此前尚未完成的响应。结束覆盖前须完成或撤销本班关联的在办响应。覆盖到期后，已接单人员仍可登记结果。
3. 值班长打开响应的「处置核对清单」，填写本次涉及的巡房、呼叫、移位安排、任务回执或交班补记。接单照护员逐项登记凭据或阻碍。受阻项目由值班长填写复核安排，再由照护员核对。页面保留每次处理的人员、时间和说明。
4. 覆盖派单必须完成所有核对项目后才能提交处置结果。同一告警版本随后生成交班单时，会附上核对数量、处置回执和凭据链接，便于接班员签收前查看。

首次种子运行会为康复翼一层创建 115-A 沈慧芳的告警和唐宁的 8 小时覆盖。唐宁使用 `relief@zhaohui.local` 和 `zhaohui-demo` 登录。覆盖到期后，值班长可登记新班次。再次执行 seed 会保留既有班次和业务记录。未登记过覆盖的区域可继续使用原有派单流程，值班长可为任何在办响应添加核对清单。

新增模型位于 `backend/migrations/003_shift_coverage.sql` 和 `004_response_checks.sql`。`coverage*.py`、`checklist*.py` 负责规则、请求校验及 API。原生前端的值班覆盖、可用人员选择和核对工作台分别由 `shiftCoverage.js`、`coverageDispatch.js`、`responseChecks.js` 和 `checklistItems.js` 提供。
