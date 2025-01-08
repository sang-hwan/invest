# test.py

import os
import subprocess

def test_all():
    """
    Simple test script that runs the main functions of each module in sequence.
    Assumes that data_collector.py, summarize_content.py, and sentiment_analysis.py
    are in the same directory.
    """
    # 1) Run data collection
    print("[TEST] Running data_collector.py...")
    subprocess.run(["python", "data_collector.py"], check=True)

    # 2) Summarize collected data
    print("[TEST] Running summarize_content.py...")
    subprocess.run(["python", "summarize_content.py"], check=True)

    # 3) Analyze sentiment
    print("[TEST] Running sentiment_analysis.py...")
    subprocess.run(["python", "sentiment_analysis.py"], check=True)

    print("[TEST] All steps completed.")

if __name__ == "__main__":
    test_all()

