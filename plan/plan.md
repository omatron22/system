# Knowledge Graph-Based Business Analysis System

## Project Overview

This project builds an intelligent business analysis system that processes the 30 business assessment groups defined in the Qmirac Engine Guidelines (as specified in `blueprint.md`). The system takes CSV files containing business data, analyzes them according to the specific questions outlined in the blueprint, and generates three types of PDF reports with strategic recommendations.

## Understanding the Blueprint

The `blueprint.md` file defines the core structure of our system:

1. **30 Assessment Groups**: The blueprint defines 30 specific business areas to analyze, such as "Vision," "Market Assessment," "Risk Assessment," etc.

2. **Group-Specific Questions**: Each group has dedicated analysis questions. For example, the Vision group asks: "Is the Vision Statement Clear, concise, inspiring, future-focused, Ambitious and Achievable?"

3. **Three Required Reports**: The system must generate three specific PDF reports:
   - Strategy Summary Recommendation
   - Strategic Assessment Chart - Goals
   - Execution Chart - Goals

## Building Block Methodology

We're building this system one solid component at a time:

1. **Start with what we know works**: Build a reliable data extractor first
2. **Add one layer at a time**: Only move to the next component when the current one is solid
3. **Test thoroughly**: Verify each component before adding more complexity
4. **Keep it focused**: Each file and function should do one thing well

## Development Roadmap

### 1. Group Data Extractor (First Component)

**What it does**: Extracts and organizes data for each of the 30 assessment groups from CSV files.

**How it works**:
- Reads CSV files that contain business data
- Matches sections to the 30 groups defined in `blueprint.md`
- Uses group names and keywords for accurate matching
- Organizes the data by group, ready for analysis

**What success looks like**:
- Correctly identifies all 30 groups from the blueprint
- Extracts the right data for each group
- Handles missing or incomplete data gracefully
- Runs efficiently even with large files

### 2. Group Analyzer (Second Component)

**What it does**: Applies the specific questions from `blueprint.md` to each assessment group.

**How it works**:
- Takes the extracted group data
- For each group, uses the exact questions from the blueprint
- Uses local LLMs (via Ollama) to analyze the data
- Generates findings and preliminary recommendations for each group

**What success looks like**:
- Provides relevant answers to each group's questions
- Generates consistent, well-structured analysis
- Works with different LLMs like DeepSeek or Phi
- Adapts to various data quality levels

### 3. Knowledge Graph Integration (Third Component)

**What it does**: Stores entities and relationships in Neo4j to enable deeper analysis.

**How it works**:
- Takes the analysis results
- Maps business entities and their relationships to a graph structure
- Creates connections that reflect real business relationships
- Allows for querying complex patterns and relationships

**What success looks like**:
- Creates a graph that accurately represents the business
- Makes it easy to find connections between different assessment areas
- Supports the specific questions from the blueprint
- Scales well as more data is added

### 4. Report Generator (Fourth Component)

**What it does**: Creates the three PDF reports specified in the Qmirac blueprint.

**How it works**:
- Takes analysis results from the previous components
- Formats the data according to each report's requirements
- Generates visualizations that help understand the data
- Creates professional, readable PDF documents

**What success looks like**:
- Produces the exact three report types specified in the blueprint
- Clearly presents the findings and recommendations
- Includes helpful visualizations and metrics
- Makes complex business information easy to understand

### 5. Feedback Processor (Final Component)

**What it does**: Allows users to refine the analysis through follow-up questions.

**How it works**:
- Processes user questions about specific assessment areas
- Uses the knowledge graph to find relevant information
- Updates the analysis based on new insights or clarifications
- Enables an iterative improvement process

**What success looks like**:
- Makes the analysis better over time
- Maintains context between questions
- Updates recommendations as new information emerges
- Makes the system more useful through interaction

## Real-World Application

The system takes business data organized around the 30 groups from the blueprint and transforms it into actionable business insights. For example:

1. **Input**: CSV data about a company's vision statement, market position, financial metrics, etc.

2. **Processing**: The system extracts this data, analyzes it using the specific questions from the blueprint (e.g., "Is the Vision Statement Clear, concise, inspiring, future-focused, Ambitious and Achievable?"), and generates insights.

3. **Output**: Three detailed reports that help business leaders understand their current position and strategic options.

## Next Steps

We begin by building the Group Data Extractor that can reliably identify and extract data for all 30 assessment groups from CSV files. This component will be the foundation for everything else we build.

Once this is working well, we'll move on to applying the specific questions from the blueprint to each group, one solid component at a time.