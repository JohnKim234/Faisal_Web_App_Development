import time
from generate_graphs import generate_graphs
from recommendations import generate_recommendations

print("Background tasks started...")

while True:
    try:
        # Generate updated graphs
        generate_graphs()

        # Generate recommendations:
        generate_recommendations()

        print("Updated graphs & recommendations")

    except Exception as e:
        print(f"Error in background task: {e}")

    # Wait 5 seconds before updating again
    time.sleep(5)