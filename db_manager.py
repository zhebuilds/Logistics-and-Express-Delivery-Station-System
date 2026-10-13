"""
数据库操作封装模块
"""

import os
import math
import uuid
import pymysql


class DatabaseManager:
    """封装了驿站系统所有的数据库读写操作。"""

    def __init__(self):
        self.conn = None

    # ==================== 连接与初始化 ====================

    def authenticate(self, host, port, user, password):
        """连接数据库，管理员首次连接时自动建表，员工直接连。"""
        self.conn = pymysql.connect(
            host=host, port=int(port), user=user,
            password=password, charset='utf8mb4',
            init_command="SET time_zone='+08:00'"
        )
        if user.strip().lower() in ('root', 'manager'):
            self._init_schema()
        self.conn.select_db('db_express_station_2026')

    def _init_schema(self):
        """读取 schema_logistics.sql 并执行建表、建触发器。"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sql_file = os.path.join(base_dir, 'schema_logistics.sql')
        if not os.path.exists(sql_file):
            return

        with open(sql_file, 'r', encoding='utf-8') as f:
            raw_lines = f.readlines()

        # 按 DELIMITER 分段解析 SQL 语句
        stmts = []
        buf = []
        in_trigger = False

        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
                continue
            if stripped.startswith('DELIMITER //'):
                in_trigger = True
                continue
            if stripped.startswith('DELIMITER ;'):
                in_trigger = False
                continue

            buf.append(line)

            if not in_trigger and stripped.endswith(';'):
                stmts.append(''.join(buf))
                buf = []
            elif in_trigger and stripped.endswith('END //'):
                stmts.append(''.join(buf).replace('END //', 'END;'))
                buf = []

        with self.conn.cursor() as cur:
            for sql in stmts:
                sql = sql.strip()
                if not sql:
                    continue
                try:
                    cur.execute(sql)
                except pymysql.Error as e:
                    # 静默忽略"已存在"类错误，其他的打印一下方便排查
                    if e.args[0] not in (1050, 1359, 1396, 1142, 3162):
                        print(f'[DB] {e}')
        self.conn.commit()
        self._seed_demo_data()

    def _seed_demo_data(self):
        """插入演示数据（INSERT IGNORE 保证幂等）。"""
        with self.conn.cursor() as cur:
            cur.execute('USE db_express_station_2026;')

            # 货架
            cur.execute("""INSERT IGNORE INTO shelf VALUES
                ('A-01',50,0),('A-02',50,0),('B-01',50,0),('C-01',50,0)""")

            # 客户
            cur.execute("""INSERT IGNORE INTO customer (customer_id,name,phone,address) VALUES
                (1,'李明辉','13912345001','软件园 A 栋 302'),
                (2,'王思雨','13912345002','理工楼 3 号 105'),
                (3,'赵子涵','13912345003','学生公寓 12 栋 608'),
                (4,'陈嘉伟','13912345004','信息楼 5 层 512'),
                (5,'周雨萱','13912345005','创业园 B 栋 201'),
                (6,'吴浩然','13912345006','学生公寓 8 栋 403'),
                (7,'郑晓婷','13912345007','图书馆南门取件点'),
                (8,'孙志强','13912345008','行政楼 2 层 218')""")

            # 配送员
            cur.execute("""INSERT IGNORE INTO courier (courier_id,name,phone,region) VALUES
                (1,'张师傅','13800000001','南区'),
                (2,'刘师傅','13800000002','北区')""")

            # 包裹（各种状态，带历史时间方便日报展示）
            cur.execute("""INSERT IGNORE INTO package
                (tracking_no,customer_id,weight,shelf_id,pickup_code,status,inbound_time,outbound_time) VALUES
                ('SF10001',1,1.2,'A-01','386521','已入库', DATE_SUB(NOW(),INTERVAL 2 DAY), NULL),
                ('SF10002',1,3.5,'A-01','751903','已入库', DATE_SUB(NOW(),INTERVAL 1 DAY), NULL),
                ('JD20001',2,0.8,'B-01','420867','已入库', NOW(), NULL),
                ('ZT30001',1,2.1, NULL, '193548','派送中', DATE_SUB(NOW(),INTERVAL 3 DAY), NULL),
                ('ZT30002',2,5.5, NULL, '647029','派送中', DATE_SUB(NOW(),INTERVAL 1 DAY), NULL),
                ('YD40001',1,1.0, NULL, '825173','已签收', DATE_SUB(NOW(),INTERVAL 5 DAY), DATE_SUB(NOW(),INTERVAL 4 DAY)),
                ('YD40002',2,1.5, NULL, '539284','已签收', DATE_SUB(NOW(),INTERVAL 3 DAY), DATE_SUB(NOW(),INTERVAL 2 DAY)),
                ('YD40003',3,0.5, NULL, '961437','已签收', DATE_SUB(NOW(),INTERVAL 1 DAY), DATE_SUB(NOW(),INTERVAL 1 DAY)),
                ('EMS5001',2,8.0, NULL, '704615','异常件', DATE_SUB(NOW(),INTERVAL 4 DAY), NULL)""")

            # 派送任务
            cur.execute("""INSERT IGNORE INTO dispatch_task
                (task_id,tracking_no,courier_id,status,dispatch_time) VALUES
                (1,'ZT30001',1,'派送中', DATE_SUB(NOW(),INTERVAL 3 DAY)),
                (2,'ZT30002',2,'派送中', DATE_SUB(NOW(),INTERVAL 1 DAY)),
                (3,'YD40001',1,'已签收', DATE_SUB(NOW(),INTERVAL 4 DAY)),
                (4,'YD40002',1,'已签收', DATE_SUB(NOW(),INTERVAL 2 DAY))""")

            # 寄件
            cur.execute("""INSERT IGNORE INTO send_order
                (order_id,sender_name,sender_phone,dest_address,weight,freight,waybill_no) VALUES
                (1,'张三','13700000001','北京市海淀区',2.5,22.00,'WB8A3C4D2E'),
                (2,'李明','13700000002','本市高新区',1.0,6.00,'WBF5E1B7A9')""")

            # 异常记录
            cur.execute("""INSERT IGNORE INTO exception_log
                (log_id,tracking_no,issue_type,description) VALUES
                (1,'EMS5001','破损','外包装严重变形，内件疑似损坏')""")

            # 修复旧数据：补全缺失的取件码和入库时间（兼容之前版本遗留的数据）
            cur.execute("""UPDATE package
                SET pickup_code = LPAD(FLOOR(RAND() * 999999), 6, '0')
                WHERE pickup_code IS NULL AND status IN ('已入库','派送中','已签收','异常件')""")
            cur.execute("""UPDATE package
                SET inbound_time = CURRENT_TIMESTAMP
                WHERE inbound_time IS NULL AND status IN ('已入库','派送中','已签收','异常件')""")
        self.conn.commit()

    # ==================== 看板与查询 ====================

    def get_dashboard_stats(self):
        """按状态统计包裹数量。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute('SELECT status, COUNT(*) as count FROM package GROUP BY status')
            return cur.fetchall()

    def get_latest_packages(self, limit=20, status=None):
        """获取包裹明细，可按状态过滤。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            base = ('SELECT p.tracking_no, c.name AS customer_name, c.phone AS customer_phone, '
                    'p.weight, p.shelf_id, p.status, p.pickup_code, p.inbound_time, '
                    'CASE WHEN p.weight<=1 THEN 1.00 WHEN p.weight<=5 THEN 2.00 '
                    'WHEN p.weight<=10 THEN 3.00 ELSE 5.00 END AS fee '
                    'FROM package p LEFT JOIN customer c ON p.customer_id=c.customer_id')
            if status:
                cur.execute(base + ' WHERE p.status=%s ORDER BY p.tracking_no DESC LIMIT %s',
                            (status, limit))
            else:
                cur.execute(base + ' ORDER BY p.tracking_no DESC LIMIT %s', (limit,))
            return cur.fetchall()

    def search_package(self, keyword):
        """按单号模糊搜索。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                'SELECT p.tracking_no, c.name AS customer_name, c.phone AS customer_phone, '
                'p.weight, p.shelf_id, p.status, p.pickup_code, p.inbound_time, p.outbound_time, '
                'CASE WHEN p.weight<=1 THEN 1.00 WHEN p.weight<=5 THEN 2.00 '
                'WHEN p.weight<=10 THEN 3.00 ELSE 5.00 END AS fee '
                'FROM package p LEFT JOIN customer c ON p.customer_id=c.customer_id '
                'WHERE p.tracking_no LIKE %s LIMIT 10',
                (f'%{keyword}%',)
            )
            return cur.fetchall()

    # ==================== 包裹管理 ====================

    def register_inbound(self, track_no, cust_name, cust_phone, weight, shelf):
        """入库登记：按手机号查找客户，不存在则自动创建。"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT customer_id FROM customer WHERE phone=%s", (cust_phone,))
            row = cur.fetchone()
            if row:
                cust_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO customer (name,phone) VALUES (%s,%s)",
                    (cust_name, cust_phone)
                )
                cust_id = cur.lastrowid
            cur.execute(
                "INSERT INTO package (tracking_no,customer_id,weight,shelf_id,status) "
                "VALUES (%s,%s,%s,%s,'已入库')",
                (track_no, cust_id, weight, shelf)
            )
        self.conn.commit()

    def process_outbound(self, track_no):
        """扫码出库，触发器自动记录出库时间和释放货架。"""
        with self.conn.cursor() as cur:
            affected = cur.execute(
                "UPDATE package SET status='已签收' "
                "WHERE tracking_no=%s AND status IN ('已入库','异常件')",
                (track_no,)
            )
        self.conn.commit()
        return affected

    # ==================== 寄件服务 ====================

    @staticmethod
    def _calc_freight(weight, is_remote=False):
        """按重量计费：每公斤 8 元，不足 1kg 按 1kg 计。偏远地区加价 20%。"""
        w = float(weight)
        base = max(1, math.ceil(w)) * 8.0
        if is_remote:
            base *= 1.2
        return round(base, 2)

    def add_send_order(self, sender_name, sender_phone, dest_address, weight, is_remote=False):
        """创建寄件订单，返回面单号和运费。"""
        freight = self._calc_freight(weight, is_remote)
        waybill = 'WB' + uuid.uuid4().hex[:8].upper()
        with self.conn.cursor() as cur:
            cur.execute(
                'INSERT INTO send_order '
                '(sender_name,sender_phone,dest_address,weight,freight,waybill_no) '
                'VALUES (%s,%s,%s,%s,%s,%s)',
                (sender_name, sender_phone, dest_address, float(weight), freight, waybill)
            )
        self.conn.commit()
        return {'waybill': waybill, 'freight': freight}

    def get_send_orders(self, limit=20):
        """获取寄件历史记录。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                'SELECT waybill_no, sender_name, sender_phone, dest_address, '
                'weight, freight, create_time FROM send_order '
                'ORDER BY create_time DESC LIMIT %s', (limit,)
            )
            return cur.fetchall()

    # ==================== 配送调度 ====================

    def get_couriers(self):
        """获取在职配送员列表。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT courier_id,name,region FROM courier WHERE status='在职'")
            return cur.fetchall()

    def dispatch_package(self, track_no, courier_id):
        """派发任务，同时更新包裹状态。"""
        with self.conn.cursor() as cur:
            affected = cur.execute(
                "UPDATE package SET status='派送中' "
                "WHERE tracking_no=%s AND status IN ('已入库','待入库','异常件')",
                (track_no,)
            )
            if affected > 0:
                cur.execute(
                    'INSERT INTO dispatch_task (tracking_no,courier_id) VALUES (%s,%s)',
                    (track_no, int(courier_id))
                )
        self.conn.commit()
        return affected

    def get_pending_tasks(self):
        """获取待签收的派送任务。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                'SELECT d.task_id, d.tracking_no, c.name AS courier_name, '
                'd.status, d.dispatch_time '
                'FROM dispatch_task d JOIN courier c ON d.courier_id=c.courier_id '
                "WHERE d.status='派送中' ORDER BY d.dispatch_time DESC"
            )
            return cur.fetchall()

    def confirm_delivery(self, task_id):
        """签收确认（触发器自动回写包裹状态和出库时间）。"""
        with self.conn.cursor() as cur:
            affected = cur.execute(
                "UPDATE dispatch_task SET status='已签收' "
                "WHERE task_id=%s AND status='派送中'",
                (task_id,)
            )
        self.conn.commit()
        return affected

    # ==================== 客户服务 ====================

    def log_package_exception(self, track_no, issue_type, desc):
        """登记异常件（触发器自动更新包裹状态）。"""
        with self.conn.cursor() as cur:
            affected = cur.execute(
                'INSERT INTO exception_log (tracking_no,issue_type,description) '
                'VALUES (%s,%s,%s)',
                (track_no, issue_type, desc)
            )
        self.conn.commit()
        return affected

    def get_exceptions(self):
        """获取近期异常记录。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                'SELECT log_id, tracking_no, issue_type, description, '
                'report_time, is_resolved FROM exception_log '
                'ORDER BY report_time DESC LIMIT 20'
            )
            return cur.fetchall()

    def resolve_exception(self, log_id, target_status='已入库'):
        """标记异常已处理，并将包裹恢复为指定状态。"""
        with self.conn.cursor() as cur:
            cur.execute('SELECT tracking_no FROM exception_log WHERE log_id=%s', (log_id,))
            row = cur.fetchone()
            affected = cur.execute(
                'UPDATE exception_log SET is_resolved=1 WHERE log_id=%s',
                (log_id,)
            )
            if row:
                track_no = row[0]
                cur.execute(
                    'SELECT COUNT(*) FROM exception_log '
                    'WHERE tracking_no=%s AND is_resolved=0',
                    (track_no,)
                )
                unresolved = cur.fetchone()[0]
                if unresolved == 0:
                    cur.execute(
                        "UPDATE package SET status=%s "
                        "WHERE tracking_no=%s AND status='异常件'",
                        (target_status, track_no)
                    )
                    # 如果直接签收，同步关闭对应的派送任务
                    if target_status == '已签收':
                        cur.execute(
                            "UPDATE dispatch_task SET status='已签收', sign_time=NOW() "
                            "WHERE tracking_no=%s AND status='派送中'",
                            (track_no,)
                        )
        self.conn.commit()
        return affected

    def add_complaint(self, cust_name, cust_phone, track_no, content):
        """登记客户投诉：按手机号查找客户，不存在则新建。"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT customer_id FROM customer WHERE phone=%s", (cust_phone,))
            row = cur.fetchone()
            if row:
                cust_id = row[0]
            else:
                cur.execute("INSERT INTO customer (name,phone) VALUES (%s,%s)",
                            (cust_name, cust_phone))
                cust_id = cur.lastrowid
            cur.execute(
                'INSERT INTO complaint (customer_id,tracking_no,content) '
                'VALUES (%s,%s,%s)',
                (cust_id, track_no or None, content)
            )
        self.conn.commit()

    def get_complaints(self):
        """获取近期投诉工单。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                'SELECT co.complaint_id, cu.name AS customer_name, '
                'co.tracking_no, co.content, co.status, co.create_time '
                'FROM complaint co JOIN customer cu ON co.customer_id=cu.customer_id '
                'ORDER BY co.create_time DESC LIMIT 20'
            )
            return cur.fetchall()

    def resolve_complaint(self, complaint_id):
        """关闭投诉工单。"""
        with self.conn.cursor() as cur:
            affected = cur.execute(
                "UPDATE complaint SET status='已关闭' WHERE complaint_id=%s",
                (complaint_id,)
            )
        self.conn.commit()
        return affected

    # ==================== 绩效统计 ====================

    def get_performance_report(self):
        """获取宏观运营数据。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT COUNT(*) as c FROM package WHERE status='派送中'")
            delivering = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM package WHERE status='已签收'")
            signed = cur.fetchone()['c']
            cur.execute('SELECT COALESCE(SUM(freight),0) as r FROM send_order')
            send_revenue = float(cur.fetchone()['r'])
            cur.execute(
                'SELECT COALESCE(SUM(CASE WHEN weight<=1 THEN 1.00 '
                'WHEN weight<=5 THEN 2.00 WHEN weight<=10 THEN 3.00 '
                'ELSE 5.00 END),0) as r FROM package'
            )
            pickup_revenue = float(cur.fetchone()['r'])
            return {
                'delivering': delivering,
                'signed': signed,
                'send_revenue': send_revenue,
                'pickup_revenue': pickup_revenue,
                'total_revenue': send_revenue + pickup_revenue,
            }

    def get_daily_report(self):
        """最近 7 天入库/出库量统计。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT d.day,
                       COALESCE(i.cnt, 0) AS inbound_cnt,
                       COALESCE(o.cnt, 0) AS outbound_cnt
                FROM (
                    SELECT DATE_SUB(CURDATE(), INTERVAL n DAY) AS day
                    FROM (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3
                          UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) nums
                ) d
                LEFT JOIN (
                    SELECT DATE(inbound_time) AS day, COUNT(*) AS cnt
                    FROM package WHERE inbound_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                    GROUP BY DATE(inbound_time)
                ) i ON d.day = i.day
                LEFT JOIN (
                    SELECT DATE(outbound_time) AS day, COUNT(*) AS cnt
                    FROM package WHERE outbound_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                    GROUP BY DATE(outbound_time)
                ) o ON d.day = o.day
                ORDER BY d.day DESC
            """)
            return cur.fetchall()

    def get_courier_workload(self):
        """各配送员工作量统计。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                'SELECT c.name, c.region, '
                'COUNT(d.task_id) AS total, '
                "SUM(CASE WHEN d.status='已签收' THEN 1 ELSE 0 END) AS signed "
                'FROM courier c LEFT JOIN dispatch_task d ON c.courier_id=d.courier_id '
                'GROUP BY c.courier_id, c.name, c.region'
            )
            return cur.fetchall()
