-- ============================================================
-- 物流快递驿站运营管理系统
-- ============================================================

CREATE DATABASE IF NOT EXISTS db_express_station_2026 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE db_express_station_2026;

-- ============================================================
-- 第一部分：建表与完整性约束
-- ============================================================

-- 客户信息表
CREATE TABLE IF NOT EXISTS customer (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(15) NOT NULL UNIQUE,
    address VARCHAR(255)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 配送员信息表
CREATE TABLE IF NOT EXISTS courier (
    courier_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(15) NOT NULL UNIQUE,
    region VARCHAR(50) NOT NULL COMMENT '负责区域',
    status VARCHAR(10) DEFAULT '在职',
    CONSTRAINT chk_courier_status CHECK (status IN ('在职', '休假', '离职'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 货架信息表
CREATE TABLE IF NOT EXISTS shelf (
    shelf_id VARCHAR(20) PRIMARY KEY COMMENT '货架编号',
    capacity INT NOT NULL DEFAULT 50,
    current_count INT NOT NULL DEFAULT 0,
    CONSTRAINT chk_shelf_count CHECK (current_count >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 包裹主表
CREATE TABLE IF NOT EXISTS package (
    tracking_no VARCHAR(50) PRIMARY KEY COMMENT '快递单号',
    customer_id INT NOT NULL,
    weight DECIMAL(5, 2) NOT NULL,
    shelf_id VARCHAR(20),
    pickup_code VARCHAR(10) UNIQUE COMMENT '六位取件码',
    status VARCHAR(10) NOT NULL DEFAULT '待入库',
    inbound_time DATETIME,
    outbound_time DATETIME,
    FOREIGN KEY (customer_id) REFERENCES customer (customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (shelf_id) REFERENCES shelf (shelf_id) ON DELETE SET NULL,
    CONSTRAINT chk_pkg_status CHECK (
        status IN (
            '待入库',
            '已入库',
            '派送中',
            '已签收',
            '异常件'
        )
    ),
    CONSTRAINT chk_pkg_weight CHECK (weight > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 寄件业务表
CREATE TABLE IF NOT EXISTS send_order (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_name VARCHAR(50) NOT NULL,
    sender_phone VARCHAR(15) NOT NULL,
    dest_address VARCHAR(255) NOT NULL,
    weight DECIMAL(5, 2) NOT NULL,
    freight DECIMAL(8, 2) NOT NULL COMMENT '运费',
    waybill_no VARCHAR(50) UNIQUE COMMENT '电子面单号',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_send_weight CHECK (weight > 0),
    CONSTRAINT chk_send_freight CHECK (freight > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 派送任务表
CREATE TABLE IF NOT EXISTS dispatch_task (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    tracking_no VARCHAR(50) NOT NULL,
    courier_id INT NOT NULL,
    status VARCHAR(10) DEFAULT '派送中',
    dispatch_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    sign_time DATETIME,
    FOREIGN KEY (tracking_no) REFERENCES package (tracking_no) ON DELETE CASCADE,
    FOREIGN KEY (courier_id) REFERENCES courier (courier_id) ON DELETE CASCADE,
    CONSTRAINT chk_task_status CHECK (
        status IN ('派送中', '已签收', '异常未达')
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 异常记录表
CREATE TABLE IF NOT EXISTS exception_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    tracking_no VARCHAR(50) NOT NULL,
    issue_type VARCHAR(10) NOT NULL,
    description TEXT,
    report_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_resolved BOOLEAN DEFAULT 0,
    FOREIGN KEY (tracking_no) REFERENCES package (tracking_no) ON DELETE CASCADE,
    CONSTRAINT chk_issue_type CHECK (
        issue_type IN ('破损', '滞留', '退件', '其他')
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- 客户投诉表
CREATE TABLE IF NOT EXISTS complaint (
    complaint_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    tracking_no VARCHAR(50),
    content TEXT NOT NULL,
    status VARCHAR(10) DEFAULT '待处理',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customer (customer_id) ON DELETE CASCADE,
    CONSTRAINT chk_complaint_status CHECK (
        status IN ('待处理', '处理中', '已关闭')
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============================================================
-- 第二部分：触发器
-- ============================================================
DROP TRIGGER IF EXISTS trg_pkg_before_insert;

DROP TRIGGER IF EXISTS trg_pkg_after_insert;

DROP TRIGGER IF EXISTS trg_pkg_before_update;

DROP TRIGGER IF EXISTS trg_pkg_before_delete;

DROP TRIGGER IF EXISTS trg_dispatch_before_update;

DROP TRIGGER IF EXISTS trg_exception_after_insert;

DROP TRIGGER IF EXISTS trg_send_before_insert;

DELIMITER /
/

-- 触发器 1/7：包裹插入前 — 自动填充取件码和入库时间
CREATE TRIGGER trg_pkg_before_insert
BEFORE INSERT ON package
FOR EACH ROW
BEGIN
    IF NEW.status = '已入库' THEN
        IF NEW.inbound_time IS NULL THEN
            SET NEW.inbound_time = CURRENT_TIMESTAMP;
        END IF;
        IF NEW.pickup_code IS NULL THEN
            SET NEW.pickup_code = LPAD(FLOOR(RAND() * 999999), 6, '0');
        END IF;
    END IF;
END
/
/

-- 触发器 2/7：包裹插入后 — 更新货架占用数（仅在行真正插入时执行）
CREATE TRIGGER trg_pkg_after_insert
AFTER INSERT ON package
FOR EACH ROW
BEGIN
    IF NEW.status = '已入库' AND NEW.shelf_id IS NOT NULL THEN
        UPDATE shelf SET current_count = current_count + 1
        WHERE shelf_id = NEW.shelf_id;
    END IF;
END
/
/

-- 触发器 3/7：包裹更新前 — 处理入库/离架/签收三种状态变更
CREATE TRIGGER trg_pkg_before_update
BEFORE UPDATE ON package
FOR EACH ROW
BEGIN
    -- 状态 → 已入库：记录入库时间、生成取件码、占用货架
    IF NEW.status = '已入库' AND OLD.status != '已入库' THEN
        SET NEW.inbound_time = CURRENT_TIMESTAMP;
        SET NEW.pickup_code  = LPAD(FLOOR(RAND() * 999999), 6, '0');
        IF NEW.shelf_id IS NOT NULL THEN
            UPDATE shelf SET current_count = current_count + 1
            WHERE shelf_id = NEW.shelf_id;
        END IF;
    END IF;

    -- 从"已入库"变为其他状态：释放货架
    IF OLD.status = '已入库' AND NEW.status != '已入库' THEN
        IF OLD.shelf_id IS NOT NULL THEN
            UPDATE shelf SET current_count = current_count - 1
            WHERE shelf_id = OLD.shelf_id;
        END IF;
        SET NEW.shelf_id = NULL;
    END IF;

    -- 状态 → 已签收：记录出库时间
    IF NEW.status = '已签收' AND OLD.status != '已签收' THEN
        SET NEW.outbound_time = CURRENT_TIMESTAMP;
    END IF;
END
/
/

-- 触发器 4/7：包裹删除前 — 释放货架空间
CREATE TRIGGER trg_pkg_before_delete
BEFORE DELETE ON package
FOR EACH ROW
BEGIN
    IF OLD.status = '已入库' AND OLD.shelf_id IS NOT NULL THEN
        UPDATE shelf SET current_count = current_count - 1
        WHERE shelf_id = OLD.shelf_id;
    END IF;
END
/
/

-- 触发器 5/7：派送任务更新前 — 签收时自动回写包裹状态
CREATE TRIGGER trg_dispatch_before_update
BEFORE UPDATE ON dispatch_task
FOR EACH ROW
BEGIN
    IF NEW.status = '已签收' AND OLD.status != '已签收' THEN
        SET NEW.sign_time = CURRENT_TIMESTAMP;
        UPDATE package SET status = '已签收'
        WHERE tracking_no = NEW.tracking_no;
    END IF;
END
/
/

-- 触发器 6/7：异常登记后 — 自动将包裹标记为异常件
CREATE TRIGGER trg_exception_after_insert
AFTER INSERT ON exception_log
FOR EACH ROW
BEGIN
    UPDATE package SET status = '异常件'
    WHERE tracking_no = NEW.tracking_no;
END
/
/

-- 触发器 7/7：寄件插入前 — 自动补全面单号
CREATE TRIGGER trg_send_before_insert
BEFORE INSERT ON send_order
FOR EACH ROW
BEGIN
    IF NEW.waybill_no IS NULL OR NEW.waybill_no = '' THEN
        SET NEW.waybill_no = CONCAT('WB', UPPER(LEFT(UUID(), 8)));
    END IF;
END
/
/

DELIMITER;

-- ============================================================
-- 第三部分：安全与权限控制
-- ============================================================

-- 创建角色
CREATE ROLE IF NOT EXISTS 'role_manager', 'role_staff';

-- 站长角色：全库权限
GRANT ALL PRIVILEGES ON db_express_station_2026.* TO 'role_manager';

-- 员工角色：按表授权（对象许可）
GRANT
SELECT,
INSERT
,
UPDATE ON db_express_station_2026.package TO 'role_staff';

GRANT
SELECT,
INSERT
    ON db_express_station_2026.customer TO 'role_staff';

GRANT
SELECT ON db_express_station_2026.shelf TO 'role_staff';

GRANT
SELECT,
INSERT
    ON db_express_station_2026.send_order TO 'role_staff';

GRANT
SELECT,
INSERT
,
UPDATE ON db_express_station_2026.dispatch_task TO 'role_staff';

GRANT
SELECT,
INSERT
,
UPDATE ON db_express_station_2026.exception_log TO 'role_staff';

GRANT
SELECT,
INSERT
,
UPDATE ON db_express_station_2026.complaint TO 'role_staff';

-- 命令许可撤销演示（REVOKE）
REVOKE DELETE ON db_express_station_2026.package
FROM 'role_staff';

-- 视图：列级别访问控制（员工只能看到脱敏后的包裹信息）
CREATE OR REPLACE VIEW v_package_brief AS
SELECT
    tracking_no,
    status,
    shelf_id,
    pickup_code,
    inbound_time
FROM package;

GRANT
SELECT ON db_express_station_2026.v_package_brief TO 'role_staff';

-- 创建实际用户并绑定角色
CREATE USER IF NOT EXISTS 'manager' @'%' IDENTIFIED BY 'manager123';

CREATE USER IF NOT EXISTS 'staff' @'%' IDENTIFIED BY 'staff123';

GRANT 'role_manager' TO 'manager' @'%';

GRANT 'role_staff' TO 'staff' @'%';

SET DEFAULT ROLE ALL TO 'manager' @'%';

SET DEFAULT ROLE ALL TO 'staff' @'%';

FLUSH PRIVILEGES;