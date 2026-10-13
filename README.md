# Campus Express Station Management System

<p align="right"><b>English</b> · <a href="#中文">中文</a></p>

A desktop operations system for a campus parcel station, built as a database course project. The window is a frameless Python app; business rules live in MySQL tables, checks, triggers, roles, and a column-level view.

<a id="english"></a>

## What it does

Staff connect to a local MySQL server from the login screen, then work through seven panels:

| Panel | What happens |
| --- | --- |
| Overview | Counts packages by status and lists recent parcels. Click a card to filter. |
| Inbound | Registers a parcel. A missing customer is created from name and phone. |
| Outbound | Marks an in-stock or exception parcel as signed for. |
| Send | Creates a waybill. Freight is ¥8 per kg (rounded up), plus 20% for remote areas. |
| Dispatch | Assigns an on-duty courier and confirms delivery. |
| Service | Searches a tracking number, logs damage / delay / return issues, and handles complaints. |
| Reports | Pickup fees, send revenue, a 7-day inbound/outbound report, and courier workload. Hidden for the staff account. |

Pickup fee is calculated from weight, not stored: ≤1 kg ¥1, ≤5 kg ¥2, ≤10 kg ¥3, otherwise ¥5.

## Stack

- Python desktop shell: [pywebview](https://pywebview.flowrl.com/) (`main.py`)
- UI: `web/index.html`, `web/style.css`, `web/app.js` (light / dark theme)
- Database access: PyMySQL (`db_manager.py`)
- Schema: `schema_logistics.sql` → database `db_express_station_2026`

## Layout

```
main.py                 window, JS API, login roles
db_manager.py           queries, schema loader, demo seed
schema_logistics.sql    tables, triggers, roles, users, view
web/                    frontend
```

## Run

MySQL 8 must already be running. Python packages:

```powershell
pip install pywebview pymysql cryptography
python main.py
```

On the login screen, use host `127.0.0.1`, port `3306`, and a MySQL account. The first connection should be `root` (or another account that can create databases and users).

| Account | Password | When it exists | UI |
| --- | --- | --- | --- |
| `root` | your MySQL root password | already on the server | treated as manager |
| `manager` | `manager123` | created by the schema script | manager, including reports |
| `staff` | `staff123` | created by the schema script | staff; reports are hidden |

The UI calls anyone whose username is not `staff` a manager. MySQL still enforces the real grants.

## When the SQL script runs

`schema_logistics.sql` is **not** a file you paste into MySQL by hand, and it does **not** run when the window merely opens.

It runs inside `DatabaseManager.authenticate()` after a successful login, and only if the username is `root` or `manager`:

1. The app reads `schema_logistics.sql` and executes it: create the database, tables, seven triggers, `role_manager` / `role_staff`, users `manager` and `staff`, the view `v_package_brief`, and the grants.
2. `_seed_demo_data()` then inserts sample shelves, customers, couriers, parcels, tasks, send orders, and one exception. `INSERT IGNORE` keeps that step safe to repeat.

A `staff` login only selects the existing database. It never runs the script, so the first login must be an account that can `CREATE DATABASE` and `CREATE USER` — normally `root`. `manager` does not exist until that first run.

Later logins as `root` or `manager` run the same file again. Statements use `IF NOT EXISTS` / `INSERT IGNORE`, and “already exists” errors are ignored, so the database is not dropped or rebuilt.

You can still execute the file yourself with the official `mysql` client if you want the database ready before opening the app. The file uses `DELIMITER //` for triggers; some GUI clients do not honor that command. The app’s own parser does.

## Schema (course points)

Eight tables: `customer`, `courier`, `shelf`, `package`, `send_order`, `dispatch_task`, `exception_log`, `complaint`.

Parcel status: `待入库` → `已入库` → `派送中` → `已签收`, plus `异常件`.

| Trigger | Effect |
| --- | --- |
| `trg_pkg_before_insert` | On inbound insert, fills inbound time and a 6-digit pickup code. |
| `trg_pkg_after_insert` | Increases the shelf count. |
| `trg_pkg_before_update` | Handles inbound, leaving a shelf, and sign-off time. |
| `trg_pkg_before_delete` | Frees the shelf. |
| `trg_dispatch_before_update` | Signing a task writes the parcel as signed for. |
| `trg_exception_after_insert` | Marks the parcel as an exception. |
| `trg_send_before_insert` | Fills a waybill number when one is missing. |

`role_manager` has full rights on the database. `role_staff` can read and write operational tables but cannot `DELETE` parcels. `v_package_brief` exposes only tracking number, status, shelf, pickup code, and inbound time.

Seeded shelves are `A-01`, `A-02`, `B-01`, and `C-01`. Sample tracking numbers include `SF10001` (in stock) and `ZT30001` (out for delivery).

---

<a id="中文"></a>

# 校园驿站管理系统

<p align="right"><a href="#english">English</a> · <b>中文</b></p>

这是一个数据库课程设计：校园快递驿站的桌面运营系统。窗口由 Python 无边框程序承载，业务规则放在 MySQL 的表、检查约束、触发器、角色和列级视图里。

## 做什么

员工在登录页连上本机 MySQL 后，使用七个功能页：

| 页面 | 作用 |
| --- | --- |
| 包裹总览 | 按状态统计包裹，列出近期明细。点击卡片可过滤。 |
| 包裹入库 | 登记入库。手机号找不到客户时，按姓名和电话自动建档。 |
| 扫码出库 | 把「已入库」或「异常件」改为「已签收」。 |
| 寄件服务 | 生成电子面单。运费每公斤 8 元，不足 1 公斤按 1 公斤计，偏远地区加价 20%。 |
| 配送调度 | 指派在职配送员，并确认签收。 |
| 客户服务 | 按单号查询，登记破损 / 滞留 / 退件 / 其他，处理投诉。 |
| 绩效统计 | 代收费、寄件营收、近 7 天入出库、配送员工作量。员工账号看不到这一页。 |

代收费按重量现算、不入库：≤1 kg 为 1 元，≤5 kg 为 2 元，≤10 kg 为 3 元，更重为 5 元。

## 技术

- 桌面壳：pywebview（`main.py`）
- 界面：`web/index.html`、`web/style.css`、`web/app.js`（可切换明暗主题）
- 数据访问：PyMySQL（`db_manager.py`）
- 脚本：`schema_logistics.sql`，库名 `db_express_station_2026`

## 目录

```
main.py                 窗口、给前端调用的接口、登录角色
db_manager.py           查询、加载 SQL、写入演示数据
schema_logistics.sql    建表、触发器、角色、用户、视图
web/                    前端页面
```

## 运行

本机需要已经启动的 MySQL 8。安装依赖后启动：

```powershell
pip install pywebview pymysql cryptography
python main.py
```

登录页填写主机 `127.0.0.1`、端口 `3306` 和 MySQL 账号。第一次请用 `root`（或其它能建库、建用户的账号）。

| 账号 | 密码 | 何时可用 | 界面 |
| --- | --- | --- | --- |
| `root` | 你自己的 root 密码 | 服务器上本来就有 | 按站长处理 |
| `manager` | `manager123` | 脚本创建 | 站长，含绩效统计 |
| `staff` | `staff123` | 脚本创建 | 员工，隐藏绩效统计 |

界面只根据用户名是不是 `staff` 区分员工和站长。真正能不能改表，仍由 MySQL 权限决定。

## 数据库脚本什么时候执行

`schema_logistics.sql` **不用**手动粘进 MySQL，也 **不是** 窗口一打开就执行。

它在登录成功之后，由 `DatabaseManager.authenticate()` 调用，并且只有用户名是 `root` 或 `manager` 才会跑：

1. 程序读取 `schema_logistics.sql` 并执行：建库、建表、7 个触发器、角色 `role_manager` / `role_staff`、用户 `manager` 和 `staff`、视图 `v_package_brief`，以及授权。
2. 接着 `_seed_demo_data()` 写入示例货架、客户、配送员、包裹、派送任务、寄件和一条异常记录。`INSERT IGNORE` 保证重复执行不会插出第二份。

用 `staff` 登录只会选中已有的库，不会执行脚本。所以第一次必须用能 `CREATE DATABASE`、`CREATE USER` 的账号，一般是 `root`。`manager` 要等这次执行之后才存在。

之后再用 `root` 或 `manager` 登录，还会再执行同一份文件。语句带 `IF NOT EXISTS` / `INSERT IGNORE`，已存在类错误会被忽略，不会删库重建。

如果想在打开程序之前就把库建好，可以用官方 `mysql` 客户端自行执行该文件。文件里的触发器用了 `DELIMITER //`，部分图形客户端不认这条命令；程序自己的解析器可以处理。

## 库表（课程设计要点）

八张表：`customer`、`courier`、`shelf`、`package`、`send_order`、`dispatch_task`、`exception_log`、`complaint`。

包裹状态：`待入库` → `已入库` → `派送中` → `已签收`，另有 `异常件`。

| 触发器 | 作用 |
| --- | --- |
| `trg_pkg_before_insert` | 入库插入时补入库时间和 6 位取件码。 |
| `trg_pkg_after_insert` | 货架占用数 +1。 |
| `trg_pkg_before_update` | 处理入库、离架、签收时间。 |
| `trg_pkg_before_delete` | 释放货架。 |
| `trg_dispatch_before_update` | 任务签收时把包裹写成已签收。 |
| `trg_exception_after_insert` | 把包裹标成异常件。 |
| `trg_send_before_insert` | 面单号为空时自动补上。 |

`role_manager` 拥有该库全部权限。`role_staff` 可以读写业务表，但不能 `DELETE` 包裹。视图 `v_package_brief` 只露出单号、状态、货架、取件码和入库时间。

演示货架是 `A-01`、`A-02`、`B-01`、`C-01`。示例单号里，`SF10001` 是已入库，`ZT30001` 是派送中。
