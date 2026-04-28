import requests
import json
import os

BASE_URL = "http://localhost:5000/api"

class APIService:
    def __init__(self):
        self.token = self._load_token()

    def _load_token(self):
        if os.path.exists('session.json'):
            try:
                with open('session.json', 'r') as f:
                    data = json.load(f)
                    return data.get('token')
            except:
                return None
        return None

    def _get_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def login(self, email, password):
        try:
            response = requests.post(f"{BASE_URL}/auth/login", 
                                     json={"email": email, "password": password})
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                from datetime import datetime
                with open('session.json', 'w') as f:
                    json.dump({
                        "user": data['name'], 
                        "role": data['role'], 
                        "email": email, 
                        "token": self.token,
                        "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, f)
                return True, data
            else:
                return False, response.json().get('message', 'Login failed')
        except Exception as e:
            return False, str(e)

    def register(self, name, email, password, role, department):
        try:
            response = requests.post(f"{BASE_URL}/auth/register", 
                                     json={
                                         "name": name, 
                                         "email": email, 
                                         "password": password, 
                                         "role": role, 
                                         "department": department
                                     })
            if response.status_code == 201:
                return True, response.json()
            else:
                return False, response.json().get('message', 'Registration failed')
        except Exception as e:
            return False, str(e)

    # Projects
    def get_projects(self):
        try:
            response = requests.get(f"{BASE_URL}/projects", headers=self._get_headers())
            return response.json() if response.status_code == 200 else []
        except:
            return []

    def create_project(self, project_data):
        try:
            response = requests.post(f"{BASE_URL}/projects", 
                                     json=project_data, 
                                     headers=self._get_headers())
            return response.status_code == 201
        except:
            return False

    # Tasks
    def get_tasks(self):
        try:
            response = requests.get(f"{BASE_URL}/tasks", headers=self._get_headers())
            return response.json() if response.status_code == 200 else []
        except:
            return []

    def update_task(self, task_id, task_data):
        try:
            response = requests.put(f"{BASE_URL}/tasks/{task_id}", 
                                    json=task_data, 
                                    headers=self._get_headers())
            return response.status_code == 200
        except:
            return False

    # Users
    def get_users(self):
        try:
            response = requests.get(f"{BASE_URL}/users", headers=self._get_headers())
            return response.json() if response.status_code == 200 else []
        except:
            return []

    def get_profile(self):
        try:
            response = requests.get(f"{BASE_URL}/auth/profile", headers=self._get_headers())
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.json().get('message', 'Failed to fetch profile')
        except Exception as e:
            return False, str(e)

# Create a singleton instance
api = APIService()
