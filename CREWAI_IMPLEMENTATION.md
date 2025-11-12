# CrewAI Integration Summary

## Overview

This document summarizes the CrewAI integration that replaces the fixed-step query processing flow with an agentic, dynamic approach that can handle any type of user query.

## Problem Statement

The previous implementation had several limitations:

1. **Fixed Mapping Dependencies**: Sensor mappings were hardcoded, requiring manual updates when sensors changed
2. **Limited Query Types**: Could only handle simple queries (current values, basic trends)
3. **Fixed SQL Patterns**: SQL queries were generated using fixed patterns that couldn't adapt to complex queries
4. **No Dynamic Discovery**: Couldn't discover sensors dynamically from the database schema

### Examples of Queries That Previously Failed:

- ❌ "Calculate correlation between @glucose and @pH in cell_1"
- ❌ "Show me standard deviation of @oxygen levels"
- ❌ "What's the regression analysis of @viability over time?"
- ❌ "Show me @glucose vs @pH scatter plot for cell_1"
- ❌ "Show @glucose data from January 1st to January 15th"
- ❌ "Show me @glucose data when @pH was above 7.0"

## Solution: CrewAI Agentic Flow

### Architecture

```
User Query + @references + page_type + cell_id
    ↓
[API Endpoint: /api/chatbot/query]
    ↓
[CrewAI Service: process_query()]
    ↓
[Crew: Sequential Process]
    ↓
┌─────────────────────────────────────────┐
│ Task 1: Data Extraction Task             │
│ Agent 1: Data Extraction Agent            │
│                                           │
│ Step 0: Extract cell IDs from query      │
│   → Call get_tdengine_schema(cell_ids)   │
│   → Receives: Table structure, columns,  │
│      sensors, mappings, SQL examples       │
│                                           │
│ Step 1: Extract and normalize parameters │
│   - Cell IDs (normalize: "cell1"→"cell_1")│
│   - Sensor names (from schema/@refs)     │
│   - Time period (parse all formats)      │
│   - Query intent (correlation/stat/etc)  │
│                                           │
│ Step 2: Generate SQL queries             │
│   - Use schema info for tables/columns    │
│   - Handle multi-cell (UNION ALL)         │
│   - Handle statistics (per-cell)         │
│   - Always include time filtering         │
│                                           │
│ Step 3: Execute query                     │
│   → Call execute_tdengine_query(sql)     │
│                                           │
│ Step 4: Return structured JSON            │
│   - cells, sensors, time_range            │
│   - query_intent                          │
│   - data/statistics/correlations          │
└─────────────────────────────────────────┘
    ↓
[Structured JSON Data]
    ↓
┌─────────────────────────────────────────┐
│ Task 2: Response Generation Task         │
│ Agent 2: Response Generation Agent       │
│                                           │
│ Step 1: Analyze Agent 1's output         │
│   - Check time_range, query_intent        │
│   - Identify relevant data sections       │
│                                           │
│ Step 2: Extract information by type       │
│   - Correlation: coefficients & meaning   │
│   - Statistical: per-cell or single       │
│   - Comparison: differences & patterns     │
│   - Trend: direction & magnitude          │
│                                           │
│ Step 3: Generate natural language         │
│   - Answer in first sentence              │
│   - Include time period                   │
│   - Present per-cell results if multi     │
│   - Explain statistical results           │
│                                           │
│ Returns: Human-readable answer            │
└─────────────────────────────────────────┘
    ↓
[Final Response]
    ↓
[Return to Frontend]
```

## File Structure

```
backend/
├── crew.py                    # Main crew file (declares agents, tasks, crew)
├── crewai_service.py          # Service wrapper for API integration
├── config/
│   ├── agents.yaml           # Agent configurations
│   └── tasks.yaml            # Task configurations
├── tools/
│   ├── __init__.py
│   └── tdengine_tool.py      # TDengine query tool
└── server.py                  # Updated to use CrewAI service
```

## Key Components

