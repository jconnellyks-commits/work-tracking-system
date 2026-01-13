"""
Gunicorn configuration for Work Tracking System.
"""
import multiprocessing

# Bind to localhost - nginx handles external connections
bind = "127.0.0.1:8000"

# Workers - for a small VM, 2-4 workers is usually sufficient
workers = 2

# Worker class
worker_class = "sync"

# Timeout for worker processes (seconds)
timeout = 120

# Graceful timeout
graceful_timeout = 30

# Keep-alive connections
keepalive = 5

# Maximum requests per worker before restart (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/var/log/work-tracking/gunicorn-access.log"
errorlog = "/var/log/work-tracking/gunicorn-error.log"
loglevel = "info"

# Process naming
proc_name = "work-tracking"

# Preload app for faster worker spawning
preload_app = True

# Daemon mode - disabled since systemd manages the process
daemon = False
