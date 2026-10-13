// ========== 主题切换 ==========
(function initTheme() {
    var saved = localStorage.getItem('theme');
    if (saved) {
        document.documentElement.setAttribute('data-theme', saved);
    } else {
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    }
})();

function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcons();
}

function updateThemeIcons() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    var icon = isDark ? 'light_mode' : 'dark_mode';
    document.querySelectorAll('.theme-toggle .material-icons-outlined').forEach(function(el) {
        el.textContent = icon;
    });
}

// ========== pywebview 就绪后再初始化 ==========
var api = null;

function waitForApi() {
    return new Promise(function(resolve) {
        if (window.pywebview && window.pywebview.api) {
            resolve(window.pywebview.api);
        } else {
            window.addEventListener('pywebviewready', function() {
                resolve(window.pywebview.api);
            });
        }
    });
}

// ========== DOM 缓存 ==========
const views = {
    login: document.getElementById('login-view'),
    dashboard: document.getElementById('dashboard-view')
};

const panels = {
    'panel-stats':    document.getElementById('panel-stats'),
    'panel-inbound':  document.getElementById('panel-inbound'),
    'panel-outbound': document.getElementById('panel-outbound'),
    'panel-send':     document.getElementById('panel-send'),
    'panel-dispatch': document.getElementById('panel-dispatch'),
    'panel-service':  document.getElementById('panel-service'),
    'panel-report':   document.getElementById('panel-report')
};

const STATUS_COLORS = {
    '已入库': '#0b57d0',
    '已签收': '#146c2e',
    '派送中': '#00639b',
    '异常件': '#b3261e',
    '待入库': '#5f6368'
};

let currentFilter = null;

// ========== Toast ==========
function showToast(msg, type) {
    type = type || 'error';
    var box = document.getElementById('toast-container');
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    var icon = type === 'success' ? 'check_circle' : 'error_outline';
    el.innerHTML = '<span class="material-icons-outlined">' + icon + '</span> ' + msg;
    box.appendChild(el);
    setTimeout(function() {
        el.style.animation = 'fadeOut .3s ease forwards';
        setTimeout(function() { el.remove(); }, 300);
    }, 3000);
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function() {
    updateThemeIcons();

    // 标题栏：窗口控制按钮
    document.getElementById('btn-minimize').addEventListener('click', function() {
        waitForApi().then(function(a) { a.minimize_window(); });
    });
    document.getElementById('btn-maximize').addEventListener('click', function() {
        var icon = document.querySelector('#btn-maximize .material-icons-outlined');
        waitForApi().then(function(a) {
            a.maximize_window();
            // 切换图标：最大化 ↔ 还原
            if (icon.textContent === 'crop_square') {
                icon.textContent = 'filter_none';
            } else {
                icon.textContent = 'crop_square';
            }
        });
    });
    document.getElementById('btn-close').addEventListener('click', function() {
        waitForApi().then(function(a) { a.close_window(); });
    });

    // 标题栏：主题切换
    document.getElementById('titlebar-theme-btn').addEventListener('click', toggleTheme);
});

// ========== 登录 ==========
document.getElementById('btn-login').addEventListener('click', async function() {
    var host = document.getElementById('login-host').value;
    var port = document.getElementById('login-port').value;
    var user = document.getElementById('login-user').value;
    var pwd  = document.getElementById('login-pwd').value;
    var btn  = document.getElementById('btn-login');
    btn.innerHTML = '<span class="material-icons-outlined">hourglass_empty</span> 连接中...';

    var a = await waitForApi();
    var res = await a.authenticate(host, port, user, pwd);
    if (res.success) {
        showToast('连接成功 — ' + (res.role === 'manager' ? '管理员' : '员工'), 'success');
        views.login.classList.remove('active-view');
        views.dashboard.classList.add('active-view');

        // 显示角色名称
        var roleName = res.role === 'manager' ? '管理员' : '员工';
        document.getElementById('sidebar-role-name').innerText = roleName;

        // 员工权限限制：隐藏绩效统计
        var reportNav = document.querySelector('[data-target="panel-report"]');
        if (res.role === 'staff') {
            reportNav.style.display = 'none';
        } else {
            reportNav.style.display = '';
        }

        loadDashboardData();
        loadCouriers();
    } else {
        showToast(res.error, 'error');
        btn.innerHTML = '<span class="material-icons-outlined">login</span> 连接并进入';
    }
});

