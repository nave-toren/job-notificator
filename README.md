🎯 Career Agent — Smart Job Monitoring System
An autonomous Career Agent that tracks company career pages, detects new job openings, and sends personalized email alerts based on user-selected departments.
Built to scale efficiently with multiple users and companies.

🚀 How It Works (Architecture)
The system is built around a company-first scanning strategy:
 Scan each company only once per run 🔍
Career pages are scraped and all open roles are collected.
 Jobs are cached and compared to previous runs 🧠
Only new job postings are considered for alerts.
 Personalized filtering per user 👤

Each user receives only jobs that match:
The companies they follow
The departments they selected (Engineering, Product, Support, etc.)
This design allows:

Multiple users to follow the same company
One scrape → many personalized alerts
Minimal website load and faster execution


 Smart Scraping (Site-Aware) 🕵️‍♂️
The agent automatically detects which hiring platform a company uses and applies a dedicated scraper:
🟢 Greenhouse
🟣 Lever
🟡 Generic fallback for custom career pages
This improves accuracy and avoids collecting irrelevant links like:
privacy policies, blog posts, login pages, etc.
For companies without known platforms, a keyword-based fallback scraper is used


Job Classification & Filtering 🎯 
Each job is classified by department using keyword-based NLP-style matching on:
Job title
(optionally extendable to URL / page structure)
Supported categories:
Engineering
Product
Marketing
Finance
HR / Operations
Support
Only jobs matching the user's selected departments are sent by email.


Email Delivery 📬
Alerts are sent using Resend Email API:
No SMTP servers
Reliable cloud delivery
Scales easily for production use
Each email contains:
Only newly discovered jobs
Clean HTML formatting
Personalized job lists


Cloud-Ready ☁️ 
Deployed on Render with:
Background task execution
External PostgreSQL (Neon) database
Cron-ready endpoint for scheduled scans
Designed for:
Fully automated daily scanning
No manual triggers required


Tech Stack 🧱
Backend
FastAPI
Async Playwright
Scraping
Site-aware Playwright scrapers
Generic keyword-based fallback crawler
Database
PostgreSQL (Neon)
Job cache for detecting new postings
Email
Resend API
Frontend
Jinja2 templates


Why This Is Different 🎯 
Unlike simple scrapers that:
scrape per user
send duplicate traffic
lack filtering
This system:
Scrapes per company
Distributes results intelligently
Scales with users
Mimics real-world job alert platforms