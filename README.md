# Kafka Clickstream Producer & Consumer
> **A lightweight Kafka-based pipeline that simulates user clickstream data and persists it as Parquet for downstream analytics**

---

## Purpose & Context

This tool sis part of a larger **end-to-end business case** for a fictional electronics retailer dealing with mysterious conversion drops. The whole project simulates realistic user behavior, ingests it through streaming infrastructure, and makes it analytically usable for downstream troubleshooting.

This repository focuses **exclusively on the streaming layer**.think of it as the data highway that gets events from "what users are doing right now" into "storage we can actually query later."

The pipeline has two main actors:
* A **Kafka Producer** that reads historical clickstream data and replays it as if users were browsing in real-time
* A **Kafka Consumer** that catches those events, applies some light business logic, and writes them to disk as Parquet files

---

## High-Level Architecture

```
CSV (Clickstream Data)
        ↓
Kafka Producer (Python)
        ↓
Kafka Topic (clickstream-events)
        ↓
Kafka Consumer (Python)
        ↓
Parquet Files (Analytics-Ready)
```

really Nothing fancy here.events flow in one direction, each component has a clear job, and theres no clever shortcuts that make debugging hell later.

---

## Design Philosophy

### Streaming Over Batch, even when not necessary :D

I could have just converted the CSV directly to Parquet in 30 seconds with pandas. But that would miss the entire point of demonstrating streaming architecture. Real e-commerce sites dont get their clickstream data as convenient CSV files.they get a firehose of events from Google Analytics, Segment, or custom tracking pixels.

I explicitly chose Kafka streaming over direct batch conversion because it demonstrates understanding of how production systems actually work. A rate limiter doses the clickstream with 1000 events per second, simulating a real world environment.

### Memory Efficiency Through Chunking

The producer reads a 1GB CSV file. Loading that entirely into memory would work on my development machine, but helps not with production constraints. Instead, we use Pandas `chunksize=100` parameter to stream the CSV in small batches. This keeps memory usage flat regardless of file size.

On the consumer side the events are batched in bundles of 500 to avoid writing too much tiny files to the disk, and also throttling the disk-usage a bit. 500 seemed like a nice batch size after testing some.

### Responsibility Split

The producers job is simulation and transport, It doesnt know or care what happens to events after they hit Kafka. It just reads formats and sends. The consumers job is business logic and persistence. It subscribes processes and writes. Neither component talks to the other directly.

This separation means, you can replace the producer (maybe with a real GA4 webhook) without touching the consumer. Or swap the consumer without touching the producer. (Loose coupeling)

### Analytics-First Storage Format

I explicitly chose Parquet over PostgreSQL after spending several hours fighting ODBC encoding issues (see project log for the whole mess). This wasnt the original plan as I wanted events in TimescaleDB, a proper time-series database with SQL querying. But after hitting endless authentication failures I had to make a call: keep debugging or pivot to something that works and finally proced.

Parquet won because it loads instantly, its common with snowflake and databricks, has a 10x compression and is perfect for analytics queries. Even PoewrBI loves it <3

Looking back, the PostgreSQL fight taught me that sometimes it is OK to give up, especially when you have the choice of the tool you use. I would loved to solve it via PostgreSQL, but keep this part a bit rough, as the goal was speed, not perfection.

---

## Producer: Clickstream Simulator

Lets get into the tech! The producers job is turning historical CSV data into a realistic event stream. It reads the contaminated clickstream file (where we injected the Safari iOS bug) and replays it through Kafka as if users were browsing right now.

**How it works:**

Pandas reads the CSV in chunks of 100 rows at a time.keeps memory usage constant even with multi-million row files. For each row, we extract the event fields (timestamp, visitor ID, event type, item ID, transaction ID, device, browser, OS) and stuff them into a JSON message.

The producer then sends messages to Kafkas `clickstream-events` topic using the kafka-python library.

**Rate limiting:**

Without throttling, the producer would blast all 2.7M events in seconds! Thats unrealistic and doesnt test the consumers ability to handle sustained load, therefore I limited it to a set amount of events per second (I think 1000 in the code currently)

**Event schema (simplified):**
```json
{
  "timestamp": "2015-06-01 10:00:00",
  "visitor_id": "12345",
  "event_type": "transaction",
  "item_id": "67890",
  "transaction_id": "tx_001",
  "device": "mobile",
  "browser": "safari",
  "os": "ios"
}
```
---

## Consumer: Business Logic & Persistence

The consumer subscribes to the `clickstream-events` topic and writes events to Parquet files in batches. It uses a Kafka consumer group, which means multiple consumers could run in parallel (each handling different partitions) if we needed to scale up. For this project, a single consumer is OK.

**File naming:**

Each Parquet file gets a timestamp in the filename (`clickstream_20250127_143052.parquet`). This makes it easy to:
- See when data was written
- Sort files chronologically
- Clean up old batches if needed
- Debug issues by correlating file timestamps with logs

**Offset handling:**

The consumer uses `auto_offset_reset=earliest` by purpose, though in production you woud rather use `latest`. which means if it starts with no stored offset, it reads from the beginning of the topic. This is perfect for demos and testing.you can move away the Parquet files and reprocess everything by restarting the consumer with a new group ID.

---

## Kafka Topic Configuration

**Topic name:** `clickstream-events`

**Semantic:** One message = one user interaction

Events dont get batched into arrays or compressed into summary statistics at the topic level. Each click, cart addition, or purchase is its own message. This keeps producer and consumer logic simple and makes the topic easy to reason about.

**Retention:**

Default Kafka retention is 7 days which is fine for this demo. In production, clickstream retention depends on business needs. If youre just using Kafka for transport (events immediately land in a data lake), short retention (hours) is enough. If Kafka is your source of truth for replay/reprocessing, you might retain weeks or months though.