### 1. TDengine Tools (`tools/tdengine_tool.py`)

**Tool 1: `get_tdengine_schema(cell_ids: str)`**
- **Purpose**: Dynamically fetch database schema information for specific cell tables
- **Features**:
  - Normalizes cell ID formats ("cell1" → "cell_1", "cell 2" → "cell_2")
  - Returns table structure (CREATE TABLE statements)
  - Returns column details (name, type, length)
  - Returns available sensors per table
  - Returns sensor name mappings (@references → subtopic)
  - Provides SQL query examples
  - Called FIRST by Agent 1 before generating queries

**Tool 2: `execute_tdengine_query(sql_query: str)`**
- **Purpose**: Execute SQL queries against TDengine database
- **Features**:
  - Executes any valid TDengine SQL query
  - Returns formatted JSON results with column names
  - Handles errors gracefully
  - Supports complex queries (JOINs, aggregations, correlations, UNION ALL, etc.)
  - Returns row count and column information

### 2. Agent Configurations (`config/agents.yaml`)

**Data Extraction Agent**:
- **Role**: Data Extraction Specialist
- **Goal**: Understand queries, extract parameters, generate SQL queries
- **Temperature**: 0.3 (lower for precise SQL generation)
- **Tools**: 
  - `get_tdengine_schema` (called first to get schema info)
  - `execute_tdengine_query` (executes generated SQL)
- **Capabilities**: 
  - Dynamic schema discovery (no static mappings)
  - Handles all cell ID formats ("cell1", "cell 1", "cell_1", etc.)
  - Parses all time formats (relative, absolute, natural language)
  - Complex query generation (JOINs, UNION ALL, aggregations)
  - Statistical analysis queries (per-cell or combined)
  - Correlation queries
  - Custom date range handling
  - Multi-cell and multi-sensor queries

**Response Generation Agent**:
- **Role**: Data Analysis and Communication Specialist
- **Goal**: Interpret data and generate clear responses
- **Temperature**: 0.7 (higher for natural language)
- **Capabilities**:
  - Statistical interpretation
  - Trend analysis explanation
  - Correlation explanation
  - Clear, accessible communication

### 3. Task Configurations (`config/tasks.yaml`)

**Data Extraction Task**:
- **Step 0**: Extract cell IDs → Call `get_tdengine_schema` tool FIRST
- **Step 1**: Extract and normalize all parameters:
  - Cell IDs (all formats normalized to "cell_N")
  - Sensor names (from schema tool output or @references)
  - Time period (all formats: relative, absolute, natural language)
  - Query intent (correlation, comparison, trend, current, statistical)
- **Step 2**: Time period handling (always includes time filtering in ISO format)
- **Step 3**: Generate SQL queries using schema information
- **Step 4**: Statistical functions (correlation, stddev, variance, covariance, etc.)
- **Step 5**: Data extraction strategy:
  - Statistical queries: Calculate per-cell if multiple cells
  - Comparison queries: Time-aligned data points
  - Trend queries: Historical points chronologically
  - Current value: Latest reading
- **Step 6**: Execute query using `execute_tdengine_query` tool
- **Step 7**: Return structured JSON with cells, sensors, time_range, query_intent, and appropriate data/statistics/correlations sections

**Response Generation Task**:
- **Step 1**: Analyze Agent 1's output (time_range, query_intent, data sections)
- **Step 2**: Extract information based on query type:
  - Correlation: Coefficient and meaning
  - Statistical (single cell): All metrics
  - Statistical (multiple cells): Per-cell comparison
  - Comparison: Differences and patterns
  - Trend: Direction and magnitude
  - Current: Latest value
- **Step 3**: Generate response:
  - Answer directly in first sentence
  - Always mention time period
  - Include specific values with units
  - For multi-cell: Present per-cell results and comparisons
  - Explain statistical results clearly
  - Keep concise (2-4 paragraphs)
- **Step 4**: Handle insufficient data gracefully
- **Step 5**: Format naturally (Answer → Details → Context)

