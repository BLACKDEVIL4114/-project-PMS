# PMS v2.0 Backend (Node.js + Express + MongoDB)

This is the backend API for the Project Monitoring System, built with Node.js, Express, and MongoDB.

## Tech Stack
- **Node.js**: Runtime environment
- **Express**: Web framework
- **MongoDB**: NoSQL database (via Mongoose)
- **JWT**: For secure authentication
- **Bcryptjs**: For password hashing

## Getting Started

### Prerequisites
- Node.js installed
- MongoDB installed and running locally

### Installation
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Configure Environment Variables:
   Update the `.env` file with your `MONGO_URI` and `JWT_SECRET`.

### Running the Server
```bash
node server.js
```

## API Endpoints

### Auth
- `POST /api/auth/register`: Register a new user
- `POST /api/auth/login`: Login and get token
- `GET /api/auth/profile`: Get user profile (Protected)

### Projects
- `GET /api/projects`: Get all projects (Protected)
- `POST /api/projects`: Create a project (Admin/Manager)
- `GET /api/projects/:id`: Get project details (Protected)
- `PUT /api/projects/:id`: Update project (Admin/Manager)
- `DELETE /api/projects/:id`: Delete project (Admin)

### Tasks
- `GET /api/tasks`: Get all tasks (Protected)
- `POST /api/tasks`: Create a task (Admin/Manager/TL)
- `GET /api/tasks/:id`: Get task details (Protected)
- `PUT /api/tasks/:id`: Update task (Protected)
- `DELETE /api/tasks/:id`: Delete task (Admin/Manager)

### Users
- `GET /api/users`: Get all users (Admin)
- `PUT /api/users/:id`: Update user (Admin)
- `DELETE /api/users/:id`: Delete user (Admin)
