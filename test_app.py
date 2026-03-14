import sys
import time
print("Importing app...")
try:
    import app
    print("Imported app successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
