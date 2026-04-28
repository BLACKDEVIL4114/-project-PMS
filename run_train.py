from ai_engine import PerformanceAI
import json
import os

if __name__ == "__main__":
    ai = PerformanceAI()
    result = ai.train()
    print(json.dumps(result, indent=2))
    
    # Also save to a file for verification
    with open("training_result.json", "w") as f:
        json.dump(result, f, indent=2)
