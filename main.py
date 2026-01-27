print("MAIN FILE EXECUTED")

from observer import observe_desktop
from classifier import classify

def run_agent():
    print("Agent started")

    observations = observe_desktop()
    print(f"Observed {len(observations)} files")

    for f in observations:
        result = classify(f)
        print(result)

if __name__ == "__main__":
    run_agent()
