/**
 * Work Tracking System - Main Application
 */

const App = {
    currentPage: 'dashboard',
    user: null,
    platforms: [],
    technicians: [],

    // Initialize the app
    async init() {
        // Check authentication
        if (!API.isLoggedIn()) {
            window.location.href = '/login';
            return;
        }

        this.user = API.getUser();

        // Load platforms and technicians for forms
        try {
            const data = await API.jobs.getPlatforms();
            this.platforms = data.platforms;
        } catch (e) {
            console.error('Failed to load platforms:', e);
        }

        try {
            const data = await API.jobs.getTechnicians();
            this.technicians = data.technicians;
        } catch (e) {
            console.error('Failed to load technicians:', e);
        }

        // Setup UI
        this.setupSidebar();
        this.setupUserInfo();

        // Navigate to initial page
        const hash = window.location.hash.slice(1) || 'dashboard';
        this.navigate(hash);

        // Handle hash changes
        window.addEventListener('hashchange', () => {
            const page = window.location.hash.slice(1) || 'dashboard';
            this.navigate(page);
        });
    },

    // Setup sidebar navigation
    setupSidebar() {
        const nav = document.getElementById('sidebar-nav');
        const menuItems = [
            { id: 'dashboard', icon: 'fas fa-tachometer-alt', label: 'Dashboard' },
            { id: 'jobs', icon: 'fas fa-briefcase', label: 'Jobs' },
            { id: 'calendar', icon: 'fas fa-calendar-alt', label: 'Calendar' },
            { id: 'time-entries', icon: 'fas fa-clock', label: 'Time Entries' },
            { id: 'payout', icon: 'fas fa-money-bill-wave', label: 'Payout', roles: ['admin', 'manager'] },
            { id: 'reports', icon: 'fas fa-chart-bar', label: 'Reports', roles: ['admin', 'manager'] },
            { id: 'sms-log', icon: 'fas fa-sms', label: 'SMS Log', roles: ['admin', 'manager'] },
            { id: 'my-payouts', icon: 'fas fa-file-invoice-dollar', label: 'My Payouts', roles: ['technician'] },
            { id: 'technicians', icon: 'fas fa-hard-hat', label: 'Technicians', roles: ['admin'] },
            { id: 'users', icon: 'fas fa-users', label: 'Users', roles: ['admin'] },
            { id: 'settings', icon: 'fas fa-cog', label: 'Settings', roles: ['admin'] },
            { id: 'backups', icon: 'fas fa-database', label: 'Backups', roles: ['admin'] }
        ];

        nav.innerHTML = menuItems
            .filter(item => !item.roles || item.roles.includes(this.user.role))
            .map(item => `
                <a class="nav-item" data-page="${item.id}">
                    <i class="${item.icon}"></i>
                    ${item.label}
                </a>
            `).join('');

        // Click handlers
        nav.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                window.location.hash = item.dataset.page;
            });
        });
    },

    // Setup user info in sidebar
    setupUserInfo() {
        document.getElementById('user-name').textContent = this.user.full_name || this.user.email;
        document.getElementById('user-role').textContent = this.user.role;

        document.getElementById('logout-btn').addEventListener('click', () => {
            API.auth.logout();
        });
    },

    // Navigate to a page
    async navigate(page) {
        this.currentPage = page;

        // Update active nav item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        // Update header
        const titles = {
            'dashboard': 'Dashboard',
            'jobs': 'Jobs',
            'calendar': 'Calendar',
            'time-entries': 'Time Entries',
            'reports': 'Reports',
            'sms-log': 'SMS Log',
            'technicians': 'Technician Management',
            'users': 'User Management',
            'pay-periods': 'Pay Periods',
            'payout': 'Payout',
            'my-payouts': 'My Payouts',
            'settings': 'System Settings',
            'backups': 'Backup & Recovery'
        };
        document.getElementById('page-title').textContent = titles[page] || 'Dashboard';

        // Load page content
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';

        try {
            switch (page) {
                case 'dashboard':
                    await Pages.dashboard(content);
                    break;
                case 'jobs':
                    await Pages.jobs(content);
                    break;
                case 'calendar':
                    await Pages.calendar(content);
                    break;
                case 'time-entries':
                    await Pages.timeEntries(content);
                    break;
                case 'reports':
                    await Pages.reports(content);
                    break;
                case 'sms-log':
                    await Pages.smsLog(content);
                    break;
                case 'technicians':
                    await Pages.technicians(content);
                    break;
                case 'users':
                    await Pages.users(content);
                    break;
                case 'pay-periods':
                    await Pages.payPeriods(content);
                    break;
                case 'settings':
                    await Pages.settings(content);
                    break;
                case 'payout':
                    await Pages.payout(content);
                    break;
                case 'my-payouts':
                    await Pages.myPayouts(content);
                    break;
                case 'backups':
                    await Pages.backups(content);
                    break;
                default:
                    await Pages.dashboard(content);
            }
        } catch (error) {
            content.innerHTML = `
                <div class="alert alert-error">
                    Error loading page: ${error.message}
                </div>
            `;
        }
    },

    // Show modal
    showModal(title, body, footer = '', options = {}) {
        const modalOverlay = document.getElementById('modal-overlay');
        const modal = modalOverlay.querySelector('.modal');
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-body').innerHTML = body;
        document.getElementById('modal-footer').innerHTML = footer;

        // Handle actions bar
        const actionsEl = document.getElementById('modal-actions');
        if (options.actions) {
            actionsEl.innerHTML = options.actions;
            actionsEl.style.display = '';
        } else {
            actionsEl.innerHTML = '';
            actionsEl.style.display = 'none';
        }

        // Handle wide modal option
        if (options.wide) {
            modal.classList.add('modal-wide');
        } else {
            modal.classList.remove('modal-wide');
        }

        modalOverlay.classList.add('active');
    },

    // Hide modal
    hideModal() {
        const modalOverlay = document.getElementById('modal-overlay');
        const modal = modalOverlay.querySelector('.modal');
        modalOverlay.classList.remove('active');
        modal.classList.remove('modal-wide');
        document.getElementById('modal-actions').style.display = 'none';
    },

    // Show alert
    showAlert(message, type = 'error') {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        alert.style.position = 'fixed';
        alert.style.top = '1rem';
        alert.style.right = '1rem';
        alert.style.zIndex = '9999';
        alert.style.maxWidth = '400px';
        document.body.appendChild(alert);

        setTimeout(() => alert.remove(), 5000);
    },

    // Show error in modal form (doesn't close modal)
    showFormError(message) {
        // Remove any existing form error
        const existing = document.getElementById('form-error-alert');
        if (existing) existing.remove();

        // Create error alert at top of modal body
        const modalBody = document.querySelector('.modal-body');
        if (modalBody) {
            const errorDiv = document.createElement('div');
            errorDiv.id = 'form-error-alert';
            errorDiv.className = 'alert alert-error';
            errorDiv.style.marginBottom = '1rem';
            errorDiv.innerHTML = `<strong>Error:</strong> ${message}`;
            modalBody.insertBefore(errorDiv, modalBody.firstChild);
            // Scroll to top of modal to show error
            modalBody.scrollTop = 0;
        } else {
            // Fallback to regular alert if not in modal
            this.showAlert(message);
        }
    },

    // Format date (handles YYYY-MM-DD without timezone shift)
    formatDate(dateStr) {
        if (!dateStr) return '-';
        // Parse YYYY-MM-DD as local date, not UTC
        const [year, month, day] = dateStr.split('-');
        if (year && month && day) {
            return new Date(year, month - 1, day).toLocaleDateString();
        }
        return new Date(dateStr).toLocaleDateString();
    },

    // Format time (24h HH:MM → HH:MM display)
    formatTime(timeStr) {
        if (!timeStr) return '-';
        return timeStr.slice(0, 5);
    },

    // Format time as 12-hour (HH:MM → h:MM AM/PM)
    format12Hour(timeStr) {
        if (!timeStr) return '';
        const [h, m] = timeStr.split(':').map(Number);
        if (isNaN(h) || isNaN(m)) return timeStr;
        const ampm = h >= 12 ? 'PM' : 'AM';
        const hour = h % 12 || 12;
        return `${hour}:${String(m).padStart(2, '0')} ${ampm}`;
    },

    // Get status badge
    getStatusBadge(status) {
        const classes = {
            'draft': 'badge-secondary',
            'submitted': 'badge-warning',
            'verified': 'badge-success',
            'billed': 'badge-primary',
            'paid': 'badge-success',
            'pending': 'badge-secondary',
            'assigned': 'badge-primary',
            'in_progress': 'badge-warning',
            'completed': 'badge-success',
            'cancelled': 'badge-danger',
            'active': 'badge-success',
            'inactive': 'badge-secondary',
            'suspended': 'badge-danger',
            'open': 'badge-success',
            'closed': 'badge-secondary'
        };
        return `<span class="badge ${classes[status] || 'badge-secondary'}">${status}</span>`;
    },

    // Get platform options HTML
    getPlatformOptions(selectedId = '') {
        return this.platforms.map(p =>
            `<option value="${p.platform_id}" ${p.platform_id == selectedId ? 'selected' : ''}>${p.name}</option>`
        ).join('');
    },

    // Get technician options HTML
    getTechnicianOptions(selectedId = '') {
        return this.technicians.map(t =>
            `<option value="${t.tech_id}" ${t.tech_id == selectedId ? 'selected' : ''}>${t.name}</option>`
        ).join('');
    },

    // Get technician checkboxes HTML for multi-select
    getTechnicianCheckboxes() {
        return this.technicians.map(t =>
            `<label><input type="checkbox" value="${t.tech_id}"> ${t.name}</label>`
        ).join('');
    },

    // Date navigator HTML - generates a single-day picker with prev/next arrows
    // prefix: unique ID prefix (e.g. 'job', 'entry')
    dateNavHtml(prefix) {
        const today = new Date().toISOString().split('T')[0];
        return `
            <div class="date-nav" id="${prefix}-date-nav">
                <button class="btn btn-sm btn-secondary date-nav-toggle" id="${prefix}-date-nav-toggle" title="Single day mode">
                    <i class="fas fa-calendar-day"></i>
                </button>
                <div class="date-nav-controls" id="${prefix}-date-nav-controls" style="display: none;">
                    <button class="btn btn-sm btn-secondary" id="${prefix}-date-prev" title="Previous day"><i class="fas fa-chevron-left"></i></button>
                    <input type="date" class="form-control" id="${prefix}-date-nav-input" value="${today}">
                    <button class="btn btn-sm btn-secondary" id="${prefix}-date-next" title="Next day"><i class="fas fa-chevron-right"></i></button>
                    <button class="btn btn-sm btn-secondary" id="${prefix}-date-today" title="Today" style="font-size: 0.75rem;">Today</button>
                </div>
            </div>
        `;
    },

    // Wire up date navigator events
    // prefix: ID prefix, fromId/toId: IDs of the from/to date inputs, onChange: callback
    initDateNav(prefix, fromId, toId, onChange) {
        const toggle = document.getElementById(`${prefix}-date-nav-toggle`);
        const controls = document.getElementById(`${prefix}-date-nav-controls`);
        const input = document.getElementById(`${prefix}-date-nav-input`);
        const fromEl = document.getElementById(fromId);
        const toEl = document.getElementById(toId);
        let active = false;

        const setDay = (dateStr) => {
            input.value = dateStr;
            fromEl.value = dateStr;
            toEl.value = dateStr;
            onChange();
        };

        const shiftDay = (delta) => {
            const d = new Date(input.value + 'T00:00:00');
            d.setDate(d.getDate() + delta);
            setDay(d.toISOString().split('T')[0]);
        };

        toggle.addEventListener('click', () => {
            active = !active;
            controls.style.display = active ? 'flex' : 'none';
            toggle.classList.toggle('active', active);
            if (active) {
                // Enter single day mode: set from/to to today (or current input)
                const today = new Date().toISOString().split('T')[0];
                const current = input.value || today;
                fromEl.style.display = 'none';
                toEl.style.display = 'none';
                setDay(current);
            } else {
                // Exit single day mode: clear from/to and show them
                fromEl.style.display = '';
                toEl.style.display = '';
                fromEl.value = '';
                toEl.value = '';
                onChange();
            }
        });

        document.getElementById(`${prefix}-date-prev`).addEventListener('click', () => shiftDay(-1));
        document.getElementById(`${prefix}-date-next`).addEventListener('click', () => shiftDay(1));
        document.getElementById(`${prefix}-date-today`).addEventListener('click', () => {
            setDay(new Date().toISOString().split('T')[0]);
        });
        input.addEventListener('change', () => setDay(input.value));
    },

    // Toggle multi-select dropdown
    toggleMultiSelect(id) {
        const container = document.getElementById(id);
        const isOpen = container.classList.contains('open');

        // Close all other multi-selects
        document.querySelectorAll('.multi-select.open').forEach(el => {
            if (el.id !== id) el.classList.remove('open');
        });

        container.classList.toggle('open', !isOpen);
    },

    // Get selected values from multi-select
    getMultiSelectValues(id) {
        const container = document.getElementById(id);
        if (!container) return [];
        const checkboxes = container.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(checkboxes).map(cb => cb.value);
    },

    // Update multi-select display text
    updateMultiSelectDisplay(id, defaultText) {
        const container = document.getElementById(id);
        if (!container) return;
        const values = this.getMultiSelectValues(id);
        const displayEl = container.querySelector('.multi-select-text');

        if (values.length === 0) {
            displayEl.textContent = defaultText;
        } else if (values.length === 1) {
            // Show the label text for single selection
            const checkbox = container.querySelector(`input[value="${values[0]}"]`);
            displayEl.textContent = checkbox?.parentElement?.textContent?.trim() || values[0];
        } else {
            displayEl.textContent = `${values.length} selected`;
        }
    },

    // Initialize multi-select event handlers
    initMultiSelect(id, defaultText, onChange) {
        const container = document.getElementById(id);
        if (!container) return;

        // Add change handlers to checkboxes
        container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', () => {
                this.updateMultiSelectDisplay(id, defaultText);
                if (onChange) onChange();
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!container.contains(e.target)) {
                container.classList.remove('open');
            }
        });
    }
};

