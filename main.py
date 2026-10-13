"""
pywebview 后端入口 — 无边框窗口，线程安全。
"""
import os
import threading
import webview
from decimal import Decimal
from datetime import datetime, date
from db_manager import DatabaseManager

db = DatabaseManager()
_lock = threading.Lock()


def _serialize(obj):
    """递归转换 Decimal/datetime 等类型，确保返回值可被 JSON 序列化。"""
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return str(obj)
    return obj


class Api:
    """暴露给前端 JS 的接口集合。"""

    def __init__(self):
        self._window = None
        self._is_max = False

    # ==================== 窗口控制 ====================

    def minimize_window(self):
        if self._window:
            self._window.minimize()

    def maximize_window(self):
        if self._window:
            if self._is_max:
                self._window.restore()
            else:
                self._window.maximize()
            self._is_max = not self._is_max

    def close_window(self):
        if self._window:
            self._window.destroy()

    # ==================== 连接 ====================

    def authenticate(self, host, port, user, pwd):
        with _lock:
            try:
                # 先关闭旧连接（如有）
                if db.conn is not None:
                    try:
                        db.conn.close()
                    except Exception:
                        pass
                    db.conn = None
                db.authenticate(host, int(port), user, pwd)
                # 判断角色
                role = 'staff' if user.strip().lower() == 'staff' else 'manager'
                return {'success': True, 'error': None, 'role': role, 'user': user}
            except Exception as e:
                msg = str(e)
                if 'cryptography' in msg:
                    msg = 'MySQL 需要 cryptography 库，请运行 pip install cryptography'
                elif hasattr(e, 'args') and len(e.args) > 1:
                    msg = str(e.args[1])
                return {'success': False, 'error': msg}

    def logout(self):
        """断开数据库连接。"""
        with _lock:
            try:
                if db.conn is not None:
                    db.conn.close()
                    db.conn = None
                return {'success': True}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    # ==================== 看板 ====================

    def get_dashboard_stats(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_dashboard_stats())}
            except Exception as e:
                return {'success': False, 'data': None, 'error': str(e)}

    def get_latest_packages(self, limit=15, status=None):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_latest_packages(limit, status))}
            except Exception as e:
                return {'success': False, 'data': None, 'error': str(e)}

    def search_package(self, keyword):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.search_package(keyword))}
            except Exception as e:
                return {'success': False, 'data': None, 'error': str(e)}

    # ==================== 包裹管理 ====================

    def register_inbound(self, track_no, cust_name, cust_phone, weight, shelf):
        with _lock:
            try:
                db.register_inbound(track_no, cust_name, cust_phone, weight, shelf)
                return {'success': True}
            except Exception as e:
                msg = str(e.args[1]) if hasattr(e, 'args') and len(e.args) > 1 else str(e)
                return {'success': False, 'error': msg}

    def process_outbound(self, track_no):
        with _lock:
            try:
                if db.process_outbound(track_no) > 0:
                    return {'success': True}
                return {'success': False, 'error': '查无此单或状态不可出库'}
            except Exception as e:
                msg = str(e.args[1]) if hasattr(e, 'args') and len(e.args) > 1 else str(e)
                return {'success': False, 'error': msg}

    # ==================== 寄件服务 ====================

    def add_send_order(self, sender_name, sender_phone, dest_address, weight, is_remote=False):
        with _lock:
            try:
                res = db.add_send_order(sender_name, sender_phone, dest_address, weight, is_remote)
                return {'success': True, 'data': res}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    def get_send_orders(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_send_orders())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}

    # ==================== 配送调度 ====================

    def get_couriers(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_couriers())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}

    def dispatch_package(self, track_no, courier_id):
        with _lock:
            try:
                if db.dispatch_package(track_no, int(courier_id)) > 0:
                    return {'success': True}
                return {'success': False, 'error': '派单失败，请检查单号和包裹状态'}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    def get_pending_tasks(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_pending_tasks())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}

    def confirm_delivery(self, task_id):
        with _lock:
            try:
                if db.confirm_delivery(int(task_id)) > 0:
                    return {'success': True}
                return {'success': False, 'error': '签收失败，任务不存在或已签收'}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    # ==================== 客户服务 ====================

    def log_package_exception(self, track_no, issue_type, desc):
        with _lock:
            try:
                if db.log_package_exception(track_no, issue_type, desc) > 0:
                    return {'success': True}
                return {'success': False, 'error': '登记失败，请检查单号'}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    def get_exceptions(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_exceptions())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}

    def resolve_exception(self, log_id, target_status='已入库'):
        with _lock:
            try:
                if db.resolve_exception(int(log_id), target_status) > 0:
                    return {'success': True}
                return {'success': False, 'error': '操作失败'}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    def add_complaint(self, cust_name, cust_phone, track_no, content):
        with _lock:
            try:
                db.add_complaint(cust_name, cust_phone, track_no, content)
                return {'success': True}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    def get_complaints(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_complaints())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}

    def resolve_complaint(self, complaint_id):
        with _lock:
            try:
                if db.resolve_complaint(int(complaint_id)) > 0:
                    return {'success': True}
                return {'success': False, 'error': '操作失败'}
            except Exception as e:
                return {'success': False, 'error': str(e)}

    # ==================== 绩效统计 ====================

    def get_performance_report(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_performance_report())}
            except Exception as e:
                return {'success': False, 'data': None, 'error': str(e)}

    def get_daily_report(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_daily_report())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}

    def get_courier_workload(self):
        with _lock:
            try:
                return {'success': True, 'data': _serialize(db.get_courier_workload())}
            except Exception as e:
                return {'success': False, 'data': [], 'error': str(e)}


# ==================== 启动 ====================

if __name__ == '__main__':
    import ctypes
    # 让 Windows 把本窗口视为独立应用（而非 python.exe 子窗口）
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        'campus.express.station.v1'
    )

    api = Api()
    base = os.path.dirname(os.path.abspath(__file__))

    window = webview.create_window(
        '校园驿站管理系统',
        url=os.path.join(base, 'web', 'index.html'),
        js_api=api,
        width=1200, height=800,
        min_size=(900, 600),
        frameless=True,
        easy_drag=True
    )
    api._window = window

    def set_icon():
        """窗口显示后，用 Win32 API 设置任务栏图标。"""
        ico = os.path.join(base, 'web', 'icon.ico')
        if not os.path.exists(ico):
            return
        LR_LOADFROMFILE, IMAGE_ICON = 0x0010, 1
        WM_SETICON, ICON_BIG, ICON_SMALL = 0x0080, 1, 0
        hicon = ctypes.windll.user32.LoadImageW(
            0, ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
        )
        if not hicon:
            return
        # 按窗口标题查找句柄
        hwnd = ctypes.windll.user32.FindWindowW(None, '校园驿站管理系统')
        if hwnd:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)

    window.events.shown += set_icon
    webview.start()