// ========== 注销 ==========
document.getElementById('btn-logout').addEventListener('click', function() {
    views.dashboard.classList.remove('active-view');
    views.login.classList.add('active-view');
    document.getElementById('btn-login').innerHTML =
        '<span class="material-icons-outlined">login</span> 连接并进入';
    showToast('已注销', 'success');
});

// ========== 侧边栏切换 ==========
document.querySelectorAll('.nav-item').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
        document.querySelectorAll('.nav-item').forEach(function(b) {
            b.classList.remove('active');
        });
        var target = e.currentTarget;
        target.classList.add('active');
        var id = target.getAttribute('data-target');
        Object.values(panels).forEach(function(p) { p.classList.remove('active-panel'); });
        panels[id].classList.add('active-panel');

        if (id === 'panel-stats') loadDashboardData();
        if (id === 'panel-send') loadSendOrders();
        if (id === 'panel-dispatch') loadPendingTasks();
        if (id === 'panel-service') { loadExceptions(); loadComplaints(); }
        if (id === 'panel-report') loadReportData();
    });
});

// ========== 看板 ==========
async function loadDashboardData() {
    try {
        var a = await waitForApi();
        var res = await a.get_dashboard_stats();
        if (res && res.success) {
            renderStatsCards(res.data);
        } else if (res && res.error) {
            showToast('看板加载失败: ' + res.error);
        }
    } catch (err) {
        showToast('看板异常: ' + err.message);
    }
    loadTableData();
}

function renderStatsCards(list) {
    var grid = document.getElementById('stats-grid');
    grid.innerHTML = '';
    if (!list || list.length === 0) return;
    list.forEach(function(item) {
        var color = STATUS_COLORS[item.status] || '#5f6368';
        var card = document.createElement('div');
        card.className = 'stat-card';
        card.innerHTML =
            '<div class="stat-color-bar" style="background:' + color + '"></div>' +
            '<div class="stat-content">' +
            '<div class="stat-label">' + item.status + '</div>' +
            '<div class="stat-value" style="color:' + color + '">' + item.count + '</div></div>';
        card.addEventListener('click', function() {
            currentFilter = item.status;
            document.getElementById('table-title').innerText = '包裹明细 — ' + item.status;
            document.getElementById('btn-clear-filter').style.display = 'inline-flex';
            loadTableData();
        });
        grid.appendChild(card);
    });
}

async function loadTableData() {
    try {
        var a = await waitForApi();
        var res = await a.get_latest_packages(15, currentFilter);
        var tbody = document.getElementById('table-body');
        tbody.innerHTML = '';
        if (!res || !res.success || !res.data || res.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--md-on-surface-sub);">暂无数据</td></tr>';
            return;
        }
        res.data.forEach(function(p) {
            var color = STATUS_COLORS[p.status] || '#1f1f1f';
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td><strong>' + p.tracking_no + '</strong></td>' +
                '<td>' + (p.customer_name || '-') + '<br><span style="font-size:12px;color:var(--md-on-surface-sub)">' + (p.customer_phone || '') + '</span></td>' +
                '<td><span style="background:var(--md-surface-dim);padding:2px 8px;border-radius:4px;font-family:monospace;">' +
                    (p.pickup_code || '-') + '</span></td>' +
                '<td>' + (p.shelf_id || '-') + '</td>' +
                '<td>' + p.weight + ' kg</td>' +
                '<td style="color:var(--md-primary);font-weight:600;">¥' + (p.fee || 0).toFixed(2) + '</td>' +
                '<td>' + (p.inbound_time ? p.inbound_time.substring(0,16) : '-') + '</td>' +
                '<td style="color:' + color + ';font-weight:600;">' + p.status + '</td>';
            tbody.appendChild(tr);
        });
    } catch (err) {
        showToast('表格加载失败: ' + err.message);
    }
}

document.getElementById('btn-clear-filter').addEventListener('click', function() {
    currentFilter = null;
    document.getElementById('table-title').innerText = '包裹明细 — 全部';
    document.getElementById('btn-clear-filter').style.display = 'none';
    loadTableData();
});

