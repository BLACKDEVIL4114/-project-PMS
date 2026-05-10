import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os

def train_combined_model():
    print("Loading datasets...")
    
    # 1. Load Kaggle Dataset (Project Management (1).csv)
    # Project Status: 'Behind' or 'On Track'
    # Priority: 'Medium', 'High', 'Low'
    # Progress: numeric 0-1
    try:
        df_kaggle = pd.read_csv('Project Management (1).csv')
        # Map Project Status to binary (1 for Behind, 0 for On Track)
        df_kaggle['is_delayed'] = df_kaggle['Project Status'].apply(lambda x: 1 if str(x).lower() == 'behind' else 0)
        # Map Priority to numeric
        prio_map = {'Low': 1, 'Medium': 2, 'High': 3}
        df_kaggle['priority_num'] = df_kaggle['Priority'].map(prio_map).fillna(2)
        
        # We'll use priority, hours spent, and progress as features from this one
        # To make it compatible with the final model, we'll normalize them
        kaggle_features = df_kaggle[['priority_num', 'Hours Spent', 'Progress', 'is_delayed']].copy()
        kaggle_features.columns = ['priority', 'workload', 'complexity', 'is_delayed']
        # Scale workload to match a 1-15 scale roughly
        kaggle_features['workload'] = (kaggle_features['workload'] / kaggle_features['workload'].max() * 15).fillna(5)
        # Scale complexity to 1-5
        kaggle_features['complexity'] = (kaggle_features['complexity'] * 5).fillna(3)
        # Add some dummy features for availability and experience to match the final schema
        kaggle_features['resource_availability'] = 0.7
        kaggle_features['team_experience'] = 5
        kaggle_features['estimated_days'] = 30
    except Exception as e:
        print(f"Error processing Kaggle CSV: {e}")
        kaggle_features = pd.DataFrame()

    # 2. Load GitHub Dataset (Dataset_1.xlsx)
    # Features X1.1 to X10.7, Targets Y1 to Y4
    # Y1 is often the primary delay indicator
    try:
        df_github = pd.read_excel('Dataset_1.xlsx', header=9)
        # Assuming Y1 > 3 means delay or high risk
        df_github['is_delayed'] = df_github['Y1'].apply(lambda x: 1 if x >= 4 else 0)
        
        # Map some X features to our schema
        # Let's pick representative features
        github_features = pd.DataFrame({
            'priority': df_github['X10.1'].fillna(2), # Urgency/Priority
            'workload': df_github['X8.1'].fillna(8), # Resource related
            'complexity': df_github['X1.1'].fillna(3), # Complexity related
            'resource_availability': df_github['X7.1'].apply(lambda x: x/5).fillna(0.7),
            'team_experience': df_github['X10.3'].fillna(5),
            'estimated_days': df_github['X1.2'].apply(lambda x: x*10).fillna(30),
            'is_delayed': df_github['is_delayed']
        })
    except Exception as e:
        print(f"Error processing GitHub Excel: {e}")
        github_features = pd.DataFrame()

    # 3. Combine and Train
    print("Combining data...")
    combined_df = pd.concat([kaggle_features, github_features], ignore_index=True)
    
    # Add some synthetic noise/data to fill gaps and ensure robustness
    # (Same logic as the previous train_pms_ml.py to ensure it works with the UI)
    def generate_synthetic(n=500):
        np.random.seed(42)
        priority = np.random.choice([1, 2, 3], n)
        est_days = np.random.randint(5, 60, n)
        complexity = np.random.randint(1, 6, n)
        avail = np.random.uniform(0.1, 1.0, n)
        exp = np.random.randint(1, 11, n)
        workload = np.random.randint(1, 15, n)
        prob = (0.2 * complexity + 0.15 * (1 - avail) + 0.1 * priority + 0.1 * workload/10 - 0.1 * exp/10)
        is_delayed = (prob + np.random.normal(0, 0.05, n) > 0.5).astype(int)
        return pd.DataFrame({
            'priority': priority, 'estimated_days': est_days, 'complexity': complexity,
            'resource_availability': avail, 'team_experience': exp, 'workload': workload,
            'is_delayed': is_delayed
        })
    
    syn_df = generate_synthetic(500)
    final_df = pd.concat([combined_df, syn_df], ignore_index=True).dropna()
    
    # Ensure columns are in correct order for the UI
    feature_cols = ['priority', 'estimated_days', 'complexity', 'resource_availability', 'team_experience', 'workload']
    X = final_df[feature_cols]
    y = final_df['is_delayed']
    
    print(f"Training on {len(final_df)} samples...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Save the model
    joblib.dump(model, 'pms_delay_model.joblib')
    print("Model trained and saved as 'pms_delay_model.joblib'")
    
    # Print importance
    for name, imp in zip(feature_cols, model.feature_importances_):
        print(f"  - {name}: {imp:.2%}")

if __name__ == "__main__":
    train_combined_model()
