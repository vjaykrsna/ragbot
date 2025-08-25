# Data Pipeline Unification

## Overview

The data pipeline has been restructured to improve maintainability, testability, and separation of concerns. The previous fragmented approach has been replaced with a unified pipeline that standardizes the flow from extraction to synthesis.

## New Structure

```
src/data_pipeline/
├── __init__.py          # Package entry point
└── pipeline.py          # Unified data pipeline implementation
```

## Pipeline Stages

The unified data pipeline consists of several distinct stages:

1. **DataSourceStage**: Reads messages from the database
2. **SortingStage**: Sorts messages by date
3. **AnonymizationStage**: Anonymizes sender IDs and normalizes numeric values
4. **ConversationBuildingStage**: Groups messages into conversations
5. **PersistenceStage**: Writes processed conversations to file

## Benefits

1. **Improved Separation of Concerns**: Each stage has a single responsibility
2. **Better Testability**: Individual stages can be tested in isolation
3. **Enhanced Maintainability**: Changes to one stage don't affect others
4. **Clearer Code Organization**: Related functionality is grouped together
5. **Easier Debugging**: Issues can be traced to specific stages more easily
6. **Standardized Data Flow**: Consistent data format between stages

## Usage

To use the unified data pipeline:

```python
from src.core.config import get_settings
from src.data_pipeline import create_data_pipeline

# Get application settings
settings = get_settings()

# Create the data pipeline
pipeline = create_data_pipeline(settings)

# Run the pipeline
conversation_count = pipeline.run()
```