// ========== 入库 ==========
document.getElementById('btn-inbound').addEventListener('click', async function() {
    var track  = document.getElementById('in-track').value.trim();
    var name   = document.getElementById('in-cust-name').value.trim();
    var phone  = document.getElementById('in-cust-phone').value.trim();
    var weight = document.getElementById('in-weight').value.trim();
    var shelf  = document.getElementById('in-shelf').value;
    if (!track || !name || !phone || !weight) return showToast('请填写完整信息');

    var a = await waitForApi();
    var res = await a.register_inbound(track, name, phone, weight, shelf);
    if (res.success) {
        showToast('入库成功，取件码已自动生成', 'success');
        document.getElementById('in-track').value = '';
        document.getElementById('in-cust-name').value = '';
        document.getElementById('in-cust-phone').value = '';
        document.getElementById('in-weight').value = '';
    } else {
        showToast('入库失败: ' + res.error);
    }
});

// ========== 出库 ==========
document.getElementById('btn-outbound').addEventListener('click', async function() {
    var track = document.getElementById('out-track').value.trim();
    if (!track) return;
    var a = await waitForApi();
    var res = await a.process_outbound(track);
    if (res.success) {
        showToast('出库成功', 'success');
        document.getElementById('out-track').value = '';
    } else {
        showToast('出库失败: ' + res.error);
    }
});

// ========== 寄件 ==========
document.getElementById('btn-calc-send').addEventListener('click', async function() {
    var name   = document.getElementById('send-name').value.trim();
    var phone  = document.getElementById('send-phone').value.trim();
    var dest   = document.getElementById('send-dest').value.trim();
    var weight = document.getElementById('send-weight').value.trim();
    var remote = document.getElementById('send-remote').checked;
    if (!name || !phone || !dest || !weight) return showToast('请填写完整寄件信息');

    var a = await waitForApi();
    var res = await a.add_send_order(name, phone, dest, weight, remote);
    if (res.success) {
        showToast('面单已生成', 'success');
        var box = document.getElementById('waybill-result');
        box.innerHTML =
            '<div class="waybill-box">' +
            '<div class="waybill-title">电子面单号</div>' +
            '<div class="waybill-code">' + res.data.waybill + '</div>' +
            '<div class="waybill-freight">运费: ¥ ' + res.data.freight.toFixed(2) + '</div>' +
            (remote ? '<div style="margin-top:8px;font-size:13px;color:var(--md-on-surface-sub);">含偏远地区附加费 20%</div>' : '') +
            '<div style="margin-top:16px;font-size:13px;color:var(--md-on-surface-sub);">' +
            '寄件人: ' + name + ' | ' + phone + '<br>目的地: ' + dest + ' | 重量: ' + weight + 'kg</div>' +
            '</div>';
        document.getElementById('send-name').value = '';
        document.getElementById('send-phone').value = '';
        document.getElementById('send-dest').value = '';
        document.getElementById('send-weight').value = '';
        document.getElementById('send-remote').checked = false;
        loadSendOrders();
    } else {
        showToast('生成失败: ' + res.error);
    }
});

async function loadSendOrders() {
    var a = await waitForApi();
    var res = await a.get_send_orders();
    var tbody = document.getElementById('send-list');
    tbody.innerHTML = '';
    if (!res.success || !res.data || res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--md-on-surface-sub);">暂无寄件记录</td></tr>';
        return;
    }
    res.data.forEach(function(s) {
        var tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + s.waybill_no + '</strong></td>' +
            '<td>' + s.sender_name + '</td>' +
            '<td>' + s.sender_phone + '</td>' +
            '<td>' + s.dest_address + '</td>' +
            '<td>' + s.weight + ' kg</td>' +
            '<td style="color:var(--md-tertiary);font-weight:600;">¥ ' + s.freight.toFixed(2) + '</td>' +
            '<td>' + (s.create_time ? s.create_time.substring(0,16) : '-') + '</td>';
        tbody.appendChild(tr);
    });
}

document.getElementById('btn-refresh-send').addEventListener('click', function() {
    loadSendOrders();
});

// ========== 配送调度 ==========
async function loadCouriers() {
    var a = await waitForApi();
    var res = await a.get_couriers();
    var sel = document.getElementById('disp-courier');
    sel.innerHTML = '';
    if (res.success) {
        res.data.forEach(function(c) {
            var opt = document.createElement('option');
            opt.value = c.courier_id;
            opt.textContent = c.name + ' (' + c.region + ')';
            sel.appendChild(opt);
        });
    }
}

document.getElementById('btn-dispatch').addEventListener('click', async function() {
    var track   = document.getElementById('disp-track').value.trim();
    var courier = document.getElementById('disp-courier').value;
    if (!track) return showToast('请输入单号');

    var a = await waitForApi();
    var res = await a.dispatch_package(track, courier);
    if (res.success) {
        showToast('任务已派发', 'success');
        document.getElementById('disp-track').value = '';
        loadPendingTasks();
    } else {
        showToast(res.error);
    }
});

