/**
 * Work Tracking System - API Client
 */

const API = {
    baseUrl: '/api',

    // Get stored auth token
    getToken() {
        return localStorage.getItem('access_token');
    },

    // Set auth token
    setToken(token) {
        localStorage.setItem('access_token', token);
    },

    // Set refresh token
    setRefreshToken(token) {
        localStorage.setItem('refresh_token', token);
    },

    // Clear tokens (logout)
    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
    },

    // Get stored user
    getUser() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },

    // Set user
    setUser(user) {
        localStorage.setItem('user', JSON.stringify(user));
    },

    // Check if logged in
    isLoggedIn() {
        return !!this.getToken();
    },

    // Make API request
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const token = this.getToken();

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            const data = await response.json();

            if (!response.ok) {
                // Handle authentication errors
                if (response.status === 401) {
                    // Try to refresh token first
                    if (data.code === 'token_expired' || data.error?.includes('expired')) {
                        const refreshed = await this.refreshToken();
                        if (refreshed) {
                            // Retry the request with new token
                            return this.request(endpoint, options);
                        }
                    }
                    // Refresh failed or other auth error - redirect to login
                    this.clearTokens();
                    window.location.href = '/login';
                    return;
                }
                // For non-auth errors, throw with the actual error message
                throw new Error(data.error || data.message || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Refresh access token
    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) return false;

        try {
            const response = await fetch(`${this.baseUrl}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${refreshToken}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.setToken(data.access_token);
                return true;
            }
            return false;
        } catch {
            return false;
        }
    },

    // Auth endpoints
    auth: {
        async login(email, password) {
            const data = await API.request('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });
            API.setToken(data.access_token);
            API.setRefreshToken(data.refresh_token);
            API.setUser(data.user);
            return data;
        },

        logout() {
            API.clearTokens();
            window.location.href = '/login';
        },

        async me() {
            return API.request('/auth/me');
        },

        async updateProfile(data) {
            return API.request('/auth/me', {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        async listUsers(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/auth/users${query ? '?' + query : ''}`);
        },

        async getUser(userId) {
            return API.request(`/auth/users/${userId}`);
        },

        async createUser(userData) {
            return API.request('/auth/register', {
                method: 'POST',
                body: JSON.stringify(userData)
            });
        },

        async updateUser(userId, userData) {
            return API.request(`/auth/users/${userId}`, {
                method: 'PUT',
                body: JSON.stringify(userData)
            });
        },

        async resetPassword(userId, newPassword) {
            return API.request(`/auth/users/${userId}/reset-password`, {
                method: 'POST',
                body: JSON.stringify({ new_password: newPassword })
            });
        }
    },

    // Jobs endpoints
    jobs: {
        async list(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/jobs${query ? '?' + query : ''}`);
        },

        async get(jobId) {
            return API.request(`/jobs/${jobId}`);
        },

        async create(jobData) {
            return API.request('/jobs', {
                method: 'POST',
                body: JSON.stringify(jobData)
            });
        },

        async update(jobId, jobData) {
            return API.request(`/jobs/${jobId}`, {
                method: 'PUT',
                body: JSON.stringify(jobData)
            });
        },

        async delete(jobId) {
            return API.request(`/jobs/${jobId}`, {
                method: 'DELETE'
            });
        },

        async getTimeEntries(jobId) {
            return API.request(`/jobs/${jobId}/time-entries`);
        },

        async getPlatforms() {
            return API.request('/jobs/platforms');
        },

        async getTechnicians() {
            return API.request('/jobs/technicians');
        },

        async getStats() {
            return API.request('/jobs/stats');
        }
    },

    // Time entries endpoints
    timeEntries: {
        async list(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/time-entries${query ? '?' + query : ''}`);
        },

        async get(entryId) {
            return API.request(`/time-entries/${entryId}`);
        },

        async create(entryData) {
            return API.request('/time-entries', {
                method: 'POST',
                body: JSON.stringify(entryData)
            });
        },

        async update(entryId, entryData) {
            return API.request(`/time-entries/${entryId}`, {
                method: 'PUT',
                body: JSON.stringify(entryData)
            });
        },

        async delete(entryId) {
            return API.request(`/time-entries/${entryId}`, {
                method: 'DELETE'
            });
        },

        async submit(entryId) {
            return API.request(`/time-entries/${entryId}/submit`, {
                method: 'POST'
            });
        },

        async verify(entryId) {
            return API.request(`/time-entries/${entryId}/verify`, {
                method: 'POST'
            });
        },

        async reject(entryId, reason) {
            return API.request(`/time-entries/${entryId}/reject`, {
                method: 'POST',
                body: JSON.stringify({ reason })
            });
        },

        async bulkSubmit(entryIds) {
            return API.request('/time-entries/bulk-submit', {
                method: 'POST',
                body: JSON.stringify({ entry_ids: entryIds })
            });
        },

        async bulkVerify(entryIds) {
            return API.request('/time-entries/bulk-verify', {
                method: 'POST',
                body: JSON.stringify({ entry_ids: entryIds })
            });
        },

        async getMySummary() {
            return API.request('/time-entries/my-summary');
        },

        async groupedByJob(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/time-entries/grouped-by-job${query ? '?' + query : ''}`);
        }
    },

    // Reports endpoints
    reports: {
        async dashboard() {
            return API.request('/reports/dashboard');
        },

        async payroll(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/payroll${query ? '?' + query : ''}`);
        },

        async payrollDetail(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/payroll-detail${query ? '?' + query : ''}`);
        },

        async technicianHours(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/technician-hours${query ? '?' + query : ''}`);
        },

        async jobBilling(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/job-billing${query ? '?' + query : ''}`);
        },

        async incomeExpense(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/income-expense${query ? '?' + query : ''}`);
        },

        async platformSummary(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/platform-summary${query ? '?' + query : ''}`);
        },

        async auditLog(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/audit-log${query ? '?' + query : ''}`);
        },

        async payPeriods(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/reports/pay-periods${query ? '?' + query : ''}`);
        },

        async createPayPeriod(data) {
            return API.request('/reports/pay-periods', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        async closePayPeriod(periodId) {
            return API.request(`/reports/pay-periods/${periodId}/close`, {
                method: 'POST'
            });
        },

        async generatePayPeriods(data) {
            return API.request('/reports/pay-periods/generate', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        async deletePayPeriod(periodId) {
            return API.request(`/reports/pay-periods/${periodId}`, {
                method: 'DELETE'
            });
        }
    },

    // Technicians endpoints
    technicians: {
        async list(params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/technicians${query ? '?' + query : ''}`);
        },

        async get(techId) {
            return API.request(`/technicians/${techId}`);
        },

        async create(techData) {
            return API.request('/technicians', {
                method: 'POST',
                body: JSON.stringify(techData)
            });
        },

        async update(techId, techData) {
            return API.request(`/technicians/${techId}`, {
                method: 'PUT',
                body: JSON.stringify(techData)
            });
        },

        async delete(techId) {
            return API.request(`/technicians/${techId}`, {
                method: 'DELETE'
            });
        },

        async createUserAccount(techId, password, email = null) {
            return API.request(`/technicians/${techId}/create-user`, {
                method: 'POST',
                body: JSON.stringify({ password, email })
            });
        },

        async linkUser(techId, userId) {
            return API.request(`/technicians/${techId}/link-user`, {
                method: 'POST',
                body: JSON.stringify({ user_id: userId })
            });
        }
    },

    // Settings endpoints
    settings: {
        async list() {
            return API.request('/settings');
        },

        async get(key) {
            return API.request(`/settings/${key}`);
        },

        async update(key, data) {
            return API.request(`/settings/${key}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        async create(data) {
            return API.request('/settings', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        async getMileageRates() {
            return API.request('/settings/mileage-rates');
        },

        async createMileageRate(data) {
            return API.request('/settings/mileage-rates', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        async getCurrentMileageRate() {
            return API.request('/settings/mileage-rates/current');
        },

        async getJobPay(jobId) {
            return API.request(`/settings/pay/job/${jobId}`);
        },

        async getTechPay(techId, params = {}) {
            const query = new URLSearchParams(params).toString();
            return API.request(`/settings/pay/technician/${techId}${query ? '?' + query : ''}`);
        },

        // Backup/Restore
        async listBackups() {
            return API.request('/settings/backups');
        },

        async createBackup(label = '') {
            return API.request('/settings/backups', {
                method: 'POST',
                body: JSON.stringify({ label })
            });
        },

        async restoreBackup(filename) {
            return API.request(`/settings/backups/${filename}/restore`, {
                method: 'POST'
            });
        },

        async deleteBackup(filename) {
            return API.request(`/settings/backups/${filename}`, {
                method: 'DELETE'
            });
        },

        // Safe Mode
        async getSafeModeStatus() {
            return API.request('/settings/safe-mode');
        },

        async enterSafeMode() {
            return API.request('/settings/safe-mode/enter', {
                method: 'POST'
            });
        },

        async commitSafeMode() {
            return API.request('/settings/safe-mode/commit', {
                method: 'POST'
            });
        },

        async revertSafeMode() {
            return API.request('/settings/safe-mode/revert', {
                method: 'POST'
            });
        },

        // SMS Settings
        async getSmsSettings() {
            return API.request('/settings/sms');
        },

        async updateSmsSettings(data) {
            return API.request('/settings/sms', {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        async testSms(phoneNumber) {
            return API.request('/settings/sms/test', {
                method: 'POST',
                body: JSON.stringify({ phone_number: phoneNumber })
            });
        }
    },

    // Assignments endpoints
    assignments: {
        async getJobAssignments(jobId) {
            return API.request(`/assignments/job/${jobId}`);
        },

        async getTechAssignments(techId) {
            return API.request(`/assignments/technician/${techId}`);
        },

        async getMyAssignedJobs() {
            return API.request('/assignments/my-jobs');
        },

        async assignTechnicians(jobId, techIds, sendSms = true, notes = '') {
            return API.request(`/assignments/job/${jobId}`, {
                method: 'POST',
                body: JSON.stringify({ tech_ids: techIds, send_sms: sendSms, notes })
            });
        },

        async removeAssignment(assignmentId) {
            return API.request(`/assignments/${assignmentId}`, {
                method: 'DELETE'
            });
        },

        async resendAssignmentSms(assignmentId) {
            return API.request(`/assignments/${assignmentId}/resend-sms`, {
                method: 'POST'
            });
        },

        async getSmsStatus() {
            return API.request('/assignments/sms-status');
        }
    }
};
