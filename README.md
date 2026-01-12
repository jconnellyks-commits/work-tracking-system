# Work Tracking System

A comprehensive work tracking system built with MySQL database, web-based forms for data entry, and dynamic reports for payroll, billing, and profit analysis. Designed for field service teams managing multiple job platforms and technicians.

**Built with:** Python/Flask | MySQL | Google Cloud Platform (GCP) | Logging & Audit Trails

---

## Quick Links

- **[Setup Guide](./docs/SETUP_GUIDE.md)** - How to get the system running on GCP
- - **[Architecture Overview](./docs/ARCHITECTURE.md)** - System design and components
  - - **[Database Schema](./docs/DATABASE_SCHEMA.md)** - Complete schema documentation
    - - **[API Documentation](./docs/API_DOCS.md)** - REST API endpoints and usage
      - - **[Development Guide](./docs/DEVELOPMENT.md)** - Setup for developers and future maintenance
        - - **[User Guide](./docs/USER_GUIDE.md)** - How to use the system
          - - **[Troubleshooting](./docs/TROUBLESHOOTING.md)** - Common issues and solutions
           
            - ---

            ## Features

            ### Data Entry
            - ✅ Web forms for technicians to log hours
            - - ✅ Support for multiple job platforms (WorkMarket, FieldNation, TechLink, Tech Service Today, Internal, Direct)
              - - ✅ Automatic time calculation
                - - ✅ Data validation and error handling
                  - - ✅ Audit trail for all entries
                   
                    - ### Reports & Analytics
                    - - 📊 **Payroll Reports** - Hours worked per tech per period
                      - - 💰 **Billing Reports** - Job billing amounts and status
                        - - 📈 **Profit Analysis** - Revenue minus labor costs
                          - - 👥 **Tech Performance** - Hours, jobs, and earnings by technician
                            - - 📅 **Pay Period Management** - Bi-weekly period tracking
                             
                              - ### Administration
                              - - 👤 User management with role-based access (Admin, Technician, Manager)
                                - - 🔐 Secure authentication and authorization
                                  - - 📝 Complete audit logging of all activities
                                    - - 🔍 Activity monitoring dashboard
                                      - - 📋 Data verification workflows
                                       
                                        - ---

                                        ## Project Structure

                                        ```
                                        work-tracking-system/
                                        ├── database/
                                        │   ├── schema.sql              # Database schema creation
                                        │   ├── seed_data.sql           # Sample data for testing
                                        │   └── migration_scripts/       # Database updates and migrations
                                        ├── app/
                                        │   ├── main.py                 # Flask application entry point
                                        │   ├── config.py               # Configuration settings
                                        │   ├── routes/                 # API and web routes
                                        │   │   ├── auth.py            # Authentication routes
                                        │   │   ├── jobs.py            # Job management
                                        │   │   ├── time_entries.py    # Time logging
                                        │   │   └── reports.py         # Report generation
                                        │   ├── models/                 # Database models
                                        │   ├── utils/
                                        │   │   ├── logging.py         # Logging system
                                        │   │   ├── auth.py            # Authentication helpers
                                        │   │   └── email.py           # Email notifications
                                        │   ├── templates/              # HTML templates
                                        │   │   ├── forms/             # Data entry forms
                                        │   │   ├── reports/           # Report displays
                                        │   │   └── admin/             # Admin dashboard
                                        │   └── static/                 # CSS, JavaScript, images
                                        ├── docs/
                                        │   ├── SETUP_GUIDE.md          # Step-by-step setup
                                        │   ├── ARCHITECTURE.md         # System design
                                        │   ├── DATABASE_SCHEMA.md      # Full database docs
                                        │   ├── API_DOCS.md             # API reference
                                        │   ├── DEVELOPMENT.md          # Developer guide
                                        │   ├── USER_GUIDE.md           # End-user documentation
                                        │   ├── TROUBLESHOOTING.md      # Solutions to common issues
                                        │   └── DIAGRAMS/               # ER diagrams, flow charts
                                        ├── tests/
                                        │   ├── test_api.py             # API tests
                                        │   ├── test_models.py          # Model tests
                                        │   └── test_reports.py         # Report generation tests
                                        ├── requirements.txt            # Python dependencies
                                        ├── .env.example                # Environment variables template
                                        ├── .gitignore                  # Git ignore rules
                                        └── README.md                   # This file
                                        ```

                                        ---

                                        ## Getting Started (Quick Start)

                                        ### Prerequisites
                                        - Google Cloud Platform (GCP) account with billing enabled
                                        - - Python 3.9 or higher
                                          - - MySQL 8.0 or higher
                                            - - Git
                                             
                                              - ### Installation
                                             
                                              - 1. **Clone the repository**
                                                2.    ```bash
                                                         git clone https://github.com/jconnellyks-commits/work-tracking-system.git
                                                         cd work-tracking-system
                                                         ```

                                                      2. **Follow the [Setup Guide](./docs/SETUP_GUIDE.md)**
                                                      3.    - Set up GCP Cloud SQL instance
                                                            -    - Create database and tables
                                                                 -    - Configure environment variables
                                                                      -    - Deploy the Flask application
                                                                       
                                                                           - 3. **Initialize the database**
                                                                             4.    ```bash
                                                                                      mysql -u admin -p work_tracking_db < database/schema.sql
                                                                                      ```

                                                                                   4. **Install dependencies**
                                                                                   5.    ```bash
                                                                                            pip install -r requirements.txt
                                                                                            ```

                                                                                         5. **Run the application**
                                                                                         6.    ```bash
                                                                                                  python app/main.py
                                                                                                  ```

                                                                                               Access the application at `http://localhost:5000`

                                                                                           ---

                                                                                     ## System Overview

                                                                               ### Core Components

                                                                             1. **MySQL Database** - Centralized data storage with tables for:
                                                                             2.    - Technicians
                                                                                   -    - Jobs (from all platforms)
                                                                                        -    - Time Entries with audit trails
                                                                                             -    - Users and Permissions
                                                                                                  -    - Pay Periods
                                                                                                       -    - Invoices and Billing
                                                                                                        
                                                                                                            - 2. **Flask Web Application** - Handles:
                                                                                                              3.    - User authentication and authorization
                                                                                                                    -    - Data entry forms
                                                                                                                         -    - Report generation
                                                                                                                              -    - API endpoints
                                                                                                                                   -    - Activity logging
                                                                                                                                    
                                                                                                                                        - 3. **Logging System** - Tracks:
                                                                                                                                          4.    - Data entries and modifications
                                                                                                                                                -    - User actions
                                                                                                                                                     -    - System errors
                                                                                                                                                          -    - Report generation
                                                                                                                                                               -    - All changes with timestamps and user info
                                                                                                                                                                
                                                                                                                                                                    - ---
                                                                                                                                                                    
                                                                                                                                                                    ## Database Schema Highlights
                                                                                                                                                                    
                                                                                                                                                                    Key tables and relationships:
                                                                                                                                                                    
                                                                                                                                                                    - **technicians** - Team members (Mike, JC, etc.)
                                                                                                                                                                    - - **platforms** - Job platforms (WorkMarket, FieldNation, etc.)
                                                                                                                                                                      - - **jobs** - Job listings with ticket numbers and billing info
                                                                                                                                                                      - **time_entries** - Hours logged by technicians with audit trails
                                                                                                                                                                      - - **users** - System users with role-based access
                                                                                                                                                                        - - **pay_periods** - Bi-weekly tracking periods
                                                                                                                                                                          - - **audit_logs** - Complete activity history
                                                                                                                                                                            - - **invoices** - Billing records
                                                                                                                                                                             
                                                                                                                                                                              - See [Database Schema](./docs/DATABASE_SCHEMA.md) for complete details.
                                                                                                                                                                             
                                                                                                                                                                              - ---
                                                                                                                                                                              
                                                                                                                                                                              ## Logging & Audit Trails
                                                                                                                                                                              
                                                                                                                                                                              Every action in the system is logged with:
                                                                                                                                                                              - ✅ Who performed the action (user ID)
                                                                                                                                                                              - - ✅ What action was performed (entry created, modified, deleted)
                                                                                                                                                                                - - ✅ When it happened (timestamp)
                                                                                                                                                                                  - - ✅ What data was affected (job ID, tech ID, etc.)
                                                                                                                                                                                    - - ✅ Old vs. new values for modifications
                                                                                                                                                                                     
                                                                                                                                                                                      - This allows you to:
                                                                                                                                                                                      - - Track all changes to the system
                                                                                                                                                                                        - - Audit user actions
                                                                                                                                                                                          - - Verify data integrity
                                                                                                                                                                                            - - Troubleshoot issues
                                                                                                                                                                                              - - Maintain compliance
                                                                                                                                                                                               
                                                                                                                                                                                                - ---
                                                                                                                                                                                                
                                                                                                                                                                                                ## User Roles
                                                                                                                                                                                                
                                                                                                                                                                                                ### Admin
                                                                                                                                                                                                - Full system access
                                                                                                                                                                                                - User management
                                                                                                                                                                                                - - System configuration
                                                                                                                                                                                                  - - View all reports and audit logs
                                                                                                                                                                                                    - - Data management and corrections
                                                                                                                                                                                                     
                                                                                                                                                                                                      - ### Manager
                                                                                                                                                                                                      - - View all technician data
                                                                                                                                                                                                        - - Generate reports
                                                                                                                                                                                                          - - Manage pay periods
                                                                                                                                                                                                            - - View audit logs
                                                                                                                                                                                                             
                                                                                                                                                                                                              - ### Technician
                                                                                                                                                                                                              - Enter their own time entries
                                                                                                                                                                                                              - View their own data
                                                                                                                                                                                                              - - Submit forms
                                                                                                                                                                                                              - No access to other technician data
                                                                                                                                                                                                             
                                                                                                                                                                                                              - ---
                                                                                                                                                                                                              
                                                                                                                                                                                                              ## Reports Available
                                                                                                                                                                                                              
                                                                                                                                                                                                              1. **Payroll Report** - Hours per tech per pay period
                                                                                                                                                                                                              2. 2. **Billing Report** - Job completions and billing status
                                                                                                                                                                                                                 3. 3. **Profit Analysis** - Revenue vs. labor costs
                                                                                                                                                                                                                    4. 4. **Tech Performance** - Productivity metrics
                                                                                                                                                                                                                       5. 5. **Activity Log** - Audit trail of all system changes
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Configuration
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       The system uses environment variables. Copy `.env.example` to `.env` and configure:
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ```bash
                                                                                                                                                                                                                       # Database
                                                                                                                                                                                                                       MYSQL_HOST=your-cloud-sql-instance
                                                                                                                                                                                                                       MYSQL_USER=admin
                                                                                                                                                                                                                       MYSQL_PASSWORD=your-password
                                                                                                                                                                                                                       MYSQL_DATABASE=work_tracking_db
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       # Flask
                                                                                                                                                                                                                       FLASK_ENV=production
                                                                                                                                                                                                                       SECRET_KEY=your-secret-key

                                                                                                                                                                                                                       # Email (for notifications)
                                                                                                                                                                                                                       MAIL_SERVER=smtp.gmail.com
                                                                                                                                                                                                                       MAIL_PORT=587
                                                                                                                                                                                                                       MAIL_USERNAME=your-email@gmail.com
                                                                                                                                                                                                                       MAIL_PASSWORD=your-app-password
                                                                                                                                                                                                                       ```
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       See [Setup Guide](./docs/SETUP_GUIDE.md) for detailed configuration.
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Documentation Files
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       This repository contains comprehensive documentation:
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       | Document | Purpose |
                                                                                                                                                                                                                       |----------|---------|
                                                                                                                                                                                                                       | **SETUP_GUIDE.md** | Step-by-step instructions to get running |
                                                                                                                                                                                                                       | **ARCHITECTURE.md** | System design and how components work together |
                                                                                                                                                                                                                       | **DATABASE_SCHEMA.md** | Complete database documentation |
                                                                                                                                                                                                                       | **API_DOCS.md** | REST API endpoints and request/response formats |
                                                                                                                                                                                                                       | **DEVELOPMENT.md** | Guide for developers making changes |
                                                                                                                                                                                                                       | **USER_GUIDE.md** | How end-users operate the system |
                                                                                                                                                                                                                       | **TROUBLESHOOTING.md** | Solutions to common problems |
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Logging & Monitoring
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       The system includes:
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       - **Application Logs** - Flask/Python logging to files and console
                                                                                                                                                                                                                       - **Database Logs** - MySQL query logs and activity
                                                                                                                                                                                                                       - **Audit Logs** - Complete user action audit trail
                                                                                                                                                                                                                       - **Error Logging** - Detailed error tracking
                                                                                                                                                                                                                       - **Performance Logs** - Report generation times and system performance
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       View logs in the Admin Dashboard or access log files in `/app/logs/`
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Support & Maintenance
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ### For Future Developers
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       When picking up this project:
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       1. Start with **[DEVELOPMENT.md](./docs/DEVELOPMENT.md)** to understand the setup
                                                                                                                                                                                                                       2. Review **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** to understand the design
                                                                                                                                                                                                                       3. Check **[DATABASE_SCHEMA.md](./docs/DATABASE_SCHEMA.md)** for data structures
                                                                                                                                                                                                                       4. Review the **audit logs** to see what's been changed recently
                                                                                                                                                                                                                       5. See the **Git commit history** for recent changes
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       All code is commented and follows best practices for maintainability.
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ### Getting Help
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       - Check **[TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)** for common issues
                                                                                                                                                                                                                       - Review the **audit logs** for what's been modified
                                                                                                                                                                                                                       - Check **comments in code** for implementation details
                                                                                                                                                                                                                       - Review **Git history** for recent changes
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Technology Stack
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       - **Backend:** Python 3.9+, Flask
                                                                                                                                                                                                                       - **Database:** MySQL 8.0+
                                                                                                                                                                                                                       - **Hosting:** Google Cloud Platform (GCP)
                                                                                                                                                                                                                       - **Database Hosting:** Cloud SQL
                                                                                                                                                                                                                       - **Frontend:** HTML5, CSS3, JavaScript
                                                                                                                                                                                                                       - **Authentication:** Flask-Login with role-based access control
                                                                                                                                                                                                                       - **Logging:** Python logging module + custom audit system
                                                                                                                                                                                                                       - **Version Control:** Git/GitHub
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## License
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       This project is private and proprietary to the owner.
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Project Status
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       🚀 **MVP Development In Progress**
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       Current Phase: Foundation & Core Documentation
                                                                                                                                                                                                                       - ✅ Repository created
                                                                                                                                                                                                                       - ✅ Project structure defined
                                                                                                                                                                                                                       - ✅ Documentation framework in place
                                                                                                                                                                                                                       - ⏳ Database schema implementation
                                                                                                                                                                                                                       - ⏳ Flask application development
                                                                                                                                                                                                                       - ⏳ Form creation
                                                                                                                                                                                                                       - ⏳ Report generation
                                                                                                                                                                                                                       - ⏳ GCP deployment
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       See individual documentation files for detailed status and next steps.
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ---
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       ## Last Updated
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       Generated: January 12, 2026
                                                                                                                                                                                                                       Repository: work-tracking-system
                                                                                                                                                                                                                       Owner: jconnellyks-commits
