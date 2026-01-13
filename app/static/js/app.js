/**
 * Work Tracking System - Main Application
 */

const App = {
    currentPage: 'dashboard',
    user: null,
    platforms: [],

    // Initialize the app
    async init() {
        // Check authentication
        if (!API.isLoggedIn()) {
            window.location.href = '/login';
            return;
        }

        this.user = API.getUser();

        // Load platforms for forms
        try {
            const data = await API.jobs.getPlatforms();
            this.platforms = data.platforms;
        } catch (e) {
            console.error('Failed to load platforms:', e);
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
            { id: 'time-entries', icon: 'fas fa-clock', label: 'Time Entries' },
            { id: 'reports', icon: 'fas fa-chart-bar', label: 'Reports', roles: ['admin', 'manager'] },
            { id: 'users', icon: 'fas fa-users', label: 'Users', roles: ['admin'] }
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
            'time-entries': 'Time Entries',
            'reports': 'Reports',
            'users': 'User Management'
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
                case 'time-entries':
                    await Pages.timeEntries(content);
                    break;
                case 'reports':
                    await Pages.reports(content);
                    break;
                case 'users':
                    await Pages.users(content);
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
    showModal(title, body, footer = '') {
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-body').innerHTML = body;
        document.getElementById('modal-footer').innerHTML = footer;
        modal.classList.add('active');
    },

    // Hide modal
    hideModal() {
        document.getElementById('modal-overlay').classList.remove('active');
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

    // Format date
    formatDate(dateStr) {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleDateString();
    },

    // Format time
    formatTime(timeStr) {
        if (!timeStr) return '-';
        return timeStr.slice(0, 5);
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

        container.innerHTML = html;
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
                                <th>Date</th>
                                <th>Status</th>
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

        const loadJobs = async (page = 1) => {
            const params = { page, per_page: 20 };
            const status = document.getElementById('job-status-filter').value;
            const platform = document.getElementById('job-platform-filter').value;
            const search = document.getElementById('job-search').value;

            if (status) params.status = status;
            if (platform) params.platform_id = platform;
            if (search) params.search = search;

            const data = await API.jobs.list(params);

            const tbody = document.getElementById('jobs-table');
            if (data.jobs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center">No jobs found</td></tr>';
            } else {
                tbody.innerHTML = data.jobs.map(job => `
                    <tr>
                        <td>${job.ticket_number || '-'}</td>
                        <td>${job.description}</td>
                        <td>${job.platform_name || '-'}</td>
                        <td>${job.client_name || '-'}</td>
                        <td>${App.formatDate(job.job_date)}</td>
                        <td>${App.getStatusBadge(job.job_status)}</td>
                        <td>
                            <button class="btn btn-sm btn-secondary" onclick="Pages.viewJob(${job.job_id})">View</button>
                            ${isManager ? `<button class="btn btn-sm btn-primary" onclick="Pages.editJob(${job.job_id})">Edit</button>` : ''}
                        </td>
                    </tr>
                `).join('');
            }

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
        document.getElementById('job-search').addEventListener('input', debounce(() => loadJobs(1), 300));

        if (isManager) {
            document.getElementById('new-job-btn').addEventListener('click', () => Pages.editJob(null));
        }

        await loadJobs(1);
    },

    // View job details
    async viewJob(jobId) {
        const data = await API.jobs.get(jobId);
        const job = data.job;

        const body = `
            <div class="form-group">
                <label>Ticket Number</label>
                <p>${job.ticket_number || '-'}</p>
            </div>
            <div class="form-group">
                <label>Description</label>
                <p>${job.description}</p>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Platform</label>
                    <p>${job.platform_name || '-'}</p>
                </div>
                <div class="form-group">
                    <label>Client</label>
                    <p>${job.client_name || '-'}</p>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Status</label>
                    <p>${App.getStatusBadge(job.job_status)}</p>
                </div>
                <div class="form-group">
                    <label>Billing</label>
                    <p>${job.billing_type}: $${job.billing_amount || 0}</p>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Job Date</label>
                    <p>${App.formatDate(job.job_date)}</p>
                </div>
                <div class="form-group">
                    <label>Total Hours</label>
                    <p>${job.total_hours_worked || 0}</p>
                </div>
            </div>
        `;

        App.showModal('Job Details', body, '<button class="btn btn-secondary" onclick="App.hideModal()">Close</button>');
    },

    // Edit/create job
    async editJob(jobId) {
        let job = {};
        if (jobId) {
            const data = await API.jobs.get(jobId);
            job = data.job;
        }

        const body = `
            <form id="job-form">
                <div class="form-group">
                    <label>Platform *</label>
                    <select class="form-control" name="platform_id" required>
                        <option value="">Select Platform</option>
                        ${App.getPlatformOptions(job.platform_id)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Ticket Number</label>
                    <input type="text" class="form-control" name="ticket_number" value="${job.ticket_number || ''}">
                </div>
                <div class="form-group">
                    <label>Description *</label>
                    <input type="text" class="form-control" name="description" value="${job.description || ''}" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Client Name</label>
                        <input type="text" class="form-control" name="client_name" value="${job.client_name || ''}">
                    </div>
                    <div class="form-group">
                        <label>Job Type</label>
                        <input type="text" class="form-control" name="job_type" value="${job.job_type || ''}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Location</label>
                    <input type="text" class="form-control" name="location" value="${job.location || ''}">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Billing Type</label>
                        <select class="form-control" name="billing_type">
                            <option value="flat_rate" ${job.billing_type === 'flat_rate' ? 'selected' : ''}>Flat Rate</option>
                            <option value="hourly" ${job.billing_type === 'hourly' ? 'selected' : ''}>Hourly</option>
                            <option value="per_task" ${job.billing_type === 'per_task' ? 'selected' : ''}>Per Task</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Billing Amount</label>
                        <input type="number" step="0.01" class="form-control" name="billing_amount" value="${job.billing_amount || ''}">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Job Date</label>
                        <input type="date" class="form-control" name="job_date" value="${job.job_date || ''}">
                    </div>
                    <div class="form-group">
                        <label>Status</label>
                        <select class="form-control" name="job_status">
                            <option value="pending" ${job.job_status === 'pending' ? 'selected' : ''}>Pending</option>
                            <option value="assigned" ${job.job_status === 'assigned' ? 'selected' : ''}>Assigned</option>
                            <option value="in_progress" ${job.job_status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                            <option value="completed" ${job.job_status === 'completed' ? 'selected' : ''}>Completed</option>
                            <option value="cancelled" ${job.job_status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
                        </select>
                    </div>
                </div>
            </form>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.hideModal()">Cancel</button>
            <button class="btn btn-primary" onclick="Pages.saveJob(${jobId})">Save</button>
        `;

        App.showModal(jobId ? 'Edit Job' : 'New Job', body, footer);
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
            } else {
                await API.jobs.create(data);
                App.showAlert('Job created successfully', 'success');
            }
            App.hideModal();
            Pages.jobsPage(1);
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
                    <select class="form-control" id="entry-status-filter">
                        <option value="">All Statuses</option>
                        <option value="draft">Draft</option>
                        <option value="submitted">Submitted</option>
                        <option value="verified">Verified</option>
                        <option value="billed">Billed</option>
                        <option value="paid">Paid</option>
                    </select>
                    <input type="date" class="form-control" id="entry-from-date">
                    <input type="date" class="form-control" id="entry-to-date">
                    ${isManager ? '<button class="btn btn-success btn-sm" id="bulk-verify-btn">Bulk Verify</button>' : ''}
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                ${isManager ? '<th><input type="checkbox" id="select-all-entries"></th>' : ''}
                                <th>Date</th>
                                <th>Job</th>
                                <th>Time In</th>
                                <th>Time Out</th>
                                <th>Hours</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="entries-table"></tbody>
                    </table>
                </div>
                <div class="pagination" id="entries-pagination"></div>
            </div>
        `;

        container.innerHTML = html;

        const loadEntries = async (page = 1) => {
            const params = { page, per_page: 20 };
            const status = document.getElementById('entry-status-filter').value;
            const fromDate = document.getElementById('entry-from-date').value;
            const toDate = document.getElementById('entry-to-date').value;

            if (status) params.status = status;
            if (fromDate) params.from_date = fromDate;
            if (toDate) params.to_date = toDate;

            const data = await API.timeEntries.list(params);

            const tbody = document.getElementById('entries-table');
            if (data.time_entries.length === 0) {
                tbody.innerHTML = `<tr><td colspan="${isManager ? 9 : 8}" class="text-center">No entries found</td></tr>`;
            } else {
                tbody.innerHTML = data.time_entries.map(entry => `
                    <tr>
                        ${isManager ? `<td><input type="checkbox" class="entry-checkbox" value="${entry.entry_id}" ${entry.status !== 'submitted' ? 'disabled' : ''}></td>` : ''}
                        <td>${App.formatDate(entry.date_worked)}</td>
                        <td>${entry.job_id}</td>
                        <td>${App.formatTime(entry.time_in)}</td>
                        <td>${App.formatTime(entry.time_out)}</td>
                        <td>${entry.hours_worked || '-'}</td>
                        <td>${App.getStatusBadge(entry.status)}</td>
                        <td>
                            ${entry.status === 'draft' ? `
                                <button class="btn btn-sm btn-primary" onclick="Pages.editEntry(${entry.entry_id})">Edit</button>
                                <button class="btn btn-sm btn-success" onclick="Pages.submitEntry(${entry.entry_id})">Submit</button>
                            ` : ''}
                            ${entry.status === 'submitted' && isManager ? `
                                <button class="btn btn-sm btn-success" onclick="Pages.verifyEntry(${entry.entry_id})">Verify</button>
                                <button class="btn btn-sm btn-danger" onclick="Pages.rejectEntry(${entry.entry_id})">Reject</button>
                            ` : ''}
                        </td>
                    </tr>
                `).join('');
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

        // Event listeners
        document.getElementById('entry-status-filter').addEventListener('change', () => loadEntries(1));
        document.getElementById('entry-from-date').addEventListener('change', () => loadEntries(1));
        document.getElementById('entry-to-date').addEventListener('change', () => loadEntries(1));
        document.getElementById('new-entry-btn').addEventListener('click', () => Pages.editEntry(null));

        if (isManager) {
            document.getElementById('select-all-entries').addEventListener('change', (e) => {
                document.querySelectorAll('.entry-checkbox:not(:disabled)').forEach(cb => cb.checked = e.target.checked);
            });

            document.getElementById('bulk-verify-btn').addEventListener('click', async () => {
                const selected = [...document.querySelectorAll('.entry-checkbox:checked')].map(cb => parseInt(cb.value));
                if (selected.length === 0) {
                    App.showAlert('No entries selected');
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

        // Get jobs for dropdown
        const jobsData = await API.jobs.list({ per_page: 100, status: 'in_progress' });
        const jobOptions = jobsData.jobs.map(j =>
            `<option value="${j.job_id}" ${j.job_id == entry.job_id ? 'selected' : ''}>${j.ticket_number || j.job_id} - ${j.description.slice(0, 30)}</option>`
        ).join('');

        const body = `
            <form id="entry-form">
                <div class="form-group">
                    <label>Job *</label>
                    <select class="form-control" name="job_id" required>
                        <option value="">Select Job</option>
                        ${jobOptions}
                    </select>
                </div>
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
            App.showAlert(error.message);
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

    // Reports page
    async reports(container) {
        const html = `
            <div class="stats-grid">
                <div class="stat-card" style="cursor: pointer" onclick="Pages.showPayrollReport()">
                    <div class="stat-label">Payroll Report</div>
                    <div class="stat-value"><i class="fas fa-file-invoice-dollar"></i></div>
                </div>
                <div class="stat-card" style="cursor: pointer" onclick="Pages.showBillingReport()">
                    <div class="stat-label">Job Billing</div>
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

        content.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Payroll Report</h3>
                </div>
                <div class="filters">
                    <input type="date" class="form-control" id="payroll-from" value="${firstDay}">
                    <input type="date" class="form-control" id="payroll-to" value="${lastDay}">
                    <button class="btn btn-primary" onclick="Pages.loadPayrollReport()">Generate</button>
                </div>
                <div id="payroll-results"></div>
            </div>
        `;
    },

    async loadPayrollReport() {
        const fromDate = document.getElementById('payroll-from').value;
        const toDate = document.getElementById('payroll-to').value;

        try {
            const data = await API.reports.payroll({ from_date: fromDate, to_date: toDate });

            let html = `
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Technician</th>
                                <th>Entries</th>
                                <th>Hours</th>
                                <th>Rate</th>
                                <th>Total Pay</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.data.map(row => `
                                <tr>
                                    <td>${row.name}</td>
                                    <td>${row.entry_count}</td>
                                    <td>${row.total_hours.toFixed(2)}</td>
                                    <td>$${row.hourly_rate.toFixed(2)}</td>
                                    <td>$${row.total_pay.toFixed(2)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                        <tfoot>
                            <tr>
                                <th colspan="2">Total</th>
                                <th>${data.summary.total_hours.toFixed(2)}</th>
                                <th></th>
                                <th>$${data.summary.total_pay.toFixed(2)}</th>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;

            document.getElementById('payroll-results').innerHTML = html;
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Show billing report
    async showBillingReport() {
        const content = document.getElementById('report-content');

        content.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Job Billing Report</h3>
                </div>
                <div class="filters">
                    <input type="date" class="form-control" id="billing-from">
                    <input type="date" class="form-control" id="billing-to">
                    <button class="btn btn-primary" onclick="Pages.loadBillingReport()">Generate</button>
                </div>
                <div id="billing-results"></div>
            </div>
        `;
    },

    async loadBillingReport() {
        const fromDate = document.getElementById('billing-from').value;
        const toDate = document.getElementById('billing-to').value;

        try {
            const params = {};
            if (fromDate) params.from_date = fromDate;
            if (toDate) params.to_date = toDate;

            const data = await API.reports.jobBilling(params);

            let html = `
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Ticket</th>
                                <th>Description</th>
                                <th>Platform</th>
                                <th>Billing</th>
                                <th>Hours</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.data.map(row => `
                                <tr>
                                    <td>${row.ticket_number || '-'}</td>
                                    <td>${row.description.slice(0, 40)}</td>
                                    <td>${row.platform}</td>
                                    <td>$${row.billing_amount.toFixed(2)}</td>
                                    <td>${row.actual_hours.toFixed(2)}</td>
                                    <td>${App.getStatusBadge(row.job_status)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                        <tfoot>
                            <tr>
                                <th colspan="3">Total (${data.summary.job_count} jobs)</th>
                                <th>$${data.summary.total_billing.toFixed(2)}</th>
                                <th>${data.summary.total_hours.toFixed(2)}</th>
                                <th></th>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;

            document.getElementById('billing-results').innerHTML = html;
        } catch (error) {
            App.showAlert(error.message);
        }
    },

    // Show platform report
    async showPlatformReport() {
        const content = document.getElementById('report-content');

        try {
            const data = await API.reports.platformSummary({});

            let html = `
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Platform Summary</h3>
                    </div>
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
                        </table>
                    </div>
                </div>
            `;

            content.innerHTML = html;
        } catch (error) {
            App.showAlert(error.message);
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
            App.showAlert(error.message);
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
