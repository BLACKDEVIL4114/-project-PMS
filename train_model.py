import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import joblib

import os
# Load CSV dataset
csv_path = "employee_data.csv"
if not os.path.exists(csv_path):
    print(f"⚠️ {csv_path} not found. Creating sample data...")
    dummy_data = {
        "tasks_assigned": np.random.randint(5, 20, 100),
        "tasks_completed": np.random.randint(0, 20, 100),
        "late_tasks": np.random.randint(0, 5, 100),
        "avg_completion_time": np.random.uniform(1, 10, 100),
        "attendance_percentage": np.random.uniform(70, 100, 100),
        "productivity_score": np.random.uniform(50, 100, 100),
        "feedback_rating": np.random.uniform(1, 5, 100),
        "overtime_hours": np.random.uniform(0, 20, 100),
        "performance_score": np.random.uniform(60, 100, 100)
    }
    data = pd.DataFrame(dummy_data)
else:
    data = pd.read_csv(csv_path)

# Features
X = data[[
    "tasks_assigned",
    "tasks_completed",
    "late_tasks",
    "avg_completion_time",
    "attendance_percentage",
    "productivity_score",
    "feedback_rating",
    "overtime_hours"
]]

# Target
y = data["performance_score"]

# Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Normalize Data
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

# Save scaler
joblib.dump(scaler, "scaler.pkl")

# Build Model
model = tf.keras.Sequential([
    tf.keras.layers.Dense(32, activation='relu', input_shape=(8,)),
    tf.keras.layers.Dense(16, activation='relu'),
    tf.keras.layers.Dense(8, activation='relu'),
    tf.keras.layers.Dense(1)
])

model.compile(
    optimizer='adam',
    loss='mse',
    metrics=['mae']
)

# Train Model
model.fit(X_train, y_train, epochs=100, batch_size=16)

# Evaluate
loss, mae = model.evaluate(X_test, y_test)
print("Test MAE:", mae)

# Save Model
model.save("employee_model.h5")

print("Model trained and saved successfully.")
