# 🍽️ Smart Hotel Ordering & Management System

## 📌 Overview

The **Smart Hotel Ordering & Management System** is a digital automation platform designed to reduce crowding inside hotels, improve service efficiency, and enhance customer experience.  
Customers scan a QR code at their table, browse the menu, order food, track cooking status, and pay through UPI without waiting in queues.

Admins and cooks get dedicated dashboards to manage orders, inventory, analytics, and notifications.

---

## ✨ Key Features

### 👥 Multi-Role System
- **Customer:** Orders without login.
- **Cook:** Can view and update cooking status.
- **Admin:** Full control panel with analytics and inventory management.

### 📌 Smart Functions  
✔ Real-time menu ordering  
✔ Inventory-based menu visibility  
✔ Live kitchen status updates  
✔ QR-based ordering access  
✔ Automatic bill generation  
✔ UPI Payment simulation and payment notification  
✔ AI/Logic-based smart combo recommendations  
✔ Diet filters (Veg / Non-veg / Jain / Low calorie)

### 📊 Admin Dashboard
- Daily sales graph
- Inventory depletion tracking
- Popular dishes analytics
- Menu add/remove functionality
- Payment alerts

---

## 📁 Project Structure
Hotel_Ahanya/
│
├── app.py # Main Flask backend
├── schema.sql # Database structure & seed data
├── static/ # Images, CSS, JS
│ ├── css/
│ ├── js/
│ └── img/
├── templates/ # Web pages
│ ├── index.html
│ ├── menu.html
│ ├── cook_dashboard.html
│ ├── admin_dashboard.html
│ ├── payment.html
│ └── login.html
├── venv/ # Your virtual environment (optional)
└── README.md # Project documentation
