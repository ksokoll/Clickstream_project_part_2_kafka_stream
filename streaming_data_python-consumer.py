from kafka import KafkaConsumer
import json
import pandas as pd
from datetime import datetime
import os
import time

consumer = KafkaConsumer(
    'clickstream-events',
    bootstrap_servers=['kafka:29092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id='parquet-consumer-v3',
    max_poll_records=500
)

print("Starting consumer...")
print("Connecting to Kafka...")

# Create output directory if it doesn't exist
OUTPUT_DIR = '/data/parquet_output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Connected! Listening for events...")

# Batch configuration
batch = []
BATCH_SIZE = 500  # Write every 1000 events

for message in consumer:
    try:
        event = message.value
        batch.append(event)
        
        # Write batch to Parquet when full
        if len(batch) >= BATCH_SIZE:
            df = pd.DataFrame(batch)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{OUTPUT_DIR}/events_{timestamp}.parquet'
            
            # Write to Parquet
            df.to_parquet(filename, engine='pyarrow', index=False)
            
            print(f"Saved {len(batch)} events to {filename}")
            batch = []  # Clear batch
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)
        continue

# Save remaining events on exit (if any)
if batch:
    df = pd.DataFrame(batch)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{OUTPUT_DIR}/events_{timestamp}.parquet'
    df.to_parquet(filename, engine='pyarrow', index=False)
    print(f"Saved final {len(batch)} events")