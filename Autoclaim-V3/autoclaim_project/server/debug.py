import sys
import traceback

try:
    import app.main
    print("Import successful")
except Exception as e:
    with open("err.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print("Error caught and written to err.txt")
