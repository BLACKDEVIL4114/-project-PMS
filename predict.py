import numpy as np
import tensorflow as tf
import joblib

# Load model & scaler
model = tf.keras.models.load_model("employee_model.h5")
scaler = joblib.load("scaler.pkl")

# Example employee data
new_employee = np.array([[
    20, 18, 2, 3.1, 92, 85, 4.2, 10
]])

# Scale
new_employee_scaled = scaler.transform(new_employee)

# Predict
prediction = model.predict(new_employee_scaled)

print("Predicted Performance Score:", prediction[0][0])