// Page renderers
const Pages = {
    // Dashboard page
    async dashboard(container) {
        const data = await API.reports.dashboard();
        const stats = data.dashboard;
        const isManager = ['admin', 'manager'].includes(App.user.role);

        let html = '<div class="stats-grid">';

        if (isManager) {
            html += `
                <div class="stat-card">
                    <div class="stat-label">Pending Verification</div>
                    <div class="stat-value text-warning">${stats.pending_verification || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Jobs</div>
                    <div class="stat-value text-primary">${stats.active_jobs || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Completed This Week</div>
                    <div class="stat-value text-success">${stats.completed_this_week || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Month Hours (Verified)</div>
                    <div class="stat-value">${(stats.month_hours?.verified || 0).toFixed(1)}</div>
                </div>
            `;
        } else {
            html += `
                <div class="stat-card">
                    <div class="stat-label">My Hours This Month</div>
                    <div class="stat-value text-primary">${(stats.my_hours_this_month || 0).toFixed(1)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">My Hours This Week</div>
                    <div class="stat-value">${(stats.my_hours_this_week || 0).toFixed(1)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Draft Entries</div>
                    <div class="stat-value text-warning">${stats.my_draft_entries || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Pending Entries</div>
                    <div class="stat-value text-primary">${stats.my_pending_entries || 0}</div>
                </div>
            `;
        }

        html += '</div>';

        // Quick actions
        html += `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Quick Actions</h3>
                </div>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="window.location.hash='time-entries'; setTimeout(() => document.getElementById('new-entry-btn')?.click(), 100)">
                        <i class="fas fa-plus"></i> New Time Entry
                    </button>
                    <button class="btn btn-secondary" onclick="window.location.hash='jobs'">
                        <i class="fas fa-briefcase"></i> View Jobs
                    </button>
                    ${isManager ? `
                        <button class="btn btn-secondary" onclick="window.location.hash='reports'">
                            <i class="fas fa-chart-bar"></i> View Reports
                        </button>
                    ` : ''}
                </div>
            </div>
        `;

        // My Assigned Jobs section (for technicians)
        if (!isManager) {
            html += `
                <div class="card" id="my-assigned-jobs-card">
                    <div class="card-header">
                        <h3 class="card-title"><i class="fas fa-tasks"></i> My Assigned Jobs</h3>
                    </div>
                    <div id="my-assigned-jobs-content">
                        <div class="loading"><div class="spinner"></div>Loading...</div>
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;

        // Load assigned jobs for technicians
        if (!isManager) {
            try {
                const assignedData = await API.assignments.getMyAssignedJobs();
                const jobs = assignedData.jobs || [];
                const contentDiv = document.getElementById('my-assigned-jobs-content');

                if (jobs.length === 0) {
                    contentDiv.innerHTML = '<p class="text-muted" style="padding: 1rem;">No jobs currently assigned to you.</p>';
                } else {
                    contentDiv.innerHTML = `
                        <div class="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Ticket</th>
                                        <th>Client</th>
                                        <th>Date</th>
                                        <th>Location</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${jobs.map(job => `
                                        <tr>
                                            <td>${job.external_url
                                                ? `<a href="${job.external_url}" target="_blank">${job.ticket_number || '-'}</a>`
                                                : (job.ticket_number || '-')}</td>
                                            <td>${job.client_name || '-'}</td>
                                            <td>${App.formatDate(job.job_date)}</td>
                                            <td>${job.location || '-'}</td>
                                            <td>${App.getStatusBadge(job.job_status)}</td>
                                            <td>
                                                <button class="btn btn-sm btn-secondary" onclick="Pages.viewJob(${job.job_id})">View</button>
                                                <button class="btn btn-sm btn-success" onclick="Pages.addTimeToJob(${job.job_id})">+ Time</button>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                }
            } catch (e) {
                console.error('Failed to load assigned jobs:', e);
                document.getElementById('my-assigned-jobs-content').innerHTML =
                    '<p class="text-muted" style="padding: 1rem;">Could not load assigned jobs.</p>';
            }
        }
    },

    // Jobs page
    async jobs(container) {
        const isManager = ['admin', 'manager'].includes(App.user.role);

        let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Jobs</h3>
                    ${isManager ? '<button class="btn btn-primary" id="new-job-btn"><i class="fas fa-plus"></i> New Job</button>' : ''}
                </div>
                <div class="filters">
                    <select class="form-control" id="job-status-filter">
                        <option value="">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="assigned">Assigned</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                        <option value="cancelled">Cancelled</option>
                    </select>
                    <select class="form-control" id="job-platform-filter">
                        <option value="">All Platforms</option>
                        ${App.getPlatformOptions()}
                    </select>
                    ${App.dateNavHtml('job')}
                    <input type="date" class="form-control" id="job-from-date" title="From date">
                    <input type="date" class="form-control" id="job-to-date" title="To date">
                    <input type="text" class="form-control" id="job-search" placeholder="Search...">
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Ticket #</th>
                                <th>Description</th>
                                <th>Platform</th>
                                <th>Client</th>
                                <th class="sortable" data-sort="job_date">Date <span id="sort-date-icon"></span></th>
                                <th class="sortable" data-sort="job_status">Status <span id="sort-status-icon"></span></th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="jobs-table"></tbody>
                    </table>
                </div>
                <div class="pagination" id="jobs-pagination"></div>
            </div>
        `;

        container.innerHTML = html;

        // Sort state
        let currentSort = { by: 'job_date', order: 'desc' };

        const updateSortIcons = () => {
            document.getElementById('sort-date-icon').textContent = currentSort.by === 'job_date' ? (currentSort.order === 'desc' ? '▼' : '▲') : '';
            document.getElementById('sort-status-icon').textContent = currentSort.by === 'job_status' ? (currentSort.order === 'desc' ? '▼' : '▲') : '';
        };

        const loadJobs = async (page = 1) => {
            const params = { page, per_page: 20 };
            const status = document.getElementById('job-status-filter').value;
            const platform = document.getElementById('job-platform-filter').value;
            const search = document.getElementById('job-search').value;
            const fromDate = document.getElementById('job-from-date').value;
            const toDate = document.getElementById('job-to-date').value;

            if (status) params.status = status;
            if (platform) params.platform_id = platform;
            if (search) params.search = search;
            if (fromDate) params.from_date = fromDate;
            if (toDate) params.to_date = toDate;
            params.sort_by = currentSort.by;
            params.sort_order = currentSort.order;

            const data = await API.jobs.list(params);

            const tbody = document.getElementById('jobs-table');
            if (data.jobs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center">No jobs found</td></tr>';
            } else {
                tbody.innerHTML = data.jobs.map(job => {
                    const ticketCell = job.external_url
                        ? `<a href="${job.external_url}" target="_blank" title="Open in platform">${job.ticket_number || '-'}</a>`
                        : (job.ticket_number || '-');
                    return `
                    <tr>
                        <td>${ticketCell}</td>
                        <td>${job.description}</td>
                        <td>${job.platform_name || '-'}</td>
                        <td>${job.client_name || '-'}</td>
                        <td>${App.formatDate(job.job_date)}</td>
                        <td>${App.getStatusBadge(job.job_status)}</td>
                        <td>
                            <button class="btn btn-sm btn-secondary" onclick="Pages.viewJob(${job.job_id})">View</button>
                            <button class="btn btn-sm btn-success" onclick="Pages.addTimeToJob(${job.job_id})">+ Time</button>
                            ${isManager ? `<button class="btn btn-sm btn-info" onclick="Pages.assignTechniciansToJob(${job.job_id})" title="Assign Technicians"><i class="fas fa-user-plus"></i></button>` : ''}
                            ${isManager ? `<button class="btn btn-sm btn-danger" onclick="Pages.deleteJob(${job.job_id})">Delete</button>` : ''}
                        </td>
                    </tr>
                `}).join('');
            }
            updateSortIcons();

            // Pagination
            const pagination = document.getElementById('jobs-pagination');
            pagination.innerHTML = `
                <button ${page <= 1 ? 'disabled' : ''} onclick="Pages.jobsPage(${page - 1})">Prev</button>
                <span style="padding: 0.5rem;">Page ${page} of ${data.pages}</span>
                <button ${page >= data.pages ? 'disabled' : ''} onclick="Pages.jobsPage(${page + 1})">Next</button>
            `;
        };

        Pages.jobsPage = loadJobs;

        // Event listeners
        document.getElementById('job-status-filter').addEventListener('change', () => loadJobs(1));
        document.getElementById('job-platform-filter').addEventListener('change', () => loadJobs(1));
        document.getElementById('job-from-date').addEventListener('change', () => loadJobs(1));
        document.getElementById('job-to-date').addEventListener('change', () => loadJobs(1));
        document.getElementById('job-search').addEventListener('input', debounce(() => loadJobs(1), 300));
        App.initDateNav('job', 'job-from-date', 'job-to-date', () => loadJobs(1));

        // Sortable columns
        document.querySelectorAll('.sortable').forEach(th => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                const sortBy = th.dataset.sort;
                if (currentSort.by === sortBy) {
                    currentSort.order = currentSort.order === 'desc' ? 'asc' : 'desc';
                } else {
                    currentSort.by = sortBy;
                    currentSort.order = 'desc';
                }
                loadJobs(1);
            });
        });

        if (isManager) {
            document.getElementById('new-job-btn').addEventListener('click', () => Pages.editJob(null));
        }

        await loadJobs(1);
    },

    // Calendar page
    async calendar(container) {
        // State: track current month/year
        const state = {
            year: new Date().getFullYear(),
            month: new Date().getMonth(), // 0-indexed
            jobs: [],
            myJobIds: new Set()
        };

        const isManager = ['admin', 'manager'].includes(App.user.role);

        // Chip background colors by status
        const chipColors = {
            pending:     { bg: '#fef3c7', border: '#f59e0b', text: '#92400e' },
            assigned:    { bg: '#dbeafe', border: '#2563eb', text: '#1e3a8a' },
            in_progress: { bg: '#ffedd5', border: '#ea580c', text: '#7c2d12' },
            completed:   { bg: '#d1fae5', border: '#10b981', text: '#064e3b' },
            cancelled:   { bg: '#f3f4f6', border: '#9ca3af', text: '#6b7280' }
        };

        function formatMonthYear(year, month) {
            return new Date(year, month, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        }

        async function loadJobs() {
            // Build from/to dates for the full month (plus buffer for neighbor cells)
            const firstDay = new Date(state.year, state.month, 1);
            const lastDay = new Date(state.year, state.month + 1, 0);

            // Fetch up to 200 jobs for the month
            const fromDate = firstDay.toISOString().split('T')[0];
            const toDate = lastDay.toISOString().split('T')[0];

            const data = await API.jobs.list({ from_date: fromDate, to_date: toDate, per_page: 200, page: 1 });
            state.jobs = data.jobs || [];

            // For technicians, fetch their assigned job IDs
            state.myJobIds = new Set();
            if (!isManager) {
                try {
                    const assignedData = await API.assignments.getMyAssignedJobs();
                    (assignedData.jobs || []).forEach(j => state.myJobIds.add(j.job_id));
                } catch (e) {
                    // Non-fatal
                }
            }
        }

        function buildCalendarHTML() {
            const year = state.year;
            const month = state.month;
            const today = new Date();
            const todayStr = today.toISOString().split('T')[0];

            const firstDow = new Date(year, month, 1).getDay(); // 0=Sun
            const daysInMonth = new Date(year, month + 1, 0).getDate();

            // Group jobs by date
            const jobsByDate = {};
            for (const job of state.jobs) {
                if (!job.job_date) continue;
                if (!jobsByDate[job.job_date]) jobsByDate[job.job_date] = [];
                jobsByDate[job.job_date].push(job);
            }

            const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

            let cells = '';
            // Leading empty cells
            for (let i = 0; i < firstDow; i++) {
                cells += `<div class="calendar-day calendar-day--other-month"></div>`;
            }
            // Day cells
            for (let d = 1; d <= daysInMonth; d++) {
                const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                const isToday = dateStr === todayStr;
                const dayJobs = jobsByDate[dateStr] || [];

                const chips = dayJobs.map(job => {
                    const isMine = state.myJobIds.has(job.job_id);
                    const colors = chipColors[job.job_status] || chipColors.cancelled;
                    const timeLabel = job.scheduled_start_time
                        ? ` <span style="opacity:0.75;">(${App.format12Hour(job.scheduled_start_time)})</span>`
                        : '';
                    const mineStyle = isMine ? `border-left: 3px solid #f59e0b; font-weight: 600;` : '';
                    const label = `${job.ticket_number || '#' + job.job_id} – ${job.client_name || ''}`;
                    return `<div class="calendar-chip" style="background:${colors.bg}; color:${colors.text}; border: 1px solid ${colors.border}; ${mineStyle}" onclick="Pages.viewJob(${job.job_id})" title="${job.description || ''}">${label}${timeLabel}</div>`;
                }).join('');

                cells += `
                    <div class="calendar-day ${isToday ? 'calendar-day--today' : ''}">
                        <div class="calendar-day-number">${d}</div>
                        ${chips}
                    </div>`;
            }
            // Trailing empty cells to complete the grid row
            const totalCells = firstDow + daysInMonth;
            const trailingCells = (7 - (totalCells % 7)) % 7;
            for (let i = 0; i < trailingCells; i++) {
                cells += `<div class="calendar-day calendar-day--other-month"></div>`;
            }

            return `
                <div class="card">
                    <div class="card-header" style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                        <button class="btn btn-sm btn-secondary" id="cal-prev"><i class="fas fa-chevron-left"></i></button>
                        <h3 class="card-title" style="margin: 0; min-width: 180px; text-align: center;" id="cal-month-label">${formatMonthYear(year, month)}</h3>
                        <button class="btn btn-sm btn-secondary" id="cal-next"><i class="fas fa-chevron-right"></i></button>
                        <button class="btn btn-sm btn-primary" id="cal-today">Today</button>
                        <span style="margin-left: auto; color: var(--gray-500); font-size: 0.85rem;">${state.jobs.length} job${state.jobs.length !== 1 ? 's' : ''} this month</span>
                    </div>
                    <div style="padding: 0.5rem;">
                        <div class="calendar-grid calendar-grid--header">
                            ${dayHeaders.map(h => `<div class="calendar-day-header">${h}</div>`).join('')}
                        </div>
                        <div class="calendar-grid">
                            ${cells}
                        </div>
                    </div>
                </div>
            `;
        }

        async function render() {
            container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
            await loadJobs();
            container.innerHTML = buildCalendarHTML();
            attachEvents();
        }

        function attachEvents() {
            document.getElementById('cal-prev').addEventListener('click', async () => {
                state.month--;
                if (state.month < 0) { state.month = 11; state.year--; }
                await render();
            });
            document.getElementById('cal-next').addEventListener('click', async () => {
                state.month++;
                if (state.month > 11) { state.month = 0; state.year++; }
                await render();
            });
            document.getElementById('cal-today').addEventListener('click', async () => {
                state.year = new Date().getFullYear();
                state.month = new Date().getMonth();
                await render();
            });
        }

        await render();
    },

    // Unified job modal - view/edit in one modal
    // mode: 'view' (default for existing jobs) or 'edit' (default for new jobs)
    async viewJob(jobId) {
        return Pages.jobModal(jobId, 'view');
    },

    async editJob(jobId) {
        return Pages.jobModal(jobId, 'edit');
    },

    async jobModal(jobId, mode = 'view') {
        const isManager = ['admin', 'manager'].includes(App.user.role);
        const isNew = !jobId;

        // New job always opens in edit mode
        if (isNew) mode = 'edit';

        let job = {};
        let entries = [];
        let entriesData = {};
        let assignmentsHtml = '';
        let payHtml = '';
        let entriesHtml = '';

        if (!isNew) {
            const data = await API.jobs.get(jobId);
            job = data.job;

            // Fetch time entries
            entriesData = await API.jobs.getTimeEntries(jobId);
            entries = entriesData.time_entries || [];

            // Fetch assignments (managers only)
            if (isManager) {
                try {
                    const assignmentsData = await API.assignments.getJobAssignments(jobId);
                    const assignments = assignmentsData.assignments || [];
                    if (assignments.length > 0) {
                        assignmentsHtml = `
                            <div class="form-group" style="margin-top: 1rem;">
                                <label>Assigned Technicians (${assignments.length})
                                    <button class="btn btn-sm btn-info" style="margin-left: 1rem;" onclick="App.hideModal(); Pages.assignTechniciansToJob(${jobId})">
                                        <i class="fas fa-user-plus"></i> Assign More
                                    </button>
                                </label>
                                <div class="table-container" style="max-height: 150px; overflow-y: auto;">
                                    <table style="font-size: 0.85rem;">
                                        <thead>
                                            <tr>
                                                <th>Technician</th>
                                                <th>Phone</th>
                                                <th>Status</th>
                                                <th>SMS</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${assignments.map(a => {
                                                const smsStatusBadge = a.sms_sent_at
                                                    ? (a.sms_status === 'delivered' ? '<span class="badge badge-success">Delivered</span>'
                                                        : a.sms_status === 'failed' ? '<span class="badge badge-danger">Failed</span>'
                                                        : '<span class="badge badge-warning">Sent</span>')
                                                    : '<span class="badge badge-secondary">Not Sent</span>';
                                                return `
                                                <tr>
                                                    <td>${a.tech_name}</td>
                                                    <td>${a.tech_phone || '-'}</td>
                                                    <td>${App.getStatusBadge(a.status)}</td>
                                                    <td>${smsStatusBadge}</td>
                                                    <td>
                                                        ${a.sms_status === 'failed' || !a.sms_sent_at ? `<button class="btn btn-sm btn-warning" onclick="Pages.resendAssignmentSms(${a.assignment_id}, ${jobId})">Resend SMS</button>` : ''}
                                                        <button class="btn btn-sm btn-danger" onclick="Pages.removeAssignment(${a.assignment_id}, ${jobId})">Remove</button>
                                                    </td>
                                                </tr>
                                            `}).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        `;
                    } else {
                        assignmentsHtml = `
                            <div class="form-group" style="margin-top: 1rem;">
                                <label>Assigned Technicians</label>
                                <p class="text-muted">No technicians assigned yet
                                    <button class="btn btn-sm btn-info" style="margin-left: 0.5rem;" onclick="App.hideModal(); Pages.assignTechniciansToJob(${jobId})">
                                        <i class="fas fa-user-plus"></i> Assign
                                    </button>
                                </p>
                            </div>
                        `;
                    }
                } catch (e) {
                    console.error('Failed to load assignments:', e);
                }
            }

            // Fetch pay calculation (managers only)
            if (isManager && entries.length > 0) {
                try {
                    const payData = await API.settings.getJobPay(jobId);
                    payHtml = `
                        <div class="form-group" style="margin-top: 1rem; background: #f8f9fa; padding: 1rem; border-radius: 4px;">
                            <label style="font-size: 1.1rem; margin-bottom: 0.5rem;">Pay Breakdown</label>
                            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 0.5rem; margin-bottom: 1rem;">
                                <div><small>Job Net:</small> <strong>$${payData.job_net.toFixed(2)}</strong></div>
                                <div><small>Tech Pool (50%):</small> <strong>$${payData.tech_pool.toFixed(2)}</strong></div>
                                <div><small>Total Deductions:</small> <strong>$${payData.total_deductions.toFixed(2)}</strong></div>
                                <div><small>Total Pay:</small> <strong>$${payData.totals.total_pay.toFixed(2)}</strong></div>
                            </div>
                            <div class="table-container" style="max-height: 250px; overflow-y: auto;">
                                <table style="font-size: 0.85rem;">
                                    <thead>
                                        <tr>
                                            <th>Technician</th>
                                            <th>Hours</th>
                                            <th>Rate</th>
                                            <th>Base Pay</th>
                                            <th>Mileage</th>
                                            <th>Per Diem</th>
                                            <th>Expenses</th>
                                            <th>Total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${payData.technicians.map(t => `
                                            <tr>
                                                <td>${t.tech_name}</td>
                                                <td>${t.hours}</td>
                                                <td>$${t.effective_rate.toFixed(2)}/hr ${t.using_minimum ? '<span class="badge badge-info" title="Using minimum pay rate">MIN</span>' : ''}</td>
                                                <td>$${t.base_pay.toFixed(2)}</td>
                                                <td>$${t.mileage_pay.toFixed(2)} <small>(${t.mileage} mi)</small></td>
                                                <td>$${t.per_diem.toFixed(2)}</td>
                                                <td>$${t.personal_expenses.toFixed(2)}</td>
                                                <td><strong>$${t.total_pay.toFixed(2)}</strong></td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `;
                } catch (e) {
                    console.error('Failed to load pay data:', e);
                }
            }

            // Build time entries table
            if (entries.length > 0) {
                entriesHtml = `
                    <div class="form-group" style="margin-top: 1rem;">
                        <label>Time Entries (${entries.length})</label>
                        <div class="table-container" style="max-height: 200px; overflow-y: auto;">
                            <table style="font-size: 0.85rem;">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Technician</th>
                                        <th>Hours</th>
                                        <th>Mileage</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${entries.map(e => `
                                        <tr>
                                            <td>${App.formatDate(e.date_worked)}</td>
                                            <td>${e.tech_name || 'Tech #' + e.tech_id}</td>
                                            <td>${e.hours_worked || '-'}</td>
                                            <td>${e.mileage || 0}</td>
                                            <td>${App.getStatusBadge(e.status)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            } else {
                entriesHtml = `
                    <div class="form-group" style="margin-top: 1rem;">
                        <label>Time Entries</label>
                        <p class="text-muted">No time entries yet</p>
                    </div>
                `;
            }
        }

        const editing = mode === 'edit';

        // Helper: render a field as view or edit
        const field = (label, viewVal, editInput) => {
            if (editing) return `<div class="form-group"><label>${label}</label>${editInput}</div>`;
            return `<div class="form-group"><label>${label}</label><p>${viewVal}</p></div>`;
        };

        // Build the job fields section
        const ticketView = job.external_url
            ? `<a href="${job.external_url}" target="_blank" rel="noopener noreferrer">${job.ticket_number || '-'} <i class="fas fa-external-link-alt" style="font-size: 0.8em;"></i></a>`
            : (job.ticket_number || '-');

        const statusOptions = ['pending', 'assigned', 'in_progress', 'completed', 'cancelled'];
        const statusSelect = `<select class="form-control" name="job_status">
            ${statusOptions.map(s => `<option value="${s}" ${job.job_status === s ? 'selected' : ''}>${s.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>`).join('')}
        </select>`;

        const billingTypes = [['flat_rate', 'Flat Rate'], ['hourly', 'Hourly'], ['per_task', 'Per Task']];
        const billingSelect = `<select class="form-control" name="billing_type">
            ${billingTypes.map(([v, l]) => `<option value="${v}" ${job.billing_type === v ? 'selected' : ''}>${l}</option>`).join('')}
        </select>`;

        const formOpen = editing ? '<form id="job-form">' : '';
        const formClose = editing ? '</form>' : '';

        const body = `
            ${formOpen}
            ${field('Platform', job.platform_name || '-',
                `<select class="form-control" name="platform_id" required>
                    <option value="">Select Platform</option>
                    ${App.getPlatformOptions(job.platform_id)}
                </select>`)}
            ${field('Ticket Number', ticketView,
                `<input type="text" class="form-control" name="ticket_number" value="${job.ticket_number || ''}">`)}
            ${field('Description', job.description || '-',
                `<input type="text" class="form-control" name="description" value="${job.description || ''}" required>`)}
            <div class="form-row">
                ${field('Client', job.client_name || '-',
                    `<input type="text" class="form-control" name="client_name" value="${job.client_name || ''}">`)}
                ${field('Job Type', job.job_type || '-',
                    `<input type="text" class="form-control" name="job_type" value="${job.job_type || ''}">`)}
            </div>
            ${field('Location', job.location || '-',
                `<input type="text" class="form-control" name="location" value="${job.location || ''}">`)}
            ${editing ? field('External Platform URL', '',
                `<input type="url" class="form-control" name="external_url" value="${job.external_url || ''}" placeholder="https://...">`) : ''}
            <div class="form-row">
                ${field('Status', App.getStatusBadge(job.job_status), statusSelect)}
                ${editing
                    ? field('Billing Type', '', billingSelect)
                    : `<div class="form-group"><label>Billing</label><p>${job.billing_type || 'flat_rate'}: $${job.billing_amount || 0}</p></div>`}
            </div>
            ${editing ? `<div class="form-row">
                ${field('Billing Amount', '',
                    `<input type="number" step="0.01" class="form-control" name="billing_amount" value="${job.billing_amount || ''}">`)}
                <div class="form-group"></div>
            </div>` : ''}
            <div class="form-row">
                ${field('Job Date',
                    `${App.formatDate(job.job_date)}${job.scheduled_start_time ? ` <span class="badge badge-secondary">${App.format12Hour(job.scheduled_start_time)}</span>` : ''}`,
                    `<input type="date" class="form-control" name="job_date" value="${job.job_date || ''}">`)}
                ${editing
                    ? field('Start Time <small class="text-muted">(optional)</small>', '',
                        `<input type="time" class="form-control" name="scheduled_start_time" value="${job.scheduled_start_time || ''}">`)
                    : `<div class="form-group"><label>Total Hours</label><p>${entriesData.total_hours || 0}</p></div>`}
            </div>
            <div class="form-row">
                ${field('Expenses', `$${job.expenses || 0}`,
                    `<input type="number" step="0.01" class="form-control" name="expenses" value="${job.expenses || ''}">`)}
                ${field('Commissions', `$${job.commissions || 0}`,
                    `<input type="number" step="0.01" class="form-control" name="commissions" value="${job.commissions || ''}">`)}
            </div>
            ${formClose}
            ${!isNew ? assignmentsHtml : ''}
            ${!isNew ? entriesHtml : ''}
            ${!isNew ? payHtml : ''}
        `;

        // Build actions bar (sticky top) and footer
        let actions = '';
        let footer = '';

        if (editing) {
            actions = `
                <button class="btn btn-sm btn-secondary" onclick="${isNew ? 'App.hideModal()' : `Pages.jobModal(${jobId}, 'view')`}">Cancel</button>
                <button class="btn btn-sm btn-primary" onclick="Pages.saveJob(${jobId})"><i class="fas fa-save"></i> Save</button>
            `;
        } else {
            actions = `
                ${isManager ? `<button class="btn btn-sm btn-primary" onclick="Pages.jobModal(${jobId}, 'edit')">
                    <i class="fas fa-edit"></i> Edit
                </button>` : ''}
                ${isManager ? `<button class="btn btn-sm btn-info" onclick="App.hideModal(); Pages.assignTechniciansToJob(${jobId})">
                    <i class="fas fa-user-plus"></i> Assign Techs
                </button>` : ''}
                ${isManager ? `<button class="btn btn-sm btn-warning" onclick="App.hideModal(); Pages.requestAvailability(${jobId})">
                    <i class="fas fa-question-circle"></i> Availability
                </button>` : ''}
                <button class="btn btn-sm btn-success" onclick="App.hideModal(); Pages.addTimeToJob(${jobId})">
                    <i class="fas fa-plus"></i> Add Time
                </button>
                <button class="btn btn-sm btn-secondary" onclick="App.hideModal()" style="margin-left: auto;">Close</button>
            `;
        }

        const title = isNew ? 'New Job' : (editing ? 'Edit Job' : 'Job Details');
        App.showModal(title, body, footer, { wide: true, actions });
    },

    // Save job
    async saveJob(jobId) {
        const form = document.getElementById('job-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        try {
            if (jobId) {
                await API.jobs.update(jobId, data);
                App.showAlert('Job updated successfully', 'success');
                // Return to view mode after save
                await Pages.jobModal(jobId, 'view');
            } else {
                await API.jobs.create(data);
                App.showAlert('Job created successfully', 'success');
                App.hideModal();
            }
            if (Pages.jobsPage) Pages.jobsPage(1);
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Add time entry for a specific job
    async addTimeToJob(jobId) {
        const jobData = await API.jobs.get(jobId);
        const job = jobData.job;
        const isManager = ['admin', 'manager'].includes(App.user.role);

        // Technician field - only show for managers/admins (optional for imported entries)
        const techField = isManager ? `
            <div class="form-group">
                <label>Technician</label>
                <select class="form-control" name="tech_id">
                    <option value="">Unassigned</option>
                    ${App.getTechnicianOptions()}
                </select>
                <small class="text-muted">Leave unassigned for imported entries that need review</small>
            </div>
        ` : '';

        const body = `
            <form id="entry-form">
                <div class="form-group">
                    <label>Job</label>
                    <input type="text" class="form-control" value="${job.ticket_number || job.job_id} - ${job.description}" readonly>
                    <input type="hidden" name="job_id" value="${jobId}">
                </div>
                ${techField}
                <div class="form-group">
                    <label>Date Worked *</label>
                    <input type="date" class="form-control" name="date_worked" value="${new Date().toISOString().split('T')[0]}" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Time In</label>
                        <input type="time" class="form-control" name="time_in">
                    </div>
                    <div class="form-group">
                        <label>Time Out</label>
                        <input type="time" class="form-control" name="time_out">
                    </div>
                </div>
                <div class="form-group">
                    <label>Hours (auto-calculated if times provided)</label>
                    <input type="number" step="0.25" class="form-control" name="hours_worked">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Mileage</label>
                        <input type="number" step="0.1" class="form-control" name="mileage">
                    </div>
                    <div class="form-group">
                        <label>Per Diem</label>
                        <input type="number" step="0.01" class="form-control" name="per_diem">
                    </div>
                </div>
                <div class="form-group">
                    <label>Personal Expenses</label>
                    <input type="number" step="0.01" class="form-control" name="personal_expenses">
                </div>
                <div class="form-group">
                    <label>Notes</label>
                    <textarea class="form-control" name="notes" rows="3"></textarea>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveEntry(null)">Save</button>
        `;

        App.showModal(`Add Time - ${job.ticket_number || 'Job ' + jobId}`, body, footer);
    },

    // Delete job
    async deleteJob(jobId) {
        if (!confirm('Are you sure you want to delete this job? This cannot be undone.\n\nNote: Jobs with time entries cannot be deleted.')) {
            return;
        }

        try {
            await API.jobs.delete(jobId);
            App.showAlert('Job deleted', 'success');
            Pages.jobsPage(1);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Assign technicians to job modal
    async assignTechniciansToJob(jobId) {
        const jobData = await API.jobs.get(jobId);
        const job = jobData.job;

        // Get existing assignments
        let existingTechIds = [];
        try {
            const assignmentsData = await API.assignments.getJobAssignments(jobId);
            existingTechIds = (assignmentsData.assignments || []).map(a => a.tech_id);
        } catch (e) {
            console.error('Failed to load existing assignments:', e);
        }

        // Get active technicians (filter out already assigned)
        const availableTechs = App.technicians.filter(t => t.status === 'active' && !existingTechIds.includes(t.tech_id));

        if (availableTechs.length === 0) {
            App.showAlert('All active technicians are already assigned to this job', 'info');
            return;
        }

        const body = `
            <form id="assign-techs-form">
                <p>Assign technicians to job: <strong>${job.ticket_number || 'Job #' + jobId}</strong></p>
                <p class="text-muted">${job.description}</p>

                <div class="form-group">
                    <label>Select Technicians</label>
                    <div style="max-height: 200px; overflow-y: auto; border: 1px solid var(--gray-300); border-radius: 4px; padding: 0.5rem;">
                        ${availableTechs.map(t => `
                            <label style="display: block; padding: 0.25rem 0; cursor: pointer;">
                                <input type="checkbox" name="tech_ids" value="${t.tech_id}" style="margin-right: 0.5rem;">
                                ${t.name} ${t.phone ? `<small class="text-muted">(${t.phone})</small>` : '<small class="text-warning">(no phone)</small>'}
                            </label>
                        `).join('')}
                    </div>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" name="send_sms" checked style="margin-right: 0.5rem;">
                        Send SMS notification to assigned technicians
                    </label>
                </div>

                <div class="form-group">
                    <label>Assignment Notes (optional)</label>
                    <textarea class="form-control" name="notes" rows="2" placeholder="Additional instructions or details for the technicians..."></textarea>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveJobAssignments(${jobId})">Assign</button>
        `;

        App.showModal('Assign Technicians', body, footer);
    },

    // Save job assignments
    async saveJobAssignments(jobId) {
        const form = document.getElementById('assign-techs-form');
        const checkboxes = form.querySelectorAll('input[name="tech_ids"]:checked');
        const techIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
        const sendSms = form.querySelector('input[name="send_sms"]').checked;
        const notes = form.querySelector('textarea[name="notes"]').value;

        if (techIds.length === 0) {
            App.showFormError('Please select at least one technician');
            return;
        }

        try {
            const result = await API.assignments.assignTechnicians(jobId, techIds, sendSms, notes);
            App.showAlert(`Assigned ${result.assignments.length} technician(s)`, 'success');
            App.hideModal();
            // Refresh jobs list if we're on jobs page
            if (typeof Pages.jobsPage === 'function') {
                Pages.jobsPage(1);
            }
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Remove assignment
    async removeAssignment(assignmentId, jobId) {
        if (!confirm('Remove this technician from the job?')) {
            return;
        }

        try {
            await API.assignments.removeAssignment(assignmentId);
            App.showAlert('Assignment removed', 'success');
            // Refresh the job view modal
            App.hideModal();
            await Pages.viewJob(jobId);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Request availability from technicians for a job
    async requestAvailability(jobId) {
        const job = await API.jobs.get(jobId).catch(() => null);

        // Get existing assignments (to skip already-active techs)
        let existingTechIds = [];
        try {
            const assignmentsData = await API.assignments.getJobAssignments(jobId);
            existingTechIds = (assignmentsData.assignments || [])
                .filter(a => ['accepted', 'invited'].includes(a.status))
                .map(a => a.tech_id);
        } catch (e) { /* ignore */ }

        const availableTechs = App.technicians.filter(t =>
            t.status === 'active' && !existingTechIds.includes(t.tech_id)
        );

        if (availableTechs.length === 0) {
            App.showAlert('All active technicians already have active assignments for this job', 'info');
            return;
        }

        const body = `
            <form id="avail-request-form">
                <p>Send availability request for: <strong>${job?.job?.ticket_number || 'Job #' + jobId}</strong></p>
                <div class="form-group">
                    <label>Select Technicians</label>
                    ${availableTechs.map(t => `
                        <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
                            <input type="checkbox" name="tech_ids" value="${t.tech_id}">
                            ${t.name}${t.phone ? ` <small class="text-muted">(${t.phone})</small>` : ' <small class="text-muted">(no phone)</small>'}
                            ${t.sms_opted_in === false ? '<span class="badge badge-danger" style="font-size:0.65rem;">Opted Out</span>' : ''}
                        </label>
                    `).join('')}
                </div>
                <div class="form-group">
                    <label>Notes (optional)</label>
                    <input type="text" class="form-control" name="notes" placeholder="e.g. 2-person job, starts 8am">
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-warning" onclick="Pages.saveAvailabilityRequest(${jobId})">
                <i class="fas fa-paper-plane"></i> Send Requests
            </button>
        `;

        App.showModal('Request Availability', body, footer);
    },

    // Send availability requests
    async saveAvailabilityRequest(jobId) {
        const form = document.getElementById('avail-request-form');
        const checked = [...form.querySelectorAll('input[name="tech_ids"]:checked')];
        const techIds = checked.map(cb => parseInt(cb.value));
        const notes = form.querySelector('input[name="notes"]').value.trim();

        if (techIds.length === 0) {
            App.showFormError('Select at least one technician');
            return;
        }

        try {
            const result = await API.assignments.requestAvailability(jobId, techIds, notes);
            const sent = result.sms_results?.filter(r => r.success).length || 0;
            App.showAlert(
                `Availability request sent to ${result.assignments.length} technician(s) (${sent} SMS delivered)`,
                'success'
            );
            if (result.errors?.length) {
                result.errors.forEach(e => App.showAlert(`${e.tech_id}: ${e.error}`, 'warning'));
            }
            App.hideModal();
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Resend assignment SMS
    async resendAssignmentSms(assignmentId, jobId) {
        if (!confirm('Resend SMS notification to this technician?')) {
            return;
        }

        try {
            await API.assignments.resendAssignmentSms(assignmentId);
            App.showAlert('SMS resent', 'success');
            // Refresh the job view modal
            App.hideModal();
            await Pages.viewJob(jobId);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Time entries page
    async timeEntries(container) {
        const isManager = ['admin', 'manager'].includes(App.user.role);

        let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Time Entries</h3>
                    <button class="btn btn-primary" id="new-entry-btn"><i class="fas fa-plus"></i> New Entry</button>
                </div>
                <div class="filters">
                    <div class="multi-select" id="entry-status-filter">
                        <div class="multi-select-display" onclick="App.toggleMultiSelect('entry-status-filter')">
                            <span class="multi-select-text">All Statuses</span>
                            <i class="fas fa-chevron-down"></i>
                        </div>
                        <div class="multi-select-dropdown">
                            <label><input type="checkbox" value="draft"> Draft</label>
                            <label><input type="checkbox" value="submitted"> Submitted</label>
                            <label><input type="checkbox" value="verified"> Verified</label>
                            <label><input type="checkbox" value="billed"> Billed</label>
                            <label><input type="checkbox" value="paid"> Paid</label>
                        </div>
                    </div>
                    ${isManager ? `
                    <div class="multi-select" id="entry-tech-filter">
                        <div class="multi-select-display" onclick="App.toggleMultiSelect('entry-tech-filter')">
                            <span class="multi-select-text">All Technicians</span>
                            <i class="fas fa-chevron-down"></i>
                        </div>
                        <div class="multi-select-dropdown">
                            <label><input type="checkbox" value="unassigned"> Unassigned</label>
                            ${App.getTechnicianCheckboxes()}
                        </div>
                    </div>
                    ` : ''}
                    ${App.dateNavHtml('entry')}
                    <input type="date" class="form-control" id="entry-from-date">
                    <input type="date" class="form-control" id="entry-to-date">
                    <input type="text" class="form-control" id="entry-job-search" placeholder="Search job...">
                    <button class="btn btn-primary btn-sm" id="bulk-submit-btn">Bulk Submit</button>
                    ${isManager ? '<button class="btn btn-success btn-sm" id="bulk-verify-btn">Bulk Verify</button>' : ''}
                    <button class="btn btn-secondary btn-sm" id="toggle-group-btn"><i class="fas fa-layer-group"></i> Group by Job</button>
                </div>
                <div id="entries-list-view" class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th><input type="checkbox" id="select-all-entries"></th>
                                <th class="sortable" data-sort="date_worked">Date <span id="sort-date-icon"></span></th>
                                <th>Job</th>
                                ${isManager ? '<th>Technician</th>' : ''}
                                <th>Time In</th>
                                <th>Time Out</th>
                                <th class="sortable" data-sort="hours_worked">Hours <span id="sort-hours-icon"></span></th>
                                <th>Mileage</th>
                                <th class="sortable" data-sort="status">Status <span id="sort-status-icon"></span></th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="entries-table"></tbody>
                    </table>
                </div>
                <div id="entries-grouped-view" style="display: none;"></div>
                <div class="pagination" id="entries-pagination"></div>
            </div>
        `;

        container.innerHTML = html;

        let isGroupedView = false;
        let currentSort = { by: 'date_worked', order: 'desc' };

        const updateSortIcons = () => {
            document.getElementById('sort-date-icon').textContent = currentSort.by === 'date_worked' ? (currentSort.order === 'desc' ? '▼' : '▲') : '';
            document.getElementById('sort-hours-icon').textContent = currentSort.by === 'hours_worked' ? (currentSort.order === 'desc' ? '▼' : '▲') : '';
            document.getElementById('sort-status-icon').textContent = currentSort.by === 'status' ? (currentSort.order === 'desc' ? '▼' : '▲') : '';
        };

        const loadEntries = async (page = 1) => {
            const params = { page, per_page: 20, sort_by: currentSort.by, sort_order: currentSort.order };
            const statuses = App.getMultiSelectValues('entry-status-filter');
            const techFilters = isManager ? App.getMultiSelectValues('entry-tech-filter') : [];
            const fromDate = document.getElementById('entry-from-date').value;
            const toDate = document.getElementById('entry-to-date').value;
            const jobSearch = document.getElementById('entry-job-search').value;

            if (statuses.length > 0) params.status = statuses.join(',');
            if (techFilters.includes('unassigned')) {
                params.unassigned = 'true';
                const techIds = techFilters.filter(t => t !== 'unassigned');
                if (techIds.length > 0) params.tech_id = techIds.join(',');
            } else if (techFilters.length > 0) {
                params.tech_id = techFilters.join(',');
            }
            if (fromDate) params.from_date = fromDate;
            if (toDate) params.to_date = toDate;
            if (jobSearch) params.job_search = jobSearch;

            const data = await API.timeEntries.list(params);
            updateSortIcons();

            const tbody = document.getElementById('entries-table');
            const colSpan = isManager ? 11 : 10;
            if (data.time_entries.length === 0) {
                tbody.innerHTML = `<tr><td colspan="${colSpan}" class="text-center">No entries found</td></tr>`;
            } else {
                tbody.innerHTML = data.time_entries.map(entry => {
                    const isUnassigned = !entry.tech_id;
                    const techDisplay = isUnassigned
                        ? '<span class="badge badge-warning">Unassigned</span>'
                        : (entry.tech_name || `Tech #${entry.tech_id}`);
                    return `
                    <tr>
                        <td><input type="checkbox" class="entry-checkbox" data-status="${entry.status}" data-unassigned="${isUnassigned}" value="${entry.entry_id}" ${isManager ? (!['draft', 'submitted'].includes(entry.status) ? 'disabled' : '') : (entry.status !== 'draft' ? 'disabled' : '')}></td>
                        <td>${App.formatDate(entry.date_worked)}</td>
                        <td title="${entry.job_title || ''}"><a href="#" onclick="Pages.viewJob(${entry.job_id}); return false;" class="job-link">${entry.job_ticket || entry.job_id}</a>${entry.job_client ? `<br><small class="text-muted">${entry.job_client}</small>` : ''}</td>
                        ${isManager ? `<td>${techDisplay}</td>` : ''}
                        <td>${App.formatTime(entry.time_in)}</td>
                        <td>${App.formatTime(entry.time_out)}</td>
                        <td>${entry.hours_worked || '-'}</td>
                        <td>${entry.mileage || '-'}</td>
                        <td>${App.getStatusBadge(entry.status)}</td>
                        <td>
                            ${entry.status === 'draft' && !isUnassigned ? `
                                <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                                <button class="btn btn-sm btn-success" onclick="Pages.submitEntry(${entry.entry_id})">Submit</button>
                            ` : ''}
                            ${entry.status === 'draft' && isUnassigned && isManager ? `
                                <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                                <button class="btn btn-sm btn-warning" onclick="Pages.assignTechnician(${entry.entry_id})">Assign</button>
                            ` : ''}
                            ${entry.status !== 'draft' && entry.status !== 'paid' && isManager ? `
                                <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                            ` : ''}
                            ${entry.status === 'submitted' && isManager ? `
                                <button class="btn btn-sm btn-success" onclick="Pages.verifyEntry(${entry.entry_id})">Verify</button>
                                <button class="btn btn-sm btn-danger" onclick="Pages.rejectEntry(${entry.entry_id})">Reject</button>
                            ` : ''}
                            ${isManager ? `
                                <button class="btn btn-sm btn-secondary" onclick="Pages.copyEntry(${entry.entry_id})">Copy</button>
                                <button class="btn btn-sm btn-danger" onclick="Pages.deleteEntry(${entry.entry_id})">Delete</button>
                            ` : (entry.status === 'draft' ? `
                                <button class="btn btn-sm btn-danger" onclick="Pages.deleteEntry(${entry.entry_id})">Delete</button>
                            ` : '')}
                        </td>
                    </tr>
                `}).join('');
            }

            // Pagination
            const pagination = document.getElementById('entries-pagination');
            pagination.innerHTML = `
                <button ${page <= 1 ? 'disabled' : ''} onclick="Pages.entriesPage(${page - 1})">Prev</button>
                <span style="padding: 0.5rem;">Page ${page} of ${data.pages}</span>
                <button ${page >= data.pages ? 'disabled' : ''} onclick="Pages.entriesPage(${page + 1})">Next</button>
            `;
        };

        Pages.entriesPage = loadEntries;
        Pages.entriesGroupedPage = null; // Will be set after loadGroupedEntries is defined

        // Grouped view loader
        const loadGroupedEntries = async () => {
            const params = {};
            const statuses = App.getMultiSelectValues('entry-status-filter');
            const techFilters = isManager ? App.getMultiSelectValues('entry-tech-filter') : [];
            const fromDate = document.getElementById('entry-from-date').value;
            const toDate = document.getElementById('entry-to-date').value;
            const jobSearch = document.getElementById('entry-job-search').value;

            if (statuses.length > 0) params.status = statuses.join(',');
            if (techFilters.includes('unassigned')) {
                params.unassigned = 'true';
                const techIds = techFilters.filter(t => t !== 'unassigned');
                if (techIds.length > 0) params.tech_id = techIds.join(',');
            } else if (techFilters.length > 0) {
                params.tech_id = techFilters.join(',');
            }
            if (fromDate) params.from_date = fromDate;
            if (toDate) params.to_date = toDate;
            if (jobSearch) params.job_search = jobSearch;

            const data = await API.timeEntries.groupedByJob(params);
            const groupedView = document.getElementById('entries-grouped-view');

            if (data.grouped_entries.length === 0) {
                groupedView.innerHTML = '<p class="text-center" style="padding: 2rem;">No entries found</p>';
            } else {
                groupedView.innerHTML = data.grouped_entries.map(job => `
                    <div class="card" style="margin-bottom: 1rem;">
                        <div class="card-header">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <a href="#" onclick="Pages.viewJob(${job.job_id}); return false;" class="job-link" style="font-weight: bold;">${job.job_ticket || 'Job #' + job.job_id}</a>
                                    <span style="margin-left: 1rem; color: #666;">${job.job_client || ''}</span>
                                </div>
                                <div>
                                    <span class="badge badge-info" style="cursor: pointer;" onclick="this.closest('.card').querySelector('.table-container').style.display = this.closest('.card').querySelector('.table-container').style.display === 'none' ? 'block' : 'none'"><i class="fas fa-chevron-down"></i> ${job.entry_count} entries</span>
                                    <span style="margin-left: 0.5rem;">${job.total_hours.toFixed(2)} hrs</span>
                                    ${job.billing_amount ? `<span style="margin-left: 0.5rem; color: green;">$${job.billing_amount.toFixed(2)}</span>` : ''}
                                </div>
                            </div>
                            <div style="font-size: 0.9rem; color: #666; margin-top: 0.25rem;">${job.job_title || ''}</div>
                        </div>
                        <div class="table-container" style="display: block;">
                            <table>
                                <thead>
                                    <tr>
                                        <th><input type="checkbox" class="select-all-job" data-job-id="${job.job_id}"></th>
                                        <th>Date</th>
                                        ${isManager ? '<th>Technician</th>' : ''}
                                        <th>Time In</th>
                                        <th>Time Out</th>
                                        <th>Hours</th>
                                        <th>Mileage</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${job.entries.map(entry => {
                                        const isUnassigned = !entry.tech_id;
                                        const techDisplay = isUnassigned
                                            ? '<span class="badge badge-warning">Unassigned</span>'
                                            : (entry.tech_name || 'Tech #' + entry.tech_id);
                                        return `
                                        <tr>
                                            <td><input type="checkbox" class="entry-checkbox" data-status="${entry.status}" data-unassigned="${isUnassigned}" value="${entry.entry_id}" ${isManager ? (!['draft', 'submitted'].includes(entry.status) ? 'disabled' : '') : (entry.status !== 'draft' ? 'disabled' : '')}></td>
                                            <td>${App.formatDate(entry.date_worked)}</td>
                                            ${isManager ? '<td>' + techDisplay + '</td>' : ''}
                                            <td>${App.formatTime(entry.time_in)}</td>
                                            <td>${App.formatTime(entry.time_out)}</td>
                                            <td>${entry.hours_worked || '-'}</td>
                                            <td>${entry.mileage || '-'}</td>
                                            <td>${App.getStatusBadge(entry.status)}</td>
                                            <td>
                                                ${entry.status === 'draft' && !isUnassigned ? `
                                                    <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                                                    <button class="btn btn-sm btn-success" onclick="Pages.submitEntry(${entry.entry_id})">Submit</button>
                                                ` : ''}
                                                ${entry.status === 'draft' && isUnassigned && isManager ? `
                                                    <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                                                    <button class="btn btn-sm btn-warning" onclick="Pages.assignTechnician(${entry.entry_id})">Assign</button>
                                                ` : ''}
                                                ${entry.status !== 'draft' && entry.status !== 'paid' && isManager ? `
                                                    <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                                                ` : ''}
                                                ${entry.status === 'submitted' && isManager ? `
                                                    <button class="btn btn-sm btn-success" onclick="Pages.verifyEntry(${entry.entry_id})">Verify</button>
                                                    <button class="btn btn-sm btn-danger" onclick="Pages.rejectEntry(${entry.entry_id})">Reject</button>
                                                ` : ''}
                                                ${isManager ? `
                                                    <button class="btn btn-sm btn-secondary" onclick="Pages.copyEntry(${entry.entry_id})">Copy</button>
                                                    <button class="btn btn-sm btn-danger" onclick="Pages.deleteEntry(${entry.entry_id})">Delete</button>
                                                ` : (entry.status === 'draft' ? `
                                                    <button class="btn btn-sm btn-danger" onclick="Pages.deleteEntry(${entry.entry_id})">Delete</button>
                                                ` : '')}
                                            </td>
                                        </tr>
                                    `}).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `).join('');

                // Add select-all-job handlers
                document.querySelectorAll('.select-all-job').forEach(checkbox => {
                    checkbox.addEventListener('change', (e) => {
                        const jobCard = e.target.closest('.card');
                        jobCard.querySelectorAll('.entry-checkbox:not(:disabled)').forEach(cb => cb.checked = e.target.checked);
                    });
                });
            }

            document.getElementById('entries-pagination').innerHTML = `<span style="padding: 0.5rem;">Showing ${data.total_jobs} jobs with ${data.total_entries} entries</span>`;
        };

        Pages.entriesGroupedPage = loadGroupedEntries;

        // Smart reload - checks which view is active
        Pages.reloadEntries = () => {
            const groupedView = document.getElementById('entries-grouped-view');
            if (groupedView && groupedView.style.display !== 'none') {
                loadGroupedEntries();
            } else {
                loadEntries(1);
            }
        };

        // Toggle view handler
        document.getElementById('toggle-group-btn').addEventListener('click', async () => {
            isGroupedView = !isGroupedView;
            const listView = document.getElementById('entries-list-view');
            const groupedView = document.getElementById('entries-grouped-view');
            const toggleBtn = document.getElementById('toggle-group-btn');

            if (isGroupedView) {
                listView.style.display = 'none';
                groupedView.style.display = 'block';
                toggleBtn.innerHTML = '<i class="fas fa-list"></i> List View';
                await loadGroupedEntries();
            } else {
                listView.style.display = 'block';
                groupedView.style.display = 'none';
                toggleBtn.innerHTML = '<i class="fas fa-layer-group"></i> Group by Job';
                await loadEntries(1);
            }
        });

        // Event listeners - multi-select filters
        const reloadEntries = () => isGroupedView ? loadGroupedEntries() : loadEntries(1);
        App.initMultiSelect('entry-status-filter', 'All Statuses', reloadEntries);
        if (isManager) {
            App.initMultiSelect('entry-tech-filter', 'All Technicians', reloadEntries);
        }
        document.getElementById('entry-from-date').addEventListener('change', reloadEntries);
        document.getElementById('entry-to-date').addEventListener('change', reloadEntries);
        document.getElementById('entry-job-search').addEventListener('input', debounce(reloadEntries, 300));
        App.initDateNav('entry', 'entry-from-date', 'entry-to-date', reloadEntries);

        // Sortable columns
        document.querySelectorAll('#entries-list-view .sortable').forEach(th => {
            th.addEventListener('click', () => {
                const sortBy = th.dataset.sort;
                if (currentSort.by === sortBy) {
                    currentSort.order = currentSort.order === 'desc' ? 'asc' : 'desc';
                } else {
                    currentSort.by = sortBy;
                    currentSort.order = 'desc';
                }
                loadEntries(1);
            });
        });
        document.getElementById('new-entry-btn').addEventListener('click', () => Pages.editEntry(null));

        // Select all checkbox
        document.getElementById('select-all-entries').addEventListener('change', (e) => {
            document.querySelectorAll('.entry-checkbox:not(:disabled)').forEach(cb => cb.checked = e.target.checked);
        });

        // Bulk submit handler
        document.getElementById('bulk-submit-btn').addEventListener('click', async () => {
            const selected = [...document.querySelectorAll('.entry-checkbox:checked')]
                .filter(cb => cb.dataset.status === 'draft')
                .map(cb => parseInt(cb.value));
            if (selected.length === 0) {
                App.showAlert('No draft entries selected');
                return;
            }
            try {
                await API.timeEntries.bulkSubmit(selected);
                App.showAlert(`Submitted ${selected.length} entries`, 'success');
                loadEntries(1);
            } catch (error) {
                App.showAlert(error.message);
            }
        });

        if (isManager) {
            document.getElementById('bulk-verify-btn').addEventListener('click', async () => {
                const selected = [...document.querySelectorAll('.entry-checkbox:checked')]
                    .filter(cb => cb.dataset.status === 'submitted')
                    .map(cb => parseInt(cb.value));
                if (selected.length === 0) {
                    App.showAlert('No submitted entries selected');
                    return;
                }
                try {
                    await API.timeEntries.bulkVerify(selected);
                    App.showAlert(`Verified ${selected.length} entries`, 'success');
                    loadEntries(1);
                } catch (error) {
                    App.showAlert(error.message);
                }
            });
        }

        await loadEntries(1);
    },

    // Edit/create time entry
    async editEntry(entryId) {
        let entry = {};
        if (entryId) {
            const data = await API.timeEntries.get(entryId);
            entry = data.time_entry;
        }

        const isManager = ['admin', 'manager'].includes(App.user.role);

        // Get jobs for dropdown (exclude cancelled and completed, but keep current job if editing)
        const jobsData = await API.jobs.list({ per_page: 200 });
        const openStatuses = ['pending', 'assigned', 'in_progress'];
        const getJobOptions = (includeCompleted = false) => jobsData.jobs
            .filter(j => j.job_status !== 'cancelled' &&
                (includeCompleted || openStatuses.includes(j.job_status) || j.job_id == entry.job_id))
            .map(j => {
                const statusTag = j.job_status === 'completed' ? ' [Completed]' : '';
                return `<option value="${j.job_id}" ${j.job_id == entry.job_id ? 'selected' : ''}>${j.ticket_number || j.job_id} - ${j.description.slice(0, 30)}${statusTag}</option>`;
            }).join('');

        // Technician field - only show for managers/admins (optional for imported entries)
        const techField = isManager ? `
            <div class="form-group">
                <label>Technician</label>
                <select class="form-control" name="tech_id">
                    <option value="">Unassigned</option>
                    ${App.getTechnicianOptions(entry.tech_id)}
                </select>
                <small class="text-muted">Leave unassigned for imported entries that need review</small>
            </div>
        ` : '';

        const body = `
            <form id="entry-form">
                <div class="form-group">
                    <label>Job *</label>
                    <select class="form-control" name="job_id" id="entry-job-select" required>
                        <option value="">Select Job</option>
                        ${getJobOptions(false)}
                    </select>
                    <label style="margin-top: 0.5rem; font-weight: normal; cursor: pointer;">
                        <input type="checkbox" id="show-completed-jobs" style="margin-right: 0.5rem;">
                        Show completed jobs
                    </label>
                </div>
                ${techField}
                <div class="form-group">
                    <label>Date Worked *</label>
                    <input type="date" class="form-control" name="date_worked" value="${entry.date_worked || new Date().toISOString().split('T')[0]}" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Time In</label>
                        <input type="time" class="form-control" name="time_in" value="${entry.time_in ? entry.time_in.slice(0, 5) : ''}">
                    </div>
                    <div class="form-group">
                        <label>Time Out</label>
                        <input type="time" class="form-control" name="time_out" value="${entry.time_out ? entry.time_out.slice(0, 5) : ''}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Hours (auto-calculated if times provided)</label>
                    <input type="number" step="0.25" class="form-control" name="hours_worked" value="${entry.hours_worked || ''}">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Mileage</label>
                        <input type="number" step="0.1" class="form-control" name="mileage" value="${entry.mileage || ''}">
                    </div>
                    <div class="form-group">
                        <label>Per Diem</label>
                        <input type="number" step="0.01" class="form-control" name="per_diem" value="${entry.per_diem || ''}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Personal Expenses</label>
                    <input type="number" step="0.01" class="form-control" name="personal_expenses" value="${entry.personal_expenses || ''}">
                </div>
                <div class="form-group">
                    <label>Notes</label>
                    <textarea class="form-control" name="notes" rows="3">${entry.notes || ''}</textarea>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveEntry(${entryId})">Save</button>
        `;

        App.showModal(entryId ? 'Edit Time Entry' : 'New Time Entry', body, footer);

        // Add event listener for show completed jobs checkbox
        document.getElementById('show-completed-jobs').addEventListener('change', (e) => {
            const select = document.getElementById('entry-job-select');
            const currentValue = select.value;
            select.innerHTML = '<option value="">Select Job</option>' + getJobOptions(e.target.checked);
            if (currentValue) select.value = currentValue;
        });

        // Auto-calculate hours when time fields change
        const calculateHours = () => {
            const timeIn = document.querySelector('input[name="time_in"]').value;
            const timeOut = document.querySelector('input[name="time_out"]').value;
            if (timeIn && timeOut) {
                const [inH, inM] = timeIn.split(':').map(Number);
                const [outH, outM] = timeOut.split(':').map(Number);
                let minutes = (outH * 60 + outM) - (inH * 60 + inM);
                if (minutes < 0) minutes += 24 * 60; // Handle overnight
                const hours = (minutes / 60).toFixed(2);
                document.querySelector('input[name="hours_worked"]').value = hours;
            }
        };
        document.querySelector('input[name="time_in"]').addEventListener('change', calculateHours);
        document.querySelector('input[name="time_out"]').addEventListener('change', calculateHours);
    },

    // Save time entry
    async saveEntry(entryId) {
        const form = document.getElementById('entry-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        try {
            if (entryId) {
                await API.timeEntries.update(entryId, data);
                App.showAlert('Time entry updated', 'success');
            } else {
                await API.timeEntries.create(data);
                App.showAlert('Time entry created', 'success');
            }
            App.hideModal();
            Pages.entriesPage(1);
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Submit entry
    async submitEntry(entryId) {
        try {
            await API.timeEntries.submit(entryId);
            App.showAlert('Entry submitted', 'success');
            Pages.entriesPage(1);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Verify entry
    async verifyEntry(entryId) {
        try {
            await API.timeEntries.verify(entryId);
            App.showAlert('Entry verified', 'success');
            Pages.entriesPage(1);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Reject entry
    async rejectEntry(entryId) {
        const reason = prompt('Rejection reason:');
        if (reason === null) return;

        try {
            await API.timeEntries.reject(entryId, reason);
            App.showAlert('Entry rejected', 'success');
            Pages.entriesPage(1);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Delete entry
    async deleteEntry(entryId) {
        if (!confirm('Are you sure you want to delete this time entry? This cannot be undone.')) {
            return;
        }

        try {
            await API.timeEntries.delete(entryId);
            App.showAlert('Entry deleted', 'success');
            if (Pages.reloadEntries) {
                Pages.reloadEntries();
            } else {
                Pages.entriesPage(1);
            }
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Assign technician to unassigned entry
    async assignTechnician(entryId) {
        const data = await API.timeEntries.get(entryId);
        const entry = data.time_entry;

        const body = `
            <form id="assign-tech-form">
                <p>Assign a technician to this time entry:</p>
                <div class="form-group">
                    <label>Job</label>
                    <input type="text" class="form-control" value="Job #${entry.job_id}" readonly>
                </div>
                <div class="form-group">
                    <label>Date Worked</label>
                    <input type="text" class="form-control" value="${App.formatDate(entry.date_worked)}" readonly>
                </div>
                <div class="form-group">
                    <label>Hours</label>
                    <input type="text" class="form-control" value="${entry.hours_worked || '-'}" readonly>
                </div>
                <div class="form-group">
                    <label>Technician *</label>
                    <select class="form-control" name="tech_id" required>
                        <option value="">Select Technician</option>
                        ${App.getTechnicianOptions()}
                    </select>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveAssignment(${entryId})">Assign</button>
        `;

        App.showModal('Assign Technician', body, footer);
    },

    // Save technician assignment
    async saveAssignment(entryId) {
        const form = document.getElementById('assign-tech-form');
        const techId = form.querySelector('[name="tech_id"]').value;

        if (!techId) {
            App.showFormError('Please select a technician');
            return;
        }

        try {
            await API.timeEntries.update(entryId, { tech_id: parseInt(techId) });
            App.showAlert('Technician assigned successfully', 'success');
            App.hideModal();
            Pages.entriesPage(1);
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Copy entry (create new entry based on existing one)
    async copyEntry(entryId) {
        const data = await API.timeEntries.get(entryId);
        const entry = data.time_entry;

        // Get jobs for dropdown (exclude cancelled and completed, but keep current job if copying)
        const jobsData = await API.jobs.list({ per_page: 200 });
        const openStatuses = ['pending', 'assigned', 'in_progress'];
        const getJobOptions = (includeCompleted = false) => jobsData.jobs
            .filter(j => j.job_status !== 'cancelled' &&
                (includeCompleted || openStatuses.includes(j.job_status) || j.job_id == entry.job_id))
            .map(j => {
                const statusTag = j.job_status === 'completed' ? ' [Completed]' : '';
                return `<option value="${j.job_id}" ${j.job_id == entry.job_id ? 'selected' : ''}>${j.ticket_number || j.job_id} - ${j.description.slice(0, 30)}${statusTag}</option>`;
            }).join('');

        const body = `
            <form id="copy-entry-form">
                <p class="text-muted">Creating a copy of this time entry. Select a different technician if needed (e.g., for multiple techs on the same job).</p>
                <div class="form-group">
                    <label>Job *</label>
                    <select class="form-control" name="job_id" id="copy-job-select" required>
                        ${getJobOptions(false)}
                    </select>
                    <label style="margin-top: 0.5rem; font-weight: normal; cursor: pointer;">
                        <input type="checkbox" id="copy-show-completed-jobs" style="margin-right: 0.5rem;">
                        Show completed jobs
                    </label>
                </div>
                <div class="form-group">
                    <label>Technician *</label>
                    <select class="form-control" name="tech_id" required>
                        ${App.getTechnicianOptions(entry.tech_id)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Date Worked *</label>
                    <input type="date" class="form-control" name="date_worked" value="${entry.date_worked}" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Time In</label>
                        <input type="time" class="form-control" name="time_in" value="${entry.time_in ? entry.time_in.slice(0, 5) : ''}">
                    </div>
                    <div class="form-group">
                        <label>Time Out</label>
                        <input type="time" class="form-control" name="time_out" value="${entry.time_out ? entry.time_out.slice(0, 5) : ''}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Hours</label>
                    <input type="number" step="0.25" class="form-control" name="hours_worked" value="${entry.hours_worked || ''}">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Mileage</label>
                        <input type="number" step="0.1" class="form-control" name="mileage" value="${entry.mileage || ''}">
                    </div>
                    <div class="form-group">
                        <label>Per Diem</label>
                        <input type="number" step="0.01" class="form-control" name="per_diem" value="${entry.per_diem || ''}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Personal Expenses</label>
                    <input type="number" step="0.01" class="form-control" name="personal_expenses" value="${entry.personal_expenses || ''}">
                </div>
                <div class="form-group">
                    <label>Notes</label>
                    <textarea class="form-control" name="notes" rows="3">${entry.notes || ''}</textarea>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveCopiedEntry()">Create Copy</button>
        `;

        App.showModal('Copy Time Entry', body, footer);

        // Add event listener for show completed jobs checkbox
        document.getElementById('copy-show-completed-jobs').addEventListener('change', (e) => {
            const select = document.getElementById('copy-job-select');
            const currentValue = select.value;
            select.innerHTML = getJobOptions(e.target.checked);
            if (currentValue) select.value = currentValue;
        });
    },

    // Save copied entry
    async saveCopiedEntry() {
        const form = document.getElementById('copy-entry-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        try {
            await API.timeEntries.create(data);
            App.showAlert('Time entry copied successfully', 'success');
            App.hideModal();
            if (Pages.reloadEntries) {
                Pages.reloadEntries();
            } else {
                Pages.entriesPage(1);
            }
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Reports page
    async reports(container) {
        const html = `
            <div class="stats-grid">
                <div class="stat-card" style="cursor: pointer" onclick="Pages.showPayrollReport()">
                    <div class="stat-label">Payout Report (Legacy)</div>
                    <div class="stat-value"><i class="fas fa-file-invoice-dollar"></i></div>
                </div>
                <div class="stat-card" style="cursor: pointer" onclick="Pages.showBillingReport()">
                    <div class="stat-label">Income / Expense</div>
                    <div class="stat-value"><i class="fas fa-receipt"></i></div>
                </div>
                <div class="stat-card" style="cursor: pointer" onclick="Pages.showPlatformReport()">
                    <div class="stat-label">Platform Summary</div>
                    <div class="stat-value"><i class="fas fa-chart-pie"></i></div>
                </div>
                ${App.user.role === 'admin' ? `
                <div class="stat-card" style="cursor: pointer" onclick="Pages.showAuditLog()">
                    <div class="stat-label">Audit Log</div>
                    <div class="stat-value"><i class="fas fa-history"></i></div>
                </div>
                ` : ''}
            </div>
            <div id="report-content"></div>
        `;

        container.innerHTML = html;
    },

    // Show payroll report
    async showPayrollReport() {
        const content = document.getElementById('report-content');
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];

        // Fetch recent pay periods for quick-fill
        let periodButtons = '';
        try {
            const periodsData = await API.reports.payPeriods({ per_page: 4 });
            if (periodsData.pay_periods && periodsData.pay_periods.length > 0) {
                periodButtons = periodsData.pay_periods.slice(0, 2).map(p =>
                    `<button class="btn btn-secondary btn-sm" onclick="Pages.fillPayPeriod('${p.start_date}', '${p.end_date}')">${p.period_name}</button>`
                ).join('');
                periodButtons = `<span style="margin-right: 0.5rem;">Quick fill:</span>${periodButtons}`;
            }
        } catch (e) {
            console.log('Could not load pay periods:', e);
        }

        content.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Payroll Report</h3>
                    <div class="no-print" id="payroll-export-btns" style="display: none;">
                        <button class="btn btn-secondary btn-sm" onclick="Pages.printPayrollReport()">
                            <i class="fas fa-print"></i> Print
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.exportPayrollCSV()">
                            <i class="fas fa-download"></i> Export CSV
                        </button>
                    </div>
                </div>
                <div class="filters no-print">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        ${periodButtons}
                        <a href="#pay-periods" style="margin-left: auto; font-size: 0.9rem;"><i class="fas fa-cog"></i> Manage Pay Periods</a>
                    </div>
                    <input type="date" class="form-control" id="payroll-from" value="${firstDay}">
                    <input type="date" class="form-control" id="payroll-to" value="${lastDay}">
                    <div class="multi-select" id="payroll-tech-filter">
                        <div class="multi-select-display" onclick="App.toggleMultiSelect('payroll-tech-filter')">
                            <span class="multi-select-text">All Technicians</span>
                            <i class="fas fa-chevron-down"></i>
                        </div>
                        <div class="multi-select-dropdown">
                            ${App.getTechnicianCheckboxes()}
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="Pages.loadPayrollReport()">Generate</button>
                </div>
                <div id="payroll-results"></div>
            </div>
        `;

        App.initMultiSelect('payroll-tech-filter', 'All Technicians');
    },

    fillPayPeriod(startDate, endDate) {
        document.getElementById('payroll-from').value = startDate;
        document.getElementById('payroll-to').value = endDate;
        Pages.loadPayrollReport();
    },

    // Store last payroll data for export
    lastPayrollData: null,

    async loadPayrollReport() {
        const fromDate = document.getElementById('payroll-from').value;
        const toDate = document.getElementById('payroll-to').value;
        const techFilters = App.getMultiSelectValues('payroll-tech-filter');
        const resultsDiv = document.getElementById('payroll-results');

        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
        document.getElementById('payroll-export-btns').style.display = 'none';

        const params = { from_date: fromDate, to_date: toDate };
        if (techFilters.length > 0) {
            params.tech_id = techFilters.join(',');
        }

        try {
            const data = await API.reports.payrollDetail(params);

            // Store for export
            this.lastPayrollData = data;

            if (data.technicians.length === 0) {
                resultsDiv.innerHTML = '<p class="text-center" style="padding: 2rem;">No verified time entries found for this period.</p>';
                return;
            }

            // Show export buttons
            document.getElementById('payroll-export-btns').style.display = 'flex';
            document.getElementById('payroll-export-btns').style.gap = '0.5rem';

            let html = '';

            // Grand totals summary at top
            html += `
                <div style="background: #f8f9fa; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">
                    <h4 style="margin-bottom: 0.5rem;">Period Summary: ${fromDate} to ${toDate}</h4>
                    <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; text-align: center;">
                        <div><small>Technicians</small><br><strong>${data.technician_count}</strong></div>
                        <div><small>Total Hours</small><br><strong>${data.grand_totals.total_hours.toFixed(2)}</strong></div>
                        <div><small>Base Pay</small><br><strong>$${data.grand_totals.total_base_pay.toFixed(2)}</strong></div>
                        <div><small>Mileage</small><br><strong>$${data.grand_totals.total_mileage_pay.toFixed(2)}</strong></div>
                        <div><small>Per Diem</small><br><strong>$${data.grand_totals.total_per_diem.toFixed(2)}</strong></div>
                        <div><small>Total Pay</small><br><strong style="color: var(--success);">$${data.grand_totals.total_pay.toFixed(2)}</strong></div>
                    </div>
                </div>
            `;

            // Each technician gets their own section
            for (const tech of data.technicians) {
                html += `
                    <div class="card" style="margin-bottom: 1rem;">
                        <div class="card-header" style="background: #f8f9fa;">
                            <h3 class="card-title">${tech.tech_name} <small style="font-weight: normal;">(Min Pay: $${tech.min_pay.toFixed(2)}/hr)</small></h3>
                            <span style="font-size: 1.25rem; font-weight: bold; color: var(--success);">$${tech.totals.total_pay.toFixed(2)}</span>
                        </div>
                        <div class="table-container">
                            <table style="font-size: 0.85rem;">
                                <thead>
                                    <tr>
                                        <th>Date(s)</th>
                                        <th>Job</th>
                                        <th>Link</th>
                                        <th>Hours</th>
                                        <th>Rate</th>
                                        <th>Base Pay</th>
                                        <th>Mileage</th>
                                        <th>Per Diem</th>
                                        <th>Expenses</th>
                                        <th>Total Pay</th>
                                        <th>Profit</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${tech.jobs.map(job => {
                                        const profitColor = job.tech_profit_share >= 0 ? 'var(--success)' : 'var(--danger)';
                                        const ratioDisplay = job.hours_ratio < 1 ? ` <small>(${(job.hours_ratio * 100).toFixed(0)}%)</small>` : '';
                                        return `
                                        <tr>
                                            <td style="white-space: nowrap;">${job.date_display || '-'}</td>
                                            <td>
                                                <a href="#" onclick="Pages.viewJob(${job.job_id}); return false;" style="color: var(--primary); text-decoration: underline;">
                                                    ${job.ticket_number || 'Job #' + job.job_id}
                                                </a>
                                                <small style="display: block; color: var(--gray-500);">${job.description.slice(0, 30)}${job.description.length > 30 ? '...' : ''}</small>
                                            </td>
                                            <td>${job.external_url ? `<a href="${job.external_url}" target="_blank" title="Open in platform"><i class="fas fa-external-link-alt"></i></a>` : '-'}</td>
                                            <td>${job.hours}</td>
                                            <td>$${job.effective_rate.toFixed(2)} ${job.using_minimum ? '<span class="badge badge-info">MIN</span>' : ''}</td>
                                            <td>$${job.base_pay.toFixed(2)}</td>
                                            <td>$${job.mileage_pay.toFixed(2)} <small>(${job.mileage} mi)</small></td>
                                            <td>$${job.per_diem.toFixed(2)}</td>
                                            <td>$${job.personal_expenses.toFixed(2)}</td>
                                            <td><strong>$${job.total_pay.toFixed(2)}</strong></td>
                                            <td style="color: ${profitColor}; font-weight: bold;">$${job.tech_profit_share.toFixed(2)}${ratioDisplay}</td>
                                        </tr>
                                    `}).join('')}
                                </tbody>
                                <tfoot>
                                    <tr style="background: #f8f9fa;">
                                        <th colspan="3">Totals</th>
                                        <th>${tech.totals.total_hours.toFixed(2)}</th>
                                        <th>${tech.totals.total_hours > 0 ? '$' + (tech.totals.total_base_pay / tech.totals.total_hours).toFixed(2) + ' avg' : '-'}</th>
                                        <th>$${tech.totals.total_base_pay.toFixed(2)}</th>
                                        <th>$${tech.totals.total_mileage_pay.toFixed(2)}</th>
                                        <th>$${tech.totals.total_per_diem.toFixed(2)}</th>
                                        <th>$${tech.totals.total_personal_expenses.toFixed(2)}</th>
                                        <th><strong>$${tech.totals.total_pay.toFixed(2)}</strong></th>
                                        <th style="color: ${tech.totals.total_profit_share >= 0 ? 'var(--success)' : 'var(--danger)'}; font-weight: bold;">$${tech.totals.total_profit_share.toFixed(2)}</th>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>
                `;
            }

            resultsDiv.innerHTML = html;
        } catch (error) {
            App.showAlert(error.message);
            resultsDiv.innerHTML = `<p class="text-center text-danger">${error.message}</p>`;
        }
    },

    // Print payroll report
    printPayrollReport() {
        window.print();
    },

    // Export payroll to CSV
    exportPayrollCSV() {
        const data = this.lastPayrollData;
        if (!data) {
            App.showAlert('No data to export');
            return;
        }

        // Build CSV content
        let csv = [];

        // Header
        csv.push(['Payroll Report']);
        csv.push([`Period: ${data.from_date} to ${data.to_date}`]);
        csv.push([`Generated: ${data.generated_at}`]);
        csv.push([]);

        // Grand totals
        csv.push(['SUMMARY']);
        csv.push(['Technicians', 'Total Hours', 'Base Pay', 'Mileage Pay', 'Per Diem', 'Personal Expenses', 'Total Pay']);
        csv.push([
            data.technician_count,
            data.grand_totals.total_hours.toFixed(2),
            data.grand_totals.total_base_pay.toFixed(2),
            data.grand_totals.total_mileage_pay.toFixed(2),
            data.grand_totals.total_per_diem.toFixed(2),
            data.grand_totals.total_personal_expenses.toFixed(2),
            data.grand_totals.total_pay.toFixed(2)
        ]);
        csv.push([]);

        // Each technician
        for (const tech of data.technicians) {
            csv.push([]);
            csv.push([`TECHNICIAN: ${tech.tech_name}`]);
            csv.push([`Min Pay: $${tech.min_pay.toFixed(2)}/hr`]);
            csv.push(['Date(s)', 'Ticket', 'Description', 'Hours', 'Rate', 'Using Min', 'Base Pay', 'Mileage', 'Mileage Pay', 'Per Diem', 'Expenses', 'Total Pay', 'Profit Share', 'Hours %']);

            for (const job of tech.jobs) {
                csv.push([
                    job.date_display || '',
                    job.ticket_number || `Job #${job.job_id}`,
                    `"${job.description.replace(/"/g, '""')}"`,
                    job.hours,
                    job.effective_rate.toFixed(2),
                    job.using_minimum ? 'Yes' : 'No',
                    job.base_pay.toFixed(2),
                    job.mileage,
                    job.mileage_pay.toFixed(2),
                    job.per_diem.toFixed(2),
                    job.personal_expenses.toFixed(2),
                    job.total_pay.toFixed(2),
                    job.tech_profit_share.toFixed(2),
                    (job.hours_ratio * 100).toFixed(0) + '%'
                ]);
            }

            // Tech totals
            csv.push([
                'TOTALS', '', '',
                tech.totals.total_hours.toFixed(2),
                '', '',
                tech.totals.total_base_pay.toFixed(2),
                '',
                tech.totals.total_mileage_pay.toFixed(2),
                tech.totals.total_per_diem.toFixed(2),
                tech.totals.total_personal_expenses.toFixed(2),
                tech.totals.total_pay.toFixed(2),
                tech.totals.total_profit_share.toFixed(2),
                ''
            ]);
        }

        // Convert to CSV string
        const csvContent = csv.map(row => row.join(',')).join('\n');

        // Download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const filename = `payroll_${data.from_date}_to_${data.to_date}.csv`;
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
    },

    // Show income/expense report
    async showBillingReport() {
        const content = document.getElementById('report-content');
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];

        content.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Income / Expense Report</h3>
                    <div class="no-print" id="income-export-btns" style="display: none;">
                        <button class="btn btn-secondary btn-sm" onclick="Pages.printIncomeReport()">
                            <i class="fas fa-print"></i> Print
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.exportIncomeCSV()">
                            <i class="fas fa-download"></i> Export CSV
                        </button>
                    </div>
                </div>
                <div class="filters no-print">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <span>Quick:</span>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.setIncomeDates('thisMonth')">This Month</button>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.setIncomeDates('lastMonth')">Last Month</button>
                    </div>
                    <input type="date" class="form-control" id="income-from" value="${firstDay}">
                    <input type="date" class="form-control" id="income-to" value="${lastDay}">
                    <button class="btn btn-primary" onclick="Pages.loadIncomeReport()">Generate</button>
                </div>
                <div id="income-results"></div>
            </div>
        `;
    },

    setIncomeDates(period) {
        const today = new Date();
        let firstDay, lastDay;
        if (period === 'thisMonth') {
            firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        } else if (period === 'lastMonth') {
            firstDay = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            lastDay = new Date(today.getFullYear(), today.getMonth(), 0);
        }
        document.getElementById('income-from').value = firstDay.toISOString().split('T')[0];
        document.getElementById('income-to').value = lastDay.toISOString().split('T')[0];
        this.loadIncomeReport();
    },

    lastIncomeData: null,

    async loadIncomeReport() {
        const fromDate = document.getElementById('income-from').value;
        const toDate = document.getElementById('income-to').value;
        const resultsDiv = document.getElementById('income-results');

        if (!fromDate || !toDate) {
            App.showAlert('Please select date range');
            return;
        }

        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
        document.getElementById('income-export-btns').style.display = 'none';

        try {
            const data = await API.reports.incomeExpense({ from_date: fromDate, to_date: toDate });
            this.lastIncomeData = data;

            if (data.jobs.length === 0) {
                resultsDiv.innerHTML = '<p class="text-center" style="padding: 2rem;">No jobs found for this period.</p>';
                return;
            }

            document.getElementById('income-export-btns').style.display = 'flex';
            document.getElementById('income-export-btns').style.gap = '0.5rem';

            const profitClass = data.totals.net_profit >= 0 ? 'text-success' : 'text-danger';

            // Generate all dates in range
            const allDates = [];
            const startDate = new Date(fromDate);
            const endDate = new Date(toDate);
            for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
                allDates.push(d.toISOString().split('T')[0]);
            }

            // Aggregate data by date for chart (exclude projected jobs)
            // For multi-day jobs, distribute income/expenses/profit proportionally
            // across time entry dates based on hours worked each day
            const dailyData = {};
            allDates.forEach(date => {
                dailyData[date] = { income: 0, expenses: 0, profit: 0, projected: 0 };
            });
            data.jobs.forEach(job => {
                const entryHours = job.entry_hours_by_date || {};
                const entryDates = Object.keys(entryHours);
                const totalEntryHours = entryDates.reduce((sum, d) => sum + entryHours[d], 0);

                if (job.is_projected) {
                    const date = job.job_date;
                    if (date && dailyData[date]) {
                        dailyData[date].projected += job.billing;
                    }
                } else if (totalEntryHours > 0 && entryDates.length > 1) {
                    // Multi-day: distribute proportionally by hours
                    entryDates.forEach(date => {
                        if (dailyData[date]) {
                            const ratio = entryHours[date] / totalEntryHours;
                            dailyData[date].income += job.billing * ratio;
                            dailyData[date].expenses += (job.job_expenses + job.commissions + job.tech_pay) * ratio;
                            dailyData[date].profit += job.net_profit * ratio;
                        }
                    });
                } else {
                    // Single day or no entries: use job_date
                    const date = job.job_date;
                    if (date && dailyData[date]) {
                        dailyData[date].income += job.billing;
                        dailyData[date].expenses += job.job_expenses + job.commissions + job.tech_pay;
                        dailyData[date].profit += job.net_profit;
                    }
                }
            });

            // Prepare chart data
            const chartLabels = allDates.map(d => App.formatDate(d));
            const incomeData = allDates.map(d => dailyData[d].income);
            const expenseData = allDates.map(d => dailyData[d].expenses);
            const profitData = allDates.map(d => dailyData[d].profit);

            const hasProjected = data.projected && data.projected.job_count > 0;

            let html = `
                <div style="background: #f8f9fa; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">
                    <h4 style="margin-bottom: 0.5rem;">Period Summary: ${fromDate} to ${toDate}</h4>
                    <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; text-align: center;">
                        <div><small>Jobs</small><br><strong>${data.job_count}</strong>${hasProjected ? `<br><small style="color: var(--warning);">(+${data.projected.job_count} projected)</small>` : ''}</div>
                        <div><small>Income</small><br><strong style="color: var(--success);">$${data.totals.billing.toFixed(2)}</strong>${hasProjected ? `<br><small style="color: var(--warning);">(+$${data.projected.billing.toFixed(2)} projected)</small>` : ''}</div>
                        <div><small>Job Expenses</small><br><strong>$${data.totals.job_expenses.toFixed(2)}</strong></div>
                        <div><small>Commissions</small><br><strong>$${data.totals.commissions.toFixed(2)}</strong></div>
                        <div><small>Tech Pay</small><br><strong>$${data.totals.tech_pay.toFixed(2)}</strong></div>
                        <div><small>Net Profit</small><br><strong class="${profitClass}">$${data.totals.net_profit.toFixed(2)}</strong><br><small>(${data.profit_margin.toFixed(1)}%)</small></div>
                    </div>
                </div>

                <div style="background: white; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; height: 300px; position: relative;">
                    <canvas id="income-chart"></canvas>
                </div>

                <div class="table-container">
                    <table style="font-size: 0.85rem;">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Job</th>
                                <th>Platform</th>
                                <th style="text-align: right;">Income</th>
                                <th style="text-align: right;">Expenses</th>
                                <th style="text-align: right;">Commissions</th>
                                <th style="text-align: right;">Tech Pay</th>
                                <th style="text-align: right;">Net Profit</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.jobs.map(job => {
                                const profitColor = job.net_profit >= 0 ? 'var(--success)' : 'var(--danger)';
                                const rowStyle = job.is_projected ? 'background: #fff8e6; opacity: 0.85;' : '';
                                const projectedBadge = job.is_projected ? '<span style="background: var(--warning); color: white; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.7rem; margin-left: 0.3rem;">PROJECTED</span>' : '';
                                return `
                                <tr style="${rowStyle}">
                                    <td>${job.job_date ? App.formatDate(job.job_date) : '-'}${projectedBadge}</td>
                                    <td>
                                        <a href="#" onclick="Pages.viewJob(${job.job_id}); return false;" style="color: var(--primary);">
                                            ${job.ticket_number || 'Job #' + job.job_id}
                                        </a>
                                        <small style="display: block; color: var(--gray-500);">${job.description.slice(0, 30)}${job.description.length > 30 ? '...' : ''}</small>
                                    </td>
                                    <td>${job.platform || '-'}</td>
                                    <td style="text-align: right; color: ${job.is_projected ? 'var(--warning)' : 'var(--success)'};">$${job.billing.toFixed(2)}</td>
                                    <td style="text-align: right;">${job.is_projected ? '-' : '$' + job.job_expenses.toFixed(2)}</td>
                                    <td style="text-align: right;">${job.is_projected ? '-' : '$' + job.commissions.toFixed(2)}</td>
                                    <td style="text-align: right;">${job.is_projected ? '-' : '$' + job.tech_pay.toFixed(2)}</td>
                                    <td style="text-align: right; color: ${job.is_projected ? 'var(--gray-400)' : profitColor}; font-weight: bold;">${job.is_projected ? '-' : '$' + job.net_profit.toFixed(2)}</td>
                                </tr>
                            `}).join('')}
                        </tbody>
                        <tfoot>
                            <tr style="background: #f8f9fa;">
                                <th colspan="3">Totals (${data.job_count} jobs)</th>
                                <th style="text-align: right; color: var(--success);">$${data.totals.billing.toFixed(2)}</th>
                                <th style="text-align: right;">$${data.totals.job_expenses.toFixed(2)}</th>
                                <th style="text-align: right;">$${data.totals.commissions.toFixed(2)}</th>
                                <th style="text-align: right;">$${data.totals.tech_pay.toFixed(2)}</th>
                                <th style="text-align: right; font-weight: bold;" class="${profitClass}">$${data.totals.net_profit.toFixed(2)}</th>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;

            resultsDiv.innerHTML = html;

            // Create the chart (if Chart.js is loaded)
            if (typeof Chart !== 'undefined') {
                const ctx = document.getElementById('income-chart').getContext('2d');
                if (window.incomeChart) {
                    window.incomeChart.destroy();
                }
                window.incomeChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: chartLabels,
                    datasets: [
                        {
                            label: 'Income',
                            data: incomeData,
                            backgroundColor: 'rgba(16, 185, 129, 0.7)',
                            borderColor: 'rgb(16, 185, 129)',
                            borderWidth: 1
                        },
                        {
                            label: 'Expenses',
                            data: expenseData,
                            backgroundColor: 'rgba(239, 68, 68, 0.7)',
                            borderColor: 'rgb(239, 68, 68)',
                            borderWidth: 1
                        },
                        {
                            label: 'Profit',
                            data: profitData,
                            type: 'line',
                            borderColor: 'rgb(37, 99, 235)',
                            backgroundColor: 'rgba(37, 99, 235, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': $' + context.raw.toFixed(2);
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value;
                                }
                            }
                        }
                    }
                }
                });
            } else {
                // Chart.js not loaded - hide chart container
                document.getElementById('income-chart').parentElement.style.display = 'none';
            }
        } catch (error) {
            App.showAlert(error.message);
            resultsDiv.innerHTML = `<p class="text-center text-danger">${error.message}</p>`;
        }
    },

    printIncomeReport() {
        window.print();
    },

    exportIncomeCSV() {
        const data = this.lastIncomeData;
        if (!data) {
            App.showAlert('No data to export');
            return;
        }

        let csv = [];
        csv.push(['Income/Expense Report']);
        csv.push([`Period: ${data.from_date} to ${data.to_date}`]);
        csv.push([]);
        csv.push(['SUMMARY']);
        csv.push(['Jobs', 'Income', 'Job Expenses', 'Commissions', 'Tech Pay', 'Total Expenses', 'Net Profit', 'Margin %']);
        csv.push([
            data.job_count,
            data.totals.billing.toFixed(2),
            data.totals.job_expenses.toFixed(2),
            data.totals.commissions.toFixed(2),
            data.totals.tech_pay.toFixed(2),
            data.totals.total_expenses.toFixed(2),
            data.totals.net_profit.toFixed(2),
            data.profit_margin.toFixed(1)
        ]);
        csv.push([]);
        csv.push(['DETAILS']);
        csv.push(['Date', 'Ticket', 'Description', 'Platform', 'Income', 'Expenses', 'Commissions', 'Tech Pay', 'Net Profit']);

        for (const job of data.jobs) {
            csv.push([
                job.job_date || '',
                job.ticket_number || `Job #${job.job_id}`,
                `"${job.description.replace(/"/g, '""')}"`,
                job.platform || '',
                job.billing.toFixed(2),
                job.job_expenses.toFixed(2),
                job.commissions.toFixed(2),
                job.tech_pay.toFixed(2),
                job.net_profit.toFixed(2)
            ]);
        }

        const csvContent = csv.map(row => row.join(',')).join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `income_expense_${data.from_date}_to_${data.to_date}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    },

    // Show platform report
    async showPlatformReport() {
        const content = document.getElementById('report-content');
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];

        content.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Platform Summary</h3>
                </div>
                <div class="filters">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <span>Quick:</span>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.setPlatformDates('thisMonth')">This Month</button>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.setPlatformDates('lastMonth')">Last Month</button>
                        <button class="btn btn-secondary btn-sm" onclick="Pages.loadPlatformReport(true)">All Time</button>
                    </div>
                    <input type="date" class="form-control" id="platform-from" value="${firstDay}">
                    <input type="date" class="form-control" id="platform-to" value="${lastDay}">
                    <button class="btn btn-primary" onclick="Pages.loadPlatformReport()">Generate</button>
                </div>
                <div id="platform-results"></div>
            </div>
        `;

        // Auto-load with current month
        await this.loadPlatformReport();
    },

    setPlatformDates(period) {
        const today = new Date();
        let firstDay, lastDay;
        if (period === 'thisMonth') {
            firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        } else if (period === 'lastMonth') {
            firstDay = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            lastDay = new Date(today.getFullYear(), today.getMonth(), 0);
        }
        document.getElementById('platform-from').value = firstDay.toISOString().split('T')[0];
        document.getElementById('platform-to').value = lastDay.toISOString().split('T')[0];
        this.loadPlatformReport();
    },

    async loadPlatformReport(allTime = false) {
        const resultsDiv = document.getElementById('platform-results');
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';

        const params = {};
        if (!allTime) {
            params.from_date = document.getElementById('platform-from').value;
            params.to_date = document.getElementById('platform-to').value;
        }

        try {
            const data = await API.reports.platformSummary(params);

            const dateRange = data.from_date && data.to_date
                ? `${App.formatDate(data.from_date)} - ${App.formatDate(data.to_date)}`
                : 'All Time';

            // Calculate totals
            const totals = data.data.reduce((acc, row) => ({
                jobs: acc.jobs + row.job_count,
                billing: acc.billing + row.total_billing,
                hours: acc.hours + row.total_hours
            }), { jobs: 0, billing: 0, hours: 0 });

            let html = `
                <p style="margin: 1rem 0; color: var(--gray-500);">Showing: ${dateRange}</p>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Platform</th>
                                <th>Jobs</th>
                                <th>Total Billing</th>
                                <th>Total Hours</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.data.map(row => `
                                <tr>
                                    <td>${row.name}</td>
                                    <td>${row.job_count}</td>
                                    <td>$${row.total_billing.toFixed(2)}</td>
                                    <td>${row.total_hours.toFixed(2)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                        <tfoot>
                            <tr style="background: #f8f9fa; font-weight: bold;">
                                <td>Total</td>
                                <td>${totals.jobs}</td>
                                <td>$${totals.billing.toFixed(2)}</td>
                                <td>${totals.hours.toFixed(2)}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;

            resultsDiv.innerHTML = html;
        } catch (error) {
            App.showAlert(error.message);
            resultsDiv.innerHTML = `<p class="text-center text-danger">${error.message}</p>`;
        }
    },

    // Show audit log
    async showAuditLog() {
        const content = document.getElementById('report-content');

        content.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Audit Log</h3>
                </div>
                <div id="audit-results"><div class="loading"><div class="spinner"></div>Loading...</div></div>
            </div>
        `;

        try {
            const data = await API.reports.auditLog({ per_page: 50 });

            let html = `
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>User</th>
                                <th>Action</th>
                                <th>Entity</th>
                                <th>Description</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.audit_logs.map(log => `
                                <tr>
                                    <td>${new Date(log.created_at).toLocaleString()}</td>
                                    <td>${log.user_email || '-'}</td>
                                    <td>${log.action_type}</td>
                                    <td>${log.entity_type || '-'} ${log.entity_id || ''}</td>
                                    <td>${log.description || '-'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;

            document.getElementById('audit-results').innerHTML = html;
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // ===================== PAYOUT PAGE =====================

    async payout(container) {
        // Load pay periods for the selector
        let periods = [];
        try {
            const data = await API.reports.payPeriods({ per_page: 20 });
            periods = data.pay_periods || [];
        } catch (e) {
            container.innerHTML = '<div class="alert alert-error">Failed to load pay periods</div>';
            return;
        }

        // Default to most recent open or locked period
        const defaultPeriod = periods.find(p => p.status === 'locked') || periods.find(p => p.status === 'open') || periods[0];

        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Payout Management</h3>
                </div>
                <div class="card-body">
                    <div class="filters" style="margin-bottom: 1rem;">
                        <div class="form-group" style="margin: 0;">
                            <label>Pay Period</label>
                            <select id="payout-period-select" class="form-control">
                                ${periods.map(p => `<option value="${p.period_id}" ${p.period_id === (defaultPeriod?.period_id) ? 'selected' : ''}>${p.period_name} (${p.start_date} — ${p.end_date}) [${p.status}]</option>`).join('')}
                            </select>
                        </div>
                        <button class="btn btn-primary" id="payout-load-btn" style="margin-left: 0.5rem; align-self: flex-end;">Load</button>
                    </div>
                    <div id="payout-content"></div>
                </div>
            </div>
        `;

        const loadPayout = async () => {
            const periodId = document.getElementById('payout-period-select').value;
            const selectedPeriod = periods.find(p => p.period_id == periodId);
            const payoutContent = document.getElementById('payout-content');
            payoutContent.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';

            try {
                if (selectedPeriod.status === 'open') {
                    // Show live calculation with Lock button
                    const data = await API.reports.payrollDetail({
                        from_date: selectedPeriod.start_date,
                        to_date: selectedPeriod.end_date
                    });
                    Pages.renderOpenPayout(payoutContent, data, selectedPeriod, loadPayout);
                } else {
                    // Show snapshot data
                    const data = await API.payouts.list({ period_id: periodId });
                    Pages.renderLockedPayout(payoutContent, data.payouts || [], selectedPeriod, loadPayout);
                }
            } catch (e) {
                payoutContent.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
            }
        };

        document.getElementById('payout-load-btn').addEventListener('click', loadPayout);
        if (defaultPeriod) loadPayout();
    },

    renderOpenPayout(container, data, period, refreshFn) {
        if (!data.technicians || data.technicians.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No verified entries found for this period.</div>';
            return;
        }

        let html = `
            <div class="stats-grid" style="margin-bottom: 1rem;">
                <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" style="color: var(--success);">Open — Preview</div></div>
                <div class="stat-card"><div class="stat-label">Technicians</div><div class="stat-value">${data.technicians.length}</div></div>
                <div class="stat-card"><div class="stat-label">Total Hours</div><div class="stat-value">${data.grand_totals.total_hours.toFixed(2)}</div></div>
                <div class="stat-card"><div class="stat-label">Total Pay</div><div class="stat-value">$${data.grand_totals.total_pay.toFixed(2)}</div></div>
            </div>
            <div style="margin-bottom: 1rem;">
                <button class="btn btn-primary" id="lock-payouts-btn"><i class="fas fa-lock"></i> Lock Payouts</button>
            </div>
        `;

        // Per-tech cards
        data.technicians.forEach(tech => {
            html += `
                <div class="card" style="margin-bottom: 1rem;">
                    <div class="card-header">
                        <h3 class="card-title">${tech.tech_name} ${tech.worker_type ? `<span class="badge" style="font-size: 0.7rem; padding: 2px 6px;">${tech.worker_type}</span>` : ''}</h3>
                        <span>$${tech.totals.total_pay.toFixed(2)}</span>
                    </div>
                    <div class="card-body">
                        <table class="data-table">
                            <thead><tr>
                                <th>Job</th><th>Hours</th><th>Rate</th><th>Base Pay</th>
                                <th>Mileage</th><th>Per Diem</th><th>Expenses</th><th>Total</th><th>Profit</th>
                            </tr></thead>
                            <tbody>
                                ${tech.jobs.map(j => `<tr>
                                    <td>${j.ticket_number || j.description || 'Job #' + j.job_id}${j.external_url ? ` <a href="${j.external_url}" target="_blank"><i class="fas fa-external-link-alt" style="font-size: 0.7rem;"></i></a>` : ''}</td>
                                    <td>${j.hours.toFixed(2)}</td>
                                    <td>$${j.effective_rate.toFixed(2)}${j.using_minimum ? ' <i class="fas fa-exclamation-triangle" style="color: var(--warning);" title="Using minimum rate"></i>' : ''}</td>
                                    <td>$${j.base_pay.toFixed(2)}</td>
                                    <td>$${j.mileage_pay.toFixed(2)}</td>
                                    <td>$${j.per_diem.toFixed(2)}</td>
                                    <td>$${j.personal_expenses.toFixed(2)}</td>
                                    <td><strong>$${j.total_pay.toFixed(2)}</strong></td>
                                    <td>$${j.tech_profit_share.toFixed(2)}</td>
                                </tr>`).join('')}
                            </tbody>
                            <tfoot><tr>
                                <td><strong>Totals</strong></td>
                                <td><strong>${tech.totals.total_hours.toFixed(2)}</strong></td>
                                <td></td>
                                <td><strong>$${tech.totals.total_base_pay.toFixed(2)}</strong></td>
                                <td><strong>$${tech.totals.total_mileage_pay.toFixed(2)}</strong></td>
                                <td><strong>$${tech.totals.total_per_diem.toFixed(2)}</strong></td>
                                <td><strong>$${tech.totals.total_personal_expenses.toFixed(2)}</strong></td>
                                <td><strong>$${tech.totals.total_pay.toFixed(2)}</strong></td>
                                <td><strong>$${tech.totals.total_profit_share.toFixed(2)}</strong></td>
                            </tr></tfoot>
                        </table>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        document.getElementById('lock-payouts-btn').addEventListener('click', async () => {
            if (!confirm('Lock payouts for this period? This will create snapshot records.')) return;
            try {
                await API.payouts.lock({ period_id: period.period_id });
                App.showAlert('Payouts locked successfully', 'success');
                // Refresh period list to reflect status change
                window.location.hash = 'payout';
                location.reload();
            } catch (e) {
                App.showAlert('Failed to lock: ' + e.message, 'error');
            }
        });
    },

    renderLockedPayout(container, payouts, period, refreshFn) {
        if (!payouts.length) {
            container.innerHTML = '<div class="alert alert-info">No payouts found for this period.</div>';
            return;
        }

        const totalPay = payouts.reduce((s, p) => s + p.net_payout, 0);
        const totalHours = payouts.reduce((s, p) => s + p.total_hours, 0);
        const allPaid = payouts.every(p => p.status === 'paid');

        let html = `
            <div class="stats-grid" style="margin-bottom: 1rem;">
                <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" style="color: ${allPaid ? 'var(--success)' : 'var(--warning)'};">${period.status.charAt(0).toUpperCase() + period.status.slice(1)}</div></div>
                <div class="stat-card"><div class="stat-label">Technicians</div><div class="stat-value">${payouts.length}</div></div>
                <div class="stat-card"><div class="stat-label">Total Hours</div><div class="stat-value">${totalHours.toFixed(2)}</div></div>
                <div class="stat-card"><div class="stat-label">Total Net</div><div class="stat-value">$${totalPay.toFixed(2)}</div></div>
            </div>
        `;

        if (period.status === 'locked') {
            html += `<div style="margin-bottom: 1rem;">
                <button class="btn btn-success" id="pay-all-btn"><i class="fas fa-check-double"></i> Mark All Paid</button>
            </div>`;
        }

        // Per-tech payout cards
        payouts.forEach(p => {
            const statusBadge = p.status === 'paid'
                ? '<span class="badge" style="background: var(--success); color: white;">Paid</span>'
                : '<span class="badge" style="background: var(--warning); color: white;">Locked</span>';

            html += `
                <div class="card" style="margin-bottom: 1rem;">
                    <div class="card-header">
                        <h3 class="card-title">${p.tech_name} ${p.worker_type ? `<span class="badge" style="font-size: 0.7rem; padding: 2px 6px;">${p.worker_type}</span>` : ''} ${statusBadge}</h3>
                        <span style="font-size: 1.2rem; font-weight: bold;">$${p.net_payout.toFixed(2)}</span>
                    </div>
                    <div class="card-body">
                        <table class="data-table" style="margin-bottom: 0.5rem;">
                            <tr><td>Base Pay</td><td style="text-align:right">$${p.total_base_pay.toFixed(2)}</td></tr>
                            <tr><td>Mileage</td><td style="text-align:right">$${p.total_mileage_pay.toFixed(2)}</td></tr>
                            <tr><td>Per Diem</td><td style="text-align:right">$${p.total_per_diem.toFixed(2)}</td></tr>
                            <tr><td>Personal Expenses</td><td style="text-align:right">$${p.total_personal_expenses.toFixed(2)}</td></tr>
                            ${p.total_bonuses > 0 ? `<tr><td style="color: var(--success);">Bonuses</td><td style="text-align:right; color: var(--success);">+$${p.total_bonuses.toFixed(2)}</td></tr>` : ''}
                            ${p.total_deductions > 0 ? `<tr><td style="color: var(--danger);">Deductions</td><td style="text-align:right; color: var(--danger);">-$${p.total_deductions.toFixed(2)}</td></tr>` : ''}
                            ${p.total_advance_repayment > 0 ? `<tr><td style="color: var(--danger);">Advance Repayment</td><td style="text-align:right; color: var(--danger);">-$${p.total_advance_repayment.toFixed(2)}</td></tr>` : ''}
                            <tr style="font-weight: bold; border-top: 2px solid var(--border);"><td>Net Payout</td><td style="text-align:right">$${p.net_payout.toFixed(2)}</td></tr>
                        </table>
                        <div class="btn-group" style="gap: 0.25rem; flex-wrap: wrap;">
                            <button class="btn btn-sm btn-secondary" onclick="Pages.viewPayoutStub(${p.payout_id})"><i class="fas fa-file-alt"></i> View Stub</button>
                            ${p.status === 'locked' ? `
                                <button class="btn btn-sm btn-success" onclick="Pages.markPaid(${p.payout_id})"><i class="fas fa-check"></i> Mark Paid</button>
                                <button class="btn btn-sm btn-secondary" onclick="Pages.addPayoutLineItem(${p.payout_id}, 'bonus')"><i class="fas fa-plus"></i> Bonus</button>
                                <button class="btn btn-sm btn-secondary" onclick="Pages.addPayoutLineItem(${p.payout_id}, 'deduction')"><i class="fas fa-minus"></i> Deduction</button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        if (period.status === 'locked') {
            document.getElementById('pay-all-btn')?.addEventListener('click', async () => {
                if (!confirm('Mark all payouts as paid? This will close the period.')) return;
                try {
                    await API.payouts.payAll({ period_id: period.period_id });
                    App.showAlert('All payouts marked as paid', 'success');
                    window.location.hash = 'payout';
                    location.reload();
                } catch (e) {
                    App.showAlert('Failed: ' + e.message, 'error');
                }
            });
        }
    },

    async markPaid(payoutId) {
        if (!confirm('Mark this payout as paid?')) return;
        try {
            await API.payouts.pay(payoutId);
            App.showAlert('Payout marked as paid', 'success');
            window.location.hash = 'payout';
            location.reload();
        } catch (e) {
            App.showAlert('Failed: ' + e.message, 'error');
        }
    },

    async addPayoutLineItem(payoutId, type) {
        const title = type === 'bonus' ? 'Add Bonus' : 'Add Deduction';
        App.showModal(title, `
            <div class="form-group">
                <label>Description</label>
                <input type="text" id="li-description" class="form-control" placeholder="Description">
            </div>
            <div class="form-group">
                <label>Amount ($)</label>
                <input type="number" id="li-amount" class="form-control" step="0.01" min="0.01" placeholder="0.00">
            </div>
        `, `
            <button class="btn btn-primary" id="save-line-item-btn">Save</button>
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
        `);

        document.getElementById('save-line-item-btn').addEventListener('click', async () => {
            const description = document.getElementById('li-description').value.trim();
            const amount = parseFloat(document.getElementById('li-amount').value);
            if (!description || !amount || amount <= 0) {
                App.showAlert('Description and positive amount required', 'error');
                return;
            }
            try {
                await API.payouts.addLineItem(payoutId, { type, description, amount });
                App.hideModal();
                App.showAlert(`${type.charAt(0).toUpperCase() + type.slice(1)} added`, 'success');
                window.location.hash = 'payout';
                location.reload();
            } catch (e) {
                App.showAlert('Failed: ' + e.message, 'error');
            }
        });
    },

    async viewPayoutStub(payoutId) {
        try {
            const data = await API.payouts.getStub(payoutId);
            Pages.renderStubModal(data);
        } catch (e) {
            App.showAlert('Failed to load stub: ' + e.message, 'error');
        }
    },

    renderStubModal(data) {
        let jobRows = '';
        if (data.job_details) {
            jobRows = data.job_details.map(j => `
                <tr>
                    <td>${j.job_ticket || 'Job #' + j.job_id}${j.external_url ? ` <a href="${j.external_url}" target="_blank"><i class="fas fa-external-link-alt" style="font-size: 0.7rem;"></i></a>` : ''}</td>
                    <td>${j.hours.toFixed(2)}</td>
                    <td>$${j.effective_rate.toFixed(2)}</td>
                    <td>$${j.base_pay.toFixed(2)}</td>
                    <td>$${j.mileage_pay.toFixed(2)}</td>
                    <td>$${j.per_diem.toFixed(2)}</td>
                    <td>$${j.personal_expenses.toFixed(2)}</td>
                </tr>
            `).join('');
        }

        let lineItemRows = '';
        if (data.line_items && data.line_items.length) {
            lineItemRows = `<h4 style="margin-top: 1rem;">Bonuses / Deductions</h4><table class="data-table">
                <thead><tr><th>Type</th><th>Description</th><th>Amount</th></tr></thead>
                <tbody>${data.line_items.map(li => `<tr>
                    <td>${li.type === 'bonus' ? '<span style="color:var(--success);">Bonus</span>' : '<span style="color:var(--danger);">Deduction</span>'}</td>
                    <td>${li.description}</td>
                    <td>${li.type === 'bonus' ? '+' : '-'}$${li.amount.toFixed(2)}</td>
                </tr>`).join('')}</tbody></table>`;
        }

        let repaymentRows = '';
        if (data.advance_repayments && data.advance_repayments.length) {
            repaymentRows = `<h4 style="margin-top: 1rem;">Advance Repayments</h4><table class="data-table">
                <thead><tr><th>Advance</th><th>Amount</th></tr></thead>
                <tbody>${data.advance_repayments.map(ar => `<tr>
                    <td>Advance #${ar.advance_id}</td>
                    <td>-$${ar.amount.toFixed(2)}</td>
                </tr>`).join('')}</tbody></table>`;
        }

        const periodLabel = data.period ? `${data.period.period_name || ''} (${data.period.start_date} — ${data.period.end_date})` : '';

        const html = `
            <div style="margin-bottom: 1rem;">
                <strong>Technician:</strong> ${data.tech_name} ${data.worker_type ? `(${data.worker_type})` : ''}<br>
                <strong>Period:</strong> ${periodLabel}<br>
                <strong>Status:</strong> ${data.status}<br>
                ${data.paid_at ? `<strong>Paid:</strong> ${new Date(data.paid_at).toLocaleString()}<br>` : ''}
            </div>

            <h4>Job Details</h4>
            <table class="data-table">
                <thead><tr><th>Job</th><th>Hours</th><th>Rate</th><th>Base</th><th>Mileage</th><th>Per Diem</th><th>Expenses</th></tr></thead>
                <tbody>${jobRows}</tbody>
            </table>

            ${lineItemRows}
            ${repaymentRows}

            <div style="margin-top: 1rem; padding: 0.75rem; background: var(--bg-tertiary); border-radius: 8px;">
                <table style="width: 100%;">
                    <tr><td>Base Pay</td><td style="text-align:right">$${data.total_base_pay.toFixed(2)}</td></tr>
                    <tr><td>Mileage</td><td style="text-align:right">$${data.total_mileage_pay.toFixed(2)}</td></tr>
                    <tr><td>Per Diem</td><td style="text-align:right">$${data.total_per_diem.toFixed(2)}</td></tr>
                    <tr><td>Personal Expenses</td><td style="text-align:right">$${data.total_personal_expenses.toFixed(2)}</td></tr>
                    ${data.total_bonuses > 0 ? `<tr><td style="color:var(--success);">Bonuses</td><td style="text-align:right;color:var(--success);">+$${data.total_bonuses.toFixed(2)}</td></tr>` : ''}
                    ${data.total_deductions > 0 ? `<tr><td style="color:var(--danger);">Deductions</td><td style="text-align:right;color:var(--danger);">-$${data.total_deductions.toFixed(2)}</td></tr>` : ''}
                    ${data.total_advance_repayment > 0 ? `<tr><td style="color:var(--danger);">Advance Repayment</td><td style="text-align:right;color:var(--danger);">-$${data.total_advance_repayment.toFixed(2)}</td></tr>` : ''}
                    <tr style="font-weight:bold;font-size:1.1rem;border-top:2px solid var(--border);"><td>Net Payout</td><td style="text-align:right">$${data.net_payout.toFixed(2)}</td></tr>
                </table>
            </div>
        `;

        App.showModal(`Pay Stub — ${data.tech_name}`, html, `
            <button class="btn btn-secondary" onclick="window.print()"><i class="fas fa-print"></i> Print</button>
            <button class="btn btn-secondary" onclick="App.hideModal()">Close</button>
        `);
    },

    // ===================== MY PAYOUTS (TECH SELF-SERVICE) =====================

    async myPayouts(container) {
        try {
            const [dashData, payoutsData] = await Promise.all([
                API.my.dashboard(),
                API.my.payouts()
            ]);

            let html = `
                <div class="stats-grid" style="margin-bottom: 1.5rem;">
                    <div class="stat-card"><div class="stat-label">YTD Earnings</div><div class="stat-value">$${dashData.ytd_earnings.toFixed(2)}</div></div>
                    <div class="stat-card"><div class="stat-label">Last Payout</div><div class="stat-value">${dashData.last_payout ? '$' + dashData.last_payout.amount.toFixed(2) : '—'}</div></div>
                    <div class="stat-card"><div class="stat-label">Next Period Ends</div><div class="stat-value">${dashData.next_period_end || '—'}</div></div>
                </div>
            `;

            if (payoutsData.payouts && payoutsData.payouts.length) {
                html += `
                    <div class="card">
                        <div class="card-header"><h3 class="card-title">Pay History</h3></div>
                        <div class="card-body">
                            <table class="data-table">
                                <thead><tr>
                                    <th>Period</th><th>Hours</th><th>Base</th><th>Mileage</th><th>Per Diem</th><th>Net</th><th>Paid</th><th></th>
                                </tr></thead>
                                <tbody>
                                    ${payoutsData.payouts.map(p => `<tr>
                                        <td>${p.period?.period_name || ''}</td>
                                        <td>${p.total_hours.toFixed(2)}</td>
                                        <td>$${p.total_base_pay.toFixed(2)}</td>
                                        <td>$${p.total_mileage_pay.toFixed(2)}</td>
                                        <td>$${p.total_per_diem.toFixed(2)}</td>
                                        <td><strong>$${p.net_payout.toFixed(2)}</strong></td>
                                        <td>${p.paid_at ? new Date(p.paid_at).toLocaleDateString() : '—'}</td>
                                        <td><button class="btn btn-sm btn-secondary" onclick="Pages.viewMyStub(${p.payout_id})"><i class="fas fa-file-alt"></i> Stub</button></td>
                                    </tr>`).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            } else {
                html += '<div class="alert alert-info">No paid payouts yet.</div>';
            }

            container.innerHTML = html;
        } catch (e) {
            container.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
        }
    },

    async viewMyStub(payoutId) {
        try {
            const data = await API.my.stub(payoutId);
            Pages.renderStubModal(data);
        } catch (e) {
            App.showAlert('Failed to load stub: ' + e.message, 'error');
        }
    },

    // Technicians page
    async technicians(container) {
        let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Technicians</h3>
                    <button class="btn btn-primary" id="new-tech-btn"><i class="fas fa-plus"></i> New Technician</button>
                </div>
                <div class="filters">
                    <select class="form-control" id="tech-status-filter">
                        <option value="">All Statuses</option>
                        <option value="active" selected>Active</option>
                        <option value="inactive">Inactive</option>
                    </select>
                    <input type="text" class="form-control" id="tech-search" placeholder="Search...">
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Phone</th>
                                <th>Minimum Pay</th>
                                <th>Status</th>
                                <th>User Account</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="technicians-table"></tbody>
                    </table>
                </div>
                <div class="pagination" id="technicians-pagination"></div>
            </div>
        `;

        container.innerHTML = html;

        const loadTechnicians = async (page = 1) => {
            const params = { page, per_page: 20 };
            const status = document.getElementById('tech-status-filter').value;
            const search = document.getElementById('tech-search').value;

            if (status) params.status = status;
            if (search) params.search = search;

            const data = await API.technicians.list(params);

            const tbody = document.getElementById('technicians-table');
            if (data.technicians.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center">No technicians found</td></tr>';
            } else {
                tbody.innerHTML = data.technicians.map(tech => `
                    <tr>
                        <td>${tech.name}</td>
                        <td>${tech.email || '-'}</td>
                        <td>
                            ${tech.phone || '-'}
                            ${tech.phone ? (tech.sms_opted_in !== false
                                ? '<span class="badge badge-success" title="Opted in to SMS" style="margin-left:4px;font-size:0.7rem;">SMS</span>'
                                : '<span class="badge badge-danger" title="Opted out of SMS" style="margin-left:4px;font-size:0.7rem;">No SMS</span>')
                                : ''}
                        </td>
                        <td>${tech.hourly_rate ? '$' + parseFloat(tech.hourly_rate).toFixed(2) : '-'}</td>
                        <td>${App.getStatusBadge(tech.status)}</td>
                        <td>
                            ${tech.has_user_account
                                ? `<span class="badge badge-success">Yes</span> <small>(${tech.user_email})</small>`
                                : `<button class="btn btn-sm btn-secondary" onclick="Pages.createTechUserAccount(${tech.tech_id}, '${tech.name}', '${tech.email || ''}')">Create Account</button>`
                            }
                        </td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="Pages.editTechnician(${tech.tech_id})">Edit</button>
                            ${tech.status === 'active'
                                ? `<button class="btn btn-sm btn-danger" onclick="Pages.deactivateTechnician(${tech.tech_id})">Deactivate</button>`
                                : `<button class="btn btn-sm btn-success" onclick="Pages.reactivateTechnician(${tech.tech_id})">Activate</button>`
                            }
                        </td>
                    </tr>
                `).join('');
            }

            // Pagination
            const pagination = document.getElementById('technicians-pagination');
            pagination.innerHTML = `
                <button ${page <= 1 ? 'disabled' : ''} onclick="Pages.techniciansPage(${page - 1})">Prev</button>
                <span style="padding: 0.5rem;">Page ${page} of ${data.pages || 1}</span>
                <button ${page >= (data.pages || 1) ? 'disabled' : ''} onclick="Pages.techniciansPage(${page + 1})">Next</button>
            `;
        };

        Pages.techniciansPage = loadTechnicians;

        // Event listeners
        document.getElementById('tech-status-filter').addEventListener('change', () => loadTechnicians(1));
        document.getElementById('tech-search').addEventListener('input', debounce(() => loadTechnicians(1), 300));
        document.getElementById('new-tech-btn').addEventListener('click', () => Pages.editTechnician(null));

        await loadTechnicians(1);
    },

    // Edit/create technician
    async editTechnician(techId) {
        let tech = {};
        if (techId) {
            const data = await API.technicians.get(techId);
            tech = data.technician;
        }

        const body = `
            <form id="tech-form">
                <div class="form-group">
                    <label>Name *</label>
                    <input type="text" class="form-control" name="name" value="${tech.name || ''}" required>
                </div>
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" class="form-control" name="email" value="${tech.email || ''}">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Phone</label>
                        <input type="text" class="form-control" name="phone" value="${tech.phone || ''}">
                    </div>
                    <div class="form-group">
                        <label>Minimum Pay</label>
                        <input type="number" step="0.01" class="form-control" name="hourly_rate" value="${tech.hourly_rate || ''}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Worker Type</label>
                    <select class="form-control" name="worker_type">
                        <option value="contractor" ${(tech.worker_type || 'contractor') === 'contractor' ? 'selected' : ''}>Contractor</option>
                        <option value="employee" ${tech.worker_type === 'employee' ? 'selected' : ''}>Employee</option>
                    </select>
                </div>
                ${techId ? `
                <div class="form-group">
                    <label>Status</label>
                    <select class="form-control" name="status">
                        <option value="active" ${tech.status === 'active' ? 'selected' : ''}>Active</option>
                        <option value="inactive" ${tech.status === 'inactive' ? 'selected' : ''}>Inactive</option>
                    </select>
                </div>
                ` : `
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="create-user-checkbox"> Create user account for this technician
                    </label>
                </div>
                <div id="user-account-fields" style="display: none;">
                    <div class="form-group">
                        <label>Password *</label>
                        <input type="password" class="form-control" name="password" placeholder="Min 8 chars, uppercase, lowercase, number">
                    </div>
                </div>
                `}
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveTechnician(${techId})">Save</button>
        `;

        App.showModal(techId ? 'Edit Technician' : 'New Technician', body, footer);

        // Toggle password field visibility for new technicians
        if (!techId) {
            document.getElementById('create-user-checkbox').addEventListener('change', (e) => {
                document.getElementById('user-account-fields').style.display = e.target.checked ? 'block' : 'none';
            });
        }
    },

    // Save technician
    async saveTechnician(techId) {
        const form = document.getElementById('tech-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        // Handle checkbox for new technicians
        if (!techId) {
            const createUserCheckbox = document.getElementById('create-user-checkbox');
            data.create_user_account = createUserCheckbox?.checked || false;
        }

        try {
            if (techId) {
                await API.technicians.update(techId, data);
                App.showAlert('Technician updated', 'success');
            } else {
                await API.technicians.create(data);
                App.showAlert('Technician created', 'success');
            }
            App.hideModal();
            // Refresh technicians list in App for dropdowns
            const techData = await API.jobs.getTechnicians();
            App.technicians = techData.technicians;
            Pages.techniciansPage(1);
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Create user account for existing technician
    async createTechUserAccount(techId, name, email) {
        const body = `
            <form id="create-user-form">
                <p>Create a user account for technician: <strong>${name}</strong></p>
                <div class="form-group">
                    <label>Email *</label>
                    <input type="email" class="form-control" name="email" value="${email}" ${email ? '' : 'required'}>
                </div>
                <div class="form-group">
                    <label>Password *</label>
                    <input type="password" class="form-control" name="password" required placeholder="Min 8 chars, uppercase, lowercase, number">
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveUserForTechnician(${techId})">Create Account</button>
        `;

        App.showModal('Create User Account', body, footer);
    },

    // Save user account for technician
    async saveUserForTechnician(techId) {
        const form = document.getElementById('create-user-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        try {
            await API.technicians.createUserAccount(techId, data.password, data.email);
            App.showAlert('User account created', 'success');
            App.hideModal();
            Pages.techniciansPage(1);
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Deactivate technician
    async deactivateTechnician(techId) {
        if (!confirm('Are you sure you want to deactivate this technician? Their user account will also be deactivated.')) {
            return;
        }

        try {
            await API.technicians.delete(techId);
            App.showAlert('Technician deactivated', 'success');
            // Refresh technicians list in App for dropdowns
            const techData = await API.jobs.getTechnicians();
            App.technicians = techData.technicians;
            Pages.techniciansPage(1);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Reactivate technician
    async reactivateTechnician(techId) {
        try {
            await API.technicians.update(techId, { status: 'active' });
            App.showAlert('Technician activated', 'success');
            // Refresh technicians list in App for dropdowns
            const techData = await API.jobs.getTechnicians();
            App.technicians = techData.technicians;
            Pages.techniciansPage(1);
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Users page
    async users(container) {
        let html = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Users</h3>
                    <button class="btn btn-primary" id="new-user-btn"><i class="fas fa-plus"></i> New User</button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Email</th>
                                <th>Name</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Last Login</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="users-table"></tbody>
                    </table>
                </div>
            </div>
        `;

        container.innerHTML = html;

        const loadUsers = async () => {
            const data = await API.auth.listUsers();
            const tbody = document.getElementById('users-table');

            tbody.innerHTML = data.users.map(user => `
                <tr>
                    <td>${user.email}</td>
                    <td>${user.full_name || '-'}</td>
                    <td>${App.getStatusBadge(user.role)}</td>
                    <td>${App.getStatusBadge(user.status)}</td>
                    <td>${user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="Pages.editUser(${user.user_id})">Edit</button>
                        <button class="btn btn-sm btn-secondary" onclick="Pages.resetUserPassword(${user.user_id})">Reset PW</button>
                    </td>
                </tr>
            `).join('');
        };

        document.getElementById('new-user-btn').addEventListener('click', () => Pages.editUser(null));

        await loadUsers();
        Pages.loadUsers = loadUsers;
    },

    // Edit/create user
    async editUser(userId) {
        let user = {};
        if (userId) {
            const data = await API.auth.getUser(userId);
            user = data.user;
        }

        const body = `
            <form id="user-form">
                <div class="form-group">
                    <label>Email *</label>
                    <input type="email" class="form-control" name="email" value="${user.email || ''}" required ${userId ? 'readonly' : ''}>
                </div>
                <div class="form-group">
                    <label>Full Name</label>
                    <input type="text" class="form-control" name="full_name" value="${user.full_name || ''}">
                </div>
                ${!userId ? `
                <div class="form-group">
                    <label>Password *</label>
                    <input type="password" class="form-control" name="password" required>
                </div>
                ` : ''}
                <div class="form-row">
                    <div class="form-group">
                        <label>Role</label>
                        <select class="form-control" name="role">
                            <option value="technician" ${user.role === 'technician' ? 'selected' : ''}>Technician</option>
                            <option value="manager" ${user.role === 'manager' ? 'selected' : ''}>Manager</option>
                            <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Status</label>
                        <select class="form-control" name="status">
                            <option value="active" ${user.status === 'active' ? 'selected' : ''}>Active</option>
                            <option value="inactive" ${user.status === 'inactive' ? 'selected' : ''}>Inactive</option>
                            <option value="suspended" ${user.status === 'suspended' ? 'selected' : ''}>Suspended</option>
                        </select>
                    </div>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveUser(${userId})">Save</button>
        `;

        App.showModal(userId ? 'Edit User' : 'New User', body, footer);
    },

    // Save user
    async saveUser(userId) {
        const form = document.getElementById('user-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        try {
            if (userId) {
                await API.auth.updateUser(userId, data);
                App.showAlert('User updated', 'success');
            } else {
                await API.auth.createUser(data);
                App.showAlert('User created', 'success');
            }
            App.hideModal();
            Pages.loadUsers();
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    // Reset user password
    async resetUserPassword(userId) {
        const newPassword = prompt('Enter new password:');
        if (!newPassword) return;

        try {
            await API.auth.resetPassword(userId, newPassword);
            App.showAlert('Password reset successfully', 'success');
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Pay Periods Management
    async payPeriods(container) {
        const isManager = ['admin', 'manager'].includes(App.user.role);
        if (!isManager) {
            container.innerHTML = '<div class="alert alert-error">Access denied</div>';
            return;
        }

        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Pay Periods</h3>
                    <button class="btn btn-primary" onclick="Pages.showGeneratePeriodsModal()">
                        <i class="fas fa-magic"></i> Generate Periods
                    </button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Period Name</th>
                                <th>Start Date</th>
                                <th>End Date</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="pay-periods-table"></tbody>
                    </table>
                </div>
            </div>
        `;

        await this.loadPayPeriods();
    },

    async loadPayPeriods() {
        const data = await API.reports.payPeriods({ per_page: 50 });
        const tbody = document.getElementById('pay-periods-table');

        if (data.pay_periods.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No pay periods defined. Click "Generate Periods" to create them.</td></tr>';
            return;
        }

        tbody.innerHTML = data.pay_periods.map(period => `
            <tr>
                <td>${period.period_name}</td>
                <td>${App.formatDate(period.start_date)}</td>
                <td>${App.formatDate(period.end_date)}</td>
                <td>${App.getStatusBadge(period.status)}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="Pages.fillPayPeriod('${period.start_date}', '${period.end_date}'); window.location.hash='reports'; setTimeout(() => Pages.showPayrollReport(), 100);">
                        <i class="fas fa-file-invoice-dollar"></i> Payroll
                    </button>
                    ${period.status === 'open' ? `
                        <button class="btn btn-sm btn-warning" onclick="Pages.closePayPeriod(${period.period_id})">Close</button>
                    ` : ''}
                    <button class="btn btn-sm btn-danger" onclick="Pages.deletePayPeriod(${period.period_id})">Delete</button>
                </td>
            </tr>
        `).join('');
    },

    showGeneratePeriodsModal() {
        const body = `
            <form id="generate-periods-form">
                <div class="form-group">
                    <label>Anchor End Date (end date of a known period)</label>
                    <input type="date" class="form-control" name="anchor_end_date" value="2026-01-21" required>
                    <small class="text-muted">The most recent pay period ends on this date</small>
                </div>
                <div class="form-group">
                    <label>Period Length (days)</label>
                    <input type="number" class="form-control" name="period_length_days" value="14" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Periods Back</label>
                        <input type="number" class="form-control" name="count_back" value="6" required>
                    </div>
                    <div class="form-group">
                        <label>Periods Forward</label>
                        <input type="number" class="form-control" name="count_forward" value="4" required>
                    </div>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.generatePeriods()">Generate</button>
        `;

        App.showModal('Generate Pay Periods', body, footer);
    },

    async generatePeriods() {
        const form = document.getElementById('generate-periods-form');
        const formData = new FormData(form);
        const data = {
            anchor_end_date: formData.get('anchor_end_date'),
            period_length_days: parseInt(formData.get('period_length_days')),
            count_back: parseInt(formData.get('count_back')),
            count_forward: parseInt(formData.get('count_forward'))
        };

        try {
            const result = await API.reports.generatePayPeriods(data);
            App.showAlert(`Generated ${result.created.length} pay periods, assigned ${result.entries_assigned} time entries`, 'success');
            App.hideModal();
            await this.loadPayPeriods();
        } catch (error) {
            App.showFormError(error.message);
        }
    },

    async closePayPeriod(periodId) {
        if (!confirm('Close this pay period? This prevents further edits to entries in this period.')) return;

        try {
            await API.reports.closePayPeriod(periodId);
            App.showAlert('Pay period closed', 'success');
            await this.loadPayPeriods();
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    async deletePayPeriod(periodId) {
        if (!confirm('Delete this pay period? Time entries will be unassigned from the period.')) return;

        try {
            await API.reports.deletePayPeriod(periodId);
            App.showAlert('Pay period deleted', 'success');
            await this.loadPayPeriods();
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // ============ Backup & Recovery ============

    async backups(container) {
        const isAdmin = App.user.role === 'admin';
        if (!isAdmin) {
            container.innerHTML = '<div class="alert alert-error">Access denied - Admin only</div>';
            return;
        }

        // Check safe mode status
        let safeModeStatus = { active: false };
        try {
            safeModeStatus = await API.settings.getSafeModeStatus();
        } catch (e) {
            console.log('Could not get safe mode status:', e);
        }

        const safeModeClass = safeModeStatus.active ? 'btn-warning' : 'btn-success';
        const safeModeIcon = safeModeStatus.active ? 'fa-shield-alt' : 'fa-shield-alt';
        const safeModeText = safeModeStatus.active ? 'Safe Mode Active' : 'Enter Safe Mode';

        container.innerHTML = `
            <div class="card" style="margin-bottom: 1rem; ${safeModeStatus.active ? 'border: 2px solid var(--warning);' : ''}">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-shield-alt"></i> Safe Mode</h3>
                </div>
                <div style="padding: 1rem;">
                    ${safeModeStatus.active ? `
                        <div class="alert alert-warning" style="margin-bottom: 1rem;">
                            <strong>Safe Mode Active</strong> - A snapshot was taken at ${App.formatDate(safeModeStatus.started_at?.split('T')[0])}.
                            You can revert all changes or commit them to make permanent.
                        </div>
                        <button class="btn btn-success" onclick="Pages.commitSafeMode()">
                            <i class="fas fa-check"></i> Commit Changes
                        </button>
                        <button class="btn btn-danger" onclick="Pages.revertSafeMode()">
                            <i class="fas fa-undo"></i> Revert to Snapshot
                        </button>
                    ` : `
                        <p style="margin-bottom: 1rem;">Enter Safe Mode to create a snapshot before making changes.
                        If something goes wrong, you can revert to the snapshot.</p>
                        <button class="btn btn-success" onclick="Pages.enterSafeMode()">
                            <i class="fas fa-shield-alt"></i> Enter Safe Mode
                        </button>
                    `}
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-database"></i> Database Backups</h3>
                    <button class="btn btn-primary" onclick="Pages.createBackup()">
                        <i class="fas fa-plus"></i> Create Backup
                    </button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Filename</th>
                                <th>Created</th>
                                <th>Size</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="backups-table">
                            <tr><td colspan="4" class="text-center">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        await this.loadBackups();
    },

    async loadBackups() {
        try {
            const data = await API.settings.listBackups();
            const tbody = document.getElementById('backups-table');

            if (data.backups.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center">No backups found</td></tr>';
                return;
            }

            tbody.innerHTML = data.backups.map(backup => `
                <tr ${backup.is_safe_mode ? 'style="background: #fff3cd;"' : ''}>
                    <td>
                        ${backup.filename}
                        ${backup.is_safe_mode ? '<span class="badge badge-warning">Safe Mode</span>' : ''}
                    </td>
                    <td>${new Date(backup.created_at).toLocaleString()}</td>
                    <td>${backup.size_mb} MB</td>
                    <td>
                        <button class="btn btn-sm btn-warning" onclick="Pages.restoreBackup('${backup.filename}')">
                            <i class="fas fa-undo"></i> Restore
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="Pages.downloadBackup('${backup.filename}')">
                            <i class="fas fa-download"></i>
                        </button>
                        ${!backup.is_safe_mode ? `
                            <button class="btn btn-sm btn-danger" onclick="Pages.deleteBackup('${backup.filename}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        ` : ''}
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    async createBackup() {
        const label = prompt('Enter a label for this backup (optional):');
        if (label === null) return; // Cancelled

        try {
            const result = await API.settings.createBackup(label);
            App.showAlert(`Backup created: ${result.backup.filename}`, 'success');
            await this.loadBackups();
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    async restoreBackup(filename) {
        if (!confirm(`Are you sure you want to restore from "${filename}"?\n\nThis will OVERWRITE the current database with the backup. This cannot be undone.`)) {
            return;
        }

        if (!confirm('FINAL WARNING: All data since this backup was created will be lost. Continue?')) {
            return;
        }

        try {
            await API.settings.restoreBackup(filename);
            App.showAlert('Database restored successfully. Please refresh the page.', 'success');
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    async deleteBackup(filename) {
        if (!confirm(`Delete backup "${filename}"? This cannot be undone.`)) {
            return;
        }

        try {
            await API.settings.deleteBackup(filename);
            App.showAlert('Backup deleted', 'success');
            await this.loadBackups();
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    downloadBackup(filename) {
        // Open in new tab - server will need a download endpoint
        window.open(`/api/settings/backups/${filename}/download`, '_blank');
    },

    async enterSafeMode() {
        if (!confirm('Enter Safe Mode?\n\nA snapshot of the database will be created. You can make changes and then either commit them or revert to the snapshot.')) {
            return;
        }

        try {
            const result = await API.settings.enterSafeMode();
            App.showAlert(result.message, 'success');
            // Refresh the page to show safe mode status
            await this.backups(document.getElementById('content'));
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    async commitSafeMode() {
        if (!confirm('Commit changes and exit Safe Mode?\n\nThe snapshot will be deleted and your changes will be permanent.')) {
            return;
        }

        try {
            const result = await API.settings.commitSafeMode();
            App.showAlert(result.message, 'success');
            await this.backups(document.getElementById('content'));
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    async revertSafeMode() {
        if (!confirm('Revert to snapshot and exit Safe Mode?\n\nALL CHANGES since entering Safe Mode will be LOST.')) {
            return;
        }

        if (!confirm('FINAL WARNING: This will restore the database to the snapshot. All recent changes will be lost. Continue?')) {
            return;
        }

        try {
            const result = await API.settings.revertSafeMode();
            App.showAlert(result.message, 'success');
            await this.backups(document.getElementById('content'));
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // ============ System Settings ============

    async settings(container) {
        const isAdmin = App.user.role === 'admin';
        if (!isAdmin) {
            container.innerHTML = '<div class="alert alert-error">Access denied - Admin only</div>';
            return;
        }

        // Get current timezone setting
        let currentTimezone = 'America/Chicago';
        try {
            const tzSetting = await API.settings.get('timezone');
            currentTimezone = tzSetting.setting.setting_value;
        } catch (e) {
            console.error('Failed to load timezone setting:', e);
        }

        // Get current SMS settings
        let smsSettings = { enabled: false, from_number: '', has_credentials: false };
        try {
            smsSettings = await API.settings.getSmsSettings();
        } catch (e) {
            console.error('Failed to load SMS settings:', e);
        }

        // Get payout preferences
        let payoutPrefs = { interval_days: 14, anchor_date: '', auto_generate: false };
        try {
            payoutPrefs = await API.request('/settings/payout-preferences');
        } catch (e) {
            console.error('Failed to load payout preferences:', e);
        }

        const timezones = [
            { value: 'America/New_York',   label: 'Eastern (ET) — New York, Atlanta, Miami' },
            { value: 'America/Chicago',    label: 'Central (CT) — Chicago, Dallas, Kansas City' },
            { value: 'America/Denver',     label: 'Mountain (MT) — Denver, Salt Lake City' },
            { value: 'America/Phoenix',    label: 'Mountain no DST — Phoenix, Arizona' },
            { value: 'America/Los_Angeles', label: 'Pacific (PT) — Los Angeles, Seattle' },
            { value: 'America/Anchorage',  label: 'Alaska (AKT)' },
            { value: 'America/Honolulu',   label: 'Hawaii (HT) — no DST' },
            { value: 'UTC',               label: 'UTC' },
        ];
        const tzOptions = timezones.map(tz =>
            `<option value="${tz.value}" ${currentTimezone === tz.value ? 'selected' : ''}>${tz.label}</option>`
        ).join('');

        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-clock"></i> Timezone</h3>
                </div>
                <div style="padding: 1rem;">
                    <div class="form-group">
                        <label>Application Timezone</label>
                        <select id="timezone-select" class="form-control" style="max-width: 400px;">
                            ${tzOptions}
                        </select>
                        <small class="text-muted">Used for "today" calculations in reports and dashboard stats.</small>
                    </div>
                    <button type="button" class="btn btn-primary" onclick="Pages.saveTimezone()">
                        <i class="fas fa-save"></i> Save Timezone
                    </button>
                </div>
            </div>

            <div class="card" style="margin-top: 1rem;">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-sms"></i> SMS Notification Settings</h3>
                </div>
                <div style="padding: 1rem;">
                    <form id="sms-settings-form">
                        <div class="form-group">
                            <label>
                                <input type="checkbox" name="enabled" ${smsSettings.enabled ? 'checked' : ''} style="margin-right: 0.5rem;">
                                Enable SMS notifications for job assignments
                            </label>
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label>API Username</label>
                                <input type="text" class="form-control" name="api_key" placeholder="${smsSettings.has_credentials ? '••••••••' : 'Enter username'}" autocomplete="off" data-lpignore="true" data-1p-ignore="true">
                                <small class="text-muted">VoIP Innovations API username</small>
                            </div>
                            <div class="form-group">
                                <label>API Password</label>
                                <input type="text" class="form-control" name="api_secret" placeholder="${smsSettings.has_credentials ? '••••••••' : 'Enter password'}" autocomplete="off" data-lpignore="true" data-1p-ignore="true">
                                <small class="text-muted">VoIP Innovations API password</small>
                            </div>
                        </div>

                        <div class="form-group">
                            <label>From Number (DID)</label>
                            <input type="text" class="form-control" name="from_number" value="${smsSettings.from_number || ''}" placeholder="+13165551234">
                            <small class="text-muted">Your SMS-enabled DID from VoIP Innovations</small>
                        </div>

                        <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                            <button type="button" class="btn btn-primary" onclick="Pages.saveSmsSettings()">
                                <i class="fas fa-save"></i> Save Settings
                            </button>
                            <button type="button" class="btn btn-secondary" onclick="Pages.testSms()">
                                <i class="fas fa-paper-plane"></i> Send Test SMS
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <div class="card" style="margin-top: 1rem;">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-info-circle"></i> SMS Setup Instructions</h3>
                </div>
                <div style="padding: 1rem;">
                    <ol style="margin-left: 1.5rem; line-height: 1.8;">
                        <li>Log in to <a href="https://backoffice.voipinnovations.com/" target="_blank">VoIP Innovations Backoffice</a></li>
                        <li>Go to API → API Users and create an API login</li>
                        <li>Whitelist your server IP (34.27.146.58)</li>
                        <li>Enable SMS on your DID (Add-Ons → Configure)</li>
                        <li>Enter credentials above and test</li>
                    </ol>
                    <p class="text-muted" style="margin-top: 1rem;">
                        <strong>Note:</strong> SMS notifications are sent when technicians are assigned to jobs.
                        Technicians must have a valid phone number in their profile to receive notifications.
                    </p>
                </div>
            </div>

            <div class="card" style="margin-top: 1rem;">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-money-bill-wave"></i> Payout Configuration</h3>
                </div>
                <div style="padding: 1rem;">
                    <div class="form-group">
                        <label>Pay Interval</label>
                        <input type="text" class="form-control" value="Biweekly — ${payoutPrefs.interval_days} days" readonly style="max-width: 300px; background: var(--bg-tertiary);">
                    </div>
                    <div class="form-group">
                        <label>Anchor Date</label>
                        <input type="date" id="payout-anchor-date" class="form-control" value="${payoutPrefs.anchor_date || ''}" style="max-width: 200px;">
                        <small class="text-muted">The first day of the first pay period. Periods generate forward from this date.</small>
                    </div>
                    <button type="button" class="btn btn-primary" onclick="Pages.savePayoutPrefs()">
                        <i class="fas fa-save"></i> Save Payout Preferences
                    </button>
                </div>
            </div>
        `;
    },

    async savePayoutPrefs() {
        const anchorDate = document.getElementById('payout-anchor-date')?.value;
        try {
            await API.request('/settings/payout-preferences', {
                method: 'PUT',
                body: JSON.stringify({ anchor_date: anchorDate || '' })
            });
            App.showAlert('Payout preferences saved', 'success');
        } catch (e) {
            App.showAlert('Failed to save: ' + e.message, 'error');
        }
    },

    async saveTimezone() {
        const select = document.getElementById('timezone-select');
        if (!select) return;
        const tz = select.value;
        try {
            await API.settings.update('timezone', { setting_value: tz });
            App.showAlert('Timezone saved', 'success');
        } catch (error) {
            App.showAlert(error.message || 'Failed to save timezone');
        }
    },

    async saveSmsSettings() {
        const form = document.getElementById('sms-settings-form');
        if (!form) {
            App.showAlert('Form not found');
            return;
        }

        const enabledCheckbox = form.querySelector('input[name="enabled"]');
        const apiKeyInput = form.querySelector('input[name="api_key"]');
        const apiSecretInput = form.querySelector('input[name="api_secret"]');
        const fromNumberInput = form.querySelector('input[name="from_number"]');

        const data = {
            enabled: enabledCheckbox ? enabledCheckbox.checked : false,
            from_number: fromNumberInput ? fromNumberInput.value.trim() : ''
        };

        // Only include credentials if they were entered
        const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
        const apiSecret = apiSecretInput ? apiSecretInput.value.trim() : '';
        if (apiKey) data.api_key = apiKey;
        if (apiSecret) data.api_secret = apiSecret;

        console.log('Saving SMS settings:', { ...data, api_key: apiKey ? '[SET]' : '[EMPTY]', api_secret: apiSecret ? '[SET]' : '[EMPTY]' });

        try {
            const result = await API.settings.updateSmsSettings(data);
            console.log('Save result:', result);
            App.showAlert('SMS settings saved', 'success');
            // Refresh the page to show updated values
            Pages.settings(document.getElementById('main-content'));
        } catch (error) {
            console.error('Save error:', error);
            App.showAlert(error.message || 'Failed to save settings');
        }
    },

    async testSms() {
        const phoneNumber = prompt('Enter phone number to send test SMS to (e.g., +1234567890):');
        if (!phoneNumber) return;

        try {
            const result = await API.settings.testSms(phoneNumber);
            App.showAlert(result.message || 'Test SMS sent successfully', 'success');
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // ============ SMS Log ============

    async smsLog(container) {
        const isManager = App.user.role === 'admin' || App.user.role === 'manager';
        if (!isManager) {
            container.innerHTML = '<div class="alert alert-error">Access denied</div>';
            return;
        }

        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title"><i class="fas fa-sms"></i> SMS Log</h3>
                </div>
                <div style="padding: 1rem; display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end;">
                    <div class="form-group" style="margin: 0;">
                        <label>Technician</label>
                        <select id="sms-log-tech" class="form-control">
                            <option value="">All Technicians</option>
                            ${App.technicians.map(t => `<option value="${t.tech_id}">${t.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>Status</label>
                        <select id="sms-log-status" class="form-control">
                            <option value="">All</option>
                            <option value="sent">Sent</option>
                            <option value="delivered">Delivered</option>
                            <option value="failed">Failed</option>
                            <option value="pending">Pending</option>
                        </select>
                    </div>
                    <button class="btn btn-secondary" onclick="Pages.loadSmsLog()">
                        <i class="fas fa-sync"></i> Refresh
                    </button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Technician</th>
                                <th>Phone</th>
                                <th>Type</th>
                                <th>Message</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="sms-log-table">
                            <tr><td colspan="6" class="text-center">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        document.getElementById('sms-log-tech').addEventListener('change', () => Pages.loadSmsLog());
        document.getElementById('sms-log-status').addEventListener('change', () => Pages.loadSmsLog());

        await Pages.loadSmsLog();
    },

    async loadSmsLog() {
        const techId = document.getElementById('sms-log-tech')?.value;
        const status = document.getElementById('sms-log-status')?.value;
        const params = { limit: 200 };
        if (techId) params.tech_id = techId;
        if (status) params.status = status;

        const tbody = document.getElementById('sms-log-table');
        if (!tbody) return;

        try {
            const data = await API.sms.getLog(params);
            const notifications = data.notifications || [];

            if (notifications.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No SMS records found</td></tr>';
                return;
            }

            const statusBadge = s => {
                const cls = { sent: 'badge-primary', delivered: 'badge-success', failed: 'badge-danger', pending: 'badge-warning' };
                return `<span class="badge ${cls[s] || 'badge-secondary'}">${s}</span>`;
            };

            const typeLabel = t => {
                const labels = {
                    job_assignment: 'Assignment',
                    invitation: 'Availability',
                    reminder: 'Reminder',
                    cancellation: 'Cancellation',
                    update: 'Update',
                    other: 'Other'
                };
                return labels[t] || t;
            };

            tbody.innerHTML = notifications.map(n => `
                <tr>
                    <td style="white-space:nowrap;">${n.created_at ? new Date(n.created_at).toLocaleString() : '-'}</td>
                    <td>${n.tech_name || '-'}</td>
                    <td style="white-space:nowrap;">${n.phone_number || '-'}</td>
                    <td>${typeLabel(n.notification_type)}</td>
                    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${(n.message_body || '').replace(/"/g, '&quot;')}">${n.message_body || ''}</td>
                    <td>${statusBadge(n.status)}</td>
                </tr>
            `).join('');
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Error: ${error.message}</td></tr>`;
        }
    }
};

// Utility: Debounce
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => App.init());