async function loadPendingTasks() {
    var a = await waitForApi();
    var res = await a.get_pending_tasks();
    var tbody = document.getElementById('task-body');
    tbody.innerHTML = '';
    if (!res.success || res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--md-on-surface-sub);">暂无待签收任务</td></tr>';
        return;
    }
    res.data.forEach(function(t) {
        var tr = document.createElement('tr');
        tr.innerHTML =
            '<td>' + t.tracking_no + '</td>' +
            '<td>' + t.courier_name + '</td>' +
            '<td>' + (t.dispatch_time ? t.dispatch_time.substring(0,16) : '-') + '</td>' +
            '<td><button class="md3-btn-outline" onclick="doSign(' + t.task_id + ')">确认签收</button></td>';
        tbody.appendChild(tr);
    });
}

async function doSign(taskId) {
    var a = await waitForApi();
    var res = await a.confirm_delivery(taskId);
    if (res.success) {
        showToast('签收成功', 'success');
        loadPendingTasks();
    } else {
        showToast(res.error);
    }
}

// ========== 客户服务：包裹查询 ==========
document.getElementById('btn-search').addEventListener('click', async function() {
    var kw = document.getElementById('search-keyword').value.trim();
    if (!kw) return;
    var a = await waitForApi();
    var res = await a.search_package(kw);
    var box = document.getElementById('search-result');
    box.innerHTML = '';
    if (!res.success || res.data.length === 0) {
        box.innerHTML = '<p style="color:var(--md-on-surface-sub);padding:8px;">未找到匹配包裹</p>';
        return;
    }
    res.data.forEach(function(p) {
        var color = STATUS_COLORS[p.status] || '#1f1f1f';
        var div = document.createElement('div');
        div.className = 'search-card';
        div.innerHTML =
            '<strong>' + p.tracking_no + '</strong> — ' +
            '<span style="color:' + color + ';font-weight:600;">' + p.status + '</span>' +
            ' | 客户: ' + (p.customer_name || '未知') +
            ' | 取件码: ' + (p.pickup_code || '无') +
            ' | 货架: ' + (p.shelf_id || '无') +
            ' | 重量: ' + p.weight + 'kg' +
            ' | 代收费: ¥' + (p.fee || 0).toFixed(2);
        box.appendChild(div);
    });
});

// ========== 客户服务：异常登记 ==========
document.getElementById('btn-exception').addEventListener('click', async function() {
    var track = document.getElementById('exc-track').value.trim();
    var type  = document.getElementById('exc-type').value;
    var desc  = document.getElementById('exc-desc').value.trim();
    if (!track || !desc) return showToast('请填写单号和描述');

    var a = await waitForApi();
    var res = await a.log_package_exception(track, type, desc);
    if (res.success) {
        showToast('异常已登记', 'success');
        document.getElementById('exc-track').value = '';
        document.getElementById('exc-desc').value = '';
        loadExceptions();
    } else {
        showToast(res.error);
    }
});

async function loadExceptions() {
    var a = await waitForApi();
    var res = await a.get_exceptions();
    var tbody = document.getElementById('exc-list');
    tbody.innerHTML = '';
    if (!res.success || res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--md-on-surface-sub);text-align:center;">暂无记录</td></tr>';
        return;
    }
    res.data.forEach(function(e) {
        var tr = document.createElement('tr');
        var statusText = e.is_resolved ? '已解决' : '未处理';
        var statusColor = e.is_resolved ? 'var(--md-success)' : 'var(--md-error)';
        var btnHtml = e.is_resolved ? '-'
            : '<div style="display:flex;gap:6px;align-items:center;">' +
              '<select id="exc-target-' + e.log_id + '" style="padding:4px 8px;border-radius:6px;border:1px solid var(--md-outline);background:var(--md-input-bg);color:var(--md-on-surface);font-size:13px;">' +
              '<option value="已入库">恢复入库</option>' +
              '<option value="已签收">直接签收</option>' +
              '</select>' +
              '<button class="md3-btn-outline" onclick="doResolveExc(' + e.log_id + ')">处理</button>' +
              '</div>';
        tr.innerHTML =
            '<td>' + e.tracking_no + '</td>' +
            '<td>' + e.issue_type + '</td>' +
            '<td>' + (e.description || '') + '</td>' +
            '<td style="color:' + statusColor + ';font-weight:500;">' + statusText + '</td>' +
            '<td>' + btnHtml + '</td>';
        tbody.appendChild(tr);
    });
}