### 4. Main Crew (`crew.py`)

- **Initialization**: 
  - Loads agent and task configs from YAML files
  - Creates agents with tools (get_tdengine_schema, execute_tdengine_query)
  - Creates base tasks from configuration
  - Initializes LLM (gemini-pro-latest)
- **Query Processing**: 
  - Creates query-specific tasks with user context
  - Builds context with page_type, cell_id, @references
  - Creates temporary crew for each query
  - Executes sequential workflow (Agent 1 → Agent 2)
  - Returns final response from Agent 2
- **No Static Schema Injection**: Schema is fetched dynamically via tool call

### 5. Service Wrapper (`crewai_service.py`)

- Provides async interface for FastAPI
- Lazy loads crew instance
- Handles errors gracefully

## Key Improvements

### 1. Dynamic Schema Discovery
- Agent 1 calls `get_tdengine_schema` tool FIRST with cell IDs from query
- Tool returns complete schema: tables, columns, sensors, mappings
- No static schema injection - everything is fetched on-demand
- No need to update mappings when sensors change
- Supports any sensor name pattern
- Schema tool normalizes cell ID formats automatically

### 2. Flexible Query Generation
- Agents generate SQL queries dynamically based on query intent and schema
- Uses schema information to identify correct tables and columns
- Supports complex queries:
  - Correlations (manual formula calculation)
  - Statistical functions (STDDEV, VAR, AVG, MIN, MAX, COUNT, SUM, PERCENTILE, etc.)
  - Multi-cell statistics (per-cell using UNION ALL)
  - Custom date ranges (all formats parsed and converted to ISO)
  - Advanced filtering (JOINs, WHERE conditions)
  - Multi-cell and multi-sensor comparisons
  - Time-aligned data for comparisons

### 3. Intelligent Parameter Extraction
- Agent handles ALL extraction and normalization (no regex/code preprocessing)
- Extracts cell IDs from query (handles all formats: "cell1", "cell 1", "cell_1", "cell one", etc.)
- Normalizes to "cell_N" format automatically
- Maps @references to sensor subtopic names using schema tool output
- Parses time periods from natural language:
  - Relative: "last X days/weeks/months", "past X days", "X days ago"
  - Absolute: "January 1st 2025", "1st Nov 2025", "Nov 1 to Nov 9 2025"
  - Relative points: "yesterday", "today", "this week", "this month"
  - Defaults to 24 hours if not specified
- Understands query intent (correlation, trend, comparison, statistical, current)
- Converts all dates to ISO format for SQL queries

### 4. Adaptive Response Generation
- Interprets complex data structures
- Explains statistical results
- Provides context-aware responses

## How It Handles Previously Failing Queries

### Example 1: Correlation Query
**Query**: "Calculate correlation between @glucose and @pH in cell_1"

**Agent 1 (Data Extraction)**:
1. Extracts cell IDs: "cell_1" from query
2. Calls `get_tdengine_schema("cell_1")` → Gets schema with sensors, mappings
3. Maps @glucose → "glucose_mM", @pH → "pH" from schema
4. Extracts time period (defaults to 24h if not specified)
5. Generates SQL to fetch both sensors' data for same time period (time-aligned)
6. Executes queries using `execute_tdengine_query` tool
7. Calculates correlation coefficient using formula: (AVG(x*y) - AVG(x)*AVG(y)) / (STDDEV(x) * STDDEV(y))
8. Returns structured JSON with correlation value, covariance, and time_range

**Agent 2 (Response Generation)**:
1. Receives correlation data
2. Explains what the correlation coefficient means
3. Provides context about the relationship

### Example 2: Custom Date Range
**Query**: "Show @glucose data from January 1st to January 15th"

