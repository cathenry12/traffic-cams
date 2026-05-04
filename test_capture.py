import main
import logging

logging.basicConfig(level=logging.INFO)
print("Starting capture test...")
main.job_capture_all()
main.job_capture_all()  # capture a second frame for timelapse
print("Testing timelapse generation...")
import datetime
main.generate_timelapse(target_date=datetime.datetime.now())
print("Test completed.")
