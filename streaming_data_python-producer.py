# python-producer.py

import pandas as pd
import json
from datetime import datetime
import time
from kafka import KafkaProducer

# Config
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']
KAFKA_TOPIC = 'clickstream-events'
CSV_PATH = '../data/df_contaminated.csv'
BATCH_SIZE = 100
EVENTS_PER_SECOND = 10000

# Initialize Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def row_to_json(row):
    """Converts pandas row into a json event"""
    event = {
        "timestamp": row.timestamp_readable,
        "visitor_id": str(row.visitorid),
        "event_type": row.event,
        "item_id": str(row.itemid),
        "transaction_id": str(row.transactionid) if pd.notna(row.transactionid) else None,
        "device": row.device,
        "browser": row.browser,
        "os": row.os
    }
    return event
# Converted all three _id columns in strings as they are not integers. Also avoiding potentiall issues with trailing zeroes.
# transaction_id: Since this is often None, this is also handled here .

# Read in chunks (batches)
total_events = 0

for chunk in pd.read_csv(CSV_PATH, chunksize=BATCH_SIZE):
    batch_count = 0
    
    for _, row in chunk.iterrows():
        event = row_to_json(row)
        
        # Sent eventto kafka
        producer.send(KAFKA_TOPIC, value=event)
        
        batch_count += 1
        total_events += 1
    
    print(f"Sent {batch_count} events (Total: {total_events})")
    
    # Rate limiting
    time.sleep(BATCH_SIZE / EVENTS_PER_SECOND)

print(f"\nDone! Sent {total_events} events total")
producer.flush()
producer.close()

# Chunked reading: Instead of loading all 2.7M rows into memory, pandas reads and yields 100 rows at a time (streaming approach).
# This keeps memory usage low (~100 rows in RAM vs 2.7M rows).