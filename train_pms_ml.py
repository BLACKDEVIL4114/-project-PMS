import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

# --- 1. Generate Synthetic Data (Combining Kaggle and GitHub features) ---
def generate_data(num_samples=1000):
    np.random.seed(42)
    
    # Kaggle-style Features
    priority = np.random.choice([1, 2, 3], num_samples) # 1: Low, 2: Medium, 3: High
    estimated_days = np.random.randint(5, 60, num_samples)
    
    # GitHub-style Features
    complexity = np.random.randint(1, 6, num_samples) # 1-5
    resource_availability = np.random.uniform(0.1, 1.0, num_samples) # 10% to 100%
    team_experience = np.random.randint(1, 11, num_samples) # 1-10 years
    workload = np.random.randint(1, 15, num_samples) # Current tasks
    
    # Target: Delay Likelihood (1: Delayed, 0: On-Time)
    # Logic: Higher complexity, lower availability, higher priority (more pressure), 
    # and higher workload increase the probability of delay.
    delay_prob = (
        0.2 * complexity + 
        0.15 * (1 - resource_availability) + 
        0.1 * priority + 
        0.1 * workload/10 - 
        0.1 * team_experience/10
    )
    
    # Add some noise
    delay_prob += np.random.normal(0, 0.05, num_samples)
    
    # Convert probability to binary target
    is_delayed = (delay_prob > 0.5).astype(int)
    
    data = pd.DataFrame({
        'priority': priority,
        'estimated_days': estimated_days,
        'complexity': complexity,
        'resource_availability': resource_availability,
        'team_experience': team_experience,
        'workload': workload,
        'is_delayed': is_delayed
    })
    
    return data

# --- 2. Train the Model ---
def train_pms_model():
    print("Generating training data...")
    df = generate_data(1500)
    
    X = df.drop('is_delayed', axis=1)
    y = df['is_delayed']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nModel Accuracy: {accuracy:.2f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save the model
    model_path = 'pms_delay_model.joblib'
    joblib.dump(model, model_path)
    print(f"\nModel saved to {model_path}")
    
    # Feature Importance (Great for Viva!)
    importances = model.feature_importances_
    feature_names = X.columns
    print("\nFeature Importances (Why tasks are delayed):")
    for name, imp in zip(feature_names, importances):
        print(f"  - {name}: {imp:.2%}")

if __name__ == "__main__":
    train_pms_model()