**Agent 1**:
1. Extracts cell IDs from query (if mentioned)
2. Calls `get_tdengine_schema` with cell IDs to get schema
3. Extracts date range: "January 1st to January 15th" → "2024-01-01 00:00:00" to "2024-01-15 23:59:59"
4. Maps @glucose to "glucose_mM" using schema tool output
5. Generates SQL: `SELECT ts, reading, unit FROM cell_N WHERE subtopic = 'glucose_mM' AND ts >= '2024-01-01 00:00:00' AND ts <= '2024-01-15 23:59:59' ORDER BY ts ASC`
6. Executes query using `execute_tdengine_query` tool
7. Returns structured JSON with data points, time_range, and query_intent

**Agent 2**:
1. Formats the data chronologically
2. Provides summary statistics
3. Explains trends if any

### Example 3: Advanced Filtering
**Query**: "Show me @glucose data when @pH was above 7.0"

**Agent 1**:
1. Extracts cell IDs and calls `get_tdengine_schema` tool
2. Maps @glucose → "glucose_mM", @pH → "pH" from schema
3. Generates SQL with JOIN on timestamp to align data:
   ```sql
   SELECT g.ts, g.reading as glucose, p.reading as pH
   FROM cell_N g
   JOIN cell_N p ON g.ts = p.ts
   WHERE g.subtopic = 'glucose_mM' 
     AND p.subtopic = 'pH' 
     AND p.reading > 7.0
     AND g.ts >= 'YYYY-MM-DD HH:MM:SS'
   ```
4. Executes query and returns filtered, time-aligned data

**Agent 2**:
1. Explains the filtering criteria
2. Provides insights about the filtered data

### Example 4: Multi-Cell Statistical Query
**Query**: "Show me standard deviation of @oxygen levels in cell1, cell 2, cell5 and cell6 between 1st november 2025 to 9th Nov 2025"

**Agent 1**:
1. Extracts cell IDs: "cell1", "cell 2", "cell5", "cell6"
2. Normalizes to: "cell_1", "cell_2", "cell_5", "cell_6"
3. Calls `get_tdengine_schema("cell_1,cell_2,cell_5,cell_6")` → Gets schema for all cells
4. Maps @oxygen → "o2_percent" from schema
5. Extracts date range: "1st november 2025 to 9th Nov 2025" → "2025-11-01 00:00:00" to "2025-11-09 23:59:59"
6. Generates SQL with UNION ALL for per-cell statistics:
   ```sql
   SELECT 'cell_1' as cell_id, STDDEV(reading) as stddev_value, AVG(reading) as mean_value
   FROM cell_1 
   WHERE subtopic = 'o2_percent' 
   AND ts >= '2025-11-01 00:00:00' 
   AND ts <= '2025-11-09 23:59:59'
   UNION ALL
   SELECT 'cell_2' as cell_id, STDDEV(reading) as stddev_value, AVG(reading) as mean_value
   FROM cell_2 
   WHERE subtopic = 'o2_percent' 
   AND ts >= '2025-11-01 00:00:00' 
   AND ts <= '2025-11-09 23:59:59'
   -- ... (for cell_5 and cell_6)
   ```
7. Executes query and returns per-cell statistics:
   ```json
   {
     "cells": ["cell_1", "cell_2", "cell_5", "cell_6"],
     "sensors": ["o2_percent"],
     "time_range": "November 1, 2025 to November 9, 2025",
     "query_intent": "statistical",
     "statistics": {
       "cell_1": {"stddev": X, "mean": Y, ...},
       "cell_2": {"stddev": X, "mean": Y, ...},
       "cell_5": {"stddev": X, "mean": Y, ...},
       "cell_6": {"stddev": X, "mean": Y, ...}
     }
   }
   ```

**Agent 2**:
1. Receives per-cell statistics
2. Presents results per cell: "Cell 1 has stddev of X, Cell 2 has stddev of Y..."
3. Compares across cells and highlights differences
4. Mentions time period analyzed

## Dependencies

Added to `requirements.txt`:
- `crewai>=0.28.0`
- `crewai-tools>=0.1.6`
- `langchain-google-genai>=1.0.0`
- `langchain>=0.1.0`
- `pyyaml>=6.0`