async function doResolveExc(logId) {
    var sel = document.getElementById('exc-target-' + logId);
    var targetStatus = sel ? sel.value : '已入库';
    var a = await waitForApi();
    var res = await a.resolve_exception(logId, targetStatus);
    if (res.success) { showToast('已处理，包裹状态变更为"' + targetStatus + '"', 'success'); loadExceptions(); }
    else showToast(res.error);
}

// ========== 客户服务：投诉 ==========
document.getElementById('btn-complaint').addEventListener('click', async function() {
    var name    = document.getElementById('comp-cust-name').value.trim();
    var phone   = document.getElementById('comp-cust-phone').value.trim();
    var track   = document.getElementById('comp-track').value.trim();
    var content = document.getElementById('comp-content').value.trim();
    if (!name || !phone || !content) return showToast('姓名、手机号和内容必填');

    var a = await waitForApi();
    var res = await a.add_complaint(name, phone, track, content);
    if (res.success) {
        showToast('投诉已登记', 'success');
        document.getElementById('comp-cust-name').value = '';
        document.getElementById('comp-cust-phone').value = '';
        document.getElementById('comp-track').value = '';
        document.getElementById('comp-content').value = '';
        loadComplaints();
    } else {
        showToast('登记失败: ' + res.error);
    }
});

async function loadComplaints() {
    var a = await waitForApi();
    var res = await a.get_complaints();
    var tbody = document.getElementById('comp-list');
    tbody.innerHTML = '';
    if (!res.success || res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--md-on-surface-sub);text-align:center;">暂无工单</td></tr>';
        return;
    }
    res.data.forEach(function(c) {
        var tr = document.createElement('tr');
        var statusColor = c.status === '已关闭' ? 'var(--md-success)' : 'var(--md-error)';
        var btnHtml = c.status === '已关闭' ? '-'
            : '<button class="md3-btn-outline" onclick="doResolveComp(' + c.complaint_id + ')">关闭</button>';
        tr.innerHTML =
            '<td>' + c.customer_name + '</td>' +
            '<td>' + (c.tracking_no || '-') + '</td>' +
            '<td>' + c.content + '</td>' +
            '<td style="color:' + statusColor + ';font-weight:500;">' + c.status + '</td>' +
            '<td>' + btnHtml + '</td>';
        tbody.appendChild(tr);
    });
}

async function doResolveComp(compId) {
    var a = await waitForApi();
    var res = await a.resolve_complaint(compId);
    if (res.success) { showToast('工单已关闭', 'success'); loadComplaints(); }
    else showToast(res.error);
}

// ========== 绩效统计 ==========
async function loadReportData() {
    var a = await waitForApi();

    var rpt = await a.get_performance_report();
    if (rpt.success) {
        document.getElementById('rep-pickup-revenue').innerText = '¥ ' + rpt.data.pickup_revenue.toFixed(2);
        document.getElementById('rep-send-revenue').innerText = '¥ ' + rpt.data.send_revenue.toFixed(2);
        document.getElementById('rep-total-revenue').innerText = '¥ ' + rpt.data.total_revenue.toFixed(2);
    }

    var daily = await a.get_daily_report();
    var dailyBody = document.getElementById('daily-body');
    dailyBody.innerHTML = '';
    if (daily.success && daily.data && daily.data.length > 0) {
        daily.data.forEach(function(r) {
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td>' + r.day + '</td>' +
                '<td>' + r.inbound_cnt + '</td>' +
                '<td>' + r.outbound_cnt + '</td>';
            dailyBody.appendChild(tr);
        });
    } else {
        dailyBody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--md-on-surface-sub);">暂无数据</td></tr>';
    }

    var wl = await a.get_courier_workload();
    var wlBody = document.getElementById('workload-body');
    wlBody.innerHTML = '';
    if (wl.success && wl.data.length > 0) {
        wl.data.forEach(function(c) {
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td>' + c.name + '</td>' +
                '<td>' + c.region + '</td>' +
                '<td>' + c.total + '</td>' +
                '<td>' + (c.signed || 0) + '</td>';
            wlBody.appendChild(tr);
        });
    } else {
        wlBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--md-on-surface-sub);">暂无数据</td></tr>';
    }
}

document.getElementById('btn-refresh-report').addEventListener('click', function() {
    showToast('正在刷新...', 'success');
    loadReportData();
});